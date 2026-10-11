---
name: hide-logo
description: Find video files with a broadcast logo (BBC, BBC EARTH...) in a folder, mark their clips on timeline "Edit" for review, then remove the logo with ffmpeg delogo and relink the clips. Use for /hide-logo or any request to find/remove channel logos in shots, including "remove the logo on shot_NNN" / Object Removal of a logo on one clip.
---

# Hide logo

Scan folder -> user reviews markers in Resolve -> `--execute`. Run each command once, reply only from its
stdout. Never open images, never ask the user to click in Resolve.

## Scan: `/hide-logo <folder>` (no argument given -> ask for a folder or a shot)

    .venv/Scripts/python .claude/skills/hide-logo/scripts/hide_logo.py "<folder>"

Marks V1 clips of "Edit": Purple = logo (score >= 0.45), Yellow = suspect (0.33-0.45). Saves
`.work/hide_logo/scan.json` for execute.
Reply in Vietnamese, plain text: count, the LOGO list and SUSPECT list exactly as printed; ask the user to add
markers on missed clips, delete wrong ones, then run `--execute`.

## Execute: `/hide-logo --execute`

    .venv/Scripts/python .claude/skills/hide-logo/scripts/hide_logo.py --execute

Any marker on a V1 clip = delogo that clip's file into `<folder>/_nologo/` (clips on read-only Z: ->
`D:\AI_video\_check\_z_nologo\`; originals untouched), relink via
ReplaceClip, delete markers. Reply: clips done + the REVIEW FIRST list (busy backgrounds where the patch may
show). Undo one clip: Replace Clip back to the original.

## One shot: `/hide-logo <shot_NNN | video.mp4 path> <corner>`

    .venv/Scripts/python .claude/skills/hide-logo/scripts/hide_logo.py "<shot_NNN or path>" tr

Corner from the user's words: top-left `tl`, top-right `tr`, bottom-left `bl`, bottom-right `br` (none given
-> omit it, the script picks the corner with most static edges). No scan, no markers, ~20s. Finds the
static logo in that corner, delogo into `_nologo/` next to the file,
Logo only near the end / appears partway ("gần cuối", "giữa video") -> add `--end`: finds the frame where the
logo pops in and delogoes only from there. Always reads the original file even if the clip is already relinked. relinks the V1 clip that uses it (a path
not on the timeline -> file only). Reply with the one output line; if it says REVIEW, ask the user to
check that corner. "Object Removal" requests for a logo -> use this (Scene Analysis can't be scripted).

## Limits

delogo is soft on foliage (upgrade: ProPainter). One logo position per folder. Fusion Object Removal is not
usable: Scene Analysis cannot be triggered from the API (Resolve 21.1).
