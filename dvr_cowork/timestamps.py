"""Parse the narration timestamp file:  [mm:ss] sentence text"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .timecode import parse_clock

_TS = re.compile(
    r"^\s*\[\s*(?P<t>\d{1,3}:\d{1,2}(?::\d{1,2})?(?:[.,]\d{1,3})?)\s*\]\s*(?P<text>.*)$"
)
# `###### 001 · [00:00.6] text`: a numbered heading in front of the cue (Vietnamese part of africa_1)
_NUMBERED = re.compile(r"^#{3,}\s*\d+\s*[·.:-]?\s*(?=\[)")
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


def _sections(lines: list[str]) -> list[str]:
    return [s.strip()[3:].strip().lower() for s in lines if s.strip().startswith("## ")]


def parse_timestamp_file(path: str | Path, section: str = "english") -> list[Cue]:
    """`## English` / `## Vietnamese` headings split a bilingual file: only `section` is read
    (no such heading -> the cues before the first heading if there are any, else the first heading).
    A file without `## ` headings is read whole."""
    lines = [_NUMBERED.sub("", l.strip()) for l in Path(path).read_text(encoding="utf-8-sig").splitlines()]
    names = _sections(lines)
    head = next((i for i, l in enumerate(lines) if l.startswith("## ")), len(lines))
    pre = any(_TS.match(l) for l in lines[:head])  # e.g. English cues with no `## English` heading
    want = next((h for h in names if h.startswith(section.lower())), None if pre or not names else names[0])
    cues: list[Cue] = []
    errors: list[str] = []
    cur = None
    for n, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("## "):
            cur = s[3:].strip().lower()
            continue
        if not s or s.startswith("#") or cur != want:
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


VO_START = 3.6  # user 2026-10-25: the narrator speaks from 0:03.6; the opening shot holds the screen alone until then


def to_vo_start(cues: list[Cue], start: float = VO_START) -> float:
    """Shift every cue so the first lands on `start` when the file starts earlier (0:00.6 -> +3.0 s). -> shift."""
    d = round(max(0.0, start - cues[0].t), 3) if cues else 0.0
    for c in cues:
        c.t = round(c.t + d, 3)
    return d
