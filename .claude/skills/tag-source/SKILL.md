---
name: tag-source
description: Vision-tag new clips in the AI and real footage indexes once each with Sonnet subagents (species, action per frame, sex, age, predation outcome, shot size, light, mood, best in/out, issues) so doc-edit finds footage without re-watching; --retag adds the story fields to clips tagged before. Use for /tag-source, after scan-source reports NEW clips, or to tag/describe the footage library.
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
- **Story fields** (user 2026-10-23, doc-edit story first): the tagger also gives `sex`, `age`, `outcome`
  (none / miss / catch / kill / unknown), `phase` (action in frames 1-4) and the actions `hide` / `chase` / `catch`
  (old clips keep `hunt`). Clips tagged before get them with
  `prepare <roots> --retag action,sex,age,outcome,phase --subject lion --sample 60`: same sheets, same agent loop,
  the tagger writes only those keys, `apply` merges them (caption, best, YOLO kept; `tags.rt` = fields done).
  Retag only a film's cast when its plan's `truth:` line shows many sex-unseen WEAK picks or refusals, never all.
- **Africa = tag by species, never all** (user 2026-10-20, cheap but good): `--subject lion,hyena --sample 60` = 60
  untagged clips per root and species, spread over the folder (a later round picks other clips). Called by doc-edit
  (new-video.md B1b) for a film's cast; the user may also ask for a species.

## Tagging loop
Tokens (user 2026-10-23): `prepare --retag` (and `tag_source.py no-animal`) fill the story fields of scenery clips
without vision and drop their rows from untagged batches (an emptied batch `[]` is skipped); the tagger opens a
batch's images in one parallel Read; one agent does 4 batches (~half the tokens of 1 per agent).
1. Per 4 batches one Agent (`subagent_type: tagger` = Read + Write only, sonnet (user choice 2026-10-07: tags matter
   more than cost); not loaded yet -> `general-purpose`, `model: sonnet`), up to 4 in parallel, `run_in_background`,
   with only this prompt (never paste the tagger instructions):
   `Read C:\Users\ADMIN\Claude_editor\.claude\skills\tag-source\tagger_prompt.md and do exactly what it says for
   {BATCH} = batch_NN, then batch_NN+1 ... (one after another), cwd C:\Users\ADMIN\Claude_editor. Final reply: one
   line "batch_NN N, ...".`
   A batch of <= 6 clips: one agent in the foreground.
2. On return check `tool_uses >= clips in its batches + 1`. Fewer = tagged from names: delete `batch_NN_result.json`,
   rerun the batch, never apply it. A stopped agent's result files are never applied either (rerun).
3. `apply batch_NN`. MISSING ids -> rerun only if > 2; off-vocab values are dropped and listed.
4. New kind of footage: `prepare --sample 40`, tag, `review`, STOP for the user to check `.work/tag_source/review.md`
   before the rest. Open sheets yourself only to settle a disputed tag (max ~6 images).
5. `apply` also YOLO-measures the clips it tagged (local GPU, 0 tokens, ~1.5-2 s per clip, cached by content hash so
   organize keeps it); `/doc-edit plan` never waits on them. Many batches = minutes: `run_in_background`.
   `--no-yolo` = tags only. Old unmeasured backlog stays (`doc-edit/scripts/yolo.py --warm`, only when asked).

6. After the last apply of a session: `.venv/Scripts/python.exe .work/tools/library_db.py sync` (Postgres query
   mirror of the JSON indexes + ledgers, user 2026-10-24; no server running -> say so, the JSON is still the truth).
   Questions about the library ("how many female lions running, unused in the last 6 videos") ->
   `library_db.py query "SQL"` instead of a Python script over the JSON.

Reply (Vietnamese): batches applied, clips tagged / total (`status`), MISSING and off-vocab notes, the `yolo:` line.

## File the new AI clips (after apply)
`D:\AI_video\_check` = the user's holding folder (never a species). Every tagged clip there (`shot_*` and generator
names like `media-generation-*`; `--shot-only` = only `shot_*`) is renamed `<species>_<caption keywords>-<size>.mp4`
and moved into its species / `landscape/<setting>` folder (only clips planned to move are touched):

    .venv/Scripts/python .claude/skills/tag-source/scripts/organize.py --apply   # move + verify (no dry-run step needed)
    .venv/Scripts/python .claude/skills/tag-source/scripts/organize.py --africa --apply   # D:\AI_video\_africa\_check -> _africa\<species>

- Africa (user 2026-10-22): same rules on `D:\AI_video\_africa` (root africa_ai_check, ALIAS_AFRICA names; folders from
  `scripts\make_africa_ai_folders.ps1`), then `scan_source.py africa_ai_check`.
- Stays in `_check`: sure=false, a blocking issue (morph, unnatural, logo, watermark, text, dark, blur), or no folder
  for the species (never create one unasked).
- Then `scan_source.py ai`: must report "moved N", never removed.
