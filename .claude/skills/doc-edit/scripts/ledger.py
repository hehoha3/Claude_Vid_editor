"""Clip ledger per workspace (channel): a new video never reuses the clips of the last N videos of its workspace.

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/ledger.py check <video> [--ws <workspace>] [--project <Resolve project>]
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/ledger.py show [<workspace>]
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/ledger.py done <video> [--ws <workspace>] [--project <Resolve project>] [--timeline <name>] [--thumb <image>] [--publish-at "YYYY-MM-DD HH:MM"]
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/ledger.py backfill   # M6: open15 of entries before 2026-11-06
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/ledger.py retire     # AI clips on >= 42 videos -> .ps1 for the user
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/ledger.py --selftest

Workspace = a channel folder holding one folder per video (D:\\Chann_shadowCanopy\\demo_4\\audios ...). Workspaces are
found by the globs of config.toml [workspaces] (default D:\\Chann_*): a new channel = a new folder, nothing else to set.
check (= /doc-edit check-timelines, any time, as often as wanted): reads every video track of the video's timeline
channN_vidK in its Resolve project (project.txt, else the day project vid_DDMMYY; loads it if another project is open, then switches back), maps each file to
its library id (content hash; a hide-logo `_nologo` copy counts as its original) and stores them in
.work/doc_edit/ledgers/<workspace>.json. A new video goes on top; re-checking a video updates it in place.
Ban for video V = clips + open_clips of the `recent` (config, default 6) newest OTHER videos of V's workspace.
open15 (2026-11-06) = clips on 0:00-15:00: those of the 9 newest other videos never before 30:00 of V, penalised after.
An AI clip on 42 videos (every channel, ai_max_videos) is never planned again; done / retire list it for deletion.
done (= /doc-edit done): final check, licensed music of the video timeline (license paths), render it ->
<video>/Done_<video>.mp4 (preset "YouTube 1080 HEVC") -> YouTube upload (dvr_cowork.youtube). Works in a day project (bin Chann_N, timeline channN_vidK). Resolve stays
open; the user moves the folder into _done himself (user 2026-10-26). Videos in _done keep their workspace.
"""
import json, os, re, sys
from datetime import date
from glob import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / ".claude/skills/scan-source/scripts")]
from dvr_cowork.config import load_config  # noqa: E402

LEDGERS = ROOT / ".work" / "doc_edit" / "ledgers"
_cfg = load_config().get("workspaces", {})
GLOBS = _cfg.get("globs", [r"D:\Chann_*"])
RECENT = int(_cfg.get("recent", 6))
# user 2026-11-06: a clip on 0:00-15:00 of one of the OPEN15_N newest videos of the channel is never used before 30:00
# of a new video (plan.py OPEN15_UNTIL) and loses to a fresh clip after it; an AI clip on AI_VIDEOS_MAX videos (every
# channel) is never planned again and goes on the delete list (retire: a PowerShell script the user runs)
OPEN15, OPEN15_N = 900.0, int(_cfg.get("open15_recent", 9))
AI_VIDEOS_MAX = int(_cfg.get("ai_max_videos", 42))
DONE = "_done"  # finished videos of a workspace: <workspace>\_done\<video>
norm = lambda p: os.path.normcase(str(p))  # noqa: E731


def roots():
    return sorted({Path(p) for g in GLOBS for p in glob(g) if Path(p).is_dir()})


def ws_of(video_dir):
    """Workspace name of a video folder (<ws>/<video> or <ws>/_done/<video>)."""
    p = Path(video_dir).parent
    return (p.parent if p.name.lower() == DONE else p).name


def find_video(video, ws=None):
    """Folder of <video> inside the workspaces or their _done (case-insensitive). Same name in two channels -> the key
    <video>__Chann_N, DVR_CHANNEL or --ws picks the channel (user 2026-11-02)."""
    from dvr_cowork.videokey import channel_of, split
    video, ch = split(video)
    hits = [b / d.name for r in roots() if not ws or r.name.lower() == ws.lower()
            for b in (r, r / DONE) if b.is_dir()
            for d in b.iterdir() if d.is_dir() and not os.path.isjunction(d) and d.name.lower() == video.lower() != DONE]
    ch = ch or os.environ.get("DVR_CHANNEL")
    if len(hits) > 1 and ch:
        hits = [h for h in hits if (channel_of(ws_of(h)) or "").lower() == ch.lower()]
    if len(hits) != 1:
        raise SystemExit(f'video "{video}": {"not found" if not hits else "in several workspaces"} '
                         f"({', '.join(map(str, hits)) or ', '.join(r.name for r in roots())}); pass --ws <workspace>")
    return hits[0]


