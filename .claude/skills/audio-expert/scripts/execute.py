"""audio-expert execute: placement_plan.json -> timeline "Edit" (A5-A9 only), with backup, readback and journal.

    .venv/Scripts/python.exe .claude/skills/audio-expert/scripts/execute.py <video> <run_id> [--replace] [--rollback]

- Refuses on stale timeline (A2 / V1 differ from timeline_snapshot_before.json) and on timeline "Master".
- Backup = DuplicateTimeline "<name>_bak_audio_<stamp>" before any write. A1-A4 and V1 are never touched.
- Tracks A6-A9 must be empty unless --replace (clears them after the backup; they only hold earlier doc-edit output).
  A5 keeps what it has; new A5 items are added in gaps (the plan was checked for overlaps with itself only).
- Re-run safe: a placement already on the timeline (same track, start, end) is skipped. Journal:
  runs/<run_id>/execution_log.jsonl. --rollback removes exactly the journaled items (track, start, end, name must match).
- Starting level + edge fades come from doc-edit place.py (TARGET / FADE); the real mix is by ear.
"""
import datetime as dt, importlib.util, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
from dvr_cowork.config import load_config  # noqa: E402
from dvr_cowork.resolve_conn import connect  # noqa: E402
from dvr_cowork.resolve_ops import (AUDIO_TOP, _norm, audio_bin, clip_fps, ensure_audio_track,  # noqa: E402
                                    ensure_bin, find_clip, find_timeline, get_project, timeline_fps)
import plan as pl  # noqa: E402

_s = importlib.util.spec_from_file_location("doc_place", ROOT / ".claude/skills/doc-edit/scripts/place.py")
dp = importlib.util.module_from_spec(_s)
_s.loader.exec_module(dp)  # TARGET, FADE, loudness (main() is guarded)


