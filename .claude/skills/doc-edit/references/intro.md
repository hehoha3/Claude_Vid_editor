# Intro music (part of the new-video run, user 2026-10-31: no separate `/doc-edit intro` command)

The intro runs 0:00 -> story 1 (`# INTRO` / `# STORY 1`, 1:30-2:00 by the screenplay); its music ends exactly there
(intro end = music end); it starts on the impact's hit (~0:01, user 2026-11-06), which intro.py picks at the same
time (`dvr_cowork/impact.py`, written into intro_music.json; plan.py then puts black 0:00 -> hit and the opener on the
hit). Needs: A2 placed (narrator from 0:03.6) and plan.json. Called from
`references/new-video.md` step C, before the prompts (D) and the one `place.py <video>` (E).

1. Music + fit, one call:

       .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/intro.py <video> ["<music file>"]

   No file (the default): it ranks the `D:\Music` tracks that have their Pixabay license beside them (`*-<id>-license.txt`,
   `*-<id>.txt`, any txt naming the id) and the `D:\Audio_lib\intro` tracks (Epidemic edit / Suno, `<stem>.license.txt`,
   audio-expert fetch); the library music only when there is none; early climax, or a quiet / mysterious start that rises before
   ~45 s; hits per 10 s, steady tempo, energy that holds; tracks already on this video's A7, the intro music of the 6
   latest videos of the same channel and of every other film of this day project (from the folder name, before
   anything is placed) skipped; user 2026-10-30 / 2026-11-05: only 'căng, dồn dập' tracks ranked = tense /
   percussive name, no calm name, >= 90 BPM or >= 9.5 hits per 10 s, energy holds >= 85 %; tense cinematic, heavy
   drums, wild: drum / tribal / war / taiko / primal names rank higher), prints the top 5
   and takes the best. A file the user names: only that one (any drive; Z: is only read). Either way the track keeps
   its own start and ending: whole bars are cut out of the middle or repeated there (joints on bar lines), the
   leftover < 1 bar comes off the tail -> `.work/doc_edit/<video>/intro_music.json` only (source pieces + fades).
   No audio file is ever written (user 2026-10-26): the cut, joints and fades are items on A7 of the timeline.
   `free tempo` in its line = no trusted bar grid: say the joints need a listen (timecode).
2. `plan.py "<audios-folder>" > <work>/plan_stdout.txt 2>&1`, read the summary as in new-video B3. `intro music:` must
   name the track without STALE; `intro beat:` = cuts on its hits / bars (cuts left off the beat sit on a narration
   onset: name them to listen to); `intro outro:` = the last landscape fades out at the music end, story 1 fades in.
   Intro THIẾU (WEAK picks count as THIẾU): judge them (edit-grammar Opening), fix the beats part / spec, re-run;
   what stays THIẾU gets its prompt in step D.
3. Placed with the body by `place.py <video>` (backup; the music's source file on A7 from 0:00 as its pieces back to
   back, short fades at the bar joints, the tail fade on the last, the 1 s from black; story 1's bed pre-lap on A5;
   imported into bin "4. Audio/Music", user 2026-11-05). A user's other track or an intro re-cut later: `intro.py <video> "<file>"`, `plan.py`,
   then the intro range must be emptied first (destructive: list the items, the user's yes, backup) and
   `place.py <video> --intro`.

Reply lines: music (picked: top 5 in one line each; or the user's), its `license:` line (NONE -> say so), fit line,
intro cuts on the beat, intro THIẾU (timecodes), what to listen to (joints, the music end into story 1).
