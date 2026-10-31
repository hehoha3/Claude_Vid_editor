---
name: hide-logo
description: Remove broadcast / AI-generator logos (BBC, Veo, Gemini...) from shots - MiniMax-Remover inpainted copies into D:\AI_video\_nologo, relinked in Resolve; find logos in a folder; overwrite originals when a video is done. Use for /hide-logo, "shot ở 21:38 có logo góc trên trái", "remove the logo on shot_NNN", Object Removal of a logo.
---

# Hide logo

Run each command once, reply only from its stdout (one line per clip). Never open images or crops: the script
checks itself (`RESIDUE` = logo edges left -> redo that clip with `--box`). The user checks in Resolve.
Script: `.venv/Scripts/python .claude/skills/hide-logo/scripts/hide_logo.py`. Day project `vid_DDMMYY`: prefix every
Resolve command with `DVR_CHANNEL=Chann_N` (two "Edit" timelines; it stops without). History, calibration, logo
kinds, engine details: `references/notes.md` (read only when a case below does not cover it).

**Copies:** logo-free copies go to `D:\AI_video\_nologo\` (Z: sources -> `_nologo\z\`, used by plan.py instead of
the Z: file), recorded in `.work/hide_logo/nologo.json`; `NOLOGO_DIR` overrides (africa: `D:\AI_video\_africa\_nologo`).
A rerun on a relinked clip always reads the original. Originals stay untouched until Done.

## Logo at timeline positions ("shot ở 21:38 và 05:12 có logo góc trên trái") - the usual case

    hide_logo.py --at 21:38 tl 05:12 tr 07:40

Corner optional after each time. Per time: the V1 clip there or a neighbour within 1 s; known logos
(`logos/*.npy`, BBC) win, the box is widened over trailing text (BBC EARTH / Earth); else static edges; else a
logo only at the start / popping in late. A file already done in the run is skipped ("same file"). The model fills
only the logo's glyphs, not the box. Reply (Vietnamese): per time the clip, `RESIDUE`, `FAILED`; no stills, no
questions, no overwrite question.

## One shot: `hide_logo.py "<shot_NNN | path>" [tl|tr|bl|br] [--end] [--box x0,y0,x1,y1 ...]`
No scan, ~30 s. `--end` forces a late-logo search. `--box` at 640x360, tight around the glyphs, one box per logo
(Gemini star: `--box 566,286,594,314`; BBC miss: `--box 0,3,50,21`). Old smeared delogo:
`MM_MASK=box ... --box 0,3,74,22`.

## Folder scan: `hide_logo.py "<folder>"` (no argument -> ask for a folder or a shot)
Marks V1 clips of "Edit" (Purple = logo >= 0.45, Yellow = suspect 0.33-0.45), writes `.work/hide_logo/scan.json`
and `check_list.txt` (LOGO lines active, SUSPECT `#? `; works without Resolve, e.g. `D:\AI_video\_check`,
`/doc-edit logo`). Reply: count, LOGO + SUSPECT lists as printed; the user fixes markers, then `--execute`.
- `--execute`: every marker on a V1 clip -> delogo, relink, markers deleted.
- `--list [file]` (`/doc-edit delogo`): delogo every active line of the reviewed list, no relink (background).
- `--timeline [name]`: read-only report of V1 shots with the logo.

## Overwrite at Done (user rule 2026-10-11)
After `/doc-edit done` (never ask whether exported): `--pending`; copies listed -> ask "Bạn có muốn ghi đè các file
trong folder _nologo lên các file gốc của chúng không?" with the list. Only on "có"/"yes": `--overwrite-all`
(closes + reopens the project, relinks, re-sets black fades; Z: originals never overwritten). Still locked ->
Resolve was quit: user reopens the project, then `--relink`. Reply: overwritten, relinked, kept (Z:), problems.
Undo one clip: Replace Clip back to the original.

Knobs (env): `MM_STEPS` (2), `MM_CROP` (336x192), `MM_MASK=box`. No GPU: `--fill clone` / `--fill interp`.
