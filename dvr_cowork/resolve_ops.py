"""Operations against the Resolve scripting API. stdlib-only (also runs inside Resolve).

About "blade": the Resolve scripting API has no Blade/Split command. Blading a clip in the UI
produces N timeline items that all reference the SAME media pool clip with different source
in/out points. apply_plan() creates exactly that structure directly (AppendToTimeline with
startFrame/endFrame/recordFrame on one MediaPoolItem): one source file, no rendered pieces.
You can still roll/slip/ripple each piece in the UI like any bladed clip.
"""
from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path

from .layout import layout
from .timecode import frames_to_tc, parse_clock, tc_to_frames


class OpsError(Exception):
    pass


class OverlapError(OpsError):
    def __init__(self, conflicts):
        self.conflicts = conflicts
        lines = ", ".join(f"#{c['line']}->#{c['next']} ({c['overlap_s']}s)" for c in conflicts)
        super().__init__(f"{len(conflicts)} narration line(s) run into the next timestamp: {lines}")


# ----------------------------------------------------------------- lookups
def get_project(resolve):
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject() if pm else None
    if not project:
        raise OpsError("No project is open in DaVinci Resolve.")
    return pm, project


def list_timelines(project):
    return [project.GetTimelineByIndex(i) for i in range(1, int(project.GetTimelineCount() or 0) + 1)]


def find_timeline(project, name):
    for tl in list_timelines(project):
        if tl and tl.GetName() == name:
            return tl
    return None


def find_bin(root, name):
    for f in root.GetSubFolderList() or []:
        if f.GetName() == name:
            return f
    return None


def _norm(p):
    return os.path.normcase(os.path.normpath(os.path.abspath(p))) if p else ""


def find_clip(folder, path):
    target = _norm(path)
    for c in folder.GetClipList() or []:
        try:
            if _norm(c.GetClipProperty("File Path")) == target:
                return c
        except Exception:  # noqa: BLE001
            continue
    for sub in folder.GetSubFolderList() or []:
        hit = find_clip(sub, path)
        if hit:
            return hit
    return None


def timeline_fps(tl, project):
    v = tl.GetSetting("timelineFrameRate") or project.GetSetting("timelineFrameRate")
    try:
        return float(v)
    except (TypeError, ValueError) as e:
        raise OpsError(f"Cannot read timeline frame rate (got {v!r})") from e


def clip_fps(item, default):
    try:
        v = float(item.GetClipProperty("FPS"))
        return v if v > 0 else default
    except Exception:  # noqa: BLE001
        return default


def clip_channels(item):
    try:
        return int(str(item.GetClipProperty("Audio Ch")).strip() or 2)
    except Exception:  # noqa: BLE001
        return 2


def ensure_audio_track(tl, idx, channels, log):
    n = int(tl.GetTrackCount("audio") or 0)
    sub = "mono" if channels == 1 else "stereo"
    created = 0
    while n < idx:
        ok = tl.AddTrack("audio", sub)
        if not ok:
            ok = tl.AddTrack("audio", {"audioType": sub})
        new_n = int(tl.GetTrackCount("audio") or 0)
        if not ok or new_n <= n:
            raise OpsError(f"Could not create audio track A{n + 1}")
        n = new_n
        created += 1
        log(f"created audio track A{n} ({sub})")
    return created


def _item_path(ti):
    try:
        mpi = ti.GetMediaPoolItem()
        return mpi.GetClipProperty("File Path") if mpi else ""
    except Exception:  # noqa: BLE001
        return ""


