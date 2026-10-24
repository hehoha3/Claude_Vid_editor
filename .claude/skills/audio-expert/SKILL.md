---
name: audio-expert
description: Sound design on timeline "Edit" - sound map from story + narrator, picks music / natural sound / SXF from the library, places them frame-exact on A5-A9 with backup and rollback. Use for /audio-expert, "sắp xếp audio", "thêm SXF / music / natural sound", "âm thanh thu hút hơn", or a thin music bed. Never touches V1 or A1-A4; no EQ/ducking/loudness.
---

# Audio expert (V1: selection + placement)

Spec: `input/audio_expert_plan.md`. Reply in Vietnamese; terms (ambience, natural sound, foreground, sound map,
Fairlight) stay English. Read `references/philosophy.md` and `references/sonic_grammar.md` once per session.
Order: **story -> what the viewer must feel -> sound map -> pick assets -> place -> verify**. Every sound has a purpose
(world, orientation, curiosity, state change, anticipation, reveal, action accent, scale, continuity, contrast,
release); silence is a choice (pre-attack, aftermath), not a gap to fill.

## Tracks (timeline "Edit" as it is; the spec's A5-A8 roles were remapped)
| track | role | may write |
|---|---|---|
| A1 | own audio of the AI clips (doc-edit, -12 dB) | no |
| A2 | Narrator Voice (speech windows = item spans) | read only |
| A3, A4 | Ambience 1/2 bed from doc-edit | no (protected) |
| A5 | Ambience 3: extra environment layers (birds, water) | yes, in free gaps |
| A6 | Natural sounds: footsteps, leaves, splashes (sync / flexible cues) | yes |
| A7 | Music: one track, sequential; a stop is a decision | yes |
| A8, A9 | SXF 1/2: state-change drops, risers, hits, whooshes | yes |

Doc-edit output on A6-A9 may be replaced after the backup (`--replace`); anything the user placed by hand on A5-A9 is
protected: ask first. Never timeline "Master".

## Modes
Data in `.work/audio_expert/`: `audio_index.jsonl` (never open whole; filter in Python), `learning_plan.md`,
`style_profile.json`, `feedback.jsonl`, `<video>/cues.txt`, `<video>/sound_map.json`, `<video>/runs/<run_id>/...`.

| mode | action |
|---|---|
| learn | refresh `learning_plan.md` / `learning_log.md` (evidence-based: read / observed / verified / unsure) |
| index | `.venv/Scripts/python.exe .claude/skills/audio-expert/scripts/index.py` (incremental; music gets a waveform arc; nothing is "listened") |
| analyze | screenplay + timestamp + `.work/voice_<audio>/plan.json` (speech windows) -> `<video>/sound_map.json` |
| plan | write `<video>/cues.txt` (format in its header), then `scripts/plan.py <video> --run <id>` -> placement_plan.json, placement_report.md, mix_notes.md |
| execute | `scripts/execute.py <video> <run_id> [--replace]` (backup, A5-A9 only, readback, journal, re-run safe); `--rollback` removes only journaled items |
| review | stdout + `placement_report.md`: tracks, bounds, A2/V1 unchanged, no duplicates |
| learn_from_current | diff snapshot before/after the user's edits -> hypotheses with evidence in `style_profile.json`; never edit this SKILL.md for it |

`execute` only when the user asked; `plan` and `index` write nothing to Resolve.

## Rules
- Flexible cues (footsteps, sub drops, offscreen detail) are moved into narrator gaps by plan.py (-6..+3 s); sync cues
  (hit, splash, riser into an event) keep the beat time. Beat times come from the screenplay, not the picture: say so,
  list them in mix_notes.
- Music: pick by waveform arc and natural end; cut before its end -> fade note. Stop music before an attack, let body
  sound carry it; no happy music after an escape. Reuse a track only as a named motif (M-calm = hypnotic journey,
  M-danger = suspicions, M-drop = sub drop at act changes).
- Species sounds: the library has none (no monkey, elephant, duiker or eagle calls). Never pass a bird or generic hit
  off as a species voice; list missing sounds in the report.
- Evidence labels: music = `waveform_analysis` (mood from filename), else `filename_only`, confidence <= 0.6. Never
  say "listened". Confidence below ~0.6 on a cue that matters -> leave the slot empty, say so.
- Starting level and 0-4 s edge fades reuse doc-edit's TARGET / FADE tables (place.py) so new clips do not bury the
  voice; not a mix. EQ, ducking, loudness, crossfades stay with the user until V2.
- The timeline is the source of truth. `project_key` = project name, `timeline_key` = timeline name.
- Report (Vietnamese): counts per track, music coverage, deliberate silences, unresolved cues, missing assets, backup name.
