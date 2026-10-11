#!/usr/bin/env python3
"""Broadcast-logo removal for the clips of a folder, reviewed on timeline "Edit".

scan:    hide_logo.py <folder>      score every video in <folder>, mark its V1 clips (Purple = logo, Yellow = suspect)
execute: hide_logo.py --execute     every marker on a V1 clip -> ffmpeg delogo of that clip's file into
                                    <folder>/_nologo/, ReplaceClip in the media pool, delete the markers.
Detection is self-calibrating and in memory: static edges shared by many files locate the logo, the strongest
files become the template, every file is scored by normalized cross-correlation (NCC) against it."""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from dvr_cowork.resolve_conn import connect  # noqa: E402
from dvr_cowork.config import load_config  # noqa: E402

TIMELINE = "Edit"
CACHE = ROOT / ".work" / "hide_logo" / "scan.json"
EXTS = {".mp4", ".mov", ".mkv", ".mxf", ".avi", ".m4v"}
# every logo-free copy (D: and read-only Z: sources) waits here until the project is Done; scan-source and
# process-ai-video skip it. MANIFEST maps copy -> original for the overwrite question at /doc-edit done.
NOLOGO = Path(load_config()["paths"]["ai_video"]) / "_check" / "_nologo"
MANIFEST = ROOT / ".work" / "hide_logo" / "nologo.json"
OVERWRITTEN = ROOT / ".work" / "hide_logo" / "overwritten.json"  # replaced copies to relink back after a Resolve quit


def manifest():
    return json.loads(MANIFEST.read_text("utf-8")) if MANIFEST.exists() else {}


def record(src, dst):
    m = manifest()
    m[str(dst)] = str(src)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=1, ensure_ascii=False), "utf-8")


def original_of(path):
    """A clip already relinked to its logo-free copy -> the untouched original (always redo from it)."""
    m = {os.path.normcase(k): v for k, v in manifest().items()}
    return m.get(os.path.normcase(str(path)), str(path))
PREFIXES = ("LOGO", "[LOGO-")
W, H, N = 640, 360, 8          # analysis size, frames sampled per file
HI, LO = 0.45, 0.33            # NCC: >= HI logo, LO..HI suspect (vid_3: logos 0.47-0.66, clean <= ~0.35)
SHIFT, PAD = 8, 6              # template search radius, template margin (px at 640x360)
EDGE_PAD = 3                   # extra px around the logo for delogo, at source resolution
FPS_END = 8                    # decode rate for --end (logo that appears late in the clip)
BUSY = 4                     # texture level from which a delogo patch can be noticed -> listed for review


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:format=duration", "-of", "json", path], capture_output=True, text=True)
    j = json.loads(out.stdout or "{}")
    s = (j.get("streams") or [{}])[0]
    return s.get("width"), s.get("height"), float(j.get("format", {}).get("duration") or 0)


def sample(path):
    """Temporal median + persistent-edge mask of N frames spread over the whole file."""
    _, _, dur = probe(path)
    fr = []
    for k in range(N):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{dur * (k + 0.5) / N:.3f}", "-i", path, "-frames:v", "1",
                              "-vf", f"scale={W}:{H}", "-pix_fmt", "gray", "-f", "rawvideo", "-"],
                             capture_output=True).stdout
        if len(raw) >= W * H:
            fr.append(np.frombuffer(raw[:W * H], np.uint8).reshape(H, W).astype(np.float32))
    if len(fr) < 3:
        return None, None
    f = np.stack(fr)
    g = np.abs(np.diff(f, axis=2))[:, :-1, :] + np.abs(np.diff(f, axis=1))[:, :, :-1]
    return np.median(f, axis=0), (g.min(axis=0) > 20) & (f.std(axis=0)[:-1, :-1] < 6)


def grad(m):
    return np.hypot(np.diff(m, axis=1)[:-1], np.diff(m, axis=0)[:, :-1])


def ncc(a, b):
    a, b = a - a.mean(), b - b.mean()
    return float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-6))


def best_match(g, tpl, x0, y0):
    th, tw = tpl.shape
    best = (-1.0, x0, y0)
    for y in range(max(0, y0 - SHIFT), min(g.shape[0] - th, y0 + SHIFT) + 1):
        for x in range(max(0, x0 - SHIFT), min(g.shape[1] - tw, x0 + SHIFT) + 1):
            best = max(best, (ncc(g[y:y + th, x:x + tw], tpl), x, y))
    return best


