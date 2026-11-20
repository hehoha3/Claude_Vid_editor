# Edit grammar (doc-edit plan)

## Story first
Film -> story -> beat -> shots -> footage. First: what the film asks, the story's place / season / cast / outcome, the
beat's job; narrator nouns last. Conflicts: `screenplay boundaries > what the footage visibly shows > subject + event
continuity > beat intent > narrator words > beauty`. Story truth = filter tokens (machine-checked, score never rescues):
- cast: `sex=female` (lioness, mother) / `age=young` (calf, cub) on every line of that animal; other sex / age refused;
  unseen sex max WEAK + "kiểm tra".
- state: stalk / hunt / run / fight line never takes a rest / sleep-only clip; `xact=rest,sleep,eat` for more.
- outcome: catch / kill / carcass refused unless `out=kill` (kill on screen per screenplay) or `act=eat` (meal at
  another time). Near miss / hidden / unknown end = no `out`.
- place / time: `# STORY n m:ss no=river,crocodile` = what that story never shows.
- identity: each story's animal is representative unless the screenplay says same one; no match cut / reused clip
  claiming a later story's animal is the earlier one.
- no fitting clip = THIẾU (row + red marker list refusals: `loại: sex 8, kill 2`); fix the filter only if the refusal
  was wrong, never loosen it to fill.

## Shots
- Impact: if intro.py picked one, plan.py puts black 0:00 -> the hit (~1 s, GFX, A9 riser -> impact); opener cuts in on
  the hit with intro music; narrator still at 0:03.6.
- Opener: narrator at 0:03.6; plan.py puts one epic shot alone on 0:00 -> sentence 1 (landscape / sun / wide sky:
  default `sp=none size=wide,aerial`); ## 1's beds / music start under it. Rare character open:
  `# OPENER Cận mắt báo đốm | real | sp=jaguar size=extreme_close` (face / eye / mouth; no zoom unless real-lens look).
  Forms below start after it; ## 1 needs no own landscape.
- `# OPENING landscape|action` (default landscape). `landscape`: `sp=none size=wide|aerial`, `real` preferred, 3-4 s,
  longer than every other intro shot. `action`: first shot = real event (`sp=<animal>` +
  `act=run|fight|attack|hunt|stalk|jump`); a wide / medium / aerial placing the animal within 20 s. plan.py rejects
  else. GFX title before either OK.
- Per story same individuals, positions, travel direction, setting. Beat order: establishing -> subject ->
  object/reaction -> atmosphere -> payoff. Change size between adjacent shots; keep screen direction; day/night + light
  match sentence and screenplay time.
- Picture shows what the sentence names (species, count, action); abstract sentence -> main character in its habitat,
  not scenery. Picture + narrator give the gist together; shots stay on the sentence's subject and action. Side shots
  in pauses (VO ● empty) or under scenic sentences.
- Story opens wide (where, who), then closes in; new character alone, clearly framed, before interacting. Cause before
  effect: predator sees -> stalks -> prey reacts -> strike -> outcome.
- THIẾU beats a wrong animal; plan.py never puts a side shot fallback under narration.

## Opening 0:00-1:30 and story 1: the hook
Biome tuning: `references/biome-story-pacing.md`. Headers (optional): `# INTRO 1:30` (0:15-2:00; > 0:30 needs >= 50%
of intro on `[tag]` shots), `# OPENING action`, `# BIOME savanna|rainforest`, `# FAST_UNTIL m:ss` (cue for hook + first
two stories, no cut-rate rule), `# STORY n m:ss` (rising, inside END, STORY 1 at/after INTRO, never inside a voice cue),
`# TURN` under a `## N` where advantage really changes. First 90 s = stay or leave; story 1 = finish or not.
Before intro shot lines write `# HOOK` lines atop part 01 (else `hook blueprint: MISSING` for intro > 0:30):

    # HOOK form: teaser | micro-story      promise: what the viewer must want to know at 1:30
    # HOOK anchor: herd > mother > calf      vulnerable: the calf, slow legs
    # HOOK threats: lioness > hyena > Mara water (rising, each a preview)
    # HOOK motif: herd moving, the gap     reset: 1:30 back to the southern plains, before the birth
    # HOOK never: a kill, the calf crossing the river

Form from the screenplay's opening (visual directions too):
- `micro-story`: ONE event: place + threat -> one animal, concrete cost -> advantage change -> consequence = open
  question into story 1. All 90 s: same individuals + count, site, time, light, direction (same `dir` / `light`).
- `teaser`: anchor (one subject) between previews of later threats, each its own place / time (`teaser_preview`):
  light / scale / bed change between; no match cut or reaction making a threat act on the anchor; no outcome, no ending.
