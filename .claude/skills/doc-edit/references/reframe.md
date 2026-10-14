# Reframe: `/doc-edit reframe [<video>]` (after step 3, or "shot bị viền đen")

Zoom / Position X-Y on V1 of "Edit" only (Transform; nothing moved, cut or replaced):

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/reframe.py <video>           # dry-run list
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/reframe.py <video> --apply   # backup Edit_bak_reframe_*, set

- `fill`: black bars (file wider than 16:9 or baked-in bars, cropdetect cache `.work/library/active_area.json`)
  -> smallest zoom that fills, crop slid toward the animal.
- punch-in, <= 15% of shots, centred on the YOLO box, only if the animal stays in frame on every sample: `strike`
  (strike/attack/catch shot, 1.2x), `tiny` (character < 18% of frame), `size` (same size as previous -> next size).
  Max zoom 1.35 on 1080p, 1.7 on UHD.
- Shots with a non-default Transform are skipped: re-running is safe.

Dry-run, show counts, then `--apply`. Reply: backup, fill / punch-in counts by reason, failures, timecodes to watch.
