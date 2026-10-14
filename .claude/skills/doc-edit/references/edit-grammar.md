# Edit grammar (doc-edit step 2)

## Shots
- Opening shot (user rule 2026-10-13): the first footage shot of "Edit" is a landscape (`sp=none size=wide` or
  `aerial`, `real` preferred), held only 3-4 s, a little longer than every other intro shot (e.g. 3.5 s, then
  1.8-3 s). plan.py rejects anything else. A GFX title before it is allowed.
- Continuity from the screenplay: same individuals, positions, travel direction, setting across a story.
- Order inside a beat: establishing -> subject -> object/reaction -> atmosphere -> payoff.
- Change shot size between adjacent shots; keep screen direction; day/night and light progression match the
  sentence and the screenplay's time of day.
- The picture shows what the sentence names (species, count, action). Abstract sentence -> show the story's main
  character in context (resting, watching, moving through its habitat), not scenery.
- Picture + narrator together tell the gist: the viewer roughly follows who is doing what, the voice fills in
  the details. Not every word needs its own shot; the shots under a sentence stay on its subject and its
  general action (a jaguar sentence shows the jaguar, ideally doing something close to what is said).
  Side shots go in pauses (VO ● empty in plan.md) or under scenic sentences.
- Each story opens with a wide that says where we are and who is there, then closes in; a new character is
  introduced alone, clearly framed, before it interacts. Cause before effect: predator sees -> stalks -> prey
  reacts -> strike -> outcome, never the outcome first.
- Missing the right clip: THIẾU (red marker, user generates it) beats a wrong animal; plan.py never puts a side
  shot fallback under narration.

## Visual thinking (learned from WILD JAVARÍ, Nature's Tether, 2026-10-13)
Before writing a sentence's shots decide, in this order: emotional tone (calm / tense / urgent) -> focal point
(what the eye must land on: the eyes, a paw on a branch, the water surface, the coil) -> light. The shot text and
filter follow from these three, not from the nouns of the sentence alone.
- Scale ladder per beat: establish (`size=aerial,wide`: where, how hostile) -> context (`medium`: the animal in
  its place) -> tension (`close_up`: eye, step, breath) -> impact (`extreme_close`: claws, teeth, scales, the bite)
  on the strike. Not every beat climbs all four, but a strike without its close/extreme_close detail feels empty.
- Angle carries meaning (`ang`): `low` = power, menace, the hero ruling its place; `top_down` (or `aerial`) =
  vastness, loneliness, the animal small in its world; `high` = vulnerability (prey, the ambushed hero);
  `eye` = intimacy, the animal's point of view.
- The viewer knows first: when danger comes for the hero, show the hidden threat (snake in the foliage above,
  dark shape under the water) before the hero notices it: threat -> hero resting, unaware -> strike. The gap
  between the two is the suspense.
- Stillness before the strike: one held shot 2.5-4 s (eyes locked, crouch, coiled body, `cam=static`), then the
  burst of short cuts. The hold is what makes the burst hit.
- Standoff without a fight (two apex predators meet): alternating eye close-ups held 2.5-4 s, then the one
  backing off in a readable medium. Nothing strikes -> no hit SXF, tension comes from length and silence.
- Reversal (hunter becomes hunted): the hero's power shots (`ang=low`) earlier in the film pay off when the
  same animal is shot `ang=high` / tight and trapped; then `ang=low` again when it fights back.
- Dark animals (black jaguar, panther): prefer dappled light and shade where the body emerges from shadow
  (`kw=shadow` / `kw=sunlight` when the captions use them); never a flat, evenly lit frame for the hero's intro.

## Rhythm - shot length follows the story's emotion, never a metronome
Lengths 1.2-6 s. Decide each length from what the moment feels like, then mix:
- Short 1.2-2 s: tension, danger, chase, fight, quick reactions, a list of things ("ăn quả, bắt côn trùng...").
  Cut shorter and shorter as tension rises (3.0 -> 2.2 -> 1.6 -> 1.3), then release.
- Medium 2-3 s: ordinary narration, showing what the sentence names.
- Long 3.5-6 s: establishing a new place, majestic/calm moments, an emotional beat (mother and young, loss,
  rest after the chase), a reveal, the payoff of a sequence. The shot right after a climax is long: let it breathe.
