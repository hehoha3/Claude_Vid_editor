"""Generate the Amazona documentary LUT library (.cube, 33^3, Rec.709 gamma 2.4 in -> out).
Creative LUTs: apply AFTER the shot is balanced (exposure/WB), as a node or group-post node.
Run: .venv/Scripts/python.exe luts/make_luts.py   (writes next to this file)"""
import numpy as np, pathlib

N = 33
OUT = pathlib.Path(__file__).parent

# name: description, params
#  con/pivot: S-contrast about pivot; lift: black lift; shoulder: highlight roll-off start (1=off)
#  sat: global sat; vib: <1 compresses already-saturated colours; gshift: degrees moved for lime-greens toward emerald
#  gsat: extra sat factor on greens; shadow/mid/high: RGB tint added (shadows/mids/highs); desat_shadow: sat loss in deep shadows
LUTS = {
    # clean blacks (lift ~0), bright whites (shoulder >= 0.9), contrast 1.08-1.20 about pivot 0.435, natural-to-rich sat,
    # greens lime -> emerald with subtractive density, very light split tone (colorist: no "faded film" / teal-orange)
    "AMZ_01_Natural_Canopy": dict(
        desc="Base look for daylight rainforest: clean blacks, bright whites, lime -> deep emerald, natural rich saturation.",
        con=1.12, pivot=0.435, lift=0.0, shoulder=0.92, sat=1.06, vib=0.15, gshift=9, gsat=0.97, gdens=0.08, wdesat=0.10,
        shadow=(0.0, 0.0, 0.003), mid=(0.0, 0.0, 0.0), high=(0.004, 0.002, -0.003), desat_shadow=0.06),
    "AMZ_02_Clear_Daylight": dict(
        desc="'clear / crisp': bright clean daylight, neutral whites, fresh emerald greens, extra vibrance.",
        con=1.10, pivot=0.435, lift=0.0, shoulder=0.93, sat=1.10, vib=0.12, gshift=8, gsat=1.0, gdens=0.06, wdesat=0.08,
        shadow=(0.0, 0.0, 0.0), mid=(0.0, 0.0, 0.0), high=(0.002, 0.001, 0.0), desat_shadow=0.04),
    "AMZ_03_Misty_Dawn": dict(
        desc="Dawn / humid haze / aftermath: gentle contrast but true blacks, warm highlights, slightly cool shade.",
        con=1.04, pivot=0.435, lift=0.006, shoulder=0.90, sat=1.00, vib=0.15, gshift=7, gsat=0.95, gdens=0.05, wdesat=0.10,
        shadow=(-0.002, 0.0, 0.006), mid=(0.0, 0.0, 0.0), high=(0.008, 0.004, -0.004), desat_shadow=0.08),
    "AMZ_04_Swamp_Olive": dict(
        desc="Flooded forest / swamp: olive-brown water kept (not cyan), deep mossy greens, solid mids.",
        con=1.12, pivot=0.43, lift=0.0, shoulder=0.91, sat=1.02, vib=0.15, gshift=3, gsat=0.95, gdens=0.08, wdesat=0.10,
        shadow=(0.0, 0.002, 0.0), mid=(0.003, 0.002, -0.003), high=(0.004, 0.002, -0.002), desat_shadow=0.08),
    "AMZ_05_Tension_Stalk": dict(
        desc="Stalk / suspicion: higher contrast, sat -6%, slightly cooler mids, deep but textured shadows.",
        con=1.20, pivot=0.435, lift=0.0, shoulder=0.92, sat=0.94, vib=0.15, gshift=11, gsat=0.92, gdens=0.10, wdesat=0.10,
        shadow=(-0.002, 0.0, 0.004), mid=(-0.004, 0.0, 0.004), high=(0.0, 0.0, 0.0), desat_shadow=0.10),
    "AMZ_06_Golden_Release": dict(
        desc="Sun shafts / warm moments / resolution: warm highlights, neutral shadows, rich natural saturation.",
        con=1.10, pivot=0.435, lift=0.0, shoulder=0.92, sat=1.08, vib=0.15, gshift=6, gsat=0.98, gdens=0.06, wdesat=0.08,
        shadow=(0.0, 0.0, 0.0), mid=(0.005, 0.002, -0.004), high=(0.012, 0.006, -0.008), desat_shadow=0.05),
    "AMZ_07_Dusk_Night": dict(
        desc="Dusk / night: true blacks, cool mids, sat -10%, highlights keep a little warmth (last light).",
        con=1.10, pivot=0.40, lift=0.004, shoulder=0.92, sat=0.90, vib=0.12, gshift=6, gsat=0.92, gdens=0.06, wdesat=0.08,
        shadow=(-0.002, 0.0, 0.006), mid=(-0.005, -0.001, 0.006), high=(0.006, 0.003, -0.002), desat_shadow=0.08),
}


