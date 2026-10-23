# Edit grammar (doc-edit plan)

## Shots
- Opening shot, two forms (spec header `# OPENING landscape|action`, default landscape = every video before):
  `landscape` (user rule 2026-10-13): `sp=none size=wide|aerial`, `real` preferred, held 3-4 s, a little longer than
  every other intro shot. `action`: the first shot is a real event on screen (`sp=<animal>` + `act=run|fight|attack|
  hunt|stalk|jump`), and a wide / medium / aerial shot with an animal that says who is where starts within 20 s.
  plan.py rejects anything else. A GFX title before either is allowed.
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

## Opening 0:00-1:30 and story 1: the hook (user 2026-10-17, widened 2026-10-21)
Biome tuning (savanna / rainforest, ordering of beats, pauses, 2-3 small examples): `references/biome-story-pacing.md`.
Spec headers (all optional): `# INTRO 1:30` (0:15-2:00; > 0:30 needs >= 50% of the intro on `[tag]` character shots),
`# OPENING action`, `# BIOME savanna|rainforest`, `# FAST_UNTIL m:ss` (story cue for the hook + first two stories, no
cut-rate rule), `# STORY n m:ss` (chapter starts, rising, inside END, STORY 1 at/after INTRO, never inside a voice cue),
`# TURN` under a `## N` where the advantage really changes (counted in the chapter report).
The first 90 s decide whether the viewer stays, story 1 whether they finish. Plan the opening as ONE micro-story with
cause and effect, not a reel of unrelated attacks: place + threat -> one animal with a concrete cost -> a change of
advantage -> a consequence that hands an open question to story 1. Find these beats in the screenplay's opening;
the clock is a frame, the screenplay's events win (a contact written at 0:38 stays at 0:38, cause before effect).

| ~time | function | picture | narrator |
|---|---|---|---|
| 0:00-0:12 | the disturbance has begun | (`landscape` form: after the 3-4 s landscape; `action` form: from frame 1) prey turns, predator accelerates, an alarm with a visible reaction, a standoff already open | one line of risk, then the action shows itself |
| 0:12-0:30 | geography of the encounter | medium / wide with both sides, the obstacle, the way out | only what cannot be seen |
| 0:30-0:55 | escalation | one continuous action: stalk -> spot -> lunge / run, or holding prey -> rival closes in | silent on the clearest lunge / contact |
| 0:55-1:12 | reversal / near result | prey escapes, hunter misses, short struggle, the weaker one takes the place | names what changed |
| 1:12-1:30 | consequence + bridge | reaction, lost prey, a new path, a danger still open | the big question, into story 1 |

- `# INTRO` (beat cuts) is the micro-story's first beat, not a scenery reel: landscape opening shot, then the threat
  on tagged character shots by ~0:10-0:15; at most 1-2 other side shots inside it. Its A7 cue sits on the first shot
  (tense / epic with hits); plan.py snaps every intro cut onto it (hit B3+ within 0.45 s, else bar, else beat within
  0.25 s; `intro beat:` line): write varied durations (short on the build, the bigger image on the bigger hit). `action` opening: if it starts at
  the point of conflict, step back in time with a clear transition (never pretend one continuous take), and show the
  placing wide by 10-20 s. Slow motion only when the real clip has the frames and it helps read the action; show it
  once at normal speed too.
