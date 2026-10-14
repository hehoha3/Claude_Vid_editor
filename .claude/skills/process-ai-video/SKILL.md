---
name: process-ai-video
description: Make AI clips in D:\AI_video look like real camera footage (blacks, saturation, casts, detail, 1920x1080, grain) and cut character-sheet head frames, overwriting in place. Use for /process-ai-video, "AI clip trông giả / less fake", or removing character sheets.
---

# Process AI video

Overwrites the originals in `D:\AI_video` (the user's explicit choice: no copies are kept). Clips already
processed carry the metadata marker `comment=ai_look_v3cs` and are skipped, so re-running only handles new clips
and never grades a clip twice. Clips found done/skipped are recorded in `.work/process_ai_video/done_index.json`
(path -> size + mtime): on the next run unchanged clips are skipped without even an ffprobe; new, moved or
replaced files (other path/size/mtime) are checked by marker as before. Clips marked `ai_look_v3` (graded before the sheet cut existed) only get the
character-sheet cut (step 0), re-encoded only if a sheet is found. Clips marked `ai_look_v2` (earlier version)
only get the v3 colour stage (step 6) + step 0, not a second base grade / softening / grain.

    .venv/Scripts/python .claude/skills/process-ai-video/scripts/process_ai_video.py                # all new clips
    .venv/Scripts/python .claude/skills/process-ai-video/scripts/process_ai_video.py "D:\AI_video\sloth"   # one folder / files

~750 clips take ~1 h: run with `run_in_background`. Afterwards run skill `scan-source` (`scan_source.py ai`):
the graded files have new content hashes, so the AI index shows them as removed + new - expected, say so.

## What it does per clip (measured, not fixed values)
Targets come from the user's real stock footage (`Z:\Unseen\Amazona\video`): luma p1 ~0.08, p99 ~0.85.
0. Character sheet cut (replaces the old Resolve skill trim-character-sheet; clips enter Resolve clean): the first
   24 frames are decoded in memory (gray 480x270, native fps). Sheet = biggest frame-to-frame jump within the first
   8 frames > 35 and >= 3x the clip's median jump (sheet then hard cut to footage); fallback: leading frames showing
   a panel grid. Those frames are cut (`trim`), audio trimmed by the same time and re-encoded AAC 192k (otherwise
   audio is copied). Expected frame count = original - cut. 1 frame is the normal case. Thresholds `CS_*`,
   `CUT_*`, `EDGE` in the script; a sheet longer than 8 frames or without cut and grid is missed.
1. White balance from near-grey midtone pixels: teal/blue casts (AI "cinematic" look) removed hard,
   warm casts (sun, golden hour) only touched lightly.
2. Levels: crushed blacks lifted to ~0.075; highlights raised toward 0.86 but max +20 % (dark scenes stay dark).
3. Saturation: mild global trim + -8 % on reds/yellows and cyans/blues (AI pushes these to the limit).
4. Micro-detail softened (negative unsharp): removes the crunchy, plastic edges on fur and leaves.
5. Lanczos fill to 1920x1080 (AI clips are 1216x672 / 1280x720), then fine temporal luma grain.
6. Colour (v3, user found v2 still too vivid): measured after steps 1-3, saturation pulled down only, ~20 % under
   the user's stock footage. Global: s90 (lit pixels) -> 0.55; per hue band (r y g c b m) p75 above target ->
   huesaturation pull, max -35 %. ffmpeg `eq` desaturates less than its factor, so the result is measured once
   and the factor corrected (`s90_out` in the log). Targets: `S90`, `HUE_T` in the script.
Render -> temp file next to the original -> frame count must match -> replaces the original. Audio copied.

## Reply (Vietnamese)
Counts (done / skipped / failed), the FAILED lines, the CHARACTER SHEET CUT list (clip + frames cut), and the
STRONG WB SHIFT list: those clips had a big
colour correction - ask the user to look at a few of them. Log with every clip's measured values and
parameters: `.work/process_ai_video/log.jsonl`.

## Test before changing parameters
`--compare <outdir> <files>` renders side-by-side (original | graded) without touching the originals; put
the out dir outside D:\AI_video and delete it after review.
