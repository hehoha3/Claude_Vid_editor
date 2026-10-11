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

Every logo-free copy (D: and read-only Z: sources) goes to `D:\AI_video\_check\_nologo\` (flat; scan-source and
process-ai-video skip it) and is recorded in `.work/hide_logo/nologo.json` (copy -> original). Originals stay
untouched until the project is Done (see "Overwrite at Done"). Re-running on a relinked clip always reads the original.

## Execute: `/hide-logo --execute`

    .venv/Scripts/python .claude/skills/hide-logo/scripts/hide_logo.py --execute

Any marker on a V1 clip = delogo that clip's file into `_check\_nologo\`, relink via ReplaceClip, delete
markers. Reply: clips done + the REVIEW FIRST list (busy backgrounds where the patch may show).
Undo one clip: Replace Clip back to the original.

## One shot: `/hide-logo <shot_NNN | video.mp4 path> <corner>`

    .venv/Scripts/python .claude/skills/hide-logo/scripts/hide_logo.py "<shot_NNN or path>" tr

Corner from the user's words: top-left `tl`, top-right `tr`, bottom-left `bl`, bottom-right `br` (none given
-> omit it, the script picks the corner with most static edges). No scan, no markers, ~20s. Finds the static
logo in that corner, delogoes into `_check\_nologo\`, relinks the V1 clip that uses it (a path not on the
timeline -> file only). Logo only near the end / appears partway ("gần cuối", "giữa video") -> add `--end`:
finds the frame where the logo pops in and delogoes only from there. Reply with the one output line; if it says
REVIEW, ask the user to check that corner. "Object Removal" requests for a logo -> use this.

## Logo reported at timeline positions ("shot ở 21:38 và 05:12 có logo góc trên trái")

The user works in Resolve and checks the result there: run it, reply with the output lines, no stills, no
questions, no overwrite question.

    .venv/Scripts/python .claude/skills/hide-logo/scripts/hide_logo.py --at 21:38 tl 05:12 tr 07:40

Corner optional after each time. For each time it scores the V1 clip there and its neighbours within 1 s (a
reported time often lands just before the cut), delogoes the one with the logo into `_check\_nologo\` and
relinks it in the open project; a failed shot does not stop the others. No logo through the whole clip ->
it tries a logo shown only at the start (removed 0-Ns) and one popping in late (removed from Ns), best share wins;
shares are close between neighbours, so check the chosen clip's corner yourself (ffmpeg crop of the original at
its `src_in`, not a timeline still) before replying. Reply in Vietnamese: per time the clip
(time range, file), REVIEW flag, FAILED lines.

## Overwrite at Done (user rule 2026-10-11)

When the user reports the video finished (or `/doc-edit done`): run `--pending`. Copies listed -> first ask
"Bạn đã xuất (render) video chưa?". Not yet -> stop, ask again after the export. Exported -> ask
"Bạn có muốn ghi đè các file trong folder _nologo lên các file gốc của chúng không?" (with the list).
Only on "có"/"yes":

    .venv/Scripts/python .claude/skills/hide-logo/scripts/hide_logo.py --pending
    .venv/Scripts/python .claude/skills/hide-logo/scripts/hide_logo.py --overwrite-all

`--overwrite-all` drives Resolve itself: saves + closes the project (Resolve holds the files open), each copy
replaces its original, reopens the project on the same timeline, relinks to the original paths, and moves each
clip's tags / YOLO cache / ledger id to the new content hash (no re-tag, no rescan). A file still locked after
the close -> it quits Resolve, finishes, and says so: ask the user to reopen the project, then run `--relink`.
Z: originals are never overwritten (copy stays linked). Reply in Vietnamese: originals overwritten, relinked,
kept (Z:), problems.
`--relink`: open project -> items on an original point at its pending copy, items on an overwritten copy at the
original again.

## Limits

delogo is soft on foliage (upgrade: ProPainter). One logo position per folder. Fusion Object Removal is not
usable: Scene Analysis cannot be triggered from the API (Resolve 21.1).
