"""Before / after sheet of the golden-grass shots of light_plan.json (cached frames, CDL + dry). Resolve untouched."""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parent))
import grade as G, match as M
import os
proj = sys.argv[1]  # the project; with DVR_CHANNEL set: its <project>_<channel> plan (light.pkey)
d = Path(".work/grade") / (f"{proj}_{os.environ['DVR_CHANNEL']}" if os.environ.get("DVR_CHANNEL") else proj)
pl = json.loads((d / "light_plan.json").read_text("utf-8"))["shots"]
from grade import timeline
_, _, _, rows = timeline()
by = {(r["start"], r["path"].lower()): r for r in rows}
tiles = []
for s in [s for s in pl if s["dry"]]:
    r = by[(s["start"], s["path"].lower())]
    im = M.grab(r).reshape(3, M.H, M.W, 3)[1].reshape(-1, 3)
    c1 = G.cdl(im, np.array(s["slope"]), np.zeros(3), s["power"], s["sat"])
    c2 = M.dry(c1, s["dry"])
    pair = np.concatenate([c1.reshape(M.H, M.W, 3), c2.reshape(M.H, M.W, 3)], 1)
    t = Image.fromarray((np.clip(pair, 0, 1) * 255).astype(np.uint8))
    ImageDraw.Draw(t).text((4, 4), f"{s['start'] // 1440:02d}:{s['start'] // 24 % 60:02d} {s['dry']['why']}", fill="white")
    tiles.append(t)
W, H, C = tiles[0].width, tiles[0].height, 3
for k in range(0, len(tiles), 24):
    part = tiles[k:k + 24]
    sheet = Image.new("RGB", (W * C, H * ((len(part) + C - 1) // C)))
    for i, t in enumerate(part):
        sheet.paste(t, ((i % C) * W, (i // C) * H))
    sheet.save(d / f"dry_preview_{k // 24 + 1}.jpg", quality=85)
    print(d / f"dry_preview_{k // 24 + 1}.jpg", len(part))
