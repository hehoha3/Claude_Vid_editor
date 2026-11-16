"""doc-edit: reframe V1 of the video timeline channN_vidK with Zoom / Position X-Y (Transform), no clips moved or cut.

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/reframe.py <video>            # dry-run: what would change
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/reframe.py <video> --apply    # backup the timeline, then set
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/reframe.py <video> --fill-only [--apply]  # letterbox fill only
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/reframe.py --selftest

User 2026-11-15: top/bottom black bars (letterbox) -> light zoom to fill, automatic (after_gen.py runs --fill-only
--apply). Side bars (pillarbox / vertical) are never zoomed: swap the clip.

1. fill: shots that leave black bars (source wider than 16:9, or bars baked into the file, ffmpeg cropdetect) are
   zoomed just enough to fill the frame.
2. punch-in (selective, YOLO subject box over the used part of the clip, MAX_SHARE of the shots at most):
   strike  the shot needed is a strike/attack/catch -> 1.2x on the animal, for impact
   tiny    character shot where the animal fills < TINY of the frame -> zoom so it reads
   size    same size as the shot before (two wides in a row) -> push to the next size, cut feels motivated
   Only character shots ([tag] line) whose clip shows that species; troop/herd shots get 'strike' only.
   Every zoomed shot is centred on the animal; the crop is checked to keep the animal in frame on all samples.
Shots whose Transform is not default (hand-made by the user, or a previous run) are left alone.
"""
import datetime as dt, json, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
CROP = ROOT / ".work" / "library" / "active_area.json"  # path -> [w, h, x, y] of the picture inside the file
SARF = ROOT / ".work" / "library" / "sar.json"  # path -> pixel aspect (1.0667 = 16:15, Resolve shows it wider)
STRIKE = re.compile(r"vồ|tấn công|lao (tới|vào|ra)|cắn|tóm|đớp|quật|bắt (mồi|được|gọn)|giết|xông|chồm", re.I)
GROUP = re.compile(r"đàn|bầy|cả |hai |những con", re.I)
TINY, MAX_SHARE = 0.18, 0.15
CAP = {1080: 1.35, 2160: 1.7}  # max zoom by source height: 1080p is already upscaled 2x on a UHD timeline
SIZE_SIDE = ((0.75, "close_up"), (0.44, "medium"), (0.0, "wide"))  # yolo.py calibration, coarse
NEXT = {"wide": 0.5, "medium": 0.8}  # target subject side when pushing to the next size


