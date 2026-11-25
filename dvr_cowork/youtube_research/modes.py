"""Modes of /research-youtube: top (legacy table), rising, competitors scan / report, outliers, pack (/create-doc-mov).

Every mode returns one summary dict (schema 1.0) -> report.write() saves JSON + Markdown and prints a short digest.
Metrics (VPH, growth, momentum, outlier ratio) are computed only when engine.metrics_ok(); otherwise items carry the
raw API numbers with evidence "raw" and metrics_status "approval_required" (YouTube Developer Policies III.E.4.h).
"""
from __future__ import annotations

import json
import re
from datetime import timedelta
from statistics import median

from . import engine as E

SHORT_S, LONG_S = 180, 20 * 60  # Shorts run up to 3 min; YouTube's "long" search bucket starts at 20 min
CUSTOM = "custom metric computed by this tool from YouTube API data, not a YouTube number"
# ponytail: keyword heuristic; YouTube's "altered or synthetic" label is not in the API, unlabelled AI videos slip through
AI_RE = re.compile(r"(?i)(\bA\.?I\b|#ai\w*|ai[- ]?(generated|made|art|video|film|animation)|\bveo\s?\d?\b|kling|"
                   r"\bsora\b|midjourney|runway\s?(gen|ml)|hailuo|minimax|\bluma\b|pika\s?labs|seedance|wan\s?2)")


def fmt(v):
    """long | medium | short | live | unknown: never compare a Short or a stream with a documentary."""
    if v.get("live") not in (None, "none"):
        return "live"
    s = v.get("duration_s")
    if not s:
        return "live" if s == 0 else "unknown"  # P0D = live / upcoming
    return "short" if s <= SHORT_S else "long" if s >= LONG_S else "medium"


def is_ai(v):
    return bool(AI_RE.search(" ".join([v.get("title") or "", *json.loads(v.get("tags") or "[]")])))


def buckets(min_m):
    return ("long",) if min_m >= 20 else ("medium", "long")


def item(v, **extra):
    return {"video_id": v["video_id"], "url": f"https://youtu.be/{v['video_id']}", "title": v["title"],
            "channel_id": v["channel_id"], "channel": v["channel_title"], "published_at": v["published_at"],
            "duration_s": v["duration_s"], "format": fmt(v), "views": v["views"], "fetched_at": v["observed_at"]} | extra


def keep(v, since, min_s, exclude=None, exclude_channels=(), ai=False):
    pub = E.parse(v.get("published_at"))
    return bool(v.get("title") and pub and pub >= since and (v.get("duration_s") or 0) >= min_s
                and fmt(v) not in ("live", "short") and v.get("channel_id") not in exclude_channels
                and not (exclude and re.search(exclude, v["title"])) and (not ai or is_ai(v)))


# ---------------------------------------------------------------- metrics (pure; callers check permission first)

def hours(a, b):
    return (b - a).total_seconds() / 3600


def growth(snaps, min_gap_h=6, target_h=24):
    """[(observed_at, views)] -> observed VPH over the real interval nearest target_h, momentum when a previous
    interval exists. Never labels a window it did not observe; views going down = invalid."""
    s = sorted((t, v) for t, v in snaps if t and v is not None)
    if len(s) < 2:
        return {"evidence": "insufficient_history", "snapshots": len(s)}
    t2, v2 = s[-1]
    earlier = [(t, v) for t, v in s[:-1] if hours(t, t2) >= min_gap_h]
    if not earlier:
        return {"evidence": "insufficient_history", "snapshots": len(s), "note": f"snapshots < {min_gap_h} h apart"}
    t1, v1 = min(earlier, key=lambda x: abs(hours(x[0], t2) - target_h))
    if v2 < v1:
        return {"evidence": "invalid", "note": "views went down between snapshots (YouTube recount)"}
    h = hours(t1, t2)
    out = {"evidence": "observed", "vph": round((v2 - v1) / h, 1), "growth": v2 - v1, "window_h": round(h, 1),
           "from": E.iso(t1), "to": E.iso(t2), "metric_label": CUSTOM}
    prev = [(t, v) for t, v in s if t < t1 and hours(t, t1) >= min_gap_h and v <= v1]
    if prev:
        t0, v0 = min(prev, key=lambda x: abs(hours(x[0], t1) - h))
        if v1 > v0:
            out["momentum"] = round(out["vph"] / ((v1 - v0) / hours(t0, t1)), 2)
    return out


