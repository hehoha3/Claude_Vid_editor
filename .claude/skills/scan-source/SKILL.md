---
name: scan-source
description: Re-index the source libraries (real footage, AI clips, audio) after files were added, moved, renamed or deleted. Use for /scan-source, when the user added/sorted/moved footage or audio, or to refresh/check the source index.
---

# Scan source

The **user sorts the files**; this skill only syncs the indexes (no vision, no file moves, 0 tokens beyond stdout).
Z: is read-only: its indexes live in `.work/library/` (also SFX / Sound). Never open a `_library.json` whole.

    .venv/Scripts/python .claude/skills/scan-source/scripts/scan_source.py          # every root
    .venv/Scripts/python .claude/skills/scan-source/scripts/scan_source.py ai        # or one root name below

- Video roots belong to a region (`REGION` in scan_source.py; `/doc-edit <audios> <region>` uses only its own).
- Audio roots are shared (user 2026-10-20): `Z:\Unseen\Amazona\audio`, `Z:\Unseen\SFX`, `Z:\Unseen\Sound`. New audio
  root = a line in ROOTS + plan.py CATEGORY (+ audio-expert index.py CATEGORY).
- Unreachable root -> skipped ("NOT REACHABLE"), index untouched. `__MACOSX` folders and `._*` files ignored.

| root | index | folders |
|---|---|---|
| `video` `Z:\Unseen\Amazona\video` (amazon, real, `source: real`) | `.work/library/video_library.json` | `<subject>/` still, `<subject>/action/` action, `birds/` flat, `landscape/<setting>/`, `supplementary_shots/<subject>/` (frogs, insects, gecko, flowers: cutaways, `supplementary: true`) |
| `ai` config.toml `ai_video` (amazon, `source: ai`, default `D:\AI_video`) | `.work/library/AI_video_library.json` | as real footage; files are `shot_NNN` so `title_hint` is null |
| `africa_video` `Z:\Unseen\Động vật\AAA Trên cạn` (africa, real) | `africa_video_library.json` | `<species folder>/...` (Vietnamese or English) -> `subject` = English species via `AFRICA_FOLDERS` (new folder name -> add it there); `AI_copyright\` excluded (own root) |
| `africa_ai` `...\AAA Trên cạn\AI_copyright` (africa, ai) | `africa_ai_library.json` | `AI\<action>\<species>\`, `bản quyền\<channel>\`; action = under Chạy / Rình / Đi bộ tới mồi |
| `africa_ai_check` `D:\AI_video\_africa` (africa, ai) | `africa_ai_check_library.json` | (2026-10-22) `_check\` new, `<species>\` filed by `organize.py --africa`; kept out of the `ai` index |
| `savannah` `Z:\Unseen\savannah` (africa, real) | `savannah_library.json` | scenery, `subject` = landscape |
| `Z:\Unseen\Amazona\audio` | `.work/library/audio_library.json` | `<category>/` as the user names them (ambience_sound, Nature_sound, tense_music...) |

Entries are keyed by content hash: moved / renamed files keep their entry (and the older vision tags of 62 video
clips). Per file: path, folder fields (video: subject, action, setting_folder; audio: category), duration, video specs
(size, fps, has_audio) or audio specs (sample_rate, channels), title_hint (stock name without date/ID suffix).

**Output** per root: `<kind>: N files | new, moved, removed, duplicates`, then NEW / MOVED / REMOVED / DUPLICATE lists.
**Reply** (Vietnamese): counts + lists (shorten long ones); DUPLICATE -> ask which copy to delete; files directly in a
root (folder field null) -> say they belong in a folder.

## Using the indexes (doc-edit plan)
Load the JSON in Python and filter: video by `subject` + `action`, then `tags`, then `title_hint`; audio by `category` +
`title_hint` + `duration`. Return a short list (path, title, duration); never paste a whole index.
