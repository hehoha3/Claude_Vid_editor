---
name: doc-edit
description: Three-step documentary edit of one video in DaVinci Resolve, with a user review stop after every step. Step 1 takes an audios folder (timestamp.md + narrator_voice.mp3 + script files) and places the narration on A2 of timeline "Edit"; step 2 (/doc-edit plan) builds the shot list and matches footage/audio from the library; step 3 (/doc-edit place) puts V1, A3-A9 and THIẾU markers on the timeline; /doc-edit reframe sets zoom/position on V1 (fills black-bar shots, a few motivated punch-ins); /doc-edit missing-prompts writes generation prompts for the THIẾU shots; /doc-edit done (or the user saying the video is "Done") records its clips so the next 3 videos never reuse them. Use for /doc-edit <audios-folder>, or when the user starts a new video edit with a timestamp file and narration audio. Also runs step 1 alone from a plain request like "phân bố voice audio theo ./audios". Never calls hide-logo (character sheets are cut by process-ai-video).
---

# Doc edit

Three steps: 1 narration -> 2 plan -> 3 place. One step per invocation. After each step reply and STOP;
the next step runs only when the user says the previous one is approved. Never chain steps, never prep
shots (no unzip, logo or character-sheet work). Economy: scripts do the heavy work; read only their stdout,
write nothing to disk except spec.txt, plan.json/md, the loudness cache and the clip ledger; media is never copied or rendered.
Goal of every plan: picture + narrator together let the viewer roughly follow the story (who, doing what),
and a viewer with eyes closed still feels it (music arc, silence before the strike, SXF on state changes).

## Audio track layout (timeline "Edit")

| track | content |
|---|---|
| A1 | audio of the AI clips on V1 (step 3 places it with the video at A1_DB = -12 dB; `place.py <video> --a1-only` adds just this to an existing timeline) |
| A2 | Narrator Voice (step 1 writes here) |
| A3 | Ambience 1 - main bed; with A4 forms the continuous bed (alternating clips, 4 s overlap crossfades via SetFades, Clip Volume to ~-32 LUFS, original files only, no rendered/merged audio) |
| A4 | Ambience 2 - partner of A3: crossfade overlaps, J/L-cut, layering |
| A5 | Ambience 3 - extra environment layers placed where needed: water, rain, night, ... |
| A6 | Natural sounds |
| A7 | Music |
| A8 | SXF 1 |
| A9 | SXF 2 |

Every step that plans or places audio uses this layout. Never put anything except narration on A2.

## Step 1 - Narration: `/doc-edit <audios-folder>`

Also runs standalone from a plain request, e.g. `/doc-edit phân bố voice audio theo ./audios`.

The folder contains (names vary, match case-insensitively):
- timestamp file `*timestamp*.md` - `[MM:SS] sentence` or `[HH:MM:SS] sentence` lines (decimals ok,
  `#` heading lines are ignored).
- narration: the single audio file (`.mp3`/`.wav`).
- script (`script*.md`, `kịch_bản.md`) and screenplay (`*screenplay*.md`, per-shot visual direction) -
  not used in step 1; step 2 reads them for story context.

No timestamp file or no audio, or more than one candidate -> tell the user and stop. If the user passes a
file instead of a folder (old style `<timestamp> [audio]`), use it and take the audio from its folder.

    .venv/Scripts/python.exe -m dvr_cowork vo-sync run "<folder>/<audio>" "<folder>/<timestamp>.md"

This transcribes the audio with Whisper (cached), imports it into bin "4. Audio", backs up timeline
"Edit", and places one A2 item per sentence on its timestamp. Read only the stdout summary (open
`.work/<audio>/report.md` only for flagged rows; never open audio, transcript or plan.json).
Flags in the summary:
- `boundary_uncertain`: pause between sentences unclear -> listen to that cut.
- `pushed`: sentence starts later than its timestamp because the previous one runs long -> check if the
  offset is acceptable.
- `head_trimmed` / `tail_trimmed`: silence trimmed to fit, usually harmless.
Errors: no timeline "Edit" or A2 locked/missing -> tell the user; bad timestamp format -> show the bad line.

Reply in Vietnamese: sentences placed, backup name, flagged lines (number, timecode, flag, what to listen
for). End with: "Duyệt A2 trong Resolve, xong báo tôi để sang bước 2 (plan)."

## Step 2 - Plan (shot list + footage + audio): `/doc-edit plan [<audios-folder>]`

