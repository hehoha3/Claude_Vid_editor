#!/usr/bin/env python3
"""Make AI-generated clips look like camera footage, in place.

    process_ai_video.py                      every clip under D:\\AI_video not processed yet (overwrites!)
    process_ai_video.py <folder or file>...  only these
    process_ai_video.py --compare OUTDIR <file>...   side-by-side test renders (original | graded), no overwrite

Per clip: measure 6 frames, then grade toward the user's real stock footage (luma p1 ~0.08, p99 ~0.85,
sat p95 ~0.76, neutral greys): white balance from near-grey pixels, levels, saturation, softer micro-detail,
fill 1920x1080 (lanczos), fine temporal luma grain. A metadata marker prevents grading a clip twice.
Leading character-sheet frames (grid of labelled views the AI generator puts before the shot) are cut off.
Each render goes to a temp file next to the original, is checked (frame count, duration), then replaces it."""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from dvr_cowork.config import load_config  # noqa: E402
ROOT = Path(load_config()["paths"]["ai_video"])  # AI clips root of this machine (config.toml)
MARK = "ai_look_v3cs"   # graded + character sheet cut
V3 = "ai_look_v3"        # graded earlier, not checked for a character sheet: sheet cut only
OLD = "ai_look_v2"       # base grade done earlier: only the v3 colour stage is added (+ sheet cut)
LOG = Path(__file__).resolve().parents[4] / ".work" / "process_ai_video" / "log.jsonl"
# path -> [size, mtime_ns] of clips known to need nothing: unchanged files are skipped without ffprobe
INDEX = LOG.parent / "done_index.json"
EXTS = {".mp4", ".mov", ".m4v", ".mkv"}
W, H = 640, 360
# targets measured on 20 random clips of Z:\Unseen\Amazona\video
BLACK, WHITE, SAT = 0.075, 0.86, 0.76
JOBS = 3


def ffprobe(p, *args):
    return subprocess.run(["ffprobe", "-v", "error", *args, str(p)], capture_output=True, text=True).stdout.strip()


def mark(p):
    return ffprobe(p, "-show_entries", "format_tags=comment", "-of", "csv=p=0")


def fps(p):
    return Fraction(ffprobe(p, "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0"))


# Character sheet at the head of the clip: a sheet frame then a hard cut to footage (biggest frame-to-frame jump in
# the first CS_MAX frames > CUT_MIN and >= CUT_RATIO x the clip's median jump), or else leading frames that show a
# panel grid (long straight borders in both directions). Frames are native, decoded in memory.
CS_W, CS_H, CS_SCAN, CS_MAX = 480, 270, 24, 8
EDGE, CUT_MIN, CUT_RATIO = 30, 35.0, 3.0


def border_lines(edges, min_run=0.25):
    """Number of distinct rows of `edges` (bool) that hold a straight run >= min_run of the width."""
    h, w = edges.shape
    need = int(min_run * w)
    count, last = 0, -10
    for y in range(int(h * 0.03), int(h * 0.97)):
        d = np.diff(np.concatenate(([0], edges[y].astype(np.int8), [0])))
        runs = np.flatnonzero(d == -1) - np.flatnonzero(d == 1)
        if runs.size and runs.max() >= need:
            if y - last > 4:
                count += 1
            last = y
    return count


def has_panels(f):
    return border_lines(np.abs(np.diff(f, axis=0)) > EDGE) + border_lines((np.abs(np.diff(f, axis=1)) > EDGE).T) >= 2