# ----------------------------------------------------------------- vo-sync apply
def apply_plan(resolve, plan, cfg, log=print, dry_run=False, force_clear=False,
               on_overlap=None, markers=None, backup=None):
    rc, ac = cfg["resolve"], cfg["align"]
    track = int(rc["audio_track"])
    markers = ac.get("markers", False) if markers is None else markers
    backup = rc.get("backup_timeline", True) if backup is None else backup
    audio = plan["audio"]
    if not os.path.isfile(audio):
        raise OpsError(f"Audio file not found: {audio}")

    pm, project = get_project(resolve)
    tl = find_timeline(project, rc["timeline_name"])
    if not tl:
        names = ", ".join(t.GetName() for t in list_timelines(project) if t)
        raise OpsError(f'Timeline "{rc["timeline_name"]}" not found in project '
                       f'"{project.GetName()}". Timelines: {names}')
    try:
        resolve.OpenPage("edit")
    except Exception:  # noqa: BLE001
        pass
    project.SetCurrentTimeline(tl)
    fps_tl = timeline_fps(tl, project)
    tl_start = int(tl.GetStartFrame())
    media_pool = project.GetMediaPool()
    root = media_pool.GetRootFolder()
    bin_ = find_bin(root, rc["audio_bin"])
    item = find_clip(bin_, audio) if bin_ else None
    fps_clip = clip_fps(item, fps_tl) if item else fps_tl

    items, conflicts = layout(plan["segments"], fps_tl, fps_clip, ac, on_overlap)
    result = {"project": project.GetName(), "timeline": tl.GetName(), "fps": fps_tl,
              "clip_fps": fps_clip, "tl_start": tl_start, "track": track, "items": items,
              "conflicts": conflicts, "dry_run": dry_run, "bin_created": False,
              "imported": False, "removed": 0, "tracks_created": 0, "backup": None,
              "placed": 0, "failed": [], "max_start_dev": 0, "max_in_dev": None}
    if conflicts:
        raise OverlapError(conflicts)

    existing = []
    if int(tl.GetTrackCount("audio") or 0) >= track:
        existing = tl.GetItemListInTrack("audio", track) or []
    ours = [ti for ti in existing if _norm(_item_path(ti)) == _norm(audio)]
    others = [ti for ti in existing if ti not in ours]
    if others and not force_clear:
        raise OpsError(f"Track A{track} already holds {len(others)} clip(s) from other media. "
                       f"Move them, or re-run with --force-clear to replace everything on A{track}.")
    if dry_run:
        result["removed"] = len(ours) + (len(others) if force_clear else 0)
        log(f"dry-run: would place {len(items)} segments on A{track} of '{tl.GetName()}' @ {fps_tl:g} fps")
        return result

    # --- from here on the project is modified
    if backup:
        stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"{tl.GetName()}_bak_{stamp}"
        try:
            media_pool.SetCurrentFolder(root)
            if tl.DuplicateTimeline(name):
                result["backup"] = name
                log(f"backup timeline: {name}")
        except Exception as e:  # noqa: BLE001
            log(f"warning: backup failed ({e}); continuing")
        project.SetCurrentTimeline(tl)

    if not bin_:
        bin_ = media_pool.AddSubFolder(root, rc["audio_bin"])
        if not bin_:
            raise OpsError(f'Could not create bin "{rc["audio_bin"]}"')
        result["bin_created"] = True
        log(f'created bin "{rc["audio_bin"]}"')
    if not item:
        media_pool.SetCurrentFolder(bin_)
        imported = media_pool.ImportMedia([os.path.normpath(audio)])
        if not imported:
            raise OpsError(f"Resolve could not import {audio}")
        item = imported[0]
        result["imported"] = True
        log(f'imported "{os.path.basename(audio)}" into bin "{rc["audio_bin"]}"')
        new_fps = clip_fps(item, fps_tl)
        if abs(new_fps - fps_clip) > 1e-3:  # recompute with the real clip rate
            fps_clip = new_fps
            items, conflicts = layout(plan["segments"], fps_tl, fps_clip, ac, on_overlap)
            if conflicts:
                raise OverlapError(conflicts)
            result.update(items=items, clip_fps=fps_clip)

    result["tracks_created"] = ensure_audio_track(tl, track, clip_channels(item), log)
    if ours or (others and force_clear):
        to_del = ours + (others if force_clear else [])
        tl.DeleteClips(to_del, False)
        result["removed"] = len(to_del)
        log(f"removed {len(to_del)} old item(s) from A{track}")

    # one AppendToTimeline per segment -> exact item <-> segment mapping
    placed = []
    for it in items:
        info = {
            "mediaPoolItem": item,
            "startFrame": int(it["src_in_f"]),
            # endFrame passed as last frame; whether Resolve treats it inclusive or exclusive,
            # the item is at most 1 frame of tail-silence shorter. verify() reports the result.
            "endFrame": int(it["src_out_f"]) - 1,
            "mediaType": 2,
            "trackIndex": track,
            "recordFrame": tl_start + int(it["rec_f"]),
        }
        res = media_pool.AppendToTimeline([info])
        ti = res[0] if res else None
        if not ti:
            result["failed"].append(it["i"])
            continue
        placed.append((it, ti))
        color = None
        if "pushed" in it["flags"] or "speech_cut" in it["flags"]:
            color = ac.get("color_pushed")
        elif any(f in it["flags"] for f in ("low_confidence", "text_not_heard", "no_pause", "boundary_uncertain")):
            color = ac.get("color_low_confidence")
        if color:
            try:
                ti.SetClipColor(color)
            except Exception:  # noqa: BLE001
                pass
    result["placed"] = len(placed)
    log(f"placed {len(placed)}/{len(items)} segments on A{track}")

    _verify(placed, tl_start, result)
    if markers:
        _write_markers(tl, items, ac, fps_tl)
    if rc.get("save_project", True):
        try:
            pm.SaveProject()
        except Exception:  # noqa: BLE001
            pass
    return result


def _verify(placed, tl_start, result):
    start_dev, in_dev, rows = 0, None, []
    for it, ti in placed:
        try:
            s = int(ti.GetStart()) - (tl_start + it["rec_f"])
        except Exception:  # noqa: BLE001
            s = None
        try:
            lo = ti.GetLeftOffset()
            d_in = None if lo is None else int(round(float(lo))) - it["src_in_f"]
        except Exception:  # noqa: BLE001
            d_in = None
        if s is not None:
            start_dev = max(start_dev, abs(s))
        if d_in is not None:
            in_dev = max(in_dev or 0, abs(d_in))
        if (s or 0) != 0 or (d_in or 0) != 0:
            rows.append({"line": it["i"], "start_dev_f": s, "src_in_dev_f": d_in})
    result["max_start_dev"] = start_dev
    result["max_in_dev"] = in_dev
    result["deviations"] = rows


