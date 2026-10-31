## New video: `/doc-edit <audios-folder> <amazon|africa>`

Region = the video folder's prefix (`amazon_` / `africa_`) or the command's word; neither -> ask, stop (SKILL.md
"Region"). Several audios folders (one per channel, user 2026-10-25): one agent per video runs B (brief, beats, plan,
prompts) in parallel; A and place of the videos run one after the other in the day project, each on its channel's
"Edit" (SKILL.md "Day project").

`<video>` = the folder's parent (`D:\Chann_1_shadowCanopy\amazon_2\audios` -> `amazon_2`); outputs land in that
video folder. Two jobs in parallel: the narration is one background command (A), the plan + prompts (B) are what
the user waits for, so B gets the attention and A never blocks it.

**0. Preflight, one call:** `ls "<folder>"` + `ls "<video>"` + `.venv/Scripts/python.exe -m dvr_cowork info`. The
folder needs (names case-insensitive) one `*timestamp*.md` (`[MM:SS] sentence` / `[HH:MM:SS]`, decimals ok, `#`
lines ignored; bilingual `## English` + `## Vietnamese` parts (user 2026-10-20): English = A2 + plan, Vietnamese =
`<video>\subtitles_vi.srt` placed on Subtitle 1 by vo-sync, same line count) and one `*screenplay*.md` (`script*.md` /
`kịch_bản.md` are not read; a `*Visual_Edit_Plan*.md` is optional, both go into the brief); missing or several -> say
which, stop. Then:
- Narration = sub-folder `mp3\` with one file per sentence, `1.mp3`, `2.mp3` ... = timestamp line 1, 2 ... (user
  2026-10-16; already cut, nothing to blade). Same preflight call (user 2026-10-23: the user cannot see broken
  files): count of `mp3\*.mp3` = English timestamp lines (africa_3: 123 passages vs 395 sentence files) and
  `find "<folder>/mp3" -name '*.mp3' -size -2000c` (ElevenLabs failures are 1686-byte files); any hit -> list every
  number at once, stop. vo-sync also decodes all files first and names every unreadable one. Old style (one narration `.mp3`/`.wav` in the folder, Whisper cuts it)
  still works when there is no `mp3\`.
- No narration yet (the user often plans before the ElevenLabs audio exists) -> B only; plan.py estimates the
  speech spans from the text. The reply says A2 waits for the audio.
- `<video>\plan.md` already there and the audio is new -> A only (the plan is done; `/doc-edit plan` afterwards
  only if the user wants exact VO ● marks).
- A: Resolve's current project = `<video>` (case-insensitive; channel form `c2_africa1` = folder `africa_1`, the
  user names it in the command) with a timeline "Edit", or the day project `vid_DDMMYY` with bin `Chann_N` and its
  "Edit" -> `run`; anything else
  (closed, other project) -> `analyze` (Whisper only, Resolve untouched) and the reply asks the user to open
  project `<video>`; on their "ok" run `vo-sync apply`. Never put A2 into another project.

### A. Narration -> A2 (background, start it first)

    .venv/Scripts/python.exe -m dvr_cowork vo-sync run "<folder>/mp3" "<folder>/<timestamp>.md"
    (old style: "<folder>/<audio>" instead of "<folder>/mp3")

Narrator from 0:03.6 (user 2026-10-25): a timestamp file starting earlier is shifted as a whole (0:00.6 -> every line
+3.0 s, the `first line moved` log line); plan.py takes the sentence times from vo-sync's plan.json, so videos synced
before keep theirs. Bash `run_in_background`, then go straight to B; never poll it. With `mp3\` there is no Whisper: files 1..n must
match the n timestamp lines exactly (else it names the missing/extra numbers and stops), each file's speech onset
is measured, `.work/<video>_mp3/plan.json` written in seconds (all B3 needs); then it imports the files into bin
"4. Audio/Narrator", backs up "Edit" and lays file n as one A2 item with its onset on timestamp n. (Old style: Whisper
(cached) -> `.work/<audio stem>/plan.json`, one bladed source.) When it finishes read only its stdout (`report.md`
next to that plan.json only for flagged rows). Flags: `pushed` (file n is longer than the gap to n+1, it starts
late: the timestamps or the take need a look), `boundary_uncertain` (old style: listen to that cut),
`head_trimmed`/`tail_trimmed` (harmless). A2 not empty / locked, no "Edit", bad timestamp line -> it stops: report it
(the line for a bad timestamp); never `--force-clear` without the user's yes.

### B. Plan + missing prompts (foreground)

1. `.venv/Scripts/python.exe .claude/skills/doc-edit/scripts/story.py brief "<folder>"` -> `.work/doc_edit/<video>/brief.md`,
   then read once, in one turn: `references/edit-grammar.md` and brief.md (Read; > ~2000 lines -> two Reads). brief.md
   = the screenplay with every beat's narrator line replaced by its numbered, timed sentences (`12 01:23.4 4.1s vo2.6 |
   text`: slot until the next sentence, voice length; the rest is a voice-free pause), a character lock only where it
   changes, plus the Visual Edit Plan without its beat table (2026-10-24: ~40 % of reading the screenplay + plan +
   timestamp file, africa_4 74 KB instead of 183 KB). Never open those three files, plan.json, audio, `_library.json`.
   brief.md stays in context for B4: don't re-read it. The Visual Edit Plan's audio routing uses other track numbers
   (A5 natural, A6 music): take its intent, the track layout is CLAUDE.md rule 1. Then one call:
   `plan.py --species <cast words> --region <region>` (species tags of that region's library per source: pick the
   exact `sp=` tokens, e.g. `sp=giant_otter,otter`).
1b. **africa only, tag by species** (user 2026-10-20: cheap but good): the Africa library is tagged only where a film
   needs it. For the cast (English folder species: `lion`, `cape buffalo`... = scan_source AFRICA_FOLDERS values)
   whose tagged count from B1 is < ~60 per source:
   `tag_source.py prepare africa_video africa_ai africa_ai_check --subject <cast,comma> --sample 60` (60 untagged clips
   per root and species, spread over the folder; plus `savannah --subject landscape --sample 40` while savannah has
   < ~150 tagged), then the tag-source loop (Sonnet agents, check, apply in background). Plan B3 needs the apply done.
   After B3: a cast species with THIẾU / WEAK slots and untagged clips left (`untagged clips skipped: ...; of the cast`)
   -> one more `--sample 60` round of that species and re-run plan BEFORE writing prompts: footage that exists is
   cheaper than generating it.
1c. **Story first** (user 2026-10-23, edit-grammar "Story first"): read the WHOLE brief (the screenplay's editorial
   boundaries, visual and sound directions, not only the narrator) before the first beat. Part 01 then opens
   with the film and story bible as `#` comment lines (plan.py ignores them, they steer your filters), the `# HOOK`
   blueprint, one `# CAST` per main character, and the story lines with their `no=`:

       # FILM question: how does a young wildebeest survive a journey that never stops?
       # BIBLE 1 01:30-06:30 southern plains, calving · [C] calf age=young, [M] mother sex=female · [L] lioness
       #   sex=female · outcome: lunge misses (no out=kill) · never: male lion, river, a herd that "rescues"
       # BIBLE 2 06:30-18:30 another calf + group (not story 1's) · [H] hyena · chase fails · ## 20 carcass = other day
       # CAST [L] sp=lion sex=female        <- tag -> tokens added to every line starting with that one tag
       # STORY 1 @16 no=river,crocodile     <- @16 = start of sentence 16 (STORY / INTRO / FAST_UNTIL)

   `# CAST` puts the truth tokens on every line of that animal (a line's own `sex=` wins: the mother vs the calf);
   `out=kill` only on the lines where the bible says the kill is seen.
2. **Beat sheet** (2026-10-24: the judgement is Claude's, the mechanical grammar is story.py's; africa_3 benchmark:
   shots <= 2 s 0 % -> 30 %, # TURN 0 -> 11, SXF 5 -> 27, natural sound 6 -> 70, at ~1/3 of the writing). Write it in
   2-4 parts with the **Write tool** (`.work/doc_edit/<video>/beats_parts/01.txt` ...; a bash heredoc of ~200
   Vietnamese lines broke on amazon_2), then
   `.venv/Scripts/python.exe .claude/skills/doc-edit/scripts/story.py expand "<folder>"` -> spec.txt (overwritten:
   later fixes = Edit on a beats part + expand again, never spec.txt by hand). Never re-read a part.

       >> 1-15 raw                           <- the hook: spec lines as below ('## n' blocks), copied as written
       >> 16-18 calm A3=water A5=water       <- a beat: sentences, emotion, audio of its first shot; 'turn' = # TURN
       [W] Đàn wildebeest chờ trên bờ | real | sp=wildebeest size=wide count=many    <- pool: story order, cycling
       [W] Một con trượt xuống mép nước | sp=wildebeest act=walk size=medium
       17: [CR] Cá sấu lao lên | real | sp=crocodile act=attack size=medium | A8=splash   <- first in sentence 17
       ~ Mặt nước nâu trống | real | sp=none size=wide set=river                      <- side shot (pause only)

   Shot line = `need | [src] | filter [| audio]` (src default any). Emotion, from the screenplay's turn, never from
   the narrator's words: `calm` `wonder` `observe` (ordinary narration) `build` `tense` `chase` `strike` (the decisive
   contact / reveal / fall) `release` (aftermath) `sad`. expand then does, by edit-grammar: lengths per emotion
   (~4.5-5 s calm / wonder / sad, ~3.4 observe, shorter and shorter in build / chase, a long hold first in release,
   uneven, '*' on the longest), side shots only in voice-free pauses >= 3 s of quiet beats (one at a time, <= 22 %),
   an A7 cue at each change of emotion (wonder -> wonder, observe -> neutral, build / tense -> tense, chase ->
   chase, release / sad -> calm), strike = A7 off on the shot before (+ riser after a build) + A8 hit + `# TURN`,
   chase start A8 whoosh, A6 natural sound from the act (footsteps, grass, drinking, eating, water, wings, breathing;
   >= 8 s apart). A token written on the beat or the line always wins. Yours: one beat per screenplay beat or per
   change of emotion inside it; 2-4 pool lines per beat in story order with changing sizes (establish -> subject ->
   reaction -> payoff); `N:` lines for what a sentence must open on (the strike, the reveal, story 1's landscape);
   side lines only in quiet beats. The expand line names beats that repeat one line 3+ times: give them more lines.
   Exact lengths, `12x4 same` chains, GFX: write those sentences as a `raw` beat. Spec line format (raw beats, and
   what expand writes):

       # REGION africa                   <- always, first line of part 01: the command's region
       # END 29:50                       <- target length; omit = last sentence end + 2 s
       # INTRO 0:20                      <- 0:15-2:00 (> 0:30 = cold-open hook, mostly character shots); omit = 0:15
       # OPENING action                  <- optional: landscape (default) | action; with # BIOME savanna|rainforest,
       # BIOME savanna                      # STORY 1 01:30 (chapter starts), # FAST_UNTIL, '# TURN' under a ## N:
       # STORY 1 01:30                      edit-grammar "Opening ... the hook" + biome-story-pacing.md
       # LOOK dry                        <- optional ground look green|dry: first shot takes it, each next shot keeps
                                            the previous one's (colour of the tag sheet), desert never; a line's
                                            look=dry / look=green,dry wins (africa_1: green -> dry -> sand jumps)
       # [D] Peters's duiker  [GC] African golden cat
       ## 1
       4 | Wide tán rừng lúc bình minh, sương | real | sp=none size=wide,aerial set=canopy light=golden kw=mist | A3=forest,birds A7=tense
       2 | [D] Cận duiker ngẩng đầu nghe | any | sp=duiker size=close_up act=look set=forest_floor | A6=insects
       * | Lối mòn trống, nắng xiên | real | sp=none set=forest_floor size=medium light=day |

   `dur` s (`*` = rest of the sentence slot + pause, exactly one per sentence; `12x4` / `*x5` = that time as 4 / 5
   shots of the same need + filter, uneven lengths: long voice-free slots, e.g. africa_1's 45 s scenes; `12x4 same` =
   those shots are consecutive parts of one clip, edit-grammar) | shot needed (Vietnamese) |
   real/ai/any/GFX | filter | audio (formats: edit-grammar.md). Write part 01 (0:00-1:30 + story 1) first and
   hardest, by edit-grammar "Opening ... the hook": the viewer decides there whether to stay. Videos before
   2026-10-24 (spec_parts/, no beats) keep their hand-written spec: `cat spec_parts/0*.txt > spec.txt` as before.
3. `story.py expand "<folder>"` (its one line: shots, side share, cues, turns, repeats), then
   `.venv/Scripts/python.exe .claude/skills/doc-edit/scripts/plan.py "<audios-folder>" > <work>/plan_stdout.txt 2>&1`
   then read only the summary: `sed -n '1,/character WEAK/p' <work>/plan_stdout.txt` (its `region:` line must be the
   command's region; the WEAK candidate list below
   it is ~150 lines: open it only in `/doc-edit plan`). With an audio it uses A's measured spans (not there yet -> it
   says so: wait for A's notification, re-run); without, the `narration:` line says the spans are estimated.
   - Multi-species leaks (amazon_2: a caiman in a jaguar hold, a jaguar in a caiman shot): give each predator / prey
     line `no=<the other story's animals>` from the start. Temperate scenery (autumn, snow, conifer) is excluded by
     plan.py itself.
   - Prints ALL spec errors grouped with `##` numbers; check the `audio:` line against edit-grammar (music
     coverage, early-ending cues, SXF count) in the same read. Fix everything in one pass of targeted edits (beats
     parts), expand, re-run.
   - YOLO-World on unmeasured clips of the spec's species (cache `.work/library/yolo.json`, normally warm via
     tag-source); many measured now -> run in background. Read only the `yolo:` line. Africa (tagged `--no-yolo`,
     4K ProRes on the NAS, ~4 clips/min, africa_1 2026-10-22: 6 h unfinished) -> plan.py uses the cache only by
     itself (`# REGION africa`; `--yolo-cached` forces it for amazon), and `yolo.py --warm` overnight when the user agrees.
   - Intro beat cuts: the intro cuts move onto the hits / bars of the intro's A7 music (`beats.py`, edit-grammar
     Intro). Read the `intro beat:` line: "not on a beat" cuts or "no A7 music under the intro" -> fix the spec.
   - Semantic tie-break (default; `--no-sem` = tags only): multilingual-e5-small compares the shot text with each
     clip caption and picks among clips of the same band; status OK / WEAK / THIẾU stays the tags'. Caption vectors
     cached in `.work/doc_edit/caption_emb_e5small.npz` (new captions ~15 s). Read only the `semantic:` line.
   - A shot no clip is long enough for -> 2-3 parts from different clips (⧉); audio stays on part 1.
   - `truth:` line (story rules): clips of the slot's animal refused by sex / age / resting / kill / no=, picks
     capped WEAK because the sex is not visible ("kiểm tra" marker), THIẾU slots caused by them. A refusal is right
     unless the bible is wrong: never drop `sex=` / `out` to fill a slot; untagged clips of that animal -> one more
     tag round (1b); many sex-unseen WEAK picks of a cast animal -> `tag_source.py prepare <roots> --retag
     action,sex,age,outcome,phase --subject <animal> --sample 60` + the tag loop, re-run plan; else THIẾU ->
     missing prompts name the sex / age.
   - `hook blueprint:` must say ok for an intro > 0:30.
   - Ledger: clips of the last 6 checked videos of the workspace are never matched on slots before 15:00
     (any clip after it, user 2026-10-25); `recent ledger` line = slots lost before 15:00, by character. Inside one video a clip may serve 3 slots over Edit + Open together, each a different part,
     >= 2 min apart (edit-grammar Source); parts already on "Open" are read from Resolve (`open:` line).
   - Character WEAK slots (top 3 candidates in stdout): in a new-video run keep plan.py's pick (speed; the user
     reviews plan.md), except those starting before 1:30: judge them always by the opening's hard rejects and
     continuity. In `/doc-edit plan` judge all: keep, `pin=<fragment>`, or `pin=none` (THIẾU); re-run.
   - THIẾU left and the user will not generate it ("thay bằng shot khác"): `plan.py <folder> --sub-all` fills every
     THIẾU slot with another part of a clip already used (same species > companion species > forest scenery; 60 s apart,
     max 4 uses; marked FALLBACK "late substitute"), then `place.py --fill`. Check the picks before placing: a shortage
     of one species falls through to scenery.
   - Audio files listed in `.work/library/audio_blocked.txt` (claimed tracks) are never picked; add a path fragment per line.
   - Outputs `.work/doc_edit/<video>/plan.json` (place input) and `<video>/plan.md` (user table; VO ● = narration).
   - Then `.work/tools/library_db.py sync` (user 2026-10-24: Postgres mirror; tables slots / slot_audio / audio /
     clips / usage); cross-video questions (THIẾU that recur, music reused in other videos, unused tracks) =
     `library_db.py query "SQL"`, never a script over the JSON.
