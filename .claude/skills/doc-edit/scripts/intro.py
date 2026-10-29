r"""/doc-edit intro (user 2026-10-25): the intro's music, fitted so it ends where story 1 starts; then plan.py cuts
the intro shots on its hits / bars and place.py --intro lays 0:00 -> story 1 on "Edit" (music on A7, bin "7. Open").

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/intro.py <video>                 pick the best track + fit it
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/intro.py <video> "<music file>"  fit the user's track
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/intro.py --selftest

Pick (measured, never listened): candidates = the library's music (plan.py AUDIO_POOL[7], blocked files out) +
D:\Music; tracks already on this video's A7 after the intro are skipped. An intro wants an early climax (loud within
~20 s) or a quiet, mysterious start that rises before ~45 s, hits to cut on (B3+ per 10 s), a steady tempo and energy
that holds. Profiles are cached in .work/library/intro_music.json (path + size + mtime).
Fit: the track's own start and ending stay; whole bars are cut out of the middle (track too long) or repeated there
(too short), joints on bar lines with short fades; the leftover (< 1 bar) comes off the tail with a fade.
Output: .work/doc_edit/<video>/intro_music.json only (source pieces + fades); no audio file is written (user
2026-10-26: all music work happens on the timeline) - place.py --intro lays the pieces on A7.
"""
import json, math, re, sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
MUSIC_DIRS = [Path(r"D:\Music")]  # user 2026-10-25: intro music outside the indexed library
EXTS = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"}
HINT = re.compile(r"open|intro|trailer|epic|tense|suspense|dread|action|drum|war|dark|myster")
CACHE = ROOT / ".work" / "library" / "intro_music.json"
SR = 22050
EARLY, RISE = 20.0, 45.0  # s: climax this early = "cao trào sớm"; a quiet start may rise until RISE
KEEP_HEAD, KEEP_TAIL = 8.0, 15.0  # s of the track's own start / ending never cut or repeated
XF_GRID, XF_FREE = 0.08, 0.6  # crossfade at a joint: on a trusted bar grid / free tempo


def loudness(a):
    """dB per 0.5 s, smoothed over 2 s."""
    hop = SR // 2
    n = len(a) // hop
    db = 20 * np.log10(np.sqrt((a[:n * hop].reshape(n, hop).astype(np.float64) ** 2).mean(1)) + 1e-6)
    return np.convolve(db, np.ones(4) / 4, "same")


def profile(path):
    import beats
    a = beats.decode(path)
    sm = loudness(a)
    peak = float(np.percentile(sm, 90))
    loud = np.where(sm > peak - 40)[0]
    end = (loud[-1] + 1) * 0.5 if len(loud) else len(a) / SR  # trailing silence is not the ending
    climax = float(np.argmax(sm >= peak - 3) * 0.5)
    after = sm[int(climax * 2):int(min(end, climax + 90) * 2)]
    m = beats.analyse(a[:int(min(end, 240) * SR)])
    hits = sum(1 for e in m["events"] if e["level"] >= 3 and climax <= e["t"] < climax + 60)
    return {"len": round(end, 2), "climax": climax, "quiet": bool(sm[:20].mean() <= peak - 9),
            "hold": round(float((after >= peak - 8).mean()) if len(after) else 0.0, 2),
            "hits10": round(hits / max(1.0, min(60.0, end - climax) / 10), 1), "bpm": m["bpm"], "conf": m["conf"],
            "bars": m["bars"]}


def score(p, path, T):
    c = p["climax"]
    form = 3.0 if c <= EARLY else 2.5 if p["quiet"] and c <= RISE else 1.0 if c <= RISE else 0.0
    return round(form + min(p["hits10"], 4) / 2 + p["conf"] + 2 * p["hold"] + 0.5 * (p["len"] >= T)
                 + 0.5 * bool(HINT.search(str(path).lower())), 2)


def candidates():
    import plan
    lib = [a["abs"] for a in plan.load_audio() if a["category"] in plan.AUDIO_POOL[7]]
    from scan_source import audio_blocked
    extra = [str(p) for d in MUSIC_DIRS if d.is_dir() for p in d.rglob("*") if p.suffix.lower() in EXTS
             and not audio_blocked(str(p))]
    return sorted(set(lib + extra))


