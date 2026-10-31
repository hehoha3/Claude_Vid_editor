"""doc-edit step 3: plan.json -> timeline "Edit": V1 clips, audio A3-A9, markers (backup first).

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/place.py <video> [--replace] [--dry-run] [--video-only] [--a1-only]

<video> = name of the video folder (.work/doc_edit/<video>/plan.json from plan.py).
Refuses if V1 or A3-A9 already hold clips; --replace clears those tracks (after the backup). A2 is never touched.
--fill (after a re-plan with new footage): keeps every existing item, places only the plan's clips whose V1 range
is still empty (+ their A1 if free), removes the markers of those slots only; audio tracks untouched.
--fill --until <s>: only slots starting before <s> (e.g. a re-cut opening, the rest of the film's empty slots wait).
A new video (user 2026-10-31: intro in the same run, no separate /doc-edit intro) = intro.py, plan.py, then a plain
place: intro + body at once. The intro music (its source file, user 2026-10-26: no fitted file) goes into bin
"7. Open" as intro.py's bar pieces back to back on A7, short fades at the joints, the tail fade on the last, the 1 s
from black; story 1's bed pre-laps the black before story 1 on A5 (prelap()).
--skip-intro: nothing before the plan's intro end (videos placed before 2026-10-31 left 0:00-intro empty).
--intro: only 0:00 -> the plan's intro end, on V1 / A1 / A3-A9 + its markers; that range must be empty (an intro
re-cut, or the videos placed with --skip-intro).
Every run: items at 0:00 fade in from black EDGE_IN, items at the video end fade out EDGE_OUT (not A2).
Multi-channel project: plan.json's video_dir D:/Chann_N_*/... -> bins and "Edit" inside bin Chann_N (resolve_ops).
Audio rules: A3/A4 entry = bed change, the bed alternates A3/A4 with BED_OVERLAP crossfades until the next change;
A5 / A7 run from their slot until the next entry on that track, 'off', or the timeline end (looped by
re-placing the file); A1 = own audio of every AI clip on V1 starting before A1_UNTIL (08:00) at A1_DB (--a1-only adds just that, nothing else touched); A6 = its slot only; A8/A9 = one hit at the slot start (moves to the other SFX track if busy).
"""
import datetime as dt, json, os, re, subprocess, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from dvr_cowork.config import load_config  # noqa: E402
from dvr_cowork.resolve_conn import connect  # noqa: E402
from dvr_cowork.resolve_ops import (_norm, audio_bin, clip_fps, ensure_audio_track, ensure_bin, find_bin, pool_root, use_channel,  # noqa: E402
                                    find_clip, find_timeline, get_project, timeline_fps)

# starting levels (integrated LUFS per clip); final mix is done by ear in Fairlight
TARGET = {3: -32, 4: -32, 5: -34, 6: -28, 7: -26, 8: -22, 9: -22}
BED_OVERLAP = 4.0
SFX_TAIL = 2.0  # s an A8/A9 hit may run past the end of its slot
A1_DB = -12  # AI clips bring their own audio to A1, this much below the clip level (user rule 2026-10-09)
A1_UNTIL = 480.0  # s: A1 only for shots starting before 08:00; later AI clips get no A1 audio (user 2026-10-28)
FADE = {3: 4.0, 4: 4.0, 5: 2.0, 6: 0.5, 7: 3.0, 8: 0.0, 9: 0.0}
EDGE_IN, EDGE_OUT = 1.0, 3.0  # s: the video opens from black / ends to black on every track but A2 (user 2026-10-26)
BIRD_ON, BIRD_OFF = 30.0, 30.0  # s: a birds bed = one bird file this long, then the non-bird bed, next time another bird (user 2026-10-27)
PRELAP = 4.0  # s: --intro, story 1's bed on A5 fades in this long before the black after the intro (user 2026-10-26)
# video bins by what the clip shows (user 2026-10-22): attack / run first, everything else Other. audio: audio_bin(track)
BINS = {"other": "1. Other_roll", "attack": "2. Attack_roll", "run": "3. Run_roll"}
ATTACK, RUN = {"attack", "hunt", "chase", "catch", "fight"}, {"run"}  # tag "action" values (chase / catch = old hunt)
# untagged clips: the folder / file name (africa AI_copyright\AI\Chạy\...)
ATTACK_RE, RUN_RE = r"attack|hunt|fight|kill|tấn công|săn", r"(?<![a-z])run|chase|chạy|đuổi"
_ACTS = {}
OPEN_BIN = "7. Open"  # intro music (intro.py)
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


