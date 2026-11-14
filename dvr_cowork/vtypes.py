"""Video types, regions and story math: the one registry every script imports (user 2026-11-12).

Folder name = type + region + day + n: `f_` footage (no AI), `fa_` footage+AI (AI <= 40 % of the footage time, every
region), `a_` full-AI; e.g. `fa_africa_121126_1`. Names without a prefix (before 2026-11-12: `africa_121126_2`,
`himalaya_101126_3`) are legacy: profile.detect reads their files. Runtime 8-180 min for every type; the story count
follows the runtime (`stories`). `python -m dvr_cowork profile stories --minutes 60` prints the options.
"""
from __future__ import annotations

import re
from pathlib import Path

TYPES = {"f": "footage", "fa": "footage_ai", "a": "full_ai"}  # folder prefix -> type id (= profile id)
PREFIX = {v: k for k, v in TYPES.items()}
LABEL = {"footage": "footage", "footage_ai": "footage+AI", "full_ai": "full-AI"}
TYPE_ALIASES = {"footage+ai": "footage_ai", "footage-ai": "footage_ai", "fa": "footage_ai", "f": "footage",
                "real": "footage", "full-ai": "full_ai", "fullai": "full_ai", "ai": "full_ai", "a": "full_ai"}
REGIONS = ("amazon", "africa", "frozen")  # amazon = jungle (Amazon, Congo); africa = savanna, desert;
# frozen = snow, ice, high mountains, polar (user 2026-11-12: was himalaya)
REGION_ALIASES = {"himalaya": "frozen", "congo": "amazon", "jungle": "amazon", "savanna": "africa",
                  "savannah": "africa", "desert": "africa", "snow": "frozen", "ice": "frozen", "polar": "frozen"}
AI_MAX = {"footage": 0.0, "footage_ai": 0.40, "full_ai": 1.0}  # share of the footage time (plan.py)
MIN_MINUTES, MAX_MINUTES = 8, 180
TOLERANCE_MIN = 3  # user 2026-11-12: "20p" = 17-23 min, "1h" = 57-63 min: the story decides inside it
# Story math (user 2026-11-12): one story only up to 15 min; 2+ stories 5-12 min each, aim 8.5 (6-10 typical);
# Story 1 the longest (x1.3, <= 15). Intro 30 s under 20 min, 1:30 from 20 min; the last line ends by target - 0:28.
LONG_FROM_MIN, INTRO_SHORT_S, INTRO_LONG_S, END_S = 20, 30, 90, 28
ONE_STORY_MAX, STORY_MIN, STORY_MAX, STORY_AIM, STORY1_GAIN, STORY1_MAX = 15.0, 5.0, 12.0, 8.5, 1.3, 15.0
NAME = re.compile(r"^(?:(fa|f|a)_)?([a-z]+)_(\d{6})(?:_(\d+))?$", re.I)


def type_id(x) -> str | None:
    k = str(x or "").strip().lower()
    k = TYPE_ALIASES.get(k, k)
    return k if k in PREFIX else None


def region_id(x) -> str | None:
    k = str(x or "").strip().lower()
    k = REGION_ALIASES.get(k, k)
    return k if k in REGIONS else None


def parse(name) -> dict | None:
    """'fa_africa_121126_1' / a path / a key '<name>__Chann_N' -> {type, region, day, n, legacy}; legacy names (no
    prefix) -> type None. Not a film name (vid_*, ocean_*) -> None."""
    base = Path(str(name)).name.split("__")[0]
    m = NAME.fullmatch(base)
    if not m or not (region := region_id(m[2])):
        return None
    return {"name": base, "type": TYPES[m[1].lower()] if m[1] else None, "region": region, "day": m[3],
            "n": int(m[4] or 1), "legacy": not m[1]}


def folder(vtype, region, day, n) -> str:
    t, r = type_id(vtype), region_id(region)
    if not t or not r:
        raise ValueError(f"type {vtype!r} must be one of {list(PREFIX)}, region {region!r} one of {REGIONS}")
    return f"{PREFIX[t]}_{r}_{day}_{n}"


def ai_max(video) -> float:
    """AI cap of a video from its folder name; legacy names are footage+AI films."""
    p = parse(video)
    return AI_MAX[(p and p["type"]) or "footage_ai"]


def check_dir(region):
    """Where the user saves generated clips of a region (jobs check, missing prompts)."""
    from .config import load_config
    ai = Path(load_config()["paths"]["ai_video"])
    return {"amazon": ai / "_check", "africa": ai / "_africa" / "_check"}.get(region_id(region), ai / "_frozen" / "_check")