def cropdetect(path, dur):
    """Picture area [w, h, x, y]; bars only if all 3 samples agree (a dark scene alone is not a letterbox)."""
    got = []
    for t in (dur * 0.25, dur * 0.5, dur * 0.75):
        r = subprocess.run(["ffmpeg", "-hide_banner", "-ss", f"{t:.2f}", "-i", path, "-t", "1", "-vf",
                            "cropdetect=limit=24:round=2:reset=0", "-f", "null", "-"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        m = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", r.stderr)
        if m:
            got.append([int(x) for x in m[-1]])
    return max(got, key=lambda c: c[0] * c[1]) if got else None


def probe_sar(path):
    """Sample (pixel) aspect ratio of the file's video stream; 1.0 when square / unknown."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=sample_aspect_ratio", "-of", "csv=p=0", path], capture_output=True, text=True)
    m = re.match(r"(\d+):(\d+)", r.stdout.strip())
    return int(m[1]) / int(m[2]) if m and int(m[1]) and int(m[2]) else 1.0


def plan_shot(W, H, sw, sh, area, boxes, need, prev_side, cap, group=False):
    """-> (zoom, pan, tilt, reason, side_after) for one V1 item, or None when it stays as is.
    boxes: YOLO boxes of the shot's character (normalized to the file), [] = none / not the character.
    group: a troop / herd shot -> only 'strike' may punch in (a wide group must stay wide)."""
    s = min(W / sw, H / sh)                       # scale-to-fit
    aw, ah, ax, ay = area or (sw, sh, 0, 0)
    z0 = max(W / (aw * s), H / (ah * s))          # zoom that fills the frame with the picture area
    z0 = 1.0 if aw / ah < W / H * 0.99 else z0     # side bars (pillarbox / vertical): never zoomed, swap (user)
    z0 = 1.0 if z0 < 1.004 else z0 * 1.002        # 0.2% over: no hairline at the edge
    cx0, cy0 = (ax + aw / 2) / sw, (ay + ah / 2) / sh  # picture-area centre
    z, reason, cx, cy, side = z0, "fill" if z0 > 1 else None, cx0, cy0, None
    if boxes:
        xs, ys = [b[0] for b in boxes], [b[1] for b in boxes]
        side = median(max(b[2], b[3]) for b in boxes) * z0
        sub = (median(xs), median(ys))
        want = None
        if need and STRIKE.search(need):
            want, why = 1.2, "strike"
        elif not group and side < TINY:
            want, why = 0.35 / side, "tiny"
        elif not group and prev_side is not None and size_of(side) == size_of(prev_side) and size_of(side) in NEXT:
            want, why = NEXT[size_of(side)] / side, "size"
        if want:
            zz = min(max(want, 1.15), cap) * z0 if why != "strike" else min(1.2, cap) * z0
            while zz >= 1.12 * z0:                # largest zoom that keeps the animal in frame on every sample
                half_x, half_y = W / (sw * s * zz) / 2, H / (sh * s * zz) / 2  # visible half-size, file units
                c = (clamp(sub[0], half_x, 1 - half_x), clamp(sub[1], half_y, 1 - half_y))
                if all(abs(x - c[0]) <= half_x - 0.04 for x in xs) and all(abs(y - c[1]) <= half_y - 0.04 for y in ys):
                    z, reason, (cx, cy) = zz, why, c
                    side = median(max(b[2], b[3]) for b in boxes) * zz
                    break
                zz -= 0.05 * z0
        elif z0 > 1:                              # fill only: still slide the crop toward the animal
            half_x, half_y = W / (sw * s * z0) / 2, H / (sh * s * z0) / 2
            lo_x, hi_x = ax / sw + half_x, (ax + aw) / sw - half_x
            lo_y, hi_y = ay / sh + half_y, (ay + ah) / sh - half_y
            cx, cy = clamp(sub[0], lo_x, hi_x), clamp(sub[1], lo_y, hi_y)
    if not reason:
        return None if side is None else (None, side)
    pan = round((0.5 - cx) * sw * s * z, 1)       # Position X, timeline pixels; + = image moves right
    tilt = round((cy - 0.5) * sh * s * z, 1)      # Position Y; + = image moves up
    return round(z, 3), pan, tilt, reason, side


def clamp(v, lo, hi):
    return lo if hi < lo else min(max(v, lo), hi)


def size_of(side):
    return next(n for lim, n in SIZE_SIDE if side >= lim)


def letterbox(area, sw, sh):
    """The cropdetect area only when it is symmetric top/bottom bars over the full width, else None."""
    if area and area[0] >= 0.97 * sw and area[1] <= 0.95 * sh and abs(area[3] - (sh - area[1] - area[3])) <= 8:
        return area
    return None


def main(video, apply, fill_only=False):
    from dvr_cowork.config import load_config
    from dvr_cowork.resolve_conn import connect
    from dvr_cowork.resolve_ops import clip_fps, get_project, timeline_fps, use_video, video_timeline
    import plan as P
    import yolo

    from dvr_cowork.videokey import video_key
    plan = json.loads((ROOT / ".work" / "doc_edit" / video_key(video) / "plan.json").read_text("utf-8"))
    slots = plan["slots"]
    cfg = load_config()
    pm, project = get_project(connect(cfg))
    use_video(video)
    tl = video_timeline(project)
    assert tl, "video timeline channN_vidK not found (Master is never touched)"
    fps, t0 = timeline_fps(tl, project), int(tl.GetStartFrame())
    W, H = (int(tl.GetSetting(k)) for k in ("timelineResolutionWidth", "timelineResolutionHeight"))
    need_at = {round(s["start"] * round(fps)): s for s in slots}
    items = sorted(tl.GetItemListInTrack("video", 1) or [], key=lambda t: t.GetStart())

    rows = []
    for it in items:
        mp = it.GetMediaPoolItem()
        if not mp:
            continue
        p = mp.GetClipProperty("File Path")
        sw, sh = (int(x) for x in mp.GetClipProperty("Resolution").split("x"))
        cf = clip_fps(mp, fps)
        a = it.GetLeftOffset() / cf
        rows.append({"it": it, "path": p, "sw": sw, "sh": sh, "in": a, "out": a + it.GetDuration() / fps,
                     "dur": float(mp.GetClipProperty("Frames") or 0) / cf,
                     "slot": need_at.get(int(it.GetStart()) - t0, {}),
                     "manual": any(abs(float(it.GetProperty(k) or d) - d) > 1e-3
                                   for k, d in (("ZoomX", 1), ("Pan", 0), ("Tilt", 0)))})

    crop = json.loads(CROP.read_text("utf-8")) if CROP.exists() else {}
    todo = sorted({r["path"] for r in rows if r["path"].lower() not in crop})
    with ThreadPoolExecutor(6) as ex:
        dur = {r["path"]: r["dur"] for r in rows}
        for p, c in zip(todo, ex.map(lambda p: cropdetect(p, dur[p]), todo)):
            crop[p.lower()] = c
    CROP.write_text(json.dumps(crop, separators=(",", ":")), "utf-8")
    sar = json.loads(SARF.read_text("utf-8")) if SARF.exists() else {}
    todo_s = sorted({r["path"] for r in rows if r["path"].lower() not in sar})
    with ThreadPoolExecutor(6) as ex:
        for p, v in zip(todo_s, ex.map(probe_sar, todo_s)):
            sar[p.lower()] = v
    SARF.write_text(json.dumps(sar, separators=(",", ":")), "utf-8")
    for r in rows:  # display width: 1920x1080 at SAR 16:15 shows as 2048x1080 -> Resolve letterboxes it
        k, a = sar.get(r["path"].lower(), 1.0), letterbox(crop.get(r["path"].lower()), r["sw"], r["sh"])
        r["sw"] = round(r["sw"] * k)
        r["area"] = a and [round(a[0] * k), a[1], round(a[2] * k), a[3]]
        r["bars"] = bool(r["area"]) or r["sw"] / r["sh"] > W / H * 1.004  # top/bottom bars on the timeline

    lib = {c["abs"].lower(): c for c in P.load_clips(plan["region"])}
    clips = [lib[p] for p in {r["path"].lower() for r in rows if not fill_only or r["bars"]} if p in lib]
    new, sec = yolo.measure(clips)
    cache = json.loads(yolo.CACHE.read_text("utf-8"))
    print(f"yolo: {len(clips)} clips on V1, {new} measured now ({sec}s); cropdetect: {len(todo)} files now")

    out, prev = [], None
    for r in rows:
        c = lib.get(r["path"].lower())
        f = cache.get(c["id"], {}).get("f", []) if c else []
        need = r["slot"].get("need", "")
        want = set(r["slot"].get("filter", {}).get("sp", [])) - {"none"}
        if not (c and need.startswith("[") and want & set(c["tags"].get("species", []))):
            f = []                                 # punch-in / slide only toward the character the line is about
        group = bool(c and c["tags"].get("count") in ("many", "few")) or bool(GROUP.search(need))
        boxes = [b for b in f[int(r["in"] * yolo.FPS):int(r["out"] * yolo.FPS) + 1] if b]
        rng = int(r["out"] * yolo.FPS) - int(r["in"] * yolo.FPS) + 1
        boxes = boxes if len(boxes) >= 0.5 * rng else []
        area = r["area"]                           # only top/bottom bars count
        if fill_only and not r["bars"]:
            continue
        cap = CAP[2160] if r["sh"] >= 2000 else CAP[1080]
        res = None if r["manual"] else plan_shot(W, H, r["sw"], r["sh"], area, boxes, need, prev, cap, group)
        prev = res[-1] if res else None
        if res and res[0]:
            out.append((r, *res[:4]))
    fills = [o for o in out if o[4] == "fill"]
    creative = sorted((o for o in out if o[4] != "fill"), key=lambda o: ("strike", "tiny", "size").index(o[4]))
    creative = [] if fill_only else creative[:int(MAX_SHARE * len(rows))]
    tcs = lambda r: (lambda s: f"{int(s // 60):02d}:{s % 60:04.1f}")((int(r["it"].GetStart()) - t0) / fps)  # noqa: E731
    print(f"V1 {len(rows)} shots; manual Transform kept {sum(r['manual'] for r in rows)}; "
          f"fill (black bars) {len(fills)}; punch-in {len(creative)}: "
          + ", ".join(f"{k} {sum(o[4] == k for o in creative)}" for k in ("strike", "tiny", "size")))
    for r, z, pan, tilt, why in sorted(fills + creative, key=lambda o: o[0]["it"].GetStart()):
        print(f"  {tcs(r)} {why:6} zoom {z:.2f} x {pan:+.0f} y {tilt:+.0f}  {Path(r['path']).name[:45]} "
              f"{r['sw']}x{r['sh']}  {r['slot'].get('need', '')[:50]}")
    if not apply:
        print("dry-run: nothing changed (--apply to set)")
        return
    bak = f"{tl.GetName()}_bak_reframe_{dt.datetime.now():%Y%m%d_%H%M%S}"
    from dvr_cowork.resolve_ops import backup_timeline
    assert backup_timeline(project, tl, bak), "backup failed, nothing changed"  # into bin "6. Timeline"
    project.SetCurrentTimeline(tl)
    bad = 0
    for r, z, pan, tilt, why in fills + creative:
        it = r["it"]
        bad += not all([it.SetProperty("ZoomX", z), it.SetProperty("ZoomY", z),
                        it.SetProperty("Pan", pan), it.SetProperty("Tilt", tilt)])
    pm.SaveProject()
    print(f"backup: {bak}; set {len(fills) + len(creative)} shots, failed {bad}")


def selftest():
    W, H = 3840, 2160
    z, pan, tilt, why, _ = plan_shot(W, H, 4096, 1716, None, [], "", None, 1.7)  # 2.39:1 scope file
    assert why == "fill" and abs(z - 4096 / 1716 / (16 / 9) * 1.002) < 1e-3 and pan == tilt == 0
    z, *_ = plan_shot(W, H, 1920, 1080, [1920, 816, 0, 132], [], "", None, 1.35)  # baked 2.35 bars
    assert abs(z - 1080 / 816 * 1.002) < 1e-3
    assert plan_shot(W, H, 1920, 1080, None, [], "", None, 1.35) is None
    assert letterbox([1920, 816, 0, 132], 1920, 1080) and not letterbox([1440, 1080, 240, 0], 1920, 1080)  # pillarbox: no
    z, *_ = plan_shot(W, H, 2048, 1080, None, [], "", None, 1.35)  # 1920x1080 at SAR 16:15 -> 1.896:1
    assert abs(z - 2048 / 1080 / (16 / 9) * 1.002) < 1e-3
    assert plan_shot(W, H, 1440, 1080, None, [], "", None, 1.35) is None  # 4:3 = side bars: never zoomed
    lone = [[0.7, 0.6, 0.1, 0.1]] * 8                       # tiny animal right of centre, character shot
    z, pan, tilt, why, side = plan_shot(W, H, 1920, 1080, None, lone, "[J] báo đốm đứng", None, 1.35)
    assert why == "tiny" and z == 1.35 and pan < 0 and tilt > 0  # image slides left/up to bring it to the centre
    walk = [[0.1 + 0.1 * i, 0.5, 0.1, 0.1] for i in range(9)]  # crosses the whole frame: no safe punch-in
    assert plan_shot(W, H, 1920, 1080, None, walk, "[J] báo đốm đi", None, 1.35)[0] is None
    big = [[0.5, 0.5, 0.3, 0.3]] * 8
    assert plan_shot(W, H, 1920, 1080, None, big, "[J] báo vồ mồi", None, 1.35)[3] == "strike"
    assert plan_shot(W, H, 1920, 1080, None, big, "Rừng", 0.3, 1.35)[3] == "size"  # two wides in a row
    assert plan_shot(W, H, 1920, 1080, None, lone, "[M] đàn khỉ", None, 1.35, group=True) == (None, 0.1)  # troop stays wide
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    selftest() if "--selftest" in sys.argv else main(a[0], "--apply" in sys.argv, "--fill-only" in sys.argv)
