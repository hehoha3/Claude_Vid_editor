---
name: doc-edit
description: Documentary edit of one video in Resolve, one step per command - new video (narration A2 + plan + missing prompts + place), plan, missing-prompts, logo, delogo, ingest, fill, color, place, reframe, check-timelines, done, status. Use for /doc-edit, "lên plan / prompt cho shot thiếu", "lấp slot thiếu", "đồng bộ màu", "check folder _check", "/scan-source ai, /tag-source", "xong video".
---

# Doc edit

- One video, one command per step: the user calls each step (user 2026-10-18: no "tiếp" chain, no "next step" line).
- Scripts do the heavy work: read only stdout (`| tail` / `grep` the summary lines). Media is never rendered except by
  `done`.
- Goal: picture + narrator let the viewer follow who does what; with eyes closed the sound still carries it.
- Replies in Vietnamese, short: result lines, problems, what the user must check.
- Resolve steps need project `<video>` open (`dvr_cowork info` once per session; else stop, ask). One failing clip never
  stops a step (name it).
- Calling a step's command = the user's yes for the change its row names (CLAUDE.md rule 2); anything else destructive
  (`--replace`, `--force-clear`) still needs an explicit yes.
- Parallel: narration A runs in the background while B plans; tag batches = up to 4 background agents; delogo and
  `apply` of many batches in the background. Never poll; act on the notification.

Tracks of "Edit": A1 AI-clip audio of V1 at -12 dB · A2 narrator only · A3/A4 bed (alternating, 4 s crossfades,
~-32 LUFS, original files) · A5 extra environment · A6 natural · A7 music · A8/A9 SXF.

## Region (user 2026-10-20)
`/doc-edit <audios-folder> amazon|africa`; no region -> ask, never guess. It becomes the spec's first line
`# REGION <region>`; plan, fill and missing-prompts then use only that region's footage (no line = amazon, the
videos before).
| region | footage roots |
|---|---|
| amazon | `Z:\Unseen\Amazona\video` + `D:\AI_video` |
| africa | `Z:\Unseen\Động vật\AAA Trên cạn` (footage; its `AI_copyright\` = AI clips; `bản quyền\` = whole films, never tagged, user handles later) + `Z:\Unseen\savannah` (scenery) + `D:\AI_video\_africa` (Africa AI clips, root `africa_ai_check`; user 2026-10-22: new clips in `_africa\_check`, filed into `_africa\<species>` like Amazon's `D:\AI_video`) |

- Audio roots shared: `Z:\Unseen\Amazona\audio`, `Z:\Unseen\SFX`, `Z:\Unseen\Sound` (a new root = scan_source ROOTS +
  plan.py CATEGORY).
- Africa `logo` / `delogo` / process-ai-video work on `D:\AI_video\_africa\_check`; ingest files them with
  `organize.py --africa --apply` (folders: `.work\scripts\make_africa_ai_folders.ps1`). Clips kept in `_check` are
  planned at most WEAK, as for Amazon.
- Africa footage is tagged per species when a film needs it (references/new-video.md B1b), never all at once.

**Story choice** (user 2026-10-21): before writing a spec read `references/biome-story-pacing.md` for the biome
(`# BIOME savanna` = Africa open country, `rainforest` = Amazon / Congo) and its hook rules. The hook (0:00-1:30, above
all the first 10 s) is planned first and hardest. The preset steers shot order and pacing only: species, places and
sounds come from the screenplay and the footage, never from the biome name.

## Commands
| command (user's words) | runs | reply |
|---|---|---|
| `/doc-edit <audios-folder> <region>` | `references/new-video.md`: A narration (background) + B plan + prompts in parallel, then place on empty tracks | place lines + new-video reply |
| `/doc-edit plan` | re-plan after spec edits / new clips: B2-B3 of new-video.md with the WEAK pin round | B reply part 3 |
| `/doc-edit missing-prompts [mm:ss-mm:ss]` | `references/missing-prompts.md`; a range -> `missing.py <video> --range=A-B` (same flag on `--check` / `--write`) | prompts reply |
| `/doc-edit logo` ("check folder _check") | `hide_logo.py "D:\AI_video\_check"` (africa: `"D:\AI_video\_africa\_check"`) (~1-2 min) | LOGO / SUSPECT names + `.work\hide_logo\check_list.txt` |
| `/doc-edit delogo` | `hide_logo.py --list` (MiniMax ~30 s per clip, background) -> `D:\AI_video\_nologo` copies (africa: env `NOLOGO_DIR`) | done, REVIEW FIRST, FAILED, gone |
| `/doc-edit ingest` ("/scan-source ai, /tag-source") | amazon: scan ai -> tag-source (prepare, Sonnet agents in parallel, apply) -> `organize.py --apply` -> scan ai ("moved N"); africa: scan africa_ai_check -> tag-source `prepare africa_ai_check` -> apply -> `organize.py --africa --apply` -> scan africa_ai_check | tagged, filed per folder, kept in `_check` (why) |
| `/doc-edit fill [--sub mm:ss]` ("lấp slot thiếu") | `plan.py <folder> [--late-sub --late-sub-t=<s>]` or `--sub-all` -> `place.py <video> --fill` (backup; `references/place-fill.md`) | THIẾU left (timecodes), placed, backup |
| `/doc-edit ingest --fill [--sub mm:ss]` | `ingest`, then `fill` in one go (no stop between); `--sub` as in `fill` | tagged, filed, THIẾU left, placed, gaps left |
| `/doc-edit place` | `references/place-fill.md` | backup, placed, max deviation, gaps, audio, failures, markers |
| `/doc-edit color` ("đồng bộ màu") | load `/colorist`, its light pass: `light.py plan` -> golden-grass preview -> `apply` (backup; light, vivid, never a broken shot) -> look at >= 12 real frames (`dvr_cowork frames`) | ranges, AI clips toned down, intro count, the frames checked |
| `/doc-edit status` | `state.py status`: every video of every channel, its stage, the command to call next (files only, no Resolve) | the table |
| `/doc-edit reframe [<video>]` | `references/reframe.md` | |
| `/doc-edit check-timelines`, `/doc-edit done` ("xong video") | `references/check-timelines.md` | |

## After a step
- Place / fill details (bins, markers, `--fill`, `--rebin`, substitutes, gaps): `references/place-fill.md`.
- Every place / fill / color apply leaves a backup timeline; many make Resolve lag: run `dvr_cowork backups` (one line)
  and when a kind has > 3, offer `dvr_cowork backups --keep 3 --apply` (user yes).
- `state.py diff <video>` only when the user asks or a step must not undo hand edits it cannot see.
