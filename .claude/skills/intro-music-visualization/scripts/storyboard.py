"""intro-music-visualization: cuts.txt -> storyboard image(s) for review without rendering or watching video.
One row cell per shot: frames at 10 % / 50 % / 90 % of the shot, cut from the SOURCE files with ffmpeg (ungraded),
labelled with the timeline in-out, length and the strongest hit inside the shot. Nothing is written to Resolve.

    .venv/Scripts/python.exe .claude/skills/intro-music-visualization/scripts/storyboard.py <name> [--lines 12-30]
    .venv/Scripts/python.exe .claude/skills/intro-music-visualization/scripts/storyboard.py cand <name> <fragment> [<fragment> ...]
    (cand: replacement candidates, 3 s each from the middle of their usable window -> .work/intro_mv/<name>_cand/)
    .venv/Scripts/python.exe .claude/skills/intro-music-visualization/scripts/storyboard.py --selftest

Needs Resolve only to resolve the clip fragments (same lookup as build.py). Output: .work/intro_mv/<name>/storyboard_N.jpg
(SHOTS_PER_IMAGE shots each). Read at most ~2 images per review pass.
"""
import subprocess, sys, tempfile
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from build import WORK, load  # noqa: E402

TW, TH = 224, 126           # thumb size
COLS = 2                    # shots per row (3 thumbs each)
SHOTS_PER_IMAGE = 24
LABEL = 16


def hit_in(events, a, b):
    hs = [e for e in events if a - 0.05 <= e["t"] < b and e["level"] >= 3]
    return max(hs, key=lambda e: e["level"]) if hs else None


def thumb(path, t, tmp):
    out = Path(tmp) / f"{abs(hash((path, t)))}.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(t, 0):.3f}", "-i", path, "-frames:v", "1",
                    "-vf", f"scale={TW}:{TH}:force_original_aspect_ratio=decrease,pad={TW}:{TH}:(ow-iw)/2:(oh-ih)/2",
                    "-y", str(out)], capture_output=True)
    if not out.exists():
        return Image.new("RGB", (TW, TH), "red")
    with Image.open(out) as im:
        return im.copy()  # file closed: the temp dir can be removed on Windows


def sheet(cells, path):
    rows = (len(cells) + COLS - 1) // COLS
    img = Image.new("RGB", (COLS * (3 * TW + 8), rows * (TH + LABEL)), "black")
    d = ImageDraw.Draw(img)
    for k, (label, thumbs) in enumerate(cells):
        x, y = (k % COLS) * (3 * TW + 8), (k // COLS) * (TH + LABEL)
        d.text((x + 3, y + 2), label, fill="yellow")
        for j, t in enumerate(thumbs):
            img.paste(t, (x + j * TW, y + LABEL))
    img.save(path, quality=78)


def main(name, lines=None):
    *_, mmap, _, shots, _ = load(name)  # same clip lookup and source in-points as build.py
    work = WORK / name
    cells = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        for k, s in enumerate(shots, 1):
            if lines and not int(lines.split("-")[0]) <= s["line"] <= int(lines.split("-")[1]):
                continue
            path, src, dur = s["path"], s["src"], s["out"] - s["in"]
            h = hit_in(mmap["events"], s["in"], s["out"])
            label = (f"#{k} L{s['line']} {s['in']:.2f}-{s['out']:.2f} ({dur:.1f}s)"
                     + (f" B{h['level']}@{h['t']:.2f}" if h else "") + f" {Path(path).stem[:26]}")
            cells.append((label, [thumb(path, src + f * dur, tmp) for f in (0.1, 0.5, 0.9)]))
    outs = []
    for i in range(0, len(cells), SHOTS_PER_IMAGE):
        p = work / f"storyboard_{i // SHOTS_PER_IMAGE + 1}.jpg"
        sheet(cells[i:i + SHOTS_PER_IMAGE], p)
        outs.append(str(p))
    print(f"{len(cells)} shots -> " + ", ".join(outs))


def selftest():
    ev = [{"t": 1.0, "level": 5}, {"t": 2.0, "level": 3}, {"t": 4.0, "level": 4}]
    assert hit_in(ev, 0.98, 3.0)["t"] == 1.0 and hit_in(ev, 2.5, 3.9) is None
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "s.jpg"
        sheet([("a", [Image.new("RGB", (TW, TH))] * 3)] * 3, p)
        assert Image.open(p).size == (COLS * (3 * TW + 8), 2 * (TH + LABEL))
    print("selftest ok")


def cand(name, frags, sec=3.0):
    """Storyboard of replacement candidates: fragments laid end to end (sec each, auto source in) in <name>_cand."""
    import shutil
    work = WORK / f"{name}_cand"
    work.mkdir(parents=True, exist_ok=True)
    shutil.copy(WORK / name / "music_map.json", work / "music_map.json")
    (work / "cuts.txt").write_text("".join(f"{k * sec} | {k * sec + sec} | {f} | auto |\n" for k, f in enumerate(frags)), "utf-8")
    main(work.name)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["--selftest"]:
        selftest()
    elif a[:1] == ["cand"] and len(a) > 2:
        cand(a[1], a[2:])
    elif a:
        main(a[0], a[a.index("--lines") + 1] if "--lines" in a else None)
    else:
        print(__doc__)
