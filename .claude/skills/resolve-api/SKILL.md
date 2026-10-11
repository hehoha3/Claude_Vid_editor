---
name: resolve-api
description: Facts and gotchas of the DaVinci Resolve Python scripting API for writing ad-hoc automation (timeline items, media pool, tracks, markers, grades, render) from this workspace. Use whenever you are about to write or debug Python that talks to Resolve, or decide whether something is possible by script.
---

# Resolve scripting API - working notes

## Connecting from this workspace
```python
import sys; sys.path.insert(0, ".")
from dvr_cowork.config import load_config
from dvr_cowork.resolve_conn import connect
resolve = connect(load_config())
project = resolve.GetProjectManager().GetCurrentProject()
```
Run with `.venv/Scripts/python.exe your_script.py`. Requires Resolve running with
External scripting = Local. Put throw-away scripts in `.work/scripts/`.
The official reference ships with Resolve:
`%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\README.txt`
- read the relevant part of it when unsure of a method; method sets change between versions.

## Object model
Resolve -> ProjectManager -> Project -> MediaPool (Folders, MediaPoolItems) / Timelines ->
TimelineItems (per track). Gallery for stills. Fusion comps per item.

## Facts that bite
- Track indices are 1-based; `GetItemListInTrack("audio", 4)` is A4. Timeline frames are absolute
  (`GetStartFrame()` is often 86400 = 01:00:00:00 at 24 fps); markers use frames relative to start.
- There is **no blade/split method**. Equivalent: `MediaPool.AppendToTimeline([{ "mediaPoolItem",
  "startFrame", "endFrame", "mediaType" (1 video, 2 audio), "trackIndex", "recordFrame" }])` with
  different source ranges of the same clip. endFrame is exclusive (verified 21.1). Source fps !=
  timeline fps: source length = ceil(timeline_frames * src_fps / tl_fps); verify `item.GetStart/GetEnd`.
- API calls take positional args only: `tl.AddMarker(frame, "Red", name, note, dur, customData)`;
  keyword args silently fail (return False / None).
- `ImportMedia` imports into the *current* media-pool folder: `SetCurrentFolder(bin)` first.
- `AppendToTimeline` targets the *current* timeline: `project.SetCurrentTimeline(tl)` first.
- `DeleteClips(items, ripple)` removes timeline items; there is no "move item" - delete and append.
- Many setters return False instead of raising; always check return values.
- `GetSetting("timelineFrameRate")` may be a string ("23.976").
- Clip colors are a fixed set (Orange, Apricot, Yellow, Lime, Olive, Green, Teal, Navy, Blue, Purple,
  Violet, Pink, Tan, Beige, Brown, Chocolate). Marker colors differ (Blue, Cyan, Green, Yellow, Red,
  Pink, Purple, Fuchsia, Rose, Lavender, Sky, Mint, Lemon, Sand, Cocoa, Cream).
- Grades by script: `TimelineItem.SetLUT(nodeIndex, path)`, `SetCDL({...})`, node graph access and
  `ApplyGradeFromDRX` exist in recent versions; complex grading is still faster by hand - script
  only repetitive application (same LUT/CDL to many clips).
- `Project.ExportCurrentFrameAsStill(path)` exports the graded frame at the playhead
  (`Timeline.SetCurrentTimecode(tc)` first; some versions need the Color page).
- Rendering: `project.SetRenderSettings({...})`, `AddRenderJob()`, `StartRendering()`,
  `IsRenderingInProgress()`.
- Undo: script changes are not always one clean undo step - duplicate the timeline first
  (`timeline.DuplicateTimeline(name)`) before bulk edits.
- Free vs Studio: some scripting features (and external scripting in some builds) are limited in
  the free version; `dvr doctor` tells you whether external connection works.

## Safety
Before any script that deletes, moves or regrades many items: dry-run (print what would change),
duplicate the timeline, then run. Report counts back to the user.
