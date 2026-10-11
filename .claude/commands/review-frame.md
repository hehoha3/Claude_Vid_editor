---
description: Critique graded frames at given timeline positions and propose concrete Resolve fixes
argument-hint: <mm:ss> [mm:ss ...]
allowed-tools: Bash(.venv/Scripts/python.exe -m dvr_cowork:*), Read
---
Review frames at: $ARGUMENTS

1. `.venv/Scripts/python.exe -m dvr_cowork frames --at $ARGUMENTS --stats`
2. Load the `colorist` skill (and `edit-craft` for continuity or pacing notes).
3. Read the numbers first, then view the PNGs it returned.
4. Answer in Vietnamese per frame: what works, the 1-3 most important problems (exposure, balance,
   color, separation, AI artifacts, continuity), the Resolve fix with starting values, and one
   alternative look with its trade-off. End with what to check across neighbouring shots.
