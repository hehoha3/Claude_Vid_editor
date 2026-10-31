"""MiniMax-Remover logo fill, called by hide_logo.delogo (fill="minimax"); runs in D:\\tools\\minimax_remover\\venv.
Usage: minimax_worker.py <src> <dst> <start_s> <end_s|-1> <x0,y0,x1,y1> [x0,y0,x1,y1 ...]   (boxes in source px)
Only a native-res crop around the logo goes through the model; its pixels replace the logo area (feathered),
everything else is the untouched source, audio copied. 10 s 1080p clip with a small logo ~30 s on the RTX 5060.
Speed limits measured 2026-10-15 (8 GB, Resolve holds ~4.6 GB): attention slows ~10x past ~4300 tokens per window
(17 latent frames x 252 tokens), and VAE + transformer on the GPU together spill into shared memory -> windows sized
to that budget (crossfaded overlap) and three phases with one model on the GPU at a time."""
import json, os, subprocess, sys, time
T = [time.time()]   # phase marks for the timing line

import numpy as np
from scipy.ndimage import binary_dilation, binary_fill_holes, gaussian_filter


def glyphs(luma, box):
    """Logo pixels inside `box` (x0, y0, x1, y1 of the frames `luma` [t, y, x]): Otsu split of the temporal median
    (the logo is the bright, steady part; semi-transparent letters too), holes filled (the dark letters inside the BBC
    squares). A box 3x the logo height made the model repaint background and left a blurred patch (2026-10-31): only
    the glyphs (+ dilation) go to the model. No clear bright part (contrast < 30, or > 70% of the box) -> whole box."""
    x0, y0, x1, y1 = box
    med = np.median(luma[:, y0:y1, x0:x1], axis=0)
    v = np.sort(med.ravel())
    best, thr = -1.0, None
    for t in np.unique(np.percentile(v, np.arange(5, 96, 2.5))):
        lo, hi = v[v < t], v[v >= t]
        if len(lo) and len(hi) and (s := len(lo) * len(hi) * (hi.mean() - lo.mean()) ** 2) > best:
            best, thr, gap = s, t, hi.mean() - lo.mean()
    g = binary_fill_holes(binary_dilation(med >= thr, iterations=1)) if thr is not None and gap >= 30 else None
    return g if g is not None and g.mean() <= 0.7 else np.ones_like(med, bool)


if sys.argv[1:] == ["--selftest"]:
    f = np.random.default_rng(0).integers(0, 120, (6, 40, 120)).astype(np.float32)   # moving dark background
    f[:, 10:30, 10:30] = 240; f[:, 15:25, 15:25] = 60       # one "B" square, dark letter inside
    f[:, 14:26, 40:44] = 230                                 # a thin "E" stroke
    m = glyphs(f, (5, 5, 60, 35))   # box-relative: frame (y, x) -> m[y - 5, x - 5]
    assert m[5:25, 5:25].all() and m[9:21, 30:34].sum() == 0 and m[9:21, 35:39].all(), "glyph mask"
    assert glyphs(np.full((6, 40, 120), 200, np.float32), (5, 5, 60, 35)).all(), "flat box -> whole box"
    sys.exit(print("selftest ok"))

import torch  # noqa: E402

REPO = r"D:\tools\minimax_remover"
sys.path.insert(0, REPO)
from diffusers.models import AutoencoderKLWan  # noqa: E402
from diffusers.schedulers import UniPCMultistepScheduler  # noqa: E402
from transformer_minimax_remover import Transformer3DModel  # noqa: E402

TOKENS, CTX, DILATE, OVER = 4300, 48, 2, 4   # token budget per window, context px around logo, mask grow px, min overlap
# calibration knobs. A/B vs ground truth 2026-10-15 (3 clips, fake logo box on real content): 6 steps 37 s err 8.6,
# 4 st 32 s 8.1, 3 st 29 s 7.9, 2 st 27 s 7.7, texture/motion equal; crop 256x160 26 s but err 10.1 -> kept 336x192
STEPS = int(os.environ.get("MM_STEPS", 2))   # 2 = default since 2026-10-31 (best err in the A/B, ~3 s less)
MIN_W, MIN_H = map(int, os.environ.get("MM_CROP", "336x192").split("x"))
src, dst, start, end, *boxes = sys.argv[1:]
boxes = [[int(v) for v in b.split(",")] for b in boxes]
dev, f16 = "cuda:0", torch.float16

