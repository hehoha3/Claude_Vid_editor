## New video (footage+AI 1-3h): `/doc-edit <audios-folder> [amazon|africa|himalaya]`

Order (user 2026-11-05): **0 preflight -> A narration (background) + B plan (foreground) -> C intro music + re-plan
-> D prompts (intro + story 1 only) -> E place**. The body after story 1 is filled at once by plan.py (BODY_SUB: the
`--sub-all` + `--sub-broad` tiers, FALLBACK markers): no prompts there. Prompts come after C because the intro fit
renumbers the groups (2026-11-05: prompts written before it had to be regenerated).

Region = the video folder's prefix (`amazon_` / `africa_` / `himalaya_`; old `congo_*` = amazon) or the command's
word; neither -> ask, stop. `<video>` = the folder's parent (`D:\Chann_1_shadowCanopy\amazon_2\audios` -> `amazon_2`);
outputs land in that video folder. Several audios folders (one per channel, user 2026-10-25): one agent per video
runs B + D (files only) in parallel; A, C's `intro.py` order and E run one video after the other (one Resolve,
SKILL.md "Day project"). The agent prompt names the channel, region, work key and the limits (no Resolve writes, no
deletes, Write tool for beats parts) and asks back for the reply parts 3-4 plus every workaround it needed.

### 0. Preflight (one call)
`ls "<folder>"` + `ls "<video>"` + `.venv/Scripts/python.exe -m dvr_cowork info` (with `DVR_CHANNEL=Chann_N`) +
`ls "<folder>/mp3" | wc -l` + `find "<folder>/mp3" -name '*.mp3' -size -2000c` + `ls .work/doc_edit/<key>/`.
- The folder needs (case-insensitive) one `*timestamp*.md` (`[MM:SS] sentence` / `[HH:MM:SS]`, decimals ok, `#`
  lines ignored; bilingual `## English` + `## Vietnamese` (user 2026-10-20): English = A2 + plan, Vietnamese =
  `<video>\subtitles_vi.srt` on Subtitle 1 by vo-sync, same line count) and one `*screenplay*.md` (`script*.md` /
  `kịch_bản.md` are not read; `*Visual_Edit_Plan*.md` optional, both go into the brief). Missing or several -> say
  which, stop.
