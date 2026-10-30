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
import re
import time
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


# One project per day may hold one video per channel (user 2026-10-25, project vid_251026): top bins Chann_1, Chann_2 ...
# each with the old sub-bins and its own timeline "Edit" in "Chann_N/6. Timeline". DVR_CHANNEL (set by use_channel()
# from the video's path D:\Chann_N_*\<video>) points every bin / timeline lookup into that channel's bin; a project
# without that bin works as before (one video per project).
CHANNEL_ENV = "DVR_CHANNEL"
_CHANN = re.compile(r"(?i)\bchann_(\d+)")


def use_channel(path):
    r"""D:\Chann_2_darkAmazona\africa_1\audios -> DVR_CHANNEL=Chann_2 (an explicit other value is an error). -> channel."""
    m = _CHANN.search(str(path or ""))
    ch = os.environ.get(CHANNEL_ENV)
    if m:
        want = f"Chann_{m[1]}"
        if ch and ch.lower() != want.lower():
            raise OpsError(f"{CHANNEL_ENV}={ch} but {path} belongs to {want}")
        os.environ[CHANNEL_ENV] = ch = want
    return ch


def channel_bin(media_pool):
    """The active channel's top bin, None when no channel is set or this project has no such bin."""
    ch = os.environ.get(CHANNEL_ENV)
    return find_bin(media_pool.GetRootFolder(), ch) if ch else None


def pool_root(media_pool):
    """Root of every bin path ("4. Audio/Music", "6. Timeline"): the channel's bin, else the media pool root."""
    return channel_bin(media_pool) or media_pool.GetRootFolder()


def _clip_ids(folder):
    out, stack = set(), [folder]
    while stack:
        f = stack.pop()
        stack += f.GetSubFolderList() or []
        out |= {c.GetUniqueId() for c in f.GetClipList() or []}
    return out


def find_timeline(project, name):
    """Timeline `name`; in a channel project only the one inside the channel's bin. Several of that name and no
    channel to choose -> OpsError (never a guess: the other channel's "Edit" would be changed)."""
    tls = [t for t in list_timelines(project) if t and t.GetName() == name]
    b = channel_bin(project.GetMediaPool())
    if b:
        ids = _clip_ids(b)
        tls = [t for t in tls if t.GetMediaPoolItem() and t.GetMediaPoolItem().GetUniqueId() in ids]
    if len(tls) > 1:
        raise OpsError(f'{len(tls)} timelines named "{name}" in project {project.GetName()}'
                       + (f" inside bin {os.environ[CHANNEL_ENV]}" if b else
                          f": set {CHANNEL_ENV}=Chann_N (or run on the video's D:\\Chann_N_* path)"))
    return tls[0] if tls else None


def find_bin(root, name):
    """Bin by name or path ("4. Audio/Narrator") under root; None if any level is missing."""
    for part in name.split("/"):
        root = next((f for f in root.GetSubFolderList() or [] if f.GetName() == part), None)
        if not root:
            return None
    return root


TIMELINE_BIN = "6. Timeline"


def tidy_timelines(project):
    """Move every timeline of the project into bin "6. Timeline" (created if missing; user 2026-10-24: timelines always
    live there). Timeline "Master" is never touched; sub-bins of "6. Timeline" are left as they are. -> moved count."""
    mp = project.GetMediaPool()
    dst = ensure_bin(mp, TIMELINE_BIN)
    want = set()
    for i in range(1, (project.GetTimelineCount() or 0) + 1):
        t = project.GetTimelineByIndex(i)
        it = t.GetMediaPoolItem() if t and t.GetName() != "Master" else None
        if it:
            want.add(it.GetUniqueId())
    move, stack = [], [mp.GetRootFolder()]
    ch = (os.environ.get(CHANNEL_ENV) or "").lower() if channel_bin(mp) else ""
    while stack:
        f = stack.pop()
        if f.GetUniqueId() == dst.GetUniqueId() or (_CHANN.fullmatch(f.GetName()) and f.GetName().lower() != ch):
            continue  # another channel's timelines stay in its own bin
        stack += f.GetSubFolderList() or []
        move += [c for c in f.GetClipList() or [] if c.GetUniqueId() in want]
    if move and not mp.MoveClips(move, dst):
        raise OpsError(f'MoveClips of {len(move)} timeline(s) into "{TIMELINE_BIN}" failed')
    return len(move)


