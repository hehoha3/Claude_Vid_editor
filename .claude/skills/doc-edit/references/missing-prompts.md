# Missing footage prompts: `/doc-edit missing-prompts` (shot director V3, user 2026-11-05)

Needs plan.json after the intro fit (new-video.md C). The user generates the clips; nothing is generated, imported or
placed here. **Footage+AI (user 2026-11-05): prompts only for the THIẾU slots of the intro + story 1** (0:00 -> story 2;
`missing.py` does that by default, `--range=A-B` / `--all` on request); the body after story 1 is filled by plan.py,
and there are **no WEAK prompts** (an intro WEAK pick is THIẾU in plan.py and gets its prompt as THIẾU).
In a new-video run (`/doc-edit <audios-folder>`) brief.md (the screenplay) is already in context: use it, never
re-read it; and the reply is SKILL.md's combined one (its part 4 = the Reply below).
Output (user 2026-11-05): **`<video>/missing-prompt.csv`**, the 19-column missing-scenes schema
(`shot_id,cluster,tc_in,tc_out,dur_s,kind,animal,action,environment,time_of_day,shot_size,camera_angle,direction,
position,keep_whole,mo_ta,search_keywords,generation_prompt,reason`; UTF-8 BOM, opens in Excel), one row per prompt.
Full-AI films write the same CSV plus `lock-assets.md` (`dvr_cowork ai prompts`, `references/full-ai.md`); footage+AI prompts carry no
locks.

## Rules shared by both video types (`dvr_cowork/prompt_rules.py`, gated by `--check` and `dvr_cowork ai build`)
- **No contact, ever**: no bite, grab, strike, pin, shove, ram, collision, horns meeting, kill, wound, blood. A
  charge, lunge or swipe misses by a body length; show before (crouch, accelerating legs), during (dust / grass hides
  the line) or after (scatter, retreat) instead of the impact.
- **Every animal in frame keeps moving** the whole clip (running, turning, stepping, scanning, ears / tail alive):
  no standing still, posing, waiting, resting, settling, freezing.
- **Never a silent stare-down**: no "stare / look / gaze at each other", locked eyes, face to face, stand-off.
- The script appends the same closing sentence to every prompt (moving animals, no stare, no contact, no cuts, no
  blood / gore / VO / music / text / logo / watermark): never write those negatives yourself.
