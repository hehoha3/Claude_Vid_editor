"""Clock / timecode helpers. stdlib-only."""
from __future__ import annotations


def parse_clock(s: str) -> float:
    """'75', '12.5', 'mm:ss', 'mm:ss.ms', 'hh:mm:ss' -> seconds."""
    s = s.strip().replace(",", ".")
    parts = s.split(":")
    if len(parts) == 1:
        return float(parts[0])
    if len(parts) > 3:
        raise ValueError(f"bad time {s!r}")
    sec = float(parts[-1])
    mins = int(parts[-2])
    hrs = int(parts[-3]) if len(parts) == 3 else 0
    if sec >= 60:
        raise ValueError(f"seconds >= 60 in {s!r}")
    if len(parts) == 3 and mins >= 60:
        raise ValueError(f"minutes >= 60 in {s!r}")
    return hrs * 3600 + mins * 60 + sec


def nominal(fps: float) -> int:
    return int(round(fps))


def frames_to_tc(frames: int, fps: float) -> str:
    """Non-drop timecode at the nominal rate (how Resolve displays 23.976 / 24 / 25 / 30)."""
    n = nominal(fps)
    sign = "-" if frames < 0 else ""
    frames = abs(int(frames))
    ff = frames % n
    s = frames // n
    return f"{sign}{s // 3600:02d}:{(s // 60) % 60:02d}:{s % 60:02d}:{ff:02d}"


def tc_to_frames(tc: str, fps: float) -> int:
    hh, mm, ss, ff = (int(x) for x in tc.replace(";", ":").split(":"))
    return ((hh * 60 + mm) * 60 + ss) * nominal(fps) + ff


def fmt_seconds(sec: float) -> str:
    m, s = divmod(max(sec, 0.0), 60)
    return f"{int(m):02d}:{s:05.2f}"
