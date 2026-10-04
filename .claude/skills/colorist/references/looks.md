# Looks and aesthetics for natural-history documentary

## What reads as "premium natural history"
- Natural, believable color with rich but controlled saturation; nothing neon.
- Clean blacks with texture still visible in dark fur/feathers; highlights that roll off softly
  (sun on water, white chest feathers keep detail).
- Clear subject separation: the animal is slightly brighter, warmer or more saturated than its
  surroundings; the background recedes (cooler, less contrast, softer).
- Consistency: a sequence feels like one camera and one time of day.
- Restraint: heavy teal/orange, crushed blacks, and strong vignettes read as "YouTube LUT", not BBC.

## Principles to argue from
1. Value hierarchy: the eye goes to the brightest, highest-contrast, most saturated, sharpest area.
   Grade so that area is the animal's eye/face or the action.
2. Atmospheric perspective: distance = lighter, lower contrast, cooler, less saturated. Recreate it
   with a gradient or depth-based window to add depth to flat AI shots.
3. Color harmony: analogous palettes (greens + yellow-greens + warm browns) feel calm; complementary
   accents (warm subject vs cool surroundings) create tension and separation. Use the accent where
   the story needs attention.
4. Saturation discipline: real scenes have few highly saturated areas. Pull saturation from
   shadows and highlights first (Lum vs Sat), keep it in the mid-tones of the subject.
5. Light direction: one believable key light. Windows that brighten the lit side of the animal and
   darken the opposite side add dimension; never brighten everything evenly.
6. Contrast is emotional: higher contrast and harder shadows = danger; lower contrast and lifted,
   warm shadows = safety, tenderness, aftermath.

## Color script for a predator/survival story (vary by chapter, keep within chapter)
| beat | intent | tendency |
|---|---|---|
| Establishing / dawn | wonder, scale | soft contrast, warm highlights, cooler shadows, gentle haze |
| Daily life / foraging | familiarity | neutral balance, natural saturation |
| Stalk / suspicion | unease | contrast up a little, saturation down 10-20%, cooler midtones, darker edges |
| Strike / chase | adrenaline | highest contrast, subject accent saturation kept, background desaturated |
| Aftermath | weight | lower saturation, slightly lifted shadows, cooler or overcast feel |
| Resolution | release | return of warmth, open highlights |
Keep changes subtle (5-15% saturation, 1/4-1/2 stop) so the audience feels rather than notices.

## Environment recipes (starting points, not presets)
### Amazon rainforest canopy / understory
- AI greens skew yellow-lime and oversaturated. Hue vs Hue: rotate yellow-greens slightly toward
  green; Hue vs Sat: reduce lime; Color Warper: compress greens toward a deeper emerald family.
- Lower green luminance a touch (Hue vs Lum) so the animal pops; watch for banding.
- Keep shafts of light warm and the shade slightly cool for depth; protect dappled highlights.
- Haze/humidity: slight lifted far background via gradient window, not global lift.
### River / oxbow lake / flooded forest
- Amazon water is brown-olive, not cyan: do not "fix" it toward blue. Keep reflections' highlights
  controlled; caiman/otter wet skin has specular sheen - keep it, it sells realism.
- Mist on water at dawn: low contrast, cool, allow a warm horizon.
### Savanna / golden hour
- Warm highlights, keep shadows neutral-to-cool (do not make everything orange). Golden fur
  (lion, leopard, impala) should sit near the skin-tone line on the vectorscope, not beyond it.
- Dust/haze: softer contrast in the distance.
### High altitude / snow / rock
- Snow must be bright (waveform ~750-900) with texture, and neutral or slightly cool in shade,
  never grey or yellow. Blue shadows on snow are physically correct - keep some.
- Thin air: crisp contrast and saturated sky near zenith, but keep sky gradient smooth.
### Night / low light
- Day-for-night if needed: lower exposure 1.5-2.5 stops, desaturate 40-60%, shift midtones cool,
  keep a few highlights (moon on water, eye shine) so it is not mud. Protect blacks from noise.
### Underwater / murky water
- Restore red only modestly; accept limited range. Gradient from surface light to depth.

## Subject notes
- Harpy eagle: grey head and white chest must stay neutral and unclipped; black chest band keeps
  feather texture. Watch blue casts in grey plumage.
- Dark wet animals (caiman, otters): exposure on the specular sheen and textured mid-tones, not on
  the deepest black; lifting their blacks reveals AI compression blocks.
- Monkeys/primates: faces have skin-like tones; keep them near the skin-tone line.
- Golden cats: separate them from yellow grass via saturation contrast and slight luminance offset.

## Film emulation (use subtly)
- Highlight roll-off (DRT / soft clip), slight subtractive density on saturated colors (Color Slice
  or Hue vs Lum), split-tone (warm highs, neutral/cool shadows), grain at timeline level last.
- Halation and Film Look Creator are Studio features; small amounts only.
- Grain unifies mixed-source AI clips more than any other single tool.