def load(ws):
    p = LEDGERS / f"{ws}.json"
    return json.loads(p.read_text("utf-8")) if p.exists() else {"workspace": ws, "videos": []}


def banned(video, video_dir=None):
    """(clip ids, video names) banned for <video>: the RECENT newest other videos of its workspace."""
    ws = ws_of(video_dir or find_video(video))
    vids = [v for v in load(ws)["videos"] if v["video"].lower() != video.lower()][:RECENT]
    return {i for v in vids for i in v.get("clips", []) + v.get("open_clips", [])}, [v["video"] for v in vids]


def open15_of(ws, v):
    """Clip ids on 0:00-15:00 of ledger entry v: recorded by check since 2026-11-06; older entries (M6 backfill) from
    the slots of their plan.json starting before 15:00, else the whole timeline (unknown -> the stricter answer)."""
    if "open15" in v:
        return v["open15"]
    from dvr_cowork.videokey import channel_of
    for key in (f"{v['video']}__{channel_of(ws)}", v["video"]):
        p = ROOT / ".work" / "doc_edit" / key / "plan.json"
        if p.exists():
            return sorted({s["id"] for s in json.loads(p.read_text("utf-8"))["slots"] if s.get("id") and s["start"] < OPEN15})
    return v.get("clips", []) + v.get("open_clips", [])


def opening(video, video_dir=None):
    """(clip ids, video names): clips on 0:00-15:00 of the OPEN15_N newest other videos of <video>'s workspace."""
    ws = ws_of(video_dir or find_video(video))
    vids = [v for v in load(ws)["videos"] if v["video"].lower() != video.lower()][:OPEN15_N]
    return {i for v in vids for i in open15_of(ws, v)}, [v["video"] for v in vids]


def backfill():
    """M6: write open15 into every ledger entry recorded before 2026-11-06 (open15_of), so it no longer depends on
    plan.json files. -> entries filled."""
    n = 0
    for p in sorted(LEDGERS.glob("*.json")):
        led = json.loads(p.read_text("utf-8"))
        for v in led["videos"]:
            if "open15" not in v:
                v["open15"], n = open15_of(led["workspace"], v), n + 1
        p.write_text(json.dumps(led, indent=1), "utf-8")
    return n


def usage(skip=None):
    """{clip id: distinct videos of every workspace whose timeline holds it}; skip = (workspace, video) not counted."""
    from collections import Counter
    n = Counter()
    for p in LEDGERS.glob("*.json"):
        led = json.loads(p.read_text("utf-8"))
        for v in led["videos"]:
            if skip and (led["workspace"].lower(), v["video"].lower()) == tuple(x.lower() for x in skip):
                continue
            n.update(set(v.get("clips", [])) | set(v.get("open_clips", [])))
    return n


def ai_files():
    """{library id: [file paths]} of the AI roots (+ their hide-logo _nologo copies)."""
    from scan_source import ROOTS, index_of
    out = {}
    for root, kind, source in ROOTS.values():
        if kind == "video" and source == "ai" and index_of(root).exists():
            for cid, c in json.loads(index_of(root).read_text("utf-8"))["clips"].items():
                out.setdefault(cid, []).append(str(root / c["path"]))
    nl = ROOT / ".work" / "hide_logo" / "nologo.json"
    by_path = {norm(p): cid for cid, ps in out.items() for p in ps}
    for copy, orig in (json.loads(nl.read_text("utf-8")) if nl.exists() else {}).items():
        if norm(orig) in by_path:
            out[by_path[norm(orig)]].append(copy)
    return out


def active_ids(skip=None):
    """Clip ids in the plan.json of videos still being made (folder directly in a workspace, not in _done), but <skip>."""
    from dvr_cowork.videokey import homes, split
    out = set()
    for p in (ROOT / ".work" / "doc_edit").glob("*/plan.json"):
        name = split(p.parent.name)[0]
        if name.lower() != (skip or "").lower() and any(h.parent.name.lower() != DONE for h in homes(name, GLOBS)):
            out |= {s.get("id") for s in json.loads(p.read_text("utf-8"))["slots"]} - {None}
    return out