def sheet_frames(p):
    """Count of leading frames that are a character sheet (0 if none)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-frames:v", str(CS_SCAN), "-vf", f"scale={CS_W}:{CS_H}",
                          "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    n = len(raw) // (CS_W * CS_H)
    fr = np.frombuffer(raw, np.uint8)[: n * CS_W * CS_H].reshape(-1, CS_H, CS_W).astype(np.int16)
    if len(fr) < 3:
        return 0
    d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))
    k = int(np.argmax(d[:CS_MAX]))
    if d[k] > CUT_MIN and d[k] / max(float(np.median(d)), 3.0) >= CUT_RATIO:
        return k + 1
    n = 0
    for f in fr[:CS_MAX]:
        if not has_panels(f):
            break
        n += 1
    return n


def frames(p, vf=""):
    dur = float(ffprobe(p, "-show_entries", "format=duration", "-of", "csv=p=0") or 0)
    out = []
    for t in (0.1, 0.25, 0.4, 0.55, 0.7, 0.85):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{dur * t:.2f}", "-i", str(p), "-frames:v", "1",
                              "-vf", (vf + "," if vf else "") + f"scale={W}:{H}", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                             capture_output=True).stdout
        if len(raw) == W * H * 3:
            out.append(np.frombuffer(raw, np.uint8).reshape(H, W, 3).astype(np.float32) / 255)
    return np.stack(out) if out else None


def params(f):
    """Grade parameters that move this clip's statistics toward the real-footage targets."""
    y = f @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    mx, mn = f.max(-1), f.min(-1)
    sat = (mx - mn) / (mx + 1e-6)
    p1, p99, s95 = (float(np.percentile(y, 1)), float(np.percentile(y, 99)), float(np.percentile(sat, 95)))
    # white balance from near-neutral midtone pixels only (foliage is saturated, so it does not vote)
    grey = (sat < 0.22) & (y > 0.15) & (y < 0.85)
    r, g, b = (f[..., i][grey].mean() for i in range(3)) if grey.sum() > 2000 else (0.0, 0.0, 0.0)
    rb, gm = float(r - b), float(g - (r + b) / 2)
    # levels: lift blacks to BLACK; raise whites toward WHITE but never more than +20 % (dark scenes stay dark)
    lo = max(p1, BLACK)
    hi = min(max(p99, min(WHITE, p99 * 1.2)), 0.95)
    a = (hi - lo) / max(p99 - p1, 0.05)
    b0 = max(0.0, lo - a * p1)
    top = min(1.0, hi + (1 - p99) * a)
    curve = (f"0/{lo:.3f}" if p1 < 0.01 else f"0/{b0:.3f} {p1:.3f}/{lo:.3f}") + f" {p99:.3f}/{hi:.3f} 1/{top:.3f}"
    return {"p1": round(p1, 3), "p99": round(p99, 3), "sat95": round(s95, 3), "rb": round(rb, 3), "gm": round(gm, 3),
            "curve": curve,
            "sat": round(float(np.clip(0.95 / max(s95, 0.01), 0.95, 1.0)), 3),
            # teal/blue casts are the AI "cinematic" look -> remove hard (colorbalance needs ~3x the measured cast);
            # warm casts are usually real light (sun, golden hour) -> touch lightly
            "wb_r": round(float(np.clip(-rb * (3.0 if rb < 0 else 0.6), -0.12, 0.12)), 3),
            "wb_g": round(float(np.clip(-gm * 0.8, -0.06, 0.06)), 3)}


# v3 colour targets: ~20 % under the user's real stock footage (measured: s90 0.705; per-hue p75
# R .48 Y .56 G .59 C .37 B .27 M .28). Saturation is only ever pulled down, never pushed up.
S90 = 0.55
HUE_T = {"r": 0.38, "y": 0.45, "g": 0.47, "c": 0.30, "b": 0.22, "m": 0.22}
HUE_BAND = {"r": (-30, 30), "y": (30, 75), "g": (75, 165), "c": (165, 210), "b": (210, 270), "m": (270, 330)}


def colour(f):
    """Measure saturation overall (s90) and per hue band (p75), return the pull-down that reaches the targets."""
    mx, mn = f.max(-1), f.min(-1)
    s = (mx - mn) / (mx + 1e-6)
    c = mx - mn + 1e-6
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    hue = np.where(mx == r, ((g - b) / c) % 6, np.where(mx == g, (b - r) / c + 2, (r - g) / c + 4)) * 60
    hue = np.where(hue > 330, hue - 360, hue)
    lit = mx > 0.15
    s90 = float(np.percentile(s[lit], 90))
    k = float(np.clip(S90 / s90, 0.65, 1.0))
    out = {"s90": round(s90, 3), "vsat": round(k, 3), "hue": {}}
    for name, (lo, hi) in HUE_BAND.items():
        m = lit & (hue >= lo) & (hue < hi) & (s > 0.1)
        if m.sum() < 0.01 * m.size:   # colour hardly present: leave it
            continue
        p75 = float(np.percentile(s[m], 75)) * k
        if p75 > HUE_T[name] * 1.05:
            out["hue"][name] = round(float(np.clip(HUE_T[name] / p75 - 1, -0.35, 0)), 3)
    return out


