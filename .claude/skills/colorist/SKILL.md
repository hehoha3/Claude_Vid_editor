---
name: colorist
description: Colorist for Resolve - scopes, nodes, primaries/secondaries, shot matching, LUTs and looks, grading AI wildlife clips (Veo/Kling) into one consistent BBC-style film (grade.py). Use for any color, grade, LUT, exposure, white balance, fur/sky/greens, night, contrast, banding, noise question or "shot looks wrong/cheap/fake".
---

# Colorist

Read the reference that fits the question; do not load all of them:
- `references/pipeline.md` - color management, scopes, node tree template, primaries/secondaries tools
- `references/looks.md` - aesthetic principles, story color scripting, wildlife/environment recipes
- `references/ai-footage.md` - problems specific to generated clips and how to fix them
- `luts/README.md` (workspace root) - the channel's AMZ LUT library, its design rules and how to rebuild/install it

## Non-negotiables
1. Balance before look. Every shot gets a neutral, matched base (exposure, white balance, contrast)
   on its own nodes before any creative node. A look on an unbalanced shot multiplies the error.
2. Judge on scopes, confirm with eyes. Waveform/parade for levels and balance, vectorscope for hue
   and saturation; the image for intent. Viewer brightness and room light lie.
3. Match to a hero shot per scene, not to the previous shot (prevents drift across a sequence).
4. Subtractive before additive: remove casts and excess saturation first, then add.
5. Keep the hierarchy: brightest + most saturated + sharpest area = where the eye should go
   (usually the animal's eye/face). Background must not out-shout the subject.
6. One look per story chapter, varied deliberately (color script), consistent within the chapter.
7. Protect natural references: fur, feathers, foliage, water and sky have expected hues; viewers
   notice when a lion turns orange or a canopy turns neon.

## Match a whole edit (one place, clean look): `scripts/grade.py`
    .venv/Scripts/python.exe .claude/skills/colorist/scripts/grade.py plan --sheet   # Resolve untouched; run in background
    .venv/Scripts/python.exe .claude/skills/colorist/scripts/grade.py apply          # only after the user's "yes"
`plan` balances every V1 shot of "Edit" toward one target per light group (Day / Golden / Dusk, from the library
light tag) with a CDL, simulates CDL + AMZ LUT and nudges until the house limits pass (clean blacks, whites ~0.95,
no neon, no clip). Read only its stdout: per group the shot-to-shot spread of p50 / sat (lower = more one place),
mean p1 / p99 / sat before -> after, flagged count. View `sheet.jpg` once (6 shots, ungraded top / graded bottom).
`apply`: backup `Edit_bak_grade_*`, Color Group per light with its LUT on the group post-clip node 1, CDL on clip
node 1 (overwrites node 1: destructive, ask first). Re-run `plan` after any V1 change.

## Fast diagnosis -> first move
| symptom (stats/scopes) | first move |
|---|---|
| luma p99 >= 0.98, clipped_pct > 1% | lower Gain or use HDR Highlight zone; soft clip at timeline level |
| luma p1 > 0.08 (washed out) | lower Lift/Offset slightly, or contrast up with pivot ~0.435 |
| luma p1 < 0.01 and crushed_pct > 5% | raise Lift or shadows (HDR Dark zone); crushed fur loses texture |
| cast in midtones (e.g. -B 0.05 = yellow) | Offset or Gamma wheel toward the missing channel, check parade |
| cast only in shadows/highlights | Lift-only or Gain-only correction (split balance) |
| sat_p95 > 0.75 | global saturation down, then Hue vs Sat on the offending hue |
| flat, lifeless (contrast < 0.5) | contrast + pivot, or Custom curve S; add local contrast via Midtone Detail sparingly |

## Answer format for grading advice
Observation (numbers/what you see) -> action in Resolve (palette, control, starting value, node) ->
why -> alternative (different look) and trade-off -> what to check on neighbouring shots.