- **`dur_s`** = the slot's length rounded up to the next half second (3.2 s -> 3.5, 5 s -> 5.5, 2.4 -> 2.5): the
  clip has a short handle. The script computes it; prompt k of a group belongs to slot k of the group (extras
  beyond the slots: the group's longest slot, no timecode).

## Steps (1h-footage+AI)
1. `.venv/Scripts/python.exe .claude/skills/doc-edit/scripts/missing.py <key>` (the work key, the video folder or its
   audios folder): THIẾU groups `G<n>` (character + main action, or setting + light), slots, seconds, suggested clip
   count (= the number of slots: one prompt per slot, user 2026-10-17; = the budget), the
   story sentences (`## n`), `others there` (the other characters' footage status in those sentences), `truth`
   (sex / age / out of its slots) and `refused in library` (what plan.py's story rules turned down). The `at` line
   lists each slot's start: slot k = prompt k, its length decides the beat count.
2. Per group, think before writing (the brief entries of its `## n` and the ones around them, never a lone sentence;
   `/doc-edit missing-prompts` on its own: read `.work/doc_edit/<video>/brief.md` (`story.py brief` if missing), not
   the screenplay file):
   - **Event**: pursuit / escape / ambush / charge / strike / reaction / travel / rest...; actors with role
     (predator, prey, bystander), goal, cause, visible effect, urgency; species, count, marks, light, time of day
     and geography from the screenplay continuity bible. Never invent animals, counts, injuries or a new
     predator-prey relation.
   - **Action graph** (pursuit): predator advances/accelerates + prey escapes/accelerates; optional
     relationship wide, obstacle/reaction, aftermath only if narration and time support them.
   - **Coverage**: generate only what is truly missing. `others there` shows the hunter OK -> write only the prey
     clips (and the other way round). Budget = one prompt per THIẾU slot (+2 max), each slot its own role / framing; budget 1 -> the most important missing
     action, and say in the reply which need stays unserved.
   - **Shot roles**: `predator_burst` `prey_escape` `relationship_wide` `reaction` `obstacle` `reacquisition`
     `aftermath` `environmental_speed`; outside chases `action` `establishing` `detail`. Each prompt adds a role,
     angle or information the others lack; never 10 prompts that differ by one adjective.
3. **Claude writes every prompt by hand, never Gemini, never a bank generator** (user 2026-11-02 / 2026-11-05: the
   intro + story 1 hold ~20-60 THIẾU slots; each prompt is written for its slot, which reads better than a combined
   bank). Check each against step 2: truth (no outcome the story lacks), event and coverage (`others there`), a
   different role / framing / angle per clip, vector = where the animal travels (still = `static`, no direction on
   rises / reaches), place + light the same as the scene (dusk: the animal still clearly lit), biology,
   relationship_wide max one. Eating = "feeds / chews / tears at the grass" (a "bite" trips the contact gate).
   Format of `.work/doc_edit/<key>/prompts.txt` (overwrite): `## G<n>` (or `## +<species>` extra group),
   then per clip a line `<role> <vector> | <camera> | <place> | <light>` and its beats as `- ` lines (untimed; the
   script times them to `dur_s`). **Beats per clip by `dur_s`**: under 5 s exactly one clean readable beat; 5–7.5 s
   one main beat + at most one secondary reaction; 8 s and longer up to four (timed by the script across the clip).
   The script writes the header "Cinematic wildlife documentary, ultra-photorealistic 4K, <dur_s>-second single
   continuous shot, 16:9, shot on <camera>, <place>, <light>." and the shared closing sentence:

       ## G2
       predator_burst L>R | side-on 300mm telephoto, speed-matched pan, medium-long shot | a muddy rainforest corridor between giant buttress roots, wet leaves | neutral daylight
       - A single adult jaguar explodes into a full-speed sprint along the corridor, running left to right, wet leaves spraying.

   - Beats tell one continuous take in time order (start -> escalation -> end state); the vector, individual(s),
     place and light never change inside a clip. `place` matches the plan's ground look (`# LOOK` / `look=` in the
     spec, africa_1: dry-season floodplain, golden grass + floodwater) so the clip cuts in with its neighbours.
   - **One species per clip** (two of the same species ok); start "A single <species>" (or "Two <species>" /
     the exact count of the bible). A predator and its prey are separate clips, intercut in the edit.
     `relationship_wide` (both in one distant frame) only when the geography cannot be told otherwise; max one per
     group, say it in the reply (two species morph more).
   - **Vector** = one screen direction for the whole take: `L>R` `R>L` `away_UR` `away_UL` `toward` (only when it
     makes sense) `static`; write it out in the text ("left to right"...). Keep one axis across a chase sequence
     (the screenplay's travel direction: west-to-east = L>R). Never reverse, U-turn, mirror, flip, teleport, orbit.
     `static` = the animal moves in place (head turns, scanning, tail flicks, grooming), never a pose.
   - **Camera grammar** (input/SKILL.md, 2026-11-05): one shot, one primary camera move, no cuts or dissolves
     inside it; change at least one of vantage / shot size / movement from the previous prompt of the group, prefer
     two. Rotate: establishing wide with the animal in its setting · distant 300–600 mm telephoto behind grass
     (compressed depth) · eye-height reaction close-up with a focus pull · prey-height simulated POV (camera at
     eye level, never body-mounted) · side-on 200–400 mm speed-matched tracking · elevated oblique aerial / top-down
     for route and formation · low ground-level profile with grass parallax · over-shoulder from behind a stalker ·
     wide static the animal crosses and exits · a motivated whip-pan reacquisition. Name the shot size in the camera
     field (wide / medium / close-up...): it fills the CSV `shot_size`. No drone flying through branches, no lens so
     close the animal would be disturbed.
   - **Chase camera DNA** (adjust to the story): ~40% elevated extreme-wide / high-oblique distant, ~25% high-angle
     telephoto with pan or controlled zoom, ~20% horizontal medium-long side tracking, ~15% rear / three-quarter
     medium. Far enough to see the whole body and the running line; roots/branches as parallax. Speed shots never
     slow motion.
   - **Outside chases** (edit-grammar "Visual thinking"): low tracking = hero's power, top-down over the canopy =
     scale, high = trapped/vulnerable, static extreme close-up of eyes / claws before a lunge (the animal still
     breathing, ears moving), slow push-in for a threat; dark animals in dappled light emerging from shade.
   - **Light**: the screenplay's phase (neutral ~5600K daylight by default; dawn / dusk / night only when the scene
     says so, the animal still clearly lit); no cyan cast, no heavy orange grade, no dark vignette.
   - **Biome lock** (plan.json `region`): amazon = tropical rainforest = broadleaf canopy, buttress roots, lianas, wet
     leaves, mud, streams; never snow, alpine, conifers/pine, autumn, desert, dry dust clouds (wet leaves, mud,
     droplets, bent ferns instead). africa = East/Southern African savanna: golden dry grass, acacia / umbrella
     thorn trees, termite mounds, red dust, waterholes, kopjes; never snow, alpine, conifers/pine, autumn, rainforest.
     A wetland screenplay (Okavango, africa_1) = its floodplain: shallow floodwater, sedge, reeds, papyrus, dry
     islands with fan palms; the screenplay's place beats the generic savanna words.
     Region by species: Amazon (jaguar, ocelot, peccary, tapir, capybara, agouti, spider monkey, harpy eagle,
     tayra), African rainforest (leopard, duiker, okapi, forest buffalo, red river hog), Borneo/Asia (clouded
     leopard, sun bear, bearded pig, reticulated python).
   - **Biology**: mammals run, snakes slither, fish swim, birds fly, frogs hop, primates leap/scramble/climb,
     sloths move slowly (a "sloth runs" line -> urgent slow climb, and flag it), crocodilians short land bursts;
     solitary species stay solitary, herds/troops only with the bible's count.
   - Opening groups (slots before 1:30, edit-grammar "Opening"): one continuous event, so every prompt of it keeps the
     same individual(s), count, axis, light and site; medium / wide framings that show both sides come first.
   - **Story truth** (group line `truth sex=female age=young out=...`, user 2026-10-23): every prompt names it
     ("A single adult lioness", "a newborn wildebeest calf"). `out=kill` = the story's outcome happens off the clip:
     write the approach or the aftermath (scatter, the hunter walking off), never the contact. A near miss stays a
     miss: the prey escapes in frame. `refused in library: sex 8, kill 2` = the library had that animal but not as
     the story needs: write exactly what was missing (the sex, the hidden pose, the miss).
   - Environment groups (`## G` with sp=none) describe the place only, no animal, with motion in it (wind in the
     grass, drifting mist, birds crossing).
4. `missing.py <video> --check`: QC gates (role/vector valid and stated, no contradicting direction, no direction on
   a still action, no reversal/orbit/slow motion, biome words, biology, species named, contact / stare / pose words,
   beats per `dur_s`, near-duplicates, budget) + a preview of roles per group. Fix every error in prompts.txt, re-run.
5. `missing.py <key> --write` (re-runs the gates, refuses on errors) -> `<video>/missing-prompt.csv`: THIẾU rows,
   then extras; `shot_id` `G2-S014` (group + slot) or `G2-X3` (extra), `cluster` = group, `tc_in`/`tc_out` =
   the slot, `dur_s`, `kind=ai_generated`, `mo_ta` = the slot's need (Vietnamese), `reason` = THIẾU (library empty,
   or an intro WEAK pick) and what the library refused. stdout gives the save folder per group (= species name for tag-source): put them in the
   reply, never in the file. Videos planned before 2026-11-05 keep their `missing_prompts.txt`.

Reply: path, prompt count, per character roles (e.g. "báo: 3 predator_burst, 1 reaction"), skipped coverage and
why (footage already OK, budget), relationship_wide clips, biology flags. The user saves every generated clip into
`D:\AI_video\_check` (`/doc-edit logo`, `delogo`, `ingest` check logos, tag and file them into the species folders);
africa: into `D:\AI_video\_africa\_check` (flat), then logo / delogo on that folder and ingest = scan africa_ai_check
+ tag + `organize.py --africa --apply` (files them into `_africa\<species>`).
Prompt QC cannot catch AI visual errors: the generated clips still need a look (tag-source issues, organize).
