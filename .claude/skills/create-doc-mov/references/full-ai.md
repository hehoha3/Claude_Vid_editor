# create-doc-mov · full-AI 8-180p (a_ folders; any region: frozen = snow / ice / high mountains; amazon, africa once their prompt locks exist)

`$E8` = `.venv/Scripts/python.exe -m dvr_cowork ai <cmd>`, `$Y` = `.venv/Scripts/python.exe -m dvr_cowork youtube <cmd>`
(workspace root). No footage flow (four_files.src.md, build_four_files.py, formats (1) / (2)).

## Cost discipline

story.json ≈ 90 % of the cost; each round trip re-reads the conversation: batch independent calls, write the story
once, fix with small Edits, never pull big files into context. Read this file once; never open sibling story.json files, `dvr_cowork/fullai/tests/*.json`
or the four generated Markdown files (review the source + build summary). vidIQ ≤ one call per run, no balance checks.
Web search only for one specific factual claim you keep; otherwise narrate observable behaviour, story-framed time.

## Concept (SKILL.md "Start of a new film": type -> trends -> 3 options -> changes?)

- Trends, one turn: `$E8 next-video Chann_N --region <region> --lang <en|es>` (the single `D:\Chann_N_*`, next
  `a_<lang>_<region>_DDMMYY_N`, `next_archetype`, recent titles / casts; skips `_pushed`; zero / several channel
  folders -> ask) + `$Y trends Chann_N [--query "..."]` (most viewed 4–20 min mountain predator / prey videos of 90
  days, views/day, title patterns, tags; 101 units per new query, 0 cached 7 days) + one `vidiq_outliers` (long-form).
  vidIQ credit / auth error -> one line, YouTube alone; YouTube API fails (revoked token: `$Y remove Chann_N` then
  `$Y login --key Chann_N`; quota) -> stop, report. Options avoid the archetype / cast of `recent` unless trends
  clearly favour it (say so).
- Folder: a given `<video>\audios` = `<video>`; use it if it is `next_video` or an `a_<lang>_<region>_DDMMYY_N` folder
  (old: `<region>_…`, `vid_DDMMYY_N`) without `.production\story.json` (pre-made: `next_video` shows N+1); else ask.
  Never reuse a folder with a source.
- **Adapt a link** (`/create-doc-mov Chann_N <youtube_url>`): one turn `next-video` + `$Y reference Chann_N <url>`
  (1 unit; no captions) + `vidiq_video_transcript` (≈5 credits). Summary ≤ 6 lines: archetype, protagonist /
  antagonist side, tension mechanics (dual peril, clock, chokepoint, reversal, hook angle), beat order. No 3-option
  step; "changes?" carries cast + runtime. Keep archetype + tension mechanics; replace geography, season, event chain,
  set pieces, escape method, all wording, title; no next scene a reference viewer could predict, no names, signature
  lines or distinctive images. Record `"reference_url"` + one-line `"adaptation_note"`. No transcript -> summarise
  title / description / tags, offer that the user pastes it; never invent its plot.
- **Runtime** = the user's minutes ± 3 (8–180; "20p" = any target 17–23 the story fills naturally): `range` of
  `python -m dvr_cowork profile stories --minutes N`, then that target's stories (one story up to 15 min, else 5–12 min
  each, Story 1 longest; hook 30 s under 20 min, 90 s from 20 min). Turns (new obstacle, changed tactic, shrinking
  clock, reversal, decisive attempt) ~one per 1.5–2 min: 4–5 ≈ 8–9 min, 6 ≈ 10–11, 7–8 ≈ 12–15. Never stretch a
  5-turn story: a longer film gets more stories.
- Cards + "changes?": cast as two sides with exact counts (protagonist: ibex mother + one kid; antagonist: one snow
  leopard). The answer locks the cast; don't reopen the concept.

## Write

1. After "changes?": `$E8 init "<video>" --minutes <m> --title "<title>"` once (region from the folder name, wpm 155,
   day project `vid_DDMMYY`; pins profile full_ai v1: no-contact / no-stare build check). Its `reminder` (amazon /
   africa: no prompt locks yet) -> user at once: `prompts` stops until the locks exist. Existing source: revise it, not
   the outputs; once voice or shots are issued keep that version, new folder for an incompatible rewrite. Film's
   numbers: `python -m dvr_cowork profile context "<video>" --phase author`.