def refine(src, pre, cs):
    """eq=saturation acts weaker than its factor on real images: measure the result once and correct."""
    f = frames(src, ",".join(x for x in (pre, colour_chain(cs)) if x))
    if f is not None:
        mx = f.max(-1)
        got = float(np.percentile(((mx - f.min(-1)) / (mx + 1e-6))[mx > 0.15], 90))
        if got > S90 * 1.03:
            cs["vsat"] = round(float(np.clip(cs["vsat"] * S90 / got, 0.55, 1.0)), 3)
        cs["s90_out"] = round(got, 3)
    return cs


def colour_chain(cs):
    return ",".join([f"eq=saturation={cs['vsat']}"] +
                    [f"huesaturation=saturation={v}:colors={n}" for n, v in cs["hue"].items()])


def base(pr):
    wb = f"colorbalance=rs={pr['wb_r'] * 0.6:.3f}:rm={pr['wb_r']:.3f}:bs={-pr['wb_r'] * 0.6:.3f}:bm={-pr['wb_r']:.3f}" \
         f":gm={pr['wb_g']:.3f}"
    return ",".join([
        wb,
        f"curves=master='{pr['curve']}'",
        f"eq=saturation={pr['sat']}",
        "huesaturation=saturation=-0.08:colors=r+y",
        "huesaturation=saturation=-0.08:colors=c+b",
    ])


FINISH = "unsharp=7:7:-0.30:7:7:0,scale=1920:1080:force_original_aspect_ratio=increase:flags=lanczos,"          "crop=1920:1080,setsar=1,noise=c0s=5:c0f=t"


def frame_count(p):
    return ffprobe(p, "-select_streams", "v:0", "-count_packets", "-show_entries", "stream=nb_read_packets",
                   "-of", "csv=p=0")


def render(src, vf, dst, compare=False, cut=0):
    """cut = leading frames dropped (character sheet); audio is then trimmed by the same time and re-encoded."""
    trim = f"trim=start_frame={cut},setpts=PTS-STARTPTS," if cut else ""
    audio = ["-af", f"atrim=start={float(cut / fps(src)):.4f},asetpts=PTS-STARTPTS", "-c:a", "aac", "-b:a", "192k"] \
        if cut else ["-c:a", "copy"]
    fc = f"[0:v]{trim}split[a][b];[b]{vf}[g];[a]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080[o];" \
         f"[o][g]hstack[v]" if compare else f"[0:v]{trim}{vf}[v]"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-filter_complex", fc, "-map", "[v]",
                        "-map", "0:a?", "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p",
                        *audio, "-map_metadata", "0", "-metadata", f"comment={MARK}",
                        "-movflags", "+faststart", str(dst)], capture_output=True, text=True)
    return r.returncode == 0, r.stderr.strip()[-200:]


def process(src, compare_dir=None):
    try:
        m = mark(src)
        if compare_dir is None and m == MARK:
            return {"file": str(src), "status": "skipped"}
        cut = sheet_frames(src)
        if m == V3:   # graded already: only cut the sheet, never grade twice
            if not cut and compare_dir is None:
                return {"file": str(src), "status": "skipped"}
            f, pr, vf = True, {"base": "v3"}, "null"
        elif m == OLD:   # base grade, softening, 1080p and grain already in the file: colour stage only
            f = frames(src)
            pr = {} if f is None else refine(src, "", {"base": "v2", **colour(f)})
            vf = None if f is None else colour_chain(pr)
        else:
            f = frames(src)
            if f is not None:
                pr = params(f)
                f = frames(src, base(pr))   # measure colour after the base grade, render in one encode
                if f is not None:
                    pr.update(refine(src, base(pr), colour(f)))
                    vf = f"{base(pr)},{colour_chain(pr)},{FINISH}"
        if f is None:
            return {"file": str(src), "status": "failed", "error": "cannot decode"}
        pr["cs"] = cut
        if compare_dir:
            dst = Path(compare_dir) / f"{src.parent.name}_{src.stem}_compare.mp4"
            ok, err = render(src, vf, dst, compare=True, cut=cut)
            return {"file": str(src), "status": "compare" if ok else "failed", "error": err or None, **pr}
        tmp = src.with_name(src.stem + ".processing" + src.suffix)
        ok, err = render(src, vf, tmp, cut=cut)
        if ok and int(frame_count(tmp)) != int(frame_count(src)) - cut:
            ok, err = False, "frame count changed"
        if not ok:
            tmp.unlink(missing_ok=True)
            return {"file": str(src), "status": "failed", "error": err, **pr}
        os.replace(tmp, src)
        return {"file": str(src), "status": "done", **pr}
    except Exception as e:  # one bad clip must not stop the batch
        return {"file": str(src), "status": "failed", "error": repr(e)[-200:]}


