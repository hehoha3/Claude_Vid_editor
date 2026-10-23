"""Clip ledger per workspace (channel): a new video never reuses the clips of the last N videos of its workspace.

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/ledger.py check <video> [--ws <workspace>] [--project <Resolve project>]
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/ledger.py show [<workspace>]
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/ledger.py done <video> [--ws <workspace>] [--project <Resolve project>] [--timeline Edit]
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/ledger.py move <video>   # redo the move of a failed done
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/ledger.py --selftest

Workspace = a channel folder holding one folder per video (D:\\Chann_shadowCanopy\\demo_4\\audios ...). Workspaces are
found by the globs of config.toml [workspaces] (default D:\\Chann_*): a new channel = a new folder, nothing else to set.
check (= /doc-edit check-timelines, any time, as often as wanted): reads every video track of the timelines "Edit"
and "Open" of Resolve project <video> (loads it if another project is open, then switches back), maps each file to
its library id (content hash; a hide-logo `_nologo` copy counts as its original) and stores them in
.work/doc_edit/ledgers/<workspace>.json. A new video goes on top; re-checking a video updates it in place.
Ban for video V = clips + open_clips of the `recent` (config, default 6) newest OTHER videos of V's workspace.
done (= /doc-edit done): licensed music of Edit + Open (license paths), render Master -> <video>/Done_<project>.mp4
(H.264), final check, relink the project's media to <workspace>/_done/<video> (temporary junction),
quit Resolve, move the folder into _done. Resolve stays closed (the user reopens it). Videos in _done keep their workspace.
"""
import json, os, re, shutil, sys
from datetime import date
from glob import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / ".claude/skills/scan-source/scripts")]
from dvr_cowork.config import load_config  # noqa: E402

LEDGERS = ROOT / ".work" / "doc_edit" / "ledgers"
TL = {"edit": "clips", "open": "open_clips"}  # timeline (any case) -> ledger field
_cfg = load_config().get("workspaces", {})
GLOBS = _cfg.get("globs", [r"D:\Chann_*"])
RECENT = int(_cfg.get("recent", 6))
DONE = "_done"  # finished videos of a workspace: <workspace>\_done\<video>
norm = lambda p: os.path.normcase(str(p))  # noqa: E731


def roots():
    return sorted({Path(p) for g in GLOBS for p in glob(g) if Path(p).is_dir()})


def ws_of(video_dir):
    """Workspace name of a video folder (<ws>/<video> or <ws>/_done/<video>)."""
    p = Path(video_dir).parent
    return (p.parent if p.name.lower() == DONE else p).name


def find_video(video, ws=None):
    """Folder of <video> inside the workspaces or their _done (case-insensitive). Same name twice -> --ws needed."""
    hits = [b / d.name for r in roots() if not ws or r.name.lower() == ws.lower()
            for b in (r, r / DONE) if b.is_dir()
            for d in b.iterdir() if d.is_dir() and not os.path.isjunction(d) and d.name.lower() == video.lower() != DONE]
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


def timeline_files(video):
    """{field: {file path}} of timelines Edit / Open of project <video>; loads the project if another one is open."""
    from dvr_cowork.resolve_conn import connect
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
    for i in range(1, project.GetTimelineCount() + 1):
        t = project.GetTimelineByIndex(i)
        if t.GetName().lower() in TL:  # a timeline not loaded yet returns no items: make it current first
            project.SetCurrentTimeline(t)
            out[TL[t.GetName().lower()]] = {
                ti.GetMediaPoolItem().GetClipProperty("File Path") for k in range(1, int(t.GetTrackCount("video")) + 1)
                for ti in t.GetItemListInTrack("video", k) or [] if ti.GetMediaPoolItem()}
    if cur:
        project.SetCurrentTimeline(cur)
    if back:
        pm.LoadProject(back)
    return out


