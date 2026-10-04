"""Analysis stage: timestamps + audio -> plan.json (seconds). No Resolve needed."""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
from pathlib import Path

from .align import match_cues, refine
from .config import POINTER, ROOT, work_root
from .timestamps import parse_timestamp_file
from .transcribe import load_audio, transcribe


def job_dir(cfg, audio: str) -> Path:
    stem = re.sub(r"[^\w.-]+", "_", Path(audio).stem)[:60] or "audio"
    d = work_root(cfg) / stem
    d.mkdir(parents=True, exist_ok=True)
    return d


def analyze(audio: str, ts_path: str, cfg: dict, log=print, transcript_json: str | None = None):
    audio = os.path.abspath(audio)
    ts_path = os.path.abspath(ts_path)
    if not os.path.isfile(audio):
        raise FileNotFoundError(f"audio not found: {audio}")
    if not os.path.isfile(ts_path):
        raise FileNotFoundError(f"timestamp file not found: {ts_path}")

    cues = parse_timestamp_file(ts_path)
    log(f"timestamps: {len(cues)} lines, first {cues[0].t:g}s, last {cues[-1].t:g}s")

    samples = load_audio(audio)  # decoded once, reused for Whisper and the pause analysis
    if transcript_json:
        tr = json.loads(Path(transcript_json).read_text(encoding="utf-8"))
    else:
        tr = transcribe(audio, cfg, work_root(cfg) / "cache", log, samples=samples)
    if not tr.get("words"):
        raise RuntimeError("Whisper returned no words - is the audio silent or in another language?")
    matches = match_cues(cues, tr["words"])
    segs, stats = refine(cues, matches, samples, cfg["align"])
    plan = {
        "version": 1,
        "created": _dt.datetime.now().isoformat(timespec="seconds"),
        "audio": audio,
        "timestamps": ts_path,
        "model": tr.get("model"),
        "stats": stats,
        "segments": segs,
    }
    d = job_dir(cfg, audio)
    plan_path = d / "plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    return plan, plan_path


def write_pointer(plan_path: Path, options: dict, config_path: str | None = None):
    POINTER.parent.mkdir(parents=True, exist_ok=True)
    POINTER.write_text(json.dumps({"workspace": str(ROOT), "plan": str(plan_path),
                                   "config": config_path, "options": options}, indent=1),
                       encoding="utf-8")
