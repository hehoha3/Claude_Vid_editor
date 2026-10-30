"""doc-edit pipeline state: which step a video is at + what the user changed since (user 2026-10-17: every step
starts from the user's own edits, less typing).

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/state.py snap <video> <step> [<audios-folder>]   # end of a step
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/state.py diff <video>                            # start of the next
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/state.py --selftest

Snapshot = items of timelines Edit + Open (track, start, end, file; read only, the user's timeline restored) when
the open Resolve project holds <video> (own project, or day project vid_DDMMYY: only its Chann_N timelines), files of
D:/AI_video/_check and _nologo, and the mtimes of the files the user edits (spec.txt, plan.md, missing_prompts.txt, the hide-logo check list, the audios folder). Stored in
.work/doc_edit/<video>/state.json; diff prints the last step and every change, grouped, short.
"""
import datetime as dt, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from dvr_cowork.config import load_config  # noqa: E402

AI = Path(load_config()["paths"]["ai_video"])
SHOW = 8  # items listed per group, the rest counted


def timelines(video, audios=None):
    """{"Edit": {"V1@12.00": "file | end 15.20"}, "Open": {...}} or a note why Resolve was not read. The open project
    must hold <video>: its own project, or the day project vid_DDMMYY (place.py's project.txt, plan.same_project) where
    only the video's channel timelines are read (DVR_CHANNEL from its D:/Chann_N_* path, never the other "Edit")."""
    try:
        import plan
        from dvr_cowork.cli import _items, _timelines
        from dvr_cowork.resolve_conn import connect
        from dvr_cowork.resolve_ops import use_channel
        pj = ROOT / ".work" / "doc_edit" / video / "plan.json"
        use_channel(audios or (json.loads(pj.read_text("utf-8")).get("video_dir") if pj.exists() else None))
        pr = connect(load_config()).GetProjectManager().GetCurrentProject()
        if not pr or not plan.same_project(pr.GetName(), video):
            return f"not read (open project {pr and pr.GetName()!r} does not hold {video!r})"
        return {t.GetName(): {f"{tr}@{a:.2f}": f"{Path(p).name} | end {b:.2f}" for tr, a, b, _, p in _items(t)}
                for t in _timelines(pr, {"edit", "open"})}
    except Exception as e:  # noqa: BLE001  Resolve closed: files are still compared
        return f"not read ({e})"


def files(video, audios):
    vdir = Path(audios).parent if audios else None
    work = ROOT / ".work" / "doc_edit" / video
    out = {f"_check/{p.name}": p.stat().st_size for p in (AI / "_check").glob("*") if p.is_file()}
    out |= {f"_nologo/{p.name}": p.stat().st_size for p in (AI / "_nologo").glob("*") if p.is_file()}
    out |= {f"_africa/_check/{p.relative_to(AI / '_africa' / '_check')}": p.stat().st_size
            for p in (AI / "_africa" / "_check").rglob("*") if p.is_file()}  # Africa holding folder (user 2026-10-22)
    watch = [work / "spec.txt", ROOT / ".work" / "hide_logo" / "check_list.txt"]
    if vdir:
        watch += [vdir / "plan.md", vdir / "missing_prompts.txt", *Path(audios).rglob("*")]
    return out | {f"mtime {p}": round(p.stat().st_mtime) for p in watch if p.is_file()}


def compare(old, new):
    """-> {"added": [...], "removed": [...], "changed": [...]} between two flat dicts."""
    return {"added": sorted(set(new) - set(old)), "removed": sorted(set(old) - set(new)),
            "changed": sorted(k for k in set(old) & set(new) if old[k] != new[k])}


def short(keys, d=None):
    s = [f"{k} ({d[k]})" if d else k for k in keys[:SHOW]]
    return ", ".join(s) + (f" ... +{len(keys) - SHOW}" if len(keys) > SHOW else "")