def logo_box(g, x, y, w, h):
    """Logo rect inside the matched window, widened to the right while a text tail continues
    (e.g. 'BBC' -> 'BBC EARTH'). Returns (x0, y0, x1, y1) at 640x360."""
    lx0, ly0, lx1, ly1 = x + PAD, y + PAD, x + w - PAD, y + h - PAD
    inside = g[ly0:ly1, lx0:lx1].mean(axis=0)
    ref = float(np.median(g[ly0:ly1, lx1:min(W - 1, lx1 + 2 * (lx1 - lx0))]))   # background level beside the logo
    if inside.mean() > 3 * ref:
        limit, gap, x_end = min(W - 2, lx1 + int(1.3 * (lx1 - lx0))), 0, lx1
        for cx in range(lx1, limit):
            if g[ly0:ly1, cx].mean() > max(2 * ref, 0.35 * inside.mean()):
                x_end, gap = cx + 1, 0
            else:
                gap += 1
                if gap > 10:   # space wider than a letter gap: tail has ended
                    break
        lx1 = x_end
    return lx0, ly0, lx1, ly1


def scan(folder):
    files = sorted(str(p) for p in Path(folder).iterdir() if p.suffix.lower() in EXTS and p.is_file())
    if not files:
        sys.exit(f"No video files in {folder}")
    with ThreadPoolExecutor(8) as pool:
        res = list(pool.map(sample, files))
    ok = [(f, med, per) for f, (med, per) in zip(files, res) if med is not None]
    acc = sum(per.astype(np.int32) for _, _, per in ok)
    ys, xs = np.nonzero(acc >= max(3, acc.max() * 0.3))
    if len(xs) < 20:
        sys.exit(f"{len(ok)} files scanned | no recurring logo found")
    x0, x1 = max(0, xs.min() - PAD), min(W - 1, xs.max() + 1 + PAD)
    y0, y1 = max(0, ys.min() - PAD), min(H - 1, ys.max() + 1 + PAD)
    grads = [grad(med) for _, med, _ in ok]
    top = np.argsort([per[y0:y1, x0:x1].sum() for _, _, per in ok])[::-1][:7]
    tpl = np.mean([grads[i][y0:y1, x0:x1] for i in top], axis=0)

    files_out = {}
    for (f, _, _), g in zip(ok, grads):
        s, x, y = best_match(g, tpl, x0, y0)
        bx = logo_box(g, x, y, x1 - x0, y1 - y0)
        files_out[os.path.normcase(f)] = {"score": round(s, 3), "box": [v / (W if i % 2 == 0 else H) for i, v in enumerate(bx)]}
    default = [(x0 + PAD) / W, (y0 + PAD) / H, (x1 - PAD) / W, (y1 - PAD) / H]
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps({"folder": str(Path(folder).resolve()), "default_box": default, "files": files_out}))

    hit = sorted(Path(f).name for f, v in files_out.items() if v["score"] >= HI)
    sus = sorted((Path(f).name, v["score"]) for f, v in files_out.items() if LO <= v["score"] < HI)
    marked = mark(files_out)
    side = ("top" if y0 < H / 2 else "bottom") + "-" + ("left" if x0 < W / 2 else "right")
    print(f"{len(ok)} files scanned | logo at {side} | {len(hit)} with logo, {len(sus)} suspect | "
          f"{marked} markers on '{TIMELINE}' (Purple = logo, Yellow = suspect)")
    print("LOGO: " + ", ".join(n.rsplit(".", 1)[0] for n in hit))
    print("SUSPECT: " + (", ".join(f"{n.rsplit('.', 1)[0]}({s:.2f})" for n, s in sus) or "none"))


def edit_timeline():
    project = connect().GetProjectManager().GetCurrentProject()
    tl = next((t for t in (project.GetTimelineByIndex(i) for i in range(1, project.GetTimelineCount() + 1))
               if t.GetName() == TIMELINE), None)
    if not tl:
        sys.exit(f"Timeline '{TIMELINE}' not found")
    project.SetCurrentTimeline(tl)
    return project, tl


def clip_path(it):
    mpi = it.GetMediaPoolItem()
    return os.path.normcase(mpi.GetClipProperty("File Path") or "") if mpi else ""