def backup_timeline(project, tl, name):
    """Duplicate `tl` as `name` into bin "6. Timeline" (created if missing), then move any other timeline lying outside
    it there too (tidy_timelines; a failure there never blocks the backup), restore the current bin, keep `tl`
    current. -> True when the copy was made. Every Resolve change starts here: one writer process at a time + the
    write log (jobs.writer_begin, V2 spec; a second writer raises before anything changes)."""
    from .jobs import writer_begin
    writer_begin(project.GetName(), os.environ.get(CHANNEL_ENV), tl.GetName(), name)
    mp = project.GetMediaPool()
    root = mp.GetRootFolder()
    prev = mp.GetCurrentFolder()
    mp.SetCurrentFolder(ensure_bin(mp, TIMELINE_BIN))
    try:
        ok = bool(tl.DuplicateTimeline(name))
        try:
            tidy_timelines(project)
        except Exception:  # noqa: BLE001  (bins are housekeeping; the backup is what matters)
            pass
        return ok
    finally:
        mp.SetCurrentFolder(prev or root)
        project.SetCurrentTimeline(tl)


def ensure_bin(media_pool, name):
    """find_bin from pool_root (the channel's bin or the media pool root), creating the missing levels."""
    b = pool_root(media_pool)
    for part in name.split("/"):
        b = find_bin(b, part) or media_pool.AddSubFolder(b, part)
        if not b:
            raise OpsError(f'Could not create bin "{name}"')
    return b


# Sub-bins of "4. Audio" (user 2026-10-16): narration, music, SFX; beds/environment/natural (A3-A6) -> Ambience.
AUDIO_TOP = "4. Audio"
AUDIO_SUB = {2: "Narrator", 7: "Music", 8: "SFX", 9: "SFX"}


