"""Light colour pass for V1 of timeline "Edit" (default /doc-edit color since 2026-10-22): small, safe CDL nudges only.

    .venv/Scripts/python.exe .claude/skills/colorist/scripts/light.py plan     # measure + decide; Resolve untouched
    .venv/Scripts/python.exe .claude/skills/colorist/scripts/light.py apply    # backup Edit, CDL on node 1 of every shot
    .venv/Scripts/python.exe .claude/skills/colorist/scripts/light.py --selftest

User 2026-10-22 (africa_1, after match.py broke shots): no heavy scene matching. Per shot only a CDL on node 1
(no per-shot LUT, no group look LUT, node 1 LUTs left as they are):
  - AI clips that are too saturated come down (to SAT_HI_AI); every other day shot gets livelier (VIVID, dull ones more),
  - every shot moves a little toward the film's median exposure and loses a little cast (partial, clamped),
  - intro shots (before the spec's '# INTRO') get INTRO_K of that,
  - a correction that would add clipping or crush, or push saturation out, is halved until it does not,
  - golden grass (user 2026-10-22, 02:25 impala pair): only inside a daytime stretch of burnt / golden grass, a shot
    whose grass is greener or paler gets that stretch's golden grass as a LUT on node 1 (match.dry; dry_pass()).
One frame per shot from the cache (match.py frames) or ffmpeg: fast and cheap. After apply, look at >= 12 real frames.
"""
import datetime as dt
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import grade as G  # noqa: E402
import match as M  # noqa: E402  (frame grab + cache only)

ROOT = G.ROOT
LIM = dict(slope=(0.93, 1.07), cast=0.03, power=(0.97, 1.04), sat=(0.80, 1.25))  # the most any shot is moved
EXP_K, CAST_K = 0.35, 0.4   # share of the way to the film's median exposure / to neutral
SAT_HI, SAT_HI_AI = 0.46, 0.40  # mean saturation: above -> down (AI clips earlier), never pushed past it
# "màu tươi" (user 2026-10-22): every day shot below SAT_HI gets at least VIVID, dull ones sqrt(SAT_AIM / sat)
SAT_AIM, VIVID = 0.42, 1.10
INTRO_K = 0.3               # intro shots: 30 % of every correction
OUT = ROOT / ".work" / "grade"
# golden grass: strength (1.0 = what the user approved at 02:25), +- shots looked at, share of golden day shots there,
# "paler" = gold saturation below this share of the stretch's; never on water (would turn gold), never below hue 28
DRY_K, DRY_WIN, DRY_SHARE, DRY_PALE, DRY_MINHUE, DRY_MINSAT = 1.0, 5, 0.6, 0.75, 28.0, 0.16
WATER = {"river", "riverbank", "lake", "swamp", "waterfall", "underwater"}
CUBE_N = 33


def is_ai(path):
    p = path.lower().replace("/", "\\")
    return "\\ai_video\\" in p or "\\ai_copyright\\" in p


def intro_end(project):
    """'# INTRO m:ss' of the video's doc-edit spec (seconds), 0 when there is none."""
    import plan as P
    for d in (ROOT / ".work" / "doc_edit").iterdir():
        sp = d / "spec.txt"
        if sp.exists() and P.same_project(project, d.name):
            m = re.search(r"^#\s*INTRO\s+(\d+):([\d.]+)", sp.read_text("utf-8"), re.M)
            return int(m[1]) * 60 + float(m[2]) if m else 0.0
    return 0.0


def decide(st, ref, ai, k):
    """CDL for one shot: st = G.stats of its frame, ref = film medians, k = strength (1 body, INTRO_K intro)."""
    s = 1.0
    if not st["lowkey"]:  # night / deep shade keeps its darkness
        s = (ref["p50"] / max(st["p50"], 0.02)) ** EXP_K
    gain = np.ones(3)
    ref_c = st["neutral"] if st["neutral"] is not None else None  # cast only from near-grey pixels (foliage is green)
    if ref_c is not None:
        gain = (ref_c.mean() / np.maximum(ref_c, 1e-3)) ** CAST_K
        gain = np.clip(gain, 1 - LIM["cast"], 1 + LIM["cast"])
    hi = SAT_HI_AI if ai else SAT_HI
    s0 = max(st["sat"], 0.05)
    if s0 > hi:
        sat = hi / s0
    elif st["lowkey"]:  # night / deep shade stays muted
        sat = 1.0
    else:
        sat = max(1.0, min(max(VIVID, (SAT_AIM / s0) ** 0.5), hi / s0))
    power = 1.0
    if st["con"] < 0.30 and not st["lowkey"]:  # flat: a touch more contrast
        power = 1.03
    c = dict(slope=1 + k * (np.clip(s, *LIM["slope"]) * gain - 1), offset=np.zeros(3),
             power=1 + k * (np.clip(power, *LIM["power"]) - 1), sat=1 + k * (np.clip(sat, *LIM["sat"]) - 1))
    return c


