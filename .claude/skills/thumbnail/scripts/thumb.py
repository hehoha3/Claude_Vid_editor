"""Thumbnail finish via headless PhotoCraft (photocraft-cli). Never edits the source image (only moves it into its
folder), never overwrites.

  thumb.py stats IMAGE
  thumb.py finish IMAGE --text "LINE 1\\nLINE 2" --logo LOGO.png --layout A|B [grade/crop/text overrides]
  thumb.py --selftest

finish -> <out-dir>/<stem>/ (source moved in) with <stem>[_vN].psd (layered), <stem>_clean.png 3840x2160
(no text/logo), <stem>_final.jpg 1280x720. Brightness/saturation auto-target the look of references/look-ref.png.
"""
import argparse, filecmp, json, math, os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from dvr_cowork.stills import still_stats  # noqa: E402

PC = r"C:\Program Files\PhotoCraft\photocraft-cli.exe"
ASSETS = Path(__file__).resolve().parents[1] / "assets"
W, H = 3840, 2160
# Safe boxes (x0, y0, x1, y1) at 3840x2160, read from assets/layout-*-guide.png.
LAYOUT = {
    "A": {"logo": (96, 66, 960, 420), "title": (96, 1512, 2349, 2070), "anchor": "bottom"},
    "B": {"logo": (96, 90, 879, 411), "title": (66, 470, 1239, 2085), "anchor": "top"},
}
# Look target = still_stats of references/look-ref.png (user's reference, 2026-10-15): bright daylight, vivid colour.
TARGET = {"p50": 0.34, "sat": 0.50}


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def auto_wb(st):
    """colorBalance midtones [cyan-red, magenta-green, yellow-blue] that pull R/B toward neutral; green is left
    alone (foliage, and look-ref itself is +G). thumb_1 (-B 0.076) -> [-5, 0, 8], what was hand-picked."""
    rgb = st["midtone_rgb"] or [0.5, 0.5, 0.5]
    m = sum(rgb) / 3
    return [int(clamp(round(-(rgb[0] - m) * 80), -15, 15)), 0, int(clamp(round(-(rgb[2] - m) * 105), -15, 15))]


def look_delta(st):
    """(EV, vibrance) that move an image with stats st toward TARGET; display luma ~ linear^(1/2.2)."""
    p50, sat = st["luma_p1_p10_p50_p90_p99"][2], st["sat_mean"]
    return 2.2 * math.log2(TARGET["p50"] / max(p50, 0.02)), (TARGET["sat"] / max(sat, 0.05) - 1) * 120