def profiles(paths):
    cache = json.loads(CACHE.read_text("utf-8")) if CACHE.exists() else {}
    out, bad = {}, []
    for k, p in enumerate(paths):
        try:  # a file gone from the index's root (moved / renamed) is listed, never stops the pick
            st = Path(p).stat()
        except OSError:
            bad.append(f"{Path(p).name} (missing)")
            continue
        key = f"{p}|{st.st_size}|{int(st.st_mtime)}"
        if key not in cache:
            try:
                cache[key] = profile(p)
            except Exception as e:  # noqa: BLE001  one unreadable file never stops the pick
                bad.append(f"{Path(p).name} ({str(e)[:60]})")
                continue
            if k % 10 == 9:
                CACHE.write_text(json.dumps(cache), "utf-8")
        out[p] = cache[key]
    CACHE.write_text(json.dumps(cache), "utf-8")
    return out, bad


def grid_of(p):
    """(bar length s, first bar line, trusted) of a profile; free tempo -> a 2 s pseudo grid from 0."""
    b = p["bars"]
    if p["conf"] >= 0.15 and len(b) >= 8:
        return float(np.median(np.diff(b))), b[0] % float(np.median(np.diff(b))), True
    return 2.0, 0.0, False


def fit_plan(L, T, bar, ph, sm=None, climax=0.0):
    """Source pieces [(start, end)] played in order: their lengths sum to T' (T <= T' < T + bar), every jump between
    two bar lines (ph + k * bar). Too long: one jump forward over n bars in the middle; too short: jumps back from one
    bar line b by k_i bars (sum = n), the head [0, b] and the ending [b, L] stay. -> (pieces, T' - T, note)."""
    D = T - L
    lines = [ph + k * bar for k in range(int((L - ph) / bar) + 1)]
    lv = (lambda t: sm[min(len(sm) - 1, int(t * 2))]) if sm is not None else (lambda t: 0.0)  # noqa: E731
    for lo, hi in ((max(KEEP_HEAD, climax), L - KEEP_TAIL), (KEEP_HEAD, L - KEEP_TAIL), (0.0, L)):
        if D < 0:
            n = int(-D // bar)
            if n == 0:
                return [(0.0, L)], L - T, "length kept"
            opts = [a for a in lines if a >= lo and a + n * bar <= hi]
            if opts:
                a = min(opts, key=lambda a: (abs(lv(a) - lv(a + n * bar)), -a))
                return [(0.0, a), (a + n * bar, L)], L - n * bar - T, f"cut {n} bars at {a:.1f}s"
        else:
            n = math.ceil(D / bar)
            maxk = int((hi - lo) / bar)
            if maxk < 1:
                continue
            q = math.ceil(n / maxk)  # jumps back
            ks = [n // q + (i < n % q) for i in range(q)]
            opts = [b for b in lines if b - max(ks) * bar >= lo and b <= hi]
            if opts:
                b = min(opts, key=lambda b: (abs(lv(b) - lv(b - ks[0] * bar)), -b))
                pieces = [(0.0, b)] + [(b - k * bar, b) for k in ks[:-1]] + [(b - ks[-1] * bar, L)]
                return pieces, L + n * bar - T, f"{q}x repeat of {'/'.join(map(str, ks))} bars before {b:.1f}s"
    return [(0.0, L)], L - T, "no bar grid fits: length kept"


def story1(vdir):
    """Where the body starts (s) = intro end = music end, from the spec + narration: story 1 opening on a landscape is
    pulled to '# INTRO' by plan.py intro_outro() (and place --skip-intro starts there); else its first shot's start."""
    import plan
    folder = next(d for d in vdir.iterdir() if d.is_dir() and any("timestamp" in p.name.lower() for p in d.glob("*.md")))
    cues, vo, _ = plan.narration(folder)
    spec = (ROOT / ".work" / "doc_edit" / vdir.name / "spec.txt").read_text("utf-8")
    end, intro, blocks = plan.parse_spec(spec)
    slots = plan.build([c.t for c in cues], end or vo[-1][1] + 2.0, blocks, intro)
    f = next(s for s in slots if not s.get("intro"))
    return intro if f["filter"].get("sp") == ["none"] else f["start"]


def main(video, music=None):
    sys.path.insert(0, str(ROOT / ".claude/skills/scan-source/scripts"))
    work = ROOT / ".work" / "doc_edit" / video
    pj = json.loads((work / "plan.json").read_text("utf-8"))
    vdir = Path(pj["video_dir"])
    T = story1(vdir)
    print(f"intro: 0:00 -> {T // 60:.0f}:{T % 60:04.1f} (story 1) = the music's length")
    if music:
        assert Path(music).is_file(), f"{music}: not a file"
        prof, bad = profiles([music])
        assert music in prof, f"{music}: not readable {bad}"
    else:
        body = {e["path"] for s in pj["slots"] if not s.get("intro") for e in s["audio"]
                if e["track"] == 7 and e.get("status") == "OK"}
        # never another video's intro music (two channels in one day project once got the same track)
        other = {json.loads(f.read_text("utf-8"))["source"] for f in work.parent.glob("*/intro_music.json")
                 if f.parent.name != video}
        paths = [p for p in candidates() if p not in body | other]
        prof, bad = profiles(paths)
        rank = sorted(prof, key=lambda p: -score(prof[p], p, T))
        for p in rank[:5]:
            x = prof[p]
            form = "early" if x["climax"] <= EARLY else "quiet->rise" if x["quiet"] and x["climax"] <= RISE else "late"
            print(f"  {score(x, p, T):5.2f} climax {x['climax']:5.1f}s {form:11s} hits {x['hits10']}/10s "
                  f"{x['bpm']} BPM conf {x['conf']} hold {x['hold']:.0%} len {x['len']:.0f}s | {p}")
        print(f"candidates {len(prof)}" + (f"; unreadable {len(bad)}: {', '.join(bad[:5])}" if bad else ""))
        music = rank[0]
    p = prof[music]
    bar, ph, trusted = grid_of(p)
    import beats
    sm = loudness(beats.decode(music))
    pieces, extra, note = fit_plan(p["len"], T, bar, ph, sm, p["climax"])
    fade = round(min(3.0, max(1.0, extra)), 2) if extra > 0.05 else 0.0
    xf = XF_GRID if trusted else XF_FREE
    how = f"{note}; tail -{extra:.1f}s" + (f" fade {fade}s" if fade else "") + ("" if trusted else "; free tempo")
    # user 2026-10-26: no fitted file; place.py lays these source pieces back to back on A7 (timeline fades)
    (work / "intro_music.json").write_text(json.dumps({
        "source": music, "pieces": [[round(a, 4), round(b, 4)] for a, b in pieces], "xf": xf, "fade": fade,
        "len": round(T, 2), "how": how}, ensure_ascii=False, indent=1), "utf-8")
    print(f"music: {Path(music).name} ({p['len']:.0f}s, {p['bpm']} BPM, bar {bar:.2f}s) -> {len(pieces)} pieces "
          f"on A7, {T:.2f}s ({how})")


def selftest():
    # 100 s track, 2 s bars from 0.5 s: fit to 130 s (repeat) and 70 s (cut) keeps head + ending, joints on bars
    for T in (130.0, 70.0, 300.0):
        pieces, extra, note = fit_plan(100.0, T, 2.0, 0.5, None, 12.0)
        tot = sum(b - a for a, b in pieces)
        assert 0 <= extra < 2.0 and abs(tot - (T + extra)) < 1e-6, (T, pieces, extra)
        assert pieces[0][0] == 0.0 and pieces[-1][1] == 100.0, pieces  # own start and ending
        joints = [x for a, b in pieces for x in (a, b) if 0 < x < 100]
        assert all(abs((x - 0.5) / 2 - round((x - 0.5) / 2)) < 1e-6 for x in joints), joints
        assert all(KEEP_HEAD <= x <= 100 - KEEP_TAIL for x in joints), (T, joints)
    assert fit_plan(100.0, 99.0, 2.0, 0.5)[0] == [(0.0, 100.0)]  # < 1 bar too long: only the tail goes
    p = {"climax": 10.0, "quiet": False, "hits10": 3.0, "conf": 0.4, "hold": 0.8, "len": 120.0}
    assert score(p, "x/epic.mp3", 90) > score(dict(p, climax=60.0), "x/epic.mp3", 90)  # early climax wins
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    selftest() if "--selftest" in sys.argv else main(a[0], a[1] if len(a) > 1 else None)