def retire(skip=None, out_dir=None):
    """AI clips on >= AI_VIDEOS_MAX videos -> .work/scripts/retire_ai_<date>.ps1 (lists; -Apply deletes; the user runs
    it, Claude never deletes). Never: a path inside any _check folder, a clip planned on an unfinished video
    (skip = the video being done now), a file off D: (listed for the user: Z: is read-only). -> (n files, script)."""
    use, keep = usage(), active_ids(skip)
    files = ai_files()
    hit = [p for cid, ps in files.items() if use[cid] >= AI_VIDEOS_MAX and cid not in keep for p in ps
           if os.path.exists(p) and not re.search(r"(?i)[\\/]_check[\\/]", p)]
    d_, other = [p for p in hit if p.upper().startswith("D:")], [p for p in hit if not p.upper().startswith("D:")]
    if not hit:
        return 0, None
    sc = Path(out_dir or ROOT / ".work" / "scripts") / f"retire_ai_{date.today():%Y%m%d}.ps1"
    sc.parent.mkdir(parents=True, exist_ok=True)
    q = lambda p: "'" + p.replace("'", "''") + "'"  # noqa: E731
    sc.write_text(
        f"# AI clips used in >= {AI_VIDEOS_MAX} videos (ledger.py retire, {date.today()}). List: .\\{sc.name}"
        f"   Delete: .\\{sc.name} -Apply   Then /scan-source.\nparam([switch]$Apply)\n$files = @(\n"
        + ",\n".join(f"  {q(p)}" for p in d_) + "\n)\n"
        "foreach ($f in $files) { if ($Apply) { Remove-Item -LiteralPath $f } else { Write-Output $f } }\n"
        + "".join(f"# not on D: (read-only, tell the user): {p}\n" for p in other), "utf-8")
    return len(hit), sc


def record(ws, video, fields):
    led = load(ws)
    old = next((v for v in led["videos"] if v["video"].lower() == video.lower()), None)
    entry = {"video": video, "first_checked": old.get("first_checked", old.get("done")) if old else str(date.today()),
             "checked": str(date.today()), **fields}
    led["videos"] = ([entry] + led["videos"]) if not old else [entry if v is old else v for v in led["videos"]]
    LEDGERS.mkdir(parents=True, exist_ok=True)
    (LEDGERS / f"{ws}.json").write_text(json.dumps(led, indent=1), "utf-8")
    return led


def library():
    from scan_source import ROOTS, index_of
    lib = {}
    for root, kind, _ in ROOTS.values():
        if kind == "video" and index_of(root).exists():  # a root never scanned yet (africa_ai_check) has no index
            for cid, c in json.loads(index_of(root).read_text("utf-8"))["clips"].items():
                lib[norm(root / c["path"])] = cid
    nl = ROOT / ".work" / "hide_logo" / "nologo.json"
    for copy, orig in (json.loads(nl.read_text("utf-8")) if nl.exists() else {}).items():
        if norm(orig) in lib:
            lib[norm(copy)] = lib[norm(orig)]
    return lib


def _tls(project):
    """The video's timeline channN_vidK (DVR_TIMELINE, set by use_channel from the video folder), as a list."""
    from dvr_cowork.resolve_ops import video_timeline
    return [t for t in (video_timeline(project),) if t]


def _proj(vdir):
    """Resolve project of a video: the one place.py wrote in .work/doc_edit/<video>/project.txt, else its day project
    vid_DDMMYY (an old name without a date stays itself)."""
    from dvr_cowork.videokey import day_project, video_key
    pt = ROOT / ".work" / "doc_edit" / video_key(vdir) / "project.txt"
    return pt.read_text("utf-8").strip().split("/")[0] if pt.exists() else day_project(vdir.name)


