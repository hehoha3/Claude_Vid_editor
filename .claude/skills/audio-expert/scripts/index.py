"""audio-expert index: every audio root of scan-source -> .work/audio_expert/audio_index.jsonl (incremental).
Amazona audio paths are relative to AUDIO; the read-only roots (Z:\\Unseen\\SFX, Sound, Sound Animal V1) are stored as
absolute paths (AUDIO / abs == abs). Files gone from the library indexes are dropped.

    .venv/Scripts/python.exe .claude/skills/audio-expert/scripts/index.py          # add new files, profile music
    .venv/Scripts/python.exe .claude/skills/audio-expert/scripts/index.py --selftest

One entry per file: type/track_target/environment from FOLDER + FILENAME only (review_method filename_only,
confidence <= 0.5, unknown fields null). Music-like files also get review_method waveform_analysis: `arc` = RMS dB
per 5 s of the file (rounded), `quiet_tail` = seconds of near-silence at the end. Nothing is ever "listened".
profile() is reused by plan.py for SFX peaks.
"""
import json, re, subprocess, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / ".claude/skills/scan-source/scripts"))
from scan_source import ROOTS, index_of  # noqa: E402
CATEGORY = {"sfx": "nature_sound", "animal": "nature_sound", "sound": "tense_music"}  # read-only root -> folder rule
AUDIO = Path(r"Z:\Unseen\Amazona\audio")
OUT = ROOT / ".work" / "audio_expert" / "audio_index.jsonl"
SR, STEP = 8000, 5
MUSIC_NAMES = ("drum-dada", "hypnotic-nature", "realm of fantastic", "paranoia-shadows", "monkey horror",
               "enchanted-forest", "alien-rainforest")


def decode(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True)
    return np.frombuffer(r.stdout, np.float32)


def db(x):
    return float(20 * np.log10(max(float(np.sqrt(np.mean(x * x))) if len(x) else 0.0, 1e-5)))


def profile(path, step=STEP):
    """-> dict(arc=[dB per step s], peak_s=time of loudest 20 ms, quiet_tail=s of tail below -50 dB)."""
    a = decode(path)
    if not len(a):
        return None
    n = step * SR
    arc = [round(db(a[i:i + n])) for i in range(0, len(a), n)]
    w = SR // 50
    env = np.sqrt(np.convolve(a * a, np.ones(w) / w, "same"))
    tail = 0.0
    for i in range(len(a), 0, -SR // 2):
        if db(a[max(0, i - SR // 2):i]) > -50:
            break
        tail += 0.5
    return {"arc": arc, "peak_s": round(float(np.argmax(env)) / SR, 2), "quiet_tail": tail}


def classify(rel):
    p = rel.replace("\\", "/").lower()
    top = p.split("/")[0]
    if top in ("tense_music", "openning") or any(m in p for m in MUSIC_NAMES):
        return "music", 7, ["tension"] if top != "ambience_sound" else ["calm"]
    if top == "sxf":
        sub = "riser" if "riser" in p else "hit" if "hit" in p or "drop" in p or "impact" in p else \
            "whoosh" if "whoosh" in p or "swoosh" in p or "swish" in p else "other"
        return "sfx_" + sub, 8, []
    env = [k for k in ("forest", "river", "water", "rain", "wind", "thunder", "cricket", "night", "bird", "insect")
           if k in p]
    return ("natural_event" if top == "nature_sound" and any(k in p for k in ("walk", "call", "chirp")) else
            "ambience"), (5 if top == "nature_sound" else 3), env


def files():
    """-> {index path: (folder path for classify(), library entry)} over all audio roots."""
    out = {}
    for key, (root, kind, _) in ROOTS.items():
        if kind != "audio":
            continue
        lib = json.loads(index_of(root).read_text("utf-8"))["clips"]
        for c in (lib.values() if isinstance(lib, dict) else lib):
            out[c["path"] if root == AUDIO else str(root / c["path"])] = (
                c["path"] if root == AUDIO else f"{CATEGORY[key]}/{c['path']}", c)
    return out


def main():
    lib = files()
    have = {}
    if OUT.exists():
        have = {json.loads(l)["path"]: json.loads(l) for l in OUT.read_text("utf-8").splitlines() if l}
    gone = [k for k in have if k not in lib]
    for k in gone:
        del have[k]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    new = 0
    for rel, (folder, c) in lib.items():
        if rel in have:
            continue
        typ, tr, env = classify(folder)
        e = {"asset_id": re.sub(r"[^a-z0-9]+", "_", rel.lower())[:80], "path": rel, "origin": "user_library",
             "type": typ, "track_target": tr, "environment": env, "species": None, "emotion": [], "function": [],
             "duration_seconds": c.get("duration"), "channels": c.get("channels"), "sample_rate": c.get("sample_rate"),
             "loopable": None, "review_method": "filename_only", "confidence": 0.4,
             "evidence": "folder/filename only; content not listened"}
        if typ == "music":
            pr = profile(AUDIO / rel)
            if pr:
                e.update(pr, review_method="waveform_analysis", confidence=0.5,
                         evidence="RMS arc per 5 s from waveform; mood from filename, not listened")
        have[rel] = e
        new += 1
    OUT.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in have.values()) + "\n", "utf-8")
    by = {}
    for e in have.values():
        by[e["type"]] = by.get(e["type"], 0) + 1
    print(f"index: {len(have)} files ({new} new, {len(gone)} gone) -> {OUT.relative_to(ROOT)} | {by}")


def selftest():
    t = np.concatenate([np.full(SR * 5, 0.1, np.float32), np.zeros(SR * 3, np.float32)])
    n = STEP * SR
    assert round(db(t[:n])) == -20 and db(t[n:]) < -90
    assert classify("tense_music\\x.mp3")[0] == "music" and classify("SXF\\336 SFX\\RISERS\\a.wav")[0] == "sfx_riser"
    assert classify("Nature_sound\\forest_ambience\\walk-on-leaves.mp3")[0] == "natural_event"
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    selftest() if "--selftest" in sys.argv else main()
