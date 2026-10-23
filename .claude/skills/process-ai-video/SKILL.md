---
name: process-ai-video
description: Make AI clips in D:\AI_video look like real camera footage (blacks, saturation, casts, detail, 1920x1080, grain) and cut character-sheet head frames, overwriting in place. Use for /process-ai-video, "AI clip trông giả / less fake", or removing character sheets.
---

# Process AI video

Overwrites the originals in `D:\AI_video` (user's choice: no copies kept).

    .venv/Scripts/python .claude/skills/process-ai-video/scripts/process_ai_video.py                # all new clips
    .venv/Scripts/python .claude/skills/process-ai-video/scripts/process_ai_video.py "D:\AI_video\sloth"   # one folder / files

~750 clips take ~1 h: `run_in_background`. Afterwards `scan-source` (`scan_source.py ai`): graded files have new
content hashes, so the AI index shows them as removed + new (expected; say so).

**Never twice:** processed clips carry the metadata marker `comment=ai_look_v3cs` and are skipped.
`.work/process_ai_video/done_index.json` (path -> size + mtime) skips unchanged clips without an ffprobe; new, moved or
replaced files are checked by marker. `ai_look_v3` (graded before the sheet cut) -> only step 0, re-encoded only if a
sheet is found. `ai_look_v2` -> only the v3 colour stage (step 6) + step 0, no second base grade / softening / grain.

## Per clip (measured, not fixed values)
Targets from the user's real stock footage (`Z:\Unseen\Amazona\video`): luma p1 ~0.08, p99 ~0.85.
0. Character-sheet cut (replaces the old Resolve skill trim-character-sheet; clips enter Resolve clean): first 24
   frames decoded in memory (gray 480x270, native fps). Sheet = biggest frame-to-frame jump in the first 8 frames > 35
   and >= 3x the clip's median jump; fallback: leading frames showing a panel grid. Those frames are cut (`trim`),
   audio trimmed by the same time and re-encoded AAC 192k (else audio copied). Expected frames = original - cut; 1
   frame is normal. Thresholds `CS_*`, `CUT_*`, `EDGE`; a sheet > 8 frames, or with neither cut nor grid, is missed.
1. White balance from near-grey midtones: teal/blue AI "cinematic" casts removed hard, warm casts (sun, golden hour)
   touched lightly.
2. Levels: crushed blacks lifted to ~0.075; highlights raised toward 0.86, max +20 % (dark scenes stay dark).
3. Saturation: mild global trim + -8 % on reds/yellows and cyans/blues (AI pushes these to the limit).
4. Micro-detail softened (negative unsharp): no crunchy, plastic edges on fur and leaves.
5. Lanczos fill to 1920x1080 (AI clips are 1216x672 / 1280x720), then fine temporal luma grain.
6. Colour v3 (user found v2 too vivid): measured after steps 1-3, saturation only pulled down, ~20 % under the stock
   footage. Global s90 (lit pixels) -> 0.55; per hue band (r y g c b m) p75 above target -> huesaturation pull, max
   -35 %. ffmpeg `eq` desaturates less than its factor: measured once, factor corrected (`s90_out` in the log).
   Targets `S90`, `HUE_T`.
Render -> temp file next to the original -> frame count must match -> replaces the original. Audio copied.

## Reply (Vietnamese)
Counts (done / skipped / failed), FAILED lines, CHARACTER SHEET CUT list (clip + frames cut), STRONG WB SHIFT list
(big colour correction: ask the user to look at a few). Per-clip values: `.work/process_ai_video/log.jsonl`.

## Test before changing parameters
`--compare <outdir> <files>` renders original | graded side by side without touching originals; out dir outside
D:\AI_video, delete it after review.
