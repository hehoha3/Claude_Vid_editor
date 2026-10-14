---
name: scan-source
description: Re-index the source libraries (real footage, AI clips, audio) after files were added, moved, renamed or deleted. Use for /scan-source, when the user added/sorted/moved footage or audio, or to refresh/check the source index.
---

# Scan source

The **user sorts the files**; this skill only keeps the indexes in sync. Drive Z: is read-only: its indexes live in
`.work/library/` (also SFX / Sound / Sound Animal V1). No vision, no file moves, 0 tokens
beyond the script output. Never open a `_library.json` whole.

    .venv/Scripts/python .claude/skills/scan-source/scripts/scan_source.py          # all three
    .venv/Scripts/python .claude/skills/scan-source/scripts/scan_source.py ai        # or video / audio

| root | index | folders |
|---|---|---|
| `Z:\Unseen\Amazona\video` (real footage, `source: real`) | `.work/library/video_library.json` | `<subject>/` still, `<subject>/action/` action, `birds/` flat, `landscape/<setting>/`, `supplementary_shots/<subject>/` (frogs, insects, gecko, flowers: cutaways, `supplementary: true`) |
| config.toml `ai_video` (AI-generated, `source: ai`, default `D:\AI_video`) | `.work/library/AI_video_library.json` | same rules as real footage; files are `shot_NNN` so `title_hint` is null |
| `Z:\Unseen\Amazona\audio` | `.work/library/audio_library.json` | `<category>/` as the user names them (ambience_sound, Nature_sound, tense_music...) |

Each file is keyed by a content hash, so moved/renamed files keep their entry (and the older vision tags of
62 video clips). Per file: path, folder fields (video: subject, action, setting_folder; audio: category),
duration, video specs (size, fps, has_audio) or audio specs (sample_rate, channels), title_hint (stock file
name without the date/ID suffix).

Output per root: `<kind>: N files | new, moved, removed, duplicates`, then NEW / MOVED / REMOVED /
DUPLICATE lists. Reply in Vietnamese with counts and lists (shorten long lists); for DUPLICATE ask which copy
to delete. Point out files sitting directly in a root (folder field null): they should go in a folder.

## Using the indexes later (doc-edit step 2)

Load the JSON in Python and filter: video by `subject` + `action`, then `tags` where present, then
`title_hint`; audio by `category` + `title_hint` + `duration`. Return a short list (path, title, duration);
never paste a whole index into the conversation.