- Both: never cut two hunts / species / sites into one claimed event; caption-only action is not the action.
Screenplay events win over the clock (contact at 0:38 stays 0:38). End on `reset`: story 1 reads earlier / elsewhere.
Guide: 0:00-0:12 disturbance begun (`landscape` after its 3-4 s, `action` from frame 1; VO one risk line) · 0:12-0:30
geography: both sides, obstacle, way out (VO only the unseen) · 0:30-0:55 one continuous escalation, stalk -> spot ->
lunge / run (VO silent on the clearest contact) · 0:55-1:12 reversal / near result (VO names the change) · 1:12-1:30
consequence + bridge, danger open (VO the big question).
- `# INTRO` = micro-story's first beat, not scenery: landscape, then threat on tagged shots by ~0:10-0:15; max 1-2 side
  shots. A7 cue (tense / epic) on its first shot; plan.py snaps intro cuts (hit B3+ within 0.45 s, else bar, else beat
  within 0.25 s; `intro beat:` line): vary durations (short on build, big image on big hit).
- `action` opening at the conflict: step back with a clear transition (no fake continuous take); placing wide by 10-20
  s. Slow motion only from real high-fps frames that help reading; also once at normal speed.
- Highlights: `highlights()` gives each animal intro shot frames of a later OK story shot, same species (chase / fight
  first, >= 5 min later, line's `no=` / `sex=` / `age=`, no carcass / meal / kill, same-frame cap 3) at 136-150 %;
  scenery keeps its clip; plan.md `★#<slot>`. Intro-only re-cut: delete V1/A1 before 1:30 (user yes, backup), then
  `place.py <video> --fill --until 90`. `split_intro()` cuts animal intro shots to 1.0-2.2 s on hits / bars / beats.
  No later footage -> own pick or THIẾU (no related / other species).
- Action zone: all intro shots but first `HL_HEAD` = 5 (set-up, 3-7) and last `HL_TAIL` = 2 (outro landscapes) show a
  chase / fight / climax of the line's species (later story shots or library clips with it as main species; chase /
  fight first, then tense / dramatic; clip <= 3x, other frames, >= 8 s apart); the line's calm act (look / rest, calm
  footage elsewhere) and a "7. Open" pick yield. `# ACTION 0:29-1:21` = zone as time window; only the intro's own animals
  in frame (no zebra / warthog / wildebeest prey). Line `intro highlights:` = `action zone: N chase/fight + M tense of K`.
  Few action clips -> more lion / predator lines in the zone, or prompts.
- `intro_outro()`: last 4 s before intro music end = one landscape fading to black (1.5 s, place.py `SetFades`); story
  1's first shot (landscape, sp=none) starts 0.6 s after music end (black, story 1's bed pre-laps on A5), fades in 2.5
  s. Later intro shots dropped (their A7 'off' too). Intro A7 plays from file start (a 34-frame head trim broke beats).
- One narration-free stretch with real movement sound. Test muted (geography) and eyes closed (sound). plan.py's hook
  output is a hypothesis, not a retention KPI.
- Hook QC in the reply first: what does the viewer understand / want at 1:30 (`promise`)? Misleading on individual,
  place, hunt result or time order = hard fail: re-plan or THIẾU.
- Hard reject: wrong species / forest, action not visible, facing directions that cannot cut, count change without
  bridge, AI anatomy errors / bodies passing through things. No gore, no holding on biting; violence needs a story role.
- No chase / fight footage -> approach, alarm, retreat or contested resource; the action as THIẾU; never a stand-in.
- VO-free windows: decisive movement on character shots, never side shots. One quiet reaction (3.5-5 s) after each result.
- Sound: A6 first, music rises as danger turns, drops only where the contact should be heard; A8/A9 on advantage
  changes, not every cut.
- Mute test from plan.md texts: at 0:30, 1:00, 1:30 a stranger names subject, obstacle, event, outcome, what is open.
  "Many animals fighting" -> reorder, add a positioning wide, or drop an encounter.
- Story 1 (~6 min): protagonist, goal, obstacle, place, action, result, consequence each visible; side shots only as
  cutaways in pauses; quiet beat before each escalation; ends on a visible result (catch, escape, loss, young safe) on
  a long aftermath shot, never a scenery fade.

## Visual thinking
Per sentence: tone (calm / tense / urgent) -> focal point (eyes, paw, water surface, coil) -> light; then text + filter.
- Scale ladder: `size=aerial,wide` -> `medium` -> `close_up` -> impact (not always all four). Strike from medium /
  wide; `extreme_close` (claws, teeth) only as accent when footage has it.
- `ang`: `low` = power / menace; `top_down` (or `aerial`) = vastness, loneliness; `high` = vulnerability; `eye` =
  intimacy, animal's POV.
