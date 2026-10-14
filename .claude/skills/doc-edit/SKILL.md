---
name: doc-edit
description: Gated documentary edit of one video in DaVinci Resolve - narration on A2 (/doc-edit <audios-folder>), shot list + footage/audio match (/doc-edit plan), place on timeline "Edit" (/doc-edit place), reframe, missing-prompts for THIẾU shots, check-timelines (clip ledger per workspace D:\Chann_*), done (archive the video into <workspace>\_done). Use for /doc-edit, a new video edit with timestamp file + narration, or "phân bố voice audio theo ./audios".
---

# Doc edit

Steps 1 narration -> 2 plan -> 3 place, one per invocation; reply and STOP after each, the next runs only when the
user approves. Never chain steps, never prep shots (no unzip / logo / character-sheet work; never calls hide-logo).
Scripts do the heavy work: read only stdout; write only spec.txt, plan.json/md, loudness cache, ledger; media is
never copied or rendered. Goal: picture + narrator let the viewer follow who does what, and with eyes closed the
sound still carries it (music arc, silence before the strike, SXF on state changes). Replies in Vietnamese.

| mode | read first |
|---|---|
| `/doc-edit <audios-folder>` (step 1) | `references/narration.md` |
| `/doc-edit reframe [<video>]` | `references/reframe.md` |
| `/doc-edit check-timelines [<video>]`, `/doc-edit done [<video>]` / "xong video" | `references/check-timelines.md` |
| `/doc-edit missing-prompts` | `references/missing-prompts.md` |
| plan / place | below |

Tracks of "Edit": A1 AI-clip audio of V1 at -12 dB · A2 narrator only · A3/A4 bed (alternating, 4 s crossfades,
~-32 LUFS, original files, no merged audio) · A5 extra environment (water, rain, night) · A6 natural · A7 music ·
A8/A9 SXF.

## Step 2 - Plan: `/doc-edit plan [<audios-folder>]`

Timeline untouched. Folder = step 1's (unknown -> ask); `<video>` = its parent folder name. Step 1 must be done.

1. Read `references/edit-grammar.md`, the screenplay and the timestamp file once (not the script; never plan.json,
   audio, `_library.json`).
2. Write `.work/doc_edit/<video>/spec.txt` in batches of ~20 sentences with `cat >> spec.txt <<'EOF'` (never re-read):

       # END 29:50                       <- target length; omit = last sentence end + 2 s
       # INTRO 0:20                      <- 0:15-0:30, side shots free before it; omit = 0:15
       # [D] Peters's duiker  [GC] African golden cat
       ## 1
       4 | Wide tán rừng lúc bình minh, sương | real | sp=none size=wide,aerial set=canopy light=golden kw=mist | A3=forest,birds A7=tense
       2 | [D] Cận duiker ngẩng đầu nghe | any | sp=duiker size=close_up act=look set=forest_floor | A6=insects
       * | Lối mòn trống, nắng xiên | real | sp=none set=forest_floor size=medium light=day |

   `dur` s (`*` = rest of the sentence slot + pause, exactly one per sentence) | shot needed (Vietnamese) |
   real/ai/any/GFX | filter | audio (formats: edit-grammar.md).
3. `.venv/Scripts/python.exe .claude/skills/doc-edit/scripts/plan.py "<audios-folder>"`
   - Prints ALL spec errors grouped with `##` numbers: fix them in one pass with targeted edits, re-run.
   - YOLO-World on unmeasured clips of the spec's species (cache `.work/library/yolo.json`, normally warm via
     tag-source); many measured now -> run in background. Read only the `yolo:` line.
   - A shot no clip is long enough for -> 2-3 parts from different clips (⧉); audio stays on part 1.
   - Ledger: clips of the last 4 checked videos of the workspace are never matched; `recent ledger` line = slots
     lost, by character. Inside one video a clip may serve 3 slots (edit-grammar Source).
   - stdout lists character WEAK slots with top 3 candidates: keep, `pin=<fragment>`, or `pin=none` (THIẾU); re-run.
   - Check the `audio:` line against edit-grammar (music coverage, early-ending cues, SXF count), fix in the same pass.
   - Outputs `.work/doc_edit/<video>/plan.json` (step 3 input) and `<video>/plan.md` (user table; VO ● = narration).
4. Reply: shots, OK / WEAK / THIẾU / GFX, species missing, THIẾU and ledger-lost by character, the audio line,
   plan.md path, every audio THIẾU (slot, timecode, sound): no substitute; user downloads one or says no (-> remove
   that token). End: "Duyệt plan.md (muốn đổi shot/clip nào cứ nói), xong báo tôi để sang bước 3 (đặt lên timeline)."

User edits -> change spec.txt and re-run; never hand-edit plan.json.

## Step 3 - Place: `/doc-edit place`

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/place.py <video>

Backs up "Edit" (`Edit_bak_place_<stamp>`), imports used files into bins 1. A_roll / 2. B_roll / 3. AI_roll /
4. Audio, places V1 frame-exact (WEAK yellow) + A1 + A3-A9 (crossfades, fades, starting Clip Volume), markers: red
THIẾU (note = shot needed), yellow WEAK, blue GFX. A2 never touched. V1/A3-A9 not empty -> it stops: say what is
there and ask before `--replace` (clears those tracks after the backup; destructive, CLAUDE.md rule 2).
`--video-only` = V1 + A1 + markers. `--a1-only` = A1 of AI clips only (A1 must be empty, no backup).
"V1 gaps of 1-3 frames" must be 0.

Reply: backup, clips placed, max start deviation, gaps, audio pieces, failures, markers. End: "Duyệt timeline; slot
đỏ cần footage mới (/doc-edit missing-prompts); /doc-edit reframe để lấp viền đen + punch-in."
