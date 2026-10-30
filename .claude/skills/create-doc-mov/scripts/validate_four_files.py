#!/usr/bin/env python3
"""Validate four-file wildlife documentary line/timestamp integrity and timing budget."""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

STAMP = re.compile(r"^\[(\d{2,}):([0-5]\d)\.(\d)\] (.+)$")

def fail(errors: list[str], message: str) -> None:
    errors.append(message)

def parse_section(body: str, name: str, errors: list[str]) -> list[tuple[float, str]]:
    result = []
    for number, line in enumerate(body.splitlines(), 1):
        if not line.strip():
            continue
        match = STAMP.fullmatch(line)
        if not match:
            fail(errors, f"{name}: malformed onset line {number}: {line[:100]!r}")
            continue
        minute, second, tenth, content = match.groups()
        result.append((int(minute) * 60 + int(second) + int(tenth) / 10, content))
    return result

def read_durations(path: Path, n: int, errors: list[str]) -> list[float]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            raw = [raw[str(i)] for i in range(1, n + 1)]
        if not isinstance(raw, list) or len(raw) != n:
            raise ValueError(f"expected {n} ordered durations")
        values = [float(x) for x in raw]
        if any(x <= 0 for x in values):
            raise ValueError("all durations must be positive")
        return values
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        fail(errors, f"invalid durations JSON: {exc}")
        return []

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="One film output directory")
    parser.add_argument("--target-minutes", type=float, required=True)
    parser.add_argument("--wpm", type=float, default=125.0, help="Planning voice rate if no MP3 manifest")
    parser.add_argument("--durations-json", type=Path, help="Ordered MP3 durations in seconds")
    parser.add_argument("--allow-first-onset", type=float, default=0.6)
    args = parser.parse_args()
    errors: list[str] = []
    warnings: list[str] = []
    folder = args.directory
    if args.target_minutes <= 0 or args.wpm <= 0:
        parser.error("target-minutes and wpm must be positive")
    if not folder.is_dir():
        parser.error(f"not a directory: {folder}")
    files = sorted(folder.glob("*.md"))
    transcript = folder / "transcript.md"
    screenplay = [p for p in files if p.name.endswith("_Screenplay_EN.md")]
    timestamp = [p for p in files if p.name.endswith("_Timestamp_EN_VI.md")]
    visual = [p for p in files if p.name.endswith("_Visual_Edit_Plan_EN.md")]
    if len(files) != 4 or not transcript.is_file() or any(len(x) != 1 for x in (screenplay, timestamp, visual)):
        fail(errors, "expected exactly four .md files with screenplay, transcript.md, timestamp EN_VI and Visual_Edit_Plan EN")
    if errors:
        for error in errors:
            print("ERROR:", error, file=sys.stderr)
        return 1

    transcript_text = transcript.read_text(encoding="utf-8")
    voice = [line for line in transcript_text.splitlines() if line.strip()]
    if not voice:
        fail(errors, "transcript has no spoken lines")
    for i, line in enumerate(voice, 1):
        if line.startswith(("#", "[", "-", "*")) or re.match(r"^(Narrator|Voice|Scene|Cảnh)\s*[:#\d]", line, re.I):
            fail(errors, f"transcript line {i} includes a label or non-voice content")
    if len(voice) > 1 and "\n\n" not in transcript_text:
        warnings.append("no blank scene separators were found in transcript.md")

    raw = timestamp[0].read_text(encoding="utf-8")
    if raw.count("## English") != 1 or raw.count("## Vietnamese") != 1:
        fail(errors, "timestamp needs exactly one ## English and one ## Vietnamese")
        en = vi = []
    else:
        before, rest = raw.split("## English", 1)
        en_text, vi_text = rest.split("## Vietnamese", 1)
        en = parse_section(en_text, "English", errors)
        vi = parse_section(vi_text, "Vietnamese", errors)
        if re.search(r"^\[", before, re.M):
            fail(errors, "timestamp entries appear before ## English")
    if len(voice) != len(en) or len(voice) != len(vi):
        fail(errors, f"line count mismatch: transcript={len(voice)}, English={len(en)}, Vietnamese={len(vi)}")
    for i, (original, entry) in enumerate(zip(voice, en), 1):
        if original != entry[1]:
            fail(errors, f"English line {i} differs from transcript")
            if len(errors) > 20:
                break
    for i, (a, b) in enumerate(zip(en, vi), 1):
        if abs(a[0] - b[0]) > 0.01:
            fail(errors, f"Vietnamese onset {i} differs from English")
        if not b[1].strip():
            fail(errors, f"Vietnamese translation {i} is empty")
    if en:
        if abs(en[0][0] - args.allow_first_onset) > 0.01:
            fail(errors, f"first onset {en[0][0]:.1f}s, expected {args.allow_first_onset:.1f}s")
        if any(en[i][0] >= en[i + 1][0] for i in range(len(en) - 1)):
            fail(errors, "English onsets must be strictly increasing")
        if en[-1][0] >= args.target_minutes * 60:
            fail(errors, "final onset is outside target runtime")
    for p, name in ((screenplay[0], "screenplay"), (visual[0], "visual plan")):
        body = p.read_text(encoding="utf-8")
        if "male" not in body.lower() or "female" not in body.lower() or "young" not in body.lower():
            warnings.append(f"{name}: inspect male/female/young bible manually")
        if "metaphor" not in body.lower():
            warnings.append(f"{name}: inspect animal metaphor bible manually")
    words = sum(len(line.split()) for line in voice)
    if args.durations_json and en:
        durations = read_durations(args.durations_json, len(voice), errors)
        if len(durations) == len(en):
            for i in range(len(en) - 1):
                if en[i][0] + durations[i] > en[i + 1][0] + 0.05:
                    fail(errors, f"voice block {i + 1} overlaps next onset by {en[i][0] + durations[i] - en[i + 1][0]:.2f}s")
            if en[-1][0] + durations[-1] > args.target_minutes * 60:
                fail(errors, "last voice block spills past film end")
            voiced = sum(durations)
            source = "measured"
        else:
            voiced = 0.0
            source = "invalid manifest"
    else:
        voiced = words * 60 / args.wpm
        source = "estimated; MP3 not measured"
    coverage = voiced / (args.target_minutes * 60)
    if source != "invalid manifest" and coverage < .55:
        warnings.append(f"voice covers about {coverage:.0%} of film at this rate; explicitly plan {args.target_minutes * 60 - voiced:.0f}s of varied picture/sound holds")
    for warning in warnings:
        print("WARN:", warning, file=sys.stderr)
    for error in errors:
        print("ERROR:", error, file=sys.stderr)
    if errors:
        return 1
    print(f"PASS: {len(voice)} transcript blocks = {len(en)} EN onsets = {len(vi)} VI onsets")
    print(f"Voice words: {words}; voice time: {voiced / 60:.1f} min ({source}); target: {args.target_minutes:.1f} min")
    print(f"First onset: {en[0][0]:.1f}s; last onset: {en[-1][0]:.1f}s")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
