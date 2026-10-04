"""Numeric 'scopes' for an exported still: cheap, objective input before Claude looks at pixels."""
from __future__ import annotations

import numpy as np


def still_stats(path) -> dict:
    from PIL import Image

    im = Image.open(path).convert("RGB")
    im.thumbnail((640, 640))
    a = np.asarray(im).astype(np.float32) / 255.0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b  # Rec.709 luma (display-referred)
    mx, mn = a.max(-1), a.min(-1)
    sat = np.where(mx > 1e-4, (mx - mn) / np.maximum(mx, 1e-4), 0.0)
    mid = (y > 0.2) & (y < 0.8)
    shadows, highs = y < 0.2, y > 0.8

    def mean_rgb(mask):
        if not mask.any():
            return None
        return [round(float(c[mask].mean()), 3) for c in (r, g, b)]

    def cast(rgb):
        if not rgb:
            return None
        m = sum(rgb) / 3
        d = {k: round(v - m, 3) for k, v in zip("RGB", rgb)}
        k = max(d, key=lambda q: abs(d[q]))
        return "neutral" if abs(d[k]) < 0.015 else f"{'+' if d[k] > 0 else '-'}{k} {abs(d[k]):.3f}"

    q = np.percentile(y, [1, 10, 50, 90, 99])
    stats = {
        "luma_p1_p10_p50_p90_p99": [round(float(v), 3) for v in q],
        "contrast_p90_minus_p10": round(float(q[3] - q[1]), 3),
        "clipped_pct": round(float((mx >= 0.995).mean() * 100), 2),
        "crushed_pct": round(float((y <= 0.02).mean() * 100), 2),
        "sat_mean": round(float(sat.mean()), 3),
        "sat_p95": round(float(np.percentile(sat, 95)), 3),
        "midtone_rgb": mean_rgb(mid),
        "cast_shadows": cast(mean_rgb(shadows)),
        "cast_midtones": cast(mean_rgb(mid)),
        "cast_highlights": cast(mean_rgb(highs)),
    }
    return stats