def timeline_files(video):
    """{"clips": {file path}, "open15": {file path on 0:00-15:00}} of the video timeline of project <video>; loads the
    project if another one is open."""
    from dvr_cowork.resolve_conn import connect
    from dvr_cowork.resolve_ops import timeline_fps
    pm = connect(load_config()).GetProjectManager()
    project, back = _current(pm), None
    if not project or project.GetName().lower() != video.lower():  # None = Resolve on the Project Manager
        back = project and project.GetName()
        assert not back or pm.SaveProject(), f'could not save open project "{back}" before switching'
        project = pm.LoadProject(video)
        if not project:
            back and pm.LoadProject(back)
            raise SystemExit(f'Resolve project "{video}" not found in the current project library; nothing recorded')
    cur, out = project.GetCurrentTimeline(), {}
    for t in _tls(project):  # a timeline not loaded yet returns no items: make it current first
        project.SetCurrentTimeline(t)
        fps, t0 = timeline_fps(t, project), int(t.GetStartFrame())
        items = [(ti.GetMediaPoolItem().GetClipProperty("File Path"), (int(ti.GetStart()) - t0) / fps)
                 for k in range(1, int(t.GetTrackCount("video")) + 1)
                 for ti in t.GetItemListInTrack("video", k) or [] if ti.GetMediaPoolItem()]
        out["clips"] = {p for p, _ in items}
        out["open15"] = {p for p, s in items if s < OPEN15}
    if cur:
        project.SetCurrentTimeline(cur)
    if back:
        pm.LoadProject(back)
    return out


def check(video, ws=None, proj=None):  # proj: Resolve project name when it differs from the folder
    vdir = find_video(video, ws)
    from dvr_cowork.resolve_ops import use_channel
    use_channel(vdir)  # D:\\Chann_N_*\\<video>: that channel's bin, timeline channN_vidK
    proj = proj or _proj(vdir)
    files = timeline_files(proj)
    if "clips" not in files:
        raise SystemExit(f'project {proj} has no timeline {os.environ.get("DVR_TIMELINE")}: nothing recorded')
    lib, fields, miss = library(), {}, {}
    for field, paths in files.items():
        got = {p: lib.get(norm(p)) for p in paths}
        fields[field] = sorted({g for g in got.values() if g})
        miss[field] = sorted(os.path.basename(p) for p, g in got.items() if not g)
    led = record(ws_of(vdir), vdir.name, fields)
    for field, name in (("clips", os.environ.get("DVR_TIMELINE")),):
        if field in fields:
            print(f'{vdir.name}: timeline "{name}" {len(fields[field])} clips recorded'
                  + (f" | not in the library index (file gone / renamed outside the pipeline, offline on the timeline): "
                     f"{', '.join(miss[field][:10])}" if miss[field] else ""))
    show(ws_of(vdir), led)


def _current(pm):
    """Open project, None on the Project Manager (Resolve then reports its blank "Untitled Project")."""
    p = pm.GetCurrentProject()
    return None if not p or p.GetName() == "Untitled Project" else p


LICENSES = ROOT / ".work" / "audio_licenses.md"
LICENSED_ROOT = norm(load_config()["paths"]["audio_lib"]) + os.sep  # Epidemic / Suno: no sidecar / row = warning
MUSIC_ROOT = norm(r"D:\Music") + os.sep  # intro music (intro.py MUSIC_DIRS), Pixabay: no row/license = warning too


def pixabay_license(p):
    """License txt beside a Pixabay track <author>-<title>-<id>.mp3: any *.txt naming that id (*-<id>-license.txt,
    *-<id>.txt ..., user 2026-10-30; "license" names first), else one whose "Audio File ID" is it; None without."""
    m = re.search(r"-(\d+)$", Path(p).stem)
    if not m:
        return None
    txts = sorted(Path(p).parent.glob("*.txt"), key=lambda t: ("license" not in t.name.lower(), t.name))
    return next((t for t in txts if re.search(rf"(?<!\d){m[1]}(?!\d)", t.stem)), None) or next(
        (t for t in txts if re.search(rf"Audio File ID:\s*{m[1]}(?!\d)", t.read_text("utf-8", "replace"))), None)


def pixabay_row(p):
    """Pixabay track -> [file, license txt, title, author] from its license txt (pixabay_license; user 2026-10-29:
    the intro music must be in audio_licenses.md), else None."""
    lic = pixabay_license(p)
    if not lic:
        return None
    t = [x.strip() for x in lic.read_text("utf-8", "replace").splitlines()] + [""]
    get = lambda key: next((t[i + 1] for i, x in enumerate(t[:-1]) if x.startswith(key)), "")
    author = re.sub(r"-\d+$", "", get("Licensor's Username").rstrip("/").rsplit("/", 1)[-1])
    return [p, str(lic), get("Audio File Title"), author]