- A long sentence is not split evenly: e.g. 3.8 + 1.7 + 2.3, not 2.6 + 2.6 + 2.6. A pause > 6 s is a short
  sequence (e.g. 1.6 + 2.0 + 4.0), not one held shot.
- plan.py checks: no shot outside 1.2-6 s, no 4 shots in a row within 0.4 s of each other, >= 25% shots <= 2 s
  and >= 10% shots >= 3.5 s. Aim higher than the minimum where the story allows.

## Side shots (scenery, birds, insects, butterfly, frog, others, a friendly non-main species) - seasoning
Side shot = any footage shot whose `need` has no `[tag]` of a main character.
- Intro: free, scenery and diversity open the film. Short: 15-30 s, set per video in the spec header
  `# INTRO m:ss` (0:15-0:30, default 0:15); end it where the first story / main character starts.
- After the intro the main characters carry every story: side shots <= 30% of footage time per video and
  clearly less than the characters' screen time in each story.
- Runs: 1 side shot = a cutaway that lets a moment breathe (most common); 2 = a short diversity beat or a
  pause (~4-7 s); 3 = only at a story/location transition or a long pause (> ~7 s), at most once per ~5 min.
  Never 4. Pick the count from the time available: don't stretch 3 side shots over a 4 s pause, don't put
  1 side shot across a 10 s transition.
- Spread them: diversity beats land at transitions and quiet moments, not in the middle of a chase/hunt.
- Variety: one landscape + one creature beats three landscapes; don't repeat the same kind back to back.
- plan.py rejects a spec that breaks the share / run rules; its THIẾU fallback only adds side shots inside the
  budget and never makes a run longer than 2.

## Source
- Write `any` by default: plan.py takes real footage whenever it fits OK and AI only where real cannot fill the
  shot. `ai` only for what real footage cannot have (two species in one frame, specific interaction); `real`
  only when an AI look would hurt (hero wide, aerial).
- Real next to AI is fine: the grade makes them one place and moment. Keep the same individual's look
  (size, markings, setting) consistent across the cut.
- Reuse: clips on "Edit" + "Open" of the last 4 checked videos of the same workspace are never used. Inside one video a clip may serve up to 3 slots,
  >= 2 min apart, each from a different part of the clip (plan.md marks it ↻2 / ↻3); fresh clips win first.
- `GFX` = black / title / map, no footage.

## Shot text (`need`)
Vietnamese, one line: subject + action + shot size + setting + light. It is what the user reads and the
note of the red THIẾU marker, so it must be enough to generate/shoot the missing clip.
Prefix the main characters with a short tag defined in the spec header (e.g. `[D]` duiker, `[GC]` golden cat)
so missing footage groups cleanly. Every shot of a main character (and of a predator/prey that drives its story)
carries the tag: plan.py counts untagged footage shots as side shots.

## Filter column (matched by plan.py against the vision tags, no tokens)
`k=v1,v2` tokens, `_` = space. Only `sp` and night/not-night are hard; the rest rank candidates.
- `sp` species, lowercase singular common name (`sp=golden_cat`, `sp=elephant`); `sp=none` = no animal
  (landscape/atmosphere). Missing species are listed by the script -> those slots become THIẾU.
- `act`: walk look none rest perch eat swim fly run call climb groom drink play hang sleep stalk carry_young
  jump feed fight attack hunt
- `size`: extreme_close close_up medium wide aerial
- `light`: day golden dusk night
- `set`: forest forest_floor canopy river undergrowth riverbank sky swamp grassland rock underwater lake
  mountain waterfall cave village
- `mood`: calm majestic dramatic eerie playful tense · `cam`: static moving · `dir`: left right toward away none
- `ang`: eye low high top_down (meaning: see Visual thinking)
- `count`: one two few many none · `kw`: words expected in the English caption (`kw=fallen_log,mist`)
- `no=<species or caption word>` hard-excludes clips (e.g. `no=jaguar,caiman` so multi-species AI clips don't leak
  one story thread into another; `no=autumn,conifer` keeps temperate scenery out). Pin fragments: no `_` (= space).
