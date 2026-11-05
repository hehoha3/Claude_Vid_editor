# create-doc-mov · full-AI 8-15p (any region: himalaya snow / high mountains; amazon, africa once their prompt locks exist)

One CLI (user 2026-11-05): `$E8` = `.venv/Scripts/python.exe -m dvr_cowork ai <cmd>`, `$Y` =
`.venv/Scripts/python.exe -m dvr_cowork youtube <cmd>`, from the workspace root. None of the footage+AI flow applies:
four_files.src.md, build_four_files.py, formats (1) / (2), the 90 s intro. Story craft and the source contract
are the two sections at the end of this file.

## Cost discipline (why the run is shaped this way)

A run is billed as tokens Claude writes (story.json ≈ 90 %), tokens re-read every turn (each extra round trip
re-reads the conversation), vidIQ credits and YouTube quota. So: batch independent calls in one turn, write the story
once, fix with small Edits, never pull big files into context.
- Read this file once (story craft + source contract included). Never open sibling story.json files,
  `dvr_cowork/fullai/tests/*.json` or the four generated Markdown files (compiled from the
  source you just wrote: review the source + the build summary).
- vidIQ: at most one call per run, no balance checks. No web search by default: narrate observable behaviour and
  story-framed time; search only for one specific factual claim you decide to keep.

## Concept (SKILL.md "Start of a new film": type -> trends -> 3 options -> changes?)

- Trends turn: `$E8 next-video Chann_N --region <region>` (the single `D:\Chann_N_*`, next `<region>_DDMMYY_N`, `next_archetype`, recent
  titles / casts; skips `_pushed`; stops on zero or several channel folders -> ask) + `$Y trends Chann_N
  [--query "..."]` (most viewed 4–20 min mountain predator / prey videos of 90 days by views/day, title patterns,
  tags; 101 units per new query, 0 cached 7 days) + one `vidiq_outliers` (long-form). vidIQ credit / auth error ->
  one line, YouTube alone. YouTube API fails (revoked token: `$Y remove Chann_N` then `$Y login --key Chann_N`; quota) -> stop,
  report. Options avoid the archetype / cast of `recent` unless trends clearly favour it (say so).
- Folder: a given `<video>\audios` path = `<video>`; use it when it is `next_video` or a `<region>_DDMMYY_N` folder (old films: `vid_DDMMYY_N`) without
  `.production\story.json` (the user pre-made it, so `next_video` shows N+1); else ask. Never reuse a folder that has
  a source.
- **Adapt a link** (`/create-doc-mov Chann_N <youtube_url>`): one turn `next-video` + `$Y reference Chann_N
  <url>` (1 unit; no captions) + `vidiq_video_transcript` (≈5 credits). Summarise in ≤ 6 lines: archetype, protagonist
  and antagonist side, tension mechanics (dual peril, clock, chokepoint, reversal, hook angle), beat order. No 3-option
  step; the "changes?" question carries cast + runtime. Keep the archetype and tension mechanics; replace geography,
  season, event chain, set pieces, escape method, all wording and the title. If a viewer of the reference could
  predict your next scene, change the obstacle or the turn; no names, signature lines or distinctive images. Record
  `"reference_url"` + a one-line `"adaptation_note"`. No transcript -> summarise from title / description / tags,
  offer that the user pastes it; never invent the reference's plot.
- **Runtime**: count the distinct turns the story carries (new obstacle, changed tactic, clock shrinking, reversal,
  decisive attempt), about one per 1.5–2 min after the first 60 s: 4–5 turns ≈ 8–9 min, 6 ≈ 10–11, 7–8 ≈ 12–15. Don't
  stretch a 5-turn story; state minutes + why in one line. Default 8–11, over 15 only on request.
- Cast in the option cards and the "changes?" question as two sides with exact counts (protagonist: ibex mother + one
  kid; antagonist: one snow leopard). The answer is the locked cast; don't reopen the concept.

