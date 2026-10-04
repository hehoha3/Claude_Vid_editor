#!/usr/bin/env python3
"""Scan V1 of timeline "Edit" for character-sheet frames at the start of each clip and place a red
timeline marker over each range. Frames are decoded in memory (ffmpeg pipe); nothing is written to disk."""
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from dvr_cowork.resolve_conn import connect  # noqa: E402

TIMELINE = "Edit"
PREFIX = "CS:"
PREFIXES = ("CS:", "CS-CUT:")   # scan clears both so old review markers never pile up
W, H = 480, 270
SCAN_FRAMES = 24          # first 1s of the clip at 24 fps
MAX_SHEET_FRAMES = 8      # a sheet is never longer than this; anything later is not a head sheet
EDGE = 30                 # gray-level step that counts as an edge
CUT_MIN, CUT_RATIO = 35.0, 3.0


def border_lines(edges: np.ndarray, min_run=0.25) -> int:
    """Number of distinct rows of `edges` (bool) that hold a straight run >= min_run of the width."""
    h, w = edges.shape
    need = int(min_run * w)
    count, last = 0, -10
    for y in range(int(h * 0.03), int(h * 0.97)):
        row = edges[y]
        padded = np.concatenate(([0], row.astype(np.int8), [0]))
        d = np.diff(padded)
        runs = np.flatnonzero(d == -1) - np.flatnonzero(d == 1)
        if runs.size and runs.max() >= need:
            if y - last > 4:
                count += 1
            last = y
    return count


def has_panels(f: np.ndarray) -> bool:
    """Grid of panels: long straight borders in both directions."""
    return border_lines(np.abs(np.diff(f, axis=0)) > EDGE) + border_lines((np.abs(np.diff(f, axis=1)) > EDGE).T) >= 2


