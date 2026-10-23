## New video: `/doc-edit <audios-folder> <amazon|africa>`

Region missing or another word -> ask which, stop (SKILL.md "Region").

`<video>` = the folder's parent (`D:\Chann_1_shadowCanopy\amazon_2\audios` -> `amazon_2`); outputs land in that
video folder. Two jobs in parallel: the narration is one background command (A), the plan + prompts (B) are what
the user waits for, so B gets the attention and A never blocks it.

**0. Preflight, one call:** `ls "<folder>"` + `ls "<video>"` + `.venv/Scripts/python.exe -m dvr_cowork info`. The
folder needs (names case-insensitive) one `*timestamp*.md` (`[MM:SS] sentence` / `[HH:MM:SS]`, decimals ok, `#`
lines ignored; bilingual `## English` + `## Vietnamese` parts (user 2026-10-20): English = A2 + plan, Vietnamese =
`<video>\subtitles_vi.srt` placed on Subtitle 1 by vo-sync, same line count) and one `*screenplay*.md` (`script*.md` / `kịch_bản.md` are not read); missing or several -> say
which, stop. Then:
- Narration = sub-folder `mp3\` with one file per sentence, `1.mp3`, `2.mp3` ... = timestamp line 1, 2 ... (user
  2026-10-16; already cut, nothing to blade). Old style (one narration `.mp3`/`.wav` in the folder, Whisper cuts it)
  still works when there is no `mp3\`.
- No narration yet (the user often plans before the ElevenLabs audio exists) -> B only; plan.py estimates the
  speech spans from the text. The reply says A2 waits for the audio.
- `<video>\plan.md` already there and the audio is new -> A only (the plan is done; `/doc-edit plan` afterwards
  only if the user wants exact VO ● marks).
- A: Resolve's current project = `<video>` (case-insensitive; channel form `c2_africa1` = folder `africa_1`, the
  user names it in the command) with a timeline "Edit" -> `run`; anything else
  (closed, other project) -> `analyze` (Whisper only, Resolve untouched) and the reply asks the user to open
  project `<video>`; on their "ok" run `vo-sync apply`. Never put A2 into another project.

### A. Narration -> A2 (background, start it first)

    .venv/Scripts/python.exe -m dvr_cowork vo-sync run "<folder>/mp3" "<folder>/<timestamp>.md"
    (old style: "<folder>/<audio>" instead of "<folder>/mp3")

Bash `run_in_background`, then go straight to B; never poll it. With `mp3\` there is no Whisper: files 1..n must
match the n timestamp lines exactly (else it names the missing/extra numbers and stops), each file's speech onset
is measured, `.work/<video>_mp3/plan.json` written in seconds (all B3 needs); then it imports the files into bin
"4. Audio/Narrator", backs up "Edit" and lays file n as one A2 item with its onset on timestamp n. (Old style: Whisper
(cached) -> `.work/<audio stem>/plan.json`, one bladed source.) When it finishes read only its stdout (`report.md`
next to that plan.json only for flagged rows). Flags: `pushed` (file n is longer than the gap to n+1, it starts
late: the timestamps or the take need a look), `boundary_uncertain` (old style: listen to that cut),
`head_trimmed`/`tail_trimmed` (harmless). A2 not empty / locked, no "Edit", bad timestamp line -> it stops: report it
(the line for a bad timestamp); never `--force-clear` without the user's yes.

### B. Plan + missing prompts (foreground)

1. Read once, in one turn: `references/edit-grammar.md`, the screenplay, the timestamp file. Never plan.json, audio,
   `_library.json`. The screenplay stays in context for B4: don't re-read it. Then one call for the numbers the spec
   needs: `plan.py --species <cast words> --region <region>` (species tags of that region's library per source: pick
   the exact `sp=` tokens, e.g. `sp=giant_otter,otter`) and the slot / speech length per sentence from A's plan.json (a 3-line python print).
1b. **africa only, tag by species** (user 2026-10-20: cheap but good): the Africa library is tagged only where a film
   needs it. For the cast (English folder species: `lion`, `cape buffalo`... = scan_source AFRICA_FOLDERS values)
   whose tagged count from B1 is < ~60 per source:
   `tag_source.py prepare africa_video africa_ai africa_ai_check --subject <cast,comma> --sample 60` (60 untagged clips
   per root and species, spread over the folder; plus `savannah --subject landscape --sample 40` while savannah has
   < ~150 tagged), then the tag-source loop (Sonnet agents, check, apply in background). Plan B3 needs the apply done.
   After B3: a cast species with THIẾU / WEAK slots and untagged clips left (`untagged clips skipped: ...; of the cast`)
   -> one more `--sample 60` round of that species and re-run plan BEFORE writing prompts: footage that exists is
   cheaper than generating it.
2. Write the spec in 3-5 parts with the **Write tool** (`.work/doc_edit/<video>/spec_parts/01.txt` ...; a bash heredoc
   of ~200 Vietnamese lines broke on amazon_2), then `cat spec_parts/0*.txt > spec.txt`; later fixes = Edit on a part
   (or one `sed` over the parts for a token added everywhere) and the same `cat`. Never re-read a part. Format:

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
   shots of the same need + filter, uneven lengths: long voice-free slots, e.g. africa_1's 45 s scenes) | shot needed (Vietnamese) |
   real/ai/any/GFX | filter | audio (formats: edit-grammar.md). Write part 01 (0:00-1:30 + story 1) first and
   hardest, by edit-grammar "Opening ... the hook": the viewer decides there whether to stay.
3. `.venv/Scripts/python.exe .claude/skills/doc-edit/scripts/plan.py "<audios-folder>" > <work>/plan_stdout.txt 2>&1`
   then read only the summary: `sed -n '1,/character WEAK/p' <work>/plan_stdout.txt` (its `region:` line must be the
   command's region; the WEAK candidate list below
   it is ~150 lines: open it only in `/doc-edit plan`). With an audio it uses A's measured spans (not there yet -> it
   says so: wait for A's notification, re-run); without, the `narration:` line says the spans are estimated.
   - Multi-species leaks (amazon_2: a caiman in a jaguar hold, a jaguar in a caiman shot): give each predator / prey
     line `no=<the other story's animals>` from the start. Temperate scenery (autumn, snow, conifer) is excluded by
     plan.py itself.
   - Prints ALL spec errors grouped with `##` numbers; check the `audio:` line against edit-grammar (music
     coverage, early-ending cues, SXF count) in the same read. Fix everything in one pass of targeted edits, re-run.
   - YOLO-World on unmeasured clips of the spec's species (cache `.work/library/yolo.json`, normally warm via
     tag-source); many measured now -> run in background. Read only the `yolo:` line. Africa (tagged `--no-yolo`,
     4K ProRes on the NAS, ~4 clips/min, africa_1 2026-10-22: 6 h unfinished) -> `plan.py <folder> --yolo-cached`
     (cache only), and `yolo.py --warm` overnight when the user agrees.
   - Intro beat cuts: the intro cuts move onto the hits / bars of the intro's A7 music (`beats.py`, edit-grammar
     Intro). Read the `intro beat:` line: "not on a beat" cuts or "no A7 music under the intro" -> fix the spec.
   - Semantic tie-break (default; `--no-sem` = tags only): multilingual-e5-small compares the shot text with each
     clip caption and picks among clips of the same band; status OK / WEAK / THIẾU stays the tags'. Caption vectors
     cached in `.work/doc_edit/caption_emb_e5small.npz` (new captions ~15 s). Read only the `semantic:` line.
   - A shot no clip is long enough for -> 2-3 parts from different clips (⧉); audio stays on part 1.
   - Ledger: clips of the last 6 checked videos of the workspace are never matched; `recent ledger` line = slots
     lost, by character. Inside one video a clip may serve 3 slots over Edit + Open together, each a different part,
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
4. Missing prompts: read `references/missing-prompts.md` and do its steps 1-5 on this plan, the screenplay from B1
   -> `<video>/missing_prompts.txt`. No THIẾU slot -> skip, say so.

