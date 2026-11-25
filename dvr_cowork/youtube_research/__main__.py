r"""/research-youtube engine CLI (read-only YouTube Data API, local SQLite cache, policy-gated metrics).

    $PY = ".venv\Scripts\python.exe"; $R = "-m", "dvr_cowork.youtube_research"
    & $PY @R doctor                                         config, policy, today's quota per bucket, reset (0 requests)
    & $PY @R top --preset africa-wildlife | -q "..." [-q ...] [--ai] [--days 10] [--top 20] [--min 3]   legacy table
    & $PY @R rising --preset africa-wildlife [--days 10] [--top 12] [--min 30]
    & $PY @R competitors --watchlist africa [--days 30] [--top 10]     scan (0 requests when fresh) + report
    & $PY @R outliers --watchlist africa [--topic "lion buffalo"] [--days 30] [--top 10]
    & $PY @R pack --preset africa-wildlife [--refresh]       /create-doc-mov research pack (reused pack_hours)
    & $PY @R selftest                                       offline tests, fake API
  any mode: --cached-only (store only, 0 requests) | --dry-run (requests it would make) | --json | --quiet

Output: a short digest on stdout; full JSON in .work/youtube_research/daily/<UTC day>/<name>.json, Markdown in
.work/youtube_research/reports/<name>.md (packs: .work/youtube_research/packs/<preset>.json).
"""
import argparse
import json
import sqlite3
import sys
import time
import unittest
from datetime import timedelta
from pathlib import Path

from . import engine as E
from . import modes as M


def short(n):
    if n is None:
        return "?"
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1e3:.0f}K" if n >= 1e3 else str(n)


def hms(s):
    if not s:
        return "?"
    h, r = divmod(s, 3600)
    return f"{h}:{r // 60:02d}:{r % 60:02d}" if h else f"{r // 60}:{r % 60:02d}"


def cell(t, k=70):
    t = " ".join((t or "").replace("|", "/").split())
    return t[:k] + "…" if len(t) > k else t


def evidence(x):
    if x.get("evidence") == "observed":
        m = f" mom x{x['momentum']}" if "momentum" in x else ""
        return f"VPH {x['vph']:g} / {x['window_h']:g}h{m}*"
    if x.get("status") == "computed":
        return f"x{x['ratio']:g} vs median {x['baseline_n']} @{x['age_h']}h*"
    return {"raw": "-", "approval_required": "-"}.get(x.get("evidence") or x.get("status"),
                                                       x.get("evidence") or x.get("status") or "-")


def markdown(s, title):
    vn = E.parse(s["as_of_utc"]).astimezone().strftime("%Y-%m-%d %H:%M")
    u = s["api_usage"]
    out = [f"{title} · as_of {vn} (giờ máy) · metrics {s['metrics_status']} · requests search {u['search_queries']} "
           f"/ standard {u['standard']} · cache hits {s['cache_hits']} · {s['returned_count']}/{s['candidates_found']}"]
    if s.get("pack_id"):
        out.append(f"pack_id {s['pack_id']}")
    if s["mode"] == "competitors":
        for c in s["items"]:
            f = c["formats"]
            out.append(f"**{cell(c['channel'], 40)}** ({short(c['subscribers'])} subs) {c['new_uploads']} new: long "
                       f"{f['long'] + f['medium']}, short {f['short']}, live {f['live']} · {c['url']}")
            out += [f"- {v['published_at'][:10]} · {short(v['views'])} · {hms(v['duration_s'])} · {cell(v['title'])} · "
                    f"{v['url']}" for v in c["videos"][:3]]
    elif s["items"]:
        out += ["| # | Views | Đăng | Dài | Kênh | Tiêu đề | Evidence | Link |", "|---|---|---|---|---|---|---|---|"]
        out += [f"| {i} | {short(x['views'])} | {(x['published_at'] or '')[:10]} | {hms(x['duration_s'])} | "
                f"{cell(x['channel'], 25)} | {cell(x['title'])} | {evidence(x)} | {x['url']} |"
                for i, x in enumerate(s["items"], 1)]
    if any("*" in line for line in out[1:]):
        out.append(f"* {M.CUSTOM}")
    out += [f"WARN {w}" for w in s["warnings"]]
    return "\n".join(out)