- `pin=<path fragment>` forces a clip; `pin=none` forces THIẾU.
Give 2-4 tokens per shot; over-filtering pushes good clips to WEAK.

## Audio column (track layout in SKILL.md; never A2)
`A<n>=kw1,kw2` tokens, English keywords matched against the audio file/folder names (library has no tags yet).
- A3 (or A4): bed change, e.g. `A3=forest`, `A3=night,crickets`. The bed runs and crossfades A3/A4 by
  itself until the next A3 entry; write it only where location / time of day changes.
- A5: extra environment layer (`A5=water`, `A5=rain`, `A5=wind`), runs until the next A5 entry or `A5=off`.
- A6: natural sound of what is on screen, this slot only (`A6=birds`, `A6=leaves`).
- A7: music cue, plays once from this slot until the next A7 entry, `A7=off`, or file end. Library mood:
  `calm` (gentle, peaceful), `neutral`/`observe`, `mystery`/`wonder`/`explore`, `tense`/`danger`/`stalk`,
  `chase`/`action`/`epic` (licensed music in Z:\Unseen\Sound, by mood folder) plus the older `tense` tracks.
  Folder `opening` is reserved for timeline "Open", never used here.
- Keywords that exist (others come back as audio THIẾU): beds/layers `forest`, `birds`, `insects`, `crickets`,
  `night`, `water`, `stream`, `rain`, `wind`, `thunder`, `fire`; animal foley `breathing`, `growl`, `attack`,
  `footsteps`, `run`, `grass`, `rustle`, `drinking`, `lapping`, `eating`, `bite`, `bone`, `splash`, `swim`,
  `underwater`, `wings`; species `crocodile`/`caiman`, `eagle`, `snake`, `bird`, `big_cat` (leopard, cheetah),
  `lion`, `elephant`, `hyena`, `hippo`; SXF `hit`, `impact`, `whoosh`, `riser`, `heartbeat`, `drop`.
- A8/A9: SFX hit at the slot start (`A8=branch,snap`, `A8=thunder`); busy A8 -> A9 automatically.
- A6/A8/A9 never substitute: every keyword must be in the file name, and a file naming an animal is used only on
  a slot of that species or its relative (KIN in plan.py). Otherwise the cue is audio THIẾU: list it in the plan
  reply (slot, timecode, sound needed). The user downloads a fitting file (rescan, re-plan) or says no -> delete
  that token from the spec, no SFX there.
- Empty = nothing new on that slot.

## Sound that moves the viewer
Plan the audio column per story, before the per-shot details: what must the viewer feel at its start, peak, end?
- Music carries emotion: one A7 cue per story beat (opening wonder, tension, chase, aftermath, resolution), never
  the same track twice in a row. Target music under 60-85% of the film; the rest is deliberate silence of music,
  not forgotten gaps. plan.py picks the track that lasts until the next A7 entry; the `audio:` line reports
  coverage and cues ending > 3 s early (add an A7 entry there or move the `off`).
- Silence before the strike: `A7=off` 1-3 s before an attack / reveal / fall, bed and natural sound only, then
  the hit on the strike slot (`A8=hit` or `impact`, `A9=whoosh` on fast movement), then a new calm or sad cue on
  the long shot after the climax. Rising tension = `A8=riser` 2-4 s before the peak.
- SXF only on state changes (danger appears, strike, escape, fall, splash, reveal): ~1 per 30-60 s in calm
  parts, denser in action; never on a narrated line that does not change anything.
- Natural sound makes the picture real: A6 on every on-screen action with a sound (breathing on a close-up,
  footsteps/rustle on a walk, lapping on drinking, bite/bone on feeding, splash on water entry, wings on take-off).
- Species voices only from the species or a close relative, named in the shot text: leopard/cheetah growl or
  attack for a jaguar/puma, crocodile for a caiman, eagle for a harpy eagle. Never an unrelated animal's voice
  (no lion roar on a monkey); no relative in the library -> breathing/foley only, report the voice as missing.
- Beds: A3 change at every location / time-of-day change (`A3=night,insects` at dusk); A5 water/rain layer
  when water or rain is on screen.