Nothing on the timeline changes in this step. Folder = the step 1 folder (default: the one used in this
conversation; unknown -> ask). Step 1 must be done (sentence positions come from `.work/<audio-stem>/plan.json`,
read by the script only). `<video>` = parent folder name of the audios folder.

1. Read `references/edit-grammar.md`, the screenplay (`*screenplay*.md` / `kịch_bản.md`) and the timestamp
   file once. Skip the script file (same text as the timestamps). Never open plan.json, audio, `_library.json`.
2. Write `.work/doc_edit/<video>/spec.txt` in batches of ~20 sentences, appended with
   `cat >> spec.txt <<'EOF'` (no re-reading what is already written):

       # END 29:50                       <- screenplay target length; omit = last sentence end + 2 s
       # INTRO 0:20                      <- intro length 0:15-0:30 (side shots free before it); omit = 0:15
       # [D] Peters's duiker  [GC] African golden cat   <- character tags used in "shot needed"
       ## 1
       4 | Wide tán rừng lúc bình minh, sương | real | sp=none size=wide,aerial set=canopy light=golden kw=mist | A3=forest,birds A7=tense
       2 | [D] Cận duiker ngẩng đầu nghe | any | sp=duiker size=close_up act=look set=forest_floor | A6=insects
       * | Lối mòn trống, nắng xiên | real | sp=none set=forest_floor size=medium light=day |

   Columns: `dur` (s; `*` = rest of the sentence slot incl. the pause after it, exactly one per sentence) |
   shot needed (Vietnamese) | real / ai / any / GFX | filter | audio. Filter and audio formats: edit-grammar.md.
3. Run (self-checks spec + filter vocab, matches footage and audio, no tokens):

       .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/plan.py "<audios-folder>"

   plan.py also runs YOLO-World (`scripts/yolo.py`, local GPU, 0 tokens) on the clips of the spec's species that
   are not measured yet (cache `.work/library/yolo.json`, each clip once, ~1-2 s per clip): cuts land where the
   subject is in frame and the measured shot size replaces the tag. `/tag-source` measures new clips right after
   tagging (`yolo.py --warm`), so this is normally 0. If the `yolo:` line shows many clips measured now, the cache
   was not warm: run plan with `run_in_background` and wait; spec errors stop it before YOLO starts.
   Read only the `yolo:` stdout line, never the cache.
   It prints ALL spec errors at once (grouped by kind, with `##` numbers): fix them all in one pass with
   targeted edits on those lines (never rewrite or re-read the whole spec), then re-run.
   A shot no single clip is long enough for is cut into 2, else 3 equal parts (each >= 1.2 s) from different
   clips of the same filter (⧉ in plan.md, counted on the `clip reuse` line); audio cues stay on the first part.
   Clips of the last 3 videos marked Done (`.work/doc_edit/recent_clips.json`, read by the script only) are
   never matched (inside one video a clip may serve up to 3 slots, see edit-grammar Source); the `recent ledger` line counts the slots they would have filled, by character tag.
   stdout lists only the character WEAK slots with their top 3 candidates (side-shot WEAK are kept): judge
   those. Keep, `pin=<file fragment>` another candidate, or `pin=none` (-> THIẾU); re-run.
   Check the `audio:` line against edit-grammar (music coverage, cues ending early, SXF count) and fix the
   audio column in the same pass if it is off.
   Outputs: `.work/doc_edit/<video>/plan.json` (step 3 input) and `<video>/plan.md` (table for the user:
   shot, chosen clip caption, fit, audio; VO ● = narration over the slot).
4. Reply in Vietnamese from stdout: shots, OK / WEAK / THIẾU / GFX counts, species missing from the library,
   THIẾU by character, slots lost to the ledger by character, the audio line, path of plan.md, and every audio
   THIẾU (slot, timecode, sound needed): no substitute is placed there; ask the user to download one or say no
   (no -> remove that audio token from spec.txt). End with:
   "Duyệt plan.md (muốn đổi shot/clip nào cứ nói), xong báo tôi để sang bước 3 (đặt lên timeline)."

User edits: change spec.txt (pin a clip, change filter/shot) and re-run plan.py; never hand-edit plan.json.

## Step 3 - Place: `/doc-edit place`

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/place.py <video>

