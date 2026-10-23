"""Scene match for V1 of timeline "Edit": every shot looks like the same place and time as its scene's hero shot.

    .venv/Scripts/python.exe .claude/skills/colorist/scripts/match.py plan        # measure, scenes, heroes, LUTs; Resolve untouched
    .venv/Scripts/python.exe .claude/skills/colorist/scripts/match.py apply       # backup Edit, group + CDL + match LUT per shot
    .venv/Scripts/python.exe .claude/skills/colorist/scripts/match.py verify      # ExportLUT of every shot -> real numbers, markers
    .venv/Scripts/python.exe .claude/skills/colorist/scripts/match.py note 02:41 group=Day warm=-0.01 note="leaves too lime"
    .venv/Scripts/python.exe .claude/skills/colorist/scripts/match.py --selftest

Per clip node 1 = CDL (balance, grade.py solver) then a per-shot match LUT (Resolve applies the node CDL before the node
LUT, probed 2026-10-16); the AMZ look LUT stays on the Color Group post-clip node. The match LUT works in Rec.709 Y'CbCr (linear on display values: 17^3 is exact):
  - lightness curve through 5 quantiles, pulled toward the scene hero (partial: framing differs between shots),
  - colour per hue band (neutral, warm = fur/earth, foliage, cool = sky/water): band a/b shift + chroma scale toward the
    hero's same band, so greens, fur and greys each match without one dragging the others (02:41: green read as a cast).
Ground season (user 2026-10-22): in a scene whose ground is mostly golden grass, a green-grass shot gets its grass
turned to the scene's golden grass inside its match LUT (dry(), strength DRY_K, note dry=0..1), canopy stays green-olive.
Scenes: consecutive shots, never across a spec '# STORY' start, cut where the light group or the measured look jumps.
Hero per scene: real footage first,
clean balance, on-target levels. Heroes are pulled half-way to their group median, shots mostly to their hero, so
scenes stay distinct but the film shares one space and time. Light group = library tag corrected by the image
(golden without warm light -> Day, near-black Day -> Dusk).
User notes: .work/grade/<project>/overrides.json via `note` (group, hero, strength, skip, exp, warm, sat, dry, note);
they survive every re-plan. LUT files: ProgramData ...\\LUT\\Amazona\\match\\<project>\\ (17^3, ~100 KB each).
"""
import datetime as dt
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import grade as G  # noqa: E402

