r"""Intro music (user 2026-10-25; part of the /doc-edit new-video run since 2026-10-31, no separate command): fitted
so it ends where story 1 starts; then plan.py cuts the intro shots on its hits / bars and place.py lays it with the
body (music on A7, bin "4. Audio/Music"; --intro = only 0:00 -> story 1, for a re-cut).

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/intro.py <video>                 pick the best track + fit it
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/intro.py <video> "<music file>"  fit the user's track
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/intro.py --selftest

Pick (measured, never listened): candidates = D:\Music tracks with their Pixabay license beside them (user
2026-10-30; the library's music only when there is none); tracks already on this video's A7 after the intro and the
intro tracks of the 6 latest videos of the same channel and of every other film of this day project (from the folder
name before place.py wrote project.txt) are skipped; only 'căng, dồn dập' tracks (driving(): tense name, no calm
name, >= 90 BPM or >= 9.5 hits / 10 s, energy holds >= 85 %) are ranked, all when none is; user 2026-11-05: tense
cinematic, heavy drums, wild -> drum / tribal / war names rank higher (DRUM). The pick's license line is printed
(-> audio_licenses.md). An intro wants an early climax (loud within
~20 s) or a quiet, mysterious start that rises before ~45 s, hits to cut on (B3+ per 10 s), a steady tempo and energy
that holds. Profiles are cached in .work/library/intro_music.json (path + size + mtime).
Fit: the track's own start and ending stay; whole bars are cut out of the middle (track too long) or repeated there
(too short), joints on bar lines with short fades; the leftover (< 1 bar) comes off the tail with a fade.
Output: .work/doc_edit/<video>/intro_music.json only (source pieces + fades); no audio file is written (user
2026-10-26: all music work happens on the timeline) - place.py --intro lays the pieces on A7.
"""
import json, math, os, re, sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
from dvr_cowork.config import load_config  # noqa: E402
# user 2026-10-25: intro music outside the indexed library; audio_lib/intro = Epidemic / Suno intros (fetch.py, 2026-11-04)
MUSIC_DIRS = [Path(r"D:\Music"), Path(load_config()["paths"]["audio_lib"]) / "intro"]
EXTS = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"}
HINT = re.compile(r"open|intro|trailer|epic|tense|tension|suspense|dread|action|drum|war|dark|myster|tribal|percussi|"
                  r"wild|primal|savage|hunt|chase|battle|timpani|taiko")
DRUM = re.compile(r"drum|percussi|tribal|war|taiko|timpani|wild|primal|savage|battle")  # user 2026-11-05: heavy drums, wild
CALM = re.compile(r"calm|soft|peace|gentle|ambient|piano|lullaby|relax|sleep|meditat|romantic|happy")
RECENT = 6  # user 2026-10-30: never the intro music of the 6 latest videos of the same channel (Chann_N)
DRIVE_BPM, DRIVE_HITS, DRIVE_HOLD = 90, 9.5, 0.85  # user 2026-10-30: "căng, dồn dập" = tense name + fast or dense + holds
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


def score(p, path, T, cold=False):
    """cold (2026-11-06): the music enters on the cold open's impact, so it must be strong from its first bars: a
    quiet start that rises later gets no bonus."""
    c = p["climax"]
    form = 3.0 if c <= EARLY else 2.5 if p["quiet"] and c <= RISE and not cold else 1.0 if c <= RISE else 0.0
    name = Path(path).stem.lower()
    return round(form + min(p["hits10"], 4) / 2 + p["conf"] + 2 * p["hold"] + 0.5 * (p["len"] >= T)
                 + 0.5 * bool(HINT.search(name)) + 1.0 * bool(DRUM.search(name)), 2)


def channel_of(work):
    """'chann_2' from plan.json's video_dir D:/Chann_2_*/<video>, else None."""
    p = work / "plan.json"
    m = p.exists() and re.search(r"(?i)\bchann_(\d+)", json.loads(p.read_text("utf-8")).get("video_dir", ""))
    return f"chann_{m[1]}" if m else None


