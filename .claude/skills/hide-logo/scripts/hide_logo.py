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
# process-ai-video skip it. MANIFEST maps copy -> original for the overwrite question when the video is finished.
NOLOGO = Path(load_config()["paths"]["ai_video"]) / "_nologo"  # was _check/_nologo until 2026-10-13
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
MINIMAX_PY = Path(r"D:\tools\minimax_remover\venv\Scripts\python.exe")   # MiniMax-Remover venv (minimax_worker.py)
FEATHER, SOFT = 12, 1.5        # clone-patch edge fade (px) and blur sigma: raise SOFT if the patch still looks glossy
HAZE = 9                      # blur sigma of the soft haze over patch + margin: raise if seams show, lower if it smears
FPS_END = 8                   # decode rate for --end (logo that appears late in the clip)
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
    grab = lambda k: subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{dur * (k + 0.5) / N:.3f}", "-i", path, "-frames:v", "1",
                                     "-vf", f"scale={W}:{H}", "-pix_fmt", "gray", "-f", "rawvideo", "-"],
                                    capture_output=True).stdout
    with ThreadPoolExecutor(N) as pool:   # the N seeks in parallel (~2.4 s -> ~0.5 s)
        raws = list(pool.map(grab, range(N)))
    fr = [np.frombuffer(raw[:W * H], np.uint8).reshape(H, W).astype(np.float32) for raw in raws if len(raw) >= W * H]
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
    res = [sample(f) for f in files]   # sample() already runs its N seeks in parallel
    ok =[(f, med, per) for f, (med, per) in zip(files, res) if med is not None]
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


def nologo_path(src):
    """One flat folder on D: (Z: is READ + COPY only); a name already used by another original gets its folder name."""
    dst = NOLOGO / Path(src).name
    if os.path.normcase(manifest().get(str(dst), src)) != os.path.normcase(src):
        dst = NOLOGO / f"{Path(src).stem}__{Path(src).parent.name}{Path(src).suffix}"
    assert dst.drive.upper() != "Z:", dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    return dst


def frames(p):
    return subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                           "stream=nb_read_packets", "-of", "csv=p=0", p], capture_output=True, text=True).stdout.strip()