def timeline_uses(project, name):
    """{lower-case file path: [(src_in, src_out) s]} of the video items on timeline <name> of the open project; the
    current timeline is restored. Edit + Open of one video share the reuse budget (plan.py REUSE_MAX, other parts)."""
    from dvr_cowork.resolve_ops import clip_fps, timeline_fps
    t = next((project.GetTimelineByIndex(i) for i in range(1, project.GetTimelineCount() + 1)
              if project.GetTimelineByIndex(i).GetName().lower() == name.lower()), None)
    if not t:
        return {}
    cur, out = project.GetCurrentTimeline(), {}
    project.SetCurrentTimeline(t)  # a timeline not loaded yet returns no items
    fps = timeline_fps(t, project)
    for k in range(1, int(t.GetTrackCount("video")) + 1):
        for ti in t.GetItemListInTrack("video", k) or []:
            if mp := ti.GetMediaPoolItem():
                a = ti.GetLeftOffset() / clip_fps(mp, fps)
                out.setdefault(str(Path(mp.GetClipProperty("File Path"))).lower(), []).append(
                    (round(a, 2), round(a + ti.GetDuration() / fps, 2)))
    if cur:
        project.SetCurrentTimeline(cur)
    return out


def check(video, ws=None, proj=None):  # proj: Resolve project name when it differs from the folder
    vdir = find_video(video, ws)
    files = timeline_files(proj or vdir.name)
    if "clips" not in files:
        raise SystemExit(f'project {video} has no timeline "Edit": nothing recorded')
    lib, fields, miss = library(), {}, {}
    for field, paths in files.items():
        got = {p: lib.get(norm(p)) for p in paths}
        fields[field] = sorted({g for g in got.values() if g})
        miss[field] = sorted(os.path.basename(p) for p, g in got.items() if not g)
    led = record(ws_of(vdir), vdir.name, fields)
    for field, name in (("clips", "Edit"), ("open_clips", "Open")):
        if field in fields:
            print(f'{vdir.name}: timeline "{name}" {len(fields[field])} clips recorded'
                  + (f" | not in the library index (file gone / renamed outside the pipeline, offline on the timeline): "
                     f"{', '.join(miss[field][:10])}" if miss[field] else ""))
    show(ws_of(vdir), led)


def _current(pm):
    """Open project, None on the Project Manager (Resolve then reports its blank "Untitled Project")."""
    p = pm.GetCurrentProject()
    return None if not p or p.GetName() == "Untitled Project" else p


def _pool(project):
    def walk(f):
        yield from f.GetClipList() or []
        for s in f.GetSubFolderList() or []:
            yield from walk(s)
    return [(c, c.GetClipProperty("File Path") or "") for c in walk(project.GetMediaPool().GetRootFolder())]


def _junction(link, target):
    import subprocess
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
    return os.path.isjunction(link)


