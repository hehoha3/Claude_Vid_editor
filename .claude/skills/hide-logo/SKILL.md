---
name: hide-logo
description: Remove broadcast / AI-generator logos (BBC, Veo, Gemini...) from shots - MiniMax-Remover inpainted copies into D:\AI_video\_nologo, relinked in Resolve; find logos in a folder; overwrite originals when a video is done. Use for /hide-logo, "shot ở 21:38 có logo góc trên trái", "remove the logo on shot_NNN", Object Removal of a logo.
---

# Hide logo

Flow: scan folder -> user reviews markers in Resolve -> `--execute`. Run each command once, reply only from its stdout.
Never open images, never ask the user to click in Resolve.

**Copies:** every logo-free copy (D: and read-only Z: sources) goes to `D:\AI_video\_nologo\` (flat; scan-source and
process-ai-video skip it), recorded in `.work/hide_logo/nologo.json` (copy -> original). Env `NOLOGO_DIR` = per-run
override (africa: `D:\AI_video\_africa\_nologo`). Copies of Z: originals go to `_nologo\z\` (user 2026-10-30) and stay: plan.py load_clips uses that copy instead of the Z: file (matched by the path after `\Unseen\`, UNC or Z:). Originals stay untouched until the project is Done ("Overwrite at
Done"). Re-running on a relinked clip always reads the original.

## Scan: `/hide-logo <folder>` (no argument -> ask for a folder or a shot)

    .venv/Scripts/python .claude/skills/hide-logo/scripts/hide_logo.py "<folder>"

Marks V1 clips of "Edit": Purple = logo (score >= 0.45), Yellow = suspect (0.33-0.45); saves `.work/hide_logo/scan.json`
for execute. Also writes `.work/hide_logo/check_list.txt` (full paths, LOGO lines active, SUSPECT lines `#? `; works
without Resolve / for clips on no timeline, e.g. `D:\AI_video\_check`; `/doc-edit logo`).
Reply (Vietnamese, plain): count, LOGO and SUSPECT lists exactly as printed; ask the user to add markers on missed
clips, delete wrong ones, then run `--execute`.

## List: `hide_logo.py --list [file]` (`/doc-edit delogo`)
Delogo every active line of the reviewed list (default `check_list.txt`) with its scan box -> `_nologo` copy, recorded
for `--overwrite-all`; no relink (not on a timeline). Files the user deleted meanwhile are skipped and named. Background
(~30 s per clip). Reply: done, REVIEW FIRST, FAILED, gone.

## Execute: `/hide-logo --execute`

    .venv/Scripts/python .claude/skills/hide-logo/scripts/hide_logo.py --execute

