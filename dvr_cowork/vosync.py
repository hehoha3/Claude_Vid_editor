"""Analysis stage: timestamps + audio -> plan.json (seconds). No Resolve needed."""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
from pathlib import Path

import numpy as np

from .align import HOP, energy_db, match_cues, refine
from .config import POINTER, ROOT, work_root
from .timestamps import parse_timestamp_file, to_vo_start
from .transcribe import load_audio, transcribe


def clips_job(folder) -> str:
    """Job name of a per-sentence folder: <video>_<folder> (D:/x/amazon_2/audios/mp3 -> amazon_2_mp3); plan.py
    reads .work/<this>/plan.json."""
    p = Path(folder)
    return f"{p.parents[1].name}_{p.name}"


def job_dir(cfg, audio: str) -> Path:
    stem = re.sub(r"[^\w.-]+", "_", Path(audio).stem)[:60] or "audio"
    d = work_root(cfg) / stem
    d.mkdir(parents=True, exist_ok=True)
    return d


def clip_files(folder: str, n: int) -> dict[int, Path]:
    """{sentence number: file} of a per-sentence folder (1.mp3, 2.mp3 ...); must be exactly 1..n."""
    files = {int(p.stem): p for p in Path(folder).iterdir()
             if p.stem.isdigit() and p.suffix.lower() in (".mp3", ".wav")}
    want = set(range(1, n + 1))
    if set(files) != want:
        raise ValueError(f"{folder}: need one file per timestamp line, 1..{n}; missing {sorted(want - set(files))[:20]}"
                         f", extra {sorted(set(files) - want)[:20]}")
    return files


def speech_span(samples, acfg: dict, sr: int = 16000) -> tuple[float, float]:
    """(onset, offset) s of the voiced part: frames within silence_db_below_speech of the speech level."""
    db = energy_db(samples, sr)
    voiced = np.flatnonzero(db >= np.percentile(db, 90) - float(acfg["silence_db_below_speech"])) if len(db) else []
    dur = len(samples) / sr
    return (voiced[0] * HOP, min(dur, (voiced[-1] + 1) * HOP)) if len(voiced) else (0.0, dur)


def clips_segments(folder: str, cues, acfg: dict):
    """One file per sentence (user 2026-10-16: audios/mp3/1.mp3 ... = timestamp line 1 ...): no Whisper, no cutting.
    Each file becomes one A2 item; its onset lands on the timestamp, head/tail pads as in refine()."""
    files, segs, total = clip_files(folder, len(cues)), [], 0.0
    audio, bad = {}, []
    for c in cues:  # decode all first: one error lists every broken file (africa_3: 5 runs, 1 file each)
        try:
            audio[c.index] = load_audio(files[c.index])
        except Exception:
            bad.append(c.index)
    if bad:
        raise ValueError(f"{folder}: {len(bad)} unreadable file(s), re-export: "
                         + " ".join(files[i].name for i in bad))
    for c in cues:
        x = audio[c.index]
        dur = len(x) / 16000
        on, off = speech_span(x, acfg)
        total += dur
        segs.append({"i": c.index, "ts": c.t, "text": c.text, "audio": str(files[c.index]),
                     "onset": round(on, 3), "offset": round(off, 3),
                     "src_in": round(max(0.0, on - float(acfg["head_pad"])), 3),
                     "src_out": round(min(dur, off + float(acfg["tail_pad"])), 3),
                     "conf": 1.0, "flags": [] if off - on >= 0.2 else ["very_short"]})
    return segs, {"duration": round(total, 3), "threshold_db": "-", "speech_db": "-", "pauses_found": 0}


def analyze(audio: str, ts_path: str, cfg: dict, log=print, transcript_json: str | None = None):
    """audio = one narration file (Whisper + cut per sentence) or a folder of per-sentence files 1..n."""
    audio = os.path.abspath(audio)
    ts_path = os.path.abspath(ts_path)
    if not os.path.exists(audio):
        raise FileNotFoundError(f"audio not found: {audio}")
    if not os.path.isfile(ts_path):
        raise FileNotFoundError(f"timestamp file not found: {ts_path}")

    cues = parse_timestamp_file(ts_path)
    if shift := to_vo_start(cues):  # whole narration later: the first sentence starts at VO_START
        log(f"timestamps: first line moved to {cues[0].t:g}s, every line +{shift:g}s")
    log(f"timestamps: {len(cues)} lines, first {cues[0].t:g}s, last {cues[-1].t:g}s")

    if os.path.isdir(audio):
        segs, stats = clips_segments(audio, cues, cfg["align"])
        model, job = "per-sentence files (no Whisper)", clips_job(audio)
    else:
        samples = load_audio(audio)  # decoded once, reused for Whisper and the pause analysis
        if transcript_json:
            tr = json.loads(Path(transcript_json).read_text(encoding="utf-8"))
        else:
            tr = transcribe(audio, cfg, work_root(cfg) / "cache", log, samples=samples)
        if not tr.get("words"):
            raise RuntimeError("Whisper returned no words - is the audio silent or in another language?")
        matches = match_cues(cues, tr["words"])
        segs, stats = refine(cues, matches, samples, cfg["align"])
        model, job = tr.get("model"), audio
    plan = {
        "version": 1,
        "created": _dt.datetime.now().isoformat(timespec="seconds"),
        "audio": audio,
        "timestamps": ts_path,
        "model": model,
        "stats": stats,
        "segments": segs,
    }
    d = job_dir(cfg, job)
    plan_path = d / "plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    return plan, plan_path


def write_pointer(plan_path: Path, options: dict, config_path: str | None = None):
    POINTER.parent.mkdir(parents=True, exist_ok=True)
    POINTER.write_text(json.dumps({"workspace": str(ROOT), "plan": str(plan_path),
                                   "config": config_path, "options": options}, indent=1),
                       encoding="utf-8")