2. **Design before prose**: archetype, motive, dual peril (living + natural, interacting), clock, chokepoint, role
   reversal, action passages + reversals (Story craft §2), one central survival question, visible payoff,
   cause-and-effect outline; cast IDs with exact counts, `terms`, LEFT / RIGHT marks (Cast lock); route + constant
   light, no animal named in them.
3. **Scenes**: hook = voice only (no `shots`; Source contract); continuous narration, triangle hook by ~00:18,
   reversal teased in its last 6 s without the result. Every later scene has `"story": k` (1, 2, … in order); story
   k ≥ 2 opens on its own `setup` scene (any length, intensity ≥ 3); any story may close on an `ending` scene; the last
   scene is an ending. Count ≠ `profile stories` -> `"stories_reason"`. Setup through action (`build` needs a setup
   shot with `intensity` ≥ 3), no repeat of the hook narration.
4. **Voice budget per scene first** (Voice math). One block = one nonblank transcript line = one MP3.
5. **story.json in one Write** (over ~11 min: first half, then one Edit appending the rest). One short clause per
   field; each scene changes the situation; each shot one action with start / end state; shots cover the scene
   exactly; a shot's `characters` = its complete visible cast, its text (+ inherited scene `direction` / `location`)
   names only them. `hook_role` + `spoiler:false` only on strong unresolved body moments: ≥ 1 each for threat,
   vulnerability, pursuit, obstacle, unanswered, aim 12–15 total (a role may hold several). `build` rejects contact
   verbs in `action` / `end_state` / beats (bite, gore, ram, grab, pin, shove, knock down, kill, wound, blood, horns
   clash…): write the miss ("swipes past a body length short"). `"lang"` (en / es, step 1) at the top; `vi` by Claude
   in the same Write: complete, natural, the narrator's calm tone.
6. `$E8 build "<video>" && $E8 validate "<video>"`; targeted Edits (never rewrite the file), rerun. Then judge what the
   compiler can't: hook / setup narration vs visible events and payoff, originality (adaptations: not the reference's
   beat order), factual claims.
7. **Self-check**: first clash at 01:00, passages + reversal each, no standing / staring / posing shot, no body contact
   in any beat.
