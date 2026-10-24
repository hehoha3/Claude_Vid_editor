"""Shot matching + house look for V1 of timeline "Edit": every shot balanced toward one target per light, one AMZ LUT.

    .venv/Scripts/python.exe .claude/skills/colorist/scripts/grade.py plan [--sheet]   # measure + solve, nothing in Resolve
    .venv/Scripts/python.exe .claude/skills/colorist/scripts/grade.py apply            # backup Edit, groups, CDL, LUTs
    .venv/Scripts/python.exe .claude/skills/colorist/scripts/grade.py --selftest

Method (demo_2, 2026-10-09; simulated grade matched Resolve stills within 0.01):
- 2 frames per shot (cache .work/grade/frames, keyed by file + in-point) -> stats: luma p1/p50/p99, sat, cast measured on
  near-neutral pixels only.
- Color Group per light (library tag): Day -> AMZ_01, Golden -> AMZ_06, Dusk/Night -> AMZ_07; the LUT sits on the
  group's post-clip node 1, so the whole film shares one look per light.
- Per shot CDL on clip node 1, closed loop (2026-10-16, demo_5: half-way matching left p50 0.15-0.35 and +-5 % casts
  between shots): simulate CDL + LUT, then pull p1 / p99 / p50 / sat and the near-neutral balance fully onto the group's
  OUTPUT target (TGT; neutral = the LUT's own tint on grey, so the look stays). Casts only from near-neutral pixels
  (none -> balance untouched: foliage is green, not a cast); sat never cut below 0.75x. Only Dusk keeps low-key shots dark; a dark Day/Golden shot is lifted to ~80 % of
  the target. Then nudged until LIM passes (clean blacks, whites ~0.91, no neon, sim clip <= 1 % because the 160x90
  sim hides speculars: ~3x more clip in Resolve). Bright-sky shots (p50 > 0.7) stay bright on purpose.
Output: .work/grade/<project>/plan.json (+ sheet.jpg: 6 shots, ungraded top / graded bottom).
"""
import datetime as dt, hashlib, importlib.util, json, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / ".claude/skills/doc-edit/scripts"), str(ROOT / ".claude/skills/scan-source/scripts")]
_s = importlib.util.spec_from_file_location("ml", ROOT / "luts" / "make_luts.py")
ml = importlib.util.module_from_spec(_s); _s.loader.exec_module(ml)

FR = ROOT / ".work" / "grade" / "frames"
W, H = 160, 90
Y = np.array([0.2126, 0.7152, 0.0722])
GROUPS = {"Day": "AMZ_01_Natural_Canopy", "Golden": "AMZ_06_Golden_Release", "Dusk": "AMZ_07_Dusk_Night"}
LIGHT = {"day": "Day", "golden": "Golden", "dusk": "Dusk", "night": "Dusk"}
# house limits after CDL + LUT: clean blacks, open whites, controlled saturation (colorist non-negotiables)
LIM = dict(p1=(0.0, 0.06), crush=(0.0, 6.0), p99=(0.72, 0.975), con=(0.25, 0.75), sat=(0.20, 0.42), sat95=(0.0, 0.74),
           clip=(0.0, 1.0))  # 160x90 sim hides specular highlights: 0.7 % here was 2-3.4 % in Resolve (demo_5)
SATMIN = 0.75  # never strip more than 25 % saturation: a lush shot cut to 0.65 reads grey / fake
# per light group: where every shot lands after CDL + LUT (from the group's raw medians, clamped to the house range;
# Dusk keeps >= 90 % of its saturation, luts/README.md)
TGT = {"Day": lambda m: dict(p99=0.91, p50=float(np.clip(m["p50"], 0.34, 0.42)), sat=float(np.clip(m["sat"], 0.30, 0.38))),
       "Golden": lambda m: dict(p99=0.91, p50=float(np.clip(m["p50"], 0.32, 0.40)), sat=float(np.clip(m["sat"], 0.31, 0.38))),
       "Dusk": lambda m: dict(p99=float(np.clip(m["p99"] * 1.1, 0.65, 0.85)), p50=float(np.clip(m["p50"], 0.14, 0.24)),
                              sat=float(np.clip(0.9 * m["sat"], 0.24, 0.38)), keep_dark=True)}


