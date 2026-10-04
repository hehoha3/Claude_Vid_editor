#!/bin/bash
# Hide Logo Skill Runner

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/scripts/hide_logo.py" "$@"