- Intro footage = highlights of the later stories (user 2026-10-22, africa_1): plan.py `highlights()` gives every
  intro shot with an animal the frames of a later OK story shot of the same species (chase / fight first, >= 5 min
  later, the line's `no=` + no carcass / meal, same-frame cap 3), played at 136-150 %; scenery intro shots keep their
  own clip. plan.md marks them `★#<slot>`. Re-cut only the intro: delete V1/A1 items before 1:30 (user yes, backup),
  then `place.py <video> --fill --until 90`. Epic intro, no empty slot (user 2026-10-22): `split_intro()` cuts every
  animal intro shot into 1.0-2.2 s pieces on music hits / bars / beats; a species without later footage takes a
  related species' chase (KIN class), then any chase / fight. Lines with a calm act (look / rest) keep calm footage.
- Intro ends with its music (user 2026-10-22): `intro_outro()` makes the last 4 s before the intro music's end one
  landscape fading to black (1.5 s, place.py `SetFades`); story 1's first shot (write it as a landscape, sp=none)
  starts at the music end and fades in from black (2.5 s). Intro shots after that point are dropped (their A7 'off'
  too); the A7 intro music must play from its file start (africa_1 had a 34-frame head trim: beats + end were off).
- Leave one stretch without narration so the viewer hears real movement. Test the hook muted (geography is clear)
  and with eyes closed (the sound means something). plan.py prints a hook hypothesis, not a retention KPI: measure
  retention after publishing.
- One event, one place: same individuals and count, same site, time of day, light and screen direction for the 90 s
  (same `dir` / `light` tokens on its shots). Never cut two hunts, species or sites into one claimed event; a
  clip whose action exists only in the caption is not the action.
- Clip picks here are stricter (the viewer must read who does what to whom; strikes read from medium / wide, see
  Visual thinking). Hard reject: wrong species / forest, action not visible, facing
  directions that cannot cut together, count changes without a bridge, AI anatomy errors or bodies passing through
  things. Violence is no bonus without a story role; no gore, don't hold on biting.
- No chase / fight footage of the species -> a credible approach, alarm, retreat or contested resource on screen,
  the missing action as THIẾU (the user generates it); never another animal standing in.
- VO-free windows (VO ● empty in the opening) carry the decisive movement on character shots, never side shots.
  One quiet reaction / aftermath shot (3.5-5 s) after each result makes the next escalation hit.
- Sound: music curve per beat (Sound that moves the viewer): A6 natural first, music rises when a choice turns
  dangerous, drops out only where hearing the contact helps; A8/A9 on changes of advantage, never on every cut.
- Mute test, from plan.md's shot texts alone: at 0:30, 1:00 and 1:30 a stranger can name the subject, the obstacle,
  the event, the outcome and what is still open. "Many animals fighting" -> reorder, add a positioning wide, or drop
  an encounter.
- Story 1 (the main emotional entry, often ~6 min): protagonist, goal, obstacle, place, action, result, consequence
  each visible in some shot; side shots only as cutaways in its pauses; a quiet beat before every escalation; it ends
  on a meaningful visible result (catch, escape, loss, the young safe) held on a long aftermath shot, never on a
  scenery fade.

## Visual thinking (learned from WILD JAVARÍ, Nature's Tether, 2026-10-13)
Before writing a sentence's shots decide, in this order: emotional tone (calm / tense / urgent) -> focal point
(what the eye must land on: the eyes, a paw on a branch, the water surface, the coil) -> light. The shot text and
filter follow from these three, not from the nouns of the sentence alone.
- Scale ladder per beat: establish (`size=aerial,wide`: where, how hostile) -> context (`medium`: the animal in
  its place) -> tension (`close_up`: eye, step, breath) -> impact. Not every beat climbs all four. A strike reads from
  medium / wide (distance, direction, rival, way out); `extreme_close` (claws, teeth) is an accent only when the
  footage has it, never a requirement.
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
Lengths mostly 1.2-6 s (a hold longer or a flash shorter is a story choice: only < 0.8 s or > 10 s is an error).
Decide each length from what the moment feels like, then mix:
- Short 1.2-2 s: tension, danger, chase, fight, quick reactions, a list of things ("ăn quả, bắt côn trùng...").
  Cut shorter and shorter as tension rises (3.0 -> 2.2 -> 1.6 -> 1.3), then release.
- Medium 2-3 s: ordinary narration, showing what the sentence names.
- Long 3.5-6 s: establishing a new place, majestic/calm moments, an emotional beat (mother and young, loss,
  rest after the chase), a reveal, the payoff of a sequence. The shot right after a climax is long: let it breathe.
- A long sentence is not split evenly: e.g. 3.8 + 1.7 + 2.3, not 2.6 + 2.6 + 2.6. A pause > 6 s is a short
  sequence (e.g. 1.6 + 2.0 + 4.0), not one held shot.
- plan.py: errors only for shots < 0.8 s or > 10 s; warnings for shots outside 1.2-6 s and 4 shots in a row within
  0.4 s; no film-wide quota. The reply gives per-chapter numbers (HOOK / STORY n: shots, <=2 s and >=3.5 s share,
  side time, THIẾU, marked `# TURN`s); judge each chapter by its job: action cuts fast, waiting and consequence hold.

## Side shots (scenery, birds, insects, butterfly, frog, others, a friendly non-main species) - seasoning
Side shot = any footage shot whose `need` has no `[tag]` of a main character.
- Side shots inside the intro are not counted (rules in the Opening section). After the intro the main characters carry every story: side shots <= 30% of footage time per video and
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
- Reuse: clips on "Edit" + "Open" of the last 6 checked videos of the same workspace are never used. Inside one video
  (user 2026-10-22: save source, not too often, not too rarely) a clip may serve up to 6 slots, >= 90 s apart: another
  part of the clip first, else the same frames again, but no frame on screen more than 3 times and those repeats >= 5
  min apart (plan.md ↻n, `=frame`); fresh clips still win at similar fit. Parts already on "Open" never come back.
- Zoom + speed (user 2026-10-22, plan.py `vary`, place.py applies, plan.md ⏱ / 🔍): real clips shot above 25 fps
  play frame-exact at 24/fps (30 fps = 80 %) except on strikes and in the hook; true slow motion (<= 50 %, 50/60 fps
  sources) only on calm holds >= 3 s, one per 20 s; aerial scenery every 2nd at 120 %. Punch-in 1.12-1.25 on 4K
  sources, never on close-ups: every other reuse, every same-frame repeat, every 5th fresh shot.
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
