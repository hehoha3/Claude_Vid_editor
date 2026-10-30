# Production layer: source file, cut map, pins, conform

`scripts/build_four_files.py` turns one source file into the four deliverables. Everything that can contradict
(onsets, shot times, rests, key-event times in prose, ending) is computed from the same data.

## Source file (`.work\doc_edit\<video>\four_files.src.md`)

Sections start with `=== NAME`:

| Section | Content |
| --- | --- |
| META | `slug: Africa_Who_Drinks_Last`, `title: …`, optional `target: 60` (minutes) |
| BIBLE | the animal bible table (copied into both plans; must contain male/female/young + metaphor) |
| SP_HEAD / SP_TAIL | screenplay prose before / after the timed beats (question, runtime map, research, alternates, mix gates) |
| VP_HEAD / VP_TAIL | plan prose (thesis, intro rules, track map / sourcing log, final gates, conform, planned-vs-fixed) |
| SCENES | the film, scene by scene |

Placeholders in prose and scene fields keep text in sync: `{{shot:1.4-09}}` (shot in-time), `{{line:12}}` (onset),
`{{lastend}}` (end of the last voice block), `{{budget}}`, `{{status}}`. Write "strike at {{shot:1.4-09}}", never a
typed time.

Scene block:

```
@ 1.4 | 04:30 | 05:30 | The lunge
see: one-paragraph picture summary          animals: bible IDs, sex, young
sound: A3/A4, A5, A6 plan                   fn: story function
clips / gate / audio: sourcing requirement, continuity gate, audio + fallback
need: MUST — … PENDING — …                  (any of MUST, ALT, PENDING before the first "—")
lead: 2   tail: 1.2   vend: 59:32           (seconds before first line, weight after last line, voice end limit)
music: …  grid: 15 2                        (intro only: per-second music text, or beat grid start + bar length)
- 5.0 | LW | a V-wake slides toward the bank | faint water hiss | the viewer knows, the herd does not | !
- * | W | the river surface smoothing over | lapping | |
> The wake stops just short of the bank. || Vệt sóng dừng lại ngay sát bờ. || 3 || @7
```

Shot line: `- duration | size | observable action | A5 natural sound | why the viewer keeps watching | flags`.
`*` = the rest of the span (one per scene). Sizes: EW W MW M C LW (water level) A (aerial) TL (time-lapse).
Flags: `!` key shot (named in the screenplay; must exist), `long` (continuous take, 8–12 s), `cb` (callback: other
frames of a clip already used), `black` (black slug, 0.5 s+). Shot ids are generated: `1.4-09`.

Voice line: `> EN || VI || weight || @shot+offset`. Weight = share of the scene's spare time placed after the line
(default 1; `tail:` for the last). A pin fixes the onset to a shot start (+offset); unpinned lines float between
anchors. Pin only lines that describe a visible event (reveal, strike, miss, storm) — those must survive conform.

## Gates (errors stop the build; `--check` runs them without writing)

- scenes contiguous from 0 to the target; shots of each scene add up to its span (±0.05 s);
- shot 0.8–8 s (`long` ≤ 12 s, `black` ≥ 0.5 s) — longer shots are where a timeline turns static;
- no two shots with the same action text — repeated footage is not allowed as filler (callbacks are new frames);
- voice blocks never overlap and never cross the scene's end / `vend`. A pin means "at or just after its shot": longer
  real audio slides it up to 1.5 s later (warning), more is an error. While planning, keep ≥ 10 % of a pinned
  segment's voice time free before the pin (warning otherwise) — Genmax runs a few percent off the 150 wpm estimate;
- every Vietnamese line present and translated (empty, equal to the EN line or without any Vietnamese letter = error);
- warning: a voice-free rest ≥ 6 s without any shot hook — write what the viewer learns or feels there.

`--report` prints, per scene, each line as `#n@offset+duration` and every rest that still lacks a hook with its shot
ids — the table to place shots, pins and hooks against. A normal build ends by running `validate_four_files.py` on
what it wrote (with `--durations-json` after conform) and fails if the validator fails.

## What the outputs contain

- **Screenplay:** per beat `**NNN · in–out** — id title. picture`, animals, sound, footage status, shot count and key
  shots, every voice-free rest ≥ 3 s as `in–out (dur): shot (dur) action → … Sound … Why watch …`, then
  `*Narrator:* [onset] line` (story.py brief drops these and inserts the real timed sentences).
- **Timestamp:** heading, status note (PLANNED / CONFORMED, number of picture-locked onsets), `## English`,
  `## Vietnamese` — nothing else (validator contract).
- **Visual_Edit_Plan:** VP_HEAD, animal bible, intro cut map **one row per second** (shot, picture when it starts,
  narrator line starting / continuing, music bar), footage status table (MUST / ALT / PENDING), cut map of every shot
  (in, out, duration, size, action, A5 sound, voice block numbers over it, flags), beat table (footage index — skipped
  by `story.py brief`), generated production QA, VP_TAIL.

## Conform

`--mp3 DIR` (ffprobe of 1.mp3…N.mp3) or `--durations-json FILE` replaces the word-count estimate (words ÷ wpm +
0.4 s). Picture (shots) and pins stay; floating onsets move inside their scene; status becomes CONFORMED and
`durations.json` is written next to the source for `validate_four_files.py --durations-json`. Until then every onset,
rest window and intro cut is a plan; the lines, their order, EN = VI count, scene spans and shot order are fixed.

`python build_four_files.py --selftest` checks pins, placeholders, the per-second intro map, footage table, the
validator run, the overlap gate and the untranslated-VI gate on a 30-second fixture. Run it after changing the script.
