---
name: tag-source
description: Vision-tag the clips of the source indexes (D:\AI_video AI clips, Z:\Unseen\Amazona\video real footage) once per clip with Sonnet subagents - species, action, shot size, angle, light/time of day, setting, mood, direction, best in/out, issues - so doc-edit can find footage without looking at video again. Use for /tag-source, after scan-source reports NEW clips, or when the user asks to tag/analyse/describe the footage library.
---

# Tag source

Phase 1 of LIBRARY_PLAN.md. Tags are stored per content hash in the root's index (`scan_source.index_of`: Z: roots in `.work/library/`)
(`clip.tags`, `"v": 2`), so renaming/moving keeps them; a clip is never tagged twice. Run `scan-source`
first (hashes must be current: `process-ai-video` rewrites files).

    .venv/Scripts/python .claude/skills/tag-source/scripts/tag_source.py status
    .venv/Scripts/python .claude/skills/tag-source/scripts/tag_source.py prepare [video|ai] [--limit N] [--sample N]
    .venv/Scripts/python .claude/skills/tag-source/scripts/tag_source.py apply batch_03 batch_04
    .venv/Scripts/python .claude/skills/tag-source/scripts/tag_source.py review batch_01 batch_02

`prepare` makes a 2x2 contact sheet per untagged clip (frames 1-4 at 15/40/65/90 %) in
`.work/tag_source/sheets/` and batch files `.work/tag_source/batch_NN.json` (20 clips each).

## Tagging loop
1. For each batch spawn one Agent (`model: sonnet` (user choice 2026-10-07: tags matter more than cost), `subagent_type: general-purpose`) with the prompt below,
   up to 4 in parallel, `run_in_background`.
2. When it returns, check `tool_uses >= clips in batch + 1`. Fewer = it tagged from names: delete
   `batch_NN_result.json` and rerun that batch. Never apply such a result.
3. `apply batch_NN`. MISSING ids -> rerun only if > 2; off-vocab values are dropped and listed.
4. First run on a new kind of footage: `prepare --sample 40`, tag, `review`, and STOP for the user to check
   `.work/tag_source/review.md` before tagging the rest. Do not open the sheets yourself except to settle
   a disputed tag (max ~6 images).

Reply (Vietnamese): batches applied, clips tagged / total (`status`), MISSING and off-vocab notes.

## File the new AI clips (after apply)
`D:\AI_video\_check` is the user's holding folder (never a species). To rename the tagged `shot_*` clips there
as `<species>_<caption keywords>-<size>.mp4` and move them into their species / `landscape/<setting>` folder:

    .venv/Scripts/python .claude/skills/tag-source/scripts/organize.py           # dry-run, show plan
    .venv/Scripts/python .claude/skills/tag-source/scripts/organize.py --apply   # move + verify

Clips stay in `_check` when sure=false, they have a blocking issue (morph, unnatural, logo, watermark, text, dark,
blur), or no folder exists for the species (never create one unasked). Then `scan_source.py ai`: must report
"moved N", never removed.

## Tagger prompt (fill BATCH)

```
You tag wildlife documentary clips for an editor. Read the file .work/tag_source/BATCH.json (cwd
C:\Users\ADMIN\Claude_editor). For EVERY row, open its "image" with the Read tool and look at it before
writing anything: a 2x2 contact sheet of 4 frames from one clip, numbered 1-4 (top-left, top-right,
bottom-left, bottom-right) in time order. Tag only what you SEE. "folder" is the user's sorting (usually
the main animal) - use it to name the species when the image agrees; never tag from title_hint or the
file name alone.

Write .work/tag_source/BATCH_result.json: {"<id>": {...}, ...} with exactly these keys:
 species: list of common names, lowercase singular ("jaguar", "capybara", "howler monkey"); [] if none.
          The main animal = the folder name (singular, e.g. folder "Eagle" -> "eagle") unless the image
          clearly shows a different kind of animal (folder jaguar, image a monkey). Do not narrow it to a
          sub-species from a silhouette. Folders landscape, bird(s), insects are not a species: name what you
          see (birds: e.g. "toucan", "parrot", "kingfisher"). Add other animals you see (prey, background).
 count: none|one|two|few|many   (animals in frame)
 action: only what clearly happens in the frames ("hunt" = chasing or catching live prey; mouth or
         hands in water = drink; still animal looking around = look). List from rest, sleep, look, walk, run, stalk, hunt, attack, eat, feed (adult feeding its young only; nectar, fruit, prey = eat), drink, swim, fly, perch, climb,
         hang, jump, fight, groom, play, call, carry_young, none
 shot_size: extreme_close|close_up|medium|wide|aerial   (size of the main subject; landscape -> wide/aerial)
 angle: eye|low|high|top_down   (camera looks up at the subject, sky behind it = low)
 camera: static|moving   (background shifts between frames = moving)
 light: day|golden|dusk|night|moon
 setting: list from canopy, forest, forest_floor, undergrowth, river, riverbank, lake, swamp, waterfall,
          underwater, grassland, rock, cave, sky, moon, mountain, village
 weather: clear|mist|rain|storm|none
 mood: calm|tense|dramatic|playful|majestic|eerie
 direction: left|right|toward|away|none   (way the main subject moves or, if still, faces on screen)
 good: frame numbers (1-4) usable in an edit: subject clear, sharp, no AI deformation, no logo/text
 issues: list from logo, text, morph (only when "source" is "ai": melted limbs, extra legs, warped faces;
         real camera footage never morphs - motion blur there is "blur"), unnatural (anything a real wildlife
         camera would never film: butcher-cut meat, plastic-looking food, impossible pose or situation, wrong
         anatomy for the species), blur, dark,
         watermark, frame_cut (subject cut by the frame edge)
 caption: one plain sentence an editor can search, e.g. "Jaguar stalks through dense undergrowth at
          night, close on its face"
 sure: true if the image is clear, false if you are guessing (tiny or dark subject)
Use only the listed words. Reply with one line: "<n> clips tagged".
```
