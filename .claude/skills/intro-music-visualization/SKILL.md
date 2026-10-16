---
name: intro-music-visualization
description: Builds a music-synced intro montage on the empty timeline "Open" - picks a tense track, maps beats/hits/drops, fills bin "7. Open", designs and reviews the cut, places V1/A1/A7 + markers for the user to finish. Use for /intro-music-visualization, "dựng intro theo nhạc", "cắt theo beat / bass / drop", or any opening montage synced to music. Never touches "Edit" or "Master".
---

# Intro music visualization

Reply in Vietnamese (terms in English: beat, bar, drop, hit, B5...). Read `references/intro-grammar.md` once per session.
Order: **music -> map -> cast + hero reservation -> pool -> design -> storyboard review x2 -> build -> readback**.
No template: each intro is designed from its own music and footage; the first frame is a strong image that answers the
first sound. Data: `.work/intro_mv/<name>/` (`music_map.json`, `cuts.txt`); `<name>` = project / video name.
Claude builds, the user reviews and finishes by hand: no stop before the build; ask only what rule 9 requires.
Tokens: read script stdout only; images only as storyboards (2 per pass, max ~6 per intro); never watch video.

## Steps
1. **Context**: `dvr info` (project, timeline "Open" exists?). Cast = the film's characters: the `# [X] species` header of
   `.work/doc_edit/<video>/spec.txt` (1 grep line). The intro introduces this cast; predators lead.
2. **Music** (READ ONLY folders, see music_pick.py). Skip if the user names a track.

       .venv/Scripts/python.exe .claude/skills/intro-music-visualization/scripts/music_pick.py [--len 45-120]

   Pick by shape, not name: slow opening 8-15 s, a clear valley before a drop, a drop, a loud climax, a final hit.
   Avoid the music of the last videos of the workspace. Then map 2-3 finalists with `music_map.py --show 5` (arc + B5 only), choose,
   and map the winner with `--show 4`:

       .venv/Scripts/python.exe .claude/skills/intro-music-visualization/scripts/music_map.py --name <name> "<file>[@in-out]" ["<file2>@in-out"]

3. **Pool** (additive imports; N = planned shots, about one per 1.85-3.7 s):

       .venv/Scripts/python.exe .claude/skills/intro-music-visualization/scripts/pool.py add --need N --extra 20 --cast jaguar,harpy_eagle,... --video <name>
       .venv/Scripts/python.exe .claude/skills/intro-music-visualization/scripts/pool.py list

   `--cast` ranks the film's species first and sinks other predators (a leopard is not the jaguar); strikes
   (attack / hunt / fight) rank above stalking. Hero shots (drop, B5) missing from the pool: query the library (tags,
   ledger-filtered) for strike / fight / face close-ups of the cast; cuts.txt may use any clip (bin, other bins, library).
4. **Design** `cuts.txt` (format in `scripts/build.py`; `##` section lines = the blueprint: section, time, intent, viewer
   feeling). Times = music_map seconds: bar lines for structure, measured hits for accents, pickup hits (one beat
   before a bar) to break a metronome. Set source in for action sync (`auto` = middle of the usable window).
5. **Review pass 1 + 2 (viewer)**: `build.py <name> --check` (lists black areas, flat-rhythm warnings), then

       .venv/Scripts/python.exe .claude/skills/intro-music-visualization/scripts/storyboard.py <name>

   Read the storyboard images (frames 10/50/90 % of every shot, from the source files) as a viewer: does the first frame
   grab? does every slam / drop show something bigger than before? is each shot readable at its length (subject size,
   darkness)? does the action happen inside the shot, not before it (else set the source in)? set-ups paid off? logos /
   text / wrong species (tags miss them)? flat stretches? Replace weak shots: `storyboard.py cand <name> <frag> ...`
   shows candidates side by side. Fix, re-check, storyboard again (pass 2), fix again.
6. **Build** into the empty timeline "Open" (any non-empty timeline is never edited: a new name `_2` is used):

       .venv/Scripts/python.exe .claude/skills/intro-music-visualization/scripts/build.py <name>

7. **Pass 3 (readback)**: the build stdout must say V1 N/N, 0 off their frame, failed none; check that the only V1 gaps are
   the planned black areas, A7 covers the music, other tracks empty, the user's timeline restored, and count bin spares.
   Rhythm problems found now: propose the exact change (do not delete clips on the built timeline without a "yes").
8. **Report** (Vietnamese, short): timeline, music (+ why this track), length, shots, sections with the move and the
   feeling each aims for, hero beats, black areas, bin clips used / spare, what was fixed in the review passes, open
   points to listen to ("nghe lại ..."), shots worth swapping and their alternatives in the bin.

## Ledger (clips used by recent videos)
`/doc-edit check-timelines` (doc-edit `ledger.py check <video>`) records the clips on timelines "Edit" and "Open" in
the ledger of the video's workspace; `pool.py add` bans "Open" + "Edit" of the last 4 checked videos of that workspace.
Inside this video, Edit + intro share one reuse budget (`build.py` / `storyboard.py` check it): a clip <= 3 parts in all,
never a part already on "Edit", once per intro; `auto` takes the largest free part. Errors name the line: pick another clip.

## Changes and learning
- One shot swap on a built timeline = `ReplaceClip` / `SetProperty` on that item only (CLAUDE.md rule 2), or edit the line
  in `cuts.txt` and build into a new timeline. Never delete timelines or bin clips without an explicit "yes".
- After the user finished an intro, if asked to learn: diff their timeline against `cuts.txt` -> add it as a reference
  to the grammar (moves, not a template) once the user agrees.

## Rules
- Never touch timelines "Edit" / "Master", any non-empty timeline, or the music files. Z: is read-only.
- No false precision: "đo được" for script numbers, never "đã nghe"; joins and cut phases need the user's ear.
- No dissolve / flash / glitch / speed ramp unless asked. No grading (colorist), no SFX design (audio-expert).