def main(video, run, replace, rollback):
    rd = ROOT / ".work" / "audio_expert" / video / "runs" / run
    plan = json.loads((rd / "placement_plan.json").read_text("utf-8"))["placements"]
    before = json.loads((rd / "timeline_snapshot_before.json").read_text("utf-8"))
    log_p = rd / "execution_log.jsonl"
    cfg = load_config()
    resolve = connect(cfg)
    pm, project = get_project(resolve)
    tl = find_timeline(project, cfg["resolve"]["timeline_name"])
    assert tl and tl.GetName().lower() != "master", 'timeline "Master" is never touched'
    orig = project.GetCurrentTimeline()
    project.SetCurrentTimeline(tl)
    fps = timeline_fps(tl, project)
    rate = round(fps)
    t0 = int(tl.GetStartFrame())
    snap = pl.snapshot(tl, fps)

    if rollback:
        done = [json.loads(l) for l in log_p.read_text("utf-8").splitlines() if l]
        live = {(n, a, b, nm): it for n in range(5, 10)
                for it in tl.GetItemListInTrack("audio", n) or []
                for a, b, nm in [(int(it.GetStart()) - t0, int(it.GetEnd()) - t0, it.GetName())]}
        hit = [live[(d["track"], d["start"], d["end"], d["name"])] for d in done
               if (d["track"], d["start"], d["end"], d["name"]) in live]
        if hit:
            tl.DeleteClips(hit, False)
        print(f"rollback: removed {len(hit)}/{len(done)} journaled items; others left alone")
        log_p.rename(rd / f"execution_log_rolledback_{dt.datetime.now():%H%M%S}.jsonl")
        pm.SaveProject()
        return

    cur = json.loads(json.dumps(snap))
    if cur["audio"]["2"] != before["audio"]["2"]:
        raise SystemExit("stale: A2 changed since the plan was made; re-run plan.py")
    if cur["video1"] != before["video1"]:
        raise SystemExit("stale: V1 changed since the plan was made; re-run plan.py")
    busy = {f"A{n}": len(v) for n, v in snap["audio"].items() if n in (6, 7, 8, 9) and v}
    if busy and not replace and not log_p.exists():
        raise SystemExit(f"A6-A9 not empty {busy}; re-run with --replace (cleared after the backup)")

    mp = project.GetMediaPool()
    root = mp.GetRootFolder()
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    mp.SetCurrentFolder(root)
    if not log_p.exists():
        bak = f"{tl.GetName()}_bak_audio_{stamp}"
        assert tl.DuplicateTimeline(bak), "backup failed, nothing changed"
        project.SetCurrentTimeline(tl)
        print("backup:", bak)
        if replace and busy:
            tl.DeleteClips([i for n in (6, 7, 8, 9) for i in tl.GetItemListInTrack("audio", n) or []], False)
            print("cleared:", busy)
    ensure_audio_track(tl, 9, 2, print)

    look = ensure_bin(mp, AUDIO_TOP)  # whole "4. Audio": a file already in any sub-bin is reused
    items, new = {}, {}  # new: file -> sub-bin of its first track (Ambience | Music | SFX), imported once
    for p in plan:
        k = _norm(p["source_path"])
        items[k] = items.get(k) or find_clip(look, p["source_path"])
        if not items[k]:
            new.setdefault(os.path.normpath(p["source_path"]), audio_bin(p["track_index"]))
    for name in sorted(set(new.values())):
        mp.SetCurrentFolder(ensure_bin(mp, name))
        for it in mp.ImportMedia(sorted(f for f, b in new.items() if b == name)) or []:
            items[_norm(it.GetClipProperty("File Path"))] = it

    have = {(n, int(i.GetStart()) - t0, int(i.GetEnd()) - t0) for n in range(5, 10)
            for i in tl.GetItemListInTrack("audio", n) or []}
    cache_p = ROOT / ".work" / "doc_edit" / video / "loudness.json"
    cache = json.loads(cache_p.read_text("utf-8")) if cache_p.exists() else {}
    ok = skipped = 0
    failed, vol_fail = [], 0
    for p in plan:
        tr, a, b2 = p["track_index"], p["timeline_start_frame_relative"], p["timeline_end_frame_relative_exclusive"]
        if (tr, a, b2) in have:
            skipped += 1
            continue
        it = items.get(_norm(p["source_path"]))
        if not it:
            failed.append(p["placement_id"]); continue
        n = b2 - a
        cf = clip_fps(it, fps)
        s0, k = round(p["source_in_seconds"] * cf), round(n * cf / fps)
        ti = None
        for _ in range(3):
            res = mp.AppendToTimeline([{"mediaPoolItem": it, "startFrame": s0, "endFrame": s0 + k, "mediaType": 2,
                                        "trackIndex": tr, "recordFrame": t0 + a}])
            ti = res[0] if res else None
            if not ti:
                break
            d = int(ti.GetEnd()) - int(ti.GetStart())
            if d == n:
                break
            tl.DeleteClips([ti], False)
            k += round((n - d) * cf / fps) or (1 if n > d else -1)
            ti = None
        if not ti:
            failed.append(p["placement_id"]); continue
        fd = round(min(dp.FADE[tr], n / rate / 2) * rate)
        if fd:
            ti.SetFades({"FadeIn": fd, "FadeOut": fd})
        lu = dp.loudness(p["source_path"], cache)
        if lu is not None and not ti.SetProperty("AudioVolume", round(dp.TARGET[tr] - lu, 1)):
            vol_fail += 1
        with log_p.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"placement_id": p["placement_id"], "track": tr, "start": a, "end": b2,
                                "name": ti.GetName(), "t": dt.datetime.now().isoformat(timespec="seconds")}) + "\n")
        ok += 1
    cache_p.write_text(json.dumps(cache, indent=0), "utf-8")

    after = json.loads(json.dumps(pl.snapshot(tl, fps)))
    (rd / "timeline_snapshot_after.json").write_text(json.dumps(after), "utf-8")
    bad = []
    for p in plan:  # readback
        key = (p["track_index"], p["timeline_start_frame_relative"], p["timeline_end_frame_relative_exclusive"])
        if not any(a == key[1] and e == key[2] for a, e, _ in after["audio"].get(str(key[0]), [])):
            bad.append(p["placement_id"])
    protected = all(after["audio"].get(str(n)) == before["audio"].get(str(n)) for n in (1, 2, 3, 4))
    print(f"placed {ok}, already there {skipped}, failed {failed}; readback mismatches {bad}; "
          f"volume not set {vol_fail}; A1-A4 unchanged: {protected}; V1 unchanged: {after['video1'] == before['video1']}; "
          f"end {after['end_rel']} vs {before['end_rel']}")
    pm.SaveProject()
    if orig and orig.GetName() != tl.GetName():
        project.SetCurrentTimeline(orig)
        print(f'back on timeline "{orig.GetName()}"')


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    main(a[0], a[1], "--replace" in sys.argv, "--rollback" in sys.argv)
