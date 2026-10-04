# Grading and repairing AI-generated footage

Generated clips have different failure modes from camera footage. Check for them before grading.

| problem | how it shows | fix (in order of preference) |
|---|---|---|
| Exposure/WB jumps between generations of one scene | cuts feel like different days | hero-shot matching (pipeline.md section 6); match Offset first |
| Over-saturated, lime greens; "plastic" texture | canopy looks synthetic | Hue vs Sat/Hue vs Hue on greens, slightly negative Midtone Detail, grain at timeline level |
| Over-sharpening / crunchy edges | halos on branches and fur | negative Midtone Detail or Soften & Sharpen (soften), never add sharpening |
| Luminance flicker | brightness pulses frame to frame | Deflicker (Studio); else avoid the clip section or key-frame Offset gently |
| Banding in skies/gradients | steps in blue sky or mist | do not push gradients; add grain/noise (dither); less Hue vs Lum on that hue |
| Blocky shadows | macroblocks when blacks are lifted | keep shadows down, NR before grade (Studio), add grain |
| Morphing anatomy / extra limbs / melting background | most visible at the start/end of a clip and in fast motion | trim to the clean middle; cut away on the frame before the error; blur/defocus a background area with a tracked window; choose another take |
| Watermark or stray text | corner logos, gibberish text | reframe (Transform zoom 103-110% if resolution allows), patch tools, or replace the shot |
| Mixed resolutions (720p/1080p/4K) | soft shots next to sharp ones | upscale consistently (Super Scale is Studio); add grain uniformly so softness matches |
| Mixed frame rates (24 vs 30) | judder/duplicate frames | conform to the timeline rate (24); retime with Optical Flow only for small changes |
| Unnatural motion speed | animal moves too fast/slow | Retime Controls; Speed Warp (Studio) for slow motion; AI clips interpolate limbs poorly - keep retimes within ~70-130% |

## Consistency across a whole film
- One color management setup, one output transform, one grain at timeline level.
- Grade per scene in Groups (pre-clip normalisation + post-clip look).
- Review the entire timeline at 1x before delivery; flag any shot that "pops" out.
- Same species across shots must keep the same fur/feather color: match on the animal, not the
  background.