8. **Report** in Vietnamese, then **stop** (no voice, shots or Resolve):
   ```
   **<video>** · Chann_<n> · full-AI · <m:ss> — <title>
   Archetype + motive / dual peril / clock / chokepoint / reversal (one line each)
   hook (00:00–00:30, or –01:30 from 20 min) · setup · per story: each passage one line (mm:ss) · ending
   Story-1 DNA: first clash mm:ss · passages n (reversal each) · contact none
   Build: runtime · voice blocks (= mp3) · words · occupancy · prompts
   File: [screenplay] · [transcript] · [timestamp] · [visual_plan] · voice -> <video>\voice\1.mp3…N.mp3
   ```
   Name any factual line not source-checked. `audios\` holds only the four Markdown files. One line for the video in
   `.work/knowledge/handoffs/current.md`.

Voice back -> `/doc-edit <video>` (doc-edit references/full-ai.md); never rewrite approved narration to hide a timing
problem.

## Story craft: DNA, opening, structure, narration

One continuous survival story played as **Story 1 of the 1h films**: early climax, nonstop strong action. DNA =
practical goal × dual peril × triangle hook (missing one = a nature walk). The Source contract wins over this section
(v1 / v2 films: 6–9 s shots).

### 1. Archetype (rotate so consecutive films differ)

The user's concept, else `next_archetype` from `next-video` (cycle migration → lost → predator → mother → throne after
the channel's latest film). Record it as `"archetype"`.

| id | Lead's motive | Dual peril (animal + nature) | Emotional arc | Opener (0–6 s) |
|---|---|---|---|---|
| `mother` | Protect a young that cannot keep up | Stalking predator + terrain the young can't cross | Tenderness → threat → clever defence → fragile safety | Young's unsteady legs at a ledge, predator shape above |
| `migration` | Reach the next range | Broken terrain (gorge, river, rockfall, avalanche) + predator at the chokepoint | Grandeur → chaos → loss → resilience | High wide of the herd fleeing a rockfall along a cliff path |
| `lost` | Rejoin the herd | Exhaustion / fog + a predator closing in | Confusion → lurking danger → instinct erupts → escape | Frightened eyes in fog, predator eyes behind |
| `predator` | Winter hunger; feeding the young | Blizzard / cold + large prey that fights back | Exhaustion → tactics → climax → respect for life | Hunter's paws skidding on ice, horned prey ahead |
| `throne` | Territory, an ageing alpha's last stand | Rival male + cliff / ice where one misstep ends it | Dominance → challenge → collapse → new balance | Two males rear and charge on an ice-glazed ledge, horns swinging past, one hoof slipping |

`predator`: the audience follows the hunter, its hunger is a real stake, the prey stays worthy, the ending earns
respect; a hunt ends in a failed attempt, a retreat or an off-screen implication. Never blood, gore or wounds.

### 2. Story-1 DNA

- **Practical goal** (food, safe route, offspring, rejoining the herd) behind every chase. Species that render well:
  snow leopard, Himalayan ibex, markhor, bharal (never "blue sheep": `build` rejects "blue"), Himalayan tahr, wolf,
  red fox, golden eagle, Eurasian lynx; 2–4 cast IDs.
- **00:00–00:30 = highlights**: hook candidates (`hook_role`, `spoiler:false`) = the biggest action of different
  passages (chase, wall jump, feint, fall-away, chokepoint leap), never an outcome.
- **Early climax**: the setup (00:30–01:00) has one fast action, not a calm tour; the first real clash / chase **opens
  the first body scene at 01:00**. No calm arrival scene.
- **Escalation** per story: 2 action passages for a 5–7 min story, 3 for 8–10, 4 for 11–15; each with a reversal
  (failed approach, dodge, footing breaks, rival arrives, prey turns, return journey) that changes the situation.
  Breathers ≤ ~30 s, still motion with new information. Last ~10 %: consequence and local resolution, still moving.
- **Action palette** (most shots): run, sprint, chase across scree and snow, pounce, lunge, wall jump (off
  near-vertical rock), rock / cliff climb, gap leap, skid down a snow chute, flight from rockfall / snow slide, rear
  and charge.
- **No contact**: charges, rearing, feints, swipes and lunges that **miss** ("horns swing past a body length apart"),
  dodges, chase-offs; no hit, bite, grab, shove or horns meeting. Near miss = climax beat; outcome = retreat, fall-back,
  chase-off. Ingest QC rejects contact clips.
- **Dual peril**: a living + a natural threat that interact (the blizzard hides the leopard's approach), both by 00:18,
  both active through the body: predator pauses -> nature presses, and vice versa.

### 3. Opening 00:00–01:00 (triangle hook by ~00:18)

- 0–6 s **visual hook**: the most arresting unresolved image the body will produce, with its natural sound. The first
  voice block opens with the **narrative hook**: one film-specific stakes sentence, *situation + why it's fatal + the
  twist that makes it worse* ("Cut off from the herd when the snow bridge collapsed, this mother ibex and her tiny kid
  are alone on a wall of ice and loose rock, and a snow leopard has already chosen them."), true for any spoiler-free
  candidates `hook` selects.
- **Audio hook**: natural sound in the candidate shots' beats (rockfall rumble, wind howl, hooves on scree); designed
  sound = A3 in doc-edit, never prompts.
- 6–12 s lead + motive · 12–18 s second peril, readable approach direction · 18–24 s chokepoint closes an option,
  clock visible · 24–30 s tease the role reversal, cut before its result. Picture = 10–12 fast cuts (threat →
  vulnerability → pursuit → obstacle → unanswered): narration names the stakes, not one image.
- 30–60 s setup: situation, route, motive, clock **through action**; no second trailer, no repeat of the hook
  narration, no resolving its promise. A narrated reset ("Minutes earlier…") is fine when the hook borrows a future
  moment.

### 4. Retention pillars

1. **Ticking clock**: a visible deadline (storm wall over the pass, sinking sun), re-shown as it shrinks.
2. **Chokepoint**: escape narrows to one option (one-hoof ledge, snow bridge), established before it matters.
3. **Role reversal**: the expected victim turns the tables without contact (prey wheels and feints, the herd forms a
   horn wall); tease 00:24–00:30, first clash at 01:00.

Scene unit (~60 s): unstable situation → sudden failure → improvised defence using terrain → decisive leap / stand that
changes position. Reuse the shape, not the events.

### 5. Middle and payoff

- Every 20–40 s a new fact with a consequence (route narrows, foothold fails); show the ledge / crack before it decides
  the outcome.
- Intercut threat → vulnerable subject → terrain → reaction, holding geography; a high wide re-establishes the route
  after a big position change. Wides = risk, mediums = action, closes = mechanism; one clear action per 3–7 s take;
  vary composition; cuts motivated by gaze, action or sound.
- Consequences stay (a fallen animal stays below, a crossed gap stays crossed; identity, marks, travel direction hold).
- End: pay off the opening question with the archetype's final emotion: the survivors' clear immediate state, a short
  release, finish. No unrelated montage, villainized predator or unsupported universal claims. Label the film an AI
  dramatization.

### 6. Narration

Physical verbs, connected paragraphs, varied sentence length; explain the consequence the image can't state; don't
narrate every paw movement or repeat "one wrong step". Facts tied to a visible survival problem, plausible or
story-framed ("weeks without a kill"); no invented statistics, no animal thoughts. 85–92 % voice occupancy; short
purposeful gaps for an impact or turn. Never promise retention numbers.

Never from the channel strategy notes: huge exact numbers ("500 goats", "−40 °C") as fact (lock 1–3 key individuals +
a background group of a stated consistent size, prefer 8–40); prompt tokens (`8k`, `--ar 16:9`, brand names; fur in
wind, breath vapour, fog, light direction go into `lock`, `environment`, beats); their 15 s / 60 s timings.

## Source contract (`story.json`, compiled by `dvr_cowork.fullai.story`)

Source: `<video>/.production/story.json` (a local file, not a database). Build outputs are regenerated together; never
edit the four Markdown files separately.

Top fields:

| Field | Meaning |
|---|---|
| schema | 2 |
| title, premise, central_question, payoff | Original film concept and visible outcome |
| archetype | `migration`, `lost`, `predator`, `mother` or `throne` (Story craft); ignored by the compiler, read for rotation |
| target_minutes | 8–180 (the user's; the film's pinned profile); includes the hook + first setup |
| fps | Default 24; match Resolve before placement |
| wpm | 155 (real narrator measured 157; `init` writes it) |
| resolve_project | Leave unset: the day project `vid_DDMMYY_N` of the folder name `<region>_DDMMYY_N` (`core.day_project`), shared with every channel's film of that day, footage+AI included |
| reference_url, adaptation_note | Adapt mode only; ignored by the compiler |
| characters | ≥ two `{id, species, name, count, terms, lock, details, absolute_lock}` entries (Cast lock) |
| count_lock | Required list: total cast, then the exact count in each situation (`9 above + 1 below = exactly 10`), and "no other animals" |
| zones | Required numbered list of every place in route order, rock-only names (reference only, never on screen) |
| terrain_lock | Required list: rock/snow/vegetation/water rules and what stays changed (`bridge stays broken`) |
| light_lock | Required list: light progression **between** shots, white balance/colour rules, no slow motion |
| environment | Terrain, weather and color lock repeated in **every** prompt; no time-of-day progression ("sun fading to dusk" changes light mid-shot); never names an animal |
| geography | Screen axis and compass only (one short line), used only when a shot has no `location`. **Never list the whole route** (generators drift through every place named), never name an animal |
| synthetic_disclosure | Clear statement of original AI dramatization |
| scenes | Ordered contiguous scenes, no gaps |

### Cast lock

Every prompt opens with `IN FRAME — exactly N animals: <locks>` and `NOT IN FRAME — <species of every other entry>: absent…`,
both built from the shot's `characters`: the **complete visible cast** of that take; nothing else in the prompt may
name anyone outside it.

- **One entry per individual the viewer must tell apart** (lead, mother, injured kid, torn-ear wolf); interchangeable
  members share one group entry with `count` > 1. Split a group when a subset separates on screen: a 10-goat herd whose
  injured kid falls and whose mother climbs down = `LEAD`, `MOTHER`, `KID` + `HERD_REST` (count 7); "9 above" = all
  but `KID`, "reunion" = all four.
- `count`: exact animals this entry puts in frame; IN FRAME total = sum of the shot's counts.
- `terms`: every word used for it in shot text (`["yearling"]`, `["leopard"]`, `["herd", "twelve ibex", "silhouettes"]`);
  distinct across characters, plurals matched automatically. `build` stops listing each shot/field that names a
  character absent from that shot.
- **Production bible**: `build` refuses a source without `details` on every character and `count_lock`, `zones`,
  `terrain_lock`, `light_lock`; they print as sections 1–5 of `lock-assets.md` (beside `missing-prompt.txt`). `name` =
  display heading (`YEARLING — CHIPPED-HORN FEMALE (LEAD)`); `details` = appearance bullets, then role/behaviour
  bullets; `absolute_lock` = the one rule that must never flip (`Scar only at the base of the LEFT horn`), also
  appended to that character's lock in every prompt.
- `lock` (one line, repeated verbatim): `Exactly N <age/sex> <species>` + build/size relative to others + coat colour +
  eyes/nose + horns/ears/tail + hooves/paws + **permanent asymmetric marks with the side in CAPS** (`pale scar at base of LEFT horn — never on the right`,
  `injured LEFT hind leg only`). Look-alikes: one distinct mark each + what they do NOT have
  (`no scar, unlike the lead`). Appearance only; behaviour belongs in shot actions.
- Off-screen presence: a call, scent or tracks of an absent animal may be described without naming it
  (`a distant bleat`, `fresh paw prints`); otherwise add it to `characters`. A visible shadow or silhouette is in frame.
- Locations and light: each scene sets `location` = that place only + its constant light
  (`A hoof-wide ledge on a north granite wall, fog-filled drop south; blue dusk`); a shot may override it. Describe
  places, **never proper names** in any prompt field (`Karsha basin` burned in as a caption); names in narration only.
  Locations describe rock, never animals.

Scene fields: `id`, `title`, `phase` (hook/setup/story/ending), `change` (what changes), `shots`, `voice`. First scene =
the hook: `voice` only, no `shots` key (`build` makes one 30 s `HOOK` window; `/doc-edit hook` tiles it with 2–4 s
cuts from reviewed body sources, no extra prompts). Second = the 30 s setup (v3: 6–10 shots of 3–5 s; v1 / v2: five
6 s). Final = ending. Main scenes: any number of shots in the pinned range (v3: 3–7 s, mostly 3–5) summing to target
runtime. IDs unique.

Each **non-hook** shot needs `duration_s, title, characters, action, camera, direction, start_state, end_state, beats`.
`title` = prompt heading (`001 — Injured Kid Is Trapped Below the Herd`). A scene may set `direction`, `characters`
and `location` once as defaults; a shot's own value wins.
- **Every shot its own `camera`** (shot size + angle + movement): `build` rejects consecutive shots with the same
  camera. Vary scale across a scene (wide → close → detail → two-shot); never repeat a beat already shown (e.g. a
  second "lowers her horns").
- **`beats`** (v3): 1 explicit, fast, continuous action clause when the clip (slot + 1 s) is under 5 s (it must carry a
  real-speed verb: sprint, bolt, leap, scramble, dart... or two actions joined by "then"; `build` rejects it
  otherwise, a lone small action renders slow motion), else 1–2; the clip is split evenly between them (lower-case
  clause, no timing). v1 / v2 films: always four. No opening-frame / hold beats (near-static clips).
- Every beat moves: run, bound, leap, scramble, skid, lunge, wheel, charge, stamp, lash. Tension shots use violent
  small motion (trembling, tail lashing, snorting), never a pose. The story moment lands early: the clip is the slot +
  1 s, the last second is full-speed follow-through.
- `build` rejects calm words in beats (still, motionless, slow, gentle, careful, calm, pause, wait, rest, settle, idle,
  freeze, hold position, small movement).

**Light never goes blue.** Locations, environment, geography, camera and beats must not use blue, bluish, cyan, teal,
dusk, twilight, night, moon or stars, or "cold colour" (`build` rejects them). Late-story light = "low warm
late-afternoon sun, neutral white balance, snow stays true white" or "golden evening light", even when the narration
says dusk. The light lock says neutral 5600K, true-white snow. Every prompt starts with the real-time speed sentence
(prompt_rules `SPEED`), adds "The video must not have a blue tint" and ends "no slow motion, no speed ramp". Never put
"high speed phantom camera", "Cinematic", "BBC Earth" or "national geographic" in the style (slow motion).

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
               "a crack splits the step ahead and the kid skids hard, forelegs braced"],
     "hook_role": "obstacle", "intensity": 4, "spoiler": false}
  ],
  "voice": [{"en": "...", "vi": "..."}]
}
```

