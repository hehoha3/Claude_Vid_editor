---
name: edit-craft
description: Documentary editing craft in DaVinci Resolve - narration-led cutting, pacing and rhythm, shot length, cut points, J/L cuts, transitions, sequence building for predator/survival stories, YouTube retention, Resolve Edit-page tools (blade, ripple, roll, slip, slide, trim mode, compound and adjustment clips), and render/delivery settings for YouTube. Use whenever the user asks how to cut, order, time or improve a sequence, whether something feels slow/fast/confusing, which transition to use, or how to export.
---

# Edit craft (natural-history documentary)

For export settings read `references/delivery.md`.

## The narration-led edit
1. VO sits on A4 (vo-sync). Picture is cut to serve it: the image should show what the line is
   about at the moment it is said, or just before (the image prompts the word). Never contradict it.
2. Let lines breathe: after a revelation or a strike, leave 1-3 s without narration; picture and
   sound effects carry it. Silence is a tool.
3. Pictures that explain need time; pictures that excite need little. A line that introduces a new
   animal needs a readable shot (wide/medium, 3-5 s), not a fast montage.

## Shot length (starting points at 24 fps; adapt to content)
| shot | typical hold |
|---|---|
| establishing wide / landscape | 4-7 s |
| medium of animal behaviour | 2.5-5 s |
| close-up / detail (eye, claw, feather) | 1.5-3 s |
| action peak / chase | 0.5-1.5 s per cut |
| reaction / aftermath | hold longer than feels safe (3-6 s) |
Vary lengths: identical durations create a mechanical rhythm. Accelerate toward a climax
(shorter and shorter), then release with one long hold.

## Building a predator/survival sequence
Establish (where, who) -> introduce prey (vulnerability) -> introduce predator (threat, its eye) ->
stalk (alternate POVs, tightening framing, slower cutting, sound drops) -> trigger (one detail: a
twitch, a snapped twig) -> strike/chase (fast cutting, screen direction consistent) -> outcome
(clear, readable shot) -> aftermath (long hold, quiet). Cross-cutting predator <-> prey builds
suspense; keep each side's screen direction consistent (predator always moving left-to-right, say).

## Cut points
- Cut on action: start a movement in shot A, finish it in shot B; the motion hides the cut.
- Cut on the eyes: a look off-screen motivates the next shot (what it sees).
- Cut on sound: a call, splash or impact is a natural cut point; music downbeats too.
- Avoid cutting between two shots of the same subject at nearly the same size and angle
  (jump cut) unless used deliberately for time compression.
- AI clips: the first and last ~0.5-1 s often contain settling drift or morphing - use the clean
  middle; check the climax frames one by one for anatomy errors.

## Sound-led editing
- J-cut: next shot's sound starts before its picture (pulls the viewer forward).
- L-cut: current shot's sound continues over the next picture (smooth, reflective).
- Ambience bed runs continuously across picture cuts within a location to hide the joins between
  AI clips; change ambience only when location/time changes.

## Transitions
- Hard cut by default.
- Cross dissolve: time passing or place change within a mood, 12-36 frames.
- Dip to black: chapter end or a death/turning point, 12-24 frames out + in.
- Avoid flashy wipes, zooms and glitch transitions in natural history.

## YouTube retention (craft, not tricks)
- Hook in the first 15-30 s: the central question or danger, a strong image, no logos/intros first.
- Open loops: pose a question, delay the answer, pay it off.
- Visual change: a new image or new framing every few seconds during narration-heavy parts; vary
  scale (wide/medium/close) and direction.
- Chapter structure with a mini-climax every few minutes; trim anything that repeats information.
- Do not cut so fast that the animal never registers; confusion loses viewers faster than slowness.

## Resolve Edit page essentials
- Modes: A = Selection, B = Blade edit mode, T = Trim edit mode. Ctrl+B or Ctrl+\ splits at the
  playhead. N toggles snapping.
- Ripple trim: change an edge and move everything after it. Roll: move a cut point between two
  clips (total length unchanged). Slip: change which part of the source is shown, same position and
  length. Slide: move a clip between its neighbours, neighbours adjust.
- Dynamic trim mode (W in trim) lets you trim while playing (J/K/L).
- Linked selection on/off controls whether audio follows video; turn it off for J/L cuts.
- Compound clips to treat a built moment as one clip; adjustment clips to apply an effect or grade
  over many clips on the tracks below.
- Markers and Edit Index to keep notes; "Find in media pool" to locate sources.
- Timeline > Detect Scene Cuts to split a pre-assembled file; Smart Reframe (Studio) for reframing.

## Giving edit feedback
Name the timecode, the problem in viewer terms ("we don't see the prey before the strike"), the
fix (concrete: trim 12 frames from the head of shot X, swap shots, add a 2 s hold), and an
alternative with its trade-off.