def rgb2hsv(c):
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    mx, mn = c.max(-1), c.min(-1); d = mx - mn
    h = np.zeros_like(mx)
    m = d > 1e-9
    rc = m & (mx == r); gc = m & (mx == g) & ~rc; bc = m & ~rc & ~gc
    h[rc] = ((g - b)[rc] / d[rc]) % 6
    h[gc] = (b - r)[gc] / d[gc] + 2
    h[bc] = (r - g)[bc] / d[bc] + 4
    return h * 60, np.where(mx > 1e-9, d / np.maximum(mx, 1e-9), 0), mx


def hsv2rgb(h, s, v):
    h = (h % 360) / 60; i = np.floor(h).astype(int) % 6; f = h - np.floor(h)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r = np.choose(i, [v, q, p, p, t, v]); g = np.choose(i, [t, v, v, q, p, p]); b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b], -1)


def smooth(x, a, b):  # 0 below a, 1 above b
    t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)


def grade(c, p):
    c = np.clip(c, 0, 1)
    # 1) hue / saturation (before tone so tone sets the final brightness)
    h, s, v = rgb2hsv(c)
    gw = smooth(h, 50, 80) * (1 - smooth(h, 150, 175))               # weight of yellow-green..green
    lime = smooth(h, 50, 80) * (1 - smooth(h, 95, 125))              # most yellow part of the greens
    h = h + p["gshift"] * (0.35 * gw + 0.65 * lime)                   # lime -> emerald
    s = s * (1 - (1 - p["gsat"]) * gw)
    s = s * p["sat"]
    s = s * (1 - p["vib"] * smooth(s, 0.45, 1.0) * 0.6)               # compress already saturated colours
    s = s * (1 - p["desat_shadow"] * (1 - smooth(v, 0.0, 0.25)))      # quiet deep shadows
    s = s * (1 - p.get("wdesat", 0.10) * smooth(v, 0.88, 1.0))        # whites stay clean
    v = v * (1 - p.get("gdens", 0.0) * gw * smooth(s, 0.15, 0.6))       # subtractive density: rich, darker greens
    c = hsv2rgb(h, np.clip(s, 0, 1), v)
    # 2) tone on luma, ratio-applied so hue is kept
    y = c @ np.array([0.2126, 0.7152, 0.0722]); y = np.maximum(y, 1e-6)
    t = p["pivot"] + (y - p["pivot"]) * p["con"]
    sh = p["shoulder"]; over = np.maximum(t - sh, 0)
    t = np.where(t > sh, sh + (1 - sh) * np.tanh(over / (1 - sh)), t)  # soft highlight roll-off
    t = np.clip(t, 0, 1)
    c = p["lift"] + c * (t / y)[..., None] * (1 - p["lift"])   # lift added after ratio so pure black lifts too
    t = p["lift"] + t * (1 - p["lift"])
    # 3) split tone
    w_s = ((1 - t) ** 2)[..., None]; w_h = (t ** 2)[..., None]; w_m = (4 * t * (1 - t))[..., None]
    c = c + w_s * np.array(p["shadow"]) + w_m * np.array(p["mid"]) + w_h * np.array(p["high"])
    return np.clip(c, 0, 1)


def write_cube(name, p):
    g = np.linspace(0, 1, N)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")                    # r fastest in file order
    rgb = np.stack([r, gg, b], -1).reshape(-1, 3)
    out = grade(rgb, p)
    with open(OUT / f"{name}.cube", "w", newline="\n") as f:
        f.write(f'TITLE "{name}"\n# {p["desc"]}\nLUT_3D_SIZE {N}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n')
        for o in out: f.write("%.6f %.6f %.6f\n" % tuple(o))
    return out


if __name__ == "__main__":
    ident = np.stack(np.meshgrid(*[np.linspace(0, 1, 17)] * 3, indexing="ij"), -1).reshape(-1, 3)
    for name, p in LUTS.items():
        write_cube(name, p)
        # self-check: grey ramp stays monotonic, no NaN, neutrals stay near-neutral
        ramp = np.linspace(0, 1, 64); ramp = np.stack([ramp] * 3, -1); o = grade(ramp, p)
        y = o @ np.array([0.2126, 0.7152, 0.0722])
        assert np.isfinite(grade(ident, p)).all() and (np.diff(y) >= -1e-6).all(), name
        print(f"{name}: black {y[0]:.3f} mid {y[32]:.3f} white {y[-1]:.3f}  max neutral drift {np.abs(o - y[:, None]).max():.3f}")