- Viewer knows first: hidden threat -> hero unaware -> strike.
- Stillness before strike: one hold 2.5-4 s (`cam=static`, eyes locked, crouch), then short cuts.
- Standoff, no fight: alternating eye close-ups 2.5-4 s, then the one backing off in a medium; no hit SXF.
- Reversal: earlier `ang=low` hero shots pay off as `ang=high` / tight and trapped; `ang=low` again when fighting back.
- Dark animals (black jaguar, panther): dappled light, body out of shadow (`kw=shadow` / `kw=sunlight`); never flat light
  for the hero's intro.

## Rhythm
Length follows emotion, never a metronome. With a beat sheet (new-video.md B2) `story.py expand` applies this and
"Sound that moves the viewer"; raw beats by hand. Mostly 1.2-6 s:
- Short 1.2-2 s: tension, chase, fight, reactions, lists ("ăn quả, bắt côn trùng..."); shrink as tension rises
  (3.0 -> 2.2 -> 1.6 -> 1.3), then release.
- Medium 2-3 s: ordinary narration.
- Long 3.5-6 s: new place, majestic / calm, emotional beat, reveal, payoff; the shot after a climax is long.
- Uneven splits: 3.8 + 1.7 + 2.3, not 2.6 + 2.6 + 2.6. Pause > 6 s = short sequence (1.6 + 2.0 + 4.0).
- plan.py: errors < 0.8 s or > 10 s; warns outside 1.2-6 s and 4 in a row within 0.4 s; no film quota. Reply: per
  chapter (HOOK / STORY n: shots, <=2 s and >=3.5 s share, side time, THIẾU, `# TURN`s); judge by job: action fast,
  waiting / consequence hold.

## Side shots
Side shot = footage whose `need` has no main-character `[tag]` (scenery, birds, insects, frog, friendly non-main species).
- Intro not counted. After it: <= 30% of footage time per video, clearly less than characters' time per story.
- Runs: 1 = cutaway (usual); 2 = diversity beat / pause ~4-7 s; 3 = only at story / location transition or pause > ~7 s,
  max once per ~5 min; never 4. Fit to time (not 3 in a 4 s pause, not 1 across 10 s).
- At transitions / quiet moments, not mid hunt; vary kinds (one landscape + one creature, not three landscapes).
- plan.py rejects share / run breaks; THIẾU fallback adds side shots only in budget, runs <= 2.

## Source
- Default `any` (real when it fits OK, else AI). `ai` only for what real cannot have (two species in frame, specific
  interaction); `real` when AI would hurt (hero wide, aerial). Real next to AI fine; keep the individual's look.
- Reuse: clips on the timeline (older ledgers: + "Open") of the last 6 checked videos of the workspace never in the
  first 15:00, after it any clip under in-video limits. Clip on 0:00-15:00 of the last 9 channel videos (ledger
  `open15`) never before 30:00, loses to fresh after.
- AI <= 40 % of footage time, every region; f_ none (plan.py AI_MAX / vtypes.ai_max; timeline order: intro + story 1
  first, then real only). AI clip on 42 videos (all channels) never planned again (ledger `retire` ->
  `.work/scripts/retire_ai_<date>.ps1`, user runs with -Apply).
- In one video: clip <= 6 slots, >= 90 s apart, other part first; a frame max 3 times, >= 5 min apart (plan.md ↻n,
  `=frame`); fresh wins at similar fit.
- `vary` (place.py applies, plan.md ⏱ / 🔍): real > 25 fps plays at 24/fps (30 fps = 80 %) except strikes and hook;
  true slow motion (<= 50 %, 50/60 fps) only on calm holds >= 3 s, one per 20 s; aerial scenery every 2nd at 120 %.
  Punch-in 1.12-1.25 on 4K, never close-ups: every other reuse, every same-frame repeat, every 5th fresh shot.
- `GFX` = black / title / map, no footage.

## Shot text (`need`)
Vietnamese, one line: subject + action + size + setting + light; doubles as the THIẾU note, so enough to generate /
shoot it. Main characters (and the predator / prey driving a story) carry a header tag (`[D]` duiker, `[GC]` golden
cat) on every shot; untagged footage = side shot.

## Filter column (matched by plan.py against the vision tags, no tokens)
`k=v1,v2`, `_` = space. Hard: `sp`, night/not-night; rest ranks. 2-4 tokens per shot (truth tokens extra, on every
line of that animal); over-filtering -> WEAK.
- `sp` lowercase singular (`sp=golden_cat`, `sp=elephant`); `sp=none` = no animal. Missing species -> THIẾU.
- `act`: walk look none rest perch eat swim fly run call climb groom drink play hang sleep stalk hide carry_young
  jump feed fight attack chase catch (hunt = chase or catch; hide <-> stalk match). Clips with `phase` cut at the act.