def save(s, name, title):
    md = markdown(s, title)
    day = E.DATA / "daily" / s["as_of_utc"][:10]
    for d in (day, E.DATA / "reports"):
        d.mkdir(parents=True, exist_ok=True)
    (day / f"{name}.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), "utf-8")
    (E.DATA / "reports" / f"{name}.md").write_text(md + "\n", "utf-8")
    return md


class DryApi(E.Api):
    """Counts the requests a run would make (cache state as is) without calling YouTube or writing the ledger."""

    def call(self, resource, **kw):
        self.used["search" if resource == "search" else "standard"] += 1
        return {"items": []}


def doctor(cfg, db):
    now = E.utcnow()
    api = E.Api(None, db, cfg, offline=True)
    b = cfg.get("budget", {})
    lines = [f"config {E.CONFIG.relative_to(E.ROOT)} hash {E.config_hash(cfg)} · metrics {E.metrics_status(cfg)}",
             f"quota today (PT {E.pt_day(now)}): search {api.spent('search')}/{b.get('search_requests_per_day')}, "
             f"standard {api.spent('standard')}/{b.get('standard_requests_per_day')} · reset {E.reset_local(now)}",
             "presets: " + ", ".join(f"{k} ({len(p['queries'])} q, >= {p.get('min_minutes')} min)"
                                     for k, p in cfg["presets"].items()),
             "watchlists: " + ", ".join(f"{k} {len(v)}" for k, v in cfg.get("watchlists", {}).items()),
             "store: " + ", ".join(f"{t} {db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]}"
                                   for t in ("videos", "snapshots", "channels", "search_cache", "runs"))]
    from ..youtube import TOKENS
    lines.append(f"tokens: {len(list(TOKENS.glob('*.json'))) if TOKENS.exists() else 0} saved")
    return "\n".join(lines)


def run_mode(a, cfg, db):
    if a.cmd == "pack" and not (a.refresh or a.dry_run):
        f = E.DATA / "packs" / f"{a.preset}.json"
        if f.exists():
            p = json.loads(f.read_text("utf-8"))
            fresh = E.parse(p["as_of_utc"]) > E.utcnow() - timedelta(hours=cfg["cache"]["pack_hours"])
            if fresh and p["pack_id"].endswith(E.config_hash(cfg)):
                p["api_usage"], p["cache_hit"] = {"search_queries": 0, "standard": 0}, True
                return p, f"pack {a.preset} (reused)"
    if a.dry_run:  # on an in-memory copy: cache, ledger and uploads_checked_at stay untouched
        mem = sqlite3.connect(":memory:")
        db.backup(mem)
        mem.row_factory = sqlite3.Row
        api = DryApi(object(), mem, cfg)
    elif a.cached_only:
        api = E.Api(None, db, cfg, offline=True)
    else:
        api = E.Api(E.client(), db, cfg)
    if a.cmd == "top":
        min_m = a.min or (20 if a.preset else 3)
        s = M.top(api, cfg, a.query, a.preset, a.days, a.top or (30 if a.preset else 20), a.ai, min_m)
        return s, f"top {a.preset or '; '.join(a.query)}"
    if a.cmd == "rising":
        return M.rising(api, cfg, a.preset, a.days, a.top or 12, a.ai, a.min), f"rising {a.preset}"
    if a.cmd == "pack":
        s = M.pack(api, cfg, a.preset, a.days, a.top or 12)
        if not a.dry_run:
            (E.DATA / "packs").mkdir(parents=True, exist_ok=True)
            (E.DATA / "packs" / f"{a.preset}.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), "utf-8")
        return s, f"pack {a.preset}"
    if not a.cached_only:
        M.competitors_scan(api, cfg, a.watchlist, max(a.days, 30))
    api.offline = True  # the report itself reads the store only
    if a.cmd == "competitors":
        return M.competitors_report(api, cfg, a.watchlist, a.days, a.top or 10), f"competitors {a.watchlist}"
    return M.outliers(api, cfg, a.watchlist, a.topic, a.days, a.top or 10), f"outliers {a.watchlist}"


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")  # titles in any language on the Windows console
    ap = argparse.ArgumentParser(prog="dvr_cowork.youtube_research")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    sub.add_parser("selftest")
    for name in ("top", "rising", "pack", "competitors", "outliers"):
        q = sub.add_parser(name)
        if name in ("top", "rising", "pack"):
            q.add_argument("--preset", required=name != "top")
        if name == "top":
            q.add_argument("-q", "--query", action="append", default=[])
        if name in ("top", "rising"):
            q.add_argument("--ai", action="store_true")
            q.add_argument("--min", type=int, help="shortest video, minutes")
        if name in ("competitors", "outliers"):
            q.add_argument("--watchlist", required=True)
        if name == "outliers":
            q.add_argument("--topic")
        if name == "pack":
            q.add_argument("--refresh", action="store_true")
        q.add_argument("--days", type=int, default=10 if name in ("top", "rising", "pack") else 30)
        q.add_argument("--top", type=int)
        for f in ("--json", "--quiet", "--cached-only", "--dry-run"):
            q.add_argument(f, action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        tests = unittest.defaultTestLoader.discover(str(Path(__file__).parent / "tests"), top_level_dir=str(E.ROOT))
        return 0 if unittest.TextTestRunner(verbosity=1).run(tests).wasSuccessful() else 1
    cfg, db = E.load_config(), E.connect()
    try:
        if a.cmd == "doctor":
            print(doctor(cfg, db))
            return 0
        if a.cmd == "top" and not (a.preset or a.query):
            ap.error("top: --preset or at least one -q")
        if getattr(a, "preset", None) and a.preset not in cfg["presets"]:
            ap.error(f"preset {a.preset!r} not in config: {sorted(cfg['presets'])}")
        E.purge(db, cfg)
        t0 = time.monotonic()
        s, title = run_mode(a, cfg, db)
        ms = int((time.monotonic() - t0) * 1000)
        if a.dry_run:
            u = s["api_usage"]
            print(f"dry-run {title}: would send search {u['search_queries']} + standard >= {u['standard']} requests "
                  f"(+1 videos.list per 50 new ids found); cache hits {s['cache_hits']}")
            return 0
        name = title.split(" (")[0].replace(" ", "_").replace(";", "")[:60]
        md = save(s, name, title)
        with db:
            db.execute("INSERT INTO runs(mode, params, started_at, elapsed_ms, requests, cache_hits, status) "
                       "VALUES(?,?,?,?,?,?,?)", (s["mode"], json.dumps(vars(a)), s["as_of_utc"], ms,
                                                 json.dumps(s["api_usage"]), s["cache_hits"], "ok"))
        if a.json:
            print(json.dumps(s, ensure_ascii=False))
        else:
            print(md.splitlines()[0] if a.quiet else md)
            print(f"({ms} ms) -> .work/youtube_research/reports/{name}.md")
        return 0
    except E.Stop as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
