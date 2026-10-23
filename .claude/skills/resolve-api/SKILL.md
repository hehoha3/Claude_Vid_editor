---
name: resolve-api
description: Gotchas of the Resolve Python scripting API (timeline items, media pool, tracks, markers, grades, render). Use before writing or debugging Python that talks to Resolve, or to decide if something is scriptable.
---

# Resolve scripting API - working notes

## Connect (from the workspace root)
```python
import sys; sys.path.insert(0, ".")
from dvr_cowork.config import load_config
from dvr_cowork.resolve_conn import connect
resolve = connect(load_config())
project = resolve.GetProjectManager().GetCurrentProject()
```
Run with `.venv/Scripts/python.exe your_script.py` (Resolve running, External scripting = Local). Throw-away scripts go
in `.work/scripts/`. Official reference (method sets change between versions; read the relevant part when unsure):
`%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\README.txt`

Object model: Resolve -> ProjectManager -> Project -> MediaPool (Folders, MediaPoolItems) / Timelines ->
TimelineItems (per track). Gallery for stills. Fusion comps per item.

## Facts that bite
- Tracks are 1-based: `GetItemListInTrack("audio", 4)` = A4. Timeline frames are absolute (`GetStartFrame()` often
  86400 = 01:00:00:00 at 24 fps); markers use frames relative to the start.
- **No blade / split method**: `MediaPool.AppendToTimeline([{ "mediaPoolItem", "startFrame", "endFrame", "mediaType"
  (1 video, 2 audio), "trackIndex", "recordFrame" }])` with different source ranges of the same clip. endFrame is
  exclusive (verified 21.1). Source fps != timeline fps: source length = ceil(timeline_frames * src_fps / tl_fps);
  verify `item.GetStart/GetEnd`.
- Positional args only: `tl.AddMarker(frame, "Red", name, note, dur, customData)`; keyword args silently fail.
- `ImportMedia` imports into the *current* media-pool folder: `SetCurrentFolder(bin)` first.
- `AppendToTimeline` targets the *current* timeline: `project.SetCurrentTimeline(tl)` first.
- `DeleteClips(items, ripple)` removes timeline items; no "move item": delete and append.
- Setters return False instead of raising: check every return value.
- `GetSetting("timelineFrameRate")` may be a string ("23.976").
- Clip colors (fixed): Orange, Apricot, Yellow, Lime, Olive, Green, Teal, Navy, Blue, Purple, Violet, Pink, Tan, Beige,
  Brown, Chocolate. Marker colors differ: Blue, Cyan, Green, Yellow, Red, Pink, Purple, Fuchsia, Rose, Lavender, Sky,
  Mint, Lemon, Sand, Cocoa, Cream.
- Grades: `TimelineItem.SetLUT(nodeIndex, path)`, `SetCDL({...})`, node graph access, `ApplyGradeFromDRX` exist in
  recent versions; script only repetitive application (same LUT/CDL on many clips), complex grading is faster by hand.
- `Project.ExportCurrentFrameAsStill(path)` = graded frame at the playhead (`Timeline.SetCurrentTimecode(tc)` first;
  some versions need the Color page; wait until `GetCurrentTimecode()` = tc, else the previous frame comes out).
- Render: `project.SetRenderSettings({...})`, `AddRenderJob()`, `StartRendering()`, `IsRenderingInProgress()`.
- Undo: script changes are not one clean undo step: `timeline.DuplicateTimeline(name)` before bulk edits.
- Every new / duplicated / imported timeline lives in bin "6. Timeline" (user 2026-10-23): `SetCurrentFolder` to it
  before `CreateEmptyTimeline` / `DuplicateTimeline` / `ImportTimelineFromFile` / `CreateTimelineFromClips`, check
  the item sits there, restore the folder. `ImportTimelineFromFile(importSourceClips=True)` dumps ALL source clips
  into the current folder: import with another bin current, then `MoveClips` only the timeline item.
- Free vs Studio: some scripting (and external scripting in some builds) is limited in Free; `dvr doctor` tells whether
  the external connection works.

## Safety
Before a script that deletes, moves or regrades many items: dry-run (print what would change), duplicate the timeline,
then run. Report counts back to the user.