def stats(a):
    y = a @ Y
    mx, mn = a.max(-1), a.min(-1)
    s = np.where(mx > 1e-4, (mx - mn) / np.maximum(mx, 1e-4), 0)
    q = np.percentile(y, [1, 10, 50, 90, 99])
    mid = (y > 0.15) & (y < 0.85)
    nm = mid & (s < 0.15)
    return dict(p1=q[0], p50=q[2], p99=q[4], con=q[3] - q[1], sat=s.mean(), mr=mid_ratio(a),
                sat95=np.percentile(s[y > 0.06], 95) if (y > 0.06).any() else 0, crush=(y <= 0.02).mean() * 100,
                clip=(mx >= 0.995).mean() * 100, nfrac=float(nm.mean()), neutral=a[nm].mean(0) if nm.mean() > 0.03 else None,
                lowkey=bool(q[2] < 0.16 or q[4] < 0.45))  # night / deep shade: keep the intent, no forced brightening


def cdl(a, slope, offset, power, sat):
    o = np.clip(a * slope + offset, 0, 1) ** power
    y = (o @ Y)[..., None]
    return np.clip(y + (o - y) * sat, 0, 1)


def mid_ratio(a):
    """Colour balance of the midtones (all content, normalised): fallback cast measure when nothing is neutral."""
    y = a @ Y
    m = a[(y > 0.12) & (y < 0.85)]
    m = m.mean(0) if len(m) > 50 else a.mean(0)
    return m / max(m.mean(), 1e-3)


def solve(st, tgt):
    """Open-loop start: full levels to the target (low-key shots keep their darkness), cast toward the group."""
    lk = st["lowkey"]
    hi = tgt["p99"] if not lk else min(tgt["p99"], st["p99"] * 1.25)
    s = float(np.clip((hi - tgt["p1"]) / max(st["p99"] - st["p1"], 0.05), 0.7, 1.8))
    o = float(np.clip(tgt["p1"] - st["p1"] * s, -0.1, 0.06))
    # no colour start from content: a foliage-only frame IS green (02:41 demo_5 turned teal/lime when its green was read
    # as a cast). Casts are corrected in converge() from near-neutral pixels only.
    return dict(slope=np.full(3, s), offset=np.full(3, o), power=1.0, sat=float(np.clip(tgt["sat"] / max(st["sat"], 0.05), SATMIN, 1.5)))


def check(f, lowkey):
    bad = [k for k, (lo, hi) in LIM.items() if not lo <= f[k] <= hi]
    return [k for k in bad if not (lowkey and (k == "con" or (k == "p99" and f[k] < LIM[k][0])))]


def converge(img, st, tgt, P, n=10):
    """Closed loop on the simulated CDL + LUT output: levels, midtone, saturation and neutral balance all pulled to the
    group target, so every shot of a light group lands on the same numbers (not half-way)."""
    g = solve(st, tgt)
    lk = st["lowkey"] and tgt.get("keep_dark", False)  # only Dusk keeps its darkness; a dark Day shot = underexposed
    hi = tgt["p99"] if not lk else min(tgt["p99"], st["p99"] * 1.25)
    tp50 = tgt["p50"] * (0.8 if st["lowkey"] else 1.0)
    # trust in the neutral pixels scales with how much of the frame is really neutral (3 % -> 0, 13 %+ -> full): in a
    # foliage frame they are pale leaves the LUT pushes to emerald on purpose; chasing them kills the green (02:41 demo_5)
    w = float(np.clip((st["nfrac"] - 0.03) / 0.10, 0, 1))
    tr = None  # this shot's own balance target: LUT neutral ** w * its uncorrected balance ** (1 - w), fixed once
    for _ in range(n):
        f = stats(ml.grade(cdl(img, g["slope"], g["offset"], g["power"], g["sat"]), P))
        sc = float(np.clip(((hi - tgt["p1"]) / max(f["p99"] - f["p1"], 0.05)) ** 0.8, 0.9, 1.1))
        g["slope"] = np.clip(g["slope"] * sc, 0.6, 1.9)
        g["offset"] = np.clip(g["offset"] + 0.8 * (tgt["p1"] - f["p1"]), -0.12, 0.08)
        if not lk:
            g["power"] = float(np.clip(g["power"] * (np.log(tp50) / np.log(min(max(f["p50"], 0.02), 0.98))) ** 0.7, 0.7, 1.45))
        g["sat"] = float(np.clip(g["sat"] * (tgt["sat"] / max(f["sat"], 0.03)) ** 0.8, SATMIN, 1.6))
        if f["neutral"] is not None and w > 0:  # residual cast after the LUT, judged on near-neutral pixels only
            nr = f["neutral"] / max(f["neutral"].mean(), 1e-3)
            tr = tgt["ratio"] ** w * nr ** (1 - w) if tr is None else tr
            k = (tr / nr) ** 0.7
            ks = g["slope"] * k / (k @ Y)
            m = ks @ Y  # total balance shift bounded to +-10 % (absolute, not per iteration)
            g["slope"] = np.clip(ks, m * 0.90, m * 1.10)
    return g


