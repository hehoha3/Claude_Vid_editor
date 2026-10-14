# Step 1 - Narration: `/doc-edit <audios-folder>` (or "phân bố voice audio theo ./audios")

Folder (names case-insensitive): `*timestamp*.md` (`[MM:SS] sentence` / `[HH:MM:SS]`, decimals ok, `#` lines
ignored), one narration audio (`.mp3`/`.wav`), script (`script*.md`, `kịch_bản.md`) and screenplay
(`*screenplay*.md`) used only in step 2. Missing timestamp/audio or several candidates -> tell the user, stop.
A file instead of a folder (old `<timestamp> [audio]`) -> use it, audio from its folder.

    .venv/Scripts/python.exe -m dvr_cowork vo-sync run "<folder>/<audio>" "<folder>/<timestamp>.md"

Whisper (cached) -> imports into bin "4. Audio", backs up "Edit", one A2 item per sentence on its timestamp.
Read only stdout (`.work/<audio>/report.md` only for flagged rows). Flags: `boundary_uncertain` (listen to that
cut), `pushed` (starts late, previous runs long: offset ok?), `head_trimmed`/`tail_trimmed` (usually harmless).
Errors: no "Edit" / A2 locked or missing -> tell the user; bad timestamp -> show the line.

Reply: sentences placed, backup, flagged lines (number, timecode, flag, what to listen for). End:
"Duyệt A2 trong Resolve, xong báo tôi để sang bước 2 (plan)."
