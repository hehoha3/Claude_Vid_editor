---
name: doc-edit
description: Assemble a full-AI mountain wildlife film in DaVinci Resolve from approved four-file story, numbered narrator MP3s and numbered generated MP4 shots. Use /doc-edit <audios>, ingest, plan, missing-prompts, status, check, music or done. Conform and place A2 before issuing prompts; return after shots for QC, hook selection and V1/A1 assembly; stop for user review before rendering/uploading.
---

# Doc edit: three deliberate handoffs

Read [workflow.md](references/workflow.md). Use only this package's CLI; do not invoke the upstream library planner or deleted skills. Calling an explicit phase authorizes its documented additive changes and backup. Do not ask again for routine authorized placement.

## Voice is ready — `/doc-edit <video>/audios`

1. Read canonical source, build status and exactly four outputs. Confirm the exact video path. Run `conform`; it validates all numbered audio and real duration, then rebuilds timestamps consistently. If speech overflows or pauses exceed limits, report all affected blocks and stop; no speech trimming, time stretching or guessing.
2. Load resolve-api. Run `info <video>` to confirm project/fps/scope, then `voice <video> --apply`. It creates the specified bins/tracks, backs up, places numbered MP3s on A2, writes/imports VI SRT and verifies every item. Report a subtitle API limitation accurately; never say placed if only the SRT was created.
3. Run `prompts <video>`. This covers **every non-hook slot**, including setup, body and ending; no footage-library search. The plan is `audios/visual_plan.md`; full prompts are `<video>/missing-prompt.md`, fixed ID mapping is `<video>/shot_manifest.csv`.
4. Return actual runtime, A2 count, occupancy, backup, prompt count and exact save folder `<video>/shots`. **Stop for manual shot generation.** Do not create placeholder visuals or render black timeline gaps as a finished video.

## Shots are ready — `/doc-edit ingest <video>`

1. Run `ingest`, then `sheets`. It validates exact file IDs, full decode, copying stability, duration, aspect ratio, audio and hashes. Do not rename/move the files and do not infer IDs by filesystem order.
2. Read each corresponding prompt and inspect its contact sheet. Review in manageable batches, but cover all clips. Check cast/count/marks, action and outcome, start/end continuity, terrain, light, direction, anatomy, logos and natural audio. Watch or extract additional frames for uncertain movement/impacts. A three-frame sample cannot guarantee perfect motion. For failed shots record precise defects and ask for those numbered regenerations; preserve every other file.
3. Complete `.production/shot_qc.json`: approved flag, reviewer, descriptive notes, evidence image paths. For suitable cliffhanger sources also set hook_ok and a clean six-second hook_start_s. Preserve prompt and media hashes; never set every approved flag programmatically without inspecting the images.
4. Run `hook`. It requires one reviewed, spoiler-free body source for each of five dramatic roles. Read `hook_selection.md` and compare the actual selected footage against hook narration; adjust QC choice/intensity/clean range if necessary before assembly. If a role is missing, request exactly that shot rather than use a resolution or generic vista.
5. Run `assemble --apply`. All body slots keep their exact original order; hook sources are intentional additional uses. V1/A1 are placed and linked through the entire runtime. Every append is verified, all conflicts preserve manual edits. Run `check` and report verified counts, hook choices, runtime, gaps, caveats and backup.
6. **Stop for user review.** Do not auto-render or change color/voice/story while waiting.

## User approved — `/doc-edit done <video>`

Run `check`, then `done --apply`. This validates the **live edited timeline**, exports with the configured preset and returns a job ID. Poll `render-status` until status VERIFIED; report failures with backup/receipt. Do not call a RUNNING render completed or re-render just because another turn started. Do not overwrite or move media/video folders. Keep Resolve open.

If YouTube delivery is configured, read [youtube-metadata.md](references/youtube-metadata.md), run `youtube-seo <video>`, write `seo_draft.json`, run `youtube-seo <video> --write`, then use `youtube-upload <video>` (channel from the `Chann_N` folder) without --apply to show the exact destination/body/file. The user's approval of those final values allows recording its request_hash as approved_request_hash in youtube_meta.json and applying that exact request. Default private; schedule only if explicitly requested with timezone. Always set realistic AI disclosure. If approval was already given for the same exact preview, proceed without a second confirmation. An unknown upload result blocks duplicate retries.

`music <video> <file> --start <seconds> --apply` places only selected music with a `.license.txt` record on A3. Do not scan an external library or invent rights. Initial gain is a listening starting point. A3 may stay empty until the user supplies licensed music.
