from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parent.parent


class Stop(RuntimeError):
    """An actionable failure; never continue with guessed media or timing."""


def video_path(value):
    p = Path(value).expanduser().resolve()
    if p.name.lower() == "audios":
        p = p.parent
    if "_pushed" in [s.lower() for s in p.parts]:
        raise Stop("The _pushed folder is outside this workflow.")
    if p.drive.upper() == "Z:" or str(p).startswith("\\\\"):
        raise Stop("Use a local video folder, not a network media root.")
    return p


def prod(video):
    return video_path(video) / ".production"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def atomic_text(path, text):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp", dir=p.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, p)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def write_json(path, data):
    atomic_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def object_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@contextlib.contextmanager
def lock(path):
    """OS-owned lock, without reading/writing the protected byte before acquisition.

    Windows byte locks are mandatory: even reading byte 0 from another handle
    raises PermissionError while it is locked. msvcrt permits locking beyond EOF,
    so an empty lock file needs no initialization. Always lock/unlock byte 0.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a+b", buffering=0) as f:
        f.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            raise Stop(f"Another writer owns {p}. Wait for that process to finish.") from e
        try:
            yield
        finally:
            f.seek(0)
            if os.name == "nt":
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f, fcntl.LOCK_UN)


def config():
    p = ROOT / "config.toml"
    return tomllib.loads(p.read_text("utf-8")) if p.exists() else {}


def run(args, timeout=180):
    try:
        r = subprocess.run([str(x) for x in args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except FileNotFoundError as e:
        raise Stop(f"Missing executable: {args[0]}") from e
    except subprocess.TimeoutExpired as e:
        raise Stop(f"Timed out: {args[0]}; no result assumed.") from e
    if r.returncode:
        raise Stop(f"{args[0]} failed: {r.stderr[-1600:]}")
    return r.stdout


def probe(path, decode=False):
    p = Path(path)
    if not p.is_file() or not p.stat().st_size:
        raise Stop(f"Missing or empty media: {p}")
    before = (p.stat().st_size, p.stat().st_mtime_ns)
    raw = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", p]))
    streams = raw.get("streams", [])
    duration = float(raw.get("format", {}).get("duration", 0))
    if not math.isfinite(duration) or duration <= 0:
        raise Stop(f"Invalid media duration: {p}")
    if decode:
        run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", p, "-f", "null", "-"], timeout=600)
    after = (p.stat().st_size, p.stat().st_mtime_ns)
    if before != after:
        raise Stop(f"File is still changing/copying: {p}")
    v = next((s for s in streams if s["codec_type"] == "video"), None)
    a = next((s for s in streams if s["codec_type"] == "audio"), None)
    from fractions import Fraction
    fps = float(Fraction(v.get("avg_frame_rate", "0/1"))) if v else 0
    return {"duration": duration, "fps": fps, "video": bool(v), "audio": bool(a),
            "width": v.get("width", 0) if v else 0, "height": v.get("height", 0) if v else 0,
            "size": before[0], "sha256": digest(p)}


def numbered(folder, suffix, count):
    """Reject aliases (01.mp4), duplicate IDs and extras before importing anything."""
    folder = Path(folder)
    got = {}
    for p in folder.iterdir() if folder.is_dir() else []:
        if p.suffix.lower() != suffix:
            continue
        if not re.fullmatch(r"[1-9]\d*", p.stem):
            raise Stop(f"Expected canonical numeric name, got {p.name}")
        n = int(p.stem)
        if n in got:
            raise Stop(f"Duplicate numeric ID: {p.name}")
        got[n] = p.resolve()
    want = set(range(1, count + 1))
    if set(got) != want:
        raise Stop(f"{folder}: missing {sorted(want-set(got))}; extra {sorted(set(got)-want)}")
    return got


def stamp(seconds):
    ms = round(seconds * 1000)
    return f"{ms//60000:02d}:{ms//1000%60:02d}.{ms%1000:03d}"


def frames(seconds, fps):
    return round(float(seconds) * float(fps))


def event(video, stage, **fields):
    p = prod(video) / "state.json"
    state = read_json(p) if p.exists() else {}
    state.update(stage=stage, **fields)
    write_json(p, state)
    return state