ROOT = G.ROOT
ml, Y = G.ml, G.Y
FR = ROOT / ".work" / "grade" / "frames320"
W, H, NS = 320, 180, 24000  # frame size (speculars survive), pixels sampled for the fits
LUTROOT = Path(r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT")
N = 17
QS = (5, 25, 50, 75, 95)
BANDS = ("neutral", "warm", "foliage", "cool")
CENT = {"warm": (130, 30), "foliage": (215, 32), "cool": (305, 35)}  # YCbCr hue (atan2(Cr, Cb)) centre, width (deg)
S_HERO, S_SHOT = dict(L=0.4, C=0.6), dict(L=0.6, C=0.85)  # pull of hero -> group, shot -> hero (+ group 25 %)
CLAMP = dict(dab=0.06, cs=(0.75, 1.3), dL=0.12)
# ground season (user 2026-10-22, africa_1 02:11 green grass next to 02:15 golden grass): a green-grass shot in a scene
# whose ground is golden gets its grass turned to the scene's golden grass (dry()), so neighbours read as one place.
# Ground hue = median HSV hue of the bright vegetation (green grass ~48, golden ~30, measured on those two shots).
CONTRAST = 0.10  # user 2026-10-22: no flat contrast; S-curve on the target lightness, slope 1.24 at mid-grey, shifts <= 0.05


# user 2026-10-22 (africa_1: stormy gazelle clip went blue-black, hippo / lion crushed): the balance solver pegs its
# limits on bright Africa footage (power 1.45, slope 1.9, offset -0.19 on 977 of 1052 shots). Its CDL is cut back to
# SOFT of the way from identity and clamped; the per-shot match LUT then does the rest within its own clamps.
SOFT = 0.4
# Africa (user 2026-10-22: lion at 00:43 muddy brown, saturation and contrast too low): the house targets were set for
# the Amazon look; an Africa project (name contains 'africa') lands on richer colour: sat targets +SAT_PLUS, limits up,
# and the match LUT lifts chroma by SAT_LIFT on top (the guard backs it off where a shot would go neon).
SAT_PLUS, SAT_LIFT = 0.07, 1.12


def africa_targets():
    for g, f in list(G.TGT.items()):
        G.TGT[g] = (lambda f: lambda m: {**f(m), "sat": min(f(m)["sat"] + SAT_PLUS, 0.5)})(f)
    G.LIM["sat"] = (G.LIM["sat"][0], 0.50)
    G.LIM["sat95"] = (G.LIM["sat95"][0], 0.82)
CDL_LIM = dict(slope=(0.8, 1.25), offset=(-0.05, 0.05), power=(0.9, 1.15), sat=(0.8, 1.2), spread=0.04)


def soften(c):
    sl = 1 + SOFT * (np.asarray(c["slope"], float) - 1)
    sl = np.clip(sl, *CDL_LIM["slope"])
    m = sl.mean()
    sl = np.clip(sl, m * (1 - CDL_LIM["spread"]), m * (1 + CDL_LIM["spread"]))  # channels stay together: no colour cast from the gain
    return dict(slope=sl, offset=np.clip(SOFT * np.asarray(c["offset"], float), *CDL_LIM["offset"]),
                power=float(np.clip(1 + SOFT * (c["power"] - 1), *CDL_LIM["power"])),
                sat=float(np.clip(1 + SOFT * (c["sat"] - 1), *CDL_LIM["sat"])))


def scurve(L, k=CONTRAST):
    """Gentle S around mid-grey: darks a little darker, lights a little lighter, ends fixed, monotone."""
    L = np.asarray(L, np.float64)
    return L + 2 * k * (L - 0.5) * (1 - (2 * L - 1) ** 2)


DRY_K, DRY_HUE, DRY_GAP = 0.7, 40.0, 8.0  # strength (note dry=0..1), scene is golden at <= 40 deg, shot is off at +8 deg

# Rec.709 Y'CbCr on display values: linear, so a 17^3 LUT reproduces the match (Oklab's gamma round trip did not:
# p99 error 0.027 on real frames, mostly in the dark greens)
MY = np.array([[0.2126, 0.7152, 0.0722], [-0.2126 / 1.8556, -0.7152 / 1.8556, 0.9278 / 1.8556],
               [0.7874 / 1.5748, -0.7152 / 1.5748, -0.0722 / 1.5748]])
MYi = np.linalg.inv(MY)


def to_lab(c):
    return np.clip(c, 0, 1) @ MY.T  # L = luma, a = Cb, b = Cr


def to_rgb(lab):
    return np.clip(lab @ MYi.T, 0, 1)


def bands(lab):
    """(n, 4) soft membership: neutral, warm, foliage, cool."""
    a, b = lab[:, 1], lab[:, 2]
    C, h = np.hypot(a, b), np.degrees(np.arctan2(b, a)) % 360
    cr = ml.smooth(C, 0.04, 0.10)
    g = lambda c, w: np.exp(-0.5 * (((h - c + 180) % 360 - 180) / w) ** 2)  # noqa: E731
    return np.stack([1 - ml.smooth(C, 0.02, 0.07)] + [cr * g(*CENT[k]) for k in BANDS[1:]], 1)


def measure(rgb):
    lab = to_lab(rgb)
    w = bands(lab)
    C = np.hypot(lab[:, 1], lab[:, 2])
    m = dict(Lq=np.percentile(lab[:, 0], QS))
    for i, k in enumerate(BANDS):
        s = w[:, i].sum()
        m[k] = dict(frac=float(s / len(w)), a=float(w[:, i] @ lab[:, 1] / max(s, 1e-6)),
                    b=float(w[:, i] @ lab[:, 2] / max(s, 1e-6)), C=float(w[:, i] @ C / max(s, 1e-6)))
    return m


def ident():
    return dict(xq=[0.25, 0.45, 0.6, 0.75, 0.9], dL=[0.0] * 5, da=[0.0] * 4, db=[0.0] * 4, cs=[1.0] * 4,
                exp=0.0, warm=0.0, sat=1.0)


def rgb2hsv(x):
    mx, mn = x.max(-1), x.min(-1)
    d = mx - mn
    h = np.zeros_like(mx)
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    m = d > 1e-6
    i = m & (mx == r); h[i] = ((g - b)[i] / d[i]) % 6
    i = m & (mx == g) & (mx != r); h[i] = (b - r)[i] / d[i] + 2
    i = m & (mx == b) & (mx != r) & (mx != g); h[i] = (r - g)[i] / d[i] + 4
    return np.stack([h * 60, np.where(mx > 0, d / np.maximum(mx, 1e-6), 0), mx], -1)


def hsv2rgb(x):
    h, s, v = x[..., 0] % 360 / 60, x[..., 1], x[..., 2]
    i, f = np.floor(h).astype(int) % 6, h - np.floor(h)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    return np.choose(i[..., None] * np.ones(3, int), [np.stack(c, -1) for c in
                     ((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))])


def ground(c):
    """Pixels -> dict(hue = ground hue or None, grass = HSV median of bright yellow-green / green (h 40-140, v > 0.4),
    gold = HSV median of golden grass (h 28-60, s > 0.25)); None where < 300 pixels."""
    h = rgb2hsv(np.clip(c, 0, 1))
    med = lambda k: [float(x) for x in np.median(h[k], 0)] if k.sum() >= 300 else None  # noqa: E731
    veg = (h[:, 0] >= 18) & (h[:, 0] <= 140) & (h[:, 1] > 0.12) & (h[:, 2] > 0.35)
    return dict(hue=float(np.median(h[veg, 0])) if veg.sum() >= 300 else None,
                grass=med((h[:, 0] >= 40) & (h[:, 0] <= 140) & (h[:, 1] > 0.06) & (h[:, 2] > 0.4)),
                gold=med((h[:, 0] >= 28) & (h[:, 0] < 60) & (h[:, 1] > 0.25) & (h[:, 2] > 0.3) & (h[:, 2] < 0.97)))


def dry(c, d):
    """Green grass -> the scene's golden grass. d = dict(src = grass HSV of the shot, ref = gold HSV of the scene, k).
    Weighted by brightness (grass bright, canopy dark keeps its green, olive at most) and hue (fur / soil < 36 deg stay)."""
    hsv = rgb2hsv(np.clip(c, 0, 1))
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    (sh, ss, sv), (th, ts, tv) = d["src"], d["ref"]
    # africa_1 2026-10-22 preview: sat x2.2 and hues 10-20 deg under the gold turned bushes / tree lines neon orange ->
    # sat never past the gold's (x1.15), hue never > 3 deg under it, deep saturated leaves (s > 0.55) mostly kept
    # greys / haze (s < 0.08) untouched: a 0.03-0.08 ramp left blotches in hazy trees and gold specks in fog
    w = d["k"] * ml.smooth(h, 36, 46) * (1 - ml.smooth(h, 165, 185)) * ml.smooth(s, 0.08, 0.16) \
        * (0.15 + 0.85 * ml.smooth(v, 0.3, 0.5)) * (1 - 0.7 * ml.smooth(s, 0.55, 0.8))
    h2 = np.maximum(th + (h - sh) * 0.5, th - 3)
    s2 = np.minimum(s * np.clip(ts / ss, 0.6, 1.6), np.maximum(s, ts * 1.15))
    v2 = v * np.clip(tv / sv, 0.8, 1.35)
    out = np.stack([h + w * (h2 - h), np.clip(s + w * (s2 - s), 0, 1), np.clip(v + w * (v2 - v), 0, 1)], -1)
    return np.clip(hsv2rgb(out), 0, 1).astype(np.float32)


def transform(c, p):
    """The match: what the per-shot LUT does (input = CDL output); dry grass first when the shot has it."""
    if p.get("dry"):
        c = dry(c, p["dry"])
    lab = to_lab(c)
    w = bands(lab)
    x = lab[:, 0]
    lab[:, 0] = x + np.interp(x, [0.0, *p["xq"], 1.0], [0.0, *p["dL"], 0.0]) + p["exp"]
    cs = np.clip(1 + w @ (np.array(p["cs"]) - 1), *CLAMP["cs"]) * p["sat"]
    lab[:, 1] = lab[:, 1] * cs + w @ np.array(p["da"]) - p["warm"]  # warmer = less blue (Cb), more red (Cr)
    lab[:, 2] = lab[:, 2] * cs + w @ np.array(p["db"]) + 0.6 * p["warm"]
    return to_rgb(lab)


def monotone(xq, dL):
    """Keep the lightness curve rising (slope >= 0.35) and inside the clamp."""
    dL = np.clip(dL, -CLAMP["dL"], CLAMP["dL"])
    y = np.array(xq) + dL
    for i in range(1, len(y)):
        y[i] = max(y[i], y[i - 1] + 0.35 * (xq[i] - xq[i - 1]))
    return list(np.minimum(y, 0.995) - np.array(xq))


def blend(m, t, s):
    """Target = m moved toward t by s (per field; bands only where both have the band)."""
    o = dict(Lq=m["Lq"] + s["L"] * (t["Lq"] - m["Lq"]))
    for k in BANDS:
        o[k] = dict(m[k])
        if m[k]["frac"] >= 0.03 and t[k]["frac"] >= 0.03:
            for f in ("a", "b", "C"):
                o[k][f] = m[k][f] + s["C"] * (t[k][f] - m[k][f])
    return o


def fit_match(img, P, tgt, keep_dark=False, it=6, k=CONTRAST):
    """Solve the match params so AMZ(transform(img)) lands on tgt (output space)."""
    p = ident()
    if not keep_dark:  # low-key dusk shots keep their own darkness
        tgt = dict(tgt, Lq=scurve(tgt["Lq"], k))
    p["xq"] = list(np.clip(np.percentile(to_lab(img)[:, 0], QS), 0.02, 0.98))
    p["xq"] = list(np.maximum.accumulate(np.array(p["xq"]) + np.arange(5) * 1e-3))
    m0 = measure(ml.grade(img, P))
    for _ in range(it):
        m = measure(ml.grade(transform(img, p), P))
        if not keep_dark:
            p["dL"] = monotone(p["xq"], np.array(p["dL"]) + 0.8 * (tgt["Lq"] - m["Lq"]))
        for i, k in enumerate(BANDS):
            if m0[k]["frac"] < 0.03 or tgt[k]["frac"] < 0.03:
                continue
            p["da"][i] = float(np.clip(p["da"][i] + 0.8 * (tgt[k]["a"] - m[k]["a"]), -CLAMP["dab"], CLAMP["dab"]))
            p["db"][i] = float(np.clip(p["db"][i] + 0.8 * (tgt[k]["b"] - m[k]["b"]), -CLAMP["dab"], CLAMP["dab"]))
            if k != "neutral" and m[k]["C"] > 0.02:
                p["cs"][i] = float(np.clip(p["cs"][i] * (tgt[k]["C"] / m[k]["C"]) ** 0.8, *CLAMP["cs"]))
    return p


def guard(r, Pm, n=10):
    """House limits after the match (the match alone pushed 152 of 757 shots into neon / clip): back off sat and the top
    of the lightness curve until the shot is no worse than its balance-only grade."""
    p, lk = r["p"], r["st"]["lowkey"] and r["group"] == "Dusk"
    allowed = set(G.check(G.stats(ml.grade(r["base"], Pm)), lk))
    for _ in range(n):
        f = G.stats(ml.grade(transform(r["base"], p), Pm))
        bad = set(G.check(f, lk)) - allowed
        if {"sat95"} & bad or ("sat" in bad and f["sat"] > G.LIM["sat"][1]):
            p["sat"] *= 0.94
        elif {"clip"} & bad or ("p99" in bad and f["p99"] > G.LIM["p99"][1]):
            p["dL"] = monotone(p["xq"], np.array(p["dL"]) - [0, 0, 0.005, 0.015, 0.025])
        elif "p1" in bad and f["p1"] > G.LIM["p1"][1]:
            p["dL"] = monotone(p["xq"], np.array(p["dL"]) - [0.015, 0.008, 0, 0, 0])
        elif "crush" in bad:
            p["dL"] = monotone(p["xq"], np.array(p["dL"]) + [0.01, 0.005, 0, 0, 0])
        else:
            return


def grab(r):
    """3 frames (20/50/80 % of the used part) at 320x180 -> (3*H*W, 3) float; cached uint8."""
    p = FR / (hashlib.md5(f"{r['path']}|{r['in']:.2f}|{r['dur']:.2f}".encode()).hexdigest()[:16] + ".npy")
    if not p.exists():
        fr = []
        for q in (0.2, 0.5, 0.8):
            o = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{r['in'] + q * r['dur']:.3f}", "-i", r["path"], "-frames:v",
                                "1", "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
            if len(o.stdout) == W * H * 3:
                fr.append(np.frombuffer(o.stdout, np.uint8).reshape(H, W, 3))
        if not fr:
            return None
        np.save(p, np.stack(fr))
    return np.load(p).reshape(-1, 3).astype(np.float32) / 255


def key(r):
    return f"{Path(r['path']).name}|{r['in']:.1f}"


def light_group(tag, st):
    """Library light tag, corrected by the image."""
    g = G.LIGHT.get(tag, "Day")
    ref = st["neutral"] if st["neutral"] is not None else st["mr"]
    warm = ref[0] / max(ref[2], 1e-3)
    if g == "Golden" and warm < 1.08:
        return "Day", "golden tag, light not warm"
    if g == "Day" and st["p50"] < 0.08 and st["p99"] < 0.35:
        return "Dusk", "day tag, near-black frame"
    return g, ""


def story_cuts(project, rows):
    """Start frames of the shots holding a '# STORY n m:ss' time of the video's spec (doc-edit): a scene never spans
    two stories (user 2026-10-22: same space inside one story). No spec found -> no cuts."""
    import re
    import plan as P
    spec = next((d / "spec.txt" for d in (ROOT / ".work" / "doc_edit").iterdir()
                 if (d / "spec.txt").exists() and P.same_project(project, d.name)), None)
    if not spec:
        return set()
    ts = [int(m[1]) * 60 + float(m[2]) for m in re.finditer(r"^#\s*STORY\s+\d+\s+(\d+):([\d.]+)", spec.read_text("utf-8"), re.M)]
    return {max((r["start"] for r in rows if r["start"] <= t * 24), default=0) for t in ts}


def scenes(rows, cuts=()):
    """Cut where the look (or light group) jumps vs the running scene for 2 shots in a row - a single cutaway stays in
    its scene; >= 6 shots per scene (demo_5: per-shot cuts at >= 4 gave 126 scenes of ~4 shots, too small to unify).
    cuts = start frames where a new scene must begin (story starts)."""
    if cuts:
        segs, cur = [], []
        for r in rows:
            if r["start"] in cuts and cur:
                segs.append(cur); cur = []
            cur.append(r)
        return [s for seg in segs + [cur] if seg for s in scenes(seg)]
    out, cur = [], []

    def feat(r):
        m = r["m0"]
        return np.array([m["Lq"][2] / 0.08, m["foliage"]["a"] / 0.025, m["foliage"]["b"] / 0.025,
                         m["neutral"]["a"] / 0.02, m["neutral"]["b"] / 0.02])

    def off(r, ref, grp):
        return r["group"] != grp or np.abs(feat(r) - ref).sum() > 8.0
    for i, r in enumerate(rows):
        if len(cur) >= 6:
            ref = np.median([feat(x) for x in cur], 0)
            grp = max(set(x["group"] for x in cur), key=[x["group"] for x in cur].count)
            if off(r, ref, grp) and (i + 1 == len(rows) or off(rows[i + 1], ref, grp)):
                out.append(cur); cur = []
        cur.append(r)
    if cur:
        out.append(cur)

    def split(s):  # > 40 shots (demo_5 S1 = 92 shots / 6 min): cut at the biggest look change between 5-shot windows
        if len(s) <= 40:
            return [s]
        f = np.array([feat(x) for x in s])
        i = max(range(6, len(s) - 6), key=lambda k: np.abs(np.median(f[k - 5:k], 0) - np.median(f[k:k + 5], 0)).sum())
        return split(s[:i]) + split(s[i:])
    return [p for s in out for p in split(s)]


def hero_score(r, tgt):
    st, f = r["st"], r["f"]
    return (2.0 * r["path"].upper().startswith("Z:") - 3 * len(r["flags"]) + 4 * min(st["nfrac"], 0.2)
            - 3 * abs(f["p50"] - tgt["p50"]) - 3 * abs(f["sat"] - tgt["sat"]) - 1.0 * (st["lowkey"] and r["group"] != "Dusk")
            - 3.0 * bool(r.get("dry")))  # a shot whose grass is off the scene's season never sets the scene's look


def season(s, ov):
    """Scene s: when most of its ground is golden (median ground hue <= DRY_HUE), every shot DRY_GAP+ greener gets
    r['dry'] toward the scene's golden grass (median gold of its golden shots); note dry=0..1 = strength. -> count."""
    hs = [r["gd"]["hue"] for r in s if r["gd"]["hue"] is not None]
    if not hs or np.median(hs) > DRY_HUE:
        return 0
    golds = [r["gd"]["gold"] for r in s if r["gd"]["gold"] and r["gd"]["hue"] is not None and r["gd"]["hue"] <= DRY_HUE]
    if not golds:
        return 0
    ref, n = [float(x) for x in np.median(golds, 0)], 0
    for r in s:
        k = float(ov.get(r["key"], {}).get("dry", DRY_K))
        g = r["gd"]
        if k > 0 and g["grass"] and g["hue"] is not None and g["hue"] >= np.median(hs) + DRY_GAP:
            r["dry"] = dict(src=g["grass"], ref=ref, k=k)
            n += 1
    return n


def lut_dir(project):
    return LUTROOT / "Amazona" / "match" / project


def write_cube(path, p):
    g = np.linspace(0, 1, N)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")  # r fastest in file order
    out = transform(np.stack([r, gg, b], -1).reshape(-1, 3), p)
    path.write_text(f"LUT_3D_SIZE {N}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n" + "".join("%.5f %.5f %.5f\n" % tuple(o) for o in out),
                    encoding="ascii")


def read_cube(path):
    v = [ln.split() for ln in path.read_text().splitlines()]
    n = next(int(x[1]) for x in v if x and x[0] == "LUT_3D_SIZE")
    d = np.array([[float(t) for t in x] for x in v if len(x) == 3 and x[0][0] in "0123456789-."], np.float32)
    return d.reshape(n, n, n, 3)  # [b][g][r]


def apply_cube(c, cube):
    """Trilinear lookup, cube indexed [b][g][r]."""
    n = cube.shape[0]
    x = np.clip(c, 0, 1) * (n - 1)
    i = np.minimum(x.astype(int), n - 2)
    f = x - i
    out = 0
    for dr in (0, 1):
        for dg in (0, 1):
            for db in (0, 1):
                w = (f[:, 0] if dr else 1 - f[:, 0]) * (f[:, 1] if dg else 1 - f[:, 1]) * (f[:, 2] if db else 1 - f[:, 2])
                out = out + w[:, None] * cube[i[:, 2] + db, i[:, 1] + dg, i[:, 0] + dr]
    return out


def overrides(project):
    p = ROOT / ".work" / "grade" / project / "overrides.json"
    return p, (json.loads(p.read_text("utf-8")) if p.exists() else {})


def plan(sheet=True):
    import plan as P
    pm, project, tl, rows = G.timeline()
    africa = "africa" in project.GetName().lower()
    if africa:
        africa_targets()
    light = {c["abs"].lower(): c["tags"].get("light") for r in P.REGIONS for c in P.load_clips(r)}  # every region: the timeline may hold either
    _, ov = overrides(project.GetName())
    FR.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(6) as ex:
        imgs = list(ex.map(grab, rows))
    rng = np.random.default_rng(0)
    rows = [dict(r, img=im[rng.choice(len(im), min(NS, len(im)), replace=False)], key=key(r)) for r, im in zip(rows, imgs) if im is not None]
    moved = {}
    for r in rows:
        r["st"] = G.stats(r["img"])
        o = ov.get(r["key"], {})
        r["group"], why = (o["group"], "note") if o.get("group") else light_group(light.get(r["path"].lower()), r["st"])
        if why:
            moved[why] = moved.get(why, 0) + 1
    # 1) balance (CDL) per group, grade.py solver
    tg = {g: G.group_target(g, [r["st"] for r in rows if r["group"] == g]) for g in G.GROUPS if any(r["group"] == g for r in rows)}

    def balance(r):
        Pm = ml.LUTS[G.GROUPS[r["group"]]]
        r["cdl"], r["f"], r["flags"] = G.fit(r["img"], r["st"], tg[r["group"]], Pm)
        r["cdl"] = soften(r["cdl"])  # flags below are of the softened grade
        r["f"] = G.stats(ml.grade(G.cdl(r["img"], r["cdl"]["slope"], r["cdl"]["offset"], r["cdl"]["power"], r["cdl"]["sat"]), Pm))
        r["flags"] = G.check(r["f"], r["st"]["lowkey"] and r["group"] == "Dusk")
        r["base"] = G.cdl(r["img"], r["cdl"]["slope"], r["cdl"]["offset"], r["cdl"]["power"], r["cdl"]["sat"])
        r["m0"] = measure(ml.grade(r["base"], Pm))
        r["gd"] = ground(r["base"])
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(balance, rows))
    # 2) scenes (never across a story start) + ground season + heroes
    sc = scenes(rows, story_cuts(project.GetName(), rows))
    n_dry = sum(season(s, ov) for s in sc)
    for r in rows:
        if r.get("dry"):  # the scene match starts from the dried grass
            r["m0"] = measure(ml.grade(dry(r["base"], r["dry"]), ml.LUTS[G.GROUPS[r["group"]]]))
    moved[f"green grass -> scene's golden grass (dry {DRY_K})"] = n_dry
    gm = {}
    for g in tg:
        ms = [r["m0"] for r in rows if r["group"] == g]
        gm[g] = dict(Lq=np.median([m["Lq"] for m in ms], 0))
        for k in BANDS:
            have = [m[k] for m in ms if m[k]["frac"] >= 0.03] or [m[k] for m in ms]
            gm[g][k] = {f: float(np.median([h[f] for h in have])) for f in ("frac", "a", "b", "C")}
    for i, s in enumerate(sc):
        pinned = [r for r in s if ov.get(r["key"], {}).get("hero")]
        hero = pinned[0] if pinned else max(s, key=lambda r: hero_score(r, tg[r["group"]]))
        for r in s:
            r["scene"], r["hero"] = i + 1, r is hero
    # 3) match: heroes toward their group median, then shots toward hero (+25 % group)

    def match(r, tgt, s):
        o = ov.get(r["key"], {})
        Pm = ml.LUTS[G.GROUPS[r["group"]]]
        if o.get("skip"):
            r["p"] = ident()
        else:
            k = float(o.get("strength", 1.0))
            img = dry(r["base"], r["dry"]) if r.get("dry") else r["base"]
            r["p"] = fit_match(img, Pm, blend(r["m0"], tgt, {q: v * k for q, v in s.items()}),
                               keep_dark=r["group"] == "Dusk" and r["st"]["lowkey"],
                               k=CONTRAST * float(np.clip((0.72 - r["f"]["con"]) / 0.15, 0.0, 1.0)))  # flat shots get it, already contrasty ones none
            if africa:
                r["p"]["sat"] *= SAT_LIFT
            if r.get("dry"):
                r["p"]["dry"] = r["dry"]  # transform() = dry, then the match fitted on the dried image
        for f in ("exp", "warm", "sat"):
            if f in o:
                r["p"][f] = float(o[f])
        guard(r, Pm)
        r["out"] = ml.grade(transform(r["base"], r["p"]), Pm)
        r["m1"] = measure(r["out"])
    heroes = [r for r in rows if r["hero"]]
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(lambda r: match(r, gm[r["group"]], S_HERO), heroes))
    hm = {r["scene"]: r["m1"] for r in heroes}
    rest = [r for r in rows if not r["hero"]]
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(lambda r: match(r, blend(hm[r["scene"]], gm[r["group"]], dict(L=0.25, C=0.25)), S_SHOT), rest))
    # 4) write LUTs + plan
    d = ROOT / ".work" / "grade" / project.GetName()
    ld = lut_dir(project.GetName())
    ld.mkdir(parents=True, exist_ok=True)
    out = []
    for r in rows:
        # per timeline slot: one file used twice (07:11 + 28:03) sits in two scenes with two different matches
        name = f"{r['start']:06d}_" + hashlib.md5(r["key"].encode()).hexdigest()[:8] + ".cube"
        write_cube(ld / name, r["p"])
        f1 = G.stats(r["out"])
        r["flags1"] = G.check(f1, r["st"]["lowkey"] and r["group"] == "Dusk")
        out.append(dict(start=r["start"], path=r["path"], key=r["key"], group=r["group"], lut=G.GROUPS[r["group"]],
                        scene=r["scene"], hero=r["hero"], slope=[round(float(x), 4) for x in r["cdl"]["slope"]],
                        offset=[round(float(x), 4) for x in r["cdl"]["offset"]], power=round(float(r["cdl"]["power"]), 4),
                        sat=round(float(r["cdl"]["sat"]), 4), match_lut=f"Amazona/match/{project.GetName()}/{name}",
                        flags=r["flags1"], sim=dict(p50=round(float(f1["p50"]), 4), p99=round(float(f1["p99"]), 4),
                                                    sat=round(float(f1["sat"]), 4), clip=round(float(f1["clip"]), 3))))
    d.mkdir(parents=True, exist_ok=True)
    (d / "match_plan.json").write_text(json.dumps({"timeline": tl.GetName(), "shots": out}), "utf-8")
    report(rows, sc, moved)
    if sheet:
        sheets(rows, sc, d)
    print("->", d / "match_plan.json", "| LUTs:", ld)


