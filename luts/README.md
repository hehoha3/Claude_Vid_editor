# Amazona LUT library (Rec.709 gamma 2.4 in -> out, 33^3 .cube)

Creative LUTs for AI/real rainforest clips. Apply on a shot that is already balanced (exposure/WB): for a whole edit
use `.claude/skills/colorist/scripts/grade.py` (per-shot CDL + these LUTs per light group).
Regenerate / tweak: `.venv/Scripts/python.exe luts/make_luts.py` (params in `LUTS` dict), then copy the .cube files to
`C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT\Amazona\` (same names) and run `project.RefreshLUTList()`.

**Any LUT / look work: load skill `colorist` first** (non-negotiables + `references/looks.md`, `ai-footage.md`) and judge
on real frames with numbers (luma p1/p99, contrast, mean sat vs the ungraded clip), not on the ramp self-check alone.

## Design rules (v2, 2026-10-09 - v1 looked hazy and old)
- Clean blacks: lift 0-0.006. Haze belongs in a gradient window on the far background, never a global lift
  (lifted blacks also expose AI macroblocks).
- Bright whites: shoulder >= 0.90 so whites reach ~0.99; soft roll-off only at the very top.
- Contrast 1.04-1.20 about pivot 0.435 (lower only for dawn haze).
- Saturation must not fall below the ungraded clip except in Tension / Dusk (max -10%). Compression (`vib`) only
  tames near-neon colours.
- Greens: lime -> emerald (`gshift`) plus subtractive density (`gdens`) for rich, darker foliage instead of grey.
- Split tone barely visible; no warm-highs + cool-shadows pairing as a style (reads as "YouTube LUT" / vintage).

v1 -> v2 on 8 demo_2 frames (mean): p1 0.066 -> 0.030, mean sat 0.260 -> 0.321 (ungraded 0.315), contrast 0.502 -> 0.532
(AMZ_01).

| LUT | when | what it does |
|---|---|---|
| AMZ_01_Natural_Canopy | daylight base, foraging | clean blacks, bright whites, lime -> deep emerald, sat +6% |
| AMZ_02_Clear_Daylight | opening, bright clean scenes | crisp, neutral whites, fresh greens, sat +10% |
| AMZ_03_Misty_Dawn | dawn, haze, aftermath | gentle contrast with true blacks, warm highlights, slightly cool shade |
| AMZ_04_Swamp_Olive | flooded forest / swamp / river | olive-brown water kept (not cyan), deep mossy greens |
| AMZ_05_Tension_Stalk | stalk, ambush, standoff | contrast 1.20, sat -6%, slightly cooler mids, denser greens |
| AMZ_06_Golden_Release | sun shafts, warm moments | warm highlights, neutral shadows, sat +8% |
| AMZ_07_Dusk_Night | dusk / night | true blacks, cool mids, sat -10%, warm last light |
