# Missing footage prompts: `/doc-edit missing-prompts` (shot director V2, user 2026-10-13)

Needs plan.json (step 2). The user generates the clips; nothing is generated, imported or placed here.

1. `.venv/Scripts/python.exe .claude/skills/doc-edit/scripts/missing.py <video>`: THIẾU groups (character + main
   action, or setting + light), slots, seconds, suggested clip count (~6 s usable per clip, = the budget), the
   story sentences (`## n`) and `others there` (the other characters' footage status in those sentences).
2. Per group, think before writing (read the screenplay entries of its `## n` and the ones around them, never a
   lone sentence):
   - **Event**: pursuit / escape / ambush / charge / strike / reaction / travel / rest...; actors with role
     (predator, prey, bystander), goal, cause, visible effect, urgency; species, count, marks, light, time of day
     and geography from the screenplay continuity bible. Never invent animals, counts, injuries or a new
     predator-prey relation.
   - **Action graph** (pursuit): predator advances/accelerates + prey escapes/accelerates; optional
     relationship wide, obstacle/reaction, aftermath only if narration and time support them.
   - **Coverage**: generate only what is truly missing. `others there` shows the hunter OK -> write only the prey
     clips (and the other way round). Budget = suggested clips (+2 max); budget 1 -> the most important missing
     action, and say in the reply which need stays unserved.
   - **Shot roles**: `predator_burst` `prey_escape` `relationship_wide` `reaction` `obstacle` `reacquisition`
     `aftermath` `environmental_speed`; outside chases `action` `establishing` `detail`. Each prompt adds a role,
     angle or information the others lack; never 10 prompts that differ by one adjective.
3. Write `.work/doc_edit/<video>/prompts.txt` (overwrite): `## G<n>` (or `## +<species>` extra group), then one line
   per clip: `<role> <vector> | <English shot content>` (the script adds the fixed house prefix):

       ## G2
       predator_burst L>R | A single adult jaguar explodes into a full-speed sprint along a muddy rainforest corridor between giant buttress roots, running left to right; distant high-oblique telephoto camera, jaguar small-to-medium in frame, pans hard with the sprint and one short controlled zoom as it gains speed; wet leaves and droplets spray backward, strong parallax; one continuous forward action, accurate feline gait, neutral daylight, no reversing, no mirrored running, no camera orbit
       prey_escape L>R | A single collared peccary bolts into a frantic escape through wet leaf litter past huge roots, running left to right; medium-long horizontal telephoto camera on the same side of the action tracks it, foreground leaves sweep past and the camera reacquires it without crossing the axis; mud kicks backward, natural motion blur, neutral daylight, no turning back

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
   - **Biome lock**: tropical rainforest = broadleaf canopy, buttress roots, lianas, wet leaves, mud, streams;
     never snow, alpine, conifers/pine, autumn, desert, dry dust clouds (wet leaves, mud, droplets, bent ferns
     instead). Light = the screenplay's (neutral daylight by default, dusk/night when the scene says so).
     Region by species: Amazon (jaguar, ocelot, peccary, tapir, capybara, agouti, spider monkey, harpy eagle,
     tayra), African rainforest (leopard, duiker, okapi, forest buffalo, red river hog), Borneo/Asia (clouded
     leopard, sun bear, bearded pig, reticulated python).
   - **Biology**: mammals run, snakes slither, fish swim, birds fly, frogs hop, primates leap/scramble/climb,
     sloths move slowly (a "sloth runs" line -> urgent slow climb, and flag it), crocodilians short land bursts;
     solitary species stay solitary, herds/troops only with the bible's count.
   - No gore, no blood, no text; environment groups (`## G` with sp=none) describe the place only, no animal.
4. `missing.py <video> --check`: QC gates (role/vector valid and stated, no contradicting direction, no
   reversal/orbit/slow motion, biome words, biology, species named, near-duplicates, budget) + a preview of roles
   per group. Fix every error in prompts.txt, re-run.
5. `missing.py <video> --write` (re-runs the gates, refuses on errors) -> `<video>/missing_prompts.txt` (prompt
   lines only, no headers, user rule 2026-10-09) + `.work/doc_edit/<video>/shot_manifest.csv` (row n = line n:
   group, role, vector, species, save folder, slots, sentences, seconds, needs, prompt). stdout gives the save
   folder per group (= species name for tag-source): put them in the reply, never in the file.

Reply: path, prompt count, per character: save folder + roles (e.g. "báo: 3 predator_burst, 1 reaction"), skipped
coverage and why (footage already OK, budget), relationship_wide clips, biology flags. Then: save into those
folders -> /process-ai-video -> /scan-source ai -> /tag-source -> /doc-edit plan -> place --replace.
Prompt QC cannot catch AI visual errors: the generated clips still need a look (tag-source issues, organize).