def spread(ms):
    """Shot-to-shot spread: lightness (p50) and colour (foliage + neutral a/b), lower = more one place."""
    L = np.std([m["Lq"][2] for m in ms])
    col = np.mean([np.std([m[k][f] for m in ms if m[k]["frac"] >= 0.03] or [0]) for k in ("neutral", "foliage") for f in "ab"])
    return L, col


def report(rows, sc, moved):
    tc = lambda f: f"{int(f / 24 // 60):02d}:{f / 24 % 60:04.1f}"  # noqa: E731
    print(f"V1 {len(rows)} shots | groups " + ", ".join(f"{g} {sum(r['group'] == g for r in rows)}" for g in G.GROUPS)
          + (f" | corrected: {moved}" if moved else ""))
    w0, w1 = [], []
    for s in sc:
        if len(s) > 1:
            w0.append(spread([r["m0"] for r in s])); w1.append(spread([r["m1"] for r in s]))
    a0, a1 = np.mean(w0, 0), np.mean(w1, 0)
    for g in G.GROUPS:
        gs = [r for r in rows if r["group"] == g]
        if gs:
            b0, b1 = spread([r["m0"] for r in gs]), spread([r["m1"] for r in gs])
            print(f"{g}: whole-group spread L {b0[0]:.3f}->{b1[0]:.3f} colour {b0[1]:.4f}->{b1[1]:.4f}")
    print(f"scenes {len(sc)} (shots per scene median {int(np.median([len(s) for s in sc]))}, max {max(len(s) for s in sc)}): "
          f"in-scene spread L {a0[0]:.3f}->{a1[0]:.3f} colour {a0[1]:.4f}->{a1[1]:.4f} (balance only -> + scene match)")
    fl = [r for r in rows if r["flags1"]]
    print(f"flagged after match {len(fl)}: " + ", ".join(f"{tc(r['start'])} {'/'.join(r['flags1'])}" for r in fl[:12])
          + (" ..." if len(fl) > 12 else ""))
    print("heroes: " + ", ".join(f"S{r['scene']} {tc(r['start'])}" for r in rows if r["hero"]))


