# Missing footage prompts: `/doc-edit missing-prompts` (shot director V2, user 2026-10-13)

Needs plan.json (SKILL.md B3). The user generates the clips; nothing is generated, imported or placed here.
In a new-video run (`/doc-edit <audios-folder>`) brief.md (the screenplay) is already in context: use it, never
re-read it; and the reply is SKILL.md's combined one (its part 4 = the Reply below).

1. `.venv/Scripts/python.exe .claude/skills/doc-edit/scripts/missing.py <video>`: THIẾU groups `G<n>` and WEAK groups `W<n>`
   (always both, user 2026-10-27; character + main action, or setting + light), slots, seconds, suggested clip count
   (= the number of slots: one prompt per slot, user 2026-10-17; = the budget; a WEAK prompt asks for what the
   picked clip lacks: the sex / age shown, the act, the framing), the
   story sentences (`## n`), `others there` (the other characters' footage status in those sentences), `truth`
   (sex / age / out of its slots) and `refused in library` (what plan.py's story rules turned down).
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
3. Write `.work/doc_edit/<video>/prompts.txt` (overwrite; Write tool): `## G<n>` / `## W<n>` (or `## +<species>` extra group),
   then per clip (= one 10 s generated video, format user 2026-10-22) a line `<role> <vector> | <camera> | <place> |
   <light>` and 2-4 beat lines `a-bs: ...` running 0-10 s without gaps. The script wraps camera / place / light in
   the fixed header "Photorealistic wildlife documentary video, 10 seconds, 16:9, shot on <camera>, <place>, <light>,
   National Geographic style, real animal anatomy and motion, no blood, no gore." and numbers the prompts `1. `, `2. `:

       ## G2
       predator_burst L>R | a long telephoto lens from a distant high-oblique position, panning hard | a muddy rainforest corridor between giant buttress roots, wet leaves | neutral daylight
       0-3s: A single adult jaguar explodes into a full-speed sprint along the corridor, running left to right, small-to-medium in frame.
       3-7s: It gains speed with an accurate feline gait, wet leaves and droplets spraying, one short controlled zoom.
       7-10s: The jaguar keeps sprinting left to right past the roots, strong parallax, one continuous forward action.

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
   - **Chase camera DNA** (adjust to the story): ~40% elevated extreme-wide / high-oblique distant, ~25% high-angle
     telephoto with pan or controlled zoom, ~20% horizontal medium-long side tracking, ~15% rear / three-quarter
     medium. Grammar: subject identity + starting action + acceleration/biomechanics + terrain interaction + fixed
     vector + camera elevation/distance/lens + tracking/pan + optional zoom + speed cues + continuity/biome limits.
     One primary camera move + at most one escalation (subject accelerates -> pan faster; gap closes -> short
     controlled zoom; occlusion -> quick reacquisition on the same axis). Far enough to see the whole body and the
     running line; roots/branches as parallax. Speed shots never slow motion.
   - **Outside chases** (edit-grammar "Visual thinking"): low tracking = hero's power, top-down over the canopy =
     scale, high = trapped/vulnerable, static extreme close-up of eyes/claws/teeth before and at a strike, slow
     push-in for a threat; dark animals in dappled light emerging from shade.
   - **Biome lock** (plan.json `region`): amazon = tropical rainforest = broadleaf canopy, buttress roots, lianas, wet
     leaves, mud, streams; never snow, alpine, conifers/pine, autumn, desert, dry dust clouds (wet leaves, mud,
     droplets, bent ferns instead). africa = East/Southern African savanna: golden dry grass, acacia / umbrella
     thorn trees, termite mounds, red dust, waterholes, kopjes; never snow, alpine, conifers/pine, autumn, rainforest.
     A wetland screenplay (Okavango, africa_1) = its floodplain: shallow floodwater, sedge, reeds, papyrus, dry
     islands with fan palms; the screenplay's place beats the generic savanna words.
     Light = the screenplay's (neutral daylight by default, dusk/night when the scene says so).
     Region by species: Amazon (jaguar, ocelot, peccary, tapir, capybara, agouti, spider monkey, harpy eagle,
     tayra), African rainforest (leopard, duiker, okapi, forest buffalo, red river hog), Borneo/Asia (clouded
     leopard, sun bear, bearded pig, reticulated python).
   - **Biology**: mammals run, snakes slither, fish swim, birds fly, frogs hop, primates leap/scramble/climb,
     sloths move slowly (a "sloth runs" line -> urgent slow climb, and flag it), crocodilians short land bursts;
     solitary species stay solitary, herds/troops only with the bible's count.
   - Opening groups (slots before 1:30, edit-grammar "Opening"): one continuous event, so every prompt of it keeps the
     same individual(s), count, axis, light and site; medium / wide framings that show both sides come first.
   - **Story truth** (group line `truth sex=female age=young out=...`, user 2026-10-23): every prompt names it
     ("A single adult lioness", "a newborn wildebeest calf"); no catch / kill / carcass unless `out=kill` (a near
     miss stays a miss: the prey escapes in frame). `refused in library: sex 8, kill 2` = the library had that animal
     but not as the story needs: write exactly what was missing (the sex, the hidden pose, the miss). The `--check`
     gates refuse prompts that break the truth.
   - No gore, no blood, no text; environment groups (`## G` with sp=none) describe the place only, no animal.
4. `missing.py <video> --check`: QC gates (role/vector valid and stated, no contradicting direction, no
   reversal/orbit/slow motion, biome words, biology, species named, near-duplicates, budget) + a preview of roles
   per group. Fix every error in prompts.txt, re-run.
5. `missing.py <video> --write` (re-runs the gates, refuses on errors) -> `<video>/missing_prompts.txt` (numbered
   prompts `1. ` .. with their beats, under `## THIEU` then `## WEAK`, no group headers, numbering runs on; user rules 2026-10-09 / 10-22 / 10-27) + `.work/doc_edit/<video>/shot_manifest.csv` (row n = prompt n:
   group, role, vector, species, save folder, slots, sentences, seconds, needs, prompt). stdout gives the save
   folder per group (= species name for tag-source): put them in the reply, never in the file.

Reply: path, prompt count, per character roles (e.g. "báo: 3 predator_burst, 1 reaction"), skipped coverage and
why (footage already OK, budget), relationship_wide clips, biology flags. The user saves every generated clip into
`D:\AI_video\_check` (`/doc-edit logo`, `delogo`, `ingest` check logos, tag and file them into the species folders);
africa: into `D:\AI_video\_africa\_check` (flat), then logo / delogo on that folder and ingest = scan africa_ai_check
+ tag + `organize.py --africa --apply` (files them into `_africa\<species>`).
Prompt QC cannot catch AI visual errors: the generated clips still need a look (tag-source issues, organize).