def fit(img, st, tgt, P):
    """converge(), then nudge until the simulated CDL + LUT passes LIM. -> (cdl dict, final stats, flags)"""
    g = converge(img, st, tgt, P)
    for _ in range(12):
        f = stats(ml.grade(cdl(img, g["slope"], g["offset"], g["power"], g["sat"]), P))
        bad = check(f, st["lowkey"])
        if "sat95" in bad or ("sat" in bad and f["sat"] > LIM["sat"][1]):
            g["sat"] *= 0.92
        elif "sat" in bad and g["sat"] < 1.25:
            g["sat"] *= 1.08
        elif ("p99" in bad and f["p99"] > LIM["p99"][1]) or "clip" in bad:
            g["slope"] = g["slope"] * 0.96
        elif "crush" in bad:
            g["offset"] = g["offset"] + 0.01
        elif "p1" in bad and f["p1"] > LIM["p1"][1]:
            g["offset"] = g["offset"] - 0.015
        elif "p99" in bad and g["slope"][1] < 1.3:
            g["slope"] = g["slope"] * 1.04
        elif "con" in bad and f["con"] < LIM["con"][0] and g["power"] < 1.3:
            g["power"] *= 1.04
        else:
            break
    return g, f, bad


def grab(c):
    """2 frames (25/75 % of the used part) as one (2*H*W, 3) float array; cached as uint8."""
    p = FR / (hashlib.md5(f"{c['path']}|{c['in']:.2f}|{c['dur']:.2f}".encode()).hexdigest()[:16] + ".npy")
    if not p.exists():
        fr = []
        for q in (0.25, 0.75):
            r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{c['in'] + q * c['dur']:.3f}", "-i", c["path"],
                                "-frames:v", "1", "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                               capture_output=True)
            if len(r.stdout) == W * H * 3:
                fr.append(np.frombuffer(r.stdout, np.uint8).reshape(H, W, 3))
        if not fr:
            return None
        np.save(p, np.stack(fr))
    return np.load(p).reshape(-1, 3).astype(np.float32) / 255


def timeline():
    from dvr_cowork.config import load_config
    from dvr_cowork.resolve_conn import connect
    from dvr_cowork.resolve_ops import clip_fps, find_timeline, get_project, timeline_fps
    pm, project = get_project(connect(load_config()))
    tl = find_timeline(project, "Edit")
    assert tl and tl.GetName() == "Edit", 'timeline "Edit" not found (Master is never touched)'
    fps, t0 = timeline_fps(tl, project), int(tl.GetStartFrame())
    rows = []
    for it in sorted(tl.GetItemListInTrack("video", 1) or [], key=lambda t: t.GetStart()):
        mp = it.GetMediaPoolItem()
        if mp:
            rows.append({"it": it, "start": int(it.GetStart()) - t0, "path": mp.GetClipProperty("File Path"),
                         "in": it.GetLeftOffset() / clip_fps(mp, fps), "dur": it.GetDuration() / fps})
    return pm, project, tl, rows


def group_target(name, sts):
    """Targets in OUTPUT space (after CDL + LUT) from the group's raw stats; neutral = the LUT's own tint on grey, so
    the look stays and casts go."""
    med = {k: float(np.median([s[k] for s in sts])) for k in ("p1", "p50", "p99", "sat")}
    grey = ml.grade(np.full((1, 3), 0.4, np.float32), ml.LUTS[GROUPS[name]])[0]
    return dict(p1=0.025, mr=np.median([s["mr"] for s in sts], 0), ratio=grey / grey.mean(), **TGT[name](med))