- Narration = `mp3\1.mp3 … N.mp3`, one per English timestamp line (user 2026-10-16; already cut). Count = lines, no
  file under 2000 bytes (ElevenLabs failures are 1686 bytes); any problem -> list every number at once, stop.
  vo-sync also decodes every file first. Old style (one narration `.mp3`/`.wav` in the folder, Whisper cuts it) still
  works when there is no `mp3\`.
- **Conform first** (user 2026-11-05): a create-doc-mov film (`four_files.src.md` in the work folder) without
  `durations.json` beside it was never conformed: run create-doc-mov job A before vo-sync,
  `.claude/skills/create-doc-mov/scripts/build_four_files.py <src> "<folder>" --mp3 "<folder>/mp3"` (PASS; STOP =
  report, no vo-sync). Never after A2 is placed.
- No narration yet -> B only (plan.py estimates the spans); the reply says A2 waits for the audio.
  `<video>\plan.md` there and the audio is new -> A only.
- Resolve's project = `<video>` or the day project `vid_DDMMYY[_N]` with bin `Chann_N` and its "Edit" -> A `run`;
  anything else -> `vo-sync analyze` (Resolve untouched), ask the user to open the project, then `vo-sync apply`.
  Never put A2 into another project.

### A. Narration -> A2 (background, start it first)

    .venv/Scripts/python.exe -m dvr_cowork vo-sync run "<folder>/mp3" "<folder>/<timestamp>.md"

Bash `run_in_background`, go straight to B, never poll. Narrator from 0:03.6 (user 2026-10-25;
a timestamp file starting elsewhere is shifted as a whole: `first line moved`). It measures each file's speech onset, writes `.work/<key>_mp3/plan.json`,
imports into `4. Audio/Narrator`, backs up "Edit", lays file n on A2 at timestamp n, writes the VI SRT. Read only its
stdout (`report.md` only for flagged rows): `pushed` (file n runs into n+1: timestamps or take need a look),
`boundary_uncertain` (old style: listen), `head_trimmed` / `tail_trimmed` (harmless). A2 not empty / locked, no
"Edit", bad timestamp line -> it stops: report it; never `--force-clear` without the user's yes.

### B. Plan (foreground; one agent per video)

1. **Brief + reads, one turn**: `.venv/Scripts/python.exe .claude/skills/doc-edit/scripts/story.py brief "<folder>"`
   -> `.work/doc_edit/<key>/brief.md` (screenplay with numbered timed sentences `12 01:23.4 4.1s vo2.6 | text` = slot
   until the next sentence + voice length, the rest a voice-free pause; the Visual Edit Plan without its beat table,
   track map, production QA and the body's per-shot cut map: ~180 KB for 60 min = two Reads). Read once:
   `references/edit-grammar.md`, `references/biome-story-pacing.md` (the biome), brief.md. Never open the
   screenplay / timestamp / visual plan files, plan.json, audio, `_library.json`. The Visual Edit Plan's audio
   routing uses other track numbers: take its intent; the layout is SKILL.md "Tracks".
   Species in the library, one call: `plan.py --species lion,hyena,baboon --region <region>` (comma or space list).
1b. **africa only, tag by species** (user 2026-10-20): cast species with < ~60 tagged clips per source ->
   `tag_source.py prepare africa_video africa_ai africa_ai_check --subject <cast,comma> --sample 60` (+ `savannah
   --subject landscape --sample 40` while savannah has < ~150 tagged), then the tag-source loop (Sonnet agents,
   apply in background); B3 needs the apply done. `QUEUED batch_NN` lines = clips already waiting in an older batch:
   tag / apply those first, never a second copy. After B3: a cast species with THIẾU in the intro + story 1 and
   untagged clips left (`untagged clips skipped: ...; of the cast`) -> one more `--sample 60` round, re-plan.
1c. **Story first** (edit-grammar "Story first"): read the WHOLE brief (editorial boundaries, visual and sound
   directions) before the first beat. Part 01 opens with the film and story bible as `#` comment lines (plan.py
   ignores them; they steer your filters), the `# HOOK` blueprint, one `# CAST` per animal the narration names
   (**every** narrated species: an untagged animal counts as a side shot and trips "side shots in a row"), and the
   story lines with their `no=`:

       # FILM question: how does a young wildebeest survive a journey that never stops?
       # BIBLE 1 01:30-06:30 southern plains, calving · [C] calf age=young, [M] mother sex=female · [L] lioness
       #   sex=female · outcome: lunge misses (no out=kill) · never: male lion, river, a herd that "rescues"
       # CAST [L] sp=lion sex=female        <- tokens added to every line (raw lines too) starting with that one tag
       # STORY 1 @16 no=river,crocodile     <- @16 = start of sentence 16 (STORY / INTRO / FAST_UNTIL)

   A line's own `sex=` wins over its CAST (the mother vs the calf). `out=kill` only where the bible says the kill is
   seen. `no=` words match whole words (+ -s / -es / -y / -ed / -ing): `no=male_lion` keeps "female lion",
   `no=cub` also refuses "cubs"; write `sparring`, not `spar`. Multi-species stories: every predator / prey line gets
   `no=<the other story's animals>` from the start. eucalyptus / koala / snow / autumn / zoo... are refused for every
   slot, roads / vehicles / fences for landscape slots (plan.py BIOME_NO, SCENERY_NO).