def bed_pieces(cue, p, dur, last, on=BIRD_ON, off=BIRD_OFF):
    """Endless (path, file length, max s on its own) for one A3/A5 cue. A birds cue with plan.py's "birds" / "rest"
    (user 2026-10-27: no bird file looped) alternates BIRD_ON s of a bird file and BIRD_OFF s of the non-bird bed, each
    bird stretch the next file, never the one heard last (last = [path], shared by all cues); else p looped."""
    birds, rest = cue.get("birds"), cue.get("rest")
    if not birds:
        while True:
            yield p, dur, dur
    k = 0
    while True:
        if birds[k % len(birds)][0] == last[0] and len(birds) > 1:
            k += 1
        bp, bd = birds[k % len(birds)]
        last[0], k = bp, k + 1
        yield bp, bd, on
        if rest:
            yield rest[0], rest[1], off


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
    last_bird = [None]
    for tr, ch in spans.items():
        ch.append((end, None))
        for (t0, p), (t1, _) in zip(ch, ch[1:]):
            if not p:
                continue
            cue = next(e for s in slots for e in s["audio"] if e.get("path") == p)
            dur = cue["dur"]
            if tr == 7 and cue.get("pieces"):  # intro.py: the source's bar pieces back to back, timeline fades
                t, xs = t0, cue["pieces"]
                for i, (a, b) in enumerate(xs):
                    ln = min(b - a, t0 + dur - t)
                    if ln <= 0:
                        break
                    last = i == len(xs) - 1 or t + ln >= t0 + dur - 1e-6
                    out.append([7, t, ln, p, a, (cue["xf"] if i else 0.0, cue["fade"] if last else cue["xf"])])
                    t += ln
                continue
            if tr == 7:  # music plays once, never looped
                out.append([7, t0, min(dur, t1 - t0), p, 0.0])
                continue
            t, gen = t0, bed_pieces(cue, p, dur, last_bird)
            if tr == 3:  # alternate A3/A4; each piece overlaps the next by BED_OVERLAP (also across bed changes)
                if dur <= 2 * BED_OVERLAP:
                    print(f"warning: bed {Path(p).name} only {dur}s, skipped")
                    continue
                while t < t1 - BED_OVERLAP:
                    pp, d, cap = next(gen)
                    ln = min(d, cap + BED_OVERLAP, t1 + (BED_OVERLAP if t1 < end else 0) - t)
                    out.append([3 + i % 2, t, ln, pp, 0.0])
                    i += 1
                    t += ln - BED_OVERLAP
            else:
                while t < t1 - 0.5:
                    pp, d, cap = next(gen)
                    ln = min(d, cap, t1 - t)
                    out.append([tr, t, ln, pp, 0.0])
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


def only_intro(slots, t):
    """Slots before the intro end t, the last one trimmed to t (--intro, the mirror of skip_intro)."""
    return [dict(s, dur=min(s["dur"], t - s["start"])) for s in slots if s["start"] < t - 0.05]


def edge_fade(a, b, d, fi, fo, end, fps):
    """New (FadeIn, FadeOut) frames of an item [a, b) d frames long: from black at 0:00, to black at the video end;
    an existing longer fade stays, SetFades fails on a fade longer than the item (africa_4's last shot: 2.79 s)."""
    return (max(fi, round(EDGE_IN * fps)) if a == 0 else fi,
            max(fo, min(round(EDGE_OUT * fps), d - 7)) if b >= end - 1 else fo)