def mark(files_out):
    _, tl = edit_timeline()
    base = tl.GetStartFrame()
    for f, m in tl.GetMarkers().items():
        if m["name"].startswith(PREFIXES):
            tl.DeleteMarkerAtFrame(f)
    n = 0
    for it in tl.GetItemListInTrack("video", 1):
        v = files_out.get(clip_path(it))
        if not v or v["score"] < LO:
            continue
        sure = v["score"] >= HI
        if tl.AddMarker(int(it.GetStart()) - base, "Purple" if sure else "Yellow",
                        f"{'LOGO' if sure else 'LOGO?'}: {it.GetName()}", f"logo match {v['score']:.2f}",
                        int(it.GetDuration()), "logo"):
            n += 1
    return n


def delogo(src, box, start=0.0, end=None):
    w, h, _ = probe(src)
    x0, y0 = max(1, int(box[0] * w) - EDGE_PAD), max(1, int(box[1] * h) - EDGE_PAD)
    x1, y1 = min(w - 2, int(np.ceil(box[2] * w)) + EDGE_PAD), min(h - 2, int(np.ceil(box[3] * h)) + EDGE_PAD)
    x0, y0 = x0 + x0 % 2, y0 + y0 % 2                          # yuv420 crops snap to even values
    bw, bh = (x1 - x0) // 2 * 2 + 2, (y1 - y0) // 2 * 2 + 2
    bw, bh = min(bw, (w - 2 - x0) // 2 * 2), min(bh, (h - 2 - y0) // 2 * 2)
    # delogo leaves a smooth patch; re-grain it with the texture level of the band right below the logo
    _, _, dur = probe(src)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{dur / 2:.3f}", "-i", src, "-frames:v", "1", "-vf",
                          f"crop={bw}:{bh}:{x0}:{min(h - bh, y1 + 2)}", "-pix_fmt", "gray", "-f", "rawvideo", "-"],
                         capture_output=True).stdout
    grain = 0
    if len(raw) >= bw * bh:
        a = np.frombuffer(raw[:bw * bh], np.uint8).reshape(bh, bw).astype(np.float32)
        hf = a[1:-1, 1:-1] - (a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:]) / 4
        grain = int(np.clip(hf.std() * 2.0, 0, 15))
    en = (f":enable='between(t,{start:.3f},{end:.3f})'" if end is not None
          else f":enable='gte(t,{start:.3f})'" if start > 0 else "")
    vf = f"[0:v]delogo=x={x0}:y={y0}:w={bw}:h={bh}{en}"
    if grain >= 2:
        vf += f",split[a][b];[b]crop={bw}:{bh}:{x0}:{y0},noise=alls={grain}:allf=t[n];[a][n]overlay={x0}:{y0}{en}"
    # one flat folder on D: (Z: is READ + COPY only); a name already used by another original gets its folder name
    dst = NOLOGO / Path(src).name
    if os.path.normcase(manifest().get(str(dst), src)) != os.path.normcase(src):
        dst = NOLOGO / f"{Path(src).stem}__{Path(src).parent.name}{Path(src).suffix}"
    assert dst.drive.upper() != "Z:", dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-filter_complex", vf + "[v]", "-map", "[v]",
                        "-map", "0:a?", "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p",
                        "-fps_mode", "passthrough", "-c:a", "copy", "-map_metadata", "0", "-movflags", "+faststart",
                        str(dst)], capture_output=True, text=True)
    if r.returncode:
        return src, None, r.stderr.strip()[-200:], grain
    count = lambda p: subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                                      "stream=nb_read_packets", "-of", "csv=p=0", p], capture_output=True, text=True).stdout.strip()
    if count(src) != count(str(dst)):
        return src, None, "frame count changed", grain
    return src, str(dst), None, grain


