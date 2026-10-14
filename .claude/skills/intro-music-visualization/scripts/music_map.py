"""intro-music-visualization: music (one file, a part of it, or several parts spliced) -> beat / bar / hit map.
numpy + ffmpeg, no tokens, nothing written to Resolve.

    .venv/Scripts/python.exe .claude/skills/intro-music-visualization/scripts/music_map.py --name <name> "<file>[@in-out]" ["<file2>@in-out" ...] [--show 3]
    .venv/Scripts/python.exe .claude/skills/intro-music-visualization/scripts/music_map.py --selftest

Pieces are placed back to back (timeline 0:00 = start of the first piece); every time printed is intro-timeline seconds.
Later pieces get a gain so their loud level matches the first; joins get JOIN_FADE, a piece cut before its file end gets
END_FADE. build.py places the music exactly like this (it reads the pieces from music_map.json).

Prints per piece: tempo (+ confidence), key (+ confidence), bar starts (downbeats on a fitted beat grid);
then the loudness arc per second, breaks, and the hits B1-B5 (level = loudness jump into the hit + low-band size).
Hit flags: entry = hit right after >= 1 s of quiet (a drop, good splice-in point), exit = hit followed by a fall-off
(a final hit, good place to end or splice out). All numbers are measured, never "listened".
"""
import json, subprocess, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / ".work" / "intro_mv"
SR, HOP, NFFT = 22050, 256, 2048
FPS = SR / HOP
LOW, HIGH = (30, 160), (2500, 9000)  # Hz: kick / bass / sub / braam vs. snare / hats / percussion
MIN_GAP = 0.12  # s between two onsets
CLUSTER = 0.35  # onsets this close = one hit
JUMP_CAP = 24   # dB; a hit out of silence is not 50 dB "stronger" than one inside the music
SILENT = -18    # dB below the track's median loudness = break
QUIET = -8      # dB vs median: 1 s before a hit (entry) / 0.5-2.5 s after it (exit)
JOIN_FADE, END_FADE = 0.08, 1.5  # s
FLUX_LAG = 0.03  # s; a flux peak (frame centre) comes this much before the onset (measured on synthetic kicks)
GAIN_MAX = 10   # dB
NOTES = "C C# D D# E F F# G G# A A# B".split()
MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]  # Krumhansl-Kessler
MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def decode(path, t0=0.0, t1=None):
    cmd = ["ffmpeg", "-v", "error", "-ss", str(t0)] + (["-to", str(t1)] if t1 else []) + \
          ["-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32).copy()


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def bands(a):
    """-> frame times, rms dB, low-band flux, high-band flux (log magnitude, half-wave rectified), chroma (12),
    raw low-band magnitude (accents: log flux hides how hard a kick is)."""
    n = 1 + max(0, len(a) - NFFT) // HOP
    f = np.fft.rfftfreq(NFFT, 1 / SR)
    lo_m, hi_m, pc_m = (f >= LOW[0]) & (f < LOW[1]), (f >= HIGH[0]) & (f < HIGH[1]), (f >= 55) & (f < 2000)
    pc = np.round(12 * np.log2(f[pc_m] / 440) + 69).astype(int) % 12
    lo, hi, rms, chroma = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(12)
    win = np.hanning(NFFT).astype(np.float32)
    for s in range(0, n, 2048):  # chunks: a 3 min track would need ~250 MB in one go
        idx = np.arange(NFFT)[None, :] + HOP * np.arange(s, min(n, s + 2048))[:, None]
        fr = a[idx]
        mag = np.abs(np.fft.rfft(fr * win, axis=1))
        lo[s:s + len(fr)], hi[s:s + len(fr)] = mag[:, lo_m].sum(1), mag[:, hi_m].sum(1)
        rms[s:s + len(fr)] = 20 * np.log10(np.sqrt((fr.astype(np.float64) ** 2).mean(1)) + 1e-6)
        chroma += np.bincount(pc, (mag[:, pc_m] ** 2).sum(0), 12)
    def flux(m):
        m = np.log1p(100 * m)
        return np.maximum(0, np.diff(m, prepend=m[0]))
    return (np.arange(n) * HOP + NFFT / 2) / SR, rms, flux(lo), flux(hi), chroma, lo


def peaks(x, t, k=1.5):
    """Local maxima above median + k*MAD, at least MIN_GAP apart (strongest wins)."""
    thr = np.median(x) + k * np.median(np.abs(x - np.median(x))) + 1e-9
    cand = np.where((x > thr) & (x >= np.roll(x, 1)) & (x >= np.roll(x, -1)))[0]
    keep = []
    for i in cand[np.argsort(-x[cand])]:
        if all(abs(t[i] - t[j]) >= MIN_GAP for j in keep):
            keep.append(i)
    return sorted(keep)


def tempo(env):
    """Autocorrelation of the onset envelope in 60-180 BPM -> (bpm, confidence 0-1). Low confidence = free tempo."""
    e = env - env.mean()
    ac = np.correlate(e, e, "full")[len(e) - 1:]
    lo, hi = int(FPS * 60 / 180), int(FPS * 60 / 60)
    if hi >= len(ac) or ac[0] <= 0:
        return None, 0.0
    lag = lo + int(np.argmax(ac[lo:hi]))
    return 60 * FPS / lag, round(float(ac[lag] / ac[0]), 2)


def grid(env, low, bpm):  # low = raw low-band magnitude
    """Fit a constant beat grid (tempo +-3 %, every phase) to the onset envelope -> (bpm, beat times, bar starts).
    Downbeat = the beat of 4 with the most low-band energy."""
    best = (-1.0, bpm, 0.0)
    for b in np.arange(bpm * 0.97, bpm * 1.03, 0.05):
        p = 60 * FPS / b
        k = np.arange(int((len(env) - 1) / p))
        for ph in np.arange(0.0, p, 1.0):
            s = env[(ph + k * p).astype(int)].mean()
            if s > best[0]:
                best = (s, b, ph)
    _, b, ph = best
    p = 60 * FPS / b
    idx = (ph + np.arange(int((len(env) - 1 - ph) / p) + 1) * p).astype(int)
    acc = np.array([low[max(0, i - 1):i + 5].max() for i in idx])  # flux peaks ~2 frames before the hit's body
    j = max(range(4), key=lambda j: acc[j::4].mean() if len(acc[j::4]) else -1)
    t = (idx * HOP + NFFT / 2) / SR + FLUX_LAG
    return round(float(b), 1), t, t[j::4]


def key(chroma):
    z = lambda v: (np.asarray(v) - np.mean(v)) / np.std(v)  # noqa: E731
    c = z(chroma)
    best = max((float(np.dot(c, z(np.roll(prof, k)))) / 12, NOTES[k] + (" major" if prof is MAJOR else " minor"))
               for prof in (MAJOR, MINOR) for k in range(12))
    return best[1], round(best[0], 2)


def analyse(a):
    t, rms, lf, hf, chroma, lraw = bands(a)
    med = float(np.median(rms))
    on = sorted(set(peaks(lf, t)) | set(peaks(hf, t, 2.5)))
    groups = []  # onsets closer than CLUSTER = one hit (a drum fill / braam is several onsets)
    for i in on:
        if groups and t[i] - t[groups[-1][0]] <= CLUSTER:  # anchored, so dense hats cannot chain a section
            groups[-1].append(i)
        else:
            groups.append([i])
    ev = []
    sec = int(FPS)
    for g in groups:
        a0, a1 = g[0], min(len(rms), g[-1] + int(0.15 * FPS) + 1)
        pk = a0 + int(np.argmax(rms[a0:a1]))  # where the hit lands = loudest frame of the cluster: the cut point
        before = rms[max(0, a0 - sec // 2):max(1, a0 - 2)].mean()
        pre = rms[max(0, a0 - sec):max(1, a0 - 4)].mean() - med if a0 > sec // 2 else 0.0
        post = rms[pk + sec // 2:pk + int(2.5 * FPS)].mean() - med if pk + sec < len(rms) else -60.0
        ev.append({"t": round(float(t[pk]), 2), "on": round(float(t[a0]), 2), "n": len(g),
                   "jump": round(float(min(rms[pk] - before, JUMP_CAP)), 1),
                   "low": round(float(lf[g].max() / (lf.max() + 1e-9)), 2),
                   "high": round(float(hf[g].max() / (hf.max() + 1e-9)), 2), "db": round(float(rms[pk] - med), 1),
                   "pre": round(float(pre), 1), "post": round(float(post), 1)})
    m = {"duration": round(len(a) / SR, 2), "arc": [], "breaks": [], "events": []}
    bpm, conf = tempo(lf + 0.5 * hf)
    m["key"], m["key_conf"] = key(chroma)
    m["conf"] = conf
    m["bpm"], beats, bars = grid(lf + 0.5 * hf, lraw, bpm) if bpm else (None, [], [])
    m["beats"], m["bars"] = [round(float(x), 3) for x in beats], [round(float(x), 3) for x in bars]
    if not ev:
        return m
    s = np.array([max(e["jump"], 0) / 8 + 2 * e["low"] + 0.5 * e["high"] + max(e["db"], -20) / 10 + 0.1 * min(e["n"], 6)
                  for e in ev])
    q = np.quantile(s, [0.3, 0.6, 0.85])
    top = set(np.argsort(-s)[:max(2, min(6, round(len(a) / SR / 20)))])
    for k, e in enumerate(ev):
        e["score"] = round(float(s[k]), 2)
        e["level"] = 5 if k in top else 1 + int(np.searchsorted(q, s[k]))
        e["kind"] = "bass" if e["low"] >= e["high"] else "perc"
        e["flag"] = ("entry " if e["pre"] <= QUIET and e["level"] >= 3 else "") + \
                    ("exit" if e["post"] <= QUIET and e["level"] >= 3 else "")
    merged = []  # two clusters landing on the same loudness peak = one hit
    for e in ev:
        if merged and e["t"] - merged[-1]["t"] < 0.15:
            if e["score"] > merged[-1]["score"]:
                e["on"] = merged[-1]["on"]; merged[-1] = e
        else:
            merged.append(e)
    m["events"] = merged
    m["arc"] = [round(float(rms[i:i + sec].mean() - med)) for i in range(0, len(rms), sec)]
    quiet = rms < med + SILENT
    i = 0
    while i < len(quiet):
        if quiet[i]:
            j = i
            while j < len(quiet) and quiet[j]:
                j += 1
            if t[j - 1] - t[i] >= 0.4:
                m["breaks"].append([round(float(t[i]), 2), round(float(t[j - 1]), 2)])
            i = j
        i += 1
    return m


def loud(a):
    """Loud level of a piece: 90th percentile of 0.1 s RMS in dB."""
    n = SR // 10
    r = [np.sqrt(np.mean(a[i:i + n] ** 2)) for i in range(0, len(a) - n, n)] or [1e-6]
    return float(20 * np.log10(np.percentile(r, 90) + 1e-6))


def fade(a, n_in, n_out):
    a = a.copy()
    if n_in:
        a[:n_in] *= np.linspace(0, 1, n_in, dtype=np.float32)
    if n_out:
        a[-n_out:] *= np.linspace(1, 0, n_out, dtype=np.float32)
    return a


def compose(specs):
    """'file@in-out' list -> (audio, pieces). Gain matches each piece to the first; fades as build.py places them."""
    pieces, parts, tl = [], [], 0.0
    for k, sp in enumerate(specs):
        path, _, rng = sp.partition("@")
        full = duration(path)
        a_in, _, a_out = rng.partition("-")
        a_in, a_out = float(a_in or 0), float(a_out or full)
        a = decode(path, a_in, a_out)
        last = k == len(specs) - 1
        p = {"path": str(Path(path)), "in": a_in, "out": round(a_in + len(a) / SR, 3), "tl": round(tl, 3),
             "fade_in": JOIN_FADE if (k or a_in > 0.3) else 0.0,
             "fade_out": (END_FADE if a_out < full - 0.5 else 0.0) if last else JOIN_FADE, "loud": loud(a)}
        p["gain"] = 0.0 if not k else float(np.clip(round(2 * (pieces[0]["loud"] - p["loud"])) / 2, -GAIN_MAX, GAIN_MAX))
        sub = analyse(a)
        p.update(bpm=sub["bpm"], conf=sub["conf"], key=sub["key"], key_conf=sub["key_conf"],
                 bars=[round(x + tl, 3) for x in sub["bars"]], beats=[round(x + tl, 3) for x in sub["beats"]])
        parts.append(fade(a * np.float32(10 ** (p["gain"] / 20)), int(p["fade_in"] * SR), int(p["fade_out"] * SR)))
        pieces.append(p)
        tl += len(a) / SR
    return np.concatenate(parts), pieces


def report(m, show=3):
    for k, p in enumerate(m["pieces"], 1):
        print(f"piece {k}: {Path(p['path']).name} {p['in']:.2f}-{p['out']:.2f} s -> timeline {p['tl']:.2f} | "
              f"{p['bpm']} BPM (conf {p['conf']}) | {p['key']} ({p['key_conf']}) | gain {p['gain']:+.1f} dB | "
              f"fades {p['fade_in']}/{p['fade_out']} s")
        b = p["bars"]
        for i in range(0, len(b), 14):
            print(("  bars " if not i else "       ") + " ".join(f"{x:.2f}" for x in b[i:i + 14]))
    print(f"duration {m['duration']} s (tempo conf < 0.3 = free tempo: trust the hits, not the bars)")
    print("arc dB vs median, 1 s steps:")
    for i in range(0, len(m["arc"]), 20):
        print(f"  {i:3d}s " + " ".join(f"{v:+3d}" for v in m["arc"][i:i + 20]))
    print("breaks:", ", ".join(f"{a}-{b}" for a, b in m["breaks"]) or "none")
    lv = [e["level"] for e in m["events"]]
    print("hits:", len(lv), " ".join(f"B{k}={lv.count(k)}" for k in range(1, 6)))
    print("hit(cut) onset  lvl kind  n  jump  low  high  dB    gap  flag")
    prev = None
    for e in m["events"]:
        if e["level"] >= show:
            gap = f"{e['t'] - prev:5.2f}" if prev is not None else "     "
            print(f"{e['t']:7.2f} {e['on']:7.2f}  B{e['level']} {e['kind']:4s} {e['n']:2d} {e['jump']:+5.1f} {e['low']:.2f} "
                  f"{e['high']:.2f} {e['db']:+5.1f} {gap}  {e['flag']}")
            prev = e["t"]


def main(argv):
    name = argv[argv.index("--name") + 1]
    show = int(argv[argv.index("--show") + 1]) if "--show" in argv else 3
    specs = [x for i, x in enumerate(argv) if not x.startswith("--") and (i == 0 or argv[i - 1] not in ("--name", "--show"))]
    a, pieces = compose(specs)
    m = analyse(a)
    m["pieces"] = pieces
    out = OUT / name / "music_map.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(m, indent=0), "utf-8")
    report(m, show)
    print(f"-> {out}")


def selftest():
    # 3 s quiet pad, then a kick every 0.5 s (120 BPM) with an accent every 4th, a loud hit at 5.0 s (a downbeat), silence from 7 s
    t = np.arange(int(9 * SR)) / SR
    a = 0.002 * np.random.default_rng(0).standard_normal(len(t)).astype(np.float32)
    for i, k in enumerate(np.arange(3.0, 7.0, 0.5)):
        g = (t >= k) & (t < k + 0.15)
        amp = 0.9 if k == 5.0 else 0.5 if i % 4 == 0 else 0.25
        a[g] += amp * np.sin(2 * np.pi * 55 * (t[g] - k)) * np.exp(-(t[g] - k) * 20)
    a[t >= 7] = 0.0
    m = analyse(a.astype(np.float32))
    ts = [e["t"] for e in m["events"]]
    assert all(any(abs(x - k) < 0.08 for x in ts) for k in np.arange(3.0, 7.0, 0.5)), ts
    assert any(abs(e["t"] - 5.0) < 0.08 for e in m["events"] if e["level"] == 5), "5.0 s hit must be B5"
    assert m["bpm"] and abs(m["bpm"] - 120) < 4, m["bpm"]
    assert any(abs(b - 3.0) < 0.06 for b in m["bars"]) and any(abs(b - 5.0) < 0.06 for b in m["bars"]), m["bars"]
    assert m["breaks"] and m["breaks"][-1][0] < 7.3, m["breaks"]
    assert "exit" in next(e for e in m["events"] if abs(e["t"] - 6.5) < 0.08)["flag"]  # last kick before the silence
    tone = np.sin(2 * np.pi * np.outer([220.0, 261.63, 329.63], t[:SR * 2]).astype(np.float32)).sum(0)  # A C E
    assert key(bands(tone.astype(np.float32))[4])[0] in ("A minor", "C major"), key(bands(tone.astype(np.float32))[4])
    assert np.allclose(fade(np.ones(10, np.float32), 5, 0)[:5], np.linspace(0, 1, 5))
    print("selftest ok")


if __name__ == "__main__":
    selftest() if sys.argv[1:] == ["--selftest"] else main(sys.argv[1:])
