# Color pipeline in DaVinci Resolve

## 1. Color management (decide once per project, before grading)
AI clips (Veo, Kling, Hailuo, Pika) arrive as 8-bit H.264/H.265, Rec.709 primaries, display gamma.
Treat them as **Rec.709 Gamma 2.4** input. Grading in a wide working space still helps: exposure
moves behave like camera stops, saturation and white balance stay natural, highlights roll off.

Option A - Resolve Color Management (simplest):
Project Settings > Color Management > Color science "DaVinci YRGB Color Managed"; turn off the
automatic preset so you can set: input Rec.709 Gamma 2.4, timeline DaVinci Wide Gamut / DaVinci
Intermediate, output Rec.709 Gamma 2.4. Enable the input/output DRT (DaVinci) for soft roll-off.

Option B - node-based (more control, common among colorists):
"DaVinci YRGB" (unmanaged). First node per clip (or a pre-clip group): Color Space Transform
Rec.709/Gamma 2.4 -> DaVinci Wide Gamut/DaVinci Intermediate. Last node at timeline level: CST
DWG/Intermediate -> Rec.709/Gamma 2.4, tone mapping DaVinci, gamut mapping saturation compression.
If the input CST has "Apply Inverse DRT" available, enable it so an ungraded shot round-trips
unchanged through the output tone mapping.

Rules: never stack a "creative LUT" that expects Rec.709 inside a wide-gamut node chain; put
Rec.709 LUTs after the output CST or wrap them in CSTs. Mid-grey in DaVinci Intermediate is ~0.336,
so set Contrast pivot near there when working in Intermediate (default pivot 0.435 suits Rec.709).

Monitoring on Windows: the GUI viewer is not color-managed; calibrate the monitor to Rec.709 /
gamma 2.4 (or sRGB, ~100 nits) or use a Blackmagic I/O card. Always check the final render on a
phone - most YouTube viewers watch there.

## 2. Scopes (Workspace > Video Scopes)
- Waveform (luma): 0-1023. Blacks of a normal daylight shot sit just above 0 (deep shadows ~ 0-60),
  mid fur/foliage ~ 350-600, bright sky 700-850, speculars may touch the top. Avoid flat plateaus at
  0 or 1023 (crushed/clipped) unless intended.
- RGB Parade: neutral things (rock, white feathers, overcast sky, snow) should have equal R=G=B
  heights. Unequal bottoms = shadow cast, unequal tops = highlight cast.
- Vectorscope: distance = saturation, angle = hue. Warm fur and skin cluster around the skin-tone
  indicator line; foliage between yellow and green; water/sky toward cyan/blue. Zoom 2x for subtle
  shots. A trace that shoots far out on one vector = oversaturated hue.
- Histogram for quick exposure distribution.

## 3. Node tree template (serial, label every node)
Clip level:
1. `NR` (Studio: Temporal NR 2 frames + light Spatial) - first, on clean source, only when needed.
2. `EXP` - Offset/HDR Global exposure, contrast + pivot.
3. `WB` - Temp/Tint or Offset wheel; check parade on a neutral.
4. `SAT` - global saturation / Color Boost / Lum vs Sat (desaturate deep shadows and near-white).
5. `SEC` - secondaries: Hue vs Hue/Sat curves, qualifiers (sky, greens), Color Warper.
6. `WIN` - relight with power windows (+tracking): brighten subject face 1/4-1/3 stop, darken
   edges, gradients on bright skies.
7. `FIX` - artifacts (blur a morphing background, patch, defocus).
Group post-clip (shared by all shots of a scene/chapter): `LOOK` (split-tone, curve, film look).
Timeline level: output CST (option B), soft clip/highlight roll-off, `GRAIN`, final vignette (rare).
Use **Groups** for chapter looks and **Shared Nodes** for anything that must stay identical.

## 4. Primary tools - when to use which
- Offset: whole-signal shift. In log/Intermediate = exposure and global balance. First move.
- Lift / Gamma / Gain (Primaries Wheels): shadows / mids / highlights; good for display-space
  shaping. Split-balance casts (cast only in shadows -> Lift).
- Log wheels (Shadow/Midtone/Highlight with adjustable ranges): tonal color in log space; cleaner
  split-toning than Lift/Gain.
- HDR palette: zone-based exposure and color (Dark, Shadow, Light, Highlight, Specular + Global)
  measured in stops. Best tool for "bring down the sky 1/2 stop, open shadows 1/3 stop" naturally.
- Contrast + Pivot: global contrast around mid-grey; pair with Midtone Detail (negative values
  soften, positive add local contrast - be gentle on AI footage, it exaggerates fake texture).
- Curves (Custom): S-curve for contrast; keep the curve smooth, small moves.
- Color Boost: raises saturation of low-saturated colors only - natural vibrance.

## 5. Secondary tools
- Hue vs Hue: rotate yellow-greens toward green, orange-reds toward orange, etc.
- Hue vs Sat / Lum vs Sat / Sat vs Sat: tame a single hue, remove saturation in deep shadows and
  near-white highlights (looks more photographic and filmic).
- Hue vs Lum: darken blues (sky) or greens - watch for noise/banding on 8-bit sources.
- Qualifier (HSL/3D): isolate sky, foliage, subject; always refine the key (clean black/white,
  blur), check with highlight mode; keep keys soft so they survive motion and compression.
- Power windows + tracker: relighting, vignettes, gradients. Feather generously.
- Color Warper (Hue-Sat / Chroma-Luma mesh): reshape a whole color range at once (e.g. compress
  greens into a tighter, deeper family).
- Color Slice (Resolve 19+): per-vector subtractive saturation and density - quick, natural
  "film density" on specific hues.
- Magic Mask / Depth Map (Studio): isolate the animal or separate fore/background without keying.

## 6. Shot matching workflow
1. Choose a hero shot per scene, grade it fully.
2. Grab a still (Gallery). For each other shot: split-screen wipe against the still.
3. Match in order: exposure (Offset/HDR global) -> contrast -> white balance on a neutral ->
   saturation -> specific hues. Compare parade tops/bottoms and vectorscope shape side by side.
4. Shot Match (right-click on the clip) can give a starting point; always refine by eye.
5. Play the sequence at speed: a matched sequence feels like one camera, one moment of day.