Any marker on a V1 clip = delogo its file into `AI_video\_nologo\`, relink via ReplaceClip, delete the markers.
Reply: clips done + REVIEW FIRST list (busy backgrounds where the patch may show). Undo one clip: Replace Clip back to
the original.

## One shot: `/hide-logo <shot_NNN | video.mp4 path> <corner>`

    .venv/Scripts/python .claude/skills/hide-logo/scripts/hide_logo.py "<shot_NNN or path>" tr

- Corner from the user's words: top-left `tl`, top-right `tr`, bottom-left `bl`, bottom-right `br`; none -> omit (the
  script picks the corner with most static edges). No scan, no markers, ~30 s.
- Finds the static logo in that corner, delogoes into `AI_video\_nologo\`, relinks the V1 clip using it (path not on the
  timeline -> file only).
- The user names video + logo place, never the time (user 2026-10-15): no logo through the whole clip -> it finds one
  shown only at the start or popping in late (verified as static edges in that span; logo-free water / animals give
  "no logo found") and fills only that span (~15 s). `--end` forces the late search.
- Reply with the one output line. "Object Removal" of a logo -> use this.
- Auto-detect misses semi-transparent logos over bright moving water (finds a letterbox edge instead): look at the
  corner crop of the original, then give boxes yourself at 640x360, one small box per logo (never one big box over two):
  `hide_logo.py "<path>" --box 583,301,608,325 616,344,639,357` (Gemini star, Veo text).
- **"logo Gemini"** (user 2026-10-16, verified on 4 clips 1280x720 8 s): semi-transparent white / grey 4-point star
  (diamond, concave sides), bottom-right but NOT in the corner: centre ~(580,300) at 640x360 (~90.6% x, 83.3% y),
  ~22x22 px, whole clip from 0 s. Auto-detect misses it or picks a wrong static edge (x~450, or mid-frame): skip auto,
  `hide_logo.py "<path>" --box 566,286,594,314`. Other resolution -> scale the box by the same ratios; unsure -> one
  corner crop (`crop=160:90:480:270` of the 640x360 frame, x4) to confirm, then the same crop of the `_nologo` copy once.

- **"logo BBC"** (user 2026-10-30, amazon_291026, 1920x1080 AI clips): three white squares "B B C", top-left
  corner, whole clip; at 640x360 ~(7,3)-(45,18) (some clips (0..9,6)-(32..43,20): scale 0.9-1.2). Template
  `logos/bbc.npy`: `known_logo()` matches it in every `--at` / one-shot run before the static-edge test (static
  scenery = a tree trunk outscored it and got inpainted, 01:22 / 12:56); 8/8 clips right. Clean ones <= 0.40, logos
  >= 0.52 (`KNOWN_HI` 0.47). Miss -> `--box 0,3,50,21`.
- **Old-delogo residue** ("đã xóa nhưng chưa sạch", user 2026-10-30): horizontal smeared streaks over the old logo
  area (an earlier ffmpeg delogo baked into the original, e.g. both frogs at amazon_291026 05:36): no static logo
  left, `--at` says FAILED -> `hide_logo.py "<file>" --box 0,3,74,22` (BBC area + the smear).
- New logo kind confirmed by the user -> add its template: the median-frame gradient crop of one clean example
  (`grad(sample(p)[0])[y0-2:y1+3, x0-2:x1+3]`) saved as `logos/<name>.npy`, then a line here.
- In a day project `vid_DDMMYY` run every Resolve command with `DVR_CHANNEL=Chann_N` (two "Edit": it stops without).

## Logo at timeline positions ("shot ở 21:38 và 05:12 có logo góc trên trái")
The user checks the result in Resolve: run it, reply with the output lines; no stills, no questions, no overwrite
question.

    .venv/Scripts/python .claude/skills/hide-logo/scripts/hide_logo.py --at 21:38 tl 05:12 tr 07:40

Corner optional after each time. Per time: scores the V1 clip there and its neighbours within 1 s (a reported time
often lands just before the cut), delogoes the one with the logo into `AI_video\_nologo\`, relinks it in the open
project; a failed shot does not stop the others. No logo through the whole clip -> tries one shown only at the start
(removed 0-Ns) and one popping in late (removed from Ns), best share wins. No crops or stills afterwards (user rule
2026-10-13): the user reports a wrong pick. Reply (Vietnamese): per time the clip (time range, file), REVIEW flag,
FAILED lines.

## Fill engine
Every fill (auto, `--box`, `--at`, `--execute`) = MiniMax-Remover (user 2026-10-15: clone patch blurred / glowed;
Netflix VOID tested: 64 min/clip on 8 GB, dropped). `scripts/minimax_worker.py` runs in its own venv
`D:\tools\minimax_remover\venv` (weights 2.6 GB + repo there): native-res crop around the logo (min 336x192, +48 px
context), 3 steps (A/B vs ground truth: as good as 6), fewest windows of <= 65 frames crossfaded, mask latent encoded
once, model pixels only on the logo (feathered), rest untouched. ~30 s per 10 s clip on the RTX 5060 with Resolve open
(stdout has per-phase timing); one clip at a time (GPU). Knobs (env): `MM_STEPS` (2 also passed the A/B), `MM_CROP`
(256x160 = 30% faster, less faithful). Without GPU: `--fill clone` (clone texture + haze, `--haze N`) or `--fill interp`
(ffmpeg delogo + haze).

## Overwrite at Done (user rule 2026-10-11)
After `/doc-edit done` (runs at once; never ask whether the video is exported, user 2026-10-13): run `--pending`.
Copies listed -> ask "Bạn có muốn ghi đè các file trong folder _nologo lên các file gốc của chúng không?" (with the
list). Only on "có"/"yes":

    .venv/Scripts/python .claude/skills/hide-logo/scripts/hide_logo.py --pending
    .venv/Scripts/python .claude/skills/hide-logo/scripts/hide_logo.py --overwrite-all

`--overwrite-all` drives Resolve itself: saves + closes the project (Resolve holds the files open), each copy replaces
its original, reopens the project on the same timeline, relinks to the original paths, moves each clip's tags / YOLO
cache / ledger id to the new content hash (no re-tag, no rescan). The reopen drops V1 fades (2026-10-30): it then
runs `place.black_fades` for every video of that project (one `black fades` line each). File still locked after the close -> it quits
Resolve, finishes, says so: ask the user to reopen the project, then `--relink`. Z: originals are never overwritten
(copy stays linked). Reply (Vietnamese): originals overwritten, relinked, kept (Z:), problems.
`--relink`: open project -> items on an original point at its pending copy, items on an overwritten copy at the
original again.

## Limits
MiniMax windows hit an attention cliff above ~4300 tokens (17 latent frames x 21x12 patches): bigger crops get shorter
windows automatically. One logo position per folder. Fusion Object Removal is not usable: Scene Analysis cannot be
triggered from the API (Resolve 21.1).