2. **Beat sheet** (the judgement is Claude's, the mechanical grammar story.py's). Write it in 2-4 parts with the
   **Write tool** (`.work/doc_edit/<key>/beats_parts/01.txt` ...; never a bash heredoc), then
   `.venv/Scripts/python.exe .claude/skills/doc-edit/scripts/story.py expand "<folder>"` -> spec.txt (overwritten:
   later fixes = Edit a beats part + expand again, never spec.txt by hand). Never re-read a part.

       >> 1-15 raw                           <- the hook: spec lines as below ('## n' blocks), copied as written
       >> 16-18 calm A3=water A5=water       <- a beat: sentences, emotion, audio of its first shot; 'turn' = # TURN
       [W] Đàn wildebeest chờ trên bờ | real | sp=wildebeest size=wide count=many    <- pool: story order, cycling
       [W] Một con trượt xuống mép nước | sp=wildebeest act=walk size=medium
       17: [CR] Cá sấu lao lên | real | sp=crocodile act=attack size=medium | A8=splash   <- opens sentence 17
       ~ Mặt nước nâu trống | real | sp=none size=wide set=river                      <- side shot (pause only)

   Shot line = `need | [src] | filter [| audio]` (src default any; a line with an empty audio column ends in `|`:
   new tokens go before that last `|`). Emotion from the screenplay's turn, never the narrator's words: `calm`
   `wonder` `observe` `build` `tense` `chase` `strike` (the decisive contact / reveal / fall) `release` `sad`. expand
   applies edit-grammar: lengths per emotion (~4.5-5 s calm / wonder / sad, ~3.4 observe, shorter and shorter in
   build / chase, a long hold first in release, uneven, '*' on the longest), side shots only in voice-free pauses
   >= 3 s of quiet beats (one at a time, <= 22 %), an A7 cue at each change of emotion (wonder -> wonder, observe ->
   neutral, build / tense -> tense, chase -> chase, release / sad -> calm), strike = A7 off on the shot before (+
   riser after a build) + A8 hit + `# TURN`, chase start A8 whoosh, A6 natural sound from the act (>= 8 s apart). A
   token written on the beat or the line always wins. Yours: one beat per screenplay beat or per change of emotion
   inside it; **at least 4 pool lines** per beat that has more shots than lines (`N:` lines open sentence N only
   and do not count), in story order with changing sizes (establish -> subject -> reaction -> payoff); side lines
   only in quiet beats. A line comes back only with 3 other shots between (`SPACING`): `shot line back within 3
   shots` names the beats with too few lines. Exact lengths, `12x4 same` chains, GFX: a `raw` beat. Spec line format
   (raw beats, and what expand writes):

       # REGION africa                   <- always, first line of part 01
       # END 29:50                       <- target length; omit = last sentence end + 2 s
       # INTRO 0:20                      <- 0:15-2:00 (> 0:30 = cold-open hook, mostly character shots); omit = 0:15
       # OPENING action                  <- optional: landscape (default) | action; with # BIOME savanna|rainforest,
       # BIOME savanna                      # STORY 1 01:30 (chapter starts), # FAST_UNTIL, '# TURN' under a ## N:
       # STORY 1 01:30                      edit-grammar "Opening ... the hook" + biome-story-pacing.md
       # LOOK dry                        <- optional ground look green|dry: first shot takes it, each next shot keeps
                                            the previous one's, desert never; a line's look= wins
       # OPENER Mặt trời mọc trên đồng cỏ | real | sp=none size=aerial no=mountain   <- optional: the 0:00 shot
       # [D] Peters's duiker  [GC] African golden cat
       ## 1
       4 | Wide tán rừng lúc bình minh, sương | real | sp=none size=wide,aerial set=canopy light=golden kw=mist | A3=forest,birds A7=tense
       2 | [D] Cận duiker ngẩng đầu nghe | any | sp=duiker size=close_up act=look set=forest_floor | A6=insects
       * | Lối mòn trống, nắng xiên | real | sp=none set=forest_floor size=medium light=day |

   `dur` s (`*` = rest of the sentence slot + pause, exactly one per sentence; `12x4` / `*x5` = that time as 4 / 5
   shots of the same need + filter, uneven; `12x4 same` = consecutive parts of one clip) | shot needed (Vietnamese) |
   real/ai/any/GFX | filter | audio (edit-grammar). Write part 01 (0:00-1:30 + story 1) first and hardest, by
   edit-grammar "Opening ... the hook": the viewer decides there whether to stay. Videos before 2026-10-24
   (spec_parts/, no beats) keep their hand-written spec: `cat spec_parts/0*.txt > spec.txt`.
