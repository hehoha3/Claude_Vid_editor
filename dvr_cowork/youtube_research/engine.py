"""Research engine: config, SQLite store with policy TTLs, read-only YouTube Data API with a per-bucket quota ledger.

Every mode (modes.py), /doc-edit seo and full-AI `youtube trends` read YouTube through `Api` + this store, so one
search or stats fetch serves all of them. Read-only: search / videos / channels / playlistItems .list, nothing else.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import tomllib
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "research_youtube.toml"
DATA = ROOT / ".work" / "youtube_research"
PT = ZoneInfo("America/Los_Angeles")  # Google's quota day
QUOTA_RE = re.compile(r"quotaExceeded|dailyLimitExceeded|rateLimitExceeded|userRateLimitExceeded")
READ = {"search", "videos", "channels", "playlistItems"}  # .list only: no upload / metadata / thumbnail writes
METADATA_DAYS = 30 # titles / names / tags: refresh or delete after 30 days (III.E.4), whatever the approval
STATS_DAYS_APPROVED = 1095  # 36 months, accepted analytics use case only


class Stop(Exception):
    """Budget reached, quota / rate limit, no token, or --cached-only needs a request: stop, never retry."""


def utcnow():
    return datetime.now(timezone.utc)


def iso(t):
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def secs(s):
    """ISO 8601 duration (PT1H2M3S, P1DT2H) -> seconds; P0D (live / upcoming) -> 0; missing / odd -> None."""
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", s or "")
    if not m:
        return None
    d, h, mi, sec = (int(x or 0) for x in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60 + sec


def num(x):
    """API count -> int; hidden / missing -> None, never 0."""
    return int(x) if x not in (None, "") else None


# ---------------------------------------------------------------- config + policy

def load_config(path=CONFIG):
    return tomllib.loads(Path(path).read_text("utf-8"))


def metrics_status(cfg, today=None):
    """'approved' only with metrics_permission = approved, an approval_ref and a review_by date not passed."""
    p = cfg.get("policy", {})
    if p.get("metrics_permission") != "approved" or not p.get("approval_ref"):
        return "approval_required"
    try:
        if date.fromisoformat(p.get("review_by", "")) < (today or date.today()):
            return "approval_expired"
    except ValueError:
        return "approval_required"
    return "approved"


def metrics_ok(cfg=None):
    """May this client compute metrics (views/day, VPH, ratios) from YouTube API Data? Fail closed."""
    try:
        return metrics_status(cfg or load_config()) == "approved"
    except (OSError, tomllib.TOMLDecodeError):
        return False


def config_hash(cfg):
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:10]


# ---------------------------------------------------------------- store

SCHEMA = [  # list index + 1 = PRAGMA user_version; append, never edit a shipped entry
    """CREATE TABLE videos(video_id TEXT PRIMARY KEY, channel_id TEXT, channel_title TEXT, title TEXT,
         published_at TEXT, duration_s INTEGER, live TEXT, tags TEXT, fetched_at TEXT);
       CREATE INDEX videos_channel ON videos(channel_id, published_at);
       CREATE TABLE snapshots(video_id TEXT, observed_at TEXT, views INTEGER, likes INTEGER, comments INTEGER,
         source TEXT, PRIMARY KEY(video_id, observed_at, source));
       CREATE TABLE channels(channel_id TEXT PRIMARY KEY, handle TEXT, title TEXT, uploads TEXT, subscribers INTEGER,
         video_count INTEGER, fetched_at TEXT, uploads_checked_at TEXT);
       CREATE TABLE search_cache(key TEXT PRIMARY KEY, fetched_at TEXT, ids TEXT);
       CREATE TABLE api_calls(day_pt TEXT, bucket TEXT, method TEXT, n INTEGER, PRIMARY KEY(day_pt, bucket, method));
       CREATE TABLE runs(run_id INTEGER PRIMARY KEY, mode TEXT, params TEXT, started_at TEXT, elapsed_ms INTEGER,
         requests TEXT, cache_hits INTEGER, status TEXT);"""]


def connect(path=None):
    """Open (and migrate) the store; WAL + 30 s busy wait so parallel sessions share it safely."""
    path = Path(path or DATA / "research.sqlite3")
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    v = db.execute("PRAGMA user_version").fetchone()[0]
    if 0 < v < len(SCHEMA) and path.exists():
        shutil.copy2(path, path.with_suffix(f".v{v}.bak"))  # rollback = put this file back
    for i, sql in enumerate(SCHEMA[v:], v + 1):
        db.executescript(sql)
        db.execute(f"PRAGMA user_version={i}")
    return db


def purge(db, cfg, now=None):
    """Policy TTLs: statistics 30 days (36 months when approved), metadata text 30 days, caches 30 days."""
    now = now or utcnow()
    stats_days = STATS_DAYS_APPROVED if metrics_status(cfg) == "approved" else METADATA_DAYS
    meta_cut, stats_cut = iso(now - timedelta(days=METADATA_DAYS)), iso(now - timedelta(days=stats_days))
    with db:
        db.execute("DELETE FROM snapshots WHERE observed_at < ?", (stats_cut,))
        if stats_days > METADATA_DAYS:  # keep ids / dates for baselines, drop the text
            db.execute("UPDATE videos SET title=NULL, channel_title=NULL, tags=NULL WHERE fetched_at < ?", (meta_cut,))
        else:
            db.execute("DELETE FROM videos WHERE fetched_at < ?", (meta_cut,))
        db.execute("DELETE FROM channels WHERE fetched_at < ?", (meta_cut,))
        db.execute("DELETE FROM search_cache WHERE fetched_at < ?", (meta_cut,))
        db.execute("DELETE FROM api_calls WHERE day_pt < ?", ((now - timedelta(days=METADATA_DAYS)).date().isoformat(),))


# ---------------------------------------------------------------- API

def pt_day(t):
    return t.astimezone(PT).date().isoformat()


def reset_local(t):
    """Next 00:00 Pacific time, shown in this PC's time zone."""
    nxt = datetime.combine(t.astimezone(PT).date() + timedelta(days=1), datetime.min.time(), PT)
    return nxt.astimezone().strftime("%Y-%m-%d %H:%M (giờ máy)")


