---
name: tag-source
description: Vision-tag new clips in the AI and real footage indexes once each with Sonnet subagents (species, action, shot size, light, mood, best in/out, issues) so doc-edit finds footage without re-watching. Use for /tag-source, after scan-source reports NEW clips, or to tag/describe the footage library.
---

# Tag source

Tags live per content hash in the root's index (`scan_source.index_of`: Z: roots in `.work/library/`; `clip.tags`,
`"v": 2`): rename / move keeps them, a clip is never tagged twice. Run `scan-source` first (hashes must be current:
`process-ai-video` rewrites files). Never run git (the user handles it, rule 2026-10-11).

    .venv/Scripts/python .claude/skills/tag-source/scripts/tag_source.py status
    .venv/Scripts/python .claude/skills/tag-source/scripts/tag_source.py prepare [<video root>...] [--limit N] [--sample N]
    .venv/Scripts/python .claude/skills/tag-source/scripts/tag_source.py apply batch_03 batch_04
    .venv/Scripts/python .claude/skills/tag-source/scripts/tag_source.py review batch_01 batch_02

- Roots: `video`, `ai` (amazon), `africa_video`, `africa_ai`, `africa_ai_check`, `savannah` (africa); none = all;
  `--sample N` = N per root.
- `prepare` = 2x2 contact sheet per untagged clip (frames 1-4 at 15/40/65/90 %) in `.work/tag_source/sheets/` +
  batch files `.work/tag_source/batch_NN.json` (20 clips each). Files > 10 min (`AI_copyright\bản quyền` films)
  are never prepared.
- Africa `folder` = English species from the user's folder (scan_source `AFRICA_FOLDERS`); null when the folder names
  no single species (the tagger names what it sees).
- **Africa = tag by species, never all** (user 2026-10-20, cheap but good): `--subject lion,hyena --sample 60` = 60
  untagged clips per root and species, spread over the folder (a later round picks other clips). Called by doc-edit
  (new-video.md B1b) for a film's cast; the user may also ask for a species.

## Tagging loop
1. Per batch one Agent (`model: sonnet` (user choice 2026-10-07: tags matter more than cost),
   `subagent_type: general-purpose`), up to 4 in parallel, `run_in_background`, with only this prompt (never paste
   the tagger instructions):
   `Read C:\Users\ADMIN\Claude_editor\.claude\skills\tag-source\tagger_prompt.md and do exactly what it says with
   {BATCH} = batch_NN, cwd C:\Users\ADMIN\Claude_editor.`
   A batch of <= 6 clips: one agent in the foreground.
2. On return check `tool_uses >= clips in batch + 1`. Fewer = tagged from names: delete `batch_NN_result.json`, rerun
   the batch, never apply it.
3. `apply batch_NN`. MISSING ids -> rerun only if > 2; off-vocab values are dropped and listed.
4. New kind of footage: `prepare --sample 40`, tag, `review`, STOP for the user to check `.work/tag_source/review.md`
   before the rest. Open sheets yourself only to settle a disputed tag (max ~6 images).
5. `apply` also YOLO-measures the clips it tagged (local GPU, 0 tokens, ~1.5-2 s per clip, cached by content hash so
   organize keeps it); `/doc-edit plan` never waits on them. Many batches = minutes: `run_in_background`.
   `--no-yolo` = tags only. Old unmeasured backlog stays (`doc-edit/scripts/yolo.py --warm`, only when asked).

Reply (Vietnamese): batches applied, clips tagged / total (`status`), MISSING and off-vocab notes, the `yolo:` line.

## File the new AI clips (after apply)
`D:\AI_video\_check` = the user's holding folder (never a species). Every tagged clip there (`shot_*` and generator
names like `media-generation-*`; `--shot-only` = only `shot_*`) is renamed `<species>_<caption keywords>-<size>.mp4`
and moved into its species / `landscape/<setting>` folder (only clips planned to move are touched):

    .venv/Scripts/python .claude/skills/tag-source/scripts/organize.py --apply   # move + verify (no dry-run step needed)
    .venv/Scripts/python .claude/skills/tag-source/scripts/organize.py --africa --apply   # D:\AI_video\_africa\_check -> _africa\<species>

- Africa (user 2026-10-22): same rules on `D:\AI_video\_africa` (root africa_ai_check, ALIAS_AFRICA names; folders from
  `.work\scripts\make_africa_ai_folders.ps1`), then `scan_source.py africa_ai_check`.
- Stays in `_check`: sure=false, a blocking issue (morph, unnatural, logo, watermark, text, dark, blur), or no folder
  for the species (never create one unasked).
- Then `scan_source.py ai`: must report "moved N", never removed.