def sheet_frames(path: str, start_s: float) -> int:
    """Count of leading frames that are a character sheet (0 if none)."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{start_s:.3f}", "-i", path, "-frames:v", str(SCAN_FRAMES),
         "-vf", f"fps=24,scale={W}:{H}", "-pix_fmt", "gray", "-f", "rawvideo", "-"],
        capture_output=True).stdout
    fr = np.frombuffer(raw, np.uint8)[: (len(raw) // (W * H)) * W * H].reshape(-1, H, W).astype(np.int16)
    if len(fr) < 3:
        return 0
    d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))
    k = int(np.argmax(d[:MAX_SHEET_FRAMES]))
    # Sheet -> footage is a hard cut far above the clip's normal frame-to-frame change.
    if d[k] > CUT_MIN and d[k] / max(float(np.median(d)), 3.0) >= CUT_RATIO:
        return k + 1
    n = 0
    for f in fr[:MAX_SHEET_FRAMES]:
        if not has_panels(f):
            break
        n += 1
    return n


def tc(frame: int, fps: int) -> str:
    return f"{frame // (3600 * fps):02d}:{frame // (60 * fps) % 60:02d}:{frame // fps % 60:02d}:{frame % fps:02d}"


def execute(project, tl):
    """Cut the marked head frames off every flagged clip (V1 + linked A1) and ripple the gap on ALL tracks.
    Resolve has no trim API, so per clip: delete it, re-place it from source frame +n at record +n, fill the
    n-frame head gap with a throw-away V1 item and ripple-delete that item. Works last-to-first so earlier
    positions stay valid."""
    import datetime
    base = tl.GetStartFrame()
    items = tl.GetItemListInTrack("video", 1)
    cuts = {}   # clip start -> frames to cut
    for f, m in tl.GetMarkers().items():
        if m["name"].startswith("CS-CUT:"):   # review leftovers of older runs, not cut requests
            continue
        it = next((i for i in items if int(i.GetStart()) - base <= f < int(i.GetEnd()) - base), None)
        if it is None:
            continue
        s = int(it.GetStart()) - base
        cuts[s] = max(cuts.get(s, 0), f + int(m["duration"]) - s)   # cut from clip head to end of marker
    marks = sorted(((s, {"name": f"clip@{s}", "duration": n}) for s, n in cuts.items()), reverse=True)
    if not marks:
        sys.exit("No markers on V1 clips. Run the scan first or add markers.")
    backup = f"{TIMELINE}_bak_cs_{datetime.datetime.now():%Y%m%d_%H%M%S}"
    if not tl.DuplicateTimeline(backup):
        sys.exit("Backup failed, nothing changed.")
    project.SetCurrentTimeline(tl)
    mp = project.GetMediaPool()
    v1 = {int(i.GetStart()) - base: i for i in tl.GetItemListInTrack("video", 1)}
    length0 = tl.GetEndFrame() - base
    done = removed = 0
    for f, m in marks:
        it, n = v1.get(f), int(m["duration"])
        if it is None or not 0 < n < int(it.GetDuration()):
            sys.exit(f"Stopped at {m['name']}: item not found/invalid. {done} clips done; backup '{backup}'.")
        mpi, src0, dur = it.GetMediaPoolItem(), int(it.GetSourceStartFrame()), int(it.GetDuration())
        old = [it] + [x for x in it.GetLinkedItems() if x.GetUniqueId() != it.GetUniqueId()]
        ok = tl.DeleteClips(old, False)
        placed = mp.AppendToTimeline([{"mediaPoolItem": mpi, "startFrame": src0 + n, "endFrame": src0 + dur,
                                       "trackIndex": 1, "recordFrame": base + f + n}]) if ok else None
        gap = mp.AppendToTimeline([{"mediaPoolItem": mpi, "startFrame": src0, "endFrame": src0 + n, "mediaType": 1,
                                    "trackIndex": 1, "recordFrame": base + f}]) if placed else None
        if not (gap and tl.DeleteClips(gap, True)):
            sys.exit(f"Stopped at {m['name']} ({done} clips done). Restore from '{backup}' if needed.")
        done, removed = done + 1, removed + n
    for f in list(tl.GetMarkers()):   # user asked for a clean timeline after trimming
        tl.DeleteMarkerAtFrame(f)
    shrink = length0 - (tl.GetEndFrame() - base)
    print(f"trimmed {done} clips, {removed} frames cut | timeline shorter by {shrink} frames | "
          f"all markers deleted | backup '{backup}'")


def main():
    project = connect().GetProjectManager().GetCurrentProject()
    tl = next((t for t in (project.GetTimelineByIndex(i) for i in range(1, project.GetTimelineCount() + 1))
               if t.GetName() == TIMELINE), None)
    if not tl:
        sys.exit(f"Timeline '{TIMELINE}' not found")
    project.SetCurrentTimeline(tl)
    if "--execute" in sys.argv:
        return execute(project, tl)
    fps = round(float(tl.GetSetting("timelineFrameRate")))
    base = tl.GetStartFrame()

    for frame, m in tl.GetMarkers().items():   # drop markers from a previous scan
        if m["name"].startswith(PREFIXES):
            tl.DeleteMarkerAtFrame(frame)

    jobs = []
    for it in tl.GetItemListInTrack("video", 1):
        mpi = it.GetMediaPoolItem()
        path = mpi.GetClipProperty("File Path") if mpi else ""
        if path:
            jobs.append((it, path))

    with ThreadPoolExecutor(8) as pool:
        counts = list(pool.map(lambda j: sheet_frames(j[1], j[0].GetSourceStartTime()), jobs))

    found = []
    for (it, _), n in zip(jobs, counts):
        n = min(n, int(it.GetDuration()))
        if n == 0:
            continue
        rel = int(it.GetStart()) - base
        tl.AddMarker(rel, "Red", f"{PREFIX} {it.GetName()}",
                     f"Character sheet: {n} frames ({n / fps:.2f}s) from clip start", n,
                     f"cs|{it.GetUniqueId()}|{n}")
        found.append((it.GetName(), rel, n))

    print(f"{len(jobs)} clips scanned on V1 | {len(found)} with character sheet | red markers placed on '{TIMELINE}'")
    print(", ".join(f"{n[5:-4]}@{tc(r + base, fps)[3:8]}({c}f)" for n, r, c in found))


if __name__ == "__main__":
    main()