def execute():
    if not CACHE.exists():
        sys.exit("No scan found. Run the scan on the folder first.")
    cache = json.loads(CACHE.read_text())
    _, tl = edit_timeline()
    base = tl.GetStartFrame()
    items = tl.GetItemListInTrack("video", 1)
    todo, used = {}, []
    for f, m in tl.GetMarkers().items():
        it = next((i for i in items if int(i.GetStart()) - base <= f < int(i.GetEnd()) - base), None)
        if it is None or not clip_path(it):
            continue
        used.append(f)
        todo.setdefault(os.path.normcase(original_of(clip_path(it))), it.GetMediaPoolItem())
    if not todo:
        sys.exit("No markers on V1 clips.")
    jobs = [(p, cache["files"].get(p, {}).get("box", cache["default_box"])) for p in todo]
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda j: delogo(*j), jobs))
    done, failed, busy = 0, [], []
    for src, dst, err, grain in results:
        if dst and todo[src].ReplaceClip(dst):
            done += 1
            record(src, dst)
            if grain >= BUSY:
                busy.append(Path(src).stem)
        else:
            failed.append(f"{Path(src).name}: {err or 'ReplaceClip failed'}")
    if not failed:
        for f in used:
            tl.DeleteMarkerAtFrame(f)
    print(f"delogo {done}/{len(todo)} clips -> {NOLOGO}, media pool relinked | "
          + ("markers deleted" if not failed else "markers kept (failures): " + "; ".join(failed)))
    print("REVIEW FIRST (detailed background, patch may show): " + (", ".join(sorted(busy)) or "none"))


def _run(idx, gap):
    """Longest run in sorted indices allowing holes up to `gap` (letter spacing) -> (first, last)."""
    if len(idx) == 0:
        return 0, 0
    runs, s = [], idx[0]
    for a, b in zip(idx, idx[1:]):
        if b - a > gap:
            runs.append((s, a)); s = b
    runs.append((s, idx[-1]))
    return max(runs, key=lambda r: r[1] - r[0])


def late_logo(src, quads, h2, w2, head=False):
    """Logo that pops in late and stays: its pixels all stop changing at the same frame, packed in one small
    window, while the background settles at scattered times. Returns (corner, box@640x360, start_s) or None."""
    from numpy.lib.stride_tricks import sliding_window_view
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-vf", f"fps={FPS_END},scale={W}:{H}",
                          "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    f = np.frombuffer(raw, np.uint8)[:len(raw) // (W * H) * W * H].reshape(-1, H, W).astype(np.float32)
    if len(f) < 16:
        return None
    if head:   # logo shown from the start, gone later = a late logo in the reversed clip
        f = f[::-1].copy()
    best = None
    for corner, (oy, ox) in quads.items():
        c = f[:, oy:oy + h2, ox:ox + w2]
        dev = np.abs(c - c[-1]) > 10
        fs = np.where(dev.any(0), len(c) - np.argmax(dev[::-1], axis=0), 0)   # frame from which pixel = end look
        for t in range(3, int(np.median(fs)) - 4):
            # settled at t AND changed abruptly around t: a logo pops in, background settles gradually
            m = ((np.abs(fs - t) <= 1) & (np.abs(c[min(t + 1, len(c) - 1)] - c[t - 3]) > 25)).astype(np.float32)
            if m.sum() < 30:
                continue
            d = sliding_window_view(m, (24, 64)).sum(axis=(2, 3))
            share = d.max() / m.sum()    # logo ~0.7, scattered background ~0.1
            if share > 0.4 and (best is None or share > best[0]):
                # tight box: longest run of dense rows, then dense columns inside it (stray pixels make delogo streak)
                r0, r1 = _run(np.nonzero(m.sum(1) >= 3)[0], 2)
                c0, c1 = _run(np.nonzero(m[r0:r1 + 1].sum(0) >= 2)[0], 8)
                bx = (ox + c0 - 2, oy + r0 - 2, ox + c1 + 3, oy + r1 + 3)
                tt = (len(f) - t + 2) / FPS_END if head else max(0.0, (t - 2) / FPS_END)
                best = (share, corner, bx, tt)
    return best   # (share, corner, box@640x360, start_s | end_s when head) or None