LICENSES = ROOT / ".work" / "audio_licenses.md"
LICENSED_ROOT = norm(r"Z:\Unseen\Sound") + os.sep  # licensed music library: a file here without a row = warning


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
    """Audio files of timelines Edit + Open -> license rows of .work/audio_licenses.md, written to
    <video folder>/audio_licenses.md, one line per file (user order 2026-10-21; no pdf copies any more):
    [start - stop], [start - stop] - title + author - license pdf path."""
    from dvr_cowork.resolve_ops import timeline_fps
    rows = license_rows(LICENSES.read_text("utf-8")) if LICENSES.exists() else {}
    cur, used = project.GetCurrentTimeline(), {}  # file -> {timeline name: [(start, stop) s]}
    for i in range(1, project.GetTimelineCount() + 1):
        t = project.GetTimelineByIndex(i)
        if t.GetName().lower() in TL:
            project.SetCurrentTimeline(t)
            fps, t0 = timeline_fps(t, project), t.GetStartFrame()
            for k in range(1, int(t.GetTrackCount("audio")) + 1):
                for ti in t.GetItemListInTrack("audio", k) or []:
                    if mp := ti.GetMediaPoolItem():
                        used.setdefault(mp.GetClipProperty("File Path"), {}).setdefault(t.GetName(), []).append(
                            ((ti.GetStart() - t0) / fps, (ti.GetEnd() - t0) / fps))
    if cur:
        project.SetCurrentTimeline(cur)
    lic = sorted(((p, rows[norm(p)]) for p in used if norm(p) in rows),
                 key=lambda x: min(a for sp in used[x[0]].values() for a, _ in sp))  # film order
    nolic = sorted(p for p in used if norm(p) not in rows and norm(p).startswith(LICENSED_ROOT))

    def line(p, c):
        spans = ", ".join((f"{name}: " if name.lower() != "edit" else "")
                          + ", ".join(f"[{_clock(a)} - {_clock(b)}]" for a, b in merge_spans(sp))
                          for name, sp in sorted(used[p].items(), key=lambda x: x[0].lower() != "edit"))
        title = " + ".join(x for x in (c[2] if len(c) > 2 else "", c[3] if len(c) > 3 else "") if x) or Path(p).stem
        return f"{spans} - {title} - {c[1]}"

    md = [f"# License nhạc của {project.GetName()} (timeline Edit + Open, {date.today()})\n",
          "Envato Elements: mỗi license chỉ cho một project, đăng ký lại cho video này.\n"]
    md += [f"- {line(p, c)}" for p, c in lic]
    if nolic:
        md += ["\n## Chưa có license\n"] + [f"- {p}" for p in nolic]
    (Path(vdir) / fname).write_text("\n".join(md) + "\n", "utf-8")
    print(f"licenses: {len(lic)} licensed audio file(s) on Edit + Open -> {Path(vdir) / fname}")
    for p, c in lic:
        print(f"  {line(p, c)}")
    if nolic:
        print(f"  NO LICENSE ROW (in {LICENSED_ROOT.rstrip(os.sep)}, missing from {LICENSES.name}): " + "; ".join(nolic))


def render_done(project, out_dir, timeline="Master", name=None):
    """Render <timeline> as H.264 mp4 Done_<project>.mp4 into out_dir and wait (user order 2026-10-13)."""
    import time
    name = name or f"Done_{project.GetName()}"
    if (Path(out_dir) / f"{name}.mp4").exists():
        print(f"render: {name}.mp4 already in {out_dir}, not rendered again")
        return
    tl = next((project.GetTimelineByIndex(i) for i in range(1, project.GetTimelineCount() + 1)
               if project.GetTimelineByIndex(i).GetName() == timeline), None)
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
    # amazon_2 2026-10-17: generic "H264" failed at 0% ("Cannot find appropriate codec"), the NVIDIA encoder is
    # listed by Resolve on this machine: try it next (still an H.264 mp4)
    st = {}
    try:
        for codec in ("H264", "H264_NVIDIA"):
            if not project.SetCurrentRenderFormatAndCodec("mp4", codec):
                continue
            assert project.SetRenderSettings({"SelectAllFrames": True, "TargetDir": str(out_dir), "CustomName": name,
                                              "ExportVideo": True, "ExportAudio": True}), "render settings refused"
            job = project.AddRenderJob()
            assert job and project.StartRendering(job), "render job did not start"
            while project.IsRenderingInProgress():
                time.sleep(5)
            st = project.GetRenderJobStatus(job) or {}
            project.DeleteRenderJob(job)  # job only, the rendered file stays
            if st.get("JobStatus") == "Complete":
                break
            print(f"render with {codec} failed: {st.get('Error') or st}")
    finally:
        for i in subs:
            tl.SetTrackEnable("subtitle", i, True)
        if cur:
            project.SetCurrentTimeline(cur)
    if st.get("JobStatus") != "Complete":
        raise SystemExit(f"render {name} failed ({st}): folder not moved, Resolve left open")
    print(f"render: {Path(out_dir) / name}.mp4 (H.264 {codec}, timeline {timeline}, {st.get('TimeTakenToRenderInMs', 0) // 1000}s)")


