"""doc-edit step 3: plan.json -> timeline "Edit": V1 clips, audio A3-A9, markers (backup first).

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/place.py <video> [--replace] [--dry-run] [--video-only] [--a1-only]

<video> = name of the video folder (.work/doc_edit/<video>/plan.json from plan.py).
Refuses if V1 or A3-A9 already hold clips; --replace clears those tracks (after the backup). A2 is never touched.
Audio rules: A3/A4 entry = bed change, the bed alternates A3/A4 with BED_OVERLAP crossfades until the next change;
A5 / A7 run from their slot until the next entry on that track, 'off', or the timeline end (looped by
re-placing the file); A1 = own audio of every AI clip on V1 at A1_DB (--a1-only adds just that, nothing else touched); A6 = its slot only; A8/A9 = one hit at the slot start (moves to the other SFX track if busy).
"""
import datetime as dt, json, os, re, subprocess, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from dvr_cowork.config import load_config  # noqa: E402
from dvr_cowork.resolve_conn import connect  # noqa: E402
from dvr_cowork.resolve_ops import (_norm, clip_fps, ensure_audio_track, find_bin, find_clip,  # noqa: E402
                                    find_timeline, get_project, timeline_fps)

# starting levels (integrated LUFS per clip); final mix is done by ear in Fairlight
TARGET = {3: -32, 4: -32, 5: -34, 6: -28, 7: -26, 8: -22, 9: -22}
BED_OVERLAP = 4.0
SFX_TAIL = 2.0  # s an A8/A9 hit may run past the end of its slot
A1_DB = -12  # AI clips bring their own audio to A1, this much below the clip level (user rule 2026-10-09)
FADE = {3: 4.0, 4: 4.0, 5: 2.0, 6: 0.5, 7: 3.0, 8: 0.0, 9: 0.0}
BINS = {"A_roll": "1. A_roll", "B_roll": "2. B_roll", "ai": "3. AI_roll", "audio": "4. Audio"}
MARK = {"THIEU": "Red", "WEAK": "Yellow", "FALLBACK": "Cyan", "GFX": "Blue"}


def video_bin(s):
    if s["source"] == "ai":
        return BINS["ai"]
    return BINS["B_roll"] if re.search(r"[\\/](landscape|supplementary_shots)[\\/]", s["path"], re.I) else BINS["A_roll"]


def loudness(path, cache):
    if path not in cache:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128", "-f", "null", "-"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
        cache[path] = float(m[-1]) if m else None
    return cache[path]


def audio_events(slots, end):
    """-> list of (track, start, length, path, src_in) pieces, seconds."""
    out, spans = [], defaultdict(list)  # track -> [(start, path|None)]
    for s in slots:
        for e in s["audio"]:
            tr = 3 if e["track"] in (3, 4) else e["track"]
            if tr in (3, 5, 7):
                spans[tr].append((s["start"], e.get("path") if e.get("status") == "OK" else None))
            elif e.get("status") == "OK":
                # A6 = its slot; A8/A9 hits ring at most SFX_TAIL into the next shot (a 104 s water file once ran
                # from 12:34 to 14:19 over three other scenes)
                ln = min(e["dur"], s["dur"] + (SFX_TAIL if tr in (8, 9) else 0))
                out.append([tr, s["start"], ln, e["path"], 0.0])
    i = 0  # bed piece counter, global so a bed change lands on the other track
    for tr, ch in spans.items():
        ch.append((end, None))
        for (t0, p), (t1, _) in zip(ch, ch[1:]):
            if not p:
                continue
            dur = next(e["dur"] for s in slots for e in s["audio"] if e.get("path") == p)
            if tr == 7:  # music plays once, never looped
                out.append([7, t0, min(dur, t1 - t0), p, 0.0])
                continue
            t = t0
            if tr == 3:  # alternate A3/A4; each piece overlaps the next by BED_OVERLAP (also across bed changes)
                if dur <= 2 * BED_OVERLAP:
                    print(f"warning: bed {Path(p).name} only {dur}s, skipped")
                    continue
                while t < t1 - BED_OVERLAP:
                    ln = min(dur, t1 + (BED_OVERLAP if t1 < end else 0) - t)
                    out.append([3 + i % 2, t, ln, p, 0.0])
                    i += 1
                    t += ln - BED_OVERLAP
            else:
                while t < t1 - 0.5:
                    ln = min(dur, t1 - t)
                    out.append([tr, t, ln, p, 0.0])
                    t += ln
    # SFX: A8 busy -> A9, both busy -> drop
    busy = {8: 0.0, 9: 0.0}
    for ev in sorted((e for e in out if e[0] in (8, 9)), key=lambda e: e[1]):
        free = [k for k in (ev[0], 17 - ev[0]) if busy[k] <= ev[1]]
        ev[0] = free[0] if free else 0
        if free:
            busy[ev[0]] = ev[1] + ev[2]
    return sorted((e for e in out if e[0]), key=lambda e: (e[1], e[0]))


