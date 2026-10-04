"""Parse the narration timestamp file:  [mm:ss] sentence text"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .timecode import parse_clock

_TS = re.compile(
    r"^\s*\[\s*(?P<t>\d{1,3}:\d{1,2}(?::\d{1,2})?(?:[.,]\d{1,3})?)\s*\]\s*(?P<text>.*)$"
)
_QUOTES = "\"'\u201c\u201d\u2018\u2019"


class TimestampError(ValueError):
    pass


@dataclass
class Cue:
    index: int  # 1-based
    t: float  # seconds on the timeline (relative to timeline start)
    text: str
    lineno: int


def _clean(s: str) -> str:
    return s.strip().strip(_QUOTES).strip()


def parse_timestamp_file(path: str | Path) -> list[Cue]:
    raw = Path(path).read_text(encoding="utf-8-sig")
    cues: list[Cue] = []
    errors: list[str] = []
    for n, line in enumerate(raw.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = _TS.match(s)
        if m:
            try:
                t = parse_clock(m["t"])
            except ValueError as e:
                errors.append(f"line {n}: {e}")
                continue
            cues.append(Cue(len(cues) + 1, t, _clean(m["text"]), n))
        elif cues:  # wrapped line -> continuation of the previous sentence
            cues[-1].text = (cues[-1].text + " " + _clean(s)).strip()
        else:
            errors.append(f"line {n}: missing [mm:ss] prefix: {s[:60]!r}")
    for a, b in zip(cues, cues[1:]):
        if b.t <= a.t:
            errors.append(f"line {b.lineno}: time {b.t:g}s is not after line {a.lineno} ({a.t:g}s)")
    for c in cues:
        if not c.text:
            errors.append(f"line {c.lineno}: empty text")
    if not cues and not errors:
        errors.append("no [mm:ss] lines found")
    if errors:
        raise TimestampError("\n".join(errors))
    return cues
