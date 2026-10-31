# hide-logo notes (history + calibration; SKILL.md has the commands)

## Known logos
- **BBC** (user 2026-10-30, amazon_291026, 1920x1080 AI clips): three white squares "B B C", top-left, whole clip;
  at 640x360 ~(7,3)-(45,18) (scale 0.9-1.2). Template `logos/bbc.npy`, matched by `known_logo()` before the
  static-edge test (static scenery, e.g. a tree trunk, outscored it: 01:22 / 12:56). Clean <= 0.40, logos >= 0.52
  (`KNOWN_HI` 0.47).
- **BBC EARTH / BBC Earth** (user 2026-10-31, amazon_301026, 7 clips): the BBC squares + the word, ~40-95 x 9-14 px
  at 640x360. The bbc box alone left "EARTH" (2 redo rounds). A `bbc_earth.npy` template scored 0.58-0.62 on EARTH
  clips but 0.49-0.53 on wrong corners (fish_many-burst, fish_surfaces...) -> dropped; `tail()` widens the bbc box
  over the text instead (static edges or logo-bright pixels, gaps <= 8 px, <= 1.5x width): 4/4 test clips right
  (EARTH, faded EARTH, "Earth", plain BBC unchanged).
- **Gemini** (user 2026-10-16, 1280x720): semi-transparent 4-point star, bottom-right but not in the corner, centre
  ~(580,300) at 640x360, ~22x22 px, whole clip. Auto-detect misses it: `--box 566,286,594,314` (scale by ratio for
  other sizes).
- **Old-delogo residue** (2026-10-30): smeared streaks over the BBC area from an earlier ffmpeg delogo; no static
  logo left, `--at` FAILED -> `MM_MASK=box hide_logo.py "<file>" --box 0,3,74,22`.
- New logo kind confirmed by the user -> template = median-frame gradient crop of one clean example
  (`grad(sample(p)[0])[y0-2:y1+3, x0-2:x1+3]`) as `logos/<name>.npy`; check it on clean clips too (false corners).

## Fill engine
MiniMax-Remover (user 2026-10-15: clone patch blurred / glowed; Netflix VOID 64 min/clip on 8 GB, dropped) in
`D:\tools\minimax_remover\venv` (weights + repo there). Native-res crop around the logo (min 336x192, +48 px
context), fewest windows of <= 65 frames crossfaded, mask latent encoded once, model pixels only on the mask.
- Mask = the glyphs, not the box (2026-10-31): Otsu split of the temporal median inside the box, holes filled,
  dilated. A box 3x the logo height left a blurred patch with edge lines; the glyph mask keeps the real background
  between letters. `MM_MASK=box` = old whole-box mask.
- Timing (RTX 5060, Resolve open, 10 s 1080p): imports 3 s, encode 5-6 s, denoise 7-10 s, decode 8-9 s,
  composite 3 s = ~30 s. Model load is ~4 s, so one process per clip costs little.
- `MM_STEPS` 2 (default since 2026-10-31; A/B 2026-10-15 vs ground truth: 6 st err 8.6, 3 st 7.9, 2 st 7.7);
  `MM_CROP` 256x160 is 30% faster but err 10.1.
- Without GPU: `--fill clone` (clone texture + haze, `--haze N`) or `--fill interp` (ffmpeg delogo + haze).
- Limits: attention cliff above ~4300 tokens per window (bigger crops get shorter windows); one logo position per
  scanned folder; Fusion Object Removal is not scriptable (Scene Analysis, Resolve 21.1).

## Overwrite at Done
`--overwrite-all` saves + closes the project (Resolve holds the files), replaces each D: original with its copy,
reopens on the same timeline, relinks, moves tags / YOLO cache / ledger id to the new content hash, then re-sets
the 4 black fades of every video of the project (the reopen drops them). File still locked -> Resolve is quit;
reopen the project, then `--relink`. Z: originals never change (the copy in `_nologo\z\` stays; plan.py uses it).

## Testing without side effects
`NOLOGO_DIR=<scratch>` keeps copies out of `_nologo`, but `record()` still writes `nologo.json` and a clip that is on
V1 gets relinked: back up `nologo.json`, test on files NOT on the timeline (`dvr_cowork find`), restore after.