def delogo(src, box, start=0.0, end=None, side=False, fill="minimax"):
    """fill="minimax" (default, user 2026-10-15: clone patch blurred / glowed): MiniMax-Remover video inpainting of a
    crop around the logo, minimax_worker.py in its own venv. "clone" / "interp": the older ffmpeg patches below.
    side=True: clone from the same rows beside the logo (inward), not above/below - over moving water the
    vertical neighbour is foam/sky of another brightness and the patch glows (user 2026-10-14)."""
    w, h, dur = probe(src)
    if fill == "minimax":
        dst = nologo_path(src)
        bxs = [f"{max(0, int(b[0] * w) - EDGE_PAD)},{max(0, int(b[1] * h) - EDGE_PAD)},"
               f"{min(w, int(np.ceil(b[2] * w)) + EDGE_PAD)},{min(h, int(np.ceil(b[3] * h)) + EDGE_PAD)}"
               for b in (box if isinstance(box[0], (list, tuple)) else [box])]
        r = subprocess.run([str(MINIMAX_PY), str(Path(__file__).with_name("minimax_worker.py")), src, str(dst),
                            f"{start:.3f}", f"{-1 if end is None else end:.3f}", *bxs], capture_output=True, text=True)
        if r.returncode:
            return src, None, (r.stderr.strip() or r.stdout.strip())[-200:], 0
        if frames(src) != frames(str(dst)):
            return src, None, "frame count changed", 0
        return src, str(dst), None, 0
    en = (f":enable='between(t,{start:.3f},{end:.3f})'" if end is not None
          else f":enable='gte(t,{start:.3f})'" if start > 0 else "")
    chain, cur, grain = [], "0:v", 0
    for i, bb in enumerate(box if isinstance(box[0], (list, tuple)) else [box]):   # several logos: one patch each
        x0, y0 = max(1, int(bb[0] * w) - EDGE_PAD), max(1, int(bb[1] * h) - EDGE_PAD)
        x1, y1 = min(w - 2, int(np.ceil(bb[2] * w)) + EDGE_PAD), min(h - 2, int(np.ceil(bb[3] * h)) + EDGE_PAD)
        x0, y0 = x0 + x0 % 2, y0 + y0 % 2                          # yuv420 crops snap to even values
        bw, bh = (x1 - x0) // 2 * 2 + 2, (y1 - y0) // 2 * 2 + 2
        bw, bh = min(bw, (w - 2 - x0) // 2 * 2), min(bh, (h - 2 - y0) // 2 * 2)
        # Clone patch (user pick 2026-10-13, over plain delogo): copy the real texture right below the logo (above it
        # when the logo sits at the bottom), feathered edge, slightly blurred (SOFT) so it is not glossy, + grain.
        px, py = max(0, x0 - FEATHER), max(0, y0 - FEATHER)
        pw, ph = min(w - px, bw + 2 * FEATHER) // 2 * 2, min(h - py, bh + 2 * FEATHER) // 2 * 2
        sy = py + ph + 2 if py + 2 * ph + 2 <= h else py - ph - 2
        sy = max(0, min(sy, h - ph))
        sx = px
        if side:
            sx, sy = (px - pw - 2 if px > w / 2 else px + pw + 2), py
            sx = max(0, min(sx, w - pw))
        # delogo leaves a smooth patch; re-grain it with the texture level of the clone source (not a letterbox bar)
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{dur / 2:.3f}", "-i", src, "-frames:v", "1", "-vf",
                              f"crop={bw}:{bh}:{max(0, min(w - bw, sx + FEATHER))}:{max(0, min(h - bh, sy + FEATHER))}", "-pix_fmt", "gray", "-f", "rawvideo", "-"],
                             capture_output=True).stdout
        g, shift = 0, 0
        if len(raw) >= bw * bh:
            a = np.frombuffer(raw[:bw * bh], np.uint8).reshape(bh, bw).astype(np.float32)
            hf = a[1:-1, 1:-1] - (a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:]) / 4
            g = int(np.clip(hf.std() * 2.0, 0, 15))
            grain = max(grain, g)
            # brightness match (user 2026-10-14: patch "bóng lên" = brighter than its surroundings): shift the patch
            # luma to the band left of the logo, same rows (logos sit at the right edge)
            lx = max(0, x0 - bw - FEATHER)
            ref = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{dur / 2:.3f}", "-i", src, "-frames:v", "1", "-vf",
                                  f"crop={bw}:{bh}:{lx}:{y0}", "-pix_fmt", "gray", "-f", "rawvideo", "-"],
                                 capture_output=True).stdout
            if len(ref) >= bw * bh:
                shift = int(np.clip(np.frombuffer(ref[:bw * bh], np.uint8).mean() - a.mean(), -40, 40))
        if fill == "interp":   # big logo over a fast pan: any copied block shows; interpolate from all 4 edges
            chain.append(f"[{cur}]delogo=x={x0}:y={y0}:w={bw}:h={bh}{en}[m{i}]")
        else:
            chain.append(f"[{cur}]split[a{i}][b{i}];[b{i}]crop={pw}:{ph}:{sx}:{sy},lutyuv=y='clip(val+{shift},16,235)',"
                         f"gblur=sigma={SOFT},noise=c0s={max(g, 3)}:allf=t,"
                         f"format=yuva420p,geq=lum='lum(X,Y)':cb='cb(X,Y)':cr='cr(X,Y)':"
                         f"a='255*min(1,min(X,W-1-X)/{FEATHER})*min(1,min(Y,H-1-Y)/{FEATHER})'[p{i}];"
                         f"[a{i}][p{i}]overlay={px}:{py}:format=auto{en}[m{i}]")
        # Haze pass (user 2026-10-14: patch edges + brightness step showed): blur the patched area plus a FEATHER
        # margin, faded over 2*FEATHER, so seams and the brightness step melt into the surroundings. No fade on a
        # side that touches the frame edge (a fade there leaves a sharp line along the edge).
        qx, qy = max(0, px - FEATHER), max(0, py - FEATHER)
        qw, qh = min(w - qx, pw + 2 * FEATHER) // 2 * 2, min(h - qy, ph + 2 * FEATHER) // 2 * 2
        f2 = 2 * FEATHER
        fx = [f"min(1,X/{f2})" if qx > 0 else "1", f"min(1,(W-1-X)/{f2})" if qx + qw < w - 2 else "1"]
        fy = [f"min(1,Y/{f2})" if qy > 0 else "1", f"min(1,(H-1-Y)/{f2})" if qy + qh < h - 2 else "1"]
        chain.append(f"[m{i}]split[c{i}][d{i}];[d{i}]crop={qw}:{qh}:{qx}:{qy},gblur=sigma={HAZE},"
                     f"noise=c0s={max(g // 2, 2)}:allf=t,format=yuva420p,geq=lum='lum(X,Y)':cb='cb(X,Y)':cr='cr(X,Y)':"
                     f"a='255*{'*'.join(fx + fy)}'[q{i}];"
                     f"[c{i}][q{i}]overlay={qx}:{qy}:format=auto{en}[o{i}]")
        cur = f"o{i}"
    vf = ";".join(chain)
    dst = nologo_path(src)
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-filter_complex", vf, "-map", f"[{cur}]",
                        "-map", "0:a?", "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p",
                        "-fps_mode", "passthrough", "-c:a", "copy", "-map_metadata", "0", "-movflags", "+faststart",
                        str(dst)], capture_output=True, text=True)
    if r.returncode:
        return src, None, r.stderr.strip()[-200:], grain
    if frames(src) != frames(str(dst)):
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
    results = [delogo(*j) for j in jobs]   # one at a time: MiniMax needs the whole GPU
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
                if r1 - r0 < 3 or c1 - c0 < 6:   # no dense rows/columns = empty box at the corner, not a logo
                    continue
                bx =(ox + c0 - 2, oy + r0 - 2, ox + c1 + 3, oy + r1 + 3)
                tt = (len(f) - t + 2) / FPS_END if head else max(0.0, (t - 2) / FPS_END)
                best = (share, corner, bx, tt)
    return best   # (share, corner, box@640x360, start_s | end_s when head) or None