SHOT_EXTS = (".mp4", ".mov", ".mkv", ".m4v", ".webm")


def shot_media(video) -> list[Path]:
    """Generated clips in <video>\\shots (one-time clips of that film, named by shot_id), sorted; no folder -> []."""
    d = Path(video) / "shots"
    return sorted(f for f in d.iterdir() if f.is_file() and f.suffix.lower() in SHOT_EXTS) if d.is_dir() else []


def intro_s(minutes) -> int:
    return INTRO_LONG_S if float(minutes) >= LONG_FROM_MIN else INTRO_SHORT_S


def split_minutes(body, n) -> list[float]:
    """Story lengths (min, 0.5 steps) for n stories in `body` minutes: Story 1 the longest, the rest even."""
    if n == 1:
        return [round(body * 2) / 2]
    avg = body / n  # the others keep >= 85 % of the average (15 min: 8 + 6, not 9 + 5)
    s1 = round(max(avg, min(avg * STORY1_GAIN, STORY1_MAX, body - max(STORY_MIN, avg * .85) * (n - 1))) * 2) / 2
    rest = (body - s1) / (n - 1)
    return [s1] + [round(rest * 2) / 2] * (n - 1)


def runtime_range(asked) -> tuple[float, float]:
    """The minutes a film may really run when the user asks `asked` (+-3 min, inside 8-180)."""
    a = float(asked)
    return max(MIN_MINUTES, a - TOLERANCE_MIN), min(MAX_MINUTES, a + TOLERANCE_MIN)


def stories(minutes, n=None) -> dict:
    """Story options for a runtime: up to 3 counts closest to STORY_AIM, the best marked; n = only that count."""
    m = float(minutes)
    if not MIN_MINUTES <= m <= MAX_MINUTES:
        raise ValueError(f"runtime {m:g} min outside {MIN_MINUTES}-{MAX_MINUTES}")
    body = m - (intro_s(m) + END_S) / 60
    ok = ([1] if body <= ONE_STORY_MAX else []) + [k for k in range(2, int(body // STORY_MIN) + 1)
                                                   if STORY_MIN <= body / k <= STORY_MAX]
    ok = ok or [max(1, round(body / STORY_AIM))]
    best = sorted(ok, key=lambda k: (abs(body / k - STORY_AIM), k))
    pick = [n] if n else sorted(best[:3])
    return {"minutes": m, "range": runtime_range(m), "intro_s": intro_s(m), "end_s": END_S, "body_min": round(body, 1),
            "recommended": best[0],
            "options": [{"stories": k, "story_min": split_minutes(body, k)} for k in pick]}


def selftest():
    assert parse("fa_africa_121126_1")["type"] == "footage_ai" and parse(r"D:\Chann_3_x\a_frozen_121126_2")["n"] == 2
    assert parse("f_amazon_121126_1__Chann_2")["type"] == "footage"
    h = parse("himalaya_101126_3")
    assert h["region"] == "frozen" and h["legacy"] and h["type"] is None
    assert parse("congo_1") is None and parse("vid_051126_1") is None and parse("amazon_311026")["n"] == 1
    assert folder("footage+AI", "himalaya", "121126", 1) == "fa_frozen_121126_1" and type_id("8p") is None
    assert ai_max("fa_amazon_121126_1") == 0.40 and ai_max("f_africa_121126_1") == 0 and ai_max("africa_121126_2") == 0.40
    got = {m: [o["stories"] for o in stories(m)["options"]] for m in (8, 10, 12, 15, 20, 30, 60, 90)}
    assert got == {8: [1], 10: [1], 12: [1, 2], 15: [1, 2], 20: [2, 3], 30: [3, 4, 5], 60: [6, 7, 8], 90: [10, 11, 12]}, got
    s = stories(60, 7)["options"][0]["story_min"]
    assert s[0] > s[1] and abs(sum(s) - stories(60)["body_min"]) < 1.5, s
    assert stories(12, 2)["options"][0]["story_min"][1] >= STORY_MIN and stories(15)["intro_s"] == 30
    assert runtime_range(20) == (17, 23) and runtime_range(60) == (57, 63) and runtime_range(8) == (8, 11)
    assert runtime_range(180) == (177, 180)
    print("vtypes selftest ok")


if __name__ == "__main__":  # python -m dvr_cowork.vtypes
    selftest()
