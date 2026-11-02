---
name: colorist
description: Colorist for Resolve - scopes, nodes, primaries/secondaries, shot matching, LUTs and looks, grading AI wildlife clips (Veo/Kling) into one consistent BBC-style film (grade.py). Use for any color, grade, LUT, exposure, white balance, fur/sky/greens, night, contrast, banding, noise question or "shot looks wrong/cheap/fake".
---

# Colorist

Read only the reference that fits the question:
- `references/pipeline.md` - color management, scopes, node tree template, primaries/secondaries tools
- `references/looks.md` - aesthetic principles, story color scripting, wildlife/environment recipes
- `references/ai-footage.md` - problems specific to generated clips and how to fix them
- `luts/README.md` (workspace root) - the channel's AMZ LUT library, its design rules, rebuild/install

## Non-negotiables
1. Balance before look: neutral, matched base (exposure, white balance, contrast) on its own nodes before any creative
   node; a look on an unbalanced shot multiplies the error.
2. Judge on scopes, confirm with eyes: waveform/parade for levels and balance, vectorscope for hue and saturation, the
   image for intent. Viewer brightness and room light lie.
3. Match to a hero shot per scene, not to the previous shot (no drift across a sequence).
4. Subtractive before additive: remove casts and excess saturation first, then add.
5. Hierarchy: brightest + most saturated + sharpest area = where the eye should go (usually the animal's eye/face);
   the background never out-shouts the subject.
6. One look per story chapter, varied deliberately (color script), consistent within the chapter.
7. Protect natural references: fur, feathers, foliage, water and sky have expected hues (a lion turning orange or a
   neon canopy is noticed).

## `/doc-edit color` = light pass `scripts/light.py`, one space per story (user 2026-10-25: "mỗi story các shot trông như cùng 1 không gian", never a broken shot; 2026-10-22: no heavy match, vivid + bright)

    .venv/Scripts/python.exe .claude/skills/colorist/scripts/light.py plan    # Resolve untouched
    .venv/Scripts/python.exe .claude/skills/colorist/scripts/dry_preview.py <project>   # golden-grass before/after
    .venv/Scripts/python.exe .claude/skills/colorist/scripts/light.py apply   # backup Edit_bak_light_<stamp>, CDL node 1

Day project: all three with `DVR_CHANNEL=Chann_N` in front; plan + golden-grass LUTs then live under
`<project>_<Chann_N>` (light.pkey, user 2026-10-30), so the two channels never share them. `plan` drops frame-cache
files (`.work/grade/frames320`) unused for 14 days (CACHE_DAYS).

**Per shot: one small CDL on node 1** (~1 min for 1000 shots, frame cache; no group look LUT):
- toward its `# STORY`'s space (`space()`: median of the story's day shots): exposure x0.6, tint of near-grey pixels
  x0.6 (story tint 40 % neutralised), sat x0.5 toward story median x1.10; slope 0.90-1.10 +-5 % per channel; power
  <= 1.04 on flat shots; sat 0.80-1.25; `plan` prints each story's spread before -> after;
- "màu tươi" (user 2026-10-22): a day shot below its story aim gets sat >= x1.10, one above it comes down to >= x0.92,
  never past SAT_HI; night stays dark + muted; over-saturated AI clips come down;
- intro shots (spec `# INTRO`) get 30 %; a correction that adds clip / crush / neon is halved until it does not.

**Golden grass** (user 2026-10-22, 02:25 impala pair; `dry_pass`), ONLY inside a daytime stretch of burnt / golden
grass (same story, +-5 shots, >= 60 % of the day shots golden):
- a shot whose grass is greener (+8 deg hue) or paler (gold sat < 75 %) gets the stretch's golden grass as its own
  LUT on node 1 (`dry_auto_<frame>.cube`, match.dry, strength 1);
- never: intro, night / dusk / golden light, water settings (waterhole too), forest / sky settings (2026-10-25: forest
  under a flying vulture went blotchy yellow), fog / dust / grey shots (sat < 0.16);
- match.dry keeps saturated leaves, greys and haze, never lifts sat past the gold or the hue > 3 deg under it; a result
  that adds neon orange, clip or sat95 is halved, then dropped;
- before apply view every sheet `.work/grade/<project>/dry_preview_N.jpg`.

**After apply** ALWAYS look at >= 12 real frames spread over the film + any shot the user named before reporting
(africa_1: match.py broke shots the numbers called fine). A shot still off: tell the user, fix that one shot.

## Heavy scene match `scripts/match.py` (ONLY when the user names it; africa_1 2026-10-22 it broke shots)
Per-shot CDL + match LUT toward one hero per scene (scenes never cross a `# STORY`). Commands and flow in the match.py
docstring: `plan` (background) -> show heroes.jpg -> user "yes" -> `apply` -> `verify`; `note <tc> k=v` overrides
survive re-plans. `grade.py` (balance only, CDL per light group) is the solver match.py builds on; alone only if asked.
Not scriptable: curves, qualifiers, windows, Hue vs Sat, Color Warper -> tell the user node + values.

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

## Grading advice format
Observation (numbers / what you see) -> action in Resolve (palette, control, starting value, node) -> why ->
alternative (different look) + trade-off -> what to check on neighbouring shots.
