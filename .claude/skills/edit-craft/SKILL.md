---
name: edit-craft
description: Documentary editing craft in Resolve - narration-led pacing, cut points, J/L cuts, transitions, predator/survival sequences, YouTube retention, Edit-page trim tools, YouTube render settings. Use when the user asks how to cut, order, time or improve a sequence, whether it feels slow/fast/confusing, which transition, or how to export.
---

# Edit craft (natural-history documentary)

Export settings: `references/delivery.md`.

## Narration-led edit
1. VO sits on A2 (vo-sync). Picture serves it: show what the line is about when it is said or just before (the image
   prompts the word); never contradict it.
2. Let lines breathe: after a revelation or strike, 1-3 s without narration; picture and effects carry it. Silence is
   a tool.
3. Pictures that explain need time, pictures that excite need little: a line introducing a new animal needs a readable
   shot (wide / medium, 3-5 s), not a fast montage.

## Shot length (starting points at 24 fps; adapt to content)
| shot | typical hold |
|---|---|
| establishing wide / landscape | 4-7 s |
| medium of animal behaviour | 2.5-5 s |
| close-up / detail (eye, claw, feather) | 1.5-3 s |
| action peak / chase | 0.5-1.5 s per cut |
| reaction / aftermath | longer than feels safe (3-6 s) |
Vary lengths (identical durations = mechanical rhythm). Accelerate toward a climax, then release with one long hold.

## Predator / survival sequence
Establish (where, who) -> prey (vulnerability) -> predator (threat, its eye) -> stalk (alternate POVs, tightening
framing, slower cutting, sound drops) -> trigger (one detail: a twitch, a snapped twig) -> strike / chase (fast cutting)
-> outcome (clear, readable shot) -> aftermath (long hold, quiet). Cross-cutting predator <-> prey builds suspense;
keep each side's screen direction consistent (e.g. predator always left-to-right).

## Reference film: WILD JAVARÍ (Nature's Tether, 2.8M views in 7 days), shape for a ~30 min single-hero film
1. Cold open on the climax image (black jaguar in the anaconda's coil) + title card, no outcome: the question is
   planted in seconds. This belongs to timeline "Open", never "Edit".
2. Place + hero: aerial over the valley, the hero emerging from shade; narration claims his power in three realms
   (ground, water, trees), foreshadows "another hunter is waiting".
3. Skill showcase: a hunt in his strongest place (canopy): stillness before the spring, fast burst, prey scatters.
4. Limit: a standoff with an equal (caiman) that ends without a fight; held eye-to-eye shots, he backs away.
5. Reversal: in his safe place the viewer sees the threat above him first; ambush; hunter becomes hunted.
6. Turn + lesson: he fights back face to face, escapes, long hold over the canopy; the closing line is the theme.
Each act is a mini-climax; per-beat visual grammar: doc-edit `references/edit-grammar.md` ("Visual thinking").

## Cut points
- On action: start a movement in shot A, finish it in B; the motion hides the cut.
- On the eyes: an off-screen look motivates the next shot (what it sees).
- On sound: a call, splash, impact or music downbeat.
- No cut between two shots of the same subject at nearly the same size and angle (jump cut), unless deliberate time
  compression.
- AI clips: the first and last ~0.5-1 s often drift or morph: use the clean middle; check climax frames one by one
  for anatomy errors.

## Sound-led editing
- J-cut: next shot's sound starts before its picture (pulls forward). L-cut: current sound continues over the next
  picture (smooth, reflective).
- The ambience bed runs across picture cuts within a location (hides AI-clip joins); change it only with location /
  time.

## Transitions
Hard cut by default. Cross dissolve: time passing or place change within a mood, 12-36 frames. Dip to black: chapter
end or a death / turning point, 12-24 frames out + in. No flashy wipes, zooms or glitch transitions.

## YouTube retention (craft, not tricks)
- Hook in the first 15-30 s: the central question or danger, a strong image, no logos / intros first.
- Open loops: pose a question, delay the answer, pay it off.
- Visual change every few seconds in narration-heavy parts: vary scale (wide / medium / close) and direction.
- Chapters with a mini-climax every few minutes; trim anything that repeats information.
- Never so fast the animal doesn't register: confusion loses viewers faster than slowness.

## Resolve Edit page
- A = Selection, B = Blade edit mode, T = Trim edit mode; Ctrl+B or Ctrl+\ splits at the playhead; N = snapping.
- Ripple: move an edge and everything after. Roll: move a cut between two clips (length unchanged). Slip: change the
  source part, same position + length. Slide: move a clip between neighbours, they adjust.
- Dynamic trim (W in trim) trims while playing (J/K/L).
- Linked selection off for J/L cuts (audio stops following video).
- Compound clips = a built moment as one clip; adjustment clips = an effect / grade over the tracks below.
- Markers and Edit Index for notes; "Find in media pool" to locate sources.
- Timeline > Detect Scene Cuts splits a pre-assembled file; Smart Reframe (Studio) for reframing.

## Edit feedback
Timecode -> the problem in viewer terms ("we don't see the prey before the strike") -> concrete fix (trim 12 frames
from the head of shot X, swap shots, add a 2 s hold) -> an alternative with its trade-off.
