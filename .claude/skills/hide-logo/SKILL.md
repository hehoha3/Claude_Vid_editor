---
name: hide-logo
description: Remove broadcast / AI-generator logos (BBC, Veo, Gemini...) from shots - MiniMax-Remover inpainted copies into D:\AI_video\_nologo, relinked in Resolve; find logos in a folder; overwrite originals when a video is done. Use for /hide-logo, "shot ở 21:38 có logo góc trên trái", "remove the logo on shot_NNN", Object Removal of a logo.
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

Every logo-free copy (D: and read-only Z: sources) goes to `D:\AI_video\_nologo\` (flat; scan-source and
process-ai-video skip it) and is recorded in `.work/hide_logo/nologo.json` (copy -> original). Originals stay
untouched until the project is Done (see "Overwrite at Done"). Re-running on a relinked clip always reads the original.

## Execute: `/hide-logo --execute`

    .venv/Scripts/python .claude/skills/hide-logo/scripts/hide_logo.py --execute

Any marker on a V1 clip = delogo that clip's file into `AI_video\_nologo\`, relink via ReplaceClip, delete
markers. Reply: clips done + the REVIEW FIRST list (busy backgrounds where the patch may show).
Undo one clip: Replace Clip back to the original.

## One shot: `/hide-logo <shot_NNN | video.mp4 path> <corner>`

    .venv/Scripts/python .claude/skills/hide-logo/scripts/hide_logo.py "<shot_NNN or path>" tr

Corner from the user's words: top-left `tl`, top-right `tr`, bottom-left `bl`, bottom-right `br` (none given
-> omit it, the script picks the corner with most static edges). No scan, no markers, ~30 s. Finds the static
logo in that corner, delogoes into `AI_video\_nologo\`, relinks the V1 clip that uses it (a path not on the
timeline -> file only). The user names the video + the logo's place, never the time (user 2026-10-15): no logo
through the whole clip -> it finds one shown only at the start or popping in late (verified as static edges in
that span; logo-free water/animals give "no logo found") and fills only that span (~15 s). `--end` forces the
late search. Reply with the one output line; "Object Removal" requests for a logo -> use this.

Auto-detect misses semi-transparent logos over bright moving water (finds a letterbox edge instead): look at the
corner crop of the original, then give the boxes yourself at 640x360, one small box per logo (never one big box over
two logos):
`hide_logo.py "<path>" --box 583,301,608,325 616,344,639,357` (Gemini star, Veo text).

**"logo Gemini" (user 2026-10-16, verified on 4 clips 1280x720 8 s)**: a semi-transparent white/grey 4-point star
(diamond, concave sides), bottom-right, NOT in the corner itself: centre ~(580,300) at 640x360 (~90.6% x, 83.3% y),
~22x22 px, the whole clip from 0 s. Auto-detect misses it or picks a wrong static edge (x~450, or mid-frame), so
skip auto: `hide_logo.py "<path>" --box 566,286,594,314`. Other resolution -> scale the box by the same ratios;
unsure -> one corner crop (`crop=160:90:480:270` of the 640x360 frame, x4) to confirm, then check the same crop of
the `_nologo` copy once.

Every fill (auto, `--box`, `--at`, `--execute`) = MiniMax-Remover (user 2026-10-15: clone patch blurred / glowed;
Netflix VOID tested: 64 min/clip on 8 GB, dropped). `scripts/minimax_worker.py` runs in its own venv
`D:\tools\minimax_remover\venv`: native-res crop around the logo (min 336x192, +48 px context), 3 steps (A/B vs
ground truth: as good as 6), fewest windows of <= 65 frames crossfaded, mask latent encoded once, model pixels
only on the logo (feathered), rest of the frame untouched. ~30 s per 10 s clip on the RTX 5060 with Resolve open
(stdout has the per-phase timing); clips run one at a time (GPU). Weights (2.6 GB) + repo in that folder.
Knobs (env): `MM_STEPS` (2 also passed the A/B), `MM_CROP` (256x160 = 30% faster, less faithful).
Fallback without GPU: `--fill clone` (clone texture + haze, `--haze N`) or `--fill interp` (ffmpeg delogo + haze).

## Logo reported at timeline positions ("shot ở 21:38 và 05:12 có logo góc trên trái")

The user works in Resolve and checks the result there: run it, reply with the output lines, no stills, no
questions, no overwrite question.

    .venv/Scripts/python .claude/skills/hide-logo/scripts/hide_logo.py --at 21:38 tl 05:12 tr 07:40

Corner optional after each time. For each time it scores the V1 clip there and its neighbours within 1 s (a
reported time often lands just before the cut), delogoes the one with the logo into `AI_video\_nologo\` and
relinks it in the open project; a failed shot does not stop the others. No logo through the whole clip ->
it tries a logo shown only at the start (removed 0-Ns) and one popping in late (removed from Ns), best share wins.
No crops or stills afterwards (user rule 2026-10-13): the user checks in Resolve and reports a wrong pick. Reply in Vietnamese: per time the clip
(time range, file), REVIEW flag, FAILED lines.

## Overwrite at Done (user rule 2026-10-11)

After `/doc-edit done` (it runs at once; never ask whether the video is exported, user 2026-10-13): run
`--pending`. Copies listed -> ask "Bạn có muốn ghi đè các file trong folder _nologo lên các file gốc của chúng không?" (with the list).
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

MiniMax windows hit an attention cliff above ~4300 tokens (17 latent frames x 21x12 patches): bigger crops get
shorter windows automatically. One logo position per folder. Fusion Object Removal is not
usable: Scene Analysis cannot be triggered from the API (Resolve 21.1).
