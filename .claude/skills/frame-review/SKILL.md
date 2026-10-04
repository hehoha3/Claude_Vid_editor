---
name: frame-review
description: How to critique graded frames from the user's DaVinci Resolve timeline and turn the critique into concrete Resolve actions. Use when the user asks "how does this look", "is this shot good", "review my grade/scene", "what would make it more cinematic/BBC", gives timecodes to check, or when you need to look at the picture before advising on color, composition, continuity or AI artifacts.
---

# Frame review

## Get the evidence cheaply
1. `.venv/Scripts/python.exe -m dvr_cowork frames --at <t1> <t2> ... --stats`
   (mm:ss relative to timeline start, or full timecode). Stills include the current grade.
2. Read the numbers first (they cost few tokens):
   - `luma_p1_p10_p50_p90_p99` (0-1): p1 ~0.02-0.06 normal blacks; p99 > 0.98 + `clipped_pct` > 1%
     = clipped highlights; p50 ~0.35-0.5 for most daylight shots.
   - `contrast_p90_minus_p10`: < 0.45 flat, 0.55-0.75 typical, > 0.85 very punchy.
   - `crushed_pct` > 5% = shadow detail lost.
   - `sat_mean` ~0.2-0.35 natural; `sat_p95` > 0.75 = something is neon.
   - `cast_*`: "+R 0.04" means red is 0.04 above the average of R,G,B in that zone.
     Small casts in highlights/shadows are often intentional (warm highs, cool shadows).
3. Then view the images (max ~6 per pass). For continuity, also grab the shots before/after.

## Critique checklist (in this order)
1. Story/readability: is it clear what we should look at? Is the animal readable at phone size?
2. Exposure and contrast of the subject (not the frame average).
3. White balance: neutrals neutral? casts intended?
4. Saturation and hue: any neon greens/oranges; fur/feather hues plausible.
5. Separation and depth: subject vs background in luminance, color and sharpness.
6. Composition: subject placement, headroom, lead room in the direction of motion/gaze, horizon,
   distracting bright edges.
7. AI artifacts: anatomy (legs, eyes, beak, fingers), morphing textures, impossible geometry,
   text/watermarks, repeated patterns, flicker (needs neighbouring frames).
8. Continuity with neighbours: same time of day, same subject color, consistent screen direction.

## Output format (Vietnamese to the user)
For each frame:
- **Điểm tốt** (1 line)
- **Vấn đề chính** (1-3, most important first, with the evidence: number or what is visible)
- **Cách sửa trong Resolve**: node, tool, starting value (e.g. "node WB: Temp -200 đến -400, kiểm
  tra parade trên lông ngực trắng" or "HDR palette > Highlight -0.5 stop", "Hue vs Sat: giảm vùng
  lime ~20%")
- **Phương án khác**: an alternative look and its trade-off
Close with sequence-level advice (what to match, what to check by playing at speed).
Be specific and honest; if a shot cannot be saved by grading (anatomy error), say so and propose
trimming around it or replacing it.