def one_clip(name, corner=None, endpart=False, head=False):
    """One shot name or video path: find its static logo in a corner (persistent edges over 8 frames), delogo,
    relink the V1 clip using it (if any). endpart=True: logo appears late in the clip; head=True: logo only at
    the start of the clip, gone later."""
    _, tl = edit_timeline()
    items = tl.GetItemListInTrack("video", 1)
    if Path(name).is_file():
        src = str(Path(name).resolve())
        it = next((i for i in items if os.path.normcase(original_of(clip_path(i))) == os.path.normcase(src)), None)
    else:
        it = next((i for i in items if Path(name).stem.lower() in i.GetName().lower()), None)
        if it is None:
            sys.exit(f"'{name}' is not a file and not on V1 of '{TIMELINE}'")
        src = it.GetMediaPoolItem().GetClipProperty("File Path")
    mpi = it.GetMediaPoolItem() if it else None
    src = original_of(src)   # clip already relinked: always redo from the untouched original
    h2, w2 = H // 2, W // 2
    quads = {"tl": (0, 0), "tr": (0, w2), "bl": (h2, 0), "br": (h2, w2)}
    start, end = 0.0, None
    if endpart or head:
        bh, bw = H // 5, W * 3 // 10    # channel logos hug the frame edge: search a corner band, not a quadrant
        bands = {"tl": (0, 0), "tr": (0, W - bw), "bl": (H - bh, 0), "br": (H - bh, W - bw)}
        found = late_logo(src, {c: bands[c] for c in ([corner] if corner else bands)}, bh, bw, head)
        if not found:
            sys.exit(f"no logo {'leaving' if head else 'appearing late'} found in corner {corner or 'any'}")
        _, corner, bx, t = found
        start, end = (0.0, t) if head else (t, None)
    else:
        _, per = sample(src)
        if per is None:
            sys.exit("could not decode " + src)
        corner = corner or max(quads, key=lambda c: per[quads[c][0]:quads[c][0] + h2, quads[c][1]:quads[c][1] + w2].sum())
        oy, ox = quads[corner]
        ys, xs = np.nonzero(per[oy:oy + h2, ox:ox + w2])
        if len(xs) < 20:
            sys.exit(f"no static logo found in corner {corner}")
        k = (abs(xs - np.median(xs)) < 80) & (abs(ys - np.median(ys)) < 40)   # densest cluster, drops stray edges
        bx = (ox + xs[k].min() - 2, oy + ys[k].min() - 2, ox + xs[k].max() + 3, oy + ys[k].max() + 3)
    box = [bx[0] / W, bx[1] / H, bx[2] / W, bx[3] / H]
    _, dst, err, grain = delogo(src, box, start, end)
    if not dst or (mpi and not mpi.ReplaceClip(dst)):
        sys.exit(f"failed: {err or 'ReplaceClip failed'}")
    record(src, dst)
    when = f"0.0-{end:.1f}s" if end is not None else f"from {start:.1f}s"
    print(f"{Path(src).stem}: logo {corner} {[int(v) for v in bx]}@640x360 {when} removed -> {dst} | "
          + ("relinked" if mpi else "not on V1, file only") + f" | grain {grain}"
          + (" REVIEW (detailed background)" if grain >= BUSY else ""))


def at_clip(tc, corner=None):
    """Timeline position the user saw the logo at (mm:ss or hh:mm:ss) -> the V1 clip there, or a neighbour within
    1 s (a reported time often lands just before the cut), whichever shows the most static edges in the corner."""
    project, tl = edit_timeline()
    fps, t0 = float(tl.GetSetting("timelineFrameRate")), int(tl.GetStartFrame())
    sec = sum(float(v) * 60 ** i for i, v in enumerate(reversed(tc.split(":"))))
    fr, pad = t0 + round(sec * fps), round(fps)
    h2, w2 = H // 2, W // 2
    quads = {"tl": (0, 0), "tr": (0, w2), "bl": (h2, 0), "br": (h2, w2)}
    best, srcs = None, []
    for it in tl.GetItemListInTrack("video", 1):
        if not (it.GetStart() <= fr + pad and it.GetEnd() > fr - pad) or not it.GetMediaPoolItem():
            continue
        src = it.GetMediaPoolItem().GetClipProperty("File Path")
        src = original_of(src)
        _, per = sample(src)
        if per is None:
            continue
        score = max(int(np.count_nonzero(per[y:y + h2, x:x + w2])) for c, (y, x) in quads.items() if c in (corner or quads))
        span = f"{(it.GetStart() - t0) / fps:.1f}-{(it.GetEnd() - t0) / fps:.1f}s"
        print(f"  candidate {span} {Path(src).name}: static edges {score}")
        if best is None or score > best[0]:
            best = (score, src)
        srcs.append(src)
    if best and best[0] >= 20:
        return one_clip(best[1], corner)
    # no logo through the whole clip: one shown only at the start (head) or popping in late (end)
    bh, bw = H // 5, W * 3 // 10
    bands = {"tl": (0, 0), "tr": (0, W - bw), "bl": (H - bh, 0), "br": (H - bh, W - bw)}
    part = None
    for src in srcs:
        for head in (True, False):
            f = late_logo(src, {c: bands[c] for c in ([corner] if corner else bands)}, bh, bw, head)
            print(f"  {Path(src).name} {'start' if head else 'late'}: " + (f"share {f[0]:.2f}" if f else "none"))
            if f and (part is None or f[0] > part[0]):
                part = (f[0], src, head)
    if not part:
        sys.exit(f"no logo found near {tc}")
    one_clip(part[1], corner, endpart=not part[2], head=part[2])


