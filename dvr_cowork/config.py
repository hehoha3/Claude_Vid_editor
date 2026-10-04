"""Configuration loading. stdlib-only (also imported by the in-app Resolve script)."""
from __future__ import annotations

import copy
from pathlib import Path

try:  # Python 3.11+
    import tomllib as _toml
except ImportError:  # pragma: no cover - Resolve's embedded Python may be older
    try:
        import tomli as _toml  # type: ignore
    except ImportError:
        _toml = None

ROOT = Path(__file__).resolve().parent.parent
POINTER = Path.home() / ".dvr_cowork" / "last_plan.json"

DEFAULTS: dict = {
    "resolve": {
        "timeline_name": "Edit",
        "audio_bin": "4. Audio",
        "audio_track": 4,
        "backup_timeline": True,
        "save_project": True,
        "script_api": "",
        "script_lib": "",
    },
    "whisper": {
        "model": "small.en",
        "language": "en",
        "device": "cpu",
        "compute_type": "int8",
        "beam_size": 5,
        "cpu_threads": 0,
    },
    "align": {
        "head_pad": 0.10,
        "tail_pad": 0.25,
        "min_silence": 0.06,
        "silence_db_below_speech": 32.0,
        "min_confidence": 0.60,
        "on_overlap": "push",
        "guard_frames": 1,
        "timestamp_clock": "timecode",
        "timestamp_offset": 0.0,
        "markers": False,
        "color_low_confidence": "Orange",
        "color_pushed": "Pink",
    },
    "paths": {
        "work_dir": ".work",
        "models_dir": ".models",
    },
}


def _merge(base: dict, over: dict) -> dict:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config(path: str | None = None) -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    p = Path(path) if path else ROOT / "config.toml"
    if p.exists() and _toml is not None:
        with open(p, "rb") as f:
            _merge(cfg, _toml.load(f))
    return cfg


def _resolve_dir(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


def work_root(cfg: dict) -> Path:
    d = _resolve_dir(cfg["paths"]["work_dir"])
    d.mkdir(parents=True, exist_ok=True)
    return d


def models_dir(cfg: dict) -> Path:
    d = _resolve_dir(cfg["paths"]["models_dir"])
    d.mkdir(parents=True, exist_ok=True)
    return d
