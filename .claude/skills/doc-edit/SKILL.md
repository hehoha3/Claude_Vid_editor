---
name: doc-edit
description: Documentary edit in Resolve, one step per command - new video(s) (narration A2 + plan + missing prompts + intro music + place of intro and body; several channels' videos in parallel in one day project), plan, missing-prompts, logo, delogo, ingest, fill, fill-THIEU (tier 4 stand-ins), color, place, reframe, check-timelines, done, status. Use for /doc-edit, "lên plan / prompt cho shot thiếu", "lấp slot thiếu", "đồng bộ màu", "check folder _check", "/scan-source ai, /tag-source", "xong video".
---

# Doc edit

- One video, one command per step: the user calls each step (user 2026-10-18: no "tiếp" chain, no "next step" line).
- Scripts do the heavy work: read only stdout (`| tail` / `grep` the summary lines). Media is never rendered except by
  `done`.
- Goal: picture + narrator let the viewer follow who does what; with eyes closed the sound still carries it.
- Replies in Vietnamese, short: result lines, problems, what the user must check.
- Resolve steps need project `<video>` or the day project `vid_DDMMYY` open (`dvr_cowork info` once per session; else
  stop, ask). One failing clip never stops a step (name it).
- Calling a step's command = the user's yes for the change its row names (CLAUDE.md rule 2); anything else destructive
  (`--replace`, `--force-clear`) still needs an explicit yes.
- Parallel: narration A runs in the background while B plans; tag batches = up to 4 background agents; delogo and
  `apply` of many batches in the background. Never poll; act on the notification.

Tracks of "Edit": A1 AI-clip audio of V1 at -12 dB (shots before 08:00 only; place.py A1_UNTIL) · A2 narrator only · A3/A4 bed (alternating, 4 s crossfades,
~-32 LUFS, original files) · A5 extra environment · A6 natural · A7 music · A8/A9 SXF.

## Day project, one video per channel (user 2026-10-25)
Project `vid_DDMMYY` (vid_251026 = 25/10/2026) holds one video per channel: top bins `Chann_1`, `Chann_2` ... each
with the sub-bins 1-7 and its own timeline "Edit" in `Chann_N/6. Timeline`. The channel comes from the audios path
(`D:\Chann_2_darkAmazona\...` -> `Chann_2`): vo-sync, `place.py`, `intro.py` and ledger set it themselves
(resolve_ops `use_channel`); every other Resolve command of a video runs with `DVR_CHANNEL=Chann_N` in front
(`DVR_CHANNEL=Chann_2 .venv/Scripts/python.exe -m dvr_cowork info`, light.py, reframe.py, audio-expert ...). Two
"Edit" and no channel -> the script stops (never a guess). A project without `Chann_*` bins works as before.
Parallel: the file work of each video (brief, beats, plan, prompts) in its own agent at once; Resolve writes
(vo-sync, place, intro, color) one at a time: they share the current timeline / bin of one Resolve.
## After the prompts: Case 1 / Case 2 per video (user 2026-10-30, `input/Claude_Vid_editor_V2_Architecture_*.md`)
`/doc-edit <audios...>` ends when each video's `missing_prompts.txt` + `shot_manifest.csv` are out: reply per video
THIẾU count + timecode ranges + prompt numbers, then wait. Waiting never turns into a fallback; Claude never opens
Muse / Chrome or generates footage (the user does, by hand). State (`dvr_cowork/jobs.py`, SQLite, Python only):
`python -m dvr_cowork.jobs status` = each recent video's stage (WAITING_FOR_USER until a decision), decision, last
Resolve write (INTERRUPTED / FAILED + its backup = rollback point). Then the user decides per video; record it first
with `jobs decide <video> ingest|fill-existing "<their words>"`:
- **Case 1** ("đã generate / lưu clip vào `_check`, scan tag organize fill") = `/doc-edit ingest --fill` for the named
  video(s), after `jobs check <video>`: only new files that finished copying (size stable, the last second decodes);
  `still copying` -> wait, ask again; `broken` -> list them for the user to remove before ingest (never imported);
  `SHARED _check` -> ask which clip is whose.
  Clip -> video / slot: `shot_manifest.csv` (`save_folder`, `slots`) is the hint, the Resolve timeline the truth; unclear
  which video a clip is for -> list the files, ask. Only open gaps are filled, hand edits kept. THIẾU left -> report,
  wait (never `fill-THIEU` on its own). Called again = only the new files.
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

## Region (user 2026-10-20)
`/doc-edit <audios-folder> [amazon|africa]`: the video folder's name says it (`amazon_3`, `africa_251026`, user
2026-10-25); neither name nor word -> ask, never guess. It becomes the spec's first line
`# REGION <region>`; plan, fill and missing-prompts then use only that region's footage (no line = amazon, the
videos before).
| region | footage roots |
|---|---|
| amazon | `Z:\Unseen\Amazona\video` + `D:\AI_video` |
| africa | `Z:\Unseen\Động vật\AAA Trên cạn` (footage; its `AI_copyright\` = AI clips; `bản quyền\` = whole films, NEVER used: plan.py load_clips skips them, user 2026-10-28) + `Z:\Unseen\savannah` (scenery) + `D:\AI_video\_africa` (Africa AI clips, root `africa_ai_check`; user 2026-10-22: new clips in `_africa\_check`, filed into `_africa\<species>` like Amazon's `D:\AI_video`) |

- Audio roots shared: `Z:\Unseen\Amazona\audio`, `Z:\Unseen\SFX`, `Z:\Unseen\Sound` (a new root = scan_source ROOTS +
  plan.py CATEGORY).
- Africa `logo` / `delogo` / process-ai-video work on `D:\AI_video\_africa\_check`; ingest files them with
  `organize.py --africa --apply` (folders: tag-source `scripts\make_africa_ai_folders.ps1`). Clips kept in `_check` are
  planned at most WEAK, as for Amazon.
- Africa footage is tagged per species when a film needs it (references/new-video.md B1b), never all at once.

**Story first** (user 2026-10-23, `input/plan.md`): shots are chosen for what the film / story / beat must make the
viewer understand, never as keyword matches of a sentence: whole screenplay -> bible + `# HOOK` blueprint -> shot
lines with truth tokens (`sex=` `age=` `out=kill` `xact=`, story `no=`) that plan.py enforces; no true clip = THIẾU
(new-video.md 1c, edit-grammar "Story first"). 2026-10-24: the film is read through `story.py brief` (one pack,
~40 % of the source files) and written as a beat sheet (emotion + shot pool per beat); `story.py expand` turns it
into spec.txt with the grammar's rhythm and sound rules (new-video.md B1-B2).

**Story choice** (user 2026-10-21): before writing a spec read `references/biome-story-pacing.md` for the biome
(`# BIOME savanna` = Africa open country, `rainforest` = Amazon / Congo) and its hook rules. The hook (0:00-1:30, above
all the first 10 s) is planned first and hardest. The preset steers shot order and pacing only: species, places and
sounds come from the screenplay and the footage, never from the biome name.

## Commands
| command (user's words) | runs | reply |
|---|---|---|
| `/doc-edit <audios-folder> [<audios-folder> ...]` | `references/new-video.md` per video: A narration (background) + B plan + prompts in parallel, then intro music picked by itself (`references/intro.md`, user 2026-10-31: no separate intro command) and place of intro + body on empty tracks; several folders = one agent per video for B, A / place one after the other | place lines + new-video reply per video |
| `/doc-edit plan` | re-plan after beat / spec edits or new clips: B2-B3 of new-video.md (`story.py expand` when beats exist) with the WEAK pin round | B reply part 3 |
| `/doc-edit missing-prompts [mm:ss-mm:ss]` | `references/missing-prompts.md`; a range -> `missing.py <video> --range=A-B` (same flag on `--check` / `--write`) | prompts reply |
| `/doc-edit logo` ("check folder _check") | `hide_logo.py "D:\AI_video\_check"` (africa: `"D:\AI_video\_africa\_check"`) (~1-2 min) | LOGO / SUSPECT names + `.work\hide_logo\check_list.txt` |
| `/doc-edit delogo` | `hide_logo.py --list` (MiniMax ~30 s per clip, background) -> `D:\AI_video\_nologo` copies (africa: env `NOLOGO_DIR`) | done, REVIEW FIRST, FAILED, gone |
| `/doc-edit ingest` ("/scan-source ai, /tag-source") | amazon: scan ai -> tag-source (prepare, Sonnet agents in parallel, apply) -> `organize.py --apply` -> scan ai ("moved N"); africa: scan africa_ai_check -> tag-source `prepare africa_ai_check` -> apply -> `organize.py --africa --apply` -> scan africa_ai_check | tagged, filed per folder, kept in `_check` (why) |
| `/doc-edit fill [--sub mm:ss]` ("lấp slot thiếu") | `plan.py <folder> [--late-sub --late-sub-t=<s>]` or `--sub-all` -> `place.py <video> --fill` (backup; `references/place-fill.md`) | THIẾU left (timecodes), placed, backup |
| `/doc-edit fill-THIEU [<video>]` (= "Sử dụng các option thay thế các slot THIEU"; user 2026-10-26: only on this command / phrase, never on its own, never in `fill`) | `plan.py <folder> --sub-broad` (`--sub-all` + tier 4: species itself > same library folder > birds / butterflies / insects / frogs > landscape; slot light first, any light last; FALLBACK "late substitute (broad)", cyan) -> `place.py <video> --fill` | slots filled (timecode -> clip), the off-light / off-setting ones to check, THIẾU left |
| `/doc-edit fallback-species [<video>] [mm:ss-mm:ss]` (user 2026-10-29: "thay các slot FALLBACK bằng shot cùng loài") | `scripts/fallback_swap.py <video> --range=A-B` dry run, then `--apply` (backup `Edit_bak_fbspecies_*`): each FALLBACK V1 shot -> a clip of the slot's species (else its family), action / setting ignored; hand-changed shots and the intro -> story 1 fade shots untouched; Teal | swapped, left alone (hand), KEEP (no clip) |
| `/doc-edit ingest --fill [--sub mm:ss]` | `ingest`, then `fill` in one go (no stop between); `--sub` as in `fill` | tagged, filed, THIẾU left, placed, gaps left |
| `/doc-edit place` | `references/place-fill.md` | backup, placed, max deviation, gaps, audio, failures, markers |
| `/doc-edit color` ("đồng bộ màu") | load `/colorist`, its light pass: `light.py plan` -> golden-grass preview -> `apply` (backup; one space per story, vivid, never a broken shot) -> look at >= 12 real frames (`dvr_cowork frames`), several per story | ranges, story spread before -> after, AI clips toned down, intro count, the frames checked |
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
