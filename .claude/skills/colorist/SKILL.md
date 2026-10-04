---
name: colorist
description: Senior colorist knowledge for DaVinci Resolve - color management, scopes, node trees, primaries and secondaries, shot matching, looks, film emulation, and specifically grading AI-generated wildlife footage (Veo/Kling clips) into a consistent BBC-style documentary. Use for any question about color, grading, LUTs, exposure, white balance, skin/fur tones, skies, greens, night scenes, contrast, look development, matching clips, banding, noise or "why does this shot look wrong/cheap/fake".
---

# Colorist

Read the reference that fits the question; do not load all of them:
- `references/pipeline.md` - color management, scopes, node tree template, primaries/secondaries tools
- `references/looks.md` - aesthetic principles, story color scripting, wildlife/environment recipes
- `references/ai-footage.md` - problems specific to generated clips and how to fix them

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
