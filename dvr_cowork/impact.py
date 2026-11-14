r"""Impact: 0:00 black + a string riser into an impact on A9, the intro music from the hit (user 2026-11-06; footage+AI
1-3h). The hit lands at `at` (<= IMPACT_MAX s); the opener shot cuts in on it, the narrator still starts at 0:03.6.
intro.py picks the film's file (one per film, never two films of one day project: REG), plan.py puts black 0 -> at.

    python -m dvr_cowork impact <video>        the impact of this film (picked once, kept)
    python -m dvr_cowork impact --selftest
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .videokey import day_project, video_key

ROOT = Path(__file__).resolve().parents[1]
IMPACT_MAX = 1.0  # s: the hit lands here at the latest; a longer riser starts part-way in
REG = ROOT / ".work" / "library" / "impact.json"


def sfx_dir():
    from .config import load_config
    return Path(load_config()["paths"]["audio_lib"]) / "SXF" / "impact"


def hit_of(samples, sr):
    """Time of the hit in a riser -> impact file: the biggest jump of the 20 ms RMS (vs the 60 ms before) up to its
    loudest point; the riser climbs smoothly, the hit jumps."""
    import numpy as np
    w = max(1, int(sr * 0.02))
    n = len(samples) // w
    if n < 6:
        return 0.0
    rms = np.sqrt((np.asarray(samples[:n * w], dtype=np.float64).reshape(n, w) ** 2).mean(1)) + 1e-9
    peak = int(rms.argmax())
    jump = np.zeros(n)
    jump[3:] = rms[3:] - rms[:-3]
    j = int(jump[:peak + 3].argmax()) if peak else 0
    return round(max(0, j - 1) * w / sr, 3)


def impact(key, files=None, reg=None, save=True):
    """The film's impact: kept once picked; else the least used file no other film of the same day project has.
    -> {path, hit, src_in, at, dur}."""
    reg = reg if reg is not None else (json.loads(REG.read_text("utf-8")) if REG.exists() else {"hits": {}, "used": {}})
    files = sorted(files if files is not None else
                   [p for p in sfx_dir().glob("*") if p.suffix.lower() in (".mp3", ".wav")], key=str)
    if not files:
        raise SystemExit(f"no impact file in {sfx_dir()} (audio-expert fetch: string riser + impact)")
    used, day = reg["used"], day_project(key)
    path = used.get(key)
    if not path or not any(str(f) == path for f in files):
        busy = {p for k, p in used.items() if k != key and day_project(k) == day}
        count = {str(f): sum(p == str(f) for p in used.values()) for f in files}
        path = min((str(f) for f in files if str(f) not in busy), key=lambda p: (count[p], p), default=None) \
            or min(count, key=lambda p: (count[p], p))
    h = reg["hits"].get(path)
    if not h:
        from .transcribe import SR, load_audio
        a = load_audio(path)
        h = {"hit": hit_of(a, SR), "dur": round(len(a) / SR, 3)}
        reg["hits"][path] = h
    src_in = round(max(0.0, h["hit"] - IMPACT_MAX), 3)
    used[key] = path
    if save:
        REG.parent.mkdir(parents=True, exist_ok=True)
        REG.write_text(json.dumps(reg, ensure_ascii=False, indent=1), "utf-8")
    return {"path": path, "hit": h["hit"], "src_in": src_in, "at": round(h["hit"] - src_in, 3),
            "dur": round(h["dur"] - src_in, 3)}


def selftest():
    import numpy as np
    sr = 16000
    t = np.arange(int(sr * 3)) / sr
    riser = np.where(t < 1.4, 0.05 + 0.25 * t / 1.4, 0.0) * np.sin(2 * np.pi * 900 * t)
    hit = np.where(t >= 1.4, np.exp(-(t - 1.4) * 3), 0.0) * np.sin(2 * np.pi * 60 * t)
    assert abs(hit_of(riser + hit, sr) - 1.4) <= 0.06, hit_of(riser + hit, sr)
    files = ["a.mp3", "b.mp3", "c.mp3"]
    reg = {"hits": {f: {"hit": 1.5, "dur": 8.0} for f in files}, "used": {"africa_061126_1__Chann_1": "a.mp3"}}
    y = impact("africa_061126_1__Chann_2", files, reg, save=False)
    assert y["path"] == "b.mp3" and (y["src_in"], y["at"], y["dur"]) == (0.5, 1.0, 7.5), y  # never the day's other film
    assert impact("africa_061126_1__Chann_2", files, reg, save=False)["path"] == "b.mp3"  # kept once picked
    print("impact selftest ok")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--selftest" in argv:
        return selftest()
    if not argv:
        print(__doc__); return 2
    v = Path(argv[0])
    v = v.parent if v.name.lower() == "audios" else v
    print(json.dumps(impact(video_key(v)), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