def main(cmd, video, step=None, audios=None):
    p = ROOT / ".work" / "doc_edit" / video / "state.json"
    if cmd == "snap":
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"step": step, "at": dt.datetime.now().isoformat(timespec="seconds"), "audios": audios,
                                 "timelines": timelines(video, audios), "files": files(video, audios)}, ensure_ascii=False,
                                indent=0), "utf-8")
        print(f"state: {video} step '{step}' recorded")
        return
    if not p.exists():
        print(f"state: {video} has no recorded step yet")
        return
    s = json.loads(p.read_text("utf-8"))
    print(f"state: {video} last step '{s['step']}' at {s['at']}")
    now_t, now_f = timelines(video, s.get("audios")), files(video, s.get("audios"))
    if isinstance(now_t, str) or isinstance(s["timelines"], str):
        print(f"timelines: {now_t if isinstance(now_t, str) else s['timelines']}")
    else:
        for name in sorted(set(now_t) | set(s["timelines"])):
            old, new = s["timelines"].get(name, {}), now_t.get(name, {})
            c = compare(old, new)
            if any(c.values()):
                print(f"{name}: user changed {sum(map(len, c.values()))} items | added: {short(c['added'], new)} | "
                      f"removed: {short(c['removed'], old)} | changed: {short(c['changed'], new)}")
            else:
                print(f"{name}: unchanged ({len(new)} items)")
    c = compare(s["files"], now_f)
    for k, v in c.items():
        if v:
            print(f"files {k}: {short(v)}")
    if not any(c.values()):
        print("files: unchanged")


def stage(vdir, done):
    """(stage, next command) of one video from the files it has: no Resolve, no tokens."""
    if done:
        return "done", "-"
    if not (vdir / "plan.md").exists():
        return "no plan", "/doc-edit <audios-folder>"
    if any(vdir.glob("Done_*.mp4")):
        return "rendered", "/doc-edit done"
    miss = vdir / "missing_prompts.txt"
    st = ROOT / ".work" / "doc_edit" / vdir.name / "state.json"
    last = json.loads(st.read_text("utf-8")).get("step") if st.exists() else None
    if last in ("P6", "color"):
        return "coloured", "/doc-edit done"
    if miss.exists() and miss.stat().st_size > 1:
        return "planned, prompts out", "Case 1: clips in _check -> /doc-edit ingest --fill / Case 2: /doc-edit fill-THIEU"
    return "planned", "/doc-edit fill, color"


def status():
    """One line per video of every workspace (config.toml [workspaces] globs), newest first."""
    import ledger
    for r in ledger.roots():
        print(f"{r.name}:")
        vids = [(d, False) for d in r.iterdir() if d.is_dir() and d.name != ledger.DONE and (d / "plan.md").exists() or
                d.is_dir() and d.name != ledger.DONE and (d / "audios").is_dir()]
        vids += [(d, True) for d in (r / ledger.DONE).glob("*") if d.is_dir()] if (r / ledger.DONE).is_dir() else []
        gone = {d.name.lower() for d, dn in vids if dn}  # a leftover folder of a finished video is not "in progress"
        vids = [(d, dn) for d, dn in vids if dn or d.name.lower() not in gone]
        for d, dn in sorted(vids, key=lambda x: x[0].stat().st_mtime, reverse=True):
            s, nxt = stage(d, dn)
            print(f"  {d.name:<12} {s:<22} next: {nxt}")


def selftest():
    c = compare({"V1@0.00": "a | end 2.00", "V1@2.00": "b | end 4.00"}, {"V1@0.00": "x | end 2.00", "V1@4.00": "c"})
    assert c == {"added": ["V1@4.00"], "removed": ["V1@2.00"], "changed": ["V1@0.00"]}, c
    assert short([str(i) for i in range(10)]).endswith("... +2")
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    selftest() if "--selftest" in sys.argv else status() if a[:1] == ["status"] else main(*a)