Backs up "Edit" (`Edit_bak_place_<stamp>`), imports only the used files into bins 1. A_roll / 2. B_roll /
3. AI_roll / 4. Audio, places V1 (video only, frame-exact on slot ranges, WEAK clips colored yellow) and
A3-A9 (bed crossfades, fades, Clip Volume to a starting loudness per track), markers over the slot range:
red THIẾU (note = shot needed), yellow WEAK, blue GFX. A2 is never touched.
If V1/A3-A9 already hold clips the script stops: say what is there and ask before re-running with `--replace`
(clears those tracks after the backup).

`--video-only` = V1 + A1 + markers, no A3-A9. `--a1-only` = only the A1 audio of AI clips (additive, no backup, A1 must be empty). Clips are placed frame-exact with no gaps (endFrame is exclusive;
other-fps clips are measured and re-placed); stdout reports "V1 gaps of 1-3 frames", which must be 0.

Reply in Vietnamese from stdout: backup name, clips placed, max start deviation, gaps, audio pieces, failures,
markers. End with: "Duyệt timeline; slot đỏ cần footage mới (/doc-edit missing-prompts); /doc-edit reframe để lấp viền đen + punch-in."

## Reframe: `/doc-edit reframe [<video>]` (also right after step 3, or "shot bị viền đen")

Sets Zoom / Position X-Y on V1 of "Edit" (Transform only; no clip is moved, cut or replaced):

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/reframe.py <video>           # dry-run list
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/reframe.py <video> --apply   # backup Edit_bak_reframe_*, set

- `fill`: black bars (file wider than 16:9, or bars baked into the file, ffmpeg cropdetect cached in
  `.work/library/active_area.json`) -> the smallest zoom that fills the frame, crop slid toward the animal.
- punch-in, at most 15% of the shots, centred on the YOLO subject box, only if the animal stays in frame on every
  sample: `strike` (shot needed is a strike/attack/catch, 1.2x), `tiny` (character fills < 18% of the frame),
  `size` (same size as the previous shot -> next size). Max zoom 1.35 on 1080p files, 1.7 on UHD.
- Shots with a non-default Transform (user's own, or an earlier run) are skipped: re-running is safe.
Run the dry-run, show the counts, then `--apply` (Transform changes only, the backup covers them). Reply in
Vietnamese: backup name, fill / punch-in counts by reason, failures, and the timecodes to watch.

## Done: `/doc-edit done [<video>]`

Run when the user reports the video finished ("Done", "xong video"), never on your own after step 3:

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/plan.py --done <video>

Puts the clip ids (library content hash, survives moves/renames) of `<video>`'s plan.json at the top of
`.work/doc_edit/recent_clips.json`; the 4th oldest video drops off. Re-running for the same video replaces its
entry; a re-plan of a video already in the ledger still may use its own clips. Clips swapped by hand in Resolve
after the plan are not seen (the plan is the record).
Then `hide_logo.py --pending` (skill hide-logo, "Overwrite at Done"): copies listed -> ask whether the video is
exported; exported -> ask whether to overwrite the originals with the `_nologo` files; "có"/"yes" ->
`hide_logo.py --overwrite-all`, otherwise nothing changes.
Reply in Vietnamese: clips recorded, the ledger line (videos newest first), the overwrite question (or its result).

## Missing footage prompts: `/doc-edit missing-prompts`

Needs a plan.json (step 2). The user generates the clips themselves.

1. `.venv/Scripts/python.exe .claude/skills/doc-edit/scripts/missing.py <video>` lists THIẾU groups (character +
   main action, or setting + light), slots, seconds and suggested clip count (~6 s usable per generated clip).
2. Write `.work/doc_edit/<video>/prompts.txt` (overwrite): `## G<n>` then one line per clip, the suggested count,
   English `[shot_content]` only (the script adds the fixed prefix). Rules:
   - ONE species per clip (two of the same species is fine, e.g. two bulls): a chase = separate clips of the
     hunter running and of the prey running, cut together in the edit. Start with "A single <species> ...".
   - Exact species from the screenplay (African golden cat, Peters's duiker, putty-nosed monkey...), action,
     shot size, camera, setting and light from the screenplay; vary size/angle between clips of one group.
   - No gore, no text; environment groups describe the place only, no animal.
3. `missing.py <video> --write` -> `<video>/missing_prompts.txt`: prompt lines only, one per line, no headers
   (user's choice). stdout lists the save folder per group (= species name, so tag-source names the species
   the plan looks for); give those folders in the reply, never inside the file.

Reply in Vietnamese: path of missing_prompts.txt, number of prompts, save folders per character, and the follow-up:
save into the listed folders -> /process-ai-video -> /scan-source ai -> /tag-source -> /doc-edit plan -> place --replace.