def static_edges(src, bx, t0, t1):
    """Pixels of box bx (640x360) that are an edge in every frame of [t0, t1] and do not change (sample()'s test)."""
    x0, y0, x1, y1 = (int(v) for v in bx)
    x0, y0 = max(x0, 0), max(y0, 0)
    span = ["-ss", f"{t0:.3f}"] + (["-to", f"{t1:.3f}"] if t1 is not None else [])
    raw = subprocess.run(["ffmpeg", "-v", "error", *span, "-i", src, "-vf", f"fps={FPS_END},scale={W}:{H}",
                          "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    f = np.frombuffer(raw, np.uint8)[:len(raw) // (W * H) * W * H].reshape(-1, H, W)[:, y0:y1, x0:x1].astype(np.float32)
    if len(f) < 3 or f.shape[1] < 2 or f.shape[2] < 2:
        return 0
    g = np.abs(np.diff(f, axis=2))[:, :-1, :] + np.abs(np.diff(f, axis=1))[:, :, :-1]
    return int(((g.min(axis=0) > 20) & (f.std(axis=0)[:-1, :-1] < 6)).sum())


def part_logo(src, corner, heads):
    """Logo on part of the clip only: head=True shown at the start then gone, False popping in late. Tries each
    mode in `heads`, best share wins -> (corner, box@640x360, start_s, end_s | None) or None."""
    bh, bw = H // 5, W * 3 // 10    # channel logos hug the frame edge: search a corner band, not a quadrant
    bands = {"tl": (0, 0), "tr": (0, W - bw), "bl": (H - bh, 0), "br": (H - bh, W - bw)}
    best = None
    for head in heads:
        f = late_logo(src, {c: bands[c] for c in ([corner] if corner else bands)}, bh, bw, head)
        # late_logo also fires on water / animals moving (2026-10-15, logo-free otter, leaf litter): keep it only if
        # the box holds persistent edges while the logo is supposed to be there, the whole-clip rule of sample()
        # (span pulled 0.5 s inward: late_logo pads the pop-in time, and logo-free frames there break the test)
        if f and static_edges(src, f[2], *((0.0, f[3] - 0.5) if head else (f[3] + 0.5, None))) >= 20 \
                and (best is None or f[0] > best[0][0]):
            best = (f, head)
    if not best:
        return None
    (_, c, bx, t), head = best
    return (c, bx, 0.0, t) if head else (c, bx, t, None)


def one_clip(name, corner=None, endpart=False, head=False, manual=None, fill="minimax"):
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
    if manual:   # --box x0,y0,x1,y1 [x0,y0,x1,y1 ...] at 640x360: semi-transparent logos the edge detector misses
        bx, corner = manual[0], "manual"
    elif endpart or head:
        found = part_logo(src, corner, [head])
        if not found:
            sys.exit(f"no logo {'leaving' if head else 'appearing late'} found in corner {corner or 'any'}")
        corner, bx, start, end = found
    else:
        _, per = sample(src)
        if per is None:
            sys.exit("could not decode " + src)
        want = corner
        corner = corner or max(quads, key=lambda c: per[quads[c][0]:quads[c][0] + h2, quads[c][1]:quads[c][1] + w2].sum())
        oy, ox = quads[corner]
        ys, xs = np.nonzero(per[oy:oy + h2, ox:ox + w2])
        if len(xs) >= 20:
            k = (abs(xs - np.median(xs)) < 80) & (abs(ys - np.median(ys)) < 40)   # densest cluster, drops stray edges
            bx = (ox + xs[k].min() - 2, oy + ys[k].min() - 2, ox + xs[k].max() + 3, oy + ys[k].max() + 3)
        else:   # user gives the corner, not the time (2026-10-15): logo only at the start, or popping in late
            found = part_logo(src, want, [True, False])
            if not found:
                sys.exit(f"no logo found in corner {want or 'any'} (whole clip, start or late)")
            corner, bx, start, end = found
    box = [bx[0] / W, bx[1] / H, bx[2] / W, bx[3] / H]
    if manual:
        box = [[b[0] / W, b[1] / H, b[2] / W, b[3] / H] for b in manual]
    _, dst, err, grain = delogo(src, box, start, end, side=bool(manual), fill=fill)
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
        # a reported time is usually where the shot starts: a clip starting at/after it wins any logo, a neighbour
        # that ended there only if it alone shows one (2026-10-12 shot_068 / landscape were picked by mistake)
        rank = (score >= 20 and it.GetStart() >= fr - pad, score)
        if best is None or rank > best[2]:
            best = (score, src, rank)
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


def _relink(project, paths, target):
    """Media pool items whose FULL path is one of `paths` -> `target` (all bins of the project). Never match by file
    name: shot_NNN.mp4 exists in many folders (2026-10-12 a name match relinked a different clip)."""
    paths = {os.path.normcase(str(x)) for x in paths}
    def walk(f):
        yield from f.GetClipList() or []
        for s in f.GetSubFolderList() or []:
            yield from walk(s)
    hits = [c for c in walk(project.GetMediaPool().GetRootFolder())
            if os.path.normcase(c.GetClipProperty("File Path") or "") in paths
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
    for led in (ROOT / ".work" / "doc_edit" / "ledgers").glob("*.json"):  # one clip ledger per workspace
        if old_id in led.read_text("utf-8"):
            led.write_text(led.read_text("utf-8").replace(old_id, new_id), "utf-8")
            moved.append(f"ledger {led.stem}")
    return f"id {old_id} -> {new_id} ({', '.join(moved) or 'not indexed'})"


def pending():
    """Logo-free copies waiting for the overwrite question when the video is finished."""
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
    n = sum(_relink(project, {c, o}, c) for c, o in m.items() if Path(c).exists())
    k = sum(_relink(project, {c, o}, o) for c, o in back.items() if Path(o).exists())
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
    """User said yes when the video is finished (video already exported): each copy in NOLOGO replaces its original (Z:
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
        # frame count only: a copy later graded by process-ai-video is 1920x1080 on purpose (user 2026-10-14)
        elif not (c.is_file() and o.is_file()) or frame_info(c)["nb_read_packets"] != frame_info(o)["nb_read_packets"]:
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
    n = sum(_relink(project, {c, o}, o) for c, o, _ in done)
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
        boxes = [a for a in sys.argv[1:] if a.count(",") == 3]   # --box 584,302,607,324 619,346,638,355
        manual = [[int(v) for v in a.split(",")] for a in boxes] or None
        haze = []
        if "--haze" in sys.argv:   # --haze 16: softer patch for this run (user: "bóng bẩy" -> blurrier)
            haze = [sys.argv[sys.argv.index("--haze") + 1]]
            HAZE = float(haze[0])
            SOFT = max(SOFT, HAZE / 3)
        # --fill clone | interp: the older ffmpeg patches (no GPU); default MiniMax-Remover
        fill = next((f for f in ("interp", "clone") if f in sys.argv), "minimax")
        args = [a for a in sys.argv[1:] if a not in ("--end", "--box", "--haze", "--fill", "interp", "clone") and a not in boxes and a not in haze]
        one_clip(args[0], args[1] if len(args) > 1 else None, endpart, manual=manual, fill=fill)
    else:
        sys.exit("usage: hide_logo.py <folder> | --execute | <shot_NNN|video path> [tl|tr|bl|br] [--end] | --at <mm:ss> [corner] | --pending | --overwrite-all | --relink")
