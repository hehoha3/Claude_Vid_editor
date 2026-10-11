---
description: Sync the narration audio to a [mm:ss] timestamp file on track A2 of timeline "Edit"
argument-hint: "<audio path>" "<timestamps path>" [--markers] [--on-overlap push|trim|abort]
allowed-tools: Bash(.venv/Scripts/python.exe -m dvr_cowork:*), Read
---
Sync narration for: $ARGUMENTS

1. Run (keep the user's quoting; add any flags they gave):
   `.venv/Scripts/python.exe -m dvr_cowork vo-sync run <audio> <timestamps>`
   First run may download the Whisper model; transcription of 30 min takes a few minutes on CPU.
2. Exit codes: 0 ok | 2 bad input (show the line numbers it printed) | 3 overlap with --on-overlap abort |
   4 Resolve/project problem (follow its printed hints; offer `doctor`).
3. Report back in Vietnamese, short:
   - how many lines were placed on A2, backup timeline name, verify deviations (should be 0f);
   - every flagged line with its number and stamp, what to listen for, grouped by flag;
   - pushed lines: how late they now start and the option to tighten the script or move the stamp.
   Open the report only to read flagged rows. Do not read plan.json or transcripts.
4. If the verify line shows a non-zero source-in deviation, report the line numbers and ask the user
   to listen before advising.