def main(video, replace=False, dry=False, video_only=False, a1_only=False):
    work = ROOT / ".work" / "doc_edit" / video
    plan = json.loads((work / "plan.json").read_text("utf-8"))
    slots, end = plan["slots"], plan["end"]
    events = [] if (video_only or a1_only) else audio_events(slots, end)
    vids = [s for s in slots if s["status"] in ("OK", "WEAK", "FALLBACK")]
    print(f"plan: {len(vids)} video clips, {len(events)} audio pieces, "
          f"{sum(s['status'] in MARK for s in slots)} markers")

    cfg = load_config()
    resolve = connect(cfg)
    pm, project = get_project(resolve)
    tl = find_timeline(project, cfg["resolve"]["timeline_name"])
    assert tl, f'timeline "{cfg["resolve"]["timeline_name"]}" not found'
    assert tl.GetName().lower() != "master", 'timeline "Master" is never touched'
    orig = project.GetCurrentTimeline()  # the timeline the user has open; restored at the end
    project.SetCurrentTimeline(tl)
    fps = timeline_fps(tl, project)
    rate = round(fps) if cfg["align"].get("timestamp_clock", "timecode") == "timecode" else fps
    t0 = int(tl.GetStartFrame())
    f = lambda sec: round(sec * rate)  # noqa: E731
    tracks = [("audio", 1)] if a1_only else [("video", 1), ("audio", 1)] + ([] if video_only else [("audio", n) for n in range(3, 10)])
    have = {f"{k[0].upper()}{n}": tl.GetItemListInTrack(k, n) or [] for k, n in tracks
            if n <= int(tl.GetTrackCount(k) or 0)}
    full = {k: len(v) for k, v in have.items() if v}
    if full and not replace:
        raise SystemExit(f"tracks not empty {full}; re-run with --replace to clear them (backup is made first)")
    if a1_only and not [s for s in slots if s["source"] == "ai" and s["status"] in ("OK", "WEAK", "FALLBACK")]:
        raise SystemExit("no AI clips in plan")
    if dry:
        print("dry-run: nothing changed")
        return

    mp = project.GetMediaPool()
    root = mp.GetRootFolder()
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    mp.SetCurrentFolder(root)
    if not a1_only:  # A1-only is purely additive on an empty track: no backup needed
        bak = f"{tl.GetName()}_bak_place_{stamp}"
        assert tl.DuplicateTimeline(bak), "backup failed, nothing changed"
        project.SetCurrentTimeline(tl)
        print("backup:", bak)
    if full:
        tl.DeleteClips([ti for v in have.values() for ti in v], False)
        print("cleared:", full)
    ensure_audio_track(tl, 9, 2, print)

    # import every needed file once, into its bin
    need = defaultdict(set)
    for s in vids:
        need[video_bin(s)].add(s["path"])
    for e in events:
        need[BINS["audio"]].add(e[3])
    items = {}
    for name, paths in need.items():
        b = find_bin(root, name) or mp.AddSubFolder(root, name)
        new = []
        for p in sorted(paths):
            items[_norm(p)] = find_clip(b, p)
            if not items[_norm(p)]:
                new.append(os.path.normpath(p))
        if new:
            mp.SetCurrentFolder(b)
            for it in mp.ImportMedia(new) or []:
                items[_norm(it.GetClipProperty("File Path"))] = it

    failed = []

    def put(path, media, track, rec, n, src_in):
        """Place exactly n timeline frames. endFrame is exclusive; clips at another fps are conformed with
        rounding, so measure the placed length and re-place with a corrected source length (max 3 tries)."""
        it = items.get(_norm(path))
        if not it:
            failed.append(Path(path).name); return None
        cf = clip_fps(it, fps)
        a, k = round(src_in * cf), round(n * cf / fps)
        for _ in range(3):
            res = mp.AppendToTimeline([{"mediaPoolItem": it, "startFrame": a, "endFrame": a + k,
                                        "mediaType": media, "trackIndex": track, "recordFrame": t0 + rec}])
            ti = res[0] if res else None
            if not ti:
                break
            d = int(ti.GetEnd()) - int(ti.GetStart())
            if d == n:
                return ti
            tl.DeleteClips([ti], False)
            k += round((n - d) * cf / fps) or (1 if n > d else -1)
        failed.append(Path(path).name)
        return None

    dev = v1 = a1 = 0
    for s in vids:
        a, b = f(s["start"]), f(s["start"] + s["dur"])
        if s["source"] == "ai":  # the clip's own audio on A1, lowered; clips without an audio stream are skipped
            n0 = len(failed)
            au = put(s["path"], 2, 1, a, b - a, s["src_in"])
            if au:
                a1 += bool(au.SetProperty("AudioVolume", A1_DB))
            else:
                del failed[n0:]
        if a1_only:
            continue
        ti = put(s["path"], 1, 1, a, b - a, s["src_in"])
        if ti:
            v1 += 1
            dev = max(dev, abs(int(ti.GetStart()) - t0 - a))
            if s["status"] in ("WEAK", "FALLBACK"):
                ti.SetClipColor("Yellow" if s["status"] == "WEAK" else "Cyan")

    cache_p = work.parent / "loudness.json"
    cache = json.loads(cache_p.read_text("utf-8")) if cache_p.exists() else {}
    vol_fail = 0
    for tr, start, ln, path, src_in in events:
        ti = put(path, 2, tr, f(start), f(start + ln) - f(start), src_in)
        if not ti:
            continue
        fd = round(min(FADE[tr], ln / 2) * rate)
        if fd:
            ti.SetFades({"FadeIn": fd, "FadeOut": fd})
        lu = loudness(path, cache)
        if lu is not None and not ti.SetProperty("AudioVolume", round(TARGET[tr] - lu, 1)):
            vol_fail += 1
    cache_p.write_text(json.dumps(cache, indent=0), "utf-8")

    for frame, m in list((tl.GetMarkers() or {}).items()):
        if str(m.get("customData", "")).startswith("doc_edit"):
            tl.DeleteMarkerAtFrame(frame)
    for s in slots:
        if s["status"] in MARK:
            a, b = f(s["start"]), f(s["start"] + s["dur"])
            tl.AddMarker(a, MARK[s["status"]], f"{s['status']} #{s['slot']}", s["need"][:240], b - a,
                         f"doc_edit:slot{s['slot']}")
    pm.SaveProject()
    if orig and orig.GetName() != tl.GetName():
        project.SetCurrentTimeline(orig)
        print(f'back on timeline "{orig.GetName()}"')
    v = sorted(tl.GetItemListInTrack("video", 1) or [], key=lambda t: t.GetStart())
    small = sum(1 for x, y in zip(v, v[1:]) if 0 < int(y.GetStart()) - int(x.GetEnd()) <= 3)
    print(f"V1 gaps of 1-3 frames: {small}; A1 audio of AI clips: {a1} at {A1_DB} dB")
    print(f"V1 placed {v1}/{len(vids)}, max start dev {dev}f; audio pieces {len(events) - (len(failed) - (len(vids) - v1))}"
          f"/{len(events)}; volume not set on {vol_fail}; failed: {failed[:20]}")