def sidecar_row(p):
    """Epidemic / Suno track (audio-expert fetch.py) -> [file, <stem>.license.txt, title, author] from the
    "Key: value" lines of that txt beside it, else None."""
    lic = Path(p).with_suffix(".license.txt")
    if not lic.exists():
        return None
    kv = dict(x.split(": ", 1) for x in lic.read_text("utf-8", "replace").splitlines() if ": " in x)
    return [p, str(lic), kv.get("Title", ""), kv.get("Author", "")]


def license_rows(text):
    """{normcase music file: license pdf} from the markdown table of audio_licenses.md."""
    rows = {}
    for line in text.splitlines():
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) >= 2 and c[1].lower().endswith(".pdf"):
            rows[norm(c[0])] = c
    return rows


def _clock(s):
    s = int(round(s))
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


def merge_spans(spans, gap=1.0):
    """[(a, b) s] -> sorted, overlapping / touching (<= gap) spans joined (crossfaded pieces of one cue = one use)."""
    out = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def licenses(project, vdir, fname="audio_licenses.md"):
    """Audio files of the video timeline -> license rows of .work/audio_licenses.md, written to
    <video folder>/audio_licenses.md, one line per file (user order 2026-10-21; no pdf copies any more):
    [start - stop], [start - stop] - title + author - license pdf path."""
    from dvr_cowork.resolve_ops import timeline_fps
    rows = license_rows(LICENSES.read_text("utf-8")) if LICENSES.exists() else {}
    cur, used = project.GetCurrentTimeline(), {}  # file -> {timeline name: [(start, stop) s]}
    for t in _tls(project):
        project.SetCurrentTimeline(t)
        fps, t0 = timeline_fps(t, project), t.GetStartFrame()
        for k in range(1, int(t.GetTrackCount("audio")) + 1):
            for ti in t.GetItemListInTrack("audio", k) or []:
                if mp := ti.GetMediaPoolItem():
                    used.setdefault(mp.GetClipProperty("File Path"), {}).setdefault(t.GetName(), []).append(
                        ((ti.GetStart() - t0) / fps, (ti.GetEnd() - t0) / fps))
    if cur:
        project.SetCurrentTimeline(cur)
    for p in used:
        if norm(p) not in rows and (r := pixabay_row(p) or sidecar_row(p)):
            rows[norm(p)] = r
    lic = sorted(((p, rows[norm(p)]) for p in used if norm(p) in rows),
                 key=lambda x: min(a for sp in used[x[0]].values() for a, _ in sp))  # film order
    nolic = sorted(p for p in used if norm(p) not in rows and norm(p).startswith((LICENSED_ROOT, MUSIC_ROOT)))

    def line(p, c):
        spans = ", ".join((f"{name}: " if name.lower() != "edit" else "")
                          + ", ".join(f"[{_clock(a)} - {_clock(b)}]" for a, b in merge_spans(sp))
                          for name, sp in sorted(used[p].items(), key=lambda x: x[0].lower() != "edit"))
        title = " + ".join(x for x in (c[2] if len(c) > 2 else "", c[3] if len(c) > 3 else "") if x) or Path(p).stem
        return f"{spans} - {title} - {c[1]}"

    md = [f"# License nhạc của {project.GetName()} (timeline {os.environ.get("DVR_TIMELINE")}, {date.today()})\n",
          "Envato Elements: mỗi license chỉ cho một project, đăng ký lại cho video này.\n",
          "Epidemic Sound: kênh YouTube phải được whitelist trong tài khoản Epidemic, nếu không sẽ bị Content ID claim.\n"]
    md += [f"- {line(p, c)}" for p, c in lic]
    if nolic:
        md += ["\n## Chưa có license\n"] + [f"- {p}" for p in nolic]
    (Path(vdir) / fname).write_text("\n".join(md) + "\n", "utf-8")
    print(f"licenses: {len(lic)} licensed audio file(s) on the video timeline -> {Path(vdir) / fname}")
    for p, c in lic:
        print(f"  {line(p, c)}")
    if nolic:
        print(f"  NO LICENSE ROW (in {LICENSED_ROOT.rstrip(os.sep)}, missing from {LICENSES.name}): " + "; ".join(nolic))


PRESET = "YouTube 1080 HEVC"


