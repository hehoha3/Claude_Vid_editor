# Amazona LUT library (Rec.709 gamma 2.4 in -> out, 33^3 .cube)

Creative LUTs for AI/real rainforest clips, installed in
`C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT\Amazona\` (Resolve name `Amazona/<LUT>.cube`).
`/doc-edit color` (light.py) does NOT use them (CDL only); `grade.py` / `match.py` put them on the Color Group post-clip
node. Apply on a shot that is already balanced (exposure/WB).
Regenerate / tweak: params in `LUTS` of `scripts/make_luts.py`, then
`.venv/Scripts/python.exe .claude/skills/colorist/scripts/make_luts.py` (writes straight into that folder, same names)
and `project.RefreshLUTList()`.

Judge on real frames with numbers (luma p1/p99, contrast, mean sat vs the ungraded clip), not on the ramp self-check
alone (non-negotiables in SKILL.md, `looks.md`, `ai-footage.md`).

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