4. Missing prompts: read `references/missing-prompts.md` and do its steps 1-5 on this plan, the screenplay from B1
   -> `<video>/missing_prompts.txt` (parts `## THIEU` + `## WEAK`). No THIẾU and no WEAK slot -> skip, say so.

User edits later -> change the beats part (old videos: spec.txt), expand, re-run (`/doc-edit plan`); never hand-edit plan.json.

### Reply (Vietnamese), in this order

1. The two files: `<video>\plan.md` and `<video>\missing_prompts.txt` (full paths).
2. A2: sentences placed, backup, flagged lines (number, timecode, flag, what to listen for); or why it is not placed
   yet (no audio yet -> "thả file narration vào <folder> rồi /doc-edit <folder>", still running, other project
   open, error).
3. Plan: shots, OK / WEAK / THIẾU / GFX, species missing, THIẾU and ledger-lost by character, the audio line,
   character WEAK count (kept as chosen), every audio THIẾU (slot, timecode, sound): no substitute; the user
   downloads one or says no (-> remove that token). The `truth:` numbers in one line. Opening: the hook promise and
   form, the mute test at 0:30 / 1:00 / 1:30 in one line each (subject, event, outcome, open question), teaser
   integrity (no preview acts on the anchor animal, no outcome shown), the 1:30 reset, opening THIẾU, and how story 1
   ends on screen.
