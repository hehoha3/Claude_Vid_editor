---
name: vo-sync
description: Narration/voiceover sync onto track A4 of timeline "Edit" in DaVinci Resolve from a [mm:ss] timestamp file, using Whisper to find each sentence in the audio. Use whenever the user gives an audio path plus a timestamp file, asks to place/align/sync/re-sync narration or VO, asks why a line is flagged, pushed or late, or wants to adjust padding, overlap behaviour or timestamp clock.
---

# VO sync

## What the tool does
1. Parses `[mm:ss] sentence` lines (also `[hh:mm:ss]`, `[mm:ss.ms]`; wrapped lines join the previous
   sentence; `#` = comment). Times must strictly increase.
2. Whisper (faster-whisper, `small.en`, CPU int8) transcribes the narration with word times. Cached
   by file hash: re-runs on the same audio skip transcription.
3. Script lines are aligned to the transcript globally (tolerates misheard words, numbers written as
   digits or words, extra/missing words).
4. Each sentence boundary is snapped to the real pause in the waveform (10 ms energy envelope), so the
   speech onset is accurate to ~10 ms even though Whisper word times drift 50-200 ms.
5. In Resolve: imports the audio into bin "4. Audio" (if not there), creates A1..A4 if missing,
   backs up timeline "Edit", removes earlier pieces of the SAME file from A4, then places one item per
   sentence. All items reference the single source clip with different in/out points: the same
   structure the Blade tool produces (the scripting API has no blade command; this is the equivalent).
6. Placement: the first voiced frame of each sentence lands exactly on its timestamp. A 0.10 s head
   pad sits before the stamp; a 0.25 s tail pad keeps the natural decay.
7. Verifies every item's start and source-in against the plan and writes `.work/<audio>/report.md`.

## Flags (in the summary and report)
| flag | meaning | what to tell the user |
|---|---|---|
| low_confidence | < 60% of the line's words recognised | listen to that line; often names or numbers |
| text_not_heard | no words matched; position interpolated between neighbours | check by ear; maybe the script line differs from what was recorded |
| no_pause / boundary_uncertain | no clear pause between two lines | listen to the cut; may clip a breath or the first syllable |
| pushed (+x s) | the previous line is longer than the gap to this stamp; this line starts x s late | shorten the previous sentence, move the stamp, or accept |
| speech_cut | with `--on-overlap trim` the previous line's ending was cut | usually unacceptable for narration |
| tail_trimmed / head_trimmed | only silence padding was shortened | harmless, not reported |

Orange items on A4 = check confidence/boundary; pink items = pushed/cut.

## Options
- `--markers`: Sky-coloured timeline marker with the sentence text at every onset (replaced on re-run).
- `--on-overlap push|trim|abort` (config default push). `abort` exits with code 3 and lists collisions.
- `--dry-run`: full computation and report, nothing changed in Resolve.
- `--force-clear`: A4 holds clips from OTHER media -> normally refused; this replaces everything on A4.
  Ask the user before using it.
- `--no-backup`, `--transcript file.json` (skip Whisper).
- config.toml `[align]`: `head_pad`, `tail_pad`, `min_silence`, `timestamp_offset`,
  `timestamp_clock` ("timecode" if stamps were read off Resolve's timecode display; "realtime" if
  from a media player. Only matters at 23.976/29.97: ~1.8 s apart after 30 min).

## Troubleshooting
- Exit 4 "not reachable": Resolve open with a project? Preferences > System > General > External
  scripting using = Local, restart Resolve. Still failing -> in-app mode: `analyze`, then in Resolve
  Workspace > Scripts > Utility > DVR_VO_Sync_apply_last_plan (after running install_inapp.ps1 once).
- Exit 2 with line numbers: fix the timestamp file (non-increasing time, missing `[...]`, ss >= 60).
- "Could not find these lines": audio and script do not match (wrong take, reordered lines,
  different language -> set `[whisper] language` and model `small`).
- Many pushed lines with small values (< 0.3 s): stamps are whole seconds, so tight script spacing
  causes this. Suggest decimals in stamps (`[01:10.4]`) or slightly looser spacing.
- Everything shifted by a constant: the stamps are relative to something else -> `timestamp_offset`.
- Shift that grows over time on a 23.976 timeline -> wrong `timestamp_clock`.
- User edited A4 by hand afterwards: `vo-sync verify` compares the track with the plan.
  Re-running `run` rebuilds A4 from scratch (pieces of the same file are replaced; backup made).

## Verify deviations
`max start deviation` must be 0f. `max source-in deviation` should be 0f. If it is a constant
non-zero value on every item, Resolve interpreted startFrame in a different unit for this audio
file (check the clip's FPS in the media pool vs the timeline). Report it plainly, suggest
`--dry-run` comparison and converting the narration to 48 kHz WAV, and listen to two items.
One frame shorter items are expected and harmless (endFrame inclusive/exclusive difference).

## Speed / cost
- `small.en` on CPU: roughly 0.1-0.3x real time on a modern 8-core CPU; `base.en` is ~2x faster
  with slightly worse word timing (boundaries are refined on the waveform anyway, so it is fine).
- GPU: `device = "cuda"`, `compute_type = "float16"` requires CUDA 12 + cuDNN 9 DLLs on Windows.
- Re-runs after changing timestamps or options never re-transcribe (cache).