def _write_markers(tl, items, ac, fps_tl):
    try:
        for frame, m in list((tl.GetMarkers() or {}).items()):
            if str(m.get("customData", "")).startswith("vo_sync"):
                tl.DeleteMarkerAtFrame(frame)
    except Exception:  # noqa: BLE001
        pass
    for it in items:
        onset = it["rec_f"] + round(it["speech_in_f"] - it["src_in_f"])
        try:
            tl.AddMarker(int(onset), "Sky", f"VO {it['i']}", it["text"][:240], 1, f"vo_sync:{it['i']}")
        except Exception:  # noqa: BLE001
            pass


# ----------------------------------------------------------------- read-only helpers
def verify_track(resolve, plan, cfg):
    """Compare what is on the VO track now with the plan (after manual edits, etc.)."""
    rc = cfg["resolve"]
    _, project = get_project(resolve)
    tl = find_timeline(project, rc["timeline_name"])
    if not tl:
        raise OpsError(f'Timeline "{rc["timeline_name"]}" not found')
    fps = timeline_fps(tl, project)
    start = int(tl.GetStartFrame())
    track = int(rc["audio_track"])
    on_track = [ti for ti in (tl.GetItemListInTrack("audio", track) or [])
                if _norm(_item_path(ti)) == _norm(plan["audio"])]
    starts = sorted(int(ti.GetStart()) - start for ti in on_track)
    rate = round(fps) if cfg["align"].get("timestamp_clock", "timecode") == "timecode" else fps
    return {"fps": fps, "items_on_track": len(on_track), "segments_in_plan": len(plan["segments"]),
            "first_starts": [frames_to_tc(s + start, fps) for s in starts[:5]],
            "expected_first": [frames_to_tc(round(s["ts"] * rate) + start, fps) for s in plan["segments"][:5]]}


def project_info(resolve, cfg):
    _, project = get_project(resolve)
    rc = cfg["resolve"]
    cur = project.GetCurrentTimeline()
    tl = find_timeline(project, rc["timeline_name"]) or cur
    info = {"project": project.GetName(),
            "timelines": [t.GetName() for t in list_timelines(project) if t],
            "current_timeline": cur.GetName() if cur else None}
    try:
        info["resolve_version"] = resolve.GetVersionString()
    except Exception:  # noqa: BLE001
        pass
    if tl:
        fps = timeline_fps(tl, project)
        tracks = {}
        for kind in ("video", "audio", "subtitle"):
            n = int(tl.GetTrackCount(kind) or 0)
            tracks[kind] = [{"n": i, "name": tl.GetTrackName(kind, i),
                             "items": len(tl.GetItemListInTrack(kind, i) or [])} for i in range(1, n + 1)]
        info["timeline"] = {
            "name": tl.GetName(), "fps": fps,
            "resolution": f'{tl.GetSetting("timelineResolutionWidth")}x{tl.GetSetting("timelineResolutionHeight")}',
            "start_tc": frames_to_tc(int(tl.GetStartFrame()), fps),
            "duration_tc": frames_to_tc(int(tl.GetEndFrame()) - int(tl.GetStartFrame()), fps),
            "tracks": tracks}
        bin_ = find_bin(project.GetMediaPool().GetRootFolder(), rc["audio_bin"])
        info["audio_bin_exists"] = bool(bin_)
    return info


def export_frames(resolve, cfg, times, out_dir):
    """Export graded stills at timeline positions ('mm:ss', 'hh:mm:ss' or full 'hh:mm:ss:ff' TC)."""
    _, project = get_project(resolve)
    tl = find_timeline(project, cfg["resolve"]["timeline_name"]) or project.GetCurrentTimeline()
    if not tl:
        raise OpsError("No timeline available")
    project.SetCurrentTimeline(tl)
    fps = timeline_fps(tl, project)
    start = int(tl.GetStartFrame())
    out_dir = Path(out_dir).resolve()  # Resolve writes nothing for a relative path
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        page = resolve.GetCurrentPage()
    except Exception:  # noqa: BLE001
        page = None
    results = []
    for t in times:
        if t.count(":") == 3:
            frame = tc_to_frames(t, fps)
        else:
            frame = start + round(parse_clock(t) * round(fps))
        tc = frames_to_tc(frame, fps)
        path = out_dir / f"frame_{tc.replace(':', '-')}.png"
        tl.SetCurrentTimecode(tc)
        ok = project.ExportCurrentFrameAsStill(str(path))
        if not ok and page != "color":
            resolve.OpenPage("color")
            tl.SetCurrentTimecode(tc)
            ok = project.ExportCurrentFrameAsStill(str(path))
        results.append({"at": t, "tc": tc, "path": str(path), "ok": bool(ok) and path.exists()})
    if page:
        try:
            resolve.OpenPage(page)
        except Exception:  # noqa: BLE001
            pass
    return results
