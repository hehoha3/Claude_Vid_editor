"""doc-edit step 3: plan.json -> timeline "Edit": V1 clips, audio A3-A9, markers (backup first).

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/place.py <video> [--replace] [--dry-run] [--video-only] [--a1-only]

<video> = name of the video folder (.work/doc_edit/<video>/plan.json from plan.py).
Refuses if V1 or A3-A9 already hold clips; --replace clears those tracks (after the backup). A2 is never touched.
--fill (after a re-plan with new footage): keeps every existing item, places only the plan's clips whose V1 range
is still empty (+ their A1 if free), removes the markers of those slots only; audio tracks untouched.
--fill --until <s>: only slots starting before <s> (e.g. a re-cut opening, the rest of the film's empty slots wait).
--skip-intro (default of a new video, user 2026-10-23): nothing before the plan's intro end; the user and Claude cut
the intro by hand later.
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
from dvr_cowork.resolve_ops import (_norm, audio_bin, clip_fps, ensure_audio_track, ensure_bin, find_bin,  # noqa: E402
                                    find_clip, find_timeline, get_project, timeline_fps)

# starting levels (integrated LUFS per clip); final mix is done by ear in Fairlight
TARGET = {3: -32, 4: -32, 5: -34, 6: -28, 7: -26, 8: -22, 9: -22}
BED_OVERLAP = 4.0
SFX_TAIL = 2.0  # s an A8/A9 hit may run past the end of its slot
A1_DB = -12  # AI clips bring their own audio to A1, this much below the clip level (user rule 2026-10-09)
FADE = {3: 4.0, 4: 4.0, 5: 2.0, 6: 0.5, 7: 3.0, 8: 0.0, 9: 0.0}
# video bins by what the clip shows (user 2026-10-22): attack / run first, everything else Other. audio: audio_bin(track)
BINS = {"other": "1. Other_roll", "attack": "2. Attack_roll", "run": "3. Run_roll"}
ATTACK, RUN = {"attack", "hunt", "chase", "catch", "fight"}, {"run"}  # tag "action" values (chase / catch = old hunt)
# untagged clips: the folder / file name (africa AI_copyright\AI\Chạy\...)
ATTACK_RE, RUN_RE = r"attack|hunt|fight|kill|tấn công|săn", r"(?<![a-z])run|chase|chạy|đuổi"
_ACTS = {}
MARK = {"THIEU": "Red", "WEAK": "Yellow", "FALLBACK": "Cyan", "GFX": "Blue"}


def bin_index(folder, out=None):
    """{normalised file path: media pool item} of a bin and all its sub-bins (resolve_ops.find_clip, walked once)."""
    out = {} if out is None else out
    for c in (folder.GetClipList() or []) if folder else []:
        try:
            out.setdefault(_norm(c.GetClipProperty("File Path")), c)
        except Exception:  # noqa: BLE001  same tolerance as find_clip
            continue
    for sub in (folder.GetSubFolderList() or []) if folder else []:
        bin_index(sub, out)
    return out


def clip_actions(path):
    """Tag actions of an indexed video clip (every video root's index, read once); [] when untagged / unknown."""
    if not _ACTS:
        sys.path.insert(0, str(ROOT / ".claude/skills/scan-source/scripts"))
        from scan_source import ROOTS, index_of
        for root, kind, _ in ROOTS.values():
            if kind == "video" and index_of(root).exists():
                for c in json.loads(index_of(root).read_text("utf-8"))["clips"].values():
                    _ACTS[_norm(str(root / c["path"]))] = (c.get("tags") or {}).get("action") or []
        _ACTS.setdefault("", [])
    return _ACTS.get(_norm(path), [])


def kind_of(path, acts):
    """attack | run | other: tags first (attack wins over run), else words in the folder / file name."""
    a = set(acts)
    if a:
        return "attack" if a & ATTACK else "run" if a & RUN else "other"
    p = path.lower()
    return "attack" if re.search(ATTACK_RE, p) else "run" if re.search(RUN_RE, p) else "other"


def video_bin(s):
    return BINS[kind_of(s["path"], clip_actions(s["path"]))]


def rebin():
    """Move every clip of the three video bins (and their sub-bins) into the bin its actions say; nothing else."""
    resolve = connect(load_config())
    pm, project = get_project(resolve)
    mp = project.GetMediaPool()
    bins = {k: ensure_bin(mp, v) for k, v in BINS.items()}
    moves, n = defaultdict(list), 0

    def walk(folder):
        nonlocal n
        for c in folder.GetClipList() or []:
            p = c.GetClipProperty("File Path") or ""
            if not p or c.GetClipProperty("Type") in ("Timeline", "Compound", "Audio"):
                continue
            n += 1
            k = kind_of(p, clip_actions(p))
            if folder.GetUniqueId() != bins[k].GetUniqueId():
                moves[k].append(c)
        for sub in folder.GetSubFolderList() or []:
            walk(sub)
    for b in bins.values():
        walk(b)
    for k, cl in moves.items():
        assert mp.MoveClips(cl, bins[k]), f"MoveClips into {BINS[k]} failed"
    pm.SaveProject()
    count = {k: len(b.GetClipList() or []) for k, b in bins.items()}
    print(f"video clips {n}; moved {sum(map(len, moves.values()))} "
          + ", ".join(f"-> {BINS[k]} {len(v)}" for k, v in moves.items())
          + " | now " + ", ".join(f"{BINS[k]} {v}" for k, v in count.items()))


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


def free(spans, a, b):
    """[a, b) overlaps none of spans (timeline frames)."""
    return all(b <= x or y <= a for x, y in spans)


def skip_intro(slots, t):
    """Slots from the intro end t on (user 2026-10-23: the intro is cut by hand with the user). A slot crossing t
    (story 1's landscape that intro_outro() pulled under the intro music) is trimmed to start at t."""
    out = []
    for s in slots:
        if s.get("intro") or s["start"] + s["dur"] <= t + 0.05:
            continue
        if s["start"] < t:
            cut = t - s["start"]
            s = dict(s, start=t, dur=s["dur"] - cut)
            if "src_in" in s:
                s["src_in"] += cut * s.get("speed", 1)
        out.append(s)
    return out


def main(video, replace=False, dry=False, video_only=False, a1_only=False, audio_only=False, fill=False, until=1e9,
         no_intro=False):
    work = ROOT / ".work" / "doc_edit" / video
    plan = json.loads((work / "plan.json").read_text("utf-8"))
    slots, end = plan["slots"], plan["end"]
    if no_intro:
        assert "intro" in plan, "plan.json has no intro end: re-run plan.py"
        slots = skip_intro(slots, plan["intro"])
        print(f"--skip-intro: V1/audio/markers from {plan['intro']:.1f}s on; 0:00-{plan['intro']:.1f}s left empty")
    events = [] if (video_only or a1_only or fill) else audio_events(slots, end)
    vids = [s for s in slots if s["status"] in ("OK", "WEAK", "FALLBACK")]
    if audio_only:  # --audio-only: A3-A9 only; V1, A1, A2 and the markers stay as they are
        vids = []
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
    # end frame = the next slot's start frame when they touch: start and dur are rounded to 0.01 s separately, so
    # f(start + dur) could land 1 frame past the next start and Resolve pushed every later clip (africa_1: +5 f drift)
    nxt = {(x["slot"], x["start"]): y["start"] for x, y in zip(slots, slots[1:]) if abs(x["start"] + x["dur"] - y["start"]) < 0.05}
    fe = lambda s: f(nxt.get((s["slot"], s["start"]), s["start"] + s["dur"]))  # split parts share a slot number  # noqa: E731
    tracks = [("audio", n) for n in range(3, 10)] if audio_only else [("audio", 1)] if a1_only else [("video", 1), ("audio", 1)] + ([] if video_only else [("audio", n) for n in range(3, 10)])
    have = {f"{k[0].upper()}{n}": tl.GetItemListInTrack(k, n) or [] for k, n in tracks
            if n <= int(tl.GetTrackCount(k) or 0)}
    full = {k: len(v) for k, v in have.items() if v}
    span = lambda k: [(int(i.GetStart()) - t0, int(i.GetEnd()) - t0) for i in have.get(k, [])]  # noqa: E731
    v1_used, a1_used = span("V1"), span("A1")
    if fill:  # user's timeline kept as is: only V1 slots still empty get their clip (new footage after a re-plan)
        vids = [s for s in vids if free(v1_used, f(s["start"]), fe(s)) and s["start"] < until]
        full = {}
        print(f"fill: {len(vids)} empty V1 slots get a clip; existing items untouched")
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
        from dvr_cowork.resolve_ops import backup_timeline
        assert backup_timeline(project, tl, bak), "backup failed, nothing changed"  # into bin "6. Timeline"
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
    # alternatives (user 2026-10-21): the next-best clips of every slot, THIẾU ones too, go into the same bins so the
    # user can swap a shot by hand; imported only, never placed. Old plan.json without "alts" -> nothing extra.
    chosen, alt = {_norm(s["path"]) for s in slots if "path" in s}, set()
    for p, src in {tuple(a) for s in slots if not (a1_only or audio_only) for a in s.get("alts", [])}:
        if _norm(p) not in chosen:
            need[video_bin({"source": src, "path": p})].add(p)
            alt.add(p)
    for e in events:
        need[audio_bin(e[0])].add(e[3])  # 4. Audio/Ambience | Music | SFX by track
    items, seen = {}, {}
    for name, paths in need.items():
        b = ensure_bin(mp, name)
        top = name.split("/")[0]  # whole "4. Audio": a file already in another sub-bin is reused
        if top not in seen:  # one walk of the bin, not one per file (hundreds of alternatives)
            seen[top] = bin_index(find_bin(root, top))
        new = []
        for p in sorted(paths):
            items[_norm(p)] = items.get(_norm(p)) or seen[top].get(_norm(p))
            if not items[_norm(p)]:
                new.append(os.path.normpath(p))
        if new:
            mp.SetCurrentFolder(b)
            for it in mp.ImportMedia(new) or []:
                items[_norm(it.GetClipProperty("File Path"))] = it
    n_alt = sum(1 for p in alt if items.get(_norm(p)))
    print(f"alternatives in bins 1-3: {n_alt}/{len(alt)} (not placed)")

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
        a, b = f(s["start"]), fe(s)
        if s["source"] == "ai" and free(a1_used, a, b):  # own audio on A1, lowered; no audio stream -> skipped
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
            # plan.py vary(): speed keeps the item length and in-point (ripple off), zoom = punch-in crop
            if s.get("speed", 1) != 1 and not ti.SetSpeed({"Percentage": round(s["speed"] * 100, 2), "RippleTimeline": False}):
                print(f"warning: speed {s['speed']} not set on slot {s['slot']}")
            if s.get("zoom", 1) != 1 and not (ti.SetProperty("ZoomX", s["zoom"]) and ti.SetProperty("ZoomY", s["zoom"])):
                print(f"warning: zoom {s['zoom']} not set on slot {s['slot']}")
            if (s.get("fade_in") or s.get("fade_out")) and not ti.SetFades(  # plan.py intro_outro(): dip to black
                    {"FadeIn": round(s.get("fade_in", 0) * fps), "FadeOut": round(s.get("fade_out", 0) * fps)}):
                print(f"warning: fades not set on slot {s['slot']}")
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

    placed = [(f(s["start"]), fe(s)) for s in vids]
    for frame, m in list((tl.GetMarkers() or {}).items()) if not audio_only else []:
        # fill: only the markers of slots filled now go (the user's other markers / notes stay)
        if str(m.get("customData", "")).startswith("doc_edit") and \
                (not fill or not free(placed, frame, frame + int(m.get("duration", 1)))):
            tl.DeleteMarkerAtFrame(frame)
    for s in slots if not (audio_only or fill) else [s for s in vids if s["status"] in MARK]:
        if s["status"] in MARK:
            a, b = f(s["start"]), fe(s)
            why = f" | {s['why']}" if re.search(r"_check|kiểm tra", str(s.get("why", ""))) else ""  # held clip / sex-age unseen
            why += (" | loại: " + ", ".join(f"{k} {n}" for k, n in s["rej"].items())) if s["status"] == "THIEU" and s.get("rej") else ""
            tl.AddMarker(a, MARK[s["status"]], f"{s['status']} #{s['slot']}", (s["need"] + why)[:240], b - a,
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
    if fill:  # what is still empty on V1 after this fill (the user's next decision), as mm:ss
        e, gaps = 0, []
        for t in v:
            a = int(t.GetStart()) - t0
            if a > e + 3:
                gaps.append(f"{int(e / f(1)) // 60:02d}:{e / f(1) % 60:04.1f}")
            e = max(e, int(t.GetEnd()) - t0)
        print(f"V1 still empty: {len(gaps)} gaps" + (": " + " ".join(gaps[:40]) if gaps else ""))


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
    assert free([(0, 10), (20, 30)], 10, 20) and not free([(0, 10)], 9, 12) and free([], 0, 5)  # --fill gaps
    assert kind_of("x", ["run", "hunt"]) == "attack" and kind_of("x", ["run"]) == "run" and kind_of("x", ["walk"]) == "other"
    assert kind_of(r"Z:\AI\Chạy\lion\a.mp4", []) == "run" and kind_of(r"D:\lion_hunts_zebra.mp4", []) == "attack"
    assert kind_of(r"Z:\savannah\brunei_grass.mov", []) == "other" and kind_of(r"D:\lion_runs.mp4", []) == "run"
    k = skip_intro([{"start": 0, "dur": 50, "intro": True}, {"start": 55, "dur": 40, "src_in": 2.0, "speed": 0.8},
                    {"start": 95, "dur": 3}], 90)  # intro shot gone, story 1's landscape trimmed to 90 s
    assert [(s["start"], s["dur"]) for s in k] == [(90, 5), (95, 3)] and abs(k[0]["src_in"] - 30.0) < 1e-9
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    until = float(sys.argv[sys.argv.index("--until") + 1]) if "--until" in sys.argv else 1e9  # --fill only slots starting before (s)
    selftest() if "--selftest" in sys.argv else rebin() if "--rebin" in sys.argv else main(a[0], "--replace" in sys.argv, "--dry-run" in sys.argv, "--video-only" in sys.argv, "--a1-only" in sys.argv, "--audio-only" in sys.argv, "--fill" in sys.argv, until, "--skip-intro" in sys.argv)