class Api:
    """Read-only YouTube Data API v3: budget per bucket and PT day, ledger in SQLite, circuit breaker on quota.

    yt = googleapiclient resource (or a fake in tests); None + offline=True = --cached-only (any request -> Stop).
    """

    def __init__(self, yt, db, cfg, now=utcnow, offline=False):
        self.yt, self.db, self.cfg, self.now, self.offline = yt, db, cfg, now, offline
        self.used, self.cache_hits = Counter(), 0

    def spent(self, bucket):
        return self.db.execute("SELECT COALESCE(SUM(n),0) FROM api_calls WHERE day_pt=? AND bucket=? AND method!='tripped'",
                               (pt_day(self.now()), bucket)).fetchone()[0]

    def _log(self, bucket, method):
        with self.db:
            self.db.execute("INSERT INTO api_calls VALUES(?,?,?,1) ON CONFLICT DO UPDATE SET n=n+1",
                            (pt_day(self.now()), bucket, method))

    def call(self, resource, **kw):
        if resource not in READ:
            raise ValueError(f"{resource}: research is read-only ({sorted(READ)} .list)")
        bucket = "search" if resource == "search" else "standard"
        if self.offline or self.yt is None:
            raise Stop(f"--cached-only: {resource}.list not cached")
        cap = self.cfg.get("budget", {}).get(f"{bucket}_requests_per_day", 0)
        tripped = self.db.execute("SELECT 1 FROM api_calls WHERE day_pt=? AND bucket=? AND method='tripped'",
                                  (pt_day(self.now()), bucket)).fetchone()
        if tripped or self.spent(bucket) >= cap:
            why = "Google quota hết hôm nay" if tripped else f"budget {bucket} {cap}/ngày đã dùng hết"
            raise Stop(f"{why}; reset {reset_local(self.now())}. Không đổi key/project để vượt.")
        for attempt in (0, 1):
            self._log(bucket, f"{resource}.list")  # a failed request still costs quota
            self.used[bucket] += 1
            try:
                return getattr(self.yt, resource)().list(**kw).execute()
            except Exception as e:
                body = getattr(e, "content", b"") or b""
                if QUOTA_RE.search(body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body)):
                    self._log(bucket, "tripped")
                    raise Stop(f"YouTube {bucket} quota / rate limit; reset {reset_local(self.now())}. Không retry.")
                if hasattr(e, "resp") or attempt:  # an API answer (4xx/5xx) or the 2nd network failure: stop
                    raise
        raise AssertionError("unreachable")

    def usage(self):
        return {"search_queries": self.used["search"], "standard": self.used["standard"]}


# ---------------------------------------------------------------- fetchers (shared cache; a cache hit = no snapshot)