3. **Plan**: `story.py expand "<folder>"` (its one line: shots, side share, cues, turns, repeats), then
   `.venv/Scripts/python.exe .claude/skills/doc-edit/scripts/plan.py "<folder>" > <work>/plan_stdout.txt 2>&1`; read
   only the summary `sed -n '1,/character WEAK/p' <work>/plan_stdout.txt` (`region:` must be the command's region).
   With an audio it uses A's measured spans (A not done -> wait for its notification, re-run).
   - Every spec error is printed at once, grouped with `##` numbers; fix them all in one pass (beats parts), expand,
     re-run. Check the `audio:` line against edit-grammar (music coverage, early-ending cues, SXF count) in the same read.
   - `yolo:` (africa: cache only, `--yolo-cached` forces it for amazon; `yolo.py --warm` overnight with the user's
     ok), `semantic:` (e5 tie-break among clips of one band; status stays the tags'), `truth:` (refusals by sex / age
     / resting / kill / no=, picks capped WEAK "kiểm tra", THIẾU they cause: right unless the bible is wrong; never
     drop `sex=` / `out` to fill a slot; untagged clips of that animal -> one more tag round; many sex-unseen WEAK
     picks of a cast animal -> `tag_source.py prepare <roots> --retag action,sex,age,outcome,phase --subject <animal>
     --sample 60` + the tag loop), `hook blueprint:` (ok for an intro > 0:30), `recent ledger` (clips of the last 6
     checked videos never fill slots before 15:00), a shot no clip is long enough for -> 2-3 parts (⧉).
   - Body after story 1: THIẾU slots are filled by the substitute tiers on every run (FALLBACK "late substitute",
     cyan); `--no-body-sub` turns it off (benchmarks). Intro WEAK picks become THIẾU (`intro WEAK -> THIẾU: n`): they
     get prompts, their old pick stays first in the bins' alternatives.
   - Character WEAK slots: keep plan.py's pick, except the intro + story 1 ones: judge them by the opening's hard
     rejects and continuity (`pin=<fragment>` / `pin=none`, re-run). `/doc-edit plan` judges all.
   - Audio files in `.work/library/audio_blocked.txt` (claimed tracks) are never picked. `audio thieu` -> audio-expert
     fetch, or the user says no (remove the token).
   - Outputs `.work/doc_edit/<key>/plan.json` (place input) and `<video>/plan.md` (user table; VO ● = narration). Then
     `.work/tools/library_db.py sync`.

### C. Intro music + re-plan (after A's notification; `references/intro.md`)
`intro.py <key>` (picks a tense, heavy-drum, wild track by itself, never one of this day project's other films or the
channel's last 6, fits it to 0:00 -> story 1), then `plan.py "<folder>"` again: the intro cuts land on its hits /
bars. Read `intro music:` / `intro beat:` (cuts not on a beat = narration onsets: say which to listen to) /
`intro outro:` + the HOOK line. Two films of one day: run C film by film (the second skips the first's track).

### D. Prompts: intro + story 1 (`references/missing-prompts.md`)
`missing.py <key>` lists the THIẾU groups of 0:00 -> story 2 (body slots are filled, never prompted; `--all` /
`--range=A-B` on request). Claude writes `.work/doc_edit/<key>/prompts.txt` by hand (typically 20-60 prompts: no bank
generator), `--check`, `--write` -> `<video>\missing-prompt.csv`. No THIẾU there -> skip, say so.

### E. Place (after C and D; Resolve one video at a time)
`place.py <key>` (no flag; `DVR_CHANNEL=Chann_N` in front in a day project): intro + body on empty tracks (not
empty -> stop, report); black 0:00 -> the impact's hit (A9, blue marker), the opener and the intro music from the hit; intro shots -> bin `7. Open`, music -> `4. Audio/Music`, story 1's bed pre-laps the black.
Then `dvr_cowork gaps` (must say 0 gaps to fill) and `dvr_cowork backups`.

### Reply (Vietnamese), per video, in this order
1. Place: backup, V1 / audio placed, max deviation, failures, red THIẾU markers (count) and the gaps line.
2. A2: sentences placed, backup, flagged lines (number, timecode, flag, what to listen for); or why not yet.
3. Intro music: picked track (top 5 one line each), license line, fit, cuts not on the beat (timecodes to listen).
4. Plan: shots, OK / WEAK / THIẾU / FALLBACK, body fallbacks to look at (scenery stand-ins), THIẾU by character in
   the intro + story 1, audio THIẾU (slot, timecode, sound), the `truth:` numbers in one line. Opening: the hook
   promise and form, the mute test at 0:30 / 1:00 / 1:30 (subject, event, outcome, open question), teaser integrity
   (no preview acts on the anchor animal, no outcome shown), the 1:30 reset, opening THIẾU, how story 1 ends on screen.
5. Prompts: `<video>\missing-prompt.csv` path, count, roles per character ("báo: 3 predator_burst, 1 reaction"),
   relationship_wide clips, biology flags; the user saves the clips into `D:\AI_video\_check` (amazon),
   `D:\AI_video\_africa\_check` (africa, flat) or `D:\AI_video\_himalaya\_check`.
No "next step" line: the user calls the next command (Case 1 / Case 2, SKILL.md).

User edits later -> change the beats part, expand, re-run (`/doc-edit plan`); never hand-edit plan.json. Videos placed
before 2026-10-31 with `--skip-intro` get their intro with `place.py <video> --intro` after `intro.py` + `plan.py`.
