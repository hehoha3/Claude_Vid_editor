# Mountain AI wildlife workspace

Reply in Vietnamese. Produce original 8–15 minute (runtime fits the story; longer only when requested) **AI-generated mountain wildlife dramatizations**. Use one continuous survival story with a locked cast and geography. Follow the user's five-stage workflow. This workspace supersedes the upstream long-form footage-library workflow.

## Commands and authorized phases

- `/create-doc-mov Chann_N` (recommend trending concepts) or `/create-doc-mov Chann_N <youtube_url>` (adapt: keep archetype + tension mechanics, change the rest, ask about cast): after the user approves concept and cast, create `D:\Chann_N_*\vid_DDMMYY_N`, then continue as below. Research via YouTube API (`youtube-trends`, `youtube-reference`) + vidIQ is allowed here, falling back to YouTube API only when vidIQ credits run out; still no TTS/browser generation.
- `/create-doc-mov <video-folder> <minutes> <concept>`: write `.production/story.json`, build and validate the four Markdown files in `audios/`, then **stop for the user to generate voice**. No TTS/API/browser generation.
- User says voice is ready, or `/doc-edit <video>/audios`: conform actual numbered MP3s, place A2 and VI subtitles, produce full-timeline plan and `missing-prompt.md` + `shot_manifest.csv`, then **stop for the user to generate shots**.
- User says shots are ready, or `/doc-edit ingest <video>`: verify `shots/1.mp4…N.mp4`, view images and compare with each prompt, complete visual QC, select five actual spoiler-free hook sources, then assemble V1 + linked A1. Preserve every body slot in narrative order. **Stop for the user's review**.
- User says OK and `/doc-edit done <video>`: validate the actual edited timeline, start render, check render status until verified. Prepare/preview upload when configured. Upload only the exact approved metadata, channel and visibility/schedule. Preserve the user's manual changes.
- `status`, `check`, `music` are scoped helpers. A request for one shot never authorizes rebuilding the timeline.

Run `.venv/Scripts/python.exe -m dvr_cowork ...` from this workspace. See README for command spelling. Skills load on demand: create-doc-mov, doc-edit, resolve-api. No other skills are required.

## Fixed production contract

- Runtime includes 30s hook + 30s setup. Default hook: five 6s shots; all timeline shots 6–9s. No fixed 60-scene rule, 10s source requirement, 90s intro, or separate Open/Master workflow.
- Video folders are always `D:\Chann_N_*\vid_DDMMYY_N`. One Resolve project `vid_DDMMYY_N` holds the same-numbered video of every channel (one video per channel). Each channel has its own top bin `Chann_N` and its own timeline `Edit` in `Chann_N/4. Timeline`; timelines are identified by that bin, not by name. Explicit source `resolve_project` can bind a different project name.
- Bins under each `Chann_N`: `1. shots`; `2. Audio/Narrator`; `2. Audio/Music`; `3. Graphics/sub-title`; `4. Timeline`. Never write into another channel's bin or Edit.
- V1 picture; A1 always contains sound of the corresponding V1 source (entire runtime, including after 08:00); A2 **Narrator Voice**; A3 **Music**. Add no A4+ tracks. Starting gains: A1 −12dB, A3 −24dB; these are not a loudness guarantee.
- Canonical authoring source is `<video>/.production/story.json`. Four outputs: `screenplay.md`, `timestamp.md`, `transcript.md`, `visual_plan.md`. `transcript.md`: English narration only; **one nonblank physical line = one numbered MP3** (a line may contain a naturally connected multi-sentence paragraph); blank line between scenes. Do not count visually rendered Markdown paragraphs. Timestamp EN/VI have matching counts/onsets and full translations.
- Narration occupancy: recommend 85–92%, gate 80–98%; normal rests ≤3s, exception ≤6s only with a reason. Actual audio files may contain internal silence: listen, do not equate container duration to speech. Never speed up, trim speech or overlap narration to force a target.
- Prompts have duration 6–9s matching each slot, 16:9, four timed beats, expanded character/environment locks, fixed direction, one coherent take and natural sound. No extra cast/injuries, blood, gore, watermark or unrequested slow motion.

## Reliability and preservation

- File-based state only: per-video JSON/CSV/Markdown plus OS locks. No database, Gemini, embedding service, library scan/tag/rename, broad media crawler, logo-removal or grading automation.
- Numbered file ID = issued prompt ID, never natural-sort position. Reject aliases, missing/extra numbers, corrupt/still-copying files and undersized clips. Do not rename user media.
- Prompt identity and media hashes invalidate stale QC. View actual frames; inspect moving action when uncertain. Metadata is never proof of anatomy, motion, continuity or hook strength. Bad footage stays unapproved and gets a specific regeneration request.
- Resolve writes are sequential, additive, globally locked and backed up. Reject collisions/manual changes; never clear, ripple, delete, undo, overwrite, silently re-plan or replace media. Every append verifies actual frames. On failure report backup and completed journal entries; do not claim completion.
- Do not alter unrelated projects, timelines, bins or media. Do not access `_pushed`, write to `Z:`, move video folders, or delete media. Keep OAuth JSON/token files under ignored `.secrets/youtube/`; never read them aloud or commit them.
- `/doc-edit done` renders from the live timeline, preserves manual edits and never overwrites a previous render. Subtitle burn-in is controlled by the named render preset; SRT stays available separately. The agent must say when subtitle API import fails.
- Upload is private by default and always discloses realistic synthetic media. Public scheduling requires an explicit approved timezone-aware instant. Unknown upload outcome blocks retry until Studio is reconciled; do not reset the receipt automatically.
- Report what was actually checked. This repository's automated tests do not replace a live Windows/Resolve smoke test.