def rerender(video, ws=None, proj=None, timeline="Edit"):
    """A video already in _done whose timeline changed (user 2026-10-21): render again next to the old file as
    Done_<project>_vN.mp4 + audio_licenses_vN.md; nothing is overwritten, moved or closed (Resolve stays open)."""
    from dvr_cowork.resolve_conn import connect
    vdir = find_video(video, ws)
    proj = proj or vdir.name
    project = _current(connect(load_config()).GetProjectManager())
    if not project or project.GetName().lower() != proj.lower():
        raise SystemExit(f'Resolve project "{proj}" is not the open project: open it first, nothing changed')
    n = 2
    while (vdir / f"Done_{project.GetName()}_v{n}.mp4").exists():
        n += 1
    licenses(project, vdir, f"audio_licenses_v{n}.md")
    render_done(project, vdir, timeline, f"Done_{project.GetName()}_v{n}")


def done(video, ws=None, proj=None, timeline="Master"):
    """Archive a finished video (user order 2026-10-13):
    0. list the licensed music used on Edit + Open (license pdf paths); render timeline Master -> H.264
       <video folder>/Done_<project>.mp4 and wait (a failed render stops here, nothing moved).
    1. final check-timelines; relink the project's media under <ws>/<video> to <ws>/_done/<video> (Change Source
       Folder). The files are not there yet, so a temporary junction _done/<video> -> <video> lets ReplaceClip see them.
    2. save, quit Resolve, remove the junction (link only), rename the folder into _done (all or nothing, never copy +
       delete). Resolve stays closed: reopening is the user's call (2026-10-13)."""
    import subprocess, time
    from dvr_cowork.resolve_conn import connect
    vdir = find_video(video, ws)
    if vdir.parent.name.lower() == DONE:
        raise SystemExit(f"{vdir} is already in {DONE}: nothing to do")
    dest = vdir.parent / DONE / vdir.name
    if dest.exists():
        raise SystemExit(f"{dest} already exists: nothing changed")
    proj = proj or vdir.name
    check(video, ws, proj)  # final ledger record of Edit + Open
    resolve = connect(load_config())
    pm = resolve.GetProjectManager()
    project = _current(pm)
    if not project or project.GetName().lower() != proj.lower():
        assert not project or pm.SaveProject(), f'could not save open project "{project.GetName()}": nothing changed'
        project = pm.LoadProject(proj)
        if not project:
            raise SystemExit(f'Resolve project "{proj}" not found: nothing changed')
    licenses(project, vdir)
    render_done(project, vdir, timeline)  # into the video folder: it moves into _done with it
    if not _junction(dest, vdir):
        raise SystemExit(f"could not create the temporary link {dest}: nothing changed")
    old = norm(vdir) + os.sep
    jobs = [(c, str(dest) + p[len(old) - 1:]) for c, p in _pool(project) if norm(p).startswith(old)]
    ok = sum(bool(c.ReplaceClip(n)) for c, n in jobs)
    assert pm.SaveProject(), "project not saved after the relink"
    running = lambda: "Resolve.exe" in subprocess.run(  # noqa: E731
        ["tasklist", "/FI", "IMAGENAME eq Resolve.exe"], capture_output=True, text=True).stdout
    resolve.Quit()  # Resolve keeps the media open: Windows refuses to move the folder while it runs
    for _ in range(90):
        if not running():
            break
        time.sleep(1)
    os.rmdir(dest)  # removes the junction only (rmdir never deletes a non-empty real folder)
    moved, err = False, ""
    for _ in range(10):  # file handles are released a moment after the process ends
        try:
            vdir.rename(dest)  # same drive: all or nothing
            moved = True
            break
        except OSError as e:
            err = str(e)
            time.sleep(1)
    moved = moved and dest.is_dir() and not os.path.isjunction(dest) and not vdir.exists()
    if not moved and not dest.exists():
        _junction(dest, vdir)  # keep the relinked paths working until the move is redone
    if not moved:
        raise SystemExit(f"relinked {ok}/{len(jobs)} but NOT moved ({err}): {dest} is a link to {vdir} for now; close "
                         f"whatever holds files there (Explorer, player), then run: ledger.py move {vdir.name}")
    handoff(f"done {vdir.name} ({ws_of(dest)}): moved into {DONE}, relinked {ok}/{len(jobs)} media, Resolve closed")
    print(f"done {vdir.name}: relinked {ok}/{len(jobs)} media to {dest} | moved {vdir} -> {dest} | "
          f"Resolve closed")