def selftest():
    S = lambda st, du, au: {"start": st, "dur": du, "audio": au}  # noqa: E731
    bed = lambda p, d: {"track": 3, "kw": ["x"], "status": "OK", "path": p, "dur": d}  # noqa: E731
    slots = [S(0, 300, [bed("a", 116), {"track": 8, "kw": ["x"], "status": "OK", "path": "h", "dur": 3}]),
             S(300, 2, [{"track": 8, "kw": ["x"], "status": "OK", "path": "h2", "dur": 3},
                        {"track": 7, "kw": ["x"], "status": "OK", "path": "m", "dur": 100}]),
             S(302, 298, [bed("b", 60), {"track": 8, "kw": ["x"], "status": "OK", "path": "h3", "dur": 3}]),
             S(600, 1, [{"track": 7, "kw": ["off"]}])]
    ev = audio_events(slots, 601.0)
    for tr in range(3, 10):
        p = sorted((e[1], e[1] + e[2]) for e in ev if e[0] == tr)
        assert all(a[1] <= b[0] + 1e-6 for a, b in zip(p, p[1:])), f"A{tr} overlaps: {p}"
    bed_p = sorted((e[1], e[1] + e[2]) for e in ev if e[0] in (3, 4))
    assert bed_p[0][0] == 0 and abs(max(b for _, b in bed_p) - 601) < 1e-6  # bed covers the whole timeline
    assert all(b[0] < a[1] for a, b in zip(bed_p, bed_p[1:]))  # no holes between bed pieces
    assert [e[0] for e in ev if e[3] == "h2"] == [8] and [e[2] for e in ev if e[3] == "m"] == [100]
    long = audio_events([S(0, 3, [{"track": 8, "kw": ["x"], "status": "OK", "path": "w", "dur": 104}])], 10.0)
    assert [e[2] for e in long] == [3 + SFX_TAIL], long  # a long SFX file is cut to its slot + tail
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    selftest() if "--selftest" in sys.argv else main(a[0], "--replace" in sys.argv, "--dry-run" in sys.argv, "--video-only" in sys.argv, "--a1-only" in sys.argv)