Hook roles: threat, vulnerability, pursuit, obstacle, unanswered, none. Intensity 0–5. Without `spoiler:false` a shot
is ineligible for hook selection; mark the actual resolution as a spoiler. Metadata is a candidate hint; `shot_qc.json`
supplies actual visual approval and a clean hook source-in later.

Narrator language (asked at step 1, never assumed): top-level `"lang": "en"` (default) or `"es"`; the voice key is
that code. `voice` = list of `{en: "one English paragraph", vi: "full Vietnamese translation"}` (es:
`{es: "one Spanish paragraph", vi: "..."}`, written natively in neutral Latin-American Spanish, VI from the Spanish;
shots, beats, bible and prompts stay English). Then `timestamp.md` opens `## Spanish`; `$Y seo` prints `LANGUAGE: es`
-> the whole seo_draft.json in Spanish, chapter names included; upload sends audio language es. Words still count at
the profile wpm (155, English voice): a Spanish block may run longer, conform shows it. No newlines inside a block;
blocks of one scene = adjacent physical lines in transcript, blank lines separate scenes. **Global nonblank
physical-line order** maps to `1.mp3…N.mp3` (not the rendered Markdown paragraph count). The compiler schedules their
starts inside each scene from estimated or measured durations; it never cuts the source audio.

