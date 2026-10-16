# Check timelines: `/doc-edit check-timelines [<video>]`

Only when the user asks (any time, any number of times). Video = this conversation's, else the open project; unknown -> ask.

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/ledger.py check <video> [--ws <workspace>]

- Workspaces = folders matching config.toml `[workspaces] globs` (default `D:\Chann_*`), one sub folder per video;
  new channel = new folder. `--ws` only when two workspaces hold a video of the same name.
- Reads every video track of "Edit" + "Open" of Resolve project `<video>` (loads it if another is open, switches
  back). plan.json is not used: hand swaps count, unused plan clips don't. Id = library content hash; a `_nologo`
  copy = its original.
- `.work/doc_edit/ledgers/<workspace>.json`: new video on top, re-check updates in place. Plan ban = Edit + Open
  clips of the `recent` (config, 4) newest other videos of the same workspace; workspaces never ban each other.
  `ledger.py show` prints all ledgers.

Reply: clips per timeline, clips not in the library index (file gone/renamed outside the pipeline = offline on the
timeline: say where, `dvr_cowork find <name>`), the workspace ledger line.

## Done: `/doc-edit done [<video>]` ("xong video", "done demo_4") - user rule 2026-10-13

Run it right away: no "exported?" question, no confirmation (the user's "done" is the go). Tell the user once that
Resolve will be closed (it stays closed: reopening is the user's call). Several videos -> one after another.

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/ledger.py done <video> [--ws <workspace>] [--project <name>]

`--project` (also on `check`) when the Resolve project is not named like the folder (amazon_1 = "build_agent").
Media still linked to an old location of the video folder (renamed drive/folder) -> first
`dvr_cowork offline --relink <old folder> <ws>\<video> --apply`, so every file under the video folder moves with it.

The render makes it long (a 30 min 4K timeline): run it with `run_in_background`, never a foreground timeout.

0. Licenses (user rule 2026-10-13): every audio file on all audio tracks of "Edit" + "Open" is looked up in
   `.work/audio_licenses.md`; prints each licensed file + its license pdf path, and files under `Z:\Unseen\Sound`
   with no row (warn the user: no license recorded). Same list (full rows + missing) written to
   `<video folder>\audio_licenses.md`, so it moves into `_done` with the video. Envato licenses are per project: remind the user to register them.
   The license pdfs themselves are copied (from Z:, read only) into `<video folder>\licenses\` as
   `<folder>_<pdf> - <title>.pdf` (user rule 2026-10-16); `licenses folder:` line in stdout.
   Export (user rule 2026-10-13): timeline "Master" rendered (read only) as H.264 mp4 `Done_<project>.mp4` into the
   video folder, waits for it; already there -> not rendered again. Render failed -> stops, nothing moved.
1. Final check-timelines (ledger), then Change Source Folder: every media pool item under `<ws>\<video>` (narration,
   audio...) -> same file under `<ws>\_done\<video>` (ReplaceClip through a temporary junction; timeline kept), saved.
2. Quit Resolve, remove the junction (link only), rename the folder into `_done` (all or nothing). Never relaunch.
Rename failed (file held by Explorer / a player) -> the junction is put back so the project still works; tell the
user what to close, then `ledger.py move <video>` (Resolve closed). Archived videos keep workspace + ledger rank.

Several videos: before the next one ask the user to reopen Resolve (done needs it). After it: `hide_logo.py --pending`; copies listed -> ask only "Bạn có muốn ghi đè các file trong folder _nologo lên
các file gốc của chúng không?"; "có" -> `hide_logo.py --overwrite-all` (needs a project open that uses them; else
ask the user to open it). Reply: the license list (file -> license path, missing ones), the `render:` line (now
under `_done\<video>`), `done ...` line per video, the overwrite question.