def safe(img, st, c, n=4):
    """Halve the correction until it adds no clipping / crush and keeps saturation sane."""
    for _ in range(n):
        f = G.stats(G.cdl(img, c["slope"], c["offset"], c["power"], c["sat"]))
        bad = (f["clip"] > st["clip"] + 0.5 or f["crush"] > st["crush"] + 1.0 or f["sat95"] > max(st["sat95"], 0.80)
               or f["p99"] > max(st["p99"], 0.975))
        if not bad:
            return c, f
        c = dict(slope=1 + (c["slope"] - 1) / 2, offset=c["offset"], power=1 + (c["power"] - 1) / 2, sat=1 + (c["sat"] - 1) / 2)
    return dict(slope=np.ones(3), offset=np.zeros(3), power=1.0, sat=1.0), st


def tags_by_path():
    """{lower abs path: tags} of every indexed video clip."""
    sys.path.insert(0, str(ROOT / ".claude/skills/scan-source/scripts"))
    from scan_source import ROOTS, index_of
    out = {}
    for root, kind, _ in ROOTS.values():
        if kind == "video" and index_of(root).exists():
            for c in json.loads(index_of(root).read_text("utf-8"))["clips"].values():
                out[str(root / c["path"]).lower()] = c.get("tags") or {}
    return out


def dry_ok(r, tags):
    """Daytime, no water, not intro, not dark: the only shots the golden-grass pass looks at or changes."""
    t = tags.get(r["path"].lower(), {})
    return (not r["intro"] and not r["f"]["lowkey"] and t.get("light", "day") == "day"
            and r["f1"]["sat"] >= DRY_MINSAT  # fog / dust / grey close-ups: no grass to turn, only blotches (46:23)
            and not WATER & set(t.get("setting") or []))


def dry_safe(c1, f1, d):
    """match.dry on the graded frame, halved until it adds no neon / clip and the grass does not go orange."""
    def neon(c):  # share of loud orange / yellow pixels (what turned bushes neon in the first africa_1 preview)
        h = M.rgb2hsv(np.clip(c, 0, 1))
        return float(((h[:, 0] < 50) & (h[:, 1] > 0.7) & (h[:, 2] > 0.35)).mean())
    n1 = neon(c1)
    for _ in range(3):
        c2 = M.dry(c1, d)
        f, g = G.stats(c2), M.ground(c2)
        if (f["sat95"] <= max(f1["sat95"], 0.80) and f["clip"] <= f1["clip"] + 0.5 and neon(c2) <= n1 + 0.005
                and (g["hue"] is None or g["hue"] >= DRY_MINHUE)):
            return d
        d = dict(d, k=d["k"] / 2)
    return None


def dry_pass(rows):
    """Golden grass only inside a burnt / golden daytime stretch: among the same story's day shots within DRY_WIN,
    >= DRY_SHARE (and >= 3) have golden ground (hue <= match.DRY_HUE). A shot there whose ground is DRY_GAP greener
    than the stretch, or whose gold is paler (< DRY_PALE of it), gets the stretch's median gold. -> count."""
    n = 0
    for i, r in enumerate(rows):
        g = r["gd"]
        if not r["ok"] or g["hue"] is None or not (g["grass"] or g["gold"]):
            continue
        win = [x for x in rows[max(0, i - DRY_WIN): i + DRY_WIN + 1]
               if x is not r and x["ok"] and x["story"] == r["story"] and x["gd"]["hue"] is not None]
        gold = [x for x in win if x["gd"]["hue"] <= M.DRY_HUE and x["gd"]["gold"]]
        if len(gold) < 3 or len(gold) < DRY_SHARE * len(win):
            continue
        med = float(np.median([x["gd"]["hue"] for x in win]))
        ref = [float(v) for v in np.median([x["gd"]["gold"] for x in gold], 0)]
        greener = g["hue"] >= med + M.DRY_GAP
        paler = g["gold"] is not None and g["gold"][1] < DRY_PALE * ref[1]
        if greener or paler:
            d = dry_safe(r["c1"], r["f1"], dict(src=g["grass"] or g["gold"], ref=ref, k=DRY_K))
            if d:
                r["dry"] = dict(d, why="greener" if greener else "paler")
                n += 1
    return n


