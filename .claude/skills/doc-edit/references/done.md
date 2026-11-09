# Done / push: `/doc-edit done [<video>]` ("xong video"), `/doc-edit push [<video>]` ("up youtube")

Run it right away: no "exported?" question, no confirmation (the user's "done" is the go). Several videos -> one
after another. Works in a day project (`vid_DDMMYY`: project / channel / timeline from `.work/doc_edit/<video>/project.txt`).

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/ledger.py done <video> [--ws <workspace>] [--project <name>] [--licenses] [--upload [--thumb <image>] [--publish-at "YYYY-MM-DD HH:MM"]]

`/doc-edit done` = steps 1-3 (render + save, no upload, no SEO). `/doc-edit push` = SEO (below, `--pick N`) ->
`ledger.py done <video> --upload` (render skipped when `Done_<video>.mp4` exists) = steps 1-4.
`--project` when the Resolve project is not named like the folder and has no project.txt. The render is long (a 60 min
4K timeline): run it with `run_in_background`.

1. Ledger (`ledger.check`, automatic, no user command since 2026-11-09): every video track of `channN_vidK` -> library
   ids (content hash; `_nologo` copy = its original) in `.work/doc_edit/ledgers/<workspace>.json` (`clips`, `open15`
   = 0:00-15:00, `intro` = before the plan's intro end). plan.py bans from them: `recent` (6 newest videos, slots
   before 15:00), `open15` (9 newest, before 30:00), `intro_week` (channel videos within 7 days, every intro slot).
   Files not in the library index (gone / renamed outside the pipeline) are named: say where (`dvr_cowork find`).
2. Licenses: `<video folder>\audio_licenses.md` only when missing (`--licenses`, or `ledger.py licenses <video>`
   alone, rewrites it). Every audio file of the timeline outside the video folder, looked up (`ledger.license_of`):
   Envato table `.work/audio_licenses.md` -> Epidemic / Suno `<stem>.license.txt` -> Pixabay id in the name ->
   same-stem `<stem>.txt` / `-license.txt` -> Storyblocks pdf in a folder above. One line per licensed file, film order:
   `[start - stop], ... - <title> + <author> - <license path>`; files without a license are left out (stdout counts
   them). Envato licenses are per project: remind the user.
3. Export: `channN_vidK` (`--timeline <name>` for another) with the preset "YouTube 1080 HEVC" (missing = stop) as
   `Done_<video>.mp4` into the video folder, waits; already there -> not rendered again. Subtitle tracks off for the
   render, back on after. Before it `place.black_fades` checks the 4 V1 black fades and puts back a missing one
   (`NOT SET` -> say so).
4. Upload (`push` only, `--upload`): `Done_<video>.mp4` -> the YouTube channel `.secrets/youtube/channels.json` maps
   the workspace's `Chann_N` to (`dvr_cowork youtube upload --apply`): title / description / tags from
   `youtube_meta.json` (SEO below, run BEFORE `ledger.py done` when missing), English, Pets & Animals, not for kids,
   private. Thumbnail: `--thumb <image>` if given, else `<video folder>\thumb\done.jpg|.png`, else none ("no thumbnail:
   thumb\done.* missing"). `--publish-at` = "đăng vào 18 giờ" (PC time; a time already past -> no upload, ask again).
   Once per video (`.work/doc_edit/<video>/youtube.json`); a later `--thumb` sets only the thumbnail. Not mapped / not
   logged in / failed -> the `youtube:` line says so, the render stays.
Resolve stays open; no relink, no folder move: the user moves the folder into `_done`.

## SEO: `python -m dvr_cowork youtube seo <video folder> [--force | --pick N]`
YouTube Data API trend search (~300 quota units, cached 7 days) + one Gemini call -> `.work/doc_edit/<video>/
youtube_meta.json`: the 3 most trending titles, always `WILD <REGION> | <Gemini's middle part> | Wildlife Documentary`,
description (chapters from the spec, AI disclosure), tags <= 500 chars. Read only the stdout lines: each title must be
true to the film (no species, kill, fight or "only / first / biggest" claim the film does not show). Pick the best true
one (click pull + fit to the whole film, not the trend order) with `--pick N` before the upload. `FLAG` lines -> fix or
tell the user. Reply: the 3 titles best first, the one used + one line why, the reminder "Thông tin tài sản: Web".

After it: `hide_logo.py --pending`; copies listed -> ask only "Bạn có muốn ghi đè các file trong folder _nologo lên
các file gốc của chúng không?"; "có" -> `hide_logo.py --overwrite-all`. Reply: licenses (count), the `render:` line,
the `youtube:` line (link; private -> the user checks Studio), the overwrite question.