T.append(time.time())
s = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                               "stream=width,height,r_frame_rate", "-of", "json", src], capture_output=True, text=True).stdout)["streams"][0]
W, H, fps = s["width"], s["height"], s["r_frame_rate"]
r16 = lambda v: -(-v // 16) * 16
ux0, uy0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
ux1, uy1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
cw, ch = min(r16(max(ux1 - ux0 + 2 * CTX, MIN_W)), W // 16 * 16), min(r16(max(uy1 - uy0 + 2 * CTX, MIN_H)), H // 16 * 16)
cx = min(max((ux0 + ux1) // 2 - cw // 2, 0), W - cw)
cy = min(max((uy0 + uy1) // 2 - ch // 2, 0), H - ch)
lat_f = max(2, min(17, TOKENS // (cw * ch // 256)))
WIN = 4 * (lat_f - 1) + 1

raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-vf", f"crop={cw}:{ch}:{cx}:{cy}", "-pix_fmt", "rgb24",
                      "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, ch, cw, 3)
n = len(fr)
num, den = map(int, fps.split("/"))
f0 = int(round(float(start) * num / den))
f1 = n if float(end) < 0 else min(n, int(round(float(end) * num / den)) + 1)
seg = fr[f0:f1]
m = len(seg)
if m < 5:
    sys.exit(f"only {m} frames to fill ({f0}-{f1})")
# fewest windows that cover the segment with >= OVER frames overlap, spread evenly (240 f -> 4 x 65, not 5)
k = 1 if m <= WIN else -(-(m - OVER) // (WIN - OVER))
starts = [round(i * (m - WIN) / (k - 1)) for i in range(k)] if k > 1 else [0]
ov = WIN - max(b - a for a, b in zip(starts, starts[1:])) if k > 1 else 0   # crossfade length
mask = np.zeros((ch, cw), bool)
luma = seg[::4].mean(axis=-1) if os.environ.get("MM_MASK") != "box" else None   # MM_MASK=box: whole box (smears)
for b in boxes:
    bx = (max(b[0] - cx, 0), max(b[1] - cy, 0), b[2] - cx, b[3] - cy)
    mask[bx[1]:bx[3], bx[0]:bx[2]] = True if luma is None else glyphs(luma, bx)
mask = binary_dilation(mask, iterations=DILATE)

T.append(time.time())
vae = AutoencoderKLWan.from_pretrained(REPO + r"\vae", torch_dtype=f16).to(dev)
tr = Transformer3DModel.from_pretrained(REPO + r"\transformer", torch_dtype=f16)
sched = UniPCMultistepScheduler.from_pretrained(REPO + r"\scheduler")
mean = torch.tensor(vae.config.latents_mean, device=dev, dtype=f16).view(1, -1, 1, 1, 1)
istd = 1 / torch.tensor(vae.config.latents_std, device=dev, dtype=f16).view(1, -1, 1, 1, 1)

T.append(time.time())
with torch.no_grad():
    lat, b = [], None   # phase 1: encode (VAE alone on the GPU)
    for s0 in starts:
        x = seg[s0:s0 + WIN]
        x = np.concatenate([x, np.repeat(x[-1:], (-(len(x) - 1)) % 4, 0)])        # 4k+1 frames
        img = torch.from_numpy(x).to(dev).permute(3, 0, 1, 2)[None].to(f16) / 127.5 - 1
        msk = torch.from_numpy(mask).to(dev, f16)[None, None, None].expand(1, 3, len(x), ch, cw)
        if b is None:   # static logo: every window has the same mask -> its latent once
            b = (vae.encode(2 * msk - 1).latent_dist.mode() - mean) * istd
        lat.append(((vae.encode(img * (1 - msk)).latent_dist.mode() - mean) * istd, b))
    torch.cuda.synchronize(); T.append(time.time())
    vae.to("cpu"); torch.cuda.empty_cache(); tr.to(dev)
    outs = []  # phase 2: denoise (transformer alone)
    for a, b in lat:
        sched.set_timesteps(STEPS, device=dev)
        z = torch.randn(a.shape, generator=torch.Generator(dev).manual_seed(42), device=dev, dtype=f16)
        for ts in sched.timesteps:
            z = sched.step(tr(hidden_states=torch.cat([z.half(), a, b], 1), timestep=ts.expand(1))[0], ts, z,
                           return_dict=False)[0]
        outs.append(z.half() / istd + mean)
    torch.cuda.synchronize(); T.append(time.time())
    tr.to("cpu"); torch.cuda.empty_cache(); vae.to(dev)
    res = np.zeros((m, ch, cw, 3), np.float32)   # phase 3: decode, crossfade the overlaps
    wsum = np.zeros((m, 1, 1, 1), np.float32)
    for s0, z in zip(starts, outs):
        v = vae.decode(z, return_dict=False)[0][0].float().clamp(-1, 1).add(1).mul(127.5)
        v = v.permute(1, 2, 3, 0).cpu().numpy()[:min(WIN, m - s0)]
        w = np.ones(len(v), np.float32)
        if s0 > 0:
            w[:ov] = np.linspace(0, 1, ov + 2)[1:-1]
        if s0 + len(v) < m:
            w[-ov:] = np.minimum(w[-ov:], np.linspace(1, 0, ov + 2)[1:-1])
        res[s0:s0 + len(v)] += v * w[:, None, None, None]
        wsum[s0:s0 + len(v)] += w[:, None, None, None]
    res /= np.maximum(wsum, 1e-6)

T.append(time.time())
# model pixels on the logo (+6 px, feathered) inside [f0, f1), the source everywhere else
al = gaussian_filter(binary_dilation(mask, iterations=6).astype(np.float32), 3)
al = (np.clip(al * 1.5, 0, 1) * 255).astype(np.uint8)[..., None]
rgba = np.zeros((n, ch, cw, 4), np.uint8)
rgba[f0:f1, ..., :3] = res.astype(np.uint8)
rgba[f0:f1, ..., 3:] = al
r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{cw}x{ch}",
                    "-r", fps, "-i", "-", "-filter_complex", f"[0:v][1:v]overlay={cx}:{cy}:eof_action=pass[v]",
                    "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p",
                    "-fps_mode", "passthrough", "-c:a", "copy", "-map_metadata", "0", "-movflags", "+faststart", dst],
                   input=rgba.tobytes(), capture_output=True)
if r.returncode:
    sys.exit("encode failed: " + r.stderr.decode(errors="replace")[-300:])
T.append(time.time())
d = [b - a for a, b in zip(T, T[1:])]
print(f"crop {cw}x{ch}+{cx}+{cy} frames {f0}-{f1} windows {len(starts)}x{WIN} | " + " ".join(
    f"{k} {v:.1f}s" for k, v in zip(("imports", "read", "load", "encode", "denoise", "decode", "composite"), d)))
