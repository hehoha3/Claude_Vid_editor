#!/bin/bash
# Voice Distribution Skill Runner
# Invoke from Claude Code with: /voice-distribution <timestamp_path> [--audio <audio_path>]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/scripts/voice_sync.py" "$@"