## Write

1. `$E8 init "<video>" [--minutes <m>] --region himalaya|amazon|africa --title "<title>"` once, after the "changes?"
   answer (wpm 155, project = the day project `vid_DDMMYY_N` of the folder name). It pins profile full_ai_mountain v2 (8–15 min, default 10; intro cut from
   body sources; no-contact / no-stare build check) into the film. Its `reminder` line (a region without prompt locks
   yet: amazon / africa) goes to the user at once (user 2026-11-05): `prompts` will stop until the locks exist. Existing
   source: revise the source, not the outputs; once voice or shots are issued, keep that version and use a new
   folder for an incompatible rewrite. `python -m dvr_cowork profile context "<video>" --phase author` = the film's numbers.
2. **Design before prose**: archetype; the lead's motive; dual peril (living + natural, interacting); ticking clock;
   chokepoint; role-reversal moment; the action passages with their reversals (Story craft §2); one central survival
   question, a visible payoff, a cause-and-effect outline; cast IDs with exact counts, `terms`, LEFT / RIGHT marks
   (one entry per individual the viewer must tell apart); route and constant light with no animal named in them.
3. **Hook and setup**: the hook scene has voice only (no `shots`: `/doc-edit hook` later tiles its 30 s with
   2–4 s cuts from reviewed body sources). Continuous narration, triangle hook by
   ~00:18, reversal teased 00:24–00:30 without its result. Setup through action: `build` needs a setup shot with
   `intensity` ≥ 3; no repeat of the hook narration.
4. **Voice budget per scene before writing it**: the voice math of the Source contract (60 s = 4 blocks 132–144
   words, 75 s = 5 blocks 163–177, 30 s = 3 blocks 62–70). One block = one nonblank transcript line = one MP3.
5. **Write story.json in one Write** (films over ~11 min: first half, then one Edit appending the rest). Shapes in
   the Source contract; scene `camera` / `characters` / `location` as defaults, every shot its own `camera`, a
   `title`, four fast continuous `beats` (story moment by 5 s), one short clause per field. A shot's `characters` is
   its complete visible cast and its text (with the scene `direction` / `location` it inherits) names only them.
   Every scene changes the situation; every shot has one action, start / end state, 6–9 s; shots cover the scene
   exactly. `hook_role` + `spoiler:false` only on strong unresolved body moments, ≥ 1 candidate each for threat,
   vulnerability, pursuit, obstacle, unanswered (aim for 12–15 candidates in total; one role may hold several).
   `build` rejects contact verbs in `action` / `end_state` / beats (bite, gore, ram, grab, pin, shove, knock down,
   kill, wound, blood, horns clash…): write the miss ("swipes past a body length short"). Vietnamese (`vi`) written by Claude in the same Write: complete,
   natural, the narrator's calm tone.