HANDOFF = ROOT / ".work" / "knowledge" / "handoffs" / "current.md"  # memory gateway: project state


def handoff(line, path=None):
    """Newest-first bullet under "Last completed:" of the gateway handoff + Updated date; no handoff -> skip."""
    import re
    p = Path(path or HANDOFF)
    if not p.is_file():
        return
    s = p.read_text("utf-8")
    s = re.sub(r"(?m)^Updated: .*$", f"Updated: {date.today()}", s, count=1)
    s = s.replace("Last completed:\n\n", f"Last completed:\n\n- {date.today()} {line}\n", 1)
    p.write_text(s, "utf-8")


def move(video, ws=None):
    """Redo the folder move of a done whose rename failed (Resolve must be closed)."""
    vdir = find_video(video, ws)
    dest = vdir.parent / DONE / vdir.name
    assert os.path.isjunction(dest), f"{dest} is not the temporary link of a failed done"
    os.rmdir(dest)
    try:
        vdir.rename(dest)
    except OSError as e:
        _junction(dest, vdir)
        raise SystemExit(f"still NOT moved ({e}); link restored")
    handoff(f"done {vdir.name} ({ws_of(dest)}): moved into {DONE} (ledger.py move)")
    print(f"moved {vdir} -> {dest}")


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
    tmp = Path(tempfile.mkdtemp())  # done's junction trick: link removal keeps the files, then the rename works
    (tmp / "v" / "audios").mkdir(parents=True); (tmp / "v" / "audios" / "a.mp3").write_text("x")
    (tmp / DONE).mkdir()
    assert _junction(tmp / DONE / "v", tmp / "v") and (tmp / DONE / "v" / "audios" / "a.mp3").read_text() == "x"
    os.rmdir(tmp / DONE / "v")
    assert (tmp / "v" / "audios" / "a.mp3").exists()
    (tmp / "v").rename(tmp / DONE / "v")
    assert (tmp / DONE / "v" / "audios" / "a.mp3").read_text() == "x" and not (tmp / "v").exists()
    rows = license_rows("| file | license |\n|---|---|\n| Z:\\S\\a.wav | Z:\\S\\1.pdf | x |\n| head | not a pdf |")
    assert rows == {norm(r"Z:\S\a.wav"): [r"Z:\S\a.wav", r"Z:\S\1.pdf", "x"]}, rows
    assert merge_spans([(70, 90), (10, 20), (20.5, 30)]) == [[10, 30], [70, 90]]
    assert _clock(65.4) == "01:05" and _clock(3725) == "1:02:05"
    h = tmp / "current.md"
    h.write_text("# H\n\nUpdated: 2000-01-01\n\nLast completed:\n\n- old\n", "utf-8")
    handoff("done v (W)", h)
    assert h.read_text("utf-8") == f"# H\n\nUpdated: {date.today()}\n\nLast completed:\n\n- {date.today()} done v (W)\n- old\n"
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
    elif a[:1] == ["move"] and len(a) >= 2:
        move(a[1], ws)
    elif a[:1] == ["done"] and len(a) >= 2:
        done(a[1], ws, proj, a[a.index("--timeline") + 1] if "--timeline" in a else "Master")  # user 2026-10-21: Edit
    elif a[:1] == ["rerender"] and len(a) >= 2:
        rerender(a[1], ws, proj, a[a.index("--timeline") + 1] if "--timeline" in a else "Edit")
    elif a[:1] == ["show"]:
        show(a[1] if len(a) > 1 else None)
    else:
        print(__doc__)
