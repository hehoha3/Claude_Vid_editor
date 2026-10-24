"""Beat / bar / hit map of one music file (numpy + ffmpeg, no tokens). plan.py snaps the intro cuts of "Edit" to it.
Analysis taken from the old intro-music-visualization music_map.py (2026-10-17). All numbers are measured, never "listened".

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/beats.py "<music file>" [seconds]
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/beats.py --selftest
"""
import subprocess, sys

import numpy as np

SR, HOP, NFFT = 22050, 256, 2048
FPS = SR / HOP
LOW, HIGH = (30, 160), (2500, 9000)  # Hz: kick / bass / sub / braam vs. snare / hats / percussion
MIN_GAP = 0.12  # s between two onsets
CLUSTER = 0.35  # onsets this close = one hit
JUMP_CAP = 24   # dB; a hit out of silence is not 50 dB "stronger" than one inside the music
FLUX_LAG = 0.03  # s; a flux peak (frame centre) comes this much before the onset (measured on synthetic kicks)


def decode(path, t0=0.0, t1=None):
    cmd = ["ffmpeg", "-v", "error", "-ss", str(t0)] + (["-to", str(t1)] if t1 else []) + \
          ["-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32).copy()


def bands(a):
    """-> frame times, rms dB, low-band flux, high-band flux (log magnitude, half-wave rectified), raw low-band magnitude."""
    n = 1 + max(0, len(a) - NFFT) // HOP
    f = np.fft.rfftfreq(NFFT, 1 / SR)
    lo_m, hi_m = (f >= LOW[0]) & (f < LOW[1]), (f >= HIGH[0]) & (f < HIGH[1])
    lo, hi, rms = np.zeros(n), np.zeros(n), np.zeros(n)
    win = np.hanning(NFFT).astype(np.float32)
    for s in range(0, n, 2048):  # chunks: a 3 min track would need ~250 MB in one go
        fr = a[np.arange(NFFT)[None, :] + HOP * np.arange(s, min(n, s + 2048))[:, None]]
        mag = np.abs(np.fft.rfft(fr * win, axis=1))
        lo[s:s + len(fr)], hi[s:s + len(fr)] = mag[:, lo_m].sum(1), mag[:, hi_m].sum(1)
        rms[s:s + len(fr)] = 20 * np.log10(np.sqrt((fr.astype(np.float64) ** 2).mean(1)) + 1e-6)

    def flux(m):
        m = np.log1p(100 * m)
        return np.maximum(0, np.diff(m, prepend=m[0]))
    return (np.arange(n) * HOP + NFFT / 2) / SR, rms, flux(lo), flux(hi), lo


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


def grid(env, low, bpm):
    """Fit a constant beat grid (tempo +-3 %, every phase) -> (bpm, beat times, bar starts).
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


def analyse(a):
    """-> {bpm, conf, beats, bars, events: [{t, level 1-5, ...}]}; t = loudness peak of a hit = the cut point."""
    t, rms, lf, hf, lraw = bands(a)
    med = float(np.median(rms))
    groups = []  # onsets closer than CLUSTER = one hit (a drum fill / braam is several onsets)
    for i in sorted(set(peaks(lf, t)) | set(peaks(hf, t, 2.5))):
        if groups and t[i] - t[groups[-1][0]] <= CLUSTER:
            groups[-1].append(i)
        else:
            groups.append([i])
    ev = []
    for g in groups:
        a0, a1 = g[0], min(len(rms), g[-1] + int(0.15 * FPS) + 1)
        pk = a0 + int(np.argmax(rms[a0:a1]))
        before = rms[max(0, a0 - int(FPS) // 2):max(1, a0 - 2)].mean()
        ev.append({"t": round(float(t[pk]), 2), "n": len(g), "jump": round(float(min(rms[pk] - before, JUMP_CAP)), 1),
                   "low": round(float(lf[g].max() / (lf.max() + 1e-9)), 2),
                   "high": round(float(hf[g].max() / (hf.max() + 1e-9)), 2), "db": round(float(rms[pk] - med), 1)})
    bpm, conf = tempo(lf + 0.5 * hf)
    bpm, beats, bars = grid(lf + 0.5 * hf, lraw, bpm) if bpm else (None, [], [])
    m = {"bpm": bpm, "conf": conf, "beats": [round(float(x), 3) for x in beats],
         "bars": [round(float(x), 3) for x in bars], "events": []}
    if not ev:
        return m
    s = np.array([max(e["jump"], 0) / 8 + 2 * e["low"] + 0.5 * e["high"] + max(e["db"], -20) / 10 + 0.1 * min(e["n"], 6)
                  for e in ev])
    q = np.quantile(s, [0.3, 0.6, 0.85])
    top = set(np.argsort(-s)[:max(2, min(6, round(len(a) / SR / 20)))])
    for k, e in enumerate(ev):
        e["score"] = round(float(s[k]), 2)
        e["level"] = 5 if k in top else 1 + int(np.searchsorted(q, s[k]))
    merged = []  # two clusters landing on the same loudness peak = one hit
    for e in ev:
        if merged and e["t"] - merged[-1]["t"] < 0.15:
            if e["score"] > merged[-1]["score"]:
                merged[-1] = e
        else:
            merged.append(e)
    m["events"] = merged
    return m


def selftest():
    # 3 s quiet pad, then a kick every 0.5 s (120 BPM) with an accent every 4th, a loud hit at 5.0 s (a downbeat)
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
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        selftest()
    else:
        m = analyse(decode(sys.argv[1], 0, float(sys.argv[2]) if len(sys.argv) > 2 else None))
        print(f"{m['bpm']} BPM (conf {m['conf']}) bars " + " ".join(f"{x:.2f}" for x in m["bars"][:16]))
        print("hits B3+: " + " ".join(f"{e['t']:.2f}/B{e['level']}" for e in m["events"] if e["level"] >= 3))
