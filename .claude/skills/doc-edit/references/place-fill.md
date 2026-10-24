# Place and fill (`/doc-edit place`, `/doc-edit fill`, `ingest --fill`)

Fill notes: `--late-sub --late-sub-t=490` = THIẾU slots from 8:10 on get the closest substitute (same species >
companion > forest scenery; 60 s apart, max 4 uses; FALLBACK "late substitute"); `--sub-all` = every THIẾU slot.
Before placing, name the slots that fell through to scenery. `pin=none` lines stay THIẾU: drop them from the spec once
footage exists. `place.py --fill` ends with `V1 still empty: N gaps: mm:ss ...`; the reply lists those gaps and the THIẾU slots left
(`missing.py <video> --range=...`), no separate gap script.

`state.py diff <video>` (what the user changed in Resolve / `_check` since the last snapshot) only when the user asks or
a step must not undo hand edits it cannot see; `place --fill` already keeps every item on the timeline.

## Place

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/place.py <video>

Clips in `D:\AI_video\_check` are planned too (user 2026-10-21), by their tags: never above WEAK (yellow marker,
note `_check: <issues>`), never with logo / watermark / text (delogo first). Every place / fill also imports up to 4
alternative clips per slot (THIẾU slots too; plan.py `ALTS`) into bins 1-3, never placed: the user swaps by hand
(`alternatives in bins 1-3: N` line).
Backs up "Edit" (`Edit_bak_place_<stamp>`), imports used files into video bins by what the clip shows (user
2026-10-22, real and AI alike): tag action attack / hunt / fight -> `2. Attack_roll`, run -> `3. Run_roll` (attack wins),
everything else -> `1. Other_roll` (untagged: words in folder / file name, e.g. `Chạy`); `place.py --rebin` re-sorts the
clips already in those three bins (media pool only, timeline untouched); 4. Audio/Ambience (A3-A6), /Music (A7), /SFX (A8-A9) (a file already anywhere in 4. Audio is reused), places
V1 frame-exact (WEAK yellow) + A1 + A3-A9 (crossfades, fades, starting Clip Volume), markers: red
THIẾU (note = shot needed), yellow WEAK, blue GFX. A2 never touched. V1/A3-A9 not empty -> it stops: say what is
there and ask before `--replace` (clears those tracks after the backup; destructive, CLAUDE.md rule 2).
`--video-only` = V1 + A1 + markers. `--a1-only` = A1 of AI clips only (A1 must be empty, no backup).
`--fill` = keeps every item on the timeline, places only plan clips whose V1 range is still empty (+ their A1),
removes only those slots' markers; audio untouched; backup first. "V1 gaps of 1-3 frames" must be 0.

Reply: backup, clips placed, max start deviation, gaps, audio pieces, failures, markers.