**Voice math** (the floor `build` enforces): inter-block gaps ≤ 3 s, lead 0.3 s, tail 0.5 s, so a scene of T s with
n blocks needs ≥ (T − 3(n−1) − 0.8) × wpm/60 words, counted as `len(en.split())` (a spaced " — " is a word: write
commas). At 155 wpm: 30 s = 3 blocks, 62–70 words · 60 s = **4** blocks, 132–144 · 75 s = **5** blocks, 163–177
(3 blocks in 60 s needs ≥ 138 words, so "≤ 137 in 3 blocks" always fails). Shot grids: 60 s = 9+9+9+9+8+8+8,
75 s = 9+8+8+8+9+8+8+9+8; a 9 min film = hook + setup + 3 × 60 s + 4 × 75 s = 62 prompts.

The compiler stops at the first problem, except voice timing and calm / blue-light words: every scene overflow / gap
and every banned word is listed in one run. Word traps: "the rest of", "slowing", "waiting", "still", "settle". Scene
`direction` / `location` are in every shot's prompt: never name an animal there. Cheap fixes: `exceeds picture window`
→ trim that scene's words or add a shot; `narrator gap` → add one short connected sentence to that scene;
`Picture totals …` → adjust one shot's `duration_s` in the scene that is off; `Repeated body action` → make the two
`action` strings describe distinct moments.

Max inter-block/tail pause 4.2s (`story.PAUSE_S`); the picture keeps changing through it (3–5 s shots, v3). A scene may
set `pause_limit_s` up to 6 with an explicit `pause_reason`, sparingly. A voice overflow is an error: shorten /
re-record the affected approved block with the user, or revise that scene's shot budget in a new production version.
Never change picture durations after prompts are issued.

After conform, `timestamp.md` has exact frame-based millisecond onsets in `## English` and `## Vietnamese`; English
equals transcript text exactly. SRT spans follow actual placed MP3 durations. Script math does not verify translation
quality, factual accuracy, dramatic strength, internal silence or visual continuity: the agent reviews them.
