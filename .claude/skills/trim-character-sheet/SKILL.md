---
name: trim-character-sheet
description: Find AI-generated clips on timeline "Edit" track V1 whose first frames show a character reference sheet (grid of labelled views of an animal), put a red marker over each range and report. Use when the user runs /trim-character-sheet or asks to find/remove character sheets at the start of shots.
---

# Trim character sheet

## Scan + mark (default, ~10s)

    .venv/Scripts/python .claude/skills/trim-character-sheet/scripts/trim_character_sheet.py

Run it once and reply from its two output lines. Do NOT export or save frames/images (not to `.work`, not
to temp), do NOT open images, do NOT re-run to "double check". The user reviews the markers in Resolve.

What the script does (all in memory, 8 clips in parallel):
- For each V1 clip it decodes the first 24 frames from the clip's in-point with ffmpeg (480x270, gray).
- Sheet = a sheet frame followed by a hard cut to footage: the biggest frame-to-frame jump within the first
  8 frames is > 35 and >= 3x the clip's median jump. Sheet length = frames up to that cut.
- Fallback when there is no cut: leading frames that show a panel grid (long straight borders in both
  directions), max 8 frames.
- Deletes markers of a previous scan (name starts `CS:`), then adds one Red marker per clip at its start,
  duration = sheet frames, name `CS: <clip>`, customData `cs|<itemId>|<frames>`.

Output: `N clips scanned | M with character sheet`, then `shot@mm:ss(Nf)` for each (mm:ss = timeline time,
Nf = sheet frames; 1f is the normal case). Tell the user (Vietnamese): how many found, that red markers are on
timeline "Edit" for review, and that nothing was cut yet.

Known limits: a clip whose sheet frames were already trimmed off (in-point past them) has nothing to flag;
a sheet longer than 8 frames or without a cut and without a clear grid would be missed. If the user
points at a missed clip, look at just that clip (one small image), then adjust thresholds.

## Trim (`--execute`, only after the user approves the markers)

    .venv/Scripts/python .claude/skills/trim-character-sheet/scripts/trim_character_sheet.py --execute

Cuts EVERY marker on the timeline that sits on a V1 clip, whatever its name or color: the red `CS:` ones
from the scan and any marker the user added by hand while reviewing (Resolve default: blue "Marker NN",
1 frame). Cut = from the clip's head to the end of the marker (marker at clip start, 1 frame -> 1 frame;
drag the marker longer to cut more). Several markers on one clip -> the furthest end wins. Old green
`CS-CUT:` markers are ignored. Do not rescan first: a scan deletes the user's markers.

Makes a backup timeline `Edit_bak_cs_<stamp>`, then per clip, last to first: delete V1 item + linked A1,
re-place it from source frame +n at record +n, fill the n-frame head gap with a throw-away V1 item and
ripple-delete it. Resolve has no trim/blade API, this is the workaround. The ripple closes the gap on ALL
tracks, so picture, A1, voice A4 and music stay aligned, but every ripple also removes those n frames from
A4/music and splits the A4 voice item at that point. Voice no longer matches timestamped.txt after this:
do any vo-sync before trimming, not after. Safe only because these clips are plain (1 node, no
fades/Fusion/speed); a clip with a grade or Fusion comp would lose it when re-placed.

Afterwards ALL markers on the timeline are deleted (user's request) and no green markers are made. Output is
one line: clips trimmed, frames cut, backup name. Reply in Vietnamese with that.

## API gotcha

`Timeline.AddMarker(frameId, color, name, note, duration, customData)`: `color` is a string ("Red",
"Green"...), NOT `resolve.MARKER_*` (those are Slate colors and make AddMarker return False).
`frameId` is relative to the timeline start (`item.GetStart() - timeline.GetStartFrame()`).