def frame_info(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                        "stream=nb_read_packets,width,height", "-of", "json", str(p)], capture_output=True, text=True)
    return json.loads(r.stdout)["streams"][0]


def _relink(project, names, target):
    """Media pool items whose file name is one of `names` -> `target` (all bins of the project)."""
    def walk(f):
        yield from f.GetClipList() or []
        for s in f.GetSubFolderList() or []:
            yield from walk(s)
    hits = [c for c in walk(project.GetMediaPool().GetRootFolder())
            if Path(c.GetClipProperty("File Path") or "").name in names
            and os.path.normcase(c.GetClipProperty("File Path")) != os.path.normcase(str(target))]
    return sum(bool(c.ReplaceClip(str(target))) for c in hits)


def _move_id(ss, orig, old_id):
    """Tags (library index), YOLO cache and clip ledger follow the file to its new content hash."""
    new_id, moved = ss.fast_hash(orig), []
    for key, (root, kind, _) in ss.ROOTS.items():
        p = ss.index_of(root)
        if root.drive.upper() == orig.drive.upper() and p.exists():
            idx = json.loads(p.read_text("utf-8"))
            if old_id in idx["clips"]:
                idx["clips"][new_id] = idx["clips"].pop(old_id)
                ss.save(root, kind, idx)
                moved.append(key + " index")
    p = ROOT / ".work" / "library" / "yolo.json"
    if p.exists():
        cache = json.loads(p.read_text("utf-8"))
        if old_id in cache:
            cache[new_id] = cache.pop(old_id)
            p.write_text(json.dumps(cache, separators=(",", ":")), "utf-8")
            moved.append("yolo cache")
    led = ROOT / ".work" / "doc_edit" / "recent_clips.json"
    if led.exists() and old_id in led.read_text("utf-8"):
        led.write_text(led.read_text("utf-8").replace(old_id, new_id), "utf-8")
        moved.append("clip ledger")
    return f"id {old_id} -> {new_id} ({', '.join(moved) or 'not indexed'})"


def pending():
    """Logo-free copies waiting for the overwrite question at /doc-edit done."""
    m = manifest()
    for clean, orig in m.items():
        z = " (Z: read-only, copy stays)" if Path(orig).drive.upper() == "Z:" else ""
        print(f"  {Path(orig).name}{z}" + ("" if Path(clean).exists() else "  MISSING copy " + clean))
    print(f"{len(m)} logo-free copies in {NOLOGO}")


def relink_pending():
    """Open project: items on an original -> its logo-free copy (pending), items on a replaced copy -> the
    original again (after an overwrite that had to quit Resolve)."""
    project = connect().GetProjectManager().GetCurrentProject()
    m, back = manifest(), (json.loads(OVERWRITTEN.read_text("utf-8")) if OVERWRITTEN.exists() else {})
    n = sum(_relink(project, {Path(c).name, Path(o).name}, c) for c, o in m.items() if Path(c).exists())
    k = sum(_relink(project, {Path(c).name, Path(o).name}, o) for c, o in back.items() if Path(o).exists())
    OVERWRITTEN.unlink(missing_ok=True)
    print(f"relinked {n} item(s) to {len(m)} logo-free copies, {k} item(s) back to {len(back)} overwritten originals")


def _replace_all(jobs):
    import time
    done, locked = [], []
    for c, o, old_id in jobs:
        for _ in range(10):  # Resolve releases the media handles a moment after the close
            try:
                c.replace(o)
                done.append((c, o, old_id))
                break
            except PermissionError:
                time.sleep(1)
        else:
            locked.append((c, o, old_id))
    return done, locked