def render_done(project, out_dir, timeline=None, name=None):
    """Render <timeline> with the preset PRESET as Done_<project>.mp4 into out_dir and wait (user order 2026-10-13)."""
    import time
    from dvr_cowork.resolve_ops import find_timeline
    name = name or f"Done_{project.GetName()}"
    if (Path(out_dir) / f"{name}.mp4").exists():
        print(f"render: {name}.mp4 already in {out_dir}, not rendered again")
        return
    from dvr_cowork.videokey import video_key
    if (ROOT / ".work" / "doc_edit" / video_key(out_dir) / "plan.json").exists():  # the 4 black fades, before any render
        import place
        print(place.black_fades(video_key(out_dir)))
    from dvr_cowork.resolve_ops import video_timeline
    tl = find_timeline(project, timeline) if timeline else video_timeline(project)  # default: the video's channN_vidK
    timeline = timeline or os.environ.get("DVR_TIMELINE")
    if not tl:
        raise SystemExit(f'no timeline "{timeline}" to render: nothing changed')
    if not any(tl.GetItemListInTrack("video", i) for i in range(1, int(tl.GetTrackCount("video")) + 1)):
        raise SystemExit(f'timeline "{timeline}" is empty (no video): assemble it first, nothing rendered or moved')
    cur = project.GetCurrentTimeline()
    project.SetCurrentTimeline(tl)
    # user 2026-10-21: the Done render carries no subtitles: switch the subtitle tracks off, restore them in finally
    subs = [i for i in range(1, int(tl.GetTrackCount("subtitle") or 0) + 1) if tl.GetIsTrackEnabled("subtitle", i)]
    for i in subs:
        tl.SetTrackEnable("subtitle", i, False)
    # user 2026-10-24: every Done render uses the Resolve render preset "YouTube 1080 HEVC" (no codec fallback: a
    # missing preset or a failed render stops here, nothing moved)
    st, codec = {}, PRESET
    try:
        assert project.LoadRenderPreset(PRESET), f'render preset "{PRESET}" not found in Resolve'
        assert project.SetRenderSettings({"SelectAllFrames": True, "TargetDir": str(out_dir), "CustomName": name,
                                          "ExportVideo": True, "ExportAudio": True}), "render settings refused"
        job = project.AddRenderJob()
        assert job and project.StartRendering(job), "render job did not start"
        while project.IsRenderingInProgress():
            time.sleep(5)
        st = project.GetRenderJobStatus(job) or {}
        project.DeleteRenderJob(job)  # job only, the rendered file stays
        if st.get("JobStatus") != "Complete":
            print(f"render with {codec} failed: {st.get('Error') or st}")
    finally:
        for i in subs:
            tl.SetTrackEnable("subtitle", i, True)
        if cur:
            project.SetCurrentTimeline(cur)
    if st.get("JobStatus") != "Complete":
        raise SystemExit(f"render {name} failed ({st})")
    print(f"render: {Path(out_dir) / name}.mp4 ({codec}, timeline {timeline}, {st.get('TimeTakenToRenderInMs', 0) // 1000}s)")


def rerender(video, ws=None, proj=None, timeline=None):
    """A video already in _done whose timeline changed (user 2026-10-21): render again next to the old file as
    Done_<video>_vN.mp4 + audio_licenses_vN.md; nothing is overwritten, moved or closed (Resolve stays open)."""
    from dvr_cowork.resolve_conn import connect
    from dvr_cowork.resolve_ops import use_channel
    vdir = find_video(video, ws)
    use_channel(vdir)
    proj = proj or _proj(vdir)
    project = _current(connect(load_config()).GetProjectManager())
    if not project or project.GetName().lower() != proj.lower():
        raise SystemExit(f'Resolve project "{proj}" is not the open project: open it first, nothing changed')
    n = 2
    while (vdir / f"Done_{vdir.name}_v{n}.mp4").exists():
        n += 1
    licenses(project, vdir, f"audio_licenses_v{n}.md")
    render_done(project, vdir, timeline, f"Done_{vdir.name}_v{n}")