def plan(sheet):
    import plan as P
    pm, project, tl, rows = timeline()
    light = {c["abs"].lower(): c["tags"].get("light") for c in P.load_clips()}
    FR.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(6) as ex:
        imgs = list(ex.map(grab, rows))
    out, rep, show = [], [], []
    for name, lut in GROUPS.items():
        cs = [(r, im, stats(im)) for r, im in zip(rows, imgs)
              if im is not None and LIGHT.get(light.get(r["path"].lower()), "Day") == name]
        if not cs:
            continue
        Pm = ml.LUTS[lut]
        tgt = group_target(name, [s for _, _, s in cs])
        f0s, f1s, fl0, fl1 = [], [], 0, 0
        for r, im, st in cs:
            g, f, bad = fit(im, st, tgt, Pm)
            f0 = stats(im)
            f0s.append(f0); f1s.append(f); fl0 += bool(check(stats(ml.grade(im, Pm)), st["lowkey"])); fl1 += bool(bad)
            out.append(dict(start=r["start"], path=r["path"], group=name, lut=lut, slope=[round(float(x), 4) for x in g["slope"]],
                            offset=[round(float(x), 4) for x in g["offset"]], power=round(g["power"], 4),
                            sat=round(g["sat"], 4), flags=bad))
            show.append((im, g, Pm))
        sd = lambda fs, k: np.std([f[k] for f in fs])  # noqa: E731  shot-to-shot spread = how "one place" it feels
        mn = lambda fs, k: np.mean([f[k] for f in fs])  # noqa: E731
        cs_ = lambda fs: float(np.std([f["mr"] for f in fs], 0).mean())  # noqa: E731  midtone colour-balance spread
        rep.append(f"{name} {len(cs)} shots, {lut}: spread p50 {sd(f0s, 'p50'):.3f}->{sd(f1s, 'p50'):.3f} sat "
                   f"{sd(f0s, 'sat'):.3f}->{sd(f1s, 'sat'):.3f} cast {cs_(f0s):.3f}->{cs_(f1s):.3f} | p1 {mn(f0s, 'p1'):.3f}->{mn(f1s, 'p1'):.3f} p99 "
                   f"{mn(f0s, 'p99'):.3f}->{mn(f1s, 'p99'):.3f} sat {mn(f0s, 'sat'):.3f}->{mn(f1s, 'sat'):.3f} | "
                   f"flagged LUT-only {fl0} -> CDL+LUT {fl1}")
    out.sort(key=lambda q: q["start"])
    d = ROOT / ".work" / "grade" / project.GetName()
    d.mkdir(parents=True, exist_ok=True)
    (d / "plan.json").write_text(json.dumps({"timeline": tl.GetName(), "shots": out}), "utf-8")
    print(f"V1 {len(rows)} shots, measured {len(out)} (no frame: {sum(i is None for i in imgs)})")
    print("\n".join(rep) + "\n(before->after: spread = std between shots, lower = more like one place)")
    if sheet:
        from PIL import Image
        pick = [show[int(k)] for k in np.linspace(0, len(show) - 1, 6)]
        tile = lambda a: a.reshape(-1, H, W, 3)[0]  # noqa: E731
        top = np.concatenate([tile(im) for im, _, _ in pick], 1)
        bot = np.concatenate([tile(ml.grade(cdl(im, g["slope"], g["offset"], g["power"], g["sat"]), Pm)) for im, g, Pm in pick], 1)
        Image.fromarray((np.concatenate([top, bot]) * 255).astype(np.uint8)).save(d / "sheet.jpg", quality=88)
        print("sheet:", d / "sheet.jpg")
    print("->", d / "plan.json")