def search_ids(api, q, *, days, duration=None, lang=None, n=50, max_age_h=6, order="viewCount"):
    """search.list ids, cached max_age_h by (query, filters, day window). Offline: whatever is cached, else []."""
    after = (api.now() - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")  # whole days: a stable cache key
    params = {"part": "id", "type": "video", "q": q, "order": order, "maxResults": n, "publishedAfter": after}
    params |= {"videoDuration": duration} if duration else {}
    params |= {"relevanceLanguage": lang} if lang else {}
    key = hashlib.sha256(("v3|" + json.dumps(params, sort_keys=True)).encode()).hexdigest()[:24]
    row = api.db.execute("SELECT ids, fetched_at FROM search_cache WHERE key=?", (key,)).fetchone()
    if row and (api.offline or parse(row["fetched_at"]) > api.now() - timedelta(hours=max_age_h)):
        api.cache_hits += 1
        return json.loads(row["ids"])
    if api.offline:
        return []
    ids = [i["id"]["videoId"] for i in api.call("search", **params).get("items", []) if i.get("id", {}).get("videoId")]
    if not ids:  # never cache an empty answer: a bad query should not block the window
        return ids
    with api.db:
        api.db.execute("INSERT OR REPLACE INTO search_cache VALUES(?,?,?)", (key, iso(api.now()), json.dumps(ids)))
    return ids


def store_video(db, v, now, source="videos.list"):
    sn, st, cd = v.get("snippet", {}), v.get("statistics", {}), v.get("contentDetails", {})
    db.execute("INSERT OR REPLACE INTO videos VALUES(?,?,?,?,?,?,?,?,?)",
               (v["id"], sn.get("channelId"), sn.get("channelTitle"), sn.get("title"), sn.get("publishedAt"),
                secs(cd.get("duration")), sn.get("liveBroadcastContent"), json.dumps(sn.get("tags", []), ensure_ascii=False),
                iso(now)))
    db.execute("INSERT OR IGNORE INTO snapshots VALUES(?,?,?,?,?,?)",
               (v["id"], iso(now), num(st.get("viewCount")), num(st.get("likeCount")), num(st.get("commentCount")), source))


def latest(db, ids):
    """id -> video row + its latest snapshot (views / likes / comments / observed_at), only ids we have."""
    out = {}
    for k in range(0, len(ids), 500):
        chunk = ids[k:k + 500]
        q = (f"SELECT v.*, s.views, s.likes, s.comments, s.observed_at FROM videos v LEFT JOIN snapshots s "
             f"ON s.video_id=v.video_id AND s.observed_at=(SELECT MAX(observed_at) FROM snapshots WHERE video_id=v.video_id) "
             f"WHERE v.video_id IN ({','.join('?' * len(chunk))})")
        out |= {r["video_id"]: dict(r) for r in db.execute(q, chunk)}
    return out


def videos(api, ids, max_age_h=6):
    """Video rows for ids (order kept); stats older than max_age_h refetched in batches of 50 (1 unit each).
    Ids the API no longer returns (private / deleted) are purged, not kept as stale truth."""
    ids = list(dict.fromkeys(ids))
    have = latest(api.db, ids)
    cut = api.now() - timedelta(hours=max_age_h)
    stale = [i for i in ids if i not in have or not have[i]["observed_at"] or parse(have[i]["observed_at"]) < cut]
    api.cache_hits += len(ids) - len(stale)
    if stale and not api.offline:
        for k in range(0, len(stale), 50):
            chunk = stale[k:k + 50]
            items = api.call("videos", part="snippet,statistics,contentDetails", id=",".join(chunk)).get("items", [])
            now, got = api.now(), {v["id"] for v in items}
            with api.db:
                for v in items:
                    store_video(api.db, v, now)
                gone = [i for i in chunk if i not in got]
                api.db.executemany("DELETE FROM videos WHERE video_id=?", [(i,) for i in gone])
                api.db.executemany("DELETE FROM snapshots WHERE video_id=?", [(i,) for i in gone])
        have = latest(api.db, ids)
    return [have[i] for i in ids if i in have]


def snapshots(db, video_id):
    return [(parse(r["observed_at"]), r["views"]) for r in
            db.execute("SELECT observed_at, views FROM snapshots WHERE video_id=? ORDER BY observed_at", (video_id,))]


def channels(api, refs, max_age_days=7):
    """'UC...' / '@handle' refs -> channel rows (id, handle, title, uploads, subscribers ...) + warnings.
    Joined by channel id everywhere; a handle is only an alias resolved with channels.list(forHandle)."""
    warn, rows, cut = [], {}, iso(api.now() - timedelta(days=max_age_days))
    ids = [r for r in refs if r.startswith("UC")]
    for h in (r for r in refs if not r.startswith("UC")):
        hit = api.db.execute("SELECT channel_id FROM channels WHERE lower(handle)=lower(?) AND fetched_at>=?",
                             (h if h.startswith("@") else "@" + h, cut)).fetchone()
        if hit:
            ids.append(hit[0])
        elif not api.offline:
            items = api.call("channels", part="snippet,contentDetails,statistics", forHandle=h).get("items", [])
            if items:
                _store_channel(api, items[0])
                ids.append(items[0]["id"])
                continue
            warn.append(f"{h}: handle not found (changed?) -> put the channel's UC... id in the watchlist")
        else:
            warn.append(f"{h}: not cached")
    ids = list(dict.fromkeys(ids))
    if not ids:
        return [], warn
    fresh = {r["channel_id"] for r in api.db.execute(
        f"SELECT channel_id FROM channels WHERE fetched_at>=? AND channel_id IN ({','.join('?' * len(ids))})", [cut, *ids])}
    stale = [i for i in ids if i not in fresh]
    api.cache_hits += len(ids) - len(stale)
    for k in range(0, len(stale) if not api.offline else 0, 50):
        items = api.call("channels", part="snippet,contentDetails,statistics", id=",".join(stale[k:k + 50])).get("items", [])
        for c in items:
            _store_channel(api, c)
        warn += [f"{i}: channel not returned (closed / wrong id)" for i in set(stale[k:k + 50]) - {c["id"] for c in items}]
    for r in api.db.execute(f"SELECT * FROM channels WHERE channel_id IN ({','.join('?' * len(ids))})", ids):
        rows[r["channel_id"]] = dict(r)
    return [rows[i] for i in ids if i in rows], warn


def _store_channel(api, c):
    sn, st = c.get("snippet", {}), c.get("statistics", {})
    old = api.db.execute("SELECT uploads_checked_at FROM channels WHERE channel_id=?", (c["id"],)).fetchone()
    with api.db:
        api.db.execute("INSERT OR REPLACE INTO channels VALUES(?,?,?,?,?,?,?,?)",
                       (c["id"], sn.get("customUrl"), sn.get("title"),
                        c.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads"),
                        None if st.get("hiddenSubscriberCount") else num(st.get("subscriberCount")),
                        num(st.get("videoCount")), iso(api.now()), old[0] if old else None))


def uploads(api, ch, days=30, max_age_h=6):
    """Ids of a channel's uploads published in the last `days`: the newest 50 of its uploads playlist (1 unit),
    rechecked at most every max_age_h; between checks the ids already stored."""
    since = api.now() - timedelta(days=days)
    checked = parse(ch.get("uploads_checked_at"))
    if api.offline or not ch.get("uploads") or (checked and checked > api.now() - timedelta(hours=max_age_h)):
        api.cache_hits += 1
        return [r[0] for r in api.db.execute("SELECT video_id FROM videos WHERE channel_id=? AND published_at>=?",
                                             (ch["channel_id"], iso(since)))]
    items = api.call("playlistItems", part="contentDetails", playlistId=ch["uploads"], maxResults=50).get("items", [])
    with api.db:
        api.db.execute("UPDATE channels SET uploads_checked_at=? WHERE channel_id=?", (iso(api.now()), ch["channel_id"]))
    return [i["contentDetails"]["videoId"] for i in items
            if (p := parse(i["contentDetails"].get("videoPublishedAt"))) and p >= since]


def search_rows(yt, q, *, days, duration, lang=None, n=25, max_age_h=168, db=None, now=utcnow):
    """For /doc-edit seo and full-AI trends: [{title, channel, views, days, tags}] + requests used (0 = cached).
    Same shape as their old private search(); one shared cache + ledger instead of three."""
    cfg = load_config()
    db = db or connect()
    purge(db, cfg, now())
    api = Api(yt, db, cfg, now)
    ids = search_ids(api, q, days=days, duration=duration, lang=lang, n=n, max_age_h=max_age_h)
    rows = videos(api, ids, max_age_h)
    t = now()
    return [{"title": r["title"], "channel": r["channel_title"], "views": r["views"] or 0,
             "days": max(1, (t - parse(r["published_at"])).days), "tags": json.loads(r["tags"] or "[]")}
            for r in rows if r["title"]], sum(api.used.values())


def client():
    """API client on any saved OAuth token (search needs no particular channel)."""
    from googleapiclient.discovery import build

    from ..youtube import TOKENS, saved
    for p in sorted(TOKENS.glob("*.json")) if TOKENS.exists() else []:
        if c := saved(p):
            return build("youtube", "v3", credentials=c, cache_discovery=False)
    raise Stop("no valid YouTube token: .venv/Scripts/python.exe -m dvr_cowork youtube login --key Chann_N")
