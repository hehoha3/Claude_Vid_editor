"""Seconds -> frames, and overlap resolution on the destination track. stdlib-only.

Each segment becomes one timeline item that references a frame range of the SAME source
audio clip. That is exactly what Resolve's Blade produces: N items, one source file.

Placement rule: the first voiced frame of each sentence (its onset) lands on its timestamp.
The small head pad before the onset is placed just before the timestamp.

timestamp_clock:
  "timecode" - [mm:ss] was read off Resolve's timeline timecode (1 s = nominal fps frames).
  "realtime" - [mm:ss] is wall-clock time (matters only for 23.976 / 29.97 timelines:
               the two differ by ~1.8 s after 30 min).
"""
from __future__ import annotations

import math


def layout(segments: list[dict], fps_tl: float, fps_clip: float, acfg: dict, strategy: str | None = None):
    clock = acfg.get("timestamp_clock", "timecode")
    offset = float(acfg.get("timestamp_offset", 0.0))
    guard = int(acfg.get("guard_frames", 1))
    strategy = strategy or acfg.get("on_overlap", "push")
    if strategy not in ("push", "trim", "abort"):
        raise ValueError(f"on_overlap must be push|trim|abort, got {strategy!r}")
    ratio = fps_tl / fps_clip  # timeline frames per source frame (1.0 in normal projects)
    rate = round(fps_tl) if clock == "timecode" else fps_tl

    items: list[dict] = []
    for s in segments:
        src_in = math.floor(s["src_in"] * fps_clip + 1e-6)
        src_out = math.ceil(s["src_out"] * fps_clip - 1e-6)
        speech_in = math.floor(s["onset"] * fps_clip + 1e-6)
        speech_out = math.ceil(s["offset"] * fps_clip - 1e-6)
        src_out = max(src_out, src_in + 1)
        target = (s["ts"] + offset) * rate  # where the onset must land (timeline frames)
        flags = list(s.get("flags", []))
        rec = round(target - (s["onset"] * fps_clip - src_in) * ratio)
        if rec < 0:  # timestamp too close to timeline start for the head pad: drop the pad
            src_in = min(speech_in, src_in + math.ceil(-rec / ratio))
            rec = round(target - (s["onset"] * fps_clip - src_in) * ratio)
            if rec < 0:
                rec = 0
                flags.append("start_clamped")
        items.append({
            "i": s["i"], "ts": s["ts"], "text": s["text"], "conf": s.get("conf", 1.0),
            "src_in_f": src_in, "src_out_f": src_out,
            "speech_in_f": speech_in, "speech_out_f": speech_out,
            "rec_f": rec, "target_f": round(target), "shift_f": 0, "flags": flags,
        })

    def dur(it):
        return max(1, round((it["src_out_f"] - it["src_in_f"]) * ratio))

    def overlap(prev, cur):
        return prev["rec_f"] + dur(prev) - (cur["rec_f"] - guard)

    conflicts: list[dict] = []
    for k in range(1, len(items)):
        prev, cur = items[k - 1], items[k]
        over = overlap(prev, cur)
        if over <= 0:
            continue
        # 1) shorten the previous tail pad (silence only)
        spare = max(0, prev["src_out_f"] - max(prev["speech_out_f"], prev["src_in_f"] + 1))
        t = min(spare, math.ceil(over / ratio))
        if t > 0:
            prev["src_out_f"] -= t
            prev["flags"].append("tail_trimmed")
            over = overlap(prev, cur)
            if over <= 0:
                continue
        # 2) shorten the current head pad (onset position is unchanged)
        spare = max(0, cur["speech_in_f"] - cur["src_in_f"])
        h = min(spare, math.ceil(over / ratio))
        if h > 0:
            cur["src_in_f"] += h
            cur["rec_f"] += round(h * ratio)
            cur["flags"].append("head_trimmed")
            over = overlap(prev, cur)
            if over <= 0:
                continue
        # 3) real speech collision
        if strategy == "trim":
            prev["src_out_f"] = max(prev["src_in_f"] + 1, prev["src_out_f"] - math.ceil(over / ratio))
            prev["flags"].append("speech_cut")
            over = overlap(prev, cur)
            if over <= 0:
                continue
            strategy_now = "push"
        else:
            strategy_now = strategy
        if strategy_now == "push":
            cur["rec_f"] += over
            cur["shift_f"] += over
            if "pushed" not in cur["flags"]:
                cur["flags"].append("pushed")
        else:
            conflicts.append({"line": prev["i"], "next": cur["i"], "overlap_s": round(over / fps_tl, 3)})

    for it in items:
        it["dur_f"] = dur(it)
    return items, conflicts