def edge_fades(tl, t0, fps, end):
    """edge_fade() on V1, A1, A3-A9 (A2: the narrator's first / last word stay whole). end = video end frame. -> set."""
    n = 0
    for kind, k in [("video", 1)] + [("audio", k) for k in range(1, int(tl.GetTrackCount("audio") or 0) + 1) if k != 2]:
        for ti in tl.GetItemListInTrack(kind, k) or []:
            old = ti.GetFades() or {}
            fi, fo = int(old.get("FadeIn", 0)), int(old.get("FadeOut", 0))
            new = edge_fade(int(ti.GetStart()) - t0, int(ti.GetEnd()) - t0, int(ti.GetDuration()), fi, fo, end, fps)
            if new != (fi, fo):
                n += bool(ti.SetFades({"FadeIn": new[0], "FadeOut": new[1]}))
    return n


def black_fades(video):
    """The 4 black fades on V1 of <video>'s "Edit" (user rule): from black on the first shot + story 1's first shot, to
    black on the last intro shot + the last shot (intro ones: plan.json fade_in / fade_out, else 2.5 / 1.5 s). Only a
    missing / shorter fade is set, then read back and saved. Called by ledger.render_done before every render and by
    hide_logo --overwrite-all after it reopens the project (2026-10-30: V1 fades were lost on that reopen). -> line."""
    from dvr_cowork.resolve_ops import CHANNEL_ENV, find_timeline
    plan = json.loads((ROOT / ".work" / "doc_edit" / video / "plan.json").read_text("utf-8"))
    m, env = re.search(r"(?i)\bchann_(\d+)", plan.get("video_dir", "")), os.environ.get(CHANNEL_ENV)
    if m:  # this video's channel, whatever was set before (overwrite-all walks several videos)
        os.environ[CHANNEL_ENV] = f"Chann_{m[1]}"
    try:
        pm = connect(load_config()).GetProjectManager()
        pr = pm.GetCurrentProject()
        tl = find_timeline(pr, "Edit")
        if not tl:
            return f"black fades {video}: no Edit in {pr.GetName()}"
        cur = pr.GetCurrentTimeline()
        pr.SetCurrentTimeline(tl)
        fps, t0 = timeline_fps(tl, pr), int(tl.GetStartFrame())
        f = lambda s: round(s * fps)  # noqa: E731
        v = sorted(tl.GetItemListInTrack("video", 1) or [], key=lambda i: int(i.GetStart()))
        slot = {f(s["start"]): s for s in plan["slots"]}
        k = sum(int(i.GetStart()) - t0 < f(plan.get("intro", 0)) - 1 for i in v)  # intro items before story 1
        want = [(0, f(EDGE_IN), 0), (len(v) - 1, 0, min(f(EDGE_OUT), int(v[-1].GetDuration()) - 7))] if v else []
        if 0 < k < len(v):
            want += [(k - 1, 0, f(slot.get(int(v[k - 1].GetStart()) - t0, {}).get("fade_out") or 1.5)),
                     (k, f(slot.get(int(v[k].GetStart()) - t0, {}).get("fade_in") or 2.5), 0)]
        fixed, bad = 0, []
        for j, fi, fo in want:
            g = v[j].GetFades() or {}
            old = (int(g.get("FadeIn", 0)), int(g.get("FadeOut", 0)))
            new = (max(old[0], fi), max(old[1], fo))
            if new != old:
                fixed += 1
                v[j].SetFades({"FadeIn": new[0], "FadeOut": new[1]})
                g = v[j].GetFades() or {}
                if (int(g.get("FadeIn", 0)), int(g.get("FadeOut", 0))) != new:
                    bad.append(f"{(int(v[j].GetStart()) - t0) / fps:.1f}s")
        if fixed:
            pm.SaveProject()
        if cur:
            pr.SetCurrentTimeline(cur)
        return f"black fades {video}: {len(want)} checked, {fixed} re-set" + (f", NOT SET at {bad}" if bad else "")
    finally:
        if env is None:
            os.environ.pop(CHANNEL_ENV, None)
        else:
            os.environ[CHANNEL_ENV] = env