def views_at_age(snaps, published, age_h, tol=0.25):
    """Views of the snapshot taken closest to age_h after publishing, within +-tol of it; else None."""
    best = None
    for t, v in snaps:
        if t and v is not None and abs(hours(published, t) - age_h) <= tol * age_h:
            if best is None or abs(hours(published, t) - age_h) < abs(hours(published, best[0]) - age_h):
                best = (t, v)
    return best[1] if best else None


def outlier(target, peers, min_n=8, tol=0.25):
    """target / peers = {"published": datetime, "snaps": [(t, views)], "format": str}. Baseline = median views of
    same-format peers at the target's age (+-tol); the target never sits in its own baseline."""
    snaps = sorted((t, v) for t, v in target["snaps"] if t and v is not None)
    if not snaps or not target.get("published"):
        return {"status": "views_missing"}
    t, views = snaps[-1]
    age = hours(target["published"], t)
    if age <= 0:
        return {"status": "dates_invalid"}
    vals = [x for p in peers if p is not target and p["format"] == target["format"] and p.get("published")
            and (x := views_at_age(p["snaps"], p["published"], age, tol)) is not None]
    if len(vals) < min_n:
        return {"status": "baseline_insufficient", "baseline_n": len(vals), "age_h": round(age)}
    base = median(vals)
    if base <= 0:
        return {"status": "baseline_zero", "baseline_n": len(vals)}
    r = views / base
    return {"status": "computed", "ratio": round(r, 2), "level": "high" if r >= 5 else "medium" if r >= 2 else "normal",
            "baseline": round(base), "baseline_n": len(vals), "age_h": round(age), "metric_label": CUSTOM}


# ---------------------------------------------------------------- modes

def summary(mode, api, cfg, items, warnings=(), **extra):
    return {"schema_version": "1.0", "mode": mode, "as_of_utc": E.iso(api.now()), "source": "youtube_data_api",
            "metrics_status": E.metrics_status(cfg), "candidates_found": extra.pop("found", len(items)),
            "returned_count": len(items), "cache_hit": not any(api.used.values()), "api_usage": api.usage(),
            "cache_hits": api.cache_hits, "items": items, "warnings": list(warnings)} | extra


def preset_ids(api, cfg, preset, days, min_m, ai=False):
    p = cfg["presets"][preset]
    qs = [q + " AI" if ai and i % 2 else q for i, q in enumerate(p["queries"])]
    ids = [i for q in qs for d in buckets(min_m)
           for i in E.search_ids(api, q, days=days, duration=d, max_age_h=cfg["cache"]["search_hours"])]
    return ids, p


def top(api, cfg, queries=None, preset=None, days=10, n=20, ai=False, min_m=3):
    """Legacy: most viewed (raw count, YouTube's own number) of a topic published in the last `days`."""
    if preset:
        ids, _ = preset_ids(api, cfg, preset, days, min_m, ai)
    else:
        ids = [i for q in queries for d in buckets(min_m)
               for i in E.search_ids(api, q, days=days, duration=d, max_age_h=cfg["cache"]["search_hours"])]
    vs = E.videos(api, ids, cfg["cache"]["stats_hours"])
    since = api.now() - timedelta(days=days)
    rows = sorted((v for v in vs if keep(v, since, min_m * 60, ai=ai)), key=lambda v: -(v["views"] or 0))
    return summary("top", api, cfg, [item(v) for v in rows[:n]], found=len(set(ids)), days=days, min_minutes=min_m)


def rising(api, cfg, preset, days=10, n=20, ai=False, min_m=None):
    """Candidates of a niche: preset searches + the preset's watchlist uploads. With approval: observed VPH first."""
    min_m = min_m or cfg["presets"][preset].get("min_minutes", 30)
    ids, p = preset_ids(api, cfg, preset, days, min_m, ai)
    warn = []
    if refs := cfg.get("watchlists", {}).get(p.get("watchlist", ""), []):
        chans, warn = E.channels(api, refs, cfg["cache"]["channel_days"])
        ids += [i for c in chans for i in E.uploads(api, c, days, cfg["cache"]["uploads_hours"])]
    vs = E.videos(api, ids, cfg["cache"]["stats_hours"])
    since = api.now() - timedelta(days=days)
    rows = [v for v in vs if keep(v, since, min_m * 60, p.get("exclude"), cfg.get("exclude_channels", []), ai)]
    ok = E.metrics_status(cfg) == "approved"
    items = []
    for v in rows:
        ev = growth(E.snapshots(api.db, v["video_id"])) if ok else {"evidence": "raw"}
        items.append(item(v, niche=preset, **ev))
    rank = {"observed": 0, "insufficient_history": 1, "invalid": 2, "raw": 1}
    items.sort(key=lambda x: (rank[x["evidence"]], -(x.get("vph") or 0), -(x["views"] or 0)))
    if not ok:
        warn.append("VPH / growth need YouTube approval (config policy); sorted by raw views. Licensed provider "
                    "numbers (vidIQ) only when the user asks.")
    return summary("rising", api, cfg, items[:n], warn, found=len(set(ids)), preset=preset, days=days, min_minutes=min_m)


