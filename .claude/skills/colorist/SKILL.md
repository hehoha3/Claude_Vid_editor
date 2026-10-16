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

## Match a whole edit (same place, same time): `scripts/match.py` (default since 2026-10-16)
User priority: every shot of a scene must look like one place and time, reviewable at once, few fixes. Claude runs
the whole loop itself; the user only reviews heroes once and the green markers after.

    .venv/Scripts/python.exe .claude/skills/colorist/scripts/match.py plan     # Resolve untouched; background (~5-10 min first run)
    .venv/Scripts/python.exe .claude/skills/colorist/scripts/match.py apply    # only after the user's "yes" (overwrites node 1)
    .venv/Scripts/python.exe .claude/skills/colorist/scripts/match.py verify   # ExportLUT per shot -> real numbers + markers
    .venv/Scripts/python.exe .claude/skills/colorist/scripts/match.py note 02:41 group=Day warm=-0.01 "note=..."

Clip node 1 = CDL (balance, grade.py solver) + a per-shot match LUT (Resolve runs the node CDL before the node LUT);
the AMZ look LUT stays on the Color Group post-clip node. Scenes are cut from the measured look; one hero per scene
(real footage first); every shot is pulled to its hero per hue band (neutral, fur/earth, foliage, sky/water) and in
lightness, heroes half-way to the group, so scenes differ but the film is one place. Light group = tag corrected by the
image. Read only stdout: whole-group and in-scene spread (L, colour) balance-only -> matched, flagged list, heroes.
View `heroes.jpg` (all heroes) and `scenes.jpg` (6 scenes: left balance only, right matched; col 1 = hero) once.
Flow per video: plan -> show the user heroes.jpg (swap: `note <tc> hero=1`) -> "yes" -> apply -> verify -> report
spreads + marker count. User notes ("02:41 lá vàng chanh") -> `note` (group / hero / strength 0-1 / skip / exp / warm /
sat), re-plan, apply, verify. Notes live in `.work/grade/<project>/overrides.json` and survive re-plans.
Not scriptable (API): curves, qualifiers, windows, Hue vs Sat, Color Warper -> tell the user node + values.

`grade.py` (balance only, CDL per light group) stays as the solver match.py builds on; use it alone only if asked.

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