- dur `12x4 same` / `*x3 same` = consecutive parts of ONE clip (stalk -> lunge -> miss, plan.md ⛓); too short ->
  separate picks, which are `illustrative`, never a claimed take. Use where one event is claimed.
- `size`: extreme_close close_up medium wide aerial · `light`: day golden dusk night
- `set`: forest forest_floor canopy river undergrowth riverbank sky swamp grassland rock underwater lake mountain
  waterfall cave village
- `mood`: calm majestic dramatic eerie playful tense · `cam`: static moving · `dir`: left right toward away none
- `ang`: eye low high top_down · `count`: one two few many none · `kw`: English caption words (`kw=fallen_log,mist`)
- `no=<species or caption word>` hard-excludes (`no=jaguar,caiman` stops multi-species AI clips leaking between
  stories; `no=autumn,conifer` keeps temperate scenery out). Pin fragments: no `_` (= space).
- `pin=<path fragment>` forces a clip; `pin=none` forces THIẾU.
- Truth (hard): `sex=female|male`, `age=young|adult`, `xact=<actions>`, `out=kill`; `# STORY n m:ss no=...` = story-wide `no=`.
- Within a sentence a moving subject (`act` run / walk / hunt / swim...) keeps the previous `dir` (opposite costs
  0.15); write `dir=` only where the screenplay fixes it.

## Audio column (track layout in SKILL.md; never A2)
`A<n>=kw1,kw2`, English keywords matched against audio file / folder names. Empty = nothing new.
- A3 (or A4): bed change (`A3=forest`, `A3=night,crickets`), crossfades A3/A4 by itself until the next A3; only at
  location / time-of-day change (`A3=night,insects` at dusk).
- A5: layer (`A5=water`, `A5=rain`, `A5=wind`) until next A5 or `A5=off`; water / rain on screen.
- A6: on-screen natural sound, this slot only (`A6=birds`, `A6=leaves`); on every action with a sound (breathing on
  close-up, footsteps / rustle, lapping, bite / bone, splash, wings).
- A7: music once from this slot until next A7, `A7=off` or file end. Moods: `calm` (gentle, peaceful),
  `neutral`/`observe`, `mystery`/`wonder`/`explore`, `tense`/`danger`/`stalk`, `chase`/`action`/`epic` (Epidemic / Suno
  in D:\Audio_lib\music by mood folder) + older `tense`. Folder `opening` reserved (formerly "Open"), never used here.
- A8/A9: SFX at slot start (`A8=branch,snap`, `A8=thunder`); busy A8 -> A9.
- Keywords (others = audio THIẾU): beds `forest`, `birds`, `insects`, `crickets`, `night`, `water`, `stream`, `rain`,
  `wind`, `thunder`, `fire`; foley `breathing`, `growl`, `attack`, `footsteps`, `run`, `grass`, `rustle`, `drinking`,
  `lapping`, `eating`, `bite`, `bone`, `splash`, `swim`, `underwater`, `wings`; species `crocodile`/`caiman`, `eagle`,
  `snake`, `bird`, `big_cat` (leopard, cheetah), `lion`, `elephant`, `hyena`, `hippo`; SXF `hit`, `impact`, `whoosh`,
  `riser`, `heartbeat`, `drop`.
- A6/A8/A9 never substitute: every keyword in the file name; an animal file only for that species or a relative (KIN in
  plan.py). Else audio THIẾU in the reply (slot, timecode, sound); user downloads (rescan, re-plan) or says no -> drop
  the token.

## Sound that moves the viewer
Per story first: what to feel at start, peak, end (beat sheet emotions; expand writes cues, A3 / A5 beds stay yours).
- Music = best fit, never by use count: most mood words, then covers its span, then closest length; never the same
  track twice in a row. One A7 cue per beat (wonder, tension, chase, aftermath, resolution).
- Music under 60-85% of the film; the rest deliberate silence. plan.py picks the track lasting to the next A7; `audio:`
  line reports coverage and cues ending > 3 s early (add an A7 or move the `off`).
- Strike: `A7=off` 1-3 s before attack / reveal / fall (bed + natural only), hit on the strike slot (`A8=hit` or
  `impact`, `A9=whoosh` on fast movement), then a calm / sad cue on the long post-climax shot. `A8=riser` 2-4 s before
  a peak.
- SXF only on state changes (danger, strike, escape, fall, splash, reveal): ~1 per 30-60 s calm, denser in action.
- Species voices only from the species or a close relative named in the text (leopard/cheetah growl or attack for
  jaguar/puma, crocodile for caiman, eagle for harpy eagle); never unrelated (no lion roar on a monkey); none ->
  breathing/foley, report the voice missing.