def recent_intros(doc, video, n=RECENT):
    """Intro tracks to skip: the n latest other videos of the same channel (newest first by file time; user
    2026-10-30) + the other videos of the same day project (two channels once got the same track)."""
    ch, day = channel_of(doc / video), day_of(doc / video)
    fs = sorted((f for f in doc.glob("*/intro_music.json") if f.parent.name != video),
                key=lambda f: f.stat().st_mtime, reverse=True)
    same = [f for f in fs if channel_of(f.parent) == ch][:n] + [f for f in fs if day_of(f.parent) == day]
    return {json.loads(f.read_text("utf-8"))["source"] for f in same}


def day_of(work):
    """Day project of a work folder: place.py's project.txt, else from the name (africa_051126_1__Chann_2 ->
    vid_051126_1, 2026-11-05: the second channel of a day got the first one's track before anything was placed)."""
    from dvr_cowork.videokey import day_project
    p = work / "project.txt"
    return (p.read_text("utf-8").split("/")[0].strip() if p.exists() else day_project(work.name)).lower()


def driving(p, path):
    """'căng, dồn dập' (user 2026-10-30): a tense / percussive name, fast (BPM) or dense hits, energy that holds."""
    name = Path(path).stem.lower()
    return bool(HINT.search(name)) and not CALM.search(name) and (p["bpm"] >= DRIVE_BPM or p["hits10"] >= DRIVE_HITS)         and p["hold"] >= DRIVE_HOLD


def candidates():
    """Intro music = D:\\Music tracks with their license beside them (user 2026-10-30; the license goes into
    audio_licenses.md at check-timelines / done); the library's music (plan.py AUDIO_POOL[7]) only when there is none."""
    import ledger
    from scan_source import audio_blocked
    music = [str(p) for d in MUSIC_DIRS if d.is_dir() for p in d.rglob("*") if p.suffix.lower() in EXTS
             and not audio_blocked(str(p))]
    lic = [p for p in music if ledger.pixabay_license(p) or ledger.sidecar_row(p)]
    if len(lic) < len(music):
        print(f"no license, skipped: {', '.join(Path(p).name for p in music if p not in lic)}")
    if lic:
        return sorted(lic)
    import plan
    print(f"no licensed track in {', '.join(map(str, MUSIC_DIRS))}: library music instead")
    return sorted({a["abs"] for a in plan.load_audio() if a["category"] in plan.AUDIO_POOL[7]})


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
    from dvr_cowork.videokey import video_key
    folder = next(d for d in vdir.iterdir() if d.is_dir() and any("timestamp" in p.name.lower() for p in d.glob("*.md")))
    cues, vo, _ = plan.narration(folder)
    spec = (ROOT / ".work" / "doc_edit" / video_key(vdir) / "spec.txt").read_text("utf-8")
    end, intro, blocks = plan.parse_spec(spec)
    slots = plan.build([c.t for c in cues], end or vo[-1][1] + 2.0, blocks, intro)
    f = next(s for s in slots if not s.get("intro"))
    return intro if f["filter"].get("sp") == ["none"] else f["start"]