def done(video, ws=None, proj=None, timeline=None, thumb=None, publish_at=None):
    """A finished video (user 2026-10-26: Master / Open deleted, no quit, no move): final check-timelines, licensed
    music of the video timeline channN_vidK -> <video folder>/audio_licenses.md, render <timeline> (preset "YouTube 1080 HEVC") as
    <video folder>/Done_<video>.mp4 and wait, then upload it to the channel's YouTube (user 2026-10-31,
    dvr_cowork.youtube). Resolve stays open on the user's timeline; the user moves the folder into
    _done. Project: --project, else the one place.py wrote in .work/doc_edit/<video>/project.txt (day project
    vid_DDMMYY/Chann_N/channN_vidK), else its day project vid_DDMMYY."""
    from dvr_cowork.resolve_conn import connect
    from dvr_cowork.resolve_ops import use_channel
    vdir = find_video(video, ws)
    proj = proj or _proj(vdir)
    check(video, ws, proj)  # final ledger record of the video timeline; sets channel + timeline
    use_channel(vdir)
    pm = connect(load_config()).GetProjectManager()
    project = _current(pm)
    if not project or project.GetName().lower() != proj.lower():
        assert not project or pm.SaveProject(), f'could not save open project "{project.GetName()}": nothing changed'
        project = pm.LoadProject(proj)
        if not project:
            raise SystemExit(f'Resolve project "{proj}" not found: nothing changed')
    licenses(project, vdir)
    render_done(project, vdir, timeline, f"Done_{vdir.name}")
    # User 2026-11-07: no --thumb -> <video>\thumb\done.jpg/.png (the final the user approved and renamed), else none.
    thumb = thumb or next((str(p) for p in sorted((vdir / "thumb").glob("done.*"))
                           if p.suffix.lower() in (".jpg", ".jpeg", ".png")), None)
    try:
        from dvr_cowork import youtube
        yt = youtube.upload(vdir, thumb, publish_at=publish_at)
    except Exception as e:  # quota / network: the render stands, upload again by hand
        yt = f"youtube: upload FAILED ({e}); retry: python -m dvr_cowork.youtube upload \"{vdir}\""
    print(yt)
    handoff(f"done {vdir.name} ({ws_of(vdir)}): rendered Done_{vdir.name}.mp4 (timeline {timeline}); {yt}; folder move = user")
    print(f"done {vdir.name}: rendered, Resolve left open; move {vdir} into {DONE} yourself")
    n, sc = retire(skip=vdir.name)
    print(f"AI clips on >= {AI_VIDEOS_MAX} videos: {n} file(s)" + (f" -> review + run (PowerShell): {sc}  then -Apply"
                                                                  if sc else ""))


HANDOFF = ROOT / ".work" / "knowledge" / "handoffs" / "current.md"  # memory gateway: project state


def handoff(line, path=None):
    """Newest-first bullet under "Last completed:" of the gateway handoff + Updated date; no handoff -> skip."""
    import re
    p = Path(path or HANDOFF)
    if not p.is_file():
        return
    s = p.read_text("utf-8")
    s = re.sub(r"(?m)^Updated: .*$", f"Updated: {date.today()}", s, count=1)
    # header may carry a note: "Last completed (newest first, ...):" (it did, so every done skipped it until 2026-10-31)
    s = re.sub(r"(?m)^(Last completed[^\n]*:\n\n?)", lambda m: f"{m[1]}- {date.today()} {line}\n", s, count=1)
    p.write_text(s, "utf-8")


def show(ws=None, led=None):
    for w in ([ws] if ws else [r.name for r in roots()]):
        led = led if ws and led else load(w)
        line = ", ".join(f"{v['video']} {v['checked']} {len(v.get('clips', []))}+{len(v.get('open_clips', []))}"
                         for v in led["videos"]) or "empty"
        print(f"ledger {w} (newest first, a new video bans the first {RECENT} other videos): {line}")