def overwrite_all():
    """User said yes at /doc-edit done (video already exported): each copy in NOLOGO replaces its original (Z:
    originals stay, read-only), Resolve is relinked to the original paths, tags / YOLO cache / ledger move to the
    new content hash. Resolve keeps the files open (Windows refuses the replace): the project is saved and closed
    around the replaces and reopened on the same timeline; if a file is still locked Resolve is quit, the rest is
    replaced, and --relink (after the user reopens the project) points the items back at the originals."""
    import time
    sys.path.insert(0, str(ROOT / ".claude" / "skills" / "scan-source" / "scripts"))
    import scan_source as ss
    m = manifest()
    jobs, kept, bad = [], [], []
    for clean, orig in m.items():
        c, o = Path(clean), Path(orig)
        if o.drive.upper() == "Z:":
            kept.append(o.name)
        elif not (c.is_file() and o.is_file()) or frame_info(c) != frame_info(o):
            bad.append(f"{o.name}: missing file or frame count differs")
        else:
            jobs.append((c, o, ss.fast_hash(o)))
    if not jobs:
        sys.exit(f"nothing to overwrite | kept (Z:) {kept} | problems {bad}")
    resolve = connect()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    name, cur = project.GetName(), (project.GetCurrentTimeline() or project.GetTimelineByIndex(1)).GetName()
    assert pm.SaveProject(), "project not saved - nothing changed"
    assert pm.CloseProject(project), "could not close the project - nothing changed"
    done, locked = _replace_all(jobs)
    quit_ = bool(locked)
    if quit_:  # closing the project did not release every file: quit Resolve and try again
        resolve.Quit()
        for _ in range(60):
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Resolve.exe"], capture_output=True, text=True).stdout
            if "Resolve.exe" not in out:
                break
            time.sleep(1)
        more, locked = _replace_all(locked)
        done += more
    for c, o, old_id in done:   # bookkeeping first: the files are already replaced
        print(f"  {o.name}: {_move_id(ss, o, old_id)}")
        m.pop(str(c), None)
    MANIFEST.write_text(json.dumps(m, indent=1, ensure_ascii=False), "utf-8")
    back = {str(c): str(o) for c, o, _ in done}
    tail = f" | kept (Z: read-only) {len(kept)} | still locked {[o.name for _, o, _ in locked]} | problems {bad}"
    if quit_:
        OVERWRITTEN.write_text(json.dumps(back, indent=1, ensure_ascii=False), "utf-8")
        print(f"overwritten {len(done)}/{len(jobs)} originals | Resolve was quit to free the files: reopen project "
              f"'{name}', then run --relink" + tail)
        return
    project = pm.LoadProject(name)
    if not project:
        OVERWRITTEN.write_text(json.dumps(back, indent=1, ensure_ascii=False), "utf-8")
        sys.exit(f"overwritten {len(done)} originals; reopen project '{name}' by hand, then run --relink")
    tl = next((t for t in (project.GetTimelineByIndex(i) for i in range(1, project.GetTimelineCount() + 1))
               if t.GetName() == cur), None)
    if tl:
        project.SetCurrentTimeline(tl)
    n = sum(_relink(project, {c.name, o.name}, o) for c, o, _ in done)
    print(f"overwritten {len(done)}/{len(jobs)} originals | relinked {n} media pool item(s) | "
          f"project '{name}' reopened on '{cur}'" + tail)


if __name__ == "__main__":
    if "--execute" in sys.argv:
        execute()
    elif "--at" in sys.argv:   # --at 21:38 tl 05:12 tr 07:40   (corner optional after each time)
        jobs = []
        for a in sys.argv[sys.argv.index("--at") + 1:]:
            if a in ("tl", "tr", "bl", "br") and jobs:
                jobs[-1][1] = a
            else:
                jobs.append([a, None])
        for tc, corner in jobs:
            print(f"{tc} {corner or 'any corner'}:")
            try:
                at_clip(tc, corner)
            except SystemExit as e:   # one shot failing must not stop the others
                print(f"  FAILED: {e}")
    elif "--pending" in sys.argv:
        pending()
    elif "--overwrite-all" in sys.argv:
        overwrite_all()
    elif "--relink" in sys.argv:
        relink_pending()
    elif len(sys.argv) > 1 and Path(sys.argv[1]).is_dir():
        scan(sys.argv[1])
    elif len(sys.argv) > 1:
        endpart = "--end" in sys.argv
        args = [a for a in sys.argv[1:] if a != "--end"]
        one_clip(args[0], args[1] if len(args) > 1 else None, endpart)
    else:
        sys.exit("usage: hide_logo.py <folder> | --execute | <shot_NNN|video path> [tl|tr|bl|br] [--end] | --at <mm:ss> [corner] | --pending | --overwrite-all | --relink")