def watch_channels(api, cfg, wl):
    refs = cfg.get("watchlists", {}).get(wl)
    if refs is None:
        raise E.Stop(f"watchlist {wl!r} not in config/research_youtube.toml [watchlists]")
    if not refs:
        raise E.Stop(f"watchlist {wl!r} is empty: add competitor channels (UC... id or @handle) in "
                     f"config/research_youtube.toml [watchlists] {wl} = [...]")
    return E.channels(api, refs, cfg["cache"]["channel_days"])


def competitors_scan(api, cfg, wl, days=30):
    """New uploads of each watchlist channel + fresh stats of the ones in the window. Fresh = 0 requests."""
    chans, warn = watch_channels(api, cfg, wl)
    ids = [i for c in chans for i in E.uploads(api, c, days, cfg["cache"]["uploads_hours"])]
    E.videos(api, ids, cfg["cache"]["stats_hours"])
    return summary("competitors_scan", api, cfg, [], warn, found=len(ids), watchlist=wl, channels=len(chans))


def competitors_report(api, cfg, wl, days=30, n=10):
    """From the store only (api offline): each channel's uploads in the window, long-form first. No ranking formula."""
    chans, warn = watch_channels(api, cfg, wl)
    since = E.iso(api.now() - timedelta(days=days))
    items = []
    for c in chans:
        ids = [r[0] for r in api.db.execute("SELECT video_id FROM videos WHERE channel_id=? AND published_at>=? "
                                            "ORDER BY published_at DESC", (c["channel_id"], since))]
        vs = list(E.latest(api.db, ids).values())
        forms = {f: sum(fmt(v) == f for v in vs) for f in ("long", "medium", "short", "live")}
        long_ = sorted((v for v in vs if fmt(v) in ("long", "medium")), key=lambda v: v["published_at"], reverse=True)
        items.append({"channel_id": c["channel_id"], "channel": c["title"], "handle": c["handle"],
                      "url": f"https://www.youtube.com/channel/{c['channel_id']}", "subscribers": c["subscribers"],
                      "new_uploads": len(vs), "formats": forms, "videos": [item(v) for v in long_[:n]]})
    return summary("competitors", api, cfg, items, warn, watchlist=wl, days=days)


def outliers(api, cfg, wl, topic=None, days=30, n=10):
    """Videos far above their own channel's usual views at the same age (approved only); else raw candidates."""
    chans, warn = watch_channels(api, cfg, wl)
    ok = E.metrics_status(cfg) == "approved"
    since = api.now() - timedelta(days=days)
    words = [w for w in re.findall(r"\w+", (topic or "").lower()) if w not in ("vs", "and", "the")]
    items = []
    for c in chans:
        ids = [r[0] for r in api.db.execute("SELECT video_id FROM videos WHERE channel_id=?", (c["channel_id"],))]
        vs = [v for v in E.latest(api.db, ids).values() if fmt(v) in ("long", "medium")]
        peers = [{"v": v, "published": E.parse(v["published_at"]), "format": fmt(v),
                  "snaps": E.snapshots(api.db, v["video_id"]) if ok else []} for v in vs]
        for p in peers:
            v = p["v"]
            if not (p["published"] and p["published"] >= since and v["title"]):
                continue
            if words and not all(w in v["title"].lower() for w in words):
                continue
            ev = outlier(p, peers) if ok else {"status": "approval_required"}
            items.append(item(v, method="median views of same-channel same-format videos at the same age",
                              **ev))
    if ok:
        items.sort(key=lambda x: (x["status"] != "computed", -(x.get("ratio") or 0)))
    else:
        items.sort(key=lambda x: -(x["views"] or 0))
        warn.append("outlier ratio needs YouTube approval (config policy): these are recent uploads by raw views, "
                    "candidate_for_manual_review. vidIQ outliers (licensed provider) only when the user asks.")
    return summary("outliers", api, cfg, items[:n], warn, found=len(items), watchlist=wl, topic=topic, days=days)


def pack(api, cfg, preset, days=10, n=12):
    """/create-doc-mov research pack: rising candidates (+ the watchlist's long-form uploads) of one niche."""
    s = rising(api, cfg, preset, days, n)
    s["mode"], s["pack_id"] = "pack", f"{preset}@{s['as_of_utc']}#{E.config_hash(cfg)}"
    return s