6. `$E8 build "<video>" && $E8 validate "<video>"`. Build lists every timing and banned-word problem in one run, other
   errors one at a time: fix with targeted Edits (never rewrite the file), rerun. Then judge what the compiler can't:
   hook / setup narration vs visible events and payoff, originality (adaptations: not the reference's beat order),
   factual claims.
7. **Self-check from your source**: first clash at 01:00, passages and the reversal of each, no standing / staring /
   posing shot, no body contact in any beat.
8. **Report** in Vietnamese, then **stop** (no voice, shots or Resolve):
   ```
   **<video>** · Chann_<n> · full-AI · <m:ss> — <title>
   Archetype + motive / dual peril / clock / chokepoint / reversal (one line each)
   00:00–00:30 highlight · 00:30–01:00 setup · each passage one line (mm:ss) · ending
   Story-1 DNA: first clash mm:ss · passages n (reversal each) · contact none
   Build: runtime · voice blocks (= mp3) · words · occupancy · prompts
   File: [screenplay] · [transcript] · [timestamp] · [visual_plan] · voice -> <video>\voice\1.mp3…N.mp3
   ```
   Name any factual line you did not source-check. `audios\` holds only the four Markdown files. Then one line for the
   video in `.work/knowledge/handoffs/current.md`.

When the user returns with voice: `/doc-edit <video>` (doc-edit references/full-ai.md); never rewrite approved
narration to hide a timing problem.

## Story craft: DNA, opening, structure, narration

One continuous survival story, a locked cast and geography, played as **Story 1 of the 1h films** from start to
finish: an early climax and nonstop strong action (user 2026-11-04). DNA = the lead's practical goal × dual peril ×
triangle hook; a film missing one of the three is a nature walk, not a survival story. Where this file and the
contract (Source contract) disagree, the contract wins: 30 s hook (2–4 s cuts from body sources), 6–9 s
shots, no gore, no animal contact, no silent stare-down. Runtime 8–15 min (default 10).

### 1. Archetype (rotate so consecutive films differ)

Take the user's concept, else `next_archetype` from `next-video` (cycle migration → lost → predator → mother →
throne after the channel's latest film; never open sibling story.json files). Record it as `"archetype"`.

| id | Archetype | Motive of the lead | Dual peril (animal + nature) | Emotional arc |
|---|---|---|---|---|
| `mother` | Mother & vulnerable young | Protect a young that cannot keep up | Stalking predator + terrain the young can't cross | Tenderness → threat → clever defence → fragile safety |
| `migration` | Deadly-terrain migration | Reach the next range | Broken terrain (gorge, river, rockfall, avalanche) + predator at the chokepoint | Grandeur → chaos → loss → resilience |
| `lost` | Lost survivor | Rejoin the herd | Exhaustion / fog + a predator closing in | Confusion → lurking danger → instinct erupts → escape |
| `predator` | Predator's quest | Winter hunger; feeding the young | Blizzard / cold + large prey that fights back | Exhaustion → tactics → climax → respect for life |
| `throne` | Battle for the throne | Territory, an ageing alpha's last stand | Rival male + cliff / ice where one misstep ends it | Dominance → challenge → collapse → new balance |

`predator`: the audience follows the hunter, its hunger is a real stake, the prey stays worthy, the ending earns
respect; a hunt ends in a failed attempt, a retreat or an off-screen implication. Never blood, gore or wounds.

### 2. Story-1 DNA (the user's rules for this type)

- **Lead with a practical goal** (food, a safe route, offspring, rejoining the herd), so every chase has a reason.
  Species the generators render well: snow leopard, Himalayan ibex, markhor, bharal (never "blue sheep": `build`
  rejects "blue"), Himalayan tahr, wolf, red fox, golden eagle, Eurasian lynx; 2–4 cast IDs.
- **Runtime 8–11 min** by default (up to 15 only on request).
- **00:00–00:30 = highlights of the whole film**: hook candidates (`hook_role`, `spoiler:false`) are the biggest
  action of different passages (chase, wall jump, feint, fall-away, chokepoint leap), never an outcome.
- **Early climax**: the setup (00:30–01:00) already has one fast action (a sprint, a leap, a collapse), not a calm
  tour; the first real clash or chase **opens the first body scene at 01:00**. No calm arrival scene.
- **Escalation**: 3 action passages for 8–10 min, 4 for 11–15. Each has a reversal (failed approach, dodge, footing
  breaks, rival arrives, prey turns, return journey) and leaves the situation changed. Between passages the breather
  is still motion carrying new information (fast traverse, climb, regrouping at a run), ≤ ~30 s. Last ~10 %:
  consequence and local resolution, still moving.
- **Action palette** (most shots of every scene): run, sprint, chase across scree and snow, pounce, lunge, wall jump
  (bounding off near-vertical rock), rock and cliff climb, leap across a gap, skid down a snow chute, flight from
  rockfall or a snow slide, rear and charge.
- **Fights without contact**: face-offs with charges, rearing, feints, swipes and lunges that **miss** ("horns swing
  past a body length apart"), dodges, chase-offs. No hit, bite, grab, shove or horns meeting. The near miss is the
  climax beat; the outcome is a retreat, a fall-back, a chase-off. Ingest QC rejects clips that show contact.

### 3. Dual peril

Pair a living threat with a natural one and let them interact: the rockfall drives the herd into the wolves' gully,
the blizzard hides the leopard's approach, thin ice makes a charge lethal. Both by 00:18 (hook), both active through
the body: if the predator pauses, nature presses, and vice versa.

### 4. Opening 00:00–01:00 (triangle hook complete by ~00:18)

- 0–6 s **visual hook**: the most arresting unresolved image the body will produce, with its natural sound. The first
  voice block opens with the **narrative hook**: one stakes sentence specific to this film, *situation + why it's
  fatal + the twist that makes it worse* ("Cut off from the herd when the snow bridge collapsed, this mother ibex and
  her tiny kid are alone on a wall of ice and loose rock, and a snow leopard has already chosen them."). It must stay
  true for whichever spoiler-free candidates `hook` later selects.
- **Audio hook**: natural sound the generated shot itself carries (rockfall rumble, wind howl, growl, hooves on scree)
  in the candidate shots' beats; designed sound belongs to A3 in doc-edit, never to prompts.
- 6–12 s the lead and the motive · 12–18 s the second peril with a readable approach direction · 18–24 s the
  chokepoint closes an option, the clock is visible · 24–30 s tease the role reversal, cut before its result.
  The picture runs 10–12 fast cuts under this narration (threat → vulnerability → pursuit → obstacle → unanswered),
  so the narration names the stakes, not one specific image.
- 30–60 s setup: the original situation, route, motive and clock **through action**; no second trailer, no repeat of
  the hook's narration, no resolving its promise. A narrated temporal reset ("Minutes earlier…") is fine when the hook
  borrows a future moment.
- Archetype openers: `migration` high wide of the herd fleeing a rockfall along a cliff path · `lost` frightened eyes
  in fog, predator eyes behind · `predator` the hunter's paws skidding on ice, horned prey ahead · `mother` the young's
  unsteady legs at a ledge, predator shape above · `throne` two males rear and charge on an ice-glazed ledge, horns
  swinging past, one hoof slipping.

### 5. Retention pillars (set up early, paid off later)

1. **Ticking clock**: a visible deadline (storm wall over the pass, rising water, sinking sun); re-show it as it
   shrinks.
2. **Chokepoint**: escape narrows to one option (a one-hoof ledge, a fogbound gully, a snow bridge); establish it
   before it matters so the climax is readable.
3. **Role reversal**: the expected victim turns the tables without contact (prey wheels and feints, a slide
   separates hunter and hunted, the herd forms a horn wall); tease it 00:24–00:30, first clash at 01:00.

Scene unit (~60 s): unstable situation → sudden failure (ledge cracks, attack) → improvised defence using terrain →
decisive leap / stand that changes position. Reuse the shape, not the events.

### 6. Middle and payoff

Every 20–40 s a new fact with a consequence: a route narrows, a foothold fails, the young falls behind, the predator
finds another line. Show the ledge / crack before it decides the outcome. Intercut threat → vulnerable subject →
terrain → reaction while holding geography; re-establish the route with a high wide after a big position change.
Wides explain risk, mediums show action, closes show the mechanism; within a 6–9 s take vary composition and action.

Consequences stay: a slipped animal remains below, a crossed gap stays crossed, identity, marks and travel direction
hold; a new scene never magically restores the old arrangement. Cuts are motivated by gaze, action or sound.

End by paying off the opening question with the archetype's final emotion (resilience, relief, respect, new
balance): the survivors' clear immediate state, a short release, finish. No unrelated montage, no villainized
predator, no unsupported universal claims. Label the film an AI dramatization.

### 7. Narration

Specific physical verbs, connected paragraphs, varied sentence length. Explain the consequence the image cannot state;
don't narrate every paw movement or repeat "one wrong step". Facts stay attached to a visible survival problem and
are plausible or story-framed ("weeks without a kill"), never invented statistics; no claims about animal thoughts.
85–92 % voice occupancy; short purposeful gaps for an impact or a turn. Never promise retention numbers.

Don't carry over from the channel strategy notes: huge exact numbers ("500 goats", "−40 °C") as fact (lock 1–3 key
individuals, a background group of a stated consistent size, prefer 8–40); prompt tokens like `8k`, `--ar 16:9`,
brand names (the compiler writes prompts from the locks: put fur in wind, breath vapour, fog, light direction into
`lock`, `environment`, beats); their 15 s / 60 s timings.

## Source contract (`story.json`, compiled by `dvr_cowork.fullai.story`)

Store source in `<video>/.production/story.json`. A JSON document is a local file, not a database. Build outputs are regenerated together; do not edit the four Markdown files separately.

Top fields:

| Field | Meaning |
|---|---|
| schema | 2 |
| title, premise, central_question, payoff | Original film concept and visible outcome |
| archetype | `migration`, `lost`, `predator`, `mother` or `throne` (see Story craft); ignored by the compiler, read for rotation |
| target_minutes | 8–15 (default 10, the film's pinned profile); includes first 60s |
| fps | Default 24; match Resolve before placement |
| wpm | 155 (measured 2026-11-05 on the real narrator, 157; `init` writes it) |
| resolve_project | Leave unset: the project is the day project `vid_DDMMYY_N` of the folder name `<region>_DDMMYY_N` (`core.day_project`), shared with every channel's film of that day, footage+AI included |
| reference_url, adaptation_note | Adapt mode only; ignored by the compiler |
| characters | At least two `{id, species, name, count, terms, lock, details, absolute_lock}` entries (see Cast lock below) |
| count_lock | Required list: total cast, then the exact count in each situation (`9 above + 1 below = exactly 10`), and "no other animals" |
| zones | Required numbered list of every place in route order, rock-only names (reference only, never on screen) |
| terrain_lock | Required list: rock/snow/vegetation/water rules and what stays changed (`bridge stays broken`) |
| light_lock | Required list: light progression **between** shots, white balance/colour rules, no slow motion |
| environment | Terrain, weather and color lock repeated in **every** prompt; no time-of-day progression ("sun fading to dusk" makes generators change light mid-shot); never names an animal |
| geography | Screen axis and compass only (one short line). Used only when a shot has no `location`. **Never list the whole route** (generators drift through every place named) and never name an animal |
| synthetic_disclosure | Clear statement of original AI dramatization |
| scenes | Ordered contiguous scenes, no gaps |

### Cast lock

Every prompt opens with `IN FRAME — exactly N animals: <locks>` and `NOT IN FRAME — <species of every other entry>: absent…`, both built from the shot's `characters`. So `characters` is the **complete visible cast** of that take, and nothing else in the prompt may name anyone outside it.

- **One entry per individual the viewer must tell apart** (lead, mother, injured kid, torn-ear wolf). Interchangeable members share one group entry with `count` > 1. Split a group when a subset separates on screen: a 10-goat herd whose injured kid falls and whose mother climbs down = `LEAD`, `MOTHER`, `KID` + `HERD_REST` (count 7); "9 above" = all but `KID`, "reunion" = all four.
- `count`: exact animals this entry puts in frame. IN FRAME total = sum of the shot's counts.
- `terms`: every word you use for it in shot text (`["yearling"]`, `["leopard"]`, `["herd", "twelve ibex", "silhouettes"]`); distinct across characters, plurals matched automatically. `build` stops listing each shot/field that names a character absent from that shot.
- **Production bible**: `build` refuses a source without `details` on every character and `count_lock`, `zones`, `terrain_lock`, `light_lock`; they print as sections 1–5 of `lock-assets.md` (beside `missing-prompt.csv`). `name` is the display heading (`YEARLING — CHIPPED-HORN FEMALE (LEAD)`); `details` lists appearance bullets then role/behaviour bullets; `absolute_lock` is the one rule that must never flip (`Scar only at the base of the LEFT horn`) and is also appended to that character's lock in every prompt.
- `lock` (one line, repeated verbatim): `Exactly N <age/sex> <species>` + build/size relative to others + coat colour + eyes/nose + horns/ears/tail + hooves/paws + **permanent asymmetric marks with the side in CAPS** (`pale scar at base of LEFT horn — never on the right`, `injured LEFT hind leg only`). Give look-alikes one distinct mark each and say what they do NOT have (`no scar, unlike the lead`). Appearance only: behaviour belongs in shot actions.
- Off-screen presence: a call, scent or tracks of an absent animal may be described without naming it (`a distant bleat`, `fresh paw prints`); otherwise add it to `characters`. A visible shadow or silhouette counts as in frame.
- Locations and light: each scene sets `location` = that place only + its constant light (`A hoof-wide ledge on a north granite wall, fog-filled drop south; blue dusk`); a shot may override it. Describe places, **never proper names** in any prompt field (`Karsha basin` was burned in as a caption) — names belong in narration only. Locations describe rock, never animals.

Each scene contains `id`, `title`, `phase` (hook/setup/story/ending), `change` (what changes), `shots`, `voice`. First scene is the hook: `voice` only, no `shots` key (`build` makes one 30 s `HOOK` window; `/doc-edit hook` tiles it with 2–4 s cuts from reviewed body sources, no extra prompts). Second scene has five 6s generated shots for setup. Final scene is ending. Main scenes may have any number of 6–9s shots summing to target runtime. IDs must be unique.

Each **non-hook** shot needs `duration_s, title, characters, action, camera, direction, start_state, end_state, beats`. `title` is the prompt heading (`001 — Injured Kid Is Trapped Below the Herd`). A scene may set `direction`, `characters` and `location` once as defaults; a shot's own value wins. **Give every shot its own `camera`** (shot size + angle + movement): `build` rejects consecutive shots with the same camera, because a scene-level camera made eight takes look identical. Vary scale across a scene (wide → close → detail → two-shot) and never repeat a beat already shown (e.g. a second "lowers her horns"). **`beats` is always four explicit, fast, continuous action clauses** for 0-2s, 2-5s, 5-7s and 7-10s of the 10s clip (lower-case clause, no timing). Every beat moves: run, bound, leap, scramble, skid, lunge, wheel, charge, stamp, lash. Tension shots use violent small motion (trembling, tail lashing, snorting), never a pose. The shot's story moment must land in 0-5s: the timeline uses only the first 6–9s, so 5-10s is full-speed follow-through. `build` rejects calm words in beats (still, motionless, slow, gentle, careful, calm, pause, wait, rest, settle, idle, freeze, hold position, small movement). Derived opening-frame/hold beats are gone: they produced gentle, near-static clips.

**Light never goes blue.** Locations, environment, geography, camera and beats must not use blue, bluish, cyan, teal, dusk, twilight, night, moon or stars, or "cold colour" (`build` rejects them). These words gave clips a strong blue cast. Write late-story light as "low warm late-afternoon sun, neutral white balance, snow stays true white" or "golden evening light", even when the narration says dusk. The light lock says neutral 5600K, true-white snow, real-time 1x speed. Every prompt adds "No slow-motion, The video must not have a blue tint". Do not put "high speed phantom camera" in the style, because it renders slow motion.

Compact scene (preferred):

```json
{
  "id": "S04", "title": "The cracked step", "phase": "story", "change": "The lower shelf is no longer safe",
  "direction": "left to right; upper wall behind the pair", "characters": ["MOTHER", "KID"],
  "shots": [
    {"duration_s": 7, "title": "The Kid Races for the Cracked Step", "camera": "high-oblique telephoto, fast tracking pan",
     "action": "The kid bounds toward the cracked step",
     "start_state": "Mother one body length ahead", "end_state": "Kid skids short of the crack",
     "beats": ["the kid bounds along the shelf past its mother, hooves spraying grit",
               "a crack splits the step ahead and the kid skids hard, forelegs braced",
               "the mother wheels around and lunges back toward it",
               "the kid scrambles sideways along the edge, grit pouring into the drop"],
     "hook_role": "obstacle", "intensity": 4, "spoiler": false},
    {"duration_s": 8, "title": "Mother Blocks the Crack", "camera": "medium side angle, locked",
     "action": "Mother charges in to block the kid",
     "start_state": "Kid at the crack", "end_state": "Mother between kid and crack",
     "beats": ["grit pours from the crack under the kid's hooves",
               "the mother charges back and shoulders between the kid and the crack",
               "the kid stumbles backward against the wall",
               "the mother stamps and swings her horns toward the edge, flanks heaving"]}
  ],
  "voice": [{"en": "...", "vi": "..."}]
}
```

Allowed hook roles: threat, vulnerability, pursuit, obstacle, unanswered, none. Intensity is 0–5. Omission of `spoiler:false` makes a shot ineligible for hook selection. Mark the actual resolution as a spoiler. Metadata is a candidate hint; `shot_qc.json` supplies actual visual approval and a clean hook source-in later.

`voice` is a list of `{en: "one English paragraph", vi: "full Vietnamese translation"}`. No newlines inside a block. Several blocks in the same scene remain adjacent physical lines in transcript; blank lines separate scenes. **Global nonblank physical-line order** maps to `1.mp3…N.mp3`. Do not use rendered Markdown paragraph count. The compiler schedules their starts inside each scene from estimated or measured durations. It never cuts the source audio.

**Voice math** (the floor `build` enforces): inter-block gaps ≤ 3 s, lead 0.3 s, tail 0.5 s, so a scene of T s with
n blocks needs ≥ (T − 3(n−1) − 0.8) × wpm/60 words, counted as `len(en.split())` (a spaced " — " is a word: write
commas). At 155 wpm: 30 s = 3 blocks, 62–70 words · 60 s = **4** blocks, 132–144 · 75 s = **5** blocks, 163–177
(3 blocks in 60 s needs ≥ 138 words, so "≤ 137 in 3 blocks" always fails). Shot grids: 60 s = 9+9+9+9+8+8+8,
75 s = 9+8+8+8+9+8+8+9+8; a 9 min film = hook + setup + 3 × 60 s + 4 × 75 s = 62 prompts.

The compiler stops at the first problem, except voice timing and calm / blue-light words: every scene overflow /
gap and every banned word is listed in one run. Word traps: "the rest of", "slowing", "waiting", "still", "settle".
Scene `direction` / `location` are in every shot's prompt: never name an animal there. Common ones and the cheap fix: `exceeds picture window` → trim that scene's words or add a shot; `narrator gap` → add one short connected sentence to that scene; `Picture totals …` → adjust one shot's `duration_s` in the scene that is off; `Repeated body action` → make the two `action` strings describe distinct moments.

Default maximum inter-block/tail pause is 3s. A scene may set `pause_limit_s` up to 6 with an explicit `pause_reason`; use sparingly. A voice overflow is an error: shorten/re-record the affected approved block with the user, or revise that scene's shot budget in a new production version. Do not change picture durations after prompts have been issued.

After conform, `timestamp.md` uses exact frame-based millisecond onsets in `## English` and `## Vietnamese`; English equals transcript text exactly. SRT spans follow actual placed MP3 durations. Script math does not verify translation quality, factual accuracy, dramatic strength, internal silence or visual continuity; the agent must review them.