def stamp(p):
    s = p.stat()
    return [s.st_size, s.st_mtime_ns]


def targets(args):
    out = []
    for a in args or [str(ROOT)]:
        p = Path(a)
        # user rule 2026-10-11: Z: is READ + COPY only; this script overwrites in place (--compare writes elsewhere)
        assert p.drive.upper() != "Z:" or compare_dir, f"refusing to overwrite on read-only drive Z: {p}"
        out += sorted(x for x in p.rglob("*") if x.suffix.lower() in EXTS and ".processing" not in x.name
                   and not {"_nologo", "_z_nologo"} & set(x.parts)) \
            if p.is_dir() else [p]
    return out


if __name__ == "__main__":
    argv = sys.argv[1:]
    compare_dir = None
    if "--compare" in argv:
        i = argv.index("--compare")
        compare_dir = argv[i + 1]
        Path(compare_dir).mkdir(parents=True, exist_ok=True)
        argv = argv[:i] + argv[i + 2:]
    files = targets(argv)
    for leftover in ROOT.rglob("*.processing.*"):   # from an interrupted run
        try:
            leftover.unlink()
        except PermissionError:   # locked = another run is rendering it right now
            pass
    LOG.parent.mkdir(parents=True, exist_ok=True)
    index = json.loads(INDEX.read_text("utf-8")) if INDEX.exists() else {}
    cached = 0
    if compare_dir is None:
        todo = [f for f in files if index.get(str(f)) != stamp(f)]
        cached, files = len(files) - len(todo), todo
    res = []
    try:
        with ThreadPoolExecutor(JOBS) as pool, open(LOG, "a", encoding="utf-8") as log:
            for r in pool.map(lambda p: process(p, compare_dir), files):
                res.append(r)
                log.write(json.dumps(r, ensure_ascii=False) + "\n")
                log.flush()
                if compare_dir is None and r["status"] in ("done", "skipped") and Path(r["file"]).exists():
                    index[r["file"]] = stamp(Path(r["file"]))
    finally:   # keep what was learned even if the run is interrupted
        if compare_dir is None:
            INDEX.write_text(json.dumps(index, ensure_ascii=False), "utf-8")
    count = {s: sum(1 for r in res if r["status"] == s) for s in ("done", "skipped", "compare", "failed")}
    print(" | ".join(f"{k} {v}" for k, v in count.items() if v) + f" | of {len(res)} | unchanged (index) {cached}")
    strong = [f"{Path(r['file']).parent.name}/{Path(r['file']).name} (wb {r['wb_r']:+.2f})"
              for r in res if r["status"] in ("done", "compare") and abs(r.get("wb_r", 0)) >= 0.08]
    if strong:
        print("STRONG WB SHIFT (check by eye): " + ", ".join(strong[:20]) + (f" ... +{len(strong) - 20}" if len(strong) > 20 else ""))
    cs = [f"{Path(r['file']).parent.name}/{Path(r['file']).name} ({r['cs']}f)"
          for r in res if r["status"] in ("done", "compare") and r.get("cs")]
    if cs:
        print(f"CHARACTER SHEET CUT ({len(cs)}): " + ", ".join(cs[:30]) + (f" ... +{len(cs) - 30}" if len(cs) > 30 else ""))
    for r in res:
        if r["status"] == "failed":
            print(f"FAILED: {r['file']}: {r.get('error')}")
