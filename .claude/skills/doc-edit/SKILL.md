---
name: doc-edit
description: Documentary edit in Resolve, three types (footage f_, footage+AI fa_, full-AI a_), any region (amazon / africa / frozen), 8-180 min - footage types: new video(s), plan, missing-prompts (fa_), logo, delogo, ingest, fill, fill-THIEU, after-gen-vid, color, place, reframe, done, push, seo, status; full-AI: voice -> prompts, shots -> film on its timeline, review, done / push. Use for /doc-edit, a pasted `D:\Chann_*\<video>` path, "lên plan / prompt cho shot thiếu", "lấp slot thiếu", "đồng bộ màu", "check folder _check", "đã gen video xong", "/scan-source /tag-source và tiếp", "voice xong / shots xong", "xong video", "up youtube".
model: sonnet
---

# Doc edit

## Pasted path -> the video's folders
1. Video folder = the pasted path or its nearest parent `D:\Chann_*\<video>` (holds `audios\`, `shots\` or
   `.production\`). `_pushed` / `_done` in the path -> stop (CLAUDE.md rule 5).
2. One call maps the media (`_pushed` never entered):
   `find "<video>" -maxdepth 3 \( -name _pushed -prune \) -o -type f \( -iname "*.mp3" -o -iname "*.wav" -o -iname "*.mp4" -o -iname "*.mov" -o -iname "*.zip" \) -printf "%h\n" | sort | uniq -c`
   (zips: list by name, never extract).
3. footage+AI -> `<video>\audios` = the `<audios-folder>` of new-video.md; full-AI -> `references/full-ai.md`.
Media not where the step reads them (MP3s outside `audios\` / `voice\`, shots outside `shots\`, only a zip, two
candidate sets) -> one AskUserQuestion: each candidate (path, count, missing / extra numbers, newest date) + the fix
(copy into the read folder with `shutil.copy2`, source kept, or the user moves it). Never pick a set by its name.

## Video type first
`.venv/Scripts/python.exe -m dvr_cowork profile detect "<video>"` -> `type` + `engine` + `region` (prefix `f_` / `fa_` /
`a_` of the folder, else the descriptor / files of an older film; `unknown` -> ask).
- **full_ai** (a_, old full_ai_mountain) -> `references/full-ai.md` only (`dvr_cowork profile context "<video>" --phase <step>`).
- **footage_ai** (fa_, old footage_ai_long) -> everything below; AI <= 40 % of the footage time (plan.py, every region).
- **footage** (f_) -> everything below without AI: plan.py leaves AI clips out, no missing-prompts / Case 1 / ingest /
  after-gen-vid / logo; THIẾU after the plan -> tell the user, then `fill-THIEU` or `fallback-species` on their word.
- **ocean_long**: disabled, the router refuses it.
- Neither / bare `/doc-edit status`: `state.py status` + `dvr_cowork ai status <folder>` of each video with `.production\`.

## Working rules
- The user calls each step; no "tiếp" chain, no "next step" line. Chains: `/scan-source /tag-source và tiếp` =
  `ingest --fill` -> stop for review; `/doc-edit after-gen-vid` (below).
- Tokens: run the step's script, read only its summary stdout (`| tail` / `grep`); never dump candidate lists, never
  explore code to run a step. Media is rendered only by `done` / `push`.
- Replies in Vietnamese, short: result lines, problems, what the user must check.
- Resolve steps need the day project `vid_DDMMYY` open (`dvr_cowork info` once per session; else stop, ask). One failing
  clip never stops a step (name it).
- Calling a step's command = the yes for the change its row names (CLAUDE.md rule 2); other destructive flags
  (`--replace`, `--force-clear`) still need an explicit yes.
- Parallel: narration A in the background while B plans; tag batches = up to 4 background agents. Never poll.
- One Resolve writer at a time (`backup_timeline` lock): `another Resolve write is running` -> wait for its notification.
- **Frame check** (after `color` / `after-gen-vid`, user 2026-11-14): `DVR_TIMELINE=channN_vidK dvr_cowork frames --at
  <>= 12 positions: >= 2 per story, AI clips, story joins> --stats --gemini`. Claude Reads (max 6 per pass, a second
  pass when more; never drop one): every `FLAG` / `?` still, every still whose stats stand out (cast, luma, sat vs the
  others), and 2 `OK` stills of different stories as control. A control that is wrong = Gemini missed it -> Read every
  remaining still, say so. Gemini error / no verdicts -> Read 6 stills (old way). Reply: frames checked (Gemini N,
  Claude K), flags confirmed / rejected, fixes.

Tracks of `channN_vidK`: A1 empty (older videos keep theirs) · A2 narrator · A3/A4 bed (alternating, 4 s crossfades,
~-32 LUFS) · A5 Ambience 3 (extra bed, story-1 pre-lap, music crossfade tails) · A6 natural · A7 music · A8 natural SFX · A9 designed SFX
(0:00 riser -> impact). Bins: `7. Open/vidK`
= that video's intro shots (0:00 -> story 1; one sub-bin per video, user 2026-11-09; plan.py prefers only the clips the
user put in its own sub-bin, not `open_placed.txt`); every
music / sound file -> `4. Audio/*`.

## Day project
Project `vid_DDMMYY` holds every video of that day: top bins `Chann_N` with sub-bins 1-7; one timeline per video
`channN_vidK` (K = the folder's `_K`) in `Chann_N/6. Timeline`. A missing one is created as a copy of the template
timeline `channN_vidK` of that channel's bin (empty only when the bin has none). The channel comes from the path
(`D:\Chann_2_*\...` -> `Chann_2`): vo-sync, place.py, intro.py, ledger, after_gen.py set it themselves; any other Resolve
command runs with `DVR_TIMELINE=channN_vidK` in front. Same folder name in two channels: work key `<video>__Chann_N`
(`dvr_cowork/videokey.py`); a bare name needs `DVR_CHANNEL=Chann_N`. File work of several videos in parallel agents;
Resolve writes one at a time. Intro rule (user 2026-11-09): no intro shot (opener included) of a footage-type video may be in
the intro of another video of its channel within 7 days (plan.py `intro week` line + guard; `ledger.intro_week`),
planned-only videos and "7. Open" clips included; never lift it by hand.

## After the prompts: Case 1 / Case 2 per video
`/doc-edit <audios...>` ends when the video is placed and `missing-prompt.csv` (intro + story 1) is out: reply THIẾU
count + timecode ranges + prompt numbers, then wait (never a fallback; Claude never opens Muse / Chrome or generates
footage). State: `python -m dvr_cowork.jobs status`. The user decides per video; record it with
`jobs decide <video> ingest|fill-existing "<their words>"`:
- **Case 1** ("đã generate / lưu clip vào `shots`") = `/doc-edit after-gen-vid <video>`. Clip -> slot = its name
  (`shot_id` of `missing-prompt.csv`); `still copying` -> wait; `broken` -> list for the user; a clip not named after
  this video's prompts -> ask whose. One home (user 2026-11-13): every generated clip of a video is in its own
  `<video>\shots`: plan.py puts each on its own slot only (any slot, no tags), never filed, never another slot
  (`shots/: N one-time clips`). after-gen-vid never reads the region `_check`: that is the shared library folder
  (filed by `/doc-edit ingest`, reused across videos under the ledger rules).
- **Case 2** ("không generate nữa, fill THIẾU bằng footage có sẵn") = `/doc-edit fill-THIEU <video>`, no second ask.
  Fill-THIEU = 100 % of the slots: strict pass, then soft gates dropped (sex / age / kill / resting / xact; FALLBACK
  cyan); hard gates never loosen (`no=`, biome, day / night, species tier order). Reply from `jobs fill-report <video>`
  (tiers A exact / B strong / C context / D last resort, `any light` flags, THIẾU + refusals).
- Generated clips (`jobs check` accepted them for this video): with `--sub-broad` every one goes on its own slot
  (start nearest its prompt's `tc_in`, whole clip, also a `pin=none` slot; filed or still in `_check`, issues ignored:
  `_check` ones WEAK + note; logo / text ones stay out -> delogo). plan prints `generated: N/M usable, K on V1, unused ...`.
- "clip X sai loài" -> `jobs reject <video> "<path fragment>" "<why>"`, then the user's step as usual.
- Mixed videos: each its own case and channel; a clip never goes to another video's bin / timeline.
- Fill is never a yes to render. Cost check: `jobs metrics --days=7`.

## Region
The folder name says it (`fa_africa_*`; old `africa_*`, `himalaya_*` = frozen, `congo_*` = amazon); else ask. Spec first line
`# REGION <region>`; plan / fill / prompts use only that region's footage.
| region | footage roots |
|---|---|
| amazon | `Z:\Unseen\Amazona\video` + `D:\AI_video` (root `ai`) |
| frozen | `Z:\AI Document` (root `frozen_video`, real footage despite the name; species folders) + `D:\AI_video\_frozen` (root `frozen_ai_check`: new clips in `_check`, filed by `organize.py --frozen`) |
| africa | `Z:\Unseen\Động vật\AAA Trên cạn` (its `AI_copyright\` = AI; `bản quyền\` NEVER used) + `Z:\Unseen\savannah` + `D:\AI_video\_africa` (root `africa_ai_check`: new clips in `_check`, filed by `organize.py --africa`) |
- Audio roots shared: `Z:\Unseen\Amazona\audio`, `Z:\Unseen\SFX`, `D:\Audio_lib`. Plan prints `audio thieu` ->
  audio-expert fetch, plan again.
- Africa footage is tagged per species when a film needs it (new-video.md B1b).

**Story first**: shots show what the story must make the viewer understand (bible + `# HOOK` blueprint -> shot lines
with truth tokens `sex=` `age=` `out=kill` `xact=` `no=` that plan.py enforces; no true clip = THIẾU). `story.py brief`
-> beat sheet -> `story.py expand` -> spec.txt (new-video.md B1-B2). Before a spec read
`references/biome-story-pacing.md` (`# BIOME savanna` / `rainforest`). Opening: black + riser -> impact at ~0:01, the
epic opener on the hit, teaser to ~1:30.

## Commands
| command (user's words) | runs | reply |
|---|---|---|
| `/doc-edit <video folder>` of a full-AI film | `references/full-ai.md` from its state | that file's replies |
| `/doc-edit <audios-folder> [...]` | `references/new-video.md` per video: preflight -> A narration (background) + B plan -> C intro music + re-plan -> D prompts (intro + story 1) -> E place on empty tracks; several folders = one agent per video for B + D, A / C / E one after the other | new-video reply |
| `/doc-edit after-gen-vid <video>` ("đã gen video xong") | ONE `after_gen.py finish <video>` (run_in_background): jobs check of `<video>\shots` only (user 2026-11-13; no tagging; copying / broken -> STOP) -> plan `--sub-broad` -> place `--fill` -> `gen_swap.py --apply` (V1 items at a generated clip's slot replaced, Orange, backup) -> gaps -> fill-report -> light.py plan + apply (backup) -> frame check (Working rules); the command = the yes for all of it | one reply: shots clips checked (stray / broken), generated used / unused, placed, swapped, THIẾU left, color spread, frames checked, backups |
| `/doc-edit plan` | B2-B3 of new-video.md (`story.py expand` when beats exist) with the WEAK pin round | B reply part 3 |
| `/doc-edit missing-prompts [mm:ss-mm:ss]` | `references/missing-prompts.md` (default intro + story 1; `--range=A-B`, `--all`) | prompts reply |
| `/doc-edit logo` | `hide_logo.py "D:\AI_video\_check"` (africa: `_africa\_check`) | LOGO / SUSPECT + `.work\hide_logo\check_list.txt` |
| `/doc-edit delogo` | `hide_logo.py --list` (background) -> `_nologo` copies (africa: env `NOLOGO_DIR`) | done, REVIEW FIRST, FAILED |
| `/doc-edit ingest` | scan root (`ai` / `africa_ai_check`) -> tag-source prepare / agents / apply -> `organize.py [--africa] --apply` -> scan | tagged, filed, kept in `_check` (why) |
| `/doc-edit fill [--sub mm:ss]` | `plan.py <audios> [--late-sub --late-sub-t=<s>]` or `--sub-all` -> `place.py <video> --fill` (`references/place-fill.md`) | THIẾU left, placed, backup |
| `/doc-edit fill-THIEU [<video>]` (only on this command / phrase) | `plan.py <audios> --sub-broad` -> `place.py <video> --fill` -> `gen_swap.py <video> --apply` when plan printed generated clips not on V1 | filled (timecode -> clip, tier), off-light ones, THIẾU left |
| `/doc-edit fallback-species [<video>] [mm:ss-mm:ss]` | `fallback_swap.py <video> --range=A-B` dry run, then `--apply` (backup; hand-changed + intro fade shots untouched; Teal) | swapped, left alone, KEEP |
| `/doc-edit ingest --fill [--sub mm:ss]` | `ingest` then `fill`, then stop for review | tagged, filed, THIẾU left, placed |
| `/doc-edit place` | `references/place-fill.md` | backup, placed, deviation, gaps, audio, markers |
| `/doc-edit color` ("đồng bộ màu") | load `/colorist`: `light.py plan` -> golden-grass preview -> `apply` (backup) -> frame check (Working rules) | spread before -> after, AI toned down, frames checked |
| `/doc-edit done [<video>]` ("xong video") | `ledger.py done <video>` (`references/done.md`): ledger, `audio_licenses.md` when missing (every audio file of the timeline, user asks again -> `--licenses`; alone: `ledger.py licenses <video>`), `shots\intro.mp4` -> `7. Open/vidK` + timeline `master_channN_vidK` (intro + nested `channN_vidK`; stale one rebuilt), render `Done_<video>.mp4`; no upload, no SEO | licenses (count listed), `master:` / `stale:` lines, `render:` line |
| `/doc-edit push [<video> ...]` ("up youtube") | SEO per video (`dvr_cowork youtube seo`, pick a true title `--pick N`) -> ONE `ledger.py push <video> [<video> ...] [--publish-at ...]` (run_in_background): renders one by one (skipped when done), uploads side by side (max 3) | per video: 3 titles + the one used, render, `youtube:` link + MB/s |
| `/doc-edit seo [<video>] [--force]` | `python -m dvr_cowork youtube seo <video folder>` | 3 titles, FLAG lines |
| `/doc-edit status` | `state.py status` (files only) | the table |
| `/doc-edit reframe [<video>]` | `references/reframe.md` | |

Paths: `plan.py` takes `<video>\audios`; `place.py`, `gen_swap.py`, `fallback_swap.py`, `after_gen.py` take `<video>`.

## After a step
- Every place / fill / swap / color apply leaves a backup timeline: `dvr_cowork backups` (one line); a kind > 3 ->
  offer `dvr_cowork backups --keep 3 --apply` (user yes).
- Benchmark after a rule change: `scripts/bench_story_first.py <video>`; `plan.py <folder> --spec=<file> --out=<dir>`.
- `state.py diff <video>` only when the user asks or a step must not undo hand edits it cannot see.
- Update `handoffs/current.md` (the video's line in place).
