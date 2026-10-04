#!/usr/bin/env python3
"""
Voice Distribution Skill
Validates and distributes narration across timeline using timestamps.
"""
import os
import sys
import re
import subprocess
import json
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


class VoiceSyncValidator:
    def __init__(self, timestamp_path: str, audio_path: str = None):
        self.timestamp_path = Path(timestamp_path)
        self.audio_path = Path(audio_path) if audio_path else None
        self.errors = []
        self.warnings = []
        self.info = []

    def validate_timestamps(self) -> bool:
        """Validate timestamp file format and structure."""
        if not self.timestamp_path.exists():
            self.errors.append(f"Timestamps file not found: {self.timestamp_path}")
            return False

        try:
            with open(self.timestamp_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            self.errors.append(f"Failed to read timestamps file: {e}")
            return False

        # Check format
        timestamps = re.findall(r'\[(\d{2}):(\d{2})\]', content)
        if not timestamps:
            self.errors.append("No timestamps found in format [MM:SS]")
            return False

        self.info.append(f"Found {len(timestamps)} timestamps")

        # Check for duplicates/ordering
        times_seconds = []
        for mm, ss in timestamps:
            sec = int(mm) * 60 + int(ss)
            times_seconds.append(sec)

        for i in range(len(times_seconds) - 1):
            if times_seconds[i] >= times_seconds[i + 1]:
                line_num = i + 1
                self.errors.append(
                    f"Timestamp ordering issue at line {line_num}: "
                    f"{times_seconds[i]}s >= {times_seconds[i+1]}s"
                )
                return False

        self.info.append(f"Duration: {times_seconds[0]}s to {times_seconds[-1]}s")
        return True

    def find_audio_file(self) -> bool:
        """Find audio file in same folder or use provided path."""
        if self.audio_path and self.audio_path.exists():
            self.info.append(f"Audio found at provided path: {self.audio_path}")
            return True

        # Search same folder as timestamps
        audio_extensions = ['.mp3', '.wav', '.m4a', '.aiff']
        folder = self.timestamp_path.parent

        candidates = []
        for ext in audio_extensions:
            candidates.extend(folder.glob(f'*{ext}'))

        if not candidates:
            if self.audio_path:
                self.errors.append(
                    f"Audio file not found at provided path: {self.audio_path}"
                )
            else:
                self.errors.append(
                    f"No audio files found in {folder}\n"
                    f"  Searched for: {', '.join(audio_extensions)}\n"
                    f"  Provide audio path with --audio flag"
                )
            return False

        if len(candidates) > 1:
            self.warnings.append(
                f"Multiple audio files found in {folder}. "
                f"Using first: {candidates[0].name}"
            )

        self.audio_path = candidates[0]
        self.info.append(f"Audio file: {self.audio_path.name} ({self.audio_path.stat().st_size / 1e6:.1f} MB)")
        return True

    def check_resolve_setup(self) -> bool:
        """Verify Resolve project has Edit timeline and A4 track."""
        # This will be checked by vo-sync CLI
        self.info.append("Resolve setup will be verified by vo-sync")
        return True

    def validate_all(self) -> bool:
        """Run all validations."""
        print("=" * 70)
        print("VOICE DISTRIBUTION - VALIDATION PHASE")
        print("=" * 70)

        checks = [
            ("Timestamps file", self.validate_timestamps),
            ("Audio file", self.find_audio_file),
            ("Resolve setup", self.check_resolve_setup),
        ]

        all_passed = True
        for name, check in checks:
            print(f"\n[OK] Checking {name}...", end=" ")
            if check():
                print("OK")
            else:
                print("FAILED")
                all_passed = False

        print("\n" + "=" * 70)
        print("VALIDATION RESULTS")
        print("=" * 70)

        if self.info:
            print("\n[INFO] Info:")
            for msg in self.info:
                print(f"  - {msg}")

        if self.warnings:
            print("\n[WARN] Warnings:")
            for msg in self.warnings:
                print(f"  - {msg}")

        if self.errors:
            print("\n[ERR] Errors:")
            for msg in self.errors:
                print(f"  - {msg}")

        return all_passed


def run_vo_sync(timestamp_path: str, audio_path: str) -> bool:
    """Execute vo-sync run command."""
    print("\n" + "=" * 70)
    print("VOICE DISTRIBUTION - SYNC PHASE")
    print("=" * 70)

    cmd = [
        sys.executable, "-m", "dvr_cowork", "vo-sync", "run",
        str(audio_path),
        str(timestamp_path)
    ]

    print(f"\nRunning: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(cmd, capture_output=False, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running vo-sync: {e}")
        return False


def read_report(audio_name: str) -> dict:
    """Read vo-sync report from .work directory."""
    work_dir = Path.cwd() / ".work" / f"voice_{audio_name}"
    report_path = work_dir / "report.md"

    if not report_path.exists():
        return None

    # Parse report for summary
    with open(report_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Extract key info
    placed = None
    flagged_count = 0

    for line in lines:
        if "Placed" in line:
            match = re.search(r'(\d+)/(\d+)', line)
            if match:
                placed = (int(match.group(1)), int(match.group(2)))
        if "boundary_uncertain" in line or "pushed" in line:
            flagged_count += 1

    return {
        "placed": placed,
        "report_path": str(report_path),
        "flagged_count": flagged_count
    }


def main():
    # Parse arguments
    if len(sys.argv) < 2:
        print("Usage: voice_sync.py <timestamps_path> [--audio <audio_path>]")
        sys.exit(1)

    timestamp_path = sys.argv[1]
    audio_path = None

    if "--audio" in sys.argv:
        idx = sys.argv.index("--audio")
        if idx + 1 < len(sys.argv):
            audio_path = sys.argv[idx + 1]

    # Validate
    validator = VoiceSyncValidator(timestamp_path, audio_path)
    if not validator.validate_all():
        print("\n❌ Validation failed. Please fix the issues above.")
        sys.exit(1)

    # Run vo-sync
    if not run_vo_sync(str(validator.timestamp_path), str(validator.audio_path)):
        print("\n[ERR] vo-sync failed. Check the output above.")
        sys.exit(1)

    # Read and display report
    audio_name = validator.audio_path.stem
    report = read_report(audio_name)

    print("\n" + "=" * 70)
    print("VOICE DISTRIBUTION - RESULTS")
    print("=" * 70)

    if report and report["placed"]:
        placed, total = report["placed"]
        print(f"\n[SUCCESS] Successfully placed {placed}/{total} audio segments on track A4")

    if report and report["flagged_count"] > 0:
        print(f"\n[WARN] {report['flagged_count']} segments flagged for review:")
        print(f"   - Review detailed report: {report['report_path']}")
        print(f"   - Listen to flagged segments in timeline 'Edit' track A4")
        print(f"   - Manually adjust timing if needed (move clip by few frames)")
    else:
        print("\n[SUCCESS] No flagged segments - audio distribution looks good!")

    print("\n" + "=" * 70)
    print("Next steps:")
    print("  1. Open timeline 'Edit' in DaVinci Resolve")
    print("  2. Play track A4 to verify audio sync")
    print("  3. For any flagged segments, listen and adjust manually if needed")
    print("  4. Proceed with color grading or delivery")
    print("=" * 70 + "\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