def write_dry_cube(path, d):
    g = np.linspace(0, 1, CUBE_N)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")  # r fastest in file order
    out = M.dry(np.stack([r, gg, b], -1).reshape(-1, 3), d)
    path.write_text(f"LUT_3D_SIZE {CUBE_N}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n"
                    + "".join("%.5f %.5f %.5f\n" % tuple(o) for o in out), encoding="ascii")


def plan():
    pm, project, tl, rows = G.timeline()
    t_intro = intro_end(project.GetName()) * 24
    with ThreadPoolExecutor(6) as ex:
        imgs = list(ex.map(M.grab, rows))
    rows = [dict(r, img=im) for r, im in zip(rows, imgs) if im is not None]
    for r in rows:
        r["st"] = G.stats(r["img"])
    ref = {"p50": float(np.clip(np.median([r["st"]["p50"] for r in rows if not r["st"]["lowkey"]]), 0.34, 0.46))}
    cuts, story, tags = M.story_cuts(project.GetName(), rows), 0, tags_by_path()
    out, n_ai, n_int = [], 0, 0
    for r in rows:
        ai, intro = is_ai(r["path"]), r["start"] < t_intro
        c, f = safe(r["img"], r["st"], decide(r["st"], ref, ai, INTRO_K if intro else 1.0))
        story += r["start"] in cuts
        r.update(c=c, f=f, ai=ai, intro=intro, story=story)
        r["c1"] = G.cdl(r["img"], c["slope"], c["offset"], c["power"], c["sat"])
        r["f1"], r["gd"] = G.stats(r["c1"]), M.ground(r["c1"])
        r["ok"] = dry_ok(r, tags)
    n_dry = dry_pass(rows)
    for r in rows:
        c, f, ai, intro = r["c"], r["f"], r["ai"], r["intro"]
        n_ai += ai and c["sat"] < 0.99
        n_int += intro
        out.append(dict(start=r["start"], path=r["path"], ai=ai, intro=intro, slope=[round(float(x), 4) for x in c["slope"]],
                        offset=[0.0, 0.0, 0.0], power=round(float(c["power"]), 4), sat=round(float(c["sat"]), 4),
                        before=dict(p50=round(float(r["st"]["p50"]), 3), sat=round(float(r["st"]["sat"]), 3)),
                        after=dict(p50=round(float(f["p50"]), 3), sat=round(float(f["sat"]), 3)),
                        dry=r.get("dry")))
    d = OUT / project.GetName()
    d.mkdir(parents=True, exist_ok=True)
    (d / "light_plan.json").write_text(json.dumps({"timeline": tl.GetName(), "shots": out}), "utf-8")
    sl = np.array([s["slope"] for s in out])
    sat = np.array([s["sat"] for s in out])
    print(f"V1 {len(out)} shots (intro {n_int} at {INTRO_K:.0%}) | film exposure target p50 {ref['p50']:.3f}")
    print(f"slope {sl.min():.3f}-{sl.max():.3f}, sat {sat.min():.3f}-{sat.max():.3f}, power "
          f"{min(s['power'] for s in out):.3f}-{max(s['power'] for s in out):.3f}; AI clips toned down: {n_ai}; "
          f"untouched (all within 1 %): {sum(1 for s in out if np.abs(np.array(s['slope']) - 1).max() < 0.01 and abs(s['sat'] - 1) < 0.01)}")
    dl = [s for s in out if s["dry"]]
    print(f"golden grass (burnt-grass daytime stretches only): {n_dry} shots: "
          + " ".join(f"{s['start'] // 1440:02d}:{s['start'] // 24 % 60:02d}({s['dry']['why'][0]}{s['dry']['k']:.2g})" for s in dl))
    print("->", d / "light_plan.json")


