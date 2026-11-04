# Check timelines: `/doc-edit check-timelines [<video>]`

Only when the user asks (any time, any number of times). Video = this conversation's, else the open project; unknown -> ask.

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/ledger.py check <video> [--ws <workspace>]

- Workspaces = folders matching config.toml `[workspaces] globs` (default `D:\Chann_*`), one sub folder per video;
  new channel = new folder. `--ws` only when two workspaces hold a video of the same name.
- Reads every video track of "Edit" + "Open" of Resolve project `<video>` (loads it if another is open, switches
  back). plan.json is not used: hand swaps count, unused plan clips don't. Id = library content hash; a `_nologo`
  copy = its original.
- `.work/doc_edit/ledgers/<workspace>.json`: new video on top, re-check updates in place. Plan ban = Edit + Open
  clips of the `recent` (config, 6) newest other videos of the same workspace, on slots before 15:00 only (`BAN_UNTIL` in plan.py, user 2026-10-25);
  workspaces never ban each other.
  `ledger.py show` prints all ledgers.

Then, in the same pass, `dvr_cowork gaps` (DVR_CHANNEL set; user 2026-10-26): every empty V1 span is an error except
THIEU slots (markers + plan) and the ~0.6 s intro -> story 1 black. Any timeline check (status, after place/fill,
"kiểm tra timeline") runs it too.

Reply: clips per timeline, clips not in the library index (file gone/renamed outside the pipeline = offline on the
timeline: say where, `dvr_cowork find <name>`), the workspace ledger line, the `gaps` lines (spans to fill ->
propose `place.py --fill`).

## Done: `/doc-edit done [<video>]` ("xong video", "done demo_4") - user rule 2026-10-13, reworked 2026-10-26

Run it right away: no "exported?" question, no confirmation (the user's "done" is the go). Several videos -> one
after another. Works in a day project (`vid_DDMMYY`: project + channel from `.work/doc_edit/<video>/project.txt`).

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/ledger.py done <video> [--ws <workspace>] [--project <name>] [--thumb <image>] [--publish-at "YYYY-MM-DD HH:MM"]

`--project` (also on `check`) when the Resolve project is not named like the folder and has no project.txt
(amazon_1 = "build_agent"). The render makes it long (a 60 min 4K timeline): run it with `run_in_background`.

1. Final check-timelines (ledger).
2. Licenses (user rule 2026-10-13, format 2026-10-21): every audio file on the audio tracks of "Edit" (+ "Open" if it
   still exists) is looked up in `.work/audio_licenses.md`, else (Pixabay, e.g. intro music in `D:\Music`) the
   license txt beside the file (`*-<id>-license.txt`, `*-<id>.txt` or any txt naming the id: `ledger.pixabay_license`), or for Epidemic / Suno files the `<stem>.license.txt` that audio-expert fetch.py writes (`ledger.sidecar_row`); files under `D:\Audio_lib` or `D:\Music` with no license -> warn.
   `<video folder>\audio_licenses.md` = one line per licensed file, film order:
   `[start - stop], [start - stop] - <title> + <author> - <license pdf path>` (timeline times, touching pieces joined),
   then the missing ones. No `licenses\` folder, no pdf copies. Envato licenses are per project: remind the user.
3. Export: timeline "Edit" (user 2026-10-26: Master / Open are deleted; `--timeline <name>` for another) rendered with
   the Resolve preset "YouTube 1080 HEVC" (missing preset = stop) as `Done_<video>.mp4` into the video folder, waits;
   already there -> not rendered again. Subtitle tracks off for the render, back on after (no subtitles in the file).
   Before it, `place.black_fades` checks the 4 V1 black fades and puts back a missing one (`black fades <video>: ...`
   line; `NOT SET` -> say so, the render has no fade there).
4. Upload (user 2026-10-31): `Done_<video>.mp4` -> the YouTube channel `.secrets/youtube/channels.json` maps the
   workspace's `Chann_N` to (`dvr_cowork.youtube upload`): title / description / tags from `youtube_meta.json` (SEO
   below, run it BEFORE `ledger.py done` when the file is missing), English, Pets & Animals, not for kids, private
   (unaudited API project), no thumbnail unless the user gives one. `--thumb` = the image the user gives
   (D:\Thumbs\...). `--publish-at` = "đăng vào 18 giờ" (PC time): private now, YouTube makes it public then
   (a time already past -> no upload, ask again). Once per video (`.work/doc_edit/<video>/youtube.json`); a `--thumb` later on an uploaded video
   sets only the thumbnail. Chann_N not mapped / not logged in / failed -> `youtube:` line says so, render stays.
Resolve stays open; no relink, no folder move: the user moves the folder into `_done` himself (user 2026-10-26).

## SEO: `python -m dvr_cowork.seo <video folder> [--force]` (user 2026-10-31, replaces vidIQ)
YouTube Data API trend search (~300 quota units, cached 7 days) + one Gemini call -> `.work/doc_edit/<video>/
youtube_meta.json`: the 3 most trending titles (user 2026-10-31, no curiosity rule), always
`WILD <REGION> | <Gemini's middle part> | Wildlife Documentary` (seo.full_title), description
(chapters from the spec, AI disclosure), tags <= 500 chars, synthetic. Claude reads only the stdout lines: each title
must be true to the film (no species, kill, fight or "only / first / biggest" claim the film does not show). Claude
picks the best true one (user 2026-11-02: click pull + fit to the whole film, not the trend order) and sets it with
`--pick N` before the upload (youtube.py reads the meta at upload time). `FLAG` lines -> fix or tell the user. Reply:
the 3 titles ranked best first, the one used + one line why (the user may switch: `--pick N`, or Studio after the
upload), and the reminder "Thông tin tài sản: Web" in Studio.

After it: `hide_logo.py --pending`; copies listed -> ask only "Bạn có muốn ghi đè các file trong folder _nologo lên
các file gốc của chúng không?"; "có" -> `hide_logo.py --overwrite-all`. Reply: the license list (file -> license path,
missing ones), the `render:` line, the `youtube:` line (link; private -> the user checks Studio), the overwrite question.
