# doc-edit · full-AI 8-15p (any region, every shot generated)

`$E8` = `.venv/Scripts/python.exe -m dvr_cowork ai <cmd> "<video>"`, `$Y` = `.venv/Scripts/python.exe -m dvr_cowork
youtube <cmd>` (one CLI, user 2026-11-05). None of the footage+AI flow applies: plan.py, place.py, intro.py, vo-sync,
light.py / color, Gemini, scan / tag, `_check`, Case 2, the day project. Always **Case 1**: every slot is empty, the
user generates every shot. `python -m dvr_cowork profile context "<video>" --phase voice|ingest|intro|sound|done`
prints the film's pinned numbers (runtime, body, intro cut range), stage and blockers in one line.

**Profile per film** (`video.project.json` + `.production/profile.lock.json`, written by `$E8 init`): the engine reads
the pinned snapshot, never the workspace profile. v2 (user 2026-11-05): 8–15 min (default 10), regions himalaya /
amazon / africa, intro 30 s of 2–4 s cuts from reviewed body sources, no animal contact / stare-down (`build`).
Films pinned to v1 finish on v1. Descriptor / snapshot mismatch or a disabled profile -> stop before any write; never
re-pin by hand. **Region prompt locks**: `prompts` stops when `dvr_cowork/fullai/config.toml` has no
`[prompts.regions.<region>]` (amazon / africa until the user writes them): tell the user, never invent the locks.

## Contract (CLAUDE.md rule 1 for this type)