def pc(*args, timeout=300):
    r = subprocess.run([PC, *map(str, args)], capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    if r.returncode != 0:
        sys.exit(f"photocraft-cli failed ({r.returncode}): {(r.stderr or r.stdout).strip()[-800:]}")
    return r.stdout


def info(path):
    return json.loads(pc("info", path, "--compact"))


def run(src, cmds, out, *extra):
    args = ["run", src]
    for cid, params in cmds:
        args += ["--cmd", cid] + (["--params", json.dumps(params, ensure_ascii=False)] if params is not None else [])
    lines = pc(*args, "--out", out, *extra).splitlines()
    return [json.loads(l) for l in lines if l.startswith("{")]


def edit_psd(psd, cmds):
    """Run cmds on this run's own PSD and replace it (via a temp file)."""
    tmp = psd.with_name(psd.stem + "_tmp.psd")
    res = run(psd, cmds, tmp)
    os.replace(tmp, psd)
    return res


def crop_169(w, h):
    """Largest centred 16:9 rect inside w x h."""
    if w * 9 >= h * 16:
        cw, ch = h * 16 // 9, h
    else:
        cw, ch = w, w * 9 // 16
    return (w - cw) // 2, (h - ch) // 2, cw, ch


def free_stem(out_dir, stem):
    """stem, else stem_v2, stem_v3... - the first with none of the three outputs on disk."""
    def taken(s):
        return any((out_dir / f"{s}{suf}").exists() for suf in (".psd", "_clean.png", "_final.jpg"))
    if not taken(stem):
        return stem
    n = 2
    while taken(f"{stem}_v{n}"):
        n += 1
    return f"{stem}_v{n}"


def fit_size(lines, box):
    """Rough pt size (72 ppi = px) so the longest line and all lines fit the box; Montserrat Black caps ~0.82 em/char (measured)."""
    bw, bh = box[2] - box[0], box[3] - box[1]
    return int(min(bh / (1.15 * len(lines)), bw / (0.82 * max(len(l) for l in lines)), 300))


def cmd_stats(a):
    d = info(a.image)
    w, h = d["width"], d["height"]
    print(json.dumps({"image": a.image, "size": [w, h], "aspect": round(w / h, 3), "crop_169": crop_169(w, h),
                      "out_dir_ok": Path(a.out_dir).is_dir(), **still_stats(a.image)}, ensure_ascii=False))


def cmd_finish(a):
    src, logo, out_dir = Path(a.image).resolve(), Path(a.logo).resolve(), Path(a.out_dir).resolve()
    for p in (src, logo, Path(PC)):  # PhotoCraft too: fail before the source is moved
        if not p.is_file():
            sys.exit(f"missing: {p}")
    if not out_dir.is_dir():
        sys.exit(f"out dir missing: {out_dir}")
    # One folder per thumbnail; the source is MOVED into it (user 2026-10-16, was a copy until then).
    # Source already in it -> reuse; a same-named file already there -> never overwrite, work on that one.
    work = src.parent if src.parent.name == src.stem else out_dir / src.stem
    work.mkdir(exist_ok=True)
    if not (work / src.name).exists():
        shutil.move(src, work / src.name)
        if not (work / src.name).is_file():
            sys.exit(f"move failed: {src} -> {work / src.name}")
    elif src != work / src.name and not filecmp.cmp(src, work / src.name, shallow=False):
        sys.exit(f"different image already named {work / src.name}; rename the source")
    src = work / src.name
    stem = free_stem(work, src.stem)
    psd, clean, final = work / f"{stem}.psd", work / f"{stem}_clean.png", work / f"{stem}_final.jpg"
    assert src not in (psd, clean, final)

    d = info(src)
    src_st = still_stats(src)
    ev0, vib0 = look_delta(src_st)
    wb = auto_wb(src_st) if a.wb == "auto" else [int(v) for v in a.wb.split(",")]
    ev = round(clamp(ev0, -0.3, 0.9), 2) if a.exposure is None else a.exposure
    vib = int(clamp(vib0, 0, 60)) if a.vibrance is None else a.vibrance
    x, y, cw, ch = [int(v) for v in a.crop.split(",")] if a.crop else crop_169(d["width"], d["height"])
    lay = LAYOUT[a.layout]
    lines = a.text.replace("\\n", "\n").split("\n")
    size = a.size or fit_size(lines, lay["title"])
    lead = int(size * 1.15)
    tx0, ty0, tx1, ty1 = lay["title"]
    gap, thick = size // 4, max(8, size // 13)  # RED_LINE under the headline (user 2026-10-15)
    if lay["anchor"] == "bottom":
        # Bottom of the last element (red line, else text) sits a.bottom px above the frame edge (user 2026-10-15:
        # lower; default 108 = the text's left margin). Glyph bottom ~ box top + 0.76*size (Montserrat Black caps).
        ty1 = H - a.bottom
        ty0 = ty1 - (gap + thick if a.line != "none" else 0) - int(0.76 * size) - (len(lines) - 1) * lead
    lg = info(logo)
    lx0, ly0, lx1, ly1 = lay["logo"]
    scale = round(min((lx1 - lx0) / lg["width"], (ly1 - ly0) / lg["height"]) * 90, 2)  # 90% of the box
    lw, lh = lg["width"] * scale / 100, lg["height"] * scale / 100
    c = a.curve
    subject = [("select.subject", None)]
    named = lambda cid, p, name: [(cid, p), ("layer.setProps", {"name": name})]  # noqa: E731
    # Light shadow (user 2026-10-15), on the headline and the red line.
    shadow = ("layer.layerStyle.dropShadow", {"color": "#000000", "opacity": a.shadow, "distance": int(max(3, size // 30) * a.shadow / 40),
                                              "size": int(max(6, size // 12) * a.shadow / 40), "add": True})

    cmds = [("image.crop", {"x": x, "y": y, "width": cw, "height": ch, "targetWidth": W, "targetHeight": H}),
            *named("layer.duplicate", None, "SHARPEN_SUBJECT"),
            *subject, ("filter.sharpen.unsharpMask", {"amount": a.sharpen, "radius": 1.2, "threshold": 3}),
            ("select.deselect", None),
            *named("layer.newAdjustmentLayer.colorBalance", {"midtones": wb},
                   "WB_NEUTRAL"),
            *named("layer.newAdjustmentLayer.exposure", {"exposure": ev, "gamma": a.gamma}, "BRIGHTNESS"),
            *named("layer.newAdjustmentLayer.curves", {"points": [[0, 0], [64, 64 - c], [192, 192 + c], [255, 255]]},
                   "CURVE_GLOBAL"),
            *named("layer.newAdjustmentLayer.hueSaturation",
                   {"yellows": {"saturation": a.yellow_sat}, "greens": {"saturation": a.green_sat}}, "HSL_YELLOW_GREEN"),
            *named("layer.newAdjustmentLayer.vibrance", {"vibrance": vib, "saturation": vib // 2}, "VIBRANCE"),
            *subject, *named("layer.newAdjustmentLayer.exposure", {"exposure": a.subject_ev}, "SUBJECT_POP"),
            *subject, ("select.inverse", None),
            *named("layer.newAdjustmentLayer.exposure", {"exposure": a.bg_ev}, "BG_DARKEN"),
            *subject, ("select.inverse", None),
            *named("layer.newAdjustmentLayer.hueSaturation", {"saturation": a.bg_sat}, "BG_DESAT"),
            ("select.deselect", None),
            ("layer.newFillLayer.gradient", {"from": "#ffffff", "to": "#000000", "style": "radial"}),
            ("layer.setProps", {"name": "VIGNETTE", "blend": "Multiply", "opacity": a.vignette}),
            ("file.placeEmbedded", {"path": str(ASSETS / f"layout-{a.layout}-guide.png"), "scale": 100,
                                    "center": [W // 2, H // 2]}),
            ("layer.setProps", {"name": "SAFE_GUIDE", "visible": False}),
            *named("file.placeEmbedded", {"path": str(logo), "scale": scale,
                                          "center": [int(lx0 + lw / 2), int(ly0 + lh / 2)]}, "LOGO"),
            ("type.create", {"box": [tx0, ty0, tx1 - tx0, max(ty1 - ty0, lead * len(lines) + size // 3)], "text": "\n".join(lines), "name": "HEADLINE",
                             "font": a.font, "fontStyle": a.font_style, "size": size, "leading": lead,
                             "color": a.color, "align": "left"}),
            *([("layer.layerStyle.stroke", {"size": a.stroke, "position": "outside", "color": "#000000"})]
              if a.stroke > 0 else []),
            shadow]
    res = run(src, cmds, psd)
    warns = sorted({w for r in res for w in r.get("warnings", [])})
    tb = next((r["result"].get("bounds") for r in res if r.get("command") == "type.create"), None)
    if tb and (tb[2] > tx1 or tb[3] + (gap + thick if a.line != "none" else 0) > ty1 + 8):  # run results give x0,y0,x1,y1 (info gives x,y,w,h)
        warns.append(f"headline overflows title box {lay['title']}: bounds {tb} -> lower --size")
    if a.line != "none" and tb:  # needs the real text bounds, so a second pass on the PSD
        edit_psd(psd, [("select.rect", {"x": tb[0], "y": tb[3] + gap, "width": tb[2] - tb[0], "height": thick}),
                       *named("layer.newFillLayer.solidColor", {"color": a.line}, "RED_LINE"), shadow,
                       ("select.deselect", None)])

    ids = {l["name"]: l["id"] for l in info(psd)["layers"]}
    to_final = [("image.imageSize", {"width": 1280, "height": 720, "resample": "bicubic"})]
    run(psd, to_final, final, "--quality", "90")
    if a.exposure is None and a.vibrance is None:  # one measured correction toward TARGET
        dev, dvib = look_delta(still_stats(final))
        if abs(dev) > 0.1 or abs(dvib) > 6:
            ev, vib = round(clamp(ev + dev, -0.3, 1.2), 2), int(clamp(vib + dvib, 0, 80))
            edit_psd(psd, [("layer.setAdjustment", {"layer": ids["BRIGHTNESS"], "exposure": ev, "gamma": a.gamma}),
                           ("layer.setAdjustment", {"layer": ids["VIBRANCE"], "vibrance": vib,
                                                    "saturation": vib // 2})])
            ids = {l["name"]: l["id"] for l in info(psd)["layers"]}
            os.remove(final)  # this run's own output, re-rendered next line
            run(psd, to_final, final, "--quality", "90")
    run(psd, [("layer.setProps", {"layer": ids[n], "visible": False})
              for n in ("LOGO", "HEADLINE", "RED_LINE") if n in ids], clean)
    fs = still_stats(final)
    print(json.dumps({"folder": str(work), "psd": psd.name, "clean": clean.name, "final": final.name,
                      "crop": [x, y, cw, ch], "layout": a.layout, "size_pt": size, "logo_scale": scale,
                      "wb": wb, "exposure": ev, "vibrance": vib, "headline_bounds": tb, "warnings": warns,
                      "final_vs_target": {"p50": [fs["luma_p1_p10_p50_p90_p99"][2], TARGET["p50"]],
                                          "sat": [fs["sat_mean"], TARGET["sat"]]},
                      "final_stats": fs}, ensure_ascii=False))


def selftest():
    assert crop_169(1920, 1080) == (0, 0, 1920, 1080)
    assert crop_169(1672, 941) == (0, 0, 1672, 940)  # thumb_1.png
    assert crop_169(2000, 2000) == (0, 437, 2000, 1125)  # square -> top/bottom trimmed
    assert crop_169(4000, 1000) == (1111, 0, 1777, 1000)  # very wide -> sides trimmed
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        assert free_stem(t, "thumb_1") == "thumb_1"
        (t / "thumb_1_final.jpg").touch()
        assert free_stem(t, "thumb_1") == "thumb_1_v2"
        (t / "thumb_1_v2.psd").touch()
        assert free_stem(t, "thumb_1") == "thumb_1_v3"
    assert fit_size(["SHORT"], LAYOUT["A"]["title"]) == 300  # capped
    assert fit_size(["A" * 40, "B"], LAYOUT["A"]["title"]) < 100
    st = lambda p50, sat: {"luma_p1_p10_p50_p90_p99": [0, 0, p50, 0, 0], "sat_mean": sat}  # noqa: E731
    assert look_delta(st(TARGET["p50"], TARGET["sat"])) == (0, 0)  # on target -> no change
    ev, vib = look_delta(st(0.25, 0.36))  # thumb_1 v2: darker + duller -> brighten + saturate
    assert 0.8 < ev < 1.1 and 40 < vib < 50, (ev, vib)
    assert auto_wb({"midtone_rgb": [0.441, 0.392, 0.303]}) == [-5, 0, 8]  # thumb_1 yellow cast
    assert auto_wb({"midtone_rgb": [0.4, 0.4, 0.4]}) == [0, 0, 0]
    assert auto_wb({"midtone_rgb": [0.37, 0.45, 0.34]}) == [1, 0, 5]  # look-ref: green kept
    assert look_delta(st(0.5, 0.7))[0] < 0 and look_delta(st(0.5, 0.7))[1] < 0  # brighter/more vivid -> pull back
    print("selftest ok")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stats")
    s.add_argument("image")
    s.add_argument("--out-dir", default=r"D:\Thumbs")
    s.set_defaults(fn=cmd_stats)
    f = sub.add_parser("finish")
    f.add_argument("image")
    f.add_argument("--text", required=True, help=r"headline; \n = line break")
    f.add_argument("--logo", required=True)
    f.add_argument("--layout", choices=["A", "B"], default="A")
    f.add_argument("--out-dir", default=r"D:\Thumbs")
    f.add_argument("--crop", help="x,y,w,h in source px (16:9); default centred")
    f.add_argument("--font", default="Montserrat")
    f.add_argument("--font-style", default="Black")
    f.add_argument("--size", type=int, help="pt at 3840 wide; default fits the title box")
    f.add_argument("--color", default="#ffffff")
    # User 2026-10-15: thin black outline (or none), shadow keeps the headline readable.
    f.add_argument("--stroke", type=int, default=3, help="outline px at 3840 wide, 0 = none")
    f.add_argument("--shadow", type=int, default=40, help="headline/line drop-shadow opacity %%, 0-100")
    f.add_argument("--bottom", type=int, default=108, help="layout A: px (at 3840) from the frame bottom to the line")
    f.add_argument("--line", default="#ff0000", help="RED_LINE colour under the headline, 'none' = no line")
    # Defaults: user 2026-10-15 wants bright, vivid colour like references/look-ref.png -> no background darkening
    # or desaturation, light vignette; BRIGHTNESS/VIBRANCE auto-target TARGET unless given.
    f.add_argument("--wb", default="auto", help="colorBalance midtones c-r,m-g,y-b; auto = neutralise R/B cast")
    f.add_argument("--exposure", type=float, help="BRIGHTNESS EV; default auto toward look-ref")
    f.add_argument("--gamma", type=float, default=1.1, help="BRIGHTNESS gamma (>1 lifts shadows)")
    f.add_argument("--vibrance", type=int, help="VIBRANCE (saturation = half); default auto toward look-ref")
    f.add_argument("--curve", type=int, default=6, help="S-curve strength (0 = flat)")
    f.add_argument("--yellow-sat", type=int, default=-5)
    f.add_argument("--green-sat", type=int, default=0)
    f.add_argument("--subject-ev", type=float, default=0.15)
    f.add_argument("--bg-ev", type=float, default=0.0)
    f.add_argument("--bg-sat", type=int, default=0)
    f.add_argument("--sharpen", type=int, default=60, help="unsharp amount on subject")
    f.add_argument("--vignette", type=float, default=0.06, help="VIGNETTE layer opacity 0..1")
    f.set_defaults(fn=cmd_finish)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
