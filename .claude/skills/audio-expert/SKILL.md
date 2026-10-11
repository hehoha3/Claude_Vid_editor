---
name: audio-expert
description: Audio storytelling for the nature documentary on timeline "Edit" - builds a sound map from the story and narrator, picks music / natural sounds / SXF from the user's audio library, places them on A5-A9 with frame-exact timing, readback and rollback. Modes learn, index, analyze, plan, execute, review, learn_from_current. Use for /audio-expert, "sắp xếp audio", "thêm SXF / music / natural sound", "âm thanh thu hút hơn", or when the music bed or SXF of an edit feels thin. Never touches V1, A1-A4 or the narrator on A2; no EQ/ducking/loudness work (that is a later mix phase).
---

# Audio expert (V1: selection + placement)

Spec: `input/audio_expert_plan.md`. Reply in Vietnamese; keep terms (ambience, natural sound, foreground, sound map, Fairlight) in English.
Think first: **story -> what the viewer must feel -> sound map -> pick assets -> place -> verify**. Every sound needs a purpose
(world, orientation, curiosity, state change, anticipation, reveal, action accent, scale, continuity, contrast, release);
silence is a choice (pre-attack, aftermath), not a gap to fill. Read `references/philosophy.md` and `references/sonic_grammar.md` once per session.

## Tracks (timeline "Edit" as it really is; the spec's A5-A8 roles were remapped)

| track | role | V1 may write |
|---|---|---|
| A1 | unused | no |
| A2 | Narrator Voice (speech windows = item spans) | read only |
| A3, A4 | Ambience 1/2 bed from doc-edit | no (protected) |
| A5 | Ambience 3: extra environment layers (birds, water) | yes, in free gaps |
| A6 | Natural sounds: footsteps, leaves, splashes (sync / flexible cues) | yes |
| A7 | Music: one track, sequential; a stop is a decision | yes |
| A8, A9 | SXF 1/2: state-change drops, risers, hits, whooshes | yes |

Existing A6-A9 content is doc-edit output and may be replaced after the backup (`--replace`). Anything the user placed by hand
on A5-A9 is protected: ask first.

## Modes and commands

Data: `.work/audio_expert/` (`audio_index.jsonl`, `learning_plan.md`, `style_profile.json`, `feedback.jsonl`, `<video>/cues.txt`,
`<video>/sound_map.json`, `<video>/runs/<run_id>/...`). Never open `audio_index.jsonl` whole; filter it in Python.

| mode | action |
|---|---|
| learn | refresh `learning_plan.md` / `learning_log.md` (evidence-based, distinguish read / observed / verified / unsure) |
| index | `.venv/Scripts/python.exe .claude/skills/audio-expert/scripts/index.py` (incremental; music gets a waveform arc; nothing is "listened") |
| analyze | read screenplay + timestamp + `.work/voice_<audio>/plan.json` (speech windows) -> write `<video>/sound_map.json` |
| plan | write `<video>/cues.txt` (format in its header), then `scripts/plan.py <video> --run <id>` -> placement_plan.json, placement_report.md, mix_notes.md |
| execute | `scripts/execute.py <video> <run_id> [--replace]` (backup, A5-A9 only, readback, journal, safe to re-run); `--rollback` removes only journaled items |
| review | read stdout + `placement_report.md`; check tracks, bounds, A2/V1 unchanged, no duplicates |
| learn_from_current | diff snapshot before/after the user's edits -> hypotheses in `style_profile.json` with evidence; never edit this SKILL.md for it |

Run `execute` only when the user asked for it; `plan` and `index` write nothing to Resolve. Never work on timeline "Master".

## Rules that matter

- Flexible cues (footsteps, sub drops, offscreen detail) are moved into narrator gaps by plan.py (-6..+3 s); sync cues
  (hit, splash, riser into an event) keep the beat time. Beat times come from the screenplay, not from the picture: say so and
  list them in mix_notes.
- Music: pick by waveform arc and natural end. A track cut before its natural end gets a fade note. Stop music before an
  attack and let body sound carry it; do not put happy music after an escape. Reuse a track only as a named motif
  (M-calm = hypnotic journey, M-danger = suspicions, M-drop = sub drop at act changes).
- Species sounds: the library has none (no monkey, elephant, duiker or eagle calls). Never present a bird or generic hit as a
  species voice; list the missing sounds in the report instead.
- Evidence labels: music = `waveform_analysis` (mood from filename), everything else `filename_only`, confidence <= 0.6.
  Never say "listened". If confidence is below ~0.6 and the cue matters, leave the slot empty and say so.
- Starting level and 0-4 s edge fades reuse doc-edit's TARGET / FADE tables (place.py) so new clips do not bury the voice; they
  are not a mix. EQ, ducking, loudness and crossfades stay with the user until V2.
- The timeline is the source of truth (see Tracks). Keep `project_key` = project name, `timeline_key` = timeline name.
- Report in Vietnamese: counts per track, music coverage, deliberate silences, unresolved cues, missing assets, backup name.