- **Project** = the day project `vid_DDMMYY_N` of the folder name (`<region>_DDMMYY_N` -> `vid_DDMMYY_N`, shared with that
  day's footage+AI films; films named `vid_DDMMYY_N` keep their name; `resolve_project` in story.json overrides). Per channel bins
  `1. Other_roll`, `2. Attack_roll`, `3. Run_roll`, `4. Audio/{Narrator,Ambience,SFX,Music}`, `5. Graphics`,
  `6. Timeline`; no `7. Open` (footage+AI only). Shots -> `1. Other_roll`, narrator -> `4. Audio/Narrator`, intro song
  -> `4. Audio/Music`, wind / birds -> `4. Audio/Ambience`, SRT -> `5. Graphics`. One timeline **"Edit"** in
  `Chann_N/6. Timeline` (found by that bin; older projects `4. Timeline`) + backups `Edit_bak_*`. Never write into
  another channel's bin or Edit; no Edit in this channel but another has one -> the user creates the empty one by hand.
- **Tracks**: V1 picture · A1 the sound of every V1 shot, the **whole** runtime, −12 dB · A2 narrator · A3/A4 wind bed
  per scene after the hook, alternating, 4 s crossfades · A5 birds on calm shots · A7/A8 intro song under the 30 s
  hook · A9 unused. Starting gains in `dvr_cowork/fullai/config.toml`, not a loudness guarantee. Fade handles 2 s.
- **Runtime** = 30 s hook + 30 s setup + body; every body shot 6–9 s. Hook: 8–15 cuts of 2–4 s (10–12 best) tiling
  30 s minus the black gap, from body sources, each optionally retimed 1.1–1.25×. Black gap (user 2026-11-06, as
  the 1h films): V1 empty for `[intro] gap_black_s` (0.6 s, `config.toml`) at the window's end, between the last
  intro cut (to black 1.5 s) and story 1 (from black 2.5 s); `done` allows only this V1 gap. Every black fade on V1
  (0:00, intro end, story 1, last shot) is set on that shot's A1 too (user 2026-11-06). Sound bridge: A5
  pre-lap = story 1's bed (`beds.json` first scene) from `[audio] prelap_s` (4 s) before the gap to 4 s into the
  story, 4 s fades, placed by `music` / `finish`; no birds there. A7 hand-edited -> `music` refuses (no
  `--replace`): `.work/scripts/add_prelap.py <video> <song> --apply` adds only the pre-lap.
- **Files**: source `.production/story.json`; `audios/` = `screenplay.md`, `timestamp.md`, `transcript.md`,
  `visual_plan.md`; narrator `voice/1..N.mp3` (legacy `audios/mp3/`); shots `shots/1..M.mp4`; prompts
  `missing-prompt.csv` (19 columns, `shot_id` = file number, `dur_s` = slot + handle) + `lock-assets.md`. The only
  prompt writer: `$E8 prompts` (never missing.py).
- **Preservation**: numbered file ID = issued prompt ID, never sort order; ID = the file name's trailing number
  (user 2026-11-06: `7.mp4`, `shot_007.mp4`, `shot-7.mp4`, `S07.mp4` = 7; `.mp4` / `.mp3` alike); duplicate IDs
  (`7.mp4` + `shot_007.mp4`), 0, missing / extra numbers, corrupt,
  still-copying or undersized files are refused; user media is never renamed. Resolve writes are additive, backed up,
  and hold the one writer lock `.work/automation/resolve_writer.lock` (busy -> wait, never retry in a loop). Never
  clear, ripple, delete, undo, overwrite or silently re-plan. On failure: report backup + journal, never "done".
- Calling a step = the yes for its documented additive changes and backup (rule 2); one named shot never authorizes
  a rebuild.

## `/doc-edit <video>` — find the folders, then resume

| need | engine reads | look also in (report only) |
|---|---|---|
| narrator `1..N.mp3` (N = voice blocks) | `voice\`, else `audios\mp3\` | `audios\*.mp3`, `*.zip`, other folders of numbered MP3s |
| shots `1..M.mp4` (M = prompt rows) | `shots\` only | `shots_old\`, `shots_v*\`, `clips\`, `*.zip`, other folders of numbered MP4s |

Incomplete set -> candidates + the copy fix in one AskUserQuestion. Then `$E8 status` and run the stage:
- no `voice_receipt.json` -> **A. Voice**.
- `WAITING_FOR_SHOTS` / `WAITING_FOR_REDO` / `READY_TO_ASSEMBLE` with `shots\` complete -> **B. Shots**; incomplete
  -> list the missing numbers, stop.
- `WAITING_FOR_REVIEW` or later -> `$E8 check`, wait for `/doc-edit done <video>`.

### A. Voice -> prompts (one call, then stop)

`$E8 info` (Resolve up, project, fps; else say what to open), then `$E8 voice-ready --apply` = conform -> A2 + SRT
(backup, verified) -> prompts for **every** non-hook slot. Idempotent; never ask for a separate prompts call.
- Conform lists **every** overflowing scene / long pause in one run: no trimming, stretching or guessing. Re-time
  recipe (one question, no re-recording): move whole seconds between shots of the scene and its neighbours (each
  6–9 s, total unchanged); hook / setup gaps ≤ 6 s get `pause_limit_s` + `pause_reason`. Dry-run on a copy
  (`story.compile_story(copy, durations)`), offer the passing plan, after the yes back up `story.json`, rerun.
- Reply: runtime, A2 count, occupancy, backup, prompt count, save folder `<video>\shots` (`1.mp4…M.mp4`). **Stop**:
  "prompts issued", never "shots generated".
- New prompt text on the same slots: edit `story.json` keeping every `duration_s` and voice block -> `$E8 conform`
  -> `$E8 voice --apply` -> `$E8 prompts --reissue` (old manifest kept); list the numbers to regenerate.

### B. Shots -> the whole film on the timeline (one pass, then stop for review)

User 2026-11-06: "shots generated" = steps 1-4 in one go (story V1/A1 -> hook -> every audio track -> finish),
never a stop after step 1; one reply at the end. The user's OK on that review = `/doc-edit done` + upload below.

1. `$E8 shots-ready --apply` = ingest (exact IDs, full decode, duration, aspect, audio, hashes; unchanged files
   reused; other names in `shots\` -> stop, the user moves them) -> body on V1 / A1 -> contact sheets.
2. **Hook review** (Claude views the sheets; never set `hook_ok` without viewing): every spoiler-free slot with a
   `hook_role` gets `hook_ok` + reviewer, notes, evidence and the clean range `hook_start_s` / `hook_end_s` (peak
   action, no near-contact, no first-frame cut; `hook_speed` 1.1–1.25 only where gait / anatomy stay natural).
   Mark 8+ (10–12 best). The hook = the 30 s highlight, never a resolution or a generic vista; roles round-robin,
   one cut per source, ordered threat → vulnerability → pursuit → obstacle → unanswered; retimed cuts have no A1.
   Too few clean sources -> widen ranges or mark more before asking for a new shot.
3. **Sound picks** (only licensed files: `<name>.license.txt` / Pixabay note beside it in `D:\Audio_lib`,
   `D:\Music\pixalbay`; a missing sound -> audio-expert fetch from Epidemic without asking, then `index.py`):
   - intro song: one tense track ≥ ~60 s with a real ending from `D:\Audio_lib\intro`; `music` cuts it itself (first
     sound at 0:00, drum / bass climax in the middle, the song's own ending into the first story shot, beat-grid
     cuts, 1 s crossfades A7 -> A8 -> A7). `climax_drive` < 0.7 -> a heavier trailer-drums track.
   - `.production/beds.json` `{"S02": "<wind file>", ...}`: one wind per scene after the hook, by feel (calm = soft,
     chase / storm = gusts or blizzard, ridge = thin high wind, ice = creaking); neighbours never share a file.
   - `.production/birds.json` `{"<prompt id>": "<bird file>"}`: calm shots only (traverse, rest, reunion, the end;
     never chase / attack / fall), 2–3 recordings rotated.
4. `$E8 finish "<video>" "<song>" --apply` = hook -> intro cuts on V1 -> song A7/A8 + beds A3/A4 + birds A5 -> check.
   Black fades as footage+AI (0:00 from black 1 s, first story shot 2.5 s, last intro cut to black 1.5 s, last shot
   3 s): report its `black fades` line. Swap a sound: edit the json / pick another song,
   `$E8 music "<video>" "<song>" --replace --apply`. A new hook over a placed intro = `$E8 assemble --apply --rehook`
   (destructive: list the intro items, user yes, backup first).
5. Reply: placed / verified, hook picks, song + bpm + cuts + climax, beds per scene, bird slots, backup, what to
   listen to (`nghe lại 0:08`). **Stop for the user's review**: no colour, no render, no voice / story change.

Redo shots ("làm lại 3, 7, 12"): `$E8 prompts "<video>" --only 3,7,12` (same IDs, same text; plain `prompts` brings
the full list back). The user overwrites `shots\N.mp4` -> `shots-ready --apply` + `finish ... --apply` again
(unchanged items stay); Resolve may show old frames until the clip is relinked (Media Pool -> Replace Clip).

## `/doc-edit done <video>` (user approved; no colour step)

`$E8 check`, then `$E8 done --apply`: validates the **live** Edit (hand edits kept), renders with `YouTube 1080 HEVC`,
never overwrites (`_v2`), returns a job ID. Poll `$E8 render-status` until VERIFIED; RUNNING is never done.

**YouTube** (user 2026-11-06: part of `done` for full-AI; the user's OK on the review = the upload yes; a time
given -> `--publish-at <ISO time +07:00>`, none -> private): `$Y seo "<video>"` prints film facts + a trend digest (~200 quota units, cached 7 days; thin
digest -> once more with `--query "snow leopard mountain goat"`). Write `.production/seo_draft.json`:
`{"titles":[3 full titles],"pick":1,"hook":"2–3 sentences","summary":"2–3 sentences, no payoff","tags":[20–30],
"hashtags":[...],"chapters":[optional]}` -> `$Y seo "<video>" --write` builds `youtube_meta.json`; fix every FLAG.
- Titles, plain title case, no caps / emoji / colons: **Clash** `<Predator> Hunts / vs <Mother|Lone|Young> <Prey>
  [and Her Baby] on a <Deadly Terrain> | <label>` or **Vulnerable moment** `A <Baby|Young|Lone> <Prey> <situation>…
  Can It <concrete test>? | <label>`. Label: `Wildlife Documentary`, `Wild Animals` or the channel's name. Story
  line ≤ ~80, whole ≤ 100 chars. True to the film, payoff hidden, searchable common names, never a competitor's
  title. Tags: pair tags, species, then niche tags; never other channels' names or absent animals.
- `$Y upload "<video>"` = the preview (channel from `Chann_N`); the user's yes to that exact preview -> record its
  `request_hash` as `approved_request_hash` in `youtube_meta.json`, `$Y upload "<video>" --apply`. Private, AI
  disclosure always on; `--publish-at 2026-11-03T18:00:00+07:00` only on request. An UNKNOWN result blocks retries
  until reconciled in Studio. After upload: thumbnail + "Altered content" in Studio.

## Recovery (on a failure only)

`voice` / `assemble` are resumable and additive: an item with the same path / range / source-in is kept, a
conflicting one aborts before anything is written; every append is journaled and read back. Partial result -> read
journal + backup, never clear or auto-restore. Source-end mismatch -> fix `[resolve] source_end` in
`dvr_cowork/fullai/config.toml` against `Scripting/README.txt`, the user picks the recovery. Issued prompt IDs are
never redefined; new media hashes reset that clip's approval. SRT append varies by Resolve version: always create +
import under `5. Graphics`, report manual placement when it fails. Resolve API gotchas: the resolve-api skill.

## After each step

One line for the video in `.work/knowledge/handoffs/current.md`. Short Vietnamese reply: results, problems, what the
user must check.
