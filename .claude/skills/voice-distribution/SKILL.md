---
name: voice-distribution
description: Automatically distribute narration across timeline using timestamps. Use this when you have a timestamped narration script file and need to sync audio to timeline. Provide the path to timestamped.txt file. The skill will validate audio existence, run vo-sync to blade-cut and distribute audio segments on track A4 of timeline "Edit", then report results with any flagged segments needing review.
compatibility: DaVinci Resolve 21.1+, dvr_cowork CLI, Whisper model
---

# Voice Distribution Skill

Automatically synchronizes narration audio with a timestamped script and distributes segments across timeline track A4.

## Workflow

When you invoke this skill with a timestamp file path, it:

1. **Validates setup** — checks timeline "Edit" exists, track A4 is ready, and finds the audio file
2. **Analyzes timestamps** — reads the timestamped.txt file for format and timestamp consistency
3. **Finds audio** — searches for audio file (same folder as timestamps or custom path if provided)
4. **Runs vo-sync** — executes `dvr_cowork vo-sync run` to:
   - Transcribe audio and match segments to timestamps
   - Blade-cut audio into individual segments
   - Distribute segments on track A4 with precise timecode alignment
5. **Reports results** — summarizes clips placed, any segments with issues (boundary_uncertain, pushed offsets), and recommendations for review

## Input Format

**Timestamped file format** (required):
```
[HH:MM] Narration text for this segment.

[HH:MM] Next segment text.
```

Each segment must have:
- A timestamp in `[HH:MM]` format (minutes:seconds)
- Narration text on the same line or following lines
- Blank line between segments

**Example:**
```
[00:06] Dawn breaks over the Amazon. Mist lifts slowly from the canopy.

[00:14] And somewhere in the treetops, a troop of spider monkeys begins to move.

[00:25] For months of the year, this forest is a world of soil and roots.
```

## Using This Skill

### Basic usage (audio in same folder as timestamps)

```
/voice-distribution D:\path\to\audios\timestamped.txt
```

The skill will look for audio files (*.mp3, *.wav, *.m4a) in the same directory.

### If audio is in a different location

```
/voice-distribution "D:\path\to\timestamped.txt" --audio "D:\different\location\narration.mp3"
```

## What Happens

1. **Validation phase:**
   - Checks for timeline "Edit" in current project
   - Verifies track A4 exists and is accessible
   - Scans for audio files near timestamps file
   - Reports what it found

2. **Processing phase:**
   - Backs up current timeline to `Edit_bak_YYYYMMDD_HHMMSS`
   - Removes previous audio from A4
   - Transcribes audio (uses Whisper small.en model)
   - Matches transcript to timestamps
   - Blade-cuts audio at each timestamp
   - Distributes 253 segments (or however many timestamps exist) on track A4

3. **Report phase:**
   - Total clips placed (e.g., 253/253)
   - List of segments with flags:
     - **boundary_uncertain**: Pause boundary unclear — listen to verify the blade cut
     - **pushed**: Segment started later than timestamp (0.04s–5.04s) due to audio overlap — may need manual adjustment
     - **tail_trimmed / head_trimmed**: Silence trimmed to fit — usually harmless
   - File path to detailed report for further review

## Possible Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| "Audio file not found" | File not in same folder or provided path is wrong | Check file exists, provide correct `--audio` path |
| "Timestamps file invalid" | Format issues (timestamps not in [HH:MM] format) | Fix timestamps, ensure blank lines between segments |
| "Track A4 not found" | Track doesn't exist or is locked | Create audio track 4, ensure it's unlocked |
| "Boundary uncertain" flagged | Pause between segments is hard to detect | Listen to flagged segment, manually adjust if needed |
| "Pushed" segments | Audio overlap forces segment to start later | Minor — acceptable if onset is close to timestamp |

## Output

After completion, you'll see:

- ✅ Total segments placed (e.g., 253/253)
- 📍 Timeline backed up as `Edit_bak_YYYYMMDD_HHMMSS`
- 🚩 Flagged segments list (if any) with specific issues
- 📄 Detailed report saved to `.work/voice_<audioname>/report.md`

**Next steps:**
- Open timeline "Edit" and play segments to verify audio sync
- For flagged segments, listen and manually adjust if needed (move clip start/end by a few frames)
- Proceed with color grading, effects, or delivery

## Technical Details

- **Timeline**: Always "Edit", track A4
- **Frame rate**: 24 fps (detected from project)
- **Model**: Whisper small.en (auto-downloads on first run)
- **Backup**: Before processing, creates timeline backup
- **CLI tool**: Runs `dvr_cowork vo-sync run` (requires `.venv` setup)

## When to Use This Skill

✅ You have a narration audio file and a timestamped script
✅ You need precise segment distribution on timeline
✅ You want automatic blade-cutting at timestamps
✅ You need a report of any segments requiring manual review

❌ Don't use for music/SFX distribution (use manual placement or different tool)
❌ Don't use if you need to adjust individual segment timing (use after for fine-tuning)
