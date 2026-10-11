"""Subject measurement for doc-edit plan: YOLO-World v2 on the local GPU (free, 0 Claude tokens).

Each clip is measured once, cached by clip id in .work/library/yolo.json: 4 fps samples of the largest box of the
clip's tagged species (or 'animal'), [cx, cy, w, h] normalized, 0 = no subject. From the boxes, derive():
  in    longest stretch with the subject in frame (seconds) -> plan.py cuts inside it
  size  shot size from how much of the frame the subject fills
  seen  share of samples with the subject

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/yolo.py --selftest
"""
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[4]
CACHE = ROOT / ".work" / "library" / "yolo.json"
MODEL = ROOT / ".models" / "yolov8s-worldv2.pt"  # auto-downloaded by ultralytics on first use
V, FPS, W, H, CONF = 1, 4, 640, 360, 0.05      # open-vocabulary scores run low: 0.05 keeps recall high
# size from the median larger side of the subject box; calibrated 2026-10-11 on 255 tagged clips (58% equal to the
# Sonnet tag, 98% within one size). Movement direction was tried: it matched the tags on only 30%, so it is not used.
SIZE_SIDE = ((0.97, "extreme_close"), (0.75, "close_up"), (0.44, "medium"), (0.0, "wide"))


def frames(path):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-hwaccel", "auto", "-i", str(path), "-vf", f"fps={FPS},scale={W}:{H}",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
    return list(np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)) if raw else []


def derive(f):
    good = [bool(b) and 0.05 < b[0] < 0.95 for b in f]  # subject present, its centre not leaving the frame
    if not any(good):
        return None
    best, start, holes = (0, 0), None, 0
    for i, g in enumerate(good + [False, False]):       # runs of good samples, single-sample holes bridged
        if g:
            start, holes = (i if start is None else start), 0
        elif start is not None:
            holes += 1
            if holes > 1:
                end = i - holes + 1
                best = max(best, (start, end), key=lambda r: r[1] - r[0])
                start, holes = None, 0
    boxes = [b for b, g in zip(f, good) if g]
    side = median(max(b[2], b[3]) for b in boxes)
    size = next(name for lim, name in SIZE_SIDE if side >= lim)
    return {"in": [round(best[0] / FPS, 2), round(best[1] / FPS, 2)], "size": size, "seen": round(len(boxes) / len(f), 2)}


def measure(clips):
    """Attach c["yolo"] to every clip; runs the model only on clips not cached yet. Returns (new, seconds)."""
    cache = json.loads(CACHE.read_text("utf-8")) if CACHE.exists() else {}
    todo = [c for c in clips if cache.get(c["id"], {}).get("v") != V]
    t0 = time.time()
    if todo:
        from ultralytics import YOLOWorld
        m = YOLOWorld(str(MODEL))
        with ThreadPoolExecutor(4) as ex:  # decode the next clips while the GPU works
            for k in range(0, len(todo), 8):
                chunk = todo[k:k + 8]
                for c, fr in zip(chunk, ex.map(lambda c: frames(c["abs"]), chunk)):
                    m.set_classes(sorted(set(c["tags"].get("species", []))) + ["animal"])
                    out = []
                    for r in (m.predict(fr, conf=CONF, verbose=False, batch=32) if fr else []):
                        b = r.boxes
                        i = int((b.xywhn[:, 2] * b.xywhn[:, 3]).argmax()) if len(b) else -1
                        out.append([round(float(x), 3) for x in b.xywhn[i]] if i >= 0 else 0)
                    cache[c["id"]] = {"v": V, "f": out}
                CACHE.parent.mkdir(parents=True, exist_ok=True)
                CACHE.write_text(json.dumps(cache, separators=(",", ":")), "utf-8")  # saved per chunk: safe to stop
    for c in clips:
        if c["id"] in cache:
            c["yolo"] = derive(cache[c["id"]]["f"])
    return len(todo), round(time.time() - t0)


def selftest():
    walk = [0, 0] + [[0.2 + 0.05 * i, 0.5, 0.3, 0.4] for i in range(12)] + [0] * 4
    y = derive(walk)
    assert y["in"] == [0.5, 3.5] and y["size"] == "wide", y
    holed = [[0.5, 0.5, 0.7, 0.8]] * 5 + [0] + [[0.5, 0.5, 0.7, 0.8]] * 5
    assert derive(holed)["in"] == [0.0, 2.75] and derive(holed)["size"] == "close_up"  # one-sample hole bridged
    assert derive([0] * 8) is None and derive([[0.99, 0.5, 0.1, 0.1]] * 8) is None  # absent / leaving the frame
    print("selftest ok")


if __name__ == "__main__":
    selftest()