def prelap(tl, mp, t0, fps, body):
    """Intro placed (--intro or a full place): story 1's bed (its A3/A4 piece at the body start, frame `body`) is heard through the black before it
    (plan.py GAP_BLACK): a slice of the same file's end on A5 from PRELAP s before the black to PRELAP s into the bed,
    fading in / out PRELAP (the bed itself fades in 4 s from the body start), at the bed's volume. -> summary."""
    bed = [ti for k in (3, 4) for ti in tl.GetItemListInTrack("audio", k) or [] if abs(int(ti.GetStart()) - t0 - body) <= 1]
    black = max((int(ti.GetEnd()) - t0 for ti in tl.GetItemListInTrack("video", 1) or [] if int(ti.GetEnd()) - t0 <= body),
                default=body)
    if not bed:
        return "pre-lap: no A3/A4 bed at story 1, skipped"
    bed, p = bed[0], round(PRELAP * fps)
    a, b = black - p, body + p
    if not free([(int(ti.GetStart()) - t0, int(ti.GetEnd()) - t0) for ti in tl.GetItemListInTrack("audio", 5) or []], a, b):
        return "pre-lap: A5 busy there, skipped"
    it = bed.GetMediaPoolItem()
    cf = float(it.GetClipProperty("FPS") or fps)
    total = bed.GetSourceStartFrame() + round((int(bed.GetDuration()) + int(bed.GetRightOffset())) * cf / fps)
    k = round((b - a) * cf / fps)
    if k > total - round(0.2 * cf):
        return "pre-lap: bed file too short, skipped"
    s_end = total - round(0.2 * cf)  # the file's end: the A3 piece plays its start, no doubled birds
    res = mp.AppendToTimeline([{"mediaPoolItem": it, "startFrame": s_end - k, "endFrame": s_end, "mediaType": 2,
                                "trackIndex": 5, "recordFrame": t0 + a}])
    if not res:
        return "pre-lap: AppendToTimeline failed"
    res[0].SetFades({"FadeIn": p, "FadeOut": p})
    res[0].SetProperty("AudioVolume", bed.GetProperty("AudioVolume"))
    return f"pre-lap: {bed.GetName()} on A5 {a / fps:.1f}-{(int(res[0].GetEnd()) - t0) / fps:.1f}s, black from {black / fps:.1f}s"


def intro_end(plan):
    """Where the body begins: story 1's first shot, or the intro end when that shot was pulled under it (s)."""
    return max(plan["intro"], next((s["start"] for s in plan["slots"] if not s.get("intro")), plan["intro"]))


