# Intro: `/doc-edit intro <video> [<music file>]` (user 2026-10-25, last step of a video)

The intro runs 0:00 -> story 1 (`# INTRO` / `# STORY 1`, 1:30-2:00 by the screenplay); its music ends exactly there
(intro end = music end). Needs: A2 placed (vo-sync, narrator from 0:03.6), plan.json, the body placed with
`--skip-intro`, the intro range 0:00 -> story 1 still empty on V1 / A1 / A3-A9.

1. Music + fit, one call:

       .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/intro.py <video> ["<music file>"]

   No file: it ranks the `D:\Music` tracks that have their Pixabay license beside them (`*-<id>-license.txt`,
   `*-<id>.txt`, any txt naming the id; the library music only when there is none; early climax, or a quiet / mysterious start that rises before
   ~45 s; hits per 10 s, steady tempo, energy that holds; tracks already on this video's A7 and the intro music of the 6 latest videos of the same channel + the other videos of this day project skipped; user 2026-10-30: only
   'căng, dồn dập' tracks ranked = tense / percussive name, >= 90 BPM or >= 9.5 hits per 10 s, energy holds >= 85 %), prints the top 5
   and takes the best. A file from the user: only that one (any drive; Z: is only read). Either way the track keeps
   its own start and ending: whole bars are cut out of the middle or repeated there (joints on bar lines), the
   leftover < 1 bar comes off the tail -> `.work/doc_edit/<video>/intro_music.json` only (source pieces + fades).
   No audio file is ever written (user 2026-10-26): the cut, joints and fades are items on A7 of the timeline.
   `free tempo` in its line = no trusted bar grid: say the joints need a listen (timecode).
2. `plan.py "<audios-folder>" > <work>/plan_stdout.txt 2>&1`, read the summary as in new-video B3. `intro music:` must
   name the track without STALE; `intro beat:` = cuts on its hits / bars; `intro outro:` = the last landscape
   fades out at the music end, story 1 fades in. Intro THIẾU / WEAK: judge them (edit-grammar Opening), fix the
   beats part / spec, re-run.
3. `place.py <video> --intro` (backup; only 0:00 -> intro end on every track; the music's source file on A7 from 0:00 as its pieces back to back, short fades at the bar joints, the tail fade on the last, the 1 s from black; story 1's bed pre-lap on A5,
   imported into bin "7. Open"). Range not empty -> it stops: report what is there, ask.

Reply: music (picked: top 5 in one line each; or the user's), its `license:` line (NONE -> say so), fit line, intro cuts on the beat, placed / backup,
intro THIẾU (timecodes), what to listen to (joints, the music end into story 1).