def sheets(rows, sc, d):
    from PIL import Image
    th = lambda a: a.reshape(-1, H, W, 3)[1][::2, ::2]  # noqa: E731  middle frame, 160x90
    hs = [r for r in rows if r["hero"]]
    cols = 8
    grid = np.ones((((len(hs) + cols - 1) // cols) * 90, cols * 160, 3), np.float32)
    for i, r in enumerate(hs):
        im = ml.grade(transform(G.cdl(grab(r), r["cdl"]["slope"], r["cdl"]["offset"], r["cdl"]["power"], r["cdl"]["sat"]),
                                r["p"]), ml.LUTS[G.GROUPS[r["group"]]])
        grid[i // cols * 90:(i // cols + 1) * 90, i % cols * 160:(i % cols + 1) * 160] = th(im)
    Image.fromarray((grid * 255).astype(np.uint8)).save(d / "heroes.jpg", quality=88)
    # 6 scenes: row = hero then 4 shots; left half balance only, right half matched
    pick = [s for s in sc if len(s) >= 5]
    pick = [pick[int(k)] for k in np.linspace(0, len(pick) - 1, min(6, len(pick)))]
    rowsimg = []
    for s in pick:
        hero = next(r for r in s if r["hero"])
        others = [r for r in s if not r["hero"]]
        sel = [hero] + [others[int(k)] for k in np.linspace(0, len(others) - 1, 4)]
        full = [(grab(r), r) for r in sel]
        base = [ml.grade(G.cdl(im, r["cdl"]["slope"], r["cdl"]["offset"], r["cdl"]["power"], r["cdl"]["sat"]),
                         ml.LUTS[G.GROUPS[r["group"]]]) for im, r in full]
        mat = [ml.grade(transform(G.cdl(im, r["cdl"]["slope"], r["cdl"]["offset"], r["cdl"]["power"], r["cdl"]["sat"]), r["p"]),
                        ml.LUTS[G.GROUPS[r["group"]]]) for im, r in full]
        rowsimg.append(np.concatenate([th(a) for a in base] + [np.ones((90, 8, 3), np.float32)] + [th(a) for a in mat], 1))
    Image.fromarray((np.concatenate(rowsimg, 0) * 255).astype(np.uint8)).save(d / "scenes.jpg", quality=88)
    print("sheets:", d / "heroes.jpg", "|", d / "scenes.jpg", "(scenes: left = balance only, right = matched; col 1 = hero)")


def apply():
    pm, project, tl, rows = G.timeline()
    q = json.loads((ROOT / ".work" / "grade" / project.GetName() / "match_plan.json").read_text("utf-8"))["shots"]
    by = {(s["start"], s["path"].lower()): s for s in q}
    miss = [r for r in rows if (r["start"], r["path"].lower()) not in by]
    assert len(miss) <= len(rows) * 0.02, f"{len(miss)} V1 shots changed since plan: re-run plan"
    assert project.RefreshLUTList()
    bak = f"Edit_bak_match_{dt.datetime.now():%Y%m%d_%H%M%S}"
    assert tl.DuplicateTimeline(bak), "backup failed, nothing changed"
    project.SetCurrentTimeline(tl)
    groups = {g.GetName(): g for g in project.GetColorGroupsList() or []}
    ok, bad = 0, []
    for r in rows:
        s = by.get((r["start"], r["path"].lower()))
        if not s:
            continue
        g = groups.get(s["group"]) or groups.setdefault(s["group"], project.AddColorGroup(s["group"]))
        a = r["it"].AssignToColorGroup(g)
        b = r["it"].SetCDL({"NodeIndex": "1", "Slope": " ".join(map(str, s["slope"])), "Offset": " ".join(map(str, s["offset"])),
                            "Power": " ".join([str(s["power"])] * 3), "Saturation": str(s["sat"])})
        c = r["it"].GetNodeGraph().SetLUT(1, s["match_lut"])
        ok += a and b and c
        if not (a and b and c):
            bad.append(s["key"])
    for name, lut in G.GROUPS.items():
        if name in groups:
            pg = groups[name].GetPostClipNodeGraph()
            pg and pg.GetNumNodes() and pg.SetLUT(1, f"Amazona/{lut}.cube")
    pm.SaveProject()
    print(f"backup: {bak}; shots graded {ok}, failed {len(bad)} {bad[:5]}, not in plan {len(miss)}")


def verify():
    """ExportLUT (Color page) of every V1 shot = the real Resolve grade incl. group LUT, on the 320x180 frames."""
    from dvr_cowork.config import load_config
    from dvr_cowork.resolve_conn import connect
    res = connect(load_config())
    pm, project, tl, rows = G.timeline()
    if "africa" in project.GetName().lower():
        africa_targets()  # same house limits as plan
    d = ROOT / ".work" / "grade" / project.GetName()
    q = {(s["start"], s["path"].lower()): s for s in json.loads((d / "match_plan.json").read_text("utf-8"))["shots"]}
    page, tmp = res.GetCurrentPage(), d / "_export.cube"
    res.OpenPage("color")
    fps, t0 = 24, int(tl.GetStartFrame())
    got, fails = [], 0
    try:
        for r in rows:
            s = q.get((r["start"], r["path"].lower()))
            im = grab(r)
            if not s or im is None:
                continue
            f = t0 + r["start"] + 2
            tl.SetCurrentTimecode(f"{f // (3600 * fps):02d}:{f // (60 * fps) % 60:02d}:{f // fps % 60:02d}:{f % fps:02d}")
            if not r["it"].ExportLUT(res.EXPORT_LUT_17PTCUBE, str(tmp)):
                fails += 1
                continue
            out = apply_cube(im, read_cube(tmp))
            got.append((r, s, G.stats(out), measure(out)))
    finally:
        res.OpenPage(page)
    flagged = []
    for r, s, st, m in got:
        why = G.check(st, s["group"] == "Dusk" and st["lowkey"])
        why += [] if st["clip"] <= 1.5 else ["clip"]
        if abs(st["p50"] - s["sim"]["p50"]) > 0.04:
            why.append("sim-mismatch")
        if why:
            flagged.append((r, s, sorted(set(why)), st))
    print(f"verified {len(got)} shots from Resolve (export failed {fails}); real clip% median {np.median([g[2]['clip'] for g in got]):.2f} "
          f"max {max(g[2]['clip'] for g in got):.2f}; p50 vs sim max diff {max(abs(g[2]['p50'] - g[1]['sim']['p50']) for g in got):.3f}")
    by_sc = {}
    for r, s, st, m in got:
        by_sc.setdefault(s["scene"], []).append(m)
    w = [spread(v) for v in by_sc.values() if len(v) > 1]
    print(f"in-scene spread (real): L {np.mean([x[0] for x in w]):.3f} colour {np.mean([x[1] for x in w]):.4f}")
    old = [fr for fr, mk in (tl.GetMarkers() or {}).items() if mk["name"] == "Grade check" and mk["color"] == "Green"]
    for fr in old:
        tl.DeleteMarkerAtFrame(fr)
    added = 0
    for r, s, why, st in flagged:
        note = f"S{s['scene']} {s['group']}: {', '.join(why)} (p50 {st['p50']:.2f} p99 {st['p99']:.2f} clip {st['clip']:.1f}%)"
        added += bool(tl.AddMarker(r["start"], "Green", "Grade check", note, r["it"].GetDuration()))
    pm.SaveProject()
    print(f"flagged {len(flagged)} -> green 'Grade check' markers {added} (old removed {len(old)})")


def note(tc, kv):
    pm, project, tl, rows = G.timeline()
    m, s = tc.split(":")
    f = (int(m) * 60 + float(s)) * 24
    r = max((x for x in rows if x["start"] <= f), key=lambda x: x["start"])
    p, ov = overrides(project.GetName())
    o = ov.setdefault(key(r), {})
    for a in kv:
        k, v = a.split("=", 1)
        assert k in ("group", "hero", "strength", "skip", "exp", "warm", "sat", "dry", "note"), k
        o[k] = v if k in ("group", "note") else (v.lower() in ("1", "true", "yes")) if k in ("hero", "skip") else float(v)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(ov, ensure_ascii=False, indent=1), "utf-8")
    print(f"{key(r)}: {o} -> re-run plan + apply")


def selftest():
    rng = np.random.default_rng(3)
    c = rng.uniform(0, 1, (5000, 3)).astype(np.float32)
    assert np.abs(to_rgb(to_lab(c)) - c).max() < 1e-3  # Y'CbCr round trip
    assert np.abs(transform(c, ident()) - c).max() < 1e-3  # identity params = identity LUT
    # 17^3 cube reproduces the transform (what Resolve interpolates)
    p = dict(ident(), dL=[0.02, 0.04, 0.03, 0.0, -0.02], da=[0.005, 0.01, -0.01, 0.0], db=[-0.01, 0.01, 0.015, -0.005], cs=[1, 1.1, 0.9, 1.05])
    tmp = ROOT / ".work" / "grade" / "_selftest.cube"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    write_cube(tmp, p)
    err = np.abs(apply_cube(c, read_cube(tmp)) - transform(c, p))
    assert np.percentile(err, 99) < 0.01, np.percentile(err, [50, 99, 100])
    # same place, two shots: foliage lime + grey cast vs hero emerald + neutral -> matched foliage hue within reach
    P = ml.LUTS["AMZ_01_Natural_Canopy"]
    leaf = lambda tint, n: np.clip(rng.uniform(0.1, 0.8, (n, 1)) * tint + rng.normal(0, 0.02, (n, 3)), 0, 1)  # noqa: E731
    hero = np.concatenate([leaf([0.55, 0.9, 0.45], 6000), leaf([0.8, 0.8, 0.8], 2000)])
    shot = np.concatenate([leaf([0.75, 0.95, 0.35], 6000), leaf([0.85, 0.8, 0.72], 2000)])
    hm, sm = measure(ml.grade(hero, P)), measure(ml.grade(shot, P))
    pm_ = fit_match(shot, P, blend(sm, hm, dict(L=1, C=1)))
    mm = measure(ml.grade(transform(shot, pm_), P))
    for k in ("foliage", "neutral"):
        d0 = np.hypot(sm[k]["a"] - hm[k]["a"], sm[k]["b"] - hm[k]["b"])
        d1 = np.hypot(mm[k]["a"] - hm[k]["a"], mm[k]["b"] - hm[k]["b"])
        assert d1 < 0.35 * d0, (k, d0, d1)
    assert pm_["cs"][2] > 0.75 and np.hypot(mm["foliage"]["a"], mm["foliage"]["b"]) > 0.1  # foliage stays green, not grey
    # ground season: bright green grass -> golden, dark canopy barely, fur untouched; k=0 = identity
    hp = lambda h, s, v: hsv2rgb(np.array([[h, s, v]], np.float32))  # noqa: E731
    d = dict(src=[50.0, 0.44, 0.6], ref=[31.0, 0.58, 0.76], k=1.0)
    grass, leaf, fur = (rgb2hsv(dry(hp(*x), d))[0] for x in ((50, 0.44, 0.6), (69, 0.49, 0.25), (30, 0.5, 0.6)))
    assert abs(grass[0] - 31) < 2 and grass[1] > 0.5, grass
    assert leaf[0] > 69 - 0.3 * (69 - 31 - 9.5), leaf  # dark leaves move < 30 % of the grass's way
    assert abs(fur[0] - 30) < 0.5 and abs(fur[2] - 0.6) < 0.01, fur
    assert np.abs(dry(c, dict(d, k=0.0)) - c).max() < 1e-4
    gd = lambda h, gold, grass: {"hue": h, "gold": gold, "grass": grass}  # noqa: E731
    sc_ = [{"key": str(i), "gd": gd(h, [31, 0.58, 0.76] if h < 40 else None, [50, 0.44, 0.6] if h > 40 else None)}
           for i, h in enumerate((30, 31, 48, 29))]
    assert season(sc_, {}) == 1 and sc_[2]["dry"]["ref"] == [31.0, 0.58, 0.76] and "dry" not in sc_[0]
    assert season([dict(x, key="a") for x in sc_[2:3]] * 3, {}) == 0  # a green scene stays green (Amazon, wet season)
    assert season([dict(sc_[2], key="z")] + sc_[:2] + sc_[3:], {"z": {"dry": 0.0}}) == 0  # note dry=0 = off
    assert [len(s) for s in scenes([{"start": i} for i in range(8)], {4})] == [4, 4]
    x = np.linspace(0, 1, 101)
    assert np.all(np.diff(scurve(x)) > 0) and abs(scurve(0.0)) < 1e-9 and abs(scurve(1.0) - 1) < 1e-9 and scurve(0.25) < 0.25 < scurve(0.75) - 0.5 + 0.25 + 1e-9
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if "--selftest" in a:
        selftest()
    elif a[:1] == ["plan"]:
        plan("--no-sheet" not in a)
    elif a[:1] == ["apply"]:
        apply()
    elif a[:1] == ["verify"]:
        verify()
    elif a[:1] == ["note"] and len(a) >= 3:
        note(a[1], a[2:])
    else:
        sys.exit(__doc__)
