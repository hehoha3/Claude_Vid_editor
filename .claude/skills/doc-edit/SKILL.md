---
name: doc-edit
description: Documentary edit in Resolve for two video types of any region (amazon / africa / himalaya) - footage+AI 1-3h (footage library + AI clips; new video(s), plan, missing-prompts, logo, delogo, ingest, fill, fill-THIEU, color, place, reframe, check-timelines, done, seo, "color n done", status) and full-AI 8-15p (every shot generated, `dvr_cowork ai`; voice -> prompts, shots -> whole film on Edit, review, done). Use for /doc-edit, a pasted video path `D:\Chann_*\<video>` (finds its audios / voice / shots folders itself), "lên plan / prompt cho shot thiếu", "lấp slot thiếu", "đồng bộ màu", "check folder _check", "/scan-source /tag-source và tiếp", "voice xong / shots xong", "xong video".
---

# Doc edit

## Pasted path -> find the video's folders first (user 2026-11-04)
The user often pastes just a path (`/doc-edit D:\Chann_1_shadowCanopy\vid_021126_1`), sometimes a sub-folder or a
file inside it. Work out the folders yourself instead of asking for the "right" path:
1. Video folder = the pasted path, or its nearest parent that is `D:\Chann_*\<video>` (holds `audios\`, `shots\` or
   `.production\`). `_pushed` / `_done` in the path -> stop (CLAUDE.md rule 5).
2. One call maps where the media really sit (count per folder, `_pushed` never entered):
   `find "<video>" -maxdepth 3 \( -name _pushed -prune \) -o -type f \( -iname "*.mp3" -o -iname "*.wav" -o -iname "*.mp4" -o -iname "*.mov" -o -iname "*.zip" \) -printf "%h\n" | sort | uniq -c`
   (zips: list them by name, never extract on your own).
3. Then the type below decides what the folders feed: footage+AI -> `<video>\audios` is the `<audios-folder>` of
   new-video.md (a pasted video folder = `/doc-edit <video>\audios`); full-AI -> `references/full-ai.md` (`voice\`
   or `audios\mp3\`, `shots\`).
Media that are not where the step reads them (MP3s outside `audios\` / `voice\`, shots outside `shots\`, only a zip,
two candidate sets such as `shots\` + `shots_old\`) -> one AskUserQuestion listing each candidate (path, count,
missing / extra numbers against what the step needs, newest date) and the fix: copy that set into the folder the step
reads (Python `shutil.copy2`, source kept, never moved / renamed / mixed), or the user moves it. After the yes copy,
verify the count, go on. A name like `_old` is no proof either way: never pick a set by guessing (rule 9).

## Video type first (user 2026-11-05: one engine `dvr_cowork`, region independent of type)
One call decides it, never the folder name, species, minutes or channel:
`.venv/Scripts/python.exe -m dvr_cowork profile detect "<video>"` -> `profile` + `engine` + `region` (descriptor
`video.project.json` when the film has one, else the engine's own files; `unknown` -> ask, rule 9; both engines'
files -> it stops).
- **full_ai_mountain** (full-AI 8-15p, any region) -> `references/full-ai.md` only (`dvr_cowork profile context
  "<video>" --phase <step>` = the pinned numbers); nothing below this section applies.
- **footage_ai_long** (footage+AI 1-3h) -> everything below.
- **ocean_long** is reserved and disabled: the router refuses it; never route an ocean film to another engine.
- Neither, or a bare `/doc-edit status`: `state.py status`, plus `dvr_cowork ai status <folder>` of each
  `D:\Chann_*\<video>` holding `.production\` outside `_done`. Still unclear -> ask (CLAUDE.md rule 9).

- One video, one command per step: the user calls each step (user 2026-10-18: no "tiếp" chain, no "next step" line).
  Two chains only (user 2026-10-31, 3 phases): `/scan-source /tag-source và tiếp` = `ingest --fill` -> stop for
  review (timeline + logos); `/doc-edit color n done` = color -> seo -> done (render + private upload).
- Scripts do the heavy work: read only stdout (`| tail` / `grep` the summary lines). Media is never rendered except by
  `done`.
- Goal: picture + narrator let the viewer follow who does what; with eyes closed the sound still carries it.
- Replies in Vietnamese, short: result lines, problems, what the user must check.
- Resolve steps need project `<video>` or the day project `vid_DDMMYY` (footage+AI) open (`dvr_cowork info` once per session; else
  stop, ask). One failing clip never stops a step (name it).
- Calling a step's command = the user's yes for the change its row names (CLAUDE.md rule 2); anything else destructive
  (`--replace`, `--force-clear`) still needs an explicit yes.
- Parallel: narration A runs in the background while B plans; tag batches = up to 4 background agents; delogo and
  `apply` of many batches in the background. Never poll; act on the notification.

Tracks of "Edit" (the one timeline + `Edit_bak_*`): A1 empty (user 2026-11-05; place.py A1_UNTIL = 0, older videos
keep theirs) · A2 narrator only · A3/A4 bed (alternating, 4 s crossfades, ~-32 LUFS, original files) · A5 extra
environment · A6 natural · A7 music · A8/A9 SXF (A9 at 0:00: the cold open's riser -> impact, user 2026-11-06). Bins: `7. Open` = the intro's shots (0:00 -> story 1) only (plan.py
gives priority in the intro + story 1 only to the clips the user put there, not to place.py's own: `open_placed.txt`); every
music / sound file -> `4. Audio/*` (the intro music too).

## Day project, one video per channel (user 2026-10-25)
Project `vid_DDMMYY` (vid_251026 = 25/10/2026) holds one video per channel: top bins `Chann_1`, `Chann_2` ... each
with the sub-bins 1-7 and its own timeline "Edit" in `Chann_N/6. Timeline`. The channel comes from the audios path
(`D:\Chann_2_darkAmazona\...` -> `Chann_2`): vo-sync, `place.py`, `intro.py` and ledger set it themselves
(resolve_ops `use_channel`); every other Resolve command of a video runs with `DVR_CHANNEL=Chann_N` in front
(`DVR_CHANNEL=Chann_2 .venv/Scripts/python.exe -m dvr_cowork info`, light.py, reframe.py, audio-expert ...). Two
"Edit" and no channel -> the script stops (never a guess). A project without `Chann_*` bins works as before.
Same video folder name in two channels (user 2026-11-02, intended: `vid_021126` -> `africa_021126_1` in Chann_1 and
Chann_2; from 2026-11-03 `vid_DDMMYY_1`): work key `<video>__Chann_N` (`dvr_cowork/videokey.py`) for
`.work/doc_edit/<key>` and the vo-sync job `.work/<key>_mp3`, from the audios path by itself; a bare name needs
`DVR_CHANNEL=Chann_N` (or pass the key: `missing.py africa_021126_1__Chann_2`), else the script stops.
Parallel: the file work of each video (brief, beats, plan, prompts) in its own agent at once; Resolve writes
(vo-sync, place, intro, color) one at a time: they share the current timeline / bin of one Resolve.
## After the prompts: Case 1 / Case 2 per video (user 2026-10-30, `input/Claude_Vid_editor_V2_Architecture_*.md`)
`/doc-edit <audios...>` ends when each video is placed and its `missing-prompt.csv` (intro + story 1) is out: reply
per video THIẾU count + timecode ranges + prompt numbers, then wait. Waiting never turns into a fallback; Claude never opens
Muse / Chrome or generates footage (the user does, by hand). State (`dvr_cowork/jobs.py`, SQLite, Python only):
`python -m dvr_cowork.jobs status` = each recent video's stage (WAITING_FOR_USER until a decision), decision, last
Resolve write (INTERRUPTED / FAILED + its backup = rollback point). Then the user decides per video; record it first
with `jobs decide <video> ingest|fill-existing "<their words>"`:
- **Case 1** ("đã generate / lưu clip vào `_check`, scan tag organize fill") = `/doc-edit ingest --fill` for the named
  video(s), after `jobs check <video>`: only new files that finished copying (size stable, the last second decodes);
  `still copying` -> wait, ask again; `broken` -> list them for the user to remove before ingest (never imported);
  `SHARED _check` -> ask which clip is whose.
  Clip -> video / slot: `missing-prompt.csv` (`shot_id` = group + slot, `animal`) is the hint, the Resolve timeline the truth; unclear
  which video a clip is for -> list the files, ask. The clips `jobs check` accepted for a video are imported into ITS
  channel's bins (intro shots -> `7. Open`, the rest 1-3 by action; place.py), then placed into the open gaps; hand
  edits kept. THIẾU left -> report, wait (never `fill-THIEU` on its own). Called again = only the new files.
- **Case 2** ("không generate nữa, fill THIẾU bằng footage có sẵn") = the yes for `/doc-edit fill-THIEU <video>` of the
  named video(s), no second ask. What is still THIẾU comes from Resolve (`dvr_cowork gaps` + markers), not the old plan.
  Truth gates never loosen (species, sex / age the story needs, outcome, day / night, screen direction): no true clip
  -> stays THIẾU with its reason, never a fake 100 %. After plan `--sub-broad`: `jobs fill-report <video>` (tiers
  A exact / B strong / C context / D last resort, `any light` flags, THIẾU + refusals) = the reply: filled
  (timecode -> clip, tier), compromises to look at, THIẾU left + why.
- User says a placed clip is wrong ("clip X sai loài") -> `jobs reject <video> "<path fragment>" "<why>"`: plan.py drops
  it for that video from then on (hard gates unchanged), then the user's step (plan / fill) as usual.
- Mixed ("video 1 có clip trong `_check`, video 2 fill THIẾU") = each video its own case, its own channel
  (`DVR_CHANNEL`), Resolve writes one after the other; a clip never goes to the other video's bin / timeline. Video
  not named and several have THIẾU -> `state.py status` lines, ask which.
- Fill is never a yes to render: color, done stay the user's commands.
- One Resolve writer at a time: `backup_timeline` holds a lock for the whole process; a second writer stops with
  `another Resolve write is running (pid, script)` -> wait for its notification, never retry in a loop.
- Cost check (user asks, or after a rule change): `jobs metrics --days=7` = Claude tokens per day (this workspace,
  subagents included) + Resolve writes per script (median time, FAILED, interrupted).

## Region (user 2026-10-20; himalaya 2026-11-05)
`/doc-edit <audios-folder> [amazon|africa|himalaya]`: the video folder's name says it (`amazon_3`, `africa_251026`,
`himalaya_051126_1`; old `congo_*` = amazon); neither name nor word -> ask, never guess. It becomes the spec's first line
`# REGION <region>`; plan, fill and missing-prompts then use only that region's footage (no line = amazon, the
videos before).
| region | footage roots |
|---|---|
| amazon | `Z:\Unseen\Amazona\video` + `D:\AI_video` |
| himalaya | none yet: every slot THIẾU -> prompts (AI clips into `D:\AI_video\_himalaya\_check`) |
| africa | `Z:\Unseen\Động vật\AAA Trên cạn` (footage; its `AI_copyright\` = AI clips; `bản quyền\` = whole films, NEVER used: plan.py load_clips skips them, user 2026-10-28) + `Z:\Unseen\savannah` (scenery) + `D:\AI_video\_africa` (Africa AI clips, root `africa_ai_check`; user 2026-10-22: new clips in `_africa\_check`, filed into `_africa\<species>` like Amazon's `D:\AI_video`) |

- Audio roots shared: `Z:\Unseen\Amazona\audio`, `Z:\Unseen\SFX`, `audio_lib` (`D:\Audio_lib`: Epidemic / Suno,
  A7 music by mood; `Z:\Unseen\Sound` dropped 2026-11-04). A new root = scan_source ROOTS (+ plan.py CATEGORY if flat).
  Plan prints `audio thieu` -> fill it with audio-expert mode fetch, then plan again.
- Africa `logo` / `delogo` / process-ai-video work on `D:\AI_video\_africa\_check`; ingest files them with
  `organize.py --africa --apply` (folders: tag-source `scripts\make_africa_ai_folders.ps1`). Clips kept in `_check` are
  planned at most WEAK, as for Amazon.
- Africa footage is tagged per species when a film needs it (references/new-video.md B1b), never all at once.

**Story first** (user 2026-10-23, `input/plan.md`): shots are chosen for what the film / story / beat must make the
viewer understand, never as keyword matches of a sentence: whole screenplay -> bible + `# HOOK` blueprint -> shot
lines with truth tokens (`sex=` `age=` `out=kill` `xact=`, story `no=`) that plan.py enforces; no true clip = THIẾU
(new-video.md 1c, edit-grammar "Story first"). 2026-10-24: the film is read through `story.py brief` (one pack,
~60 % of the source files) and written as a beat sheet (emotion + shot pool per beat); `story.py expand` turns it
into spec.txt with the grammar's rhythm and sound rules (new-video.md B1-B2).

**Story choice** (user 2026-10-21): before writing a spec read `references/biome-story-pacing.md` for the biome
(`# BIOME savanna` = Africa open country, `rainforest` = Amazon / Congo) and its hook rules. The opening is planned
first and hardest: footage+AI: 0:00-0:12 the cold open, story 1's most tense moment in full-AI clips (`references/coldopen.md`, user 2026-11-06), then the
teaser to ~1:30. The preset steers shot order and pacing only: species, places and
sounds come from the screenplay and the footage, never from the biome name.

## Commands
| command (user's words) | runs | reply |
|---|---|---|
| `/doc-edit <video folder>` of a full-AI film | `references/full-ai.md` from its state: voice -> prompts, stop; shots complete -> whole film on Edit, stop for review | that file's replies |
| `/doc-edit <audios-folder> [<audios-folder> ...]` | `references/new-video.md` per video: preflight (conform if needed) -> A narration (background) + B plan -> C intro music + re-plan -> D prompts for the intro + story 1 -> E place of intro + body on empty tracks (the body's THIẾU already filled by plan.py, user 2026-11-05); several folders = one agent per video for B + D, A / C / E one video after the other | new-video reply per video |
| `/doc-edit plan` | re-plan after beat / spec edits or new clips: B2-B3 of new-video.md (`story.py expand` when beats exist) with the WEAK pin round | B reply part 3 |
| `/doc-edit missing-prompts [mm:ss-mm:ss]` | `references/missing-prompts.md`: THIẾU of the intro + story 1 by default; a range -> `missing.py <video> --range=A-B`, the whole film `--all` (same flag on `--check` / `--write`) | prompts reply |
| `/doc-edit logo` ("check folder _check") | `hide_logo.py "D:\AI_video\_check"` (africa: `"D:\AI_video\_africa\_check"`) (~1-2 min) | LOGO / SUSPECT names + `.work\hide_logo\check_list.txt` |
| `/doc-edit delogo` | `hide_logo.py --list` (MiniMax ~30 s per clip, background) -> `D:\AI_video\_nologo` copies (africa: env `NOLOGO_DIR`) | done, REVIEW FIRST, FAILED, gone |
| `/doc-edit ingest` ("/scan-source ai, /tag-source") | amazon: scan ai -> tag-source (prepare, Sonnet agents in parallel, apply) -> `organize.py --apply` -> scan ai ("moved N"); africa: scan africa_ai_check -> tag-source `prepare africa_ai_check` -> apply -> `organize.py --africa --apply` -> scan africa_ai_check | tagged, filed per folder, kept in `_check` (why) |
| `/doc-edit fill [--sub mm:ss]` ("lấp slot thiếu") | `plan.py <folder> [--late-sub --late-sub-t=<s>]` or `--sub-all` -> `place.py <video> --fill` (backup; `references/place-fill.md`) | THIẾU left (timecodes), placed, backup |
| `/doc-edit fill-THIEU [<video>]` (= "Sử dụng các option thay thế các slot THIEU"; user 2026-10-26: only on this command / phrase, never on its own, never in `fill`; since 2026-11-05 the body after story 1 gets these tiers on every plan run, so this command matters for the intro + story 1) | `plan.py <folder> --sub-broad` (`--sub-all` + tier 4: species itself > same library folder > birds / butterflies / insects / frogs > landscape; slot light first, any light last; FALLBACK "late substitute (broad)", cyan) -> `place.py <video> --fill` | slots filled (timecode -> clip), the off-light / off-setting ones to check, THIẾU left |
| `/doc-edit fallback-species [<video>] [mm:ss-mm:ss]` (user 2026-10-29: "thay các slot FALLBACK bằng shot cùng loài") | `scripts/fallback_swap.py <video> --range=A-B` dry run, then `--apply` (backup `Edit_bak_fbspecies_*`): each FALLBACK V1 shot -> a clip of the slot's species (else its family), action / setting ignored; hand-changed shots and the intro -> story 1 fade shots untouched; Teal | swapped, left alone (hand), KEEP (no clip) |
| `/doc-edit ingest --fill [--sub mm:ss]` (also `/scan-source /tag-source và tiếp`) | `ingest`, then `fill` in one go (no stop between); `--sub` as in `fill`; then stop: the user reviews the timeline + logos | tagged, filed, THIẾU left, placed, gaps left |
| `/doc-edit place` | `references/place-fill.md` | backup, placed, max deviation, gaps, audio, failures, markers |
| `/doc-edit coldopen <video>` (part of every new footage+AI film's first run, never full-AI 8-15p; this = redo / place) | `references/coldopen.md`: story 1's tense moment -> coldopen.json -> `dvr_cowork coldopen prompts`, stop; clips in `<video>\coldopen` -> `coldopen place --apply` | the moment, prompts + save folder; then backup, cuts, what to listen to |
| `/doc-edit color` ("đồng bộ màu") | load `/colorist`, its light pass: `light.py plan` -> golden-grass preview -> `apply` (backup; one space per story, vivid, never a broken shot) -> look at >= 12 real frames (`dvr_cowork frames`), several per story | ranges, story spread before -> after, AI clips toned down, intro count, the frames checked |
| `/doc-edit color n done [<video>]` ("color và done") | `seo.py` in the background (no Resolve) while `color` runs as above; color found a broken shot / a problem -> stop, report, no render; else `done` (check-timelines.md): render + upload private, no thumbnail | color reply + SEO 3 titles + done reply |
| `/doc-edit seo [<video>] [--force]` | `python -m dvr_cowork youtube seo <video folder> [--force]` (check-timelines.md "SEO") | 3 titles (the chosen one), FLAG lines |
| `/doc-edit status` | `state.py status`: every video of every channel, its stage, the command to call next (files only, no Resolve) | the table |
| `/doc-edit reframe [<video>]` | `references/reframe.md` | |
| `/doc-edit check-timelines`, `/doc-edit done` ("xong video") | `references/check-timelines.md` | |

## After a step
- Place / fill details (bins, markers, `--fill`, `--rebin`, substitutes, gaps): `references/place-fill.md`.
- Every place / fill / color apply leaves a backup timeline; many make Resolve lag: run `dvr_cowork backups` (one line)
  and when a kind has > 3, offer `dvr_cowork backups --keep 3 --apply` (user yes).
- Shot-choice benchmark (after a rule change, user 2026-10-23): `scripts/bench_story_first.py <video>` re-runs
  today's matching on a finished video's plan.json slots -> `.work/doc_edit/<video>/bench_story_first.md` (old picks
  that break a story rule, status counts, changed slots); `plan.py <folder> --spec=<file> --out=<dir>` plans another
  spec into another folder (the video's spec / plan untouched).
- `state.py diff <video>` only when the user asks or a step must not undo hand edits it cannot see.