4. Prompts: count, per character roles (e.g. "báo: 3 predator_burst, 1 reaction"), skipped coverage and why,
   relationship_wide clips, biology flags; the user saves the generated clips into `D:\AI_video\_check` (amazon) or
   `D:\AI_video\_africa\_check` (africa, flat; ingest files them into `_africa\<species>`).

### Intro music + place (same run; user 2026-10-31: no separate `/doc-edit intro` any more)
Send the two file paths in a message the moment missing_prompts.txt exists (the user starts generating), then go on.
As soon as A2 is on and plan.json written:
1. `intro.py <video>` picks the intro music by itself and fits it to 0:00 -> story 1 (`references/intro.md`: ranking,
   license, bar cuts), then `plan.py "<audios-folder>"` again so the intro cuts land on its hits / bars (read
   `intro music:` / `intro beat:` / `intro outro:` + the HOOK line). Intro THIẾU / WEAK go into the missing prompts
   (`missing.py <video> --range=00:00-<story 1>` when the full prompt file is already out: say it overwrote it, and
   keep a copy of the old one in `.work/doc_edit/<video>/`).
2. `place.py <video>` (no flag): intro + body in one go on empty tracks (not empty -> stop, report); the intro music
   goes to bin "7. Open", story 1's bed pre-laps the black.
Place waits for A to finish (the two never write to Resolve at once); Resolve not on `<video>` -> no place, say so.
The reply starts with the place lines (backup, V1 placed, red THIẾU markers), then the intro music (top 5, license,
fit, cuts on the beat, joints to listen to), then parts 1-4 above. No "next step" line: the user calls the next
command. Videos placed before 2026-10-31 with `--skip-intro` get their intro with `place.py <video> --intro`
(intro range empty) after `intro.py` + `plan.py`.