def apply():
    pm, project, tl, rows = G.timeline()
    q = {(s["start"], s["path"].lower()): s for s in
         json.loads((OUT / project.GetName() / "light_plan.json").read_text("utf-8"))["shots"]}
    miss = [r for r in rows if (r["start"], r["path"].lower()) not in q]
    assert len(miss) <= len(rows) * 0.02, f"{len(miss)} V1 shots changed since plan: re-run plan"
    bak = f"Edit_bak_light_{dt.datetime.now():%Y%m%d_%H%M%S}"
    from dvr_cowork.resolve_ops import backup_timeline
    assert backup_timeline(project, tl, bak), "backup failed, nothing changed"  # into bin "6. Timeline"
    project.SetCurrentTimeline(tl)
    ok, bad, dry = 0, [], []
    for r in rows:
        s = q.get((r["start"], r["path"].lower()))
        if not s:
            continue
        done = r["it"].SetCDL({"NodeIndex": "1", "Slope": " ".join(map(str, s["slope"])), "Offset": "0 0 0",
                               "Power": " ".join([str(s["power"])] * 3), "Saturation": str(s["sat"])})
        ok += bool(done)
        if not done:
            bad.append(Path(s["path"]).name)
        g = r["it"].GetNodeGraph()
        old = g.GetLUT(1) or ""
        if s.get("dry"):  # golden grass: own LUT per shot, after the CDL on node 1
            cube = M.lut_dir(project.GetName()) / f"dry_auto_{s['start']:07d}.cube"
            cube.parent.mkdir(parents=True, exist_ok=True)
            write_dry_cube(cube, s["dry"])
            dry.append((g, f"Amazona/match/{project.GetName()}/{cube.name}"))
        elif "dry_auto_" in old:  # an earlier run's golden grass the new plan no longer wants
            g.SetLUT(1, "")
    project.RefreshLUTList()
    n_lut = sum(bool(g.SetLUT(1, rel)) for g, rel in dry)
    pm.SaveProject()
    print(f"backup: {bak}; CDL set on {ok} shots, failed {len(bad)} {bad[:5]}, not in plan {len(miss)}; "
          f"golden-grass LUT on {n_lut}/{len(dry)}")


def selftest():
    rng = np.random.default_rng(1)
    base = np.clip(rng.uniform(0, 1, (6000, 3)) * [0.9, 1.0, 0.8], 0, 1).astype(np.float32)
    st = G.stats(base)
    ref = {"p50": st["p50"]}
    c = decide(st, ref, False, 1.0)
    assert np.all(np.abs(c["slope"] - 1) <= 0.07 + 0.03 + 1e-6) and LIM["sat"][0] <= c["sat"] <= LIM["sat"][1]
    dull = (base * 0.3 + base.mean(1, keepdims=True) * 0.7).astype(np.float32)  # a washed-out day frame
    sd = G.stats(dull)
    assert not sd["lowkey"] and sd["sat"] < SAT_AIM and decide(sd, ref, False, 1.0)["sat"] >= VIVID  # gets livelier
    loud = np.clip(base * [1.2, 0.5, 0.2], 0, 1)  # an over-saturated AI frame
    sl = G.stats(loud)
    assert sl["sat"] > SAT_HI_AI and decide(sl, ref, True, 1.0)["sat"] < 1.0
    assert abs(decide(sl, ref, True, INTRO_K)["sat"] - 1) < abs(decide(sl, ref, True, 1.0)["sat"] - 1)  # intro: lighter
    c2, f2 = safe(loud, sl, dict(slope=np.full(3, 1.3), offset=np.zeros(3), power=1.0, sat=1.0))
    assert f2["clip"] <= sl["clip"] + 0.5  # safe() backs a clipping correction off
    assert is_ai(r"D:\AI_video\_africa\hyena\x.mp4") and not is_ai(r"Z:\Unseen\savannah\x.mov")

    def shot(h, s, v, ok=True, story=0):  # a frame of grass of one HSV colour (+ a little noise)
        px = M.hsv2rgb(np.stack([np.full(2000, h) + rng.normal(0, 2, 2000), np.full(2000, s), np.full(2000, v)], -1))
        c1 = np.clip(px, 0, 1).astype(np.float32)
        return dict(ok=ok, story=story, c1=c1, f1=G.stats(c1), gd=M.ground(c1))
    gold, green = (34, 0.55, 0.75), (75, 0.45, 0.6)
    rows = [shot(*gold) for _ in range(3)] + [shot(*green)] + [shot(*gold) for _ in range(3)]
    assert dry_pass(rows) == 1 and rows[3].get("dry") and not rows[0].get("dry")  # green shot in a golden stretch
    rows = [shot(*green) for _ in range(7)]
    assert dry_pass(rows) == 0  # green stretch: nothing turns golden
    rows = [shot(*gold) for _ in range(3)] + [shot(*green, ok=False)] + [shot(*gold) for _ in range(3)]
    assert dry_pass(rows) == 0  # intro / night / water shot is never touched
    rows = [shot(*gold, story=0) for _ in range(3)] + [shot(*green, story=1)] + [shot(*green, story=1) for _ in range(3)]
    assert dry_pass(rows) == 0  # the golden stretch ends at the story start
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    selftest() if "--selftest" in a else plan() if a[:1] == ["plan"] else apply() if a[:1] == ["apply"] else sys.exit(__doc__)