User edits later -> change spec.txt and re-run (`/doc-edit plan`); never hand-edit plan.json.

### Reply (Vietnamese), in this order

1. The two files: `<video>\plan.md` and `<video>\missing_prompts.txt` (full paths).
2. A2: sentences placed, backup, flagged lines (number, timecode, flag, what to listen for); or why it is not placed
   yet (no audio yet -> "thả file narration vào <folder> rồi /doc-edit <folder>", still running, other project
   open, error).
3. Plan: shots, OK / WEAK / THIẾU / GFX, species missing, THIẾU and ledger-lost by character, the audio line,
   character WEAK count (kept as chosen), every audio THIẾU (slot, timecode, sound): no substitute; the user
   downloads one or says no (-> remove that token). Opening: the mute test at 0:30 / 1:00 / 1:30 in one line each
   (subject, event, outcome, open question), opening THIẾU, and how story 1 ends on screen.
4. Prompts: count, per character roles (e.g. "báo: 3 predator_burst, 1 reaction"), skipped coverage and why,
   relationship_wide clips, biology flags; the user saves the generated clips into `D:\AI_video\_check` (amazon) or
   `D:\AI_video\_africa\_check` (africa, flat; ingest files them into `_africa\<species>`).

### Place (same run)
As soon as A2 is on and plan.json written: `place.py <video>` (empty tracks; not empty -> stop, report). Send the two
file paths in a message the moment missing_prompts.txt exists (the user starts generating), then go on. Place waits
for A to finish (the two never write to Resolve at once); Resolve not on `<video>` -> no place, say so. The reply
starts with the place lines (backup, V1 placed, red THIẾU markers), then parts 1-4 above. No "next step" line: the
user calls the next command.