def apply():
    pm, project, tl, rows = timeline()
    q = json.loads((ROOT / ".work" / "grade" / project.GetName() / "plan.json").read_text("utf-8"))["shots"]
    by = {(s["start"], s["path"].lower()): s for s in q}
    miss = [r for r in rows if (r["start"], r["path"].lower()) not in by]
    assert len(miss) <= len(rows) * 0.02, f"{len(miss)} V1 shots changed since plan: re-run plan"
    project.GetMediaPool().SetCurrentFolder(project.GetMediaPool().GetRootFolder())
    bak = f"Edit_bak_grade_{dt.datetime.now():%Y%m%d_%H%M%S}"
    from dvr_cowork.resolve_ops import backup_timeline
    assert backup_timeline(project, tl, bak), "backup failed, nothing changed"  # into bin "6. Timeline"
    project.SetCurrentTimeline(tl)
    groups = {g.GetName(): g for g in project.GetColorGroupsList() or []}
    ok = bad = 0
    for r in rows:
        s = by.get((r["start"], r["path"].lower()))
        if not s:
            continue
        g = groups.get(s["group"]) or groups.setdefault(s["group"], project.AddColorGroup(s["group"]))
        a = r["it"].AssignToColorGroup(g)
        b = r["it"].SetCDL({"NodeIndex": "1", "Slope": " ".join(map(str, s["slope"])),
                            "Offset": " ".join(map(str, s["offset"])), "Power": " ".join([str(s["power"])] * 3),
                            "Saturation": str(s["sat"])})
        ok += a and b; bad += not (a and b)
    luts = []
    for name, lut in GROUPS.items():
        if name in groups:
            pg = groups[name].GetPostClipNodeGraph()
            luts.append(f"{name} {bool(pg and pg.GetNumNodes() and pg.SetLUT(1, f'Amazona/{lut}.cube'))}")
    pm.SaveProject()
    print(f"backup: {bak}; shots graded {ok}, failed {bad}, not in plan {len(miss)}; group LUT set: {', '.join(luts)}")


def selftest():
    rng = np.random.default_rng(1)
    y = rng.uniform(0.02, 0.75, (4000, 1))  # lifted blacks, dull whites, slight green cast: the "hazy / vintage" shot
    grey_haze = np.clip(y * [0.95, 1.0, 0.9] + 0.09 + rng.normal(0, 0.03, (4000, 3)), 0, 1)
    st = stats(grey_haze)
    P = ml.LUTS["AMZ_01_Natural_Canopy"]
    grey = ml.grade(np.full((1, 3), 0.4, np.float32), P)[0]
    tgt = dict(p1=0.025, p99=0.93, p50=0.38, ratio=grey / grey.mean(), sat=0.33, mr=np.ones(3))
    g, f, bad = fit(grey_haze, st, tgt, P)
    assert f["p1"] < LIM["p1"][1] < st["p1"] and f["p99"] > st["p99"], (st, f, bad)  # de-hazed: clean blacks, open whites
    # two shots of one scene, one dark + warm, one bright + cool: after the grade they must land on the same numbers
    base = np.clip(rng.uniform(0, 1, (4000, 1)) ** 1.3 * [0.85, 0.95, 0.8] + rng.normal(0, 0.12, (4000, 3)) * 0.5, 0, 1)
    a, b = np.clip(base * 0.75 * [1.06, 1.0, 0.91], 0, 1), np.clip(base * 1.05 * [0.9, 1.0, 1.12] + 0.04, 0, 1)
    fa, fb = (fit(x, stats(x), tgt, P)[1] for x in (a, b))
    na, nb = (f["neutral"] / f["neutral"].mean() for f in (fa, fb))
    assert abs(fa["p50"] - fb["p50"]) < 0.03 and abs(fa["sat"] - fb["sat"]) < 0.03 and np.abs(na - nb).max() < 0.04, (fa, fb, na, nb)  # 0.04: cast trust scales with neutral area
    leaves = np.clip(rng.uniform(0.05, 0.8, (4000, 1)) * [0.72, 1.0, 0.55] + rng.normal(0, 0.02, (4000, 3)), 0, 1)
    gl = fit(leaves, stats(leaves), tgt, P)[0]
    assert gl["slope"][1] >= gl["slope"].max() - 0.02, gl  # no neutral pixels: green is content, never pulled as a cast
    night = rng.uniform(0.0, 0.2, (4000, 3))
    assert stats(night)["lowkey"] and converge(night, stats(night), dict(tgt, keep_dark=True), P)["power"] == 1.0  # Dusk night stays dark
    assert converge(night, stats(night), tgt, P)["power"] < 1.0  # a dark shot in a Day group is lifted toward the scene
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    selftest() if "--selftest" in a else plan("--sheet" in a) if a[:1] == ["plan"] else apply() if a[:1] == ["apply"] \
        else sys.exit(__doc__)