def main(video, music=None):
    sys.path[:0] = [str(ROOT / ".claude/skills/scan-source/scripts"), str(ROOT)]
    from dvr_cowork.videokey import video_key
    work = ROOT / ".work" / "doc_edit" / video_key(video)
    pj = json.loads((work / "plan.json").read_text("utf-8"))
    vdir = Path(pj["video_dir"])
    T = story1(vdir)
    imp = None
    if pj["slots"][0].get("cold"):  # 2026-11-06: riser -> impact at 0:00, the music from the hit to story 1
        from dvr_cowork.coldopen import impact
        imp = impact(video_key(video))
        print(f"impact: {Path(imp['path']).name} (hit {imp['hit']}s, from {imp['src_in']}s -> lands at {imp['at']}s)")
    at = imp["at"] if imp else 0.0
    T = round(T - at, 3)
    print(f"intro: {at:g}s -> {(T + at) // 60:.0f}:{(T + at) % 60:04.1f} (story 1) = the music's length {T:.1f}s")
    if music:
        assert Path(music).is_file(), f"{music}: not a file"
        prof, bad = profiles([music])
        assert music in prof, f"{music}: not readable {bad}"
    else:
        body = {e["path"] for s in pj["slots"] if not s.get("intro") for e in s["audio"]
                if e["track"] == 7 and e.get("status") == "OK"}
        other = recent_intros(work.parent, video)
        if other:
            print(f"intro music of the {RECENT} latest videos of this channel + this day project skipped: {', '.join(Path(x).name for x in other)}")
        paths = [p for p in candidates() if p not in body | other]
        prof, bad = profiles(paths)
        drive = [p for p in prof if driving(prof[p], p)]
        print(f"tense + driving: {len(drive)} of {len(prof)}" + ("" if drive else " -> none: every candidate ranked"))
        # user 2026-11-05/06 "drum mạnh, hoang dã": a drum / tribal / war track always before any other, then the score
        rank = sorted(drive or prof, key=lambda p: (not DRUM.search(Path(p).stem.lower()), -score(prof[p], p, T, bool(imp))))
        for p in rank[:5]:
            x = prof[p]
            form = "early" if x["climax"] <= EARLY else "quiet->rise" if x["quiet"] and x["climax"] <= RISE else "late"
            print(f"  {score(x, p, T, bool(imp)):5.2f} climax {x['climax']:5.1f}s {form:11s} hits {x['hits10']}/10s "
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
        "len": round(T, 2), "how": how, "start": at, **({"impact": imp} if imp else {})}, ensure_ascii=False, indent=1), "utf-8")
    print(f"music: {Path(music).name} ({p['len']:.0f}s, {p['bpm']} BPM, bar {bar:.2f}s) -> {len(pieces)} pieces "
          f"on A7, {T:.2f}s ({how})")
    import ledger
    r = ledger.pixabay_row(music) or ledger.sidecar_row(music)
    print(f"license: {r[1]} ({r[2]} + {r[3]}) -> audio_licenses.md at check-timelines / done" if r else
          "license: NONE found beside the track (not Pixabay?): check .work/audio_licenses.md before done")


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
    q = dict(p, bpm=93.3, hits10=9.8, hold=0.89)
    assert driving(q, "x/alec_koff-drums-tribal-492753.mp3") and not driving(q, "x/lnplusmusic-cyberpunk-614539.mp3")
    assert not driving(dict(q, bpm=70, hits10=9.3), "x/suspense-background.mp3") and not driving(dict(q, hold=0.76), "x/war.mp3")
    import tempfile, time
    d = Path(tempfile.mkdtemp())
    for k in range(10):  # v0-v7 channel 1, v8 channel 2 same day as v7, v9 channel 2 other day
        (d / f"v{k}").mkdir()
        (d / f"v{k}" / "intro_music.json").write_text(json.dumps({"source": f"m{k}"}), "utf-8")
        (d / f"v{k}" / "plan.json").write_text(json.dumps({"video_dir": f"D:/Chann_{1 + (k > 7)}_x/v{k}"}), "utf-8")
        os.utime(d / f"v{k}" / "intro_music.json", (time.time() + k, time.time() + k))
    for k, day in ((7, "vid_1"), (8, "vid_1"), (9, "vid_2")):
        (d / f"v{k}" / "project.txt").write_text(f"{day}/Chann_{1 + (k > 7)}\n", "utf-8")
    assert recent_intros(d, "v7") == {"m6", "m5", "m4", "m3", "m2", "m1", "m8"}, recent_intros(d, "v7")
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    selftest() if "--selftest" in sys.argv else main(a[0], a[1] if len(a) > 1 else None)