def selftest():
    global LEDGERS, RECENT
    import tempfile
    LEDGERS, RECENT = Path(tempfile.mkdtemp()), 4  # logic test, independent of the config value
    for v, ids in (("a", ["1"]), ("b", ["2"]), ("c", ["3"]), ("d", ["4"]), ("e", ["5"])):
        record("W", v, {"clips": ids, "open_clips": [ids[0] + "o"]})
    record("W", "b", {"clips": ["2", "22"]})  # re-check: updated in place, keeps its rank
    assert [v["video"] for v in load("W")["videos"]] == ["e", "d", "c", "b", "a"]
    ids, vids = banned("e", Path("D:/W/e"))
    assert vids == ["d", "c", "b", "a"][:RECENT] and "22" in ids and "5" not in ids, (ids, vids)
    ids, vids = banned("new", Path("D:/W/new"))
    assert vids == ["e", "d", "c", "b"][:RECENT] and "1" not in ids
    assert banned("x", Path("D:/Other/x")) == (set(), [])  # other workspace: its own (empty) ledger
    assert banned("e", Path("D:/W/_done/e")) == banned("e", Path("D:/W/e"))  # archived video keeps its workspace
    assert ws_of(r"D:\W\_done\e") == ws_of(r"D:\W\e") == "W"
    record("W", "f", {"clips": ["6", "7"], "open15": ["6"]})  # open15 (user 2026-11-06)
    ids, _ = opening("new", Path("D:/W/new"))
    assert "6" in ids and "7" not in ids and "5" in ids, ids  # e: no open15, no plan.json -> its whole timeline
    assert usage()["2"] == 1 and usage(("W", "b"))["2"] == 0 and usage()["22"] == 1
    tmp = Path(tempfile.mkdtemp())
    rows = license_rows("| file | license |\n|---|---|\n| Z:\\S\\a.wav | Z:\\S\\1.pdf | x |\n| head | not a pdf |")
    assert rows == {norm(r"Z:\S\a.wav"): [r"Z:\S\a.wav", r"Z:\S\1.pdf", "x"]}, rows
    assert merge_spans([(70, 90), (10, 20), (20.5, 30)]) == [[10, 30], [70, 90]]
    assert _clock(65.4) == "01:05" and _clock(3725) == "1:02:05"
    for name, lic in (("a-x-492750", "schlagzeug-africa-492750-license.txt"), ("b-y-376385", "y-376385.txt"),
                      ("c-z-111", "cert.txt")):  # Pixabay license by id in the name, or by the id inside
        (tmp / f"{name}.mp3").touch()
        (tmp / lic).write_text("Licensor's Username:\nhttps://pixabay.com/users/au-9/\n\nAudio File Title:\nT\n\n"
                               f"Audio File ID:\n{name.rsplit('-', 1)[1]}\n", "utf-8")
        assert pixabay_row(tmp / f"{name}.mp3")[1:] == [str(tmp / lic), "T", "au"], name
    (tmp / "d-w-4927.mp3").touch()
    assert pixabay_license(tmp / "d-w-4927.mp3") is None  # 4927 is not 492750
    h = tmp / "current.md"
    h.write_text("# H\n\nUpdated: 2000-01-01\n\nLast completed:\n\n- old\n", "utf-8")
    handoff("done v (W)", h)
    assert h.read_text("utf-8") == f"# H\n\nUpdated: {date.today()}\n\nLast completed:\n\n- {date.today()} done v (W)\n- old\n"
    h.write_text("Last completed (newest first):\n- old\n", "utf-8")  # the real header has a note, no blank line
    handoff("done v", h)
    assert h.read_text("utf-8") == f"Last completed (newest first):\n- {date.today()} done v\n- old\n", h.read_text("utf-8")
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    ws = a[a.index("--ws") + 1] if "--ws" in a else None
    proj = a[a.index("--project") + 1] if "--project" in a else None
    if a == ["--selftest"]:
        selftest()
    elif a[:1] == ["check"] and len(a) >= 2:
        check(a[1], ws, proj)
    elif a[:1] == ["done"] and len(a) >= 2:
        done(a[1], ws, proj, a[a.index("--timeline") + 1] if "--timeline" in a else None,  # user 2026-10-26
             a[a.index("--thumb") + 1] if "--thumb" in a else None,
             a[a.index("--publish-at") + 1] if "--publish-at" in a else None)
    elif a[:1] == ["rerender"] and len(a) >= 2:
        rerender(a[1], ws, proj, a[a.index("--timeline") + 1] if "--timeline" in a else None)
    elif a[:1] == ["show"]:
        show(a[1] if len(a) > 1 else None)
    elif a[:1] == ["backfill"]:
        print(f"open15 backfilled into {backfill()} ledger entries")
    elif a[:1] == ["retire"]:
        n, sc = retire()
        print(f"AI clips on >= {AI_VIDEOS_MAX} videos: {n} file(s)" + (f" -> {sc}" if sc else ""))
    else:
        print(__doc__)