def audio_bin(track):
    return f"{AUDIO_TOP}/{AUDIO_SUB.get(track, 'Ambience')}"


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
    # one narration file bladed per sentence, or one file per sentence (segment "audio", vo-sync on a folder)
    seg_audio = [s.get("audio") or plan["audio"] for s in plan["segments"]]
    files = sorted(set(seg_audio))
    if missing := [f for f in files if not os.path.isfile(f)]:
        raise OpsError(f"Audio file not found: {missing[0]}" + (f" (+{len(missing) - 1})" if len(missing) > 1 else ""))
    keys = {_norm(f) for f in files}

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
    root = pool_root(media_pool)
    pool = find_bin(root, rc["audio_bin"].split("/")[0])  # search all of "4. Audio": no duplicate imports
    found = {_norm(f): find_clip(pool, f) if pool else None for f in files}
    item = next((v for v in found.values() if v), None)  # fps / channels reference (all narration files alike)
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
    ours = [ti for ti in existing if _norm(_item_path(ti)) in keys]
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
            if backup_timeline(project, tl, name):
                result["backup"] = name
                log(f"backup timeline: {name}")
        except Exception as e:  # noqa: BLE001
            log(f"warning: backup failed ({e}); continuing")
        project.SetCurrentTimeline(tl)

    new = [f for f in files if not found[_norm(f)]]
    if new:
        result["bin_created"] = not find_bin(root, rc["audio_bin"])
        media_pool.SetCurrentFolder(ensure_bin(media_pool, rc["audio_bin"]))
        for it in media_pool.ImportMedia([os.path.normpath(f) for f in new]) or []:
            found[_norm(it.GetClipProperty("File Path"))] = it
        if bad := [f for f in new if not found[_norm(f)]]:
            raise OpsError(f"Resolve could not import {bad[0]}" + (f" (+{len(bad) - 1})" if len(bad) > 1 else ""))
        result["imported"] = len(new)
        log(f'imported {len(new)} file(s) into bin "{rc["audio_bin"]}"')
    if item is None:  # nothing was in the pool: fps of the first import
        item = found[_norm(files[0])]
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
    for it, src in zip(items, seg_audio):  # layout keeps the segment order
        info = {
            "mediaPoolItem": found[_norm(src)],
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
    try:  # a bilingual timestamp file also gives the subtitles; never fails the A2 placement
        place_subtitles(project, tl, plan, items, fps_tl, fps_clip, log)
    except Exception as e:  # noqa: BLE001
        log(f"subtitles: failed ({e})")
    if markers:
        _write_markers(tl, items, ac, fps_tl)
    if rc.get("save_project", True):
        try:
            pm.SaveProject()
        except Exception:  # noqa: BLE001
            pass
    return result


def _srt_time(sec):
    ms = round(sec * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def place_subtitles(project, tl, plan, items, fps_tl, fps_clip, log=print, section="vietnamese"):
    """`## Vietnamese` part of a bilingual timestamp file -> <video>\\subtitles_vi.srt (sentence n shown while
    A2 item n speaks) -> Subtitle 1. Skipped when the file has no such part or Subtitle 1 is not empty."""
    from .timestamps import parse_timestamp_file
    ts = Path(plan["timestamps"])
    if f"## {section}" not in ts.read_text(encoding="utf-8-sig").lower():
        return None
    subs = parse_timestamp_file(ts, section)
    if len(subs) != len(items):
        log(f"subtitles: skipped, {len(subs)} {section} lines vs {len(items)} narration lines")
        return None
    ratio = fps_tl / fps_clip  # speech_*_f / src_in_f are source frames, rec_f timeline frames
    spans = [(it["rec_f"] + (it["speech_in_f"] - it["src_in_f"]) * ratio,
              it["rec_f"] + (it["speech_out_f"] - it["src_in_f"]) * ratio) for it in items]
    rows = []
    for k, ((a, b), c) in enumerate(zip(spans, subs)):
        if k + 1 < len(spans):
            b = min(b, spans[k + 1][0] - 1)
        rows.append(f"{k + 1}\n{_srt_time(a / fps_tl)} --> {_srt_time(b / fps_tl)}\n{c.text}\n")
    srt = ts.parent.parent / f"subtitles_{section[:2]}.srt"
    srt.write_text("\n".join(rows), encoding="utf-8")
    log(f"subtitles: {len(rows)} lines -> {srt}")

    n = int(tl.GetTrackCount("subtitle") or 0)
    if n and tl.GetItemListInTrack("subtitle", 1):
        log("subtitles: Subtitle 1 is not empty, not placed (the .srt is written)")
        return srt
    if not n:
        tl.AddTrack("subtitle")
    media_pool = project.GetMediaPool()
    media_pool.SetCurrentFolder(ensure_bin(media_pool, "5. Subtitles"))
    clip = (media_pool.ImportMedia([str(srt)]) or [None])[0]
    if not clip or not media_pool.AppendToTimeline([{"mediaPoolItem": clip, "recordFrame": int(tl.GetStartFrame())}]):
        log("subtitles: import/append failed, drag the .srt onto the timeline by hand")
        return srt
    got = tl.GetItemListInTrack("subtitle", 1) or []
    log(f"subtitles: {len(got)} item(s) on Subtitle 1, first at frame "
        f"{got[0].GetStart() - int(tl.GetStartFrame()) if got else '-'} (expected {round(spans[0][0])})")
    return srt


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
    try:
        tl = find_timeline(project, rc["timeline_name"]) or cur
    except OpsError:  # several "Edit" and no channel: show the current one
        tl = cur
    info = {"project": project.GetName(), "channel": os.environ.get(CHANNEL_ENV) if channel_bin(project.GetMediaPool()) else None,
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
        bin_ = find_bin(pool_root(project.GetMediaPool()), rc["audio_bin"])
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
    results, last = [], None

    def grab(tc, path):
        # africa_1 2026-10-22: exported right after the jump, the 2nd still was the 1st frame again -> wait until the
        # playhead is there, and re-export once when the file is byte-identical to the previous still
        tl.SetCurrentTimecode(tc)
        for _ in range(20):
            if tl.GetCurrentTimecode() == tc:
                break
            time.sleep(0.05)
        time.sleep(0.15)
        return project.ExportCurrentFrameAsStill(str(path))
    for t in times:
        if t.count(":") == 3:
            frame = tc_to_frames(t, fps)
        else:
            frame = start + round(parse_clock(t) * round(fps))
        tc = frames_to_tc(frame, fps)
        path = out_dir / f"frame_{tc.replace(':', '-')}.png"
        ok = grab(tc, path)
        if not ok and page != "color":
            resolve.OpenPage("color")
            ok = grab(tc, path)
        if ok and path.exists() and last is not None and path.read_bytes() == last:
            time.sleep(0.5)
            ok = grab(tc, path)
        last = path.read_bytes() if path.exists() else None
        results.append({"at": t, "tc": tc, "path": str(path), "ok": bool(ok) and path.exists()})
    if page:
        try:
            resolve.OpenPage(page)
        except Exception:  # noqa: BLE001
            pass
    return results
