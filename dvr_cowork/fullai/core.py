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

ROOT = Path(__file__).resolve().parents[2]  # the workspace root (.secrets, .work)
# The 1h engine's writer lock (dvr_cowork.jobs): 1h and 8p never write to the one Resolve at the same time.
WRITER = ROOT / ".work" / "automation" / "resolve_writer.lock"


class Stop(RuntimeError):
    """An actionable failure; never continue with guessed media or timing."""


from ..videokey import day_project  # noqa: E402,F401  one rule for both engines


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


@contextlib.contextmanager
def resolve_lock():
    """Global Resolve writer lock; the .who note is what dvr_cowork.jobs prints when it finds the lock taken."""
    with lock(WRITER):
        WRITER.with_suffix(".who").write_text(f"pid {os.getpid()} dvr_cowork ai", "utf-8")
        yield


def config():
    p = Path(__file__).with_name("config.toml")  # 8p's own; the workspace config.toml belongs to the 1h engine
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
            "size": before[0], "mtime_ns": before[1], "sha256": digest(p)}


def unchanged(path, old):
    """Fingerprint (path, size, mtime) equals the last probe: reuse it instead of re-decoding/hashing.
    Resolve writes still re-digest every file (reviewed_media), so a cache hit never skips the final check."""
    try:
        st = Path(path).stat()
    except OSError:
        return False
    return bool(old) and old.get("path") == str(path) and old.get("size") == st.st_size and old.get("mtime_ns") == st.st_mtime_ns


def numbered(folder, suffix, count):
    """Index = the trailing number of the file name: 1.mp4, shot_001.mp4, shot-001.mp4, S01.mp4 all mean 1.
    Duplicate IDs (1.mp4 + shot_001.mp4) and extras are refused before importing anything."""
    folder = Path(folder)
    got = {}
    for p in folder.iterdir() if folder.is_dir() else []:
        if p.suffix.lower() != suffix:
            continue
        m = re.search(r"(\d+)$", p.stem)
        if not m or int(m[1]) < 1:
            raise Stop(f"No trailing index number in file name: {p.name}")
        n = int(m[1])
        if n in got:
            raise Stop(f"Duplicate numeric ID: {p.name}")
        got[n] = p.resolve()
    want = set(range(1, count + 1))
    if set(got) != want:
        raise Stop(f"{folder}: missing {sorted(want-set(got))}; extra {sorted(set(got)-want)}")
    return dict(sorted(got.items()))  # numeric order; iterdir gives 1,10,11,2…


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