def main(video, replace=False, dry=False, video_only=False, a1_only=False, audio_only=False, fill=False, until=1e9,
         no_intro=False, intro_only=False):
    work = ROOT / ".work" / "doc_edit" / video
    plan = json.loads((work / "plan.json").read_text("utf-8"))
    use_channel(plan.get("video_dir"))  # D:\Chann_N_*\<video>: that channel's bins and "Edit" (multi-channel project)
    slots, end = plan["slots"], plan["end"]
    if intro_only:  # --intro: 0:00 -> intro end on every track, the rest of the timeline untouched
        end = intro_end(plan)
        slots = only_intro(slots, end)
        print(f"--intro: V1/A1/A3-A9/markers 0:00-{end:.1f}s only")
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
    if intro_only:  # only the intro range must be empty; --replace never clears whole tracks here
        full = {k: n for k, v in have.items() if (n := sum(int(i.GetStart()) - t0 < f(end) for i in v))}
        if full:
            raise SystemExit(f"intro range 0:00-{end:.1f}s not empty {full}: nothing changed")
    span = lambda k: [(int(i.GetStart()) - t0, int(i.GetEnd()) - t0) for i in have.get(k, [])]  # noqa: E731
    v1_used, a1_used = span("V1"), span("A1")
    if fill:  # user's timeline kept as is: only V1 slots still empty get their clip (new footage after a re-plan)
        vids = [s for s in vids if free(v1_used, f(s["start"]), fe(s)) and s["start"] < until]
        full = {}
        print(f"fill: {len(vids)} empty V1 slots get a clip; existing items untouched")
    if full and not replace:
        raise SystemExit(f"tracks not empty {full}; re-run with --replace to clear them (backup is made first)")
    if a1_only and not [s for s in slots if s["source"] == "ai" and s["start"] < A1_UNTIL and s["status"] in ("OK", "WEAK", "FALLBACK")]:
        raise SystemExit("no AI clips in plan")
    if dry:
        print("dry-run: nothing changed")
        return

    mp = project.GetMediaPool()
    root = pool_root(mp)  # the channel's bin in a multi-channel project
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
        # 4. Audio/Ambience | Music | SFX by track; the intro's music -> "7. Open" (user 2026-10-25)
        need[OPEN_BIN if e[0] == 7 and (intro_only or len(e) > 5) else audio_bin(e[0])].add(e[3])  # len 6 = intro piece
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
        if s["source"] == "ai" and s["start"] < A1_UNTIL and free(a1_used, a, b):  # own audio on A1 (< 08:00), lowered
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
    for tr, start, ln, path, src_in, *fade in events:
        ti = put(path, 2, tr, f(start), f(start + ln) - f(start), src_in)
        if not ti:
            continue
        fd = 0 if intro_only and tr == 7 else round(min(FADE[tr], ln / 2) * rate)  # intro music: own start / end
        fi, fo = (round(x * rate) for x in fade[0]) if fade else (fd, fd)  # intro pieces: bar joints + tail fade
        if fi or fo:
            ti.SetFades({"FadeIn": fi, "FadeOut": fo})
        lu = loudness(path, cache)
        if lu is not None and not ti.SetProperty("AudioVolume", round(TARGET[tr] - lu, 1)):
            vol_fail += 1
    cache_p.write_text(json.dumps(cache, indent=0), "utf-8")

    placed = [(f(s["start"]), fe(s)) for s in vids]
    for frame, m in list((tl.GetMarkers() or {}).items()) if not audio_only else []:
        # fill: only the markers of slots filled now go (the user's other markers / notes stay)
        if str(m.get("customData", "")).startswith("doc_edit") and (not intro_only or frame < f(end)) and \
                (not fill or not free(placed, frame, frame + int(m.get("duration", 1)))):
            tl.DeleteMarkerAtFrame(frame)
    for s in slots if not (audio_only or fill) else [s for s in vids if s["status"] in MARK]:
        if s["status"] in MARK:
            a, b = f(s["start"]), fe(s)
            why = f" | {s['why']}" if re.search(r"_check|kiểm tra", str(s.get("why", ""))) else ""  # held clip / sex-age unseen
            why += (" | loại: " + ", ".join(f"{k} {n}" for k, n in s["rej"].items())) if s["status"] == "THIEU" and s.get("rej") else ""
            tl.AddMarker(a, MARK[s["status"]], f"{s['status']} #{s['slot']}", (s["need"] + why)[:240], b - a,
                         f"doc_edit:slot{s['slot']}")
    if intro_only or any(len(e) > 5 for e in events):  # --intro, or a full place with intro.py's pieces (len 6)
        print(prelap(tl, mp, t0, fps, f(intro_end(plan))))
    print(f"edge fades (from / to black): {edge_fades(tl, t0, fps, f(plan['end']))} items")
    pm.SaveProject()
    from dvr_cowork.resolve_ops import CHANNEL_ENV, channel_bin
    if channel_bin(mp):  # which day project / channel holds this video (plan.same_project: color, intro)
        (work / "project.txt").write_text(f"{project.GetName()}/{os.environ[CHANNEL_ENV]}\n", "utf-8")
    if orig and orig.GetName() != tl.GetName():
        project.SetCurrentTimeline(orig)
        print(f'back on timeline "{orig.GetName()}"')
    v = sorted(tl.GetItemListInTrack("video", 1) or [], key=lambda t: t.GetStart())
    small = sum(1 for x, y in zip(v, v[1:]) if 0 < int(y.GetStart()) - int(x.GetEnd()) <= 3)
    print(f"V1 gaps of 1-3 frames: {small}; A1 audio of AI clips: {a1} at {A1_DB} dB (before {A1_UNTIL // 60:.0f}:00 only)")
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
    # birds bed (user 2026-10-27): bird BIRD_ON s -> non-bird bed -> another bird file; A5 the same without overlaps
    bc = dict(bed("b1", 90), birds=[["b1", 90], ["b2", 60]], rest=["w", 120])
    for tr in (3, 5):
        ev = [e for e in audio_events([S(0, 200, [dict(bc, track=tr)])], 200.0) if e[0] in (3, 4, 5)]
        assert [e[3] for e in ev][:5] == ["b1", "w", "b2", "w", "b1"], ev
        assert all(e[2] <= BIRD_ON + BED_OVERLAP for e in ev) and abs(max(e[1] + e[2] for e in ev) - 200) < 1e-6
    long = audio_events([S(0, 3, [{"track": 8, "kw": ["x"], "status": "OK", "path": "w", "dur": 104}])], 10.0)
    assert [e[2] for e in long] == [3 + SFX_TAIL], long  # a long SFX file is cut to its slot + tail
    im = {"track": 7, "kw": ["intro"], "status": "OK", "path": "src", "dur": 90.0, "pieces": [[0, 40], [60, 112]],
          "xf": 0.08, "fade": 1.5}  # intro.py: 20 s cut out of a 112 s track, 2 s tail off
    ip = [e for e in audio_events([S(0, 90, [im])], 90.0) if e[0] == 7]
    assert [(e[1], e[2], e[4], e[5]) for e in ip] == [(0, 40, 0, (0.0, 0.08)), (40, 50, 60, (0.08, 1.5))], ip
    assert free([(0, 10), (20, 30)], 10, 20) and not free([(0, 10)], 9, 12) and free([], 0, 5)  # --fill gaps
    assert kind_of("x", ["run", "hunt"]) == "attack" and kind_of("x", ["run"]) == "run" and kind_of("x", ["walk"]) == "other"
    assert kind_of(r"Z:\AI\Chạy\lion\a.mp4", []) == "run" and kind_of(r"D:\lion_hunts_zebra.mp4", []) == "attack"
    assert kind_of(r"Z:\savannah\brunei_grass.mov", []) == "other" and kind_of(r"D:\lion_runs.mp4", []) == "run"
    k = skip_intro([{"start": 0, "dur": 50, "intro": True}, {"start": 55, "dur": 40, "src_in": 2.0, "speed": 0.8},
                    {"start": 95, "dur": 3}], 90)  # intro shot gone, story 1's landscape trimmed to 90 s
    assert [(s["start"], s["dur"]) for s in k] == [(90, 5), (95, 3)] and abs(k[0]["src_in"] - 30.0) < 1e-9
    E = 86400  # video end frame at 24 fps; first shot / last 2.79 s shot / mid shot / bed with its own 4 s fades
    assert edge_fade(0, 85, 85, 0, 0, E, 24) == (24, 0) and edge_fade(E - 67, E, 67, 0, 0, E, 24) == (0, 60)
    assert edge_fade(100, 200, 100, 0, 0, E, 24) == (0, 0) and edge_fade(0, E, E, 96, 96, E, 24) == (96, 96)
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    until = float(sys.argv[sys.argv.index("--until") + 1]) if "--until" in sys.argv else 1e9  # --fill only slots starting before (s)
    selftest() if "--selftest" in sys.argv else rebin() if "--rebin" in sys.argv else main(a[0], "--replace" in sys.argv, "--dry-run" in sys.argv, "--video-only" in sys.argv, "--a1-only" in sys.argv, "--audio-only" in sys.argv, "--fill" in sys.argv, until, "--skip-intro" in sys.argv, "--intro" in sys.argv)
