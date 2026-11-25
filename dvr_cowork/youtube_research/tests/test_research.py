"""Offline tests: fake YouTube API, fake clock, temp SQLite. No token, no network, no Resolve.

    .venv/Scripts/python.exe -m dvr_cowork.youtube_research selftest
"""
import argparse
import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dvr_cowork.youtube_research import __main__ as cli
from dvr_cowork.youtube_research import engine as E
from dvr_cowork.youtube_research import modes as M

T0 = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
CFG = E.load_config()  # the shipped config: unverified, real presets
APPROVED = copy.deepcopy(CFG) | {"policy": {"metrics_permission": "approved", "approval_ref": "case-123",
                                             "review_by": "2099-01-01"}}


class QuotaError(Exception):
    def __init__(self, reason):
        self.resp, self.content = {"status": "403"}, json.dumps({"error": {"errors": [{"reason": reason}]}}).encode()


class FakeYT:
    """search / videos / channels / playlistItems .list over in-memory data; records every request."""

    def __init__(self):
        self.vids, self.search_map, self.chans, self.calls, self.fail = {}, {}, {}, [], None

    def add(self, vid, views, title="Lion pride survival documentary", ch="UCa", age_h=48, dur="PT45M", live="none"):
        self.vids[vid] = dict(views=views, title=title, ch=ch, pub=E.iso(T0 - timedelta(hours=age_h)), dur=dur, live=live)

    def __getattr__(self, name):
        if name not in ("search", "videos", "channels", "playlistItems"):
            raise AttributeError(name)
        return lambda: self

    def list(self, **kw):
        self.calls.append(kw)
        return self

    def execute(self):
        kw = self.calls[-1]
        if self.fail:
            e, self.fail = self.fail, None
            raise e
        if "q" in kw:
            return {"items": [{"id": {"videoId": i}} for i in self.search_map.get(kw["q"], [])]}
        if "playlistId" in kw:
            ch = kw["playlistId"].replace("UU", "UC", 1)
            return {"items": [{"contentDetails": {"videoId": i, "videoPublishedAt": v["pub"]}}
                              for i, v in self.vids.items() if v["ch"] == ch]}
        if kw.get("forHandle") or (kw.get("id", "").startswith("UC")):
            want = [kw["forHandle"]] if kw.get("forHandle") else kw["id"].split(",")
            return {"items": [{"id": cid, "snippet": {"title": c["title"], "customUrl": c["handle"]},
                               "contentDetails": {"relatedPlaylists": {"uploads": "UU" + cid[2:]}},
                               "statistics": {"subscriberCount": str(c["subs"]), "videoCount": "100"}}
                              for cid, c in self.chans.items() if cid in want or c["handle"] in want]}
        return {"items": [{"id": i, "snippet": {"title": v["title"], "channelId": v["ch"], "channelTitle": "Chan " + v["ch"],
                                                "publishedAt": v["pub"], "liveBroadcastContent": v["live"], "tags": ["lion"]},
                           "statistics": {} if v["views"] is None else {"viewCount": str(v["views"])},
                           "contentDetails": {"duration": v["dur"]}}
                          for i in kw["id"].split(",") if (v := self.vids.get(i))]}

    def n(self, key):
        return sum(key in c for c in self.calls)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = E.connect(Path(self.tmp.name) / "r.sqlite3")
        self.yt, self.t = FakeYT(), T0

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def api(self, cfg=CFG, **kw):
        return E.Api(self.yt, self.db, cfg, lambda: self.t, **kw)


class Parsing(unittest.TestCase):
    def test_durations_and_formats(self):
        self.assertEqual([E.secs(x) for x in ("PT3M", "PT30M", "PT1H", "P0D", None, "bad")], [180, 1800, 3600, 0, None, None])
        self.assertEqual([M.fmt({"duration_s": s, "live": "none"}) for s in (180, 600, 1800, 0, None)],
                         ["short", "medium", "long", "live", "unknown"])
        self.assertEqual(M.fmt({"duration_s": 3600, "live": "upcoming"}), "live")
        self.assertIsNone(E.num(None))
        self.assertEqual(E.num("0"), 0)

    def test_ai_keyword_and_markdown_cells(self):
        self.assertTrue(M.is_ai({"title": "Jaguar vs Anaconda | AI Wildlife"}))
        self.assertTrue(M.is_ai({"title": "x", "tags": json.dumps(["Veo 3"])}))
        self.assertFalse(M.is_ai({"title": "Amazon Rainforest 4K - Wild Animals"}))
        self.assertEqual(cli.cell("Sư tử | Đêm\nsavanna"), "Sư tử / Đêm savanna")
        self.assertEqual(cli.short(1_234_567), "1.2M")
        self.assertEqual(cli.short(None), "?")
        self.assertEqual(cli.hms(3723), "1:02:03")


class Policy(unittest.TestCase):
    def test_fail_closed(self):
        self.assertEqual(E.metrics_status(CFG), "approval_required")
        self.assertEqual(E.metrics_status({"policy": {"metrics_permission": "approved"}}), "approval_required")  # no ref
        self.assertEqual(E.metrics_status(APPROVED), "approved")
        old = copy.deepcopy(APPROVED)
        old["policy"]["review_by"] = "2020-01-01"
        self.assertEqual(E.metrics_status(old), "approval_expired")
        self.assertFalse(E.metrics_ok(CFG))

    def test_no_write_endpoint_nas_or_pushed(self):
        api = E.Api(FakeYT(), None, CFG)
        for res in ("thumbnails", "commentThreads", "playlists"):
            with self.assertRaises(ValueError):
                api.call(res)
        src = "".join(p.read_text("utf-8") for p in Path(E.__file__).parent.glob("*.py"))
        for bad in (".insert(", ".update(", ".delete(", ".set(", "Z:", "_pushed", "MediaFileUpload"):
            self.assertNotIn(bad, src, bad)


class Store(Base):
    def test_dedup_cache_and_no_fake_snapshot(self):
        for i in range(4):
            self.yt.add(f"v{i}", 1000 * (i + 1))
        self.yt.search_map = {q: ["v0", "v1", "v2", "v3"] for q in CFG["presets"]["africa-wildlife"]["queries"]}
        s = M.rising(self.api(), CFG, "africa-wildlife")
        self.assertEqual([x["video_id"] for x in s["items"]], ["v3", "v2", "v1", "v0"])  # raw views, unique ids
        self.assertEqual(s["api_usage"], {"search_queries": 4, "standard": 1})
        snaps = self.db.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        self.t += timedelta(hours=2)
        s2 = M.rising(self.api(), CFG, "africa-wildlife")
        self.assertEqual(s2["api_usage"], {"search_queries": 0, "standard": 0})
        self.assertTrue(s2["cache_hit"])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0], snaps)
        s3 = M.rising(self.api(), CFG, "africa-wildlife", days=20)  # other window = other cache key
        self.assertEqual(s3["api_usage"]["search_queries"], 4)

    def test_search_drift_excluded(self):
        self.yt.add("shop", 9_000_000, "Amazon Prime Day shopping haul documentary")
        self.yt.add("jungle", 5000, "Amazon rainforest jaguar documentary")
        self.yt.search_map = {CFG["presets"]["amazon-wildlife"]["queries"][0]: ["shop", "jungle"]}
        s = M.rising(self.api(), CFG, "amazon-wildlife")
        self.assertEqual([x["video_id"] for x in s["items"]], ["jungle"])

    def test_shorts_live_missing_views_and_deleted(self):
        self.yt.add("long", None)
        self.yt.add("short", 10, dur="PT50S")
        self.yt.add("live", 10, dur="P0D", live="live")
        api = self.api()
        rows = {r["video_id"]: r for r in E.videos(api, ["long", "short", "live"])}
        self.assertIsNone(rows["long"]["views"])  # hidden, not 0
        self.assertEqual({k: M.fmt(v) for k, v in rows.items()}, {"long": "long", "short": "short", "live": "live"})
        del self.yt.vids["long"]  # went private / deleted
        self.t += timedelta(hours=7)
        self.assertEqual([r["video_id"] for r in E.videos(self.api(), ["long", "short"])], ["short"])
        self.assertIsNone(self.db.execute("SELECT 1 FROM snapshots WHERE video_id='long'").fetchone())

    def test_ttl_purge(self):
        self.yt.add("v", 5)
        E.videos(self.api(), ["v"])
        later = T0 + timedelta(days=31)
        E.purge(self.db, APPROVED, later)  # approved: stats stay, text goes
        self.assertEqual(self.db.execute("SELECT title, views FROM videos JOIN snapshots USING(video_id)").fetchone()[:],
                         (None, 5))
        E.purge(self.db, CFG, later)  # unverified: 30 days, everything
        self.assertEqual(self.db.execute("SELECT (SELECT COUNT(*) FROM videos)+(SELECT COUNT(*) FROM snapshots)").fetchone()[0], 0)

    def test_handle_change_keeps_one_channel(self):
        self.yt.chans = {"UCa": {"title": "Wild A", "handle": "@wilda", "subs": 1000}}
        chans, _ = E.channels(self.api(), ["@wilda"])
        self.yt.chans["UCa"]["handle"] = "@wildnew"
        self.t += timedelta(days=8)
        chans2, warn = E.channels(self.api(), ["UCa", "@wilda"])
        self.assertEqual([c["channel_id"] for c in chans2], ["UCa"])
        self.assertTrue(any("@wilda" in w for w in warn))
        self.assertEqual(self.db.execute("SELECT COUNT(*), MAX(handle) FROM channels").fetchone()[:], (1, "@wildnew"))


class Quota(Base):
    def test_search_budget_stops_standard_goes_on(self):
        cfg = copy.deepcopy(CFG)
        cfg["budget"]["search_requests_per_day"] = 1
        api = self.api(cfg)
        E.search_ids(api, "a", days=10)
        with self.assertRaisesRegex(E.Stop, "budget search"):
            E.search_ids(api, "b", days=10)
        self.yt.add("v", 1)
        self.assertEqual(len(E.videos(api, ["v"])), 1)

    def test_google_quota_trips_breaker_no_retry(self):
        api = self.api()
        self.yt.fail = QuotaError("quotaExceeded")
        with self.assertRaisesRegex(E.Stop, "quota"):
            E.search_ids(api, "a", days=10)
        n = len(self.yt.calls)
        with self.assertRaisesRegex(E.Stop, "quota"):
            E.search_ids(self.api(), "b", days=10)  # a new run the same PT day: no request at all
        self.assertEqual(len(self.yt.calls), n)
        self.assertEqual(n, 1)

    def test_network_error_retried_once(self):
        self.yt.fail = TimeoutError("net")
        self.assertEqual(E.search_ids(self.api(), "a", days=10), [])
        self.assertEqual(len(self.yt.calls), 2)

    def test_reset_is_pacific_midnight(self):
        self.assertEqual(E.pt_day(datetime(2026, 11, 20, 7, 59, tzinfo=timezone.utc)), "2026-11-19")
        self.assertEqual(E.pt_day(datetime(2026, 11, 20, 8, 0, tzinfo=timezone.utc)), "2026-11-20")

    def test_cached_only_makes_no_request(self):
        api = self.api(offline=True)
        self.assertEqual(E.search_ids(api, "a", days=10), [])
        self.assertEqual(self.yt.calls, [])


def ts(h):
    return T0 + timedelta(hours=h)


class Growth(unittest.TestCase):
    def test_levels(self):
        self.assertEqual(M.growth([(ts(0), 100)])["evidence"], "insufficient_history")
        g = M.growth([(ts(0), 1000), (ts(24), 13000)])
        self.assertEqual((g["evidence"], g["vph"], g["window_h"], g["growth"]), ("observed", 500.0, 24.0, 12000))
        self.assertEqual(M.growth([(ts(0), 1), (ts(3), 900)])["evidence"], "insufficient_history")  # 3 h != 24 h
        self.assertEqual(M.growth([(ts(0), 900), (ts(24), 800)])["evidence"], "invalid")
        self.assertEqual(M.growth([(ts(0), None), (ts(24), 800)])["evidence"], "insufficient_history")
        g = M.growth([(ts(0), 0), (ts(24), 2400), (ts(48), 7200)])  # 100/h then 200/h
        self.assertEqual((g["vph"], g["momentum"]), (200.0, 2.0))

    def test_small_rising_beats_big_flat_only_with_approval(self):
        snaps = {"small": [(ts(0), 10_000), (ts(24), 15_000)], "big": [(ts(0), 100_000), (ts(24), 100_100)]}
        self.assertGreater(M.growth(snaps["small"])["vph"], M.growth(snaps["big"])["vph"])


class Rising(Base):
    def run2(self, cfg):
        self.yt.add("small", 10_000)
        self.yt.add("big", 100_000)
        self.yt.search_map = {CFG["presets"]["africa-wildlife"]["queries"][0]: ["small", "big"]}
        M.rising(self.api(cfg), cfg, "africa-wildlife")
        self.yt.vids["small"]["views"], self.yt.vids["big"]["views"] = 15_000, 100_100
        self.t += timedelta(hours=24)
        return M.rising(self.api(cfg), cfg, "africa-wildlife")

    def test_unverified_has_no_metric(self):
        s = self.run2(CFG)
        self.assertEqual(s["metrics_status"], "approval_required")
        self.assertEqual([x["video_id"] for x in s["items"]], ["big", "small"])
        self.assertTrue(all(x["evidence"] == "raw" and "vph" not in x for x in s["items"]))
        self.assertTrue(any("approval" in w for w in s["warnings"]))

    def test_approved_ranks_observed_growth(self):
        s = self.run2(APPROVED)
        self.assertEqual([x["video_id"] for x in s["items"]], ["small", "big"])
        x = s["items"][0]
        self.assertEqual((x["evidence"], x["vph"], x["window_h"]), ("observed", 208.3, 24.0))
        self.assertIn("not a YouTube number", x["metric_label"])


class Outlier(unittest.TestCase):
    def peer(self, views, fmt="long"):
        pub = ts(-1000)
        return {"published": pub, "format": fmt, "snaps": [(pub + timedelta(hours=48), views)]}

    def target(self, views, fmt="long"):
        return {"published": ts(0), "format": fmt, "snaps": [(ts(48), views)]}

    def test_ratio_insufficient_zero_missing(self):
        peers = [self.peer(3000) for _ in range(8)]
        r = M.outlier(self.target(30_000), peers)
        self.assertEqual((r["status"], r["ratio"], r["level"], r["baseline_n"]), ("computed", 10.0, "high", 8))
        big = [self.peer(1_000_000) for _ in range(8)]
        self.assertEqual(M.outlier(self.target(200_000), big)["level"], "normal")  # big views, under its baseline
        self.assertEqual(M.outlier(self.target(5), peers[:7])["status"], "baseline_insufficient")
        self.assertEqual(M.outlier(self.target(5), [self.peer(0) for _ in range(8)])["status"], "baseline_zero")
        self.assertEqual(M.outlier(self.target(5), [self.peer(9, "short") for _ in range(8)])["status"],
                         "baseline_insufficient")  # shorts never baseline a documentary
        self.assertEqual(M.outlier({"published": ts(0), "format": "long", "snaps": [(ts(48), None)]}, peers)["status"],
                         "views_missing")
        self.assertEqual(M.outlier({"published": ts(50), "format": "long", "snaps": [(ts(48), 9)]}, peers)["status"],
                         "dates_invalid")
        t = self.target(30_000)
        self.assertEqual(M.outlier(t, [t] * 8 + peers[:7])["status"], "baseline_insufficient")  # not its own baseline

    def test_age_window_mismatch(self):
        far = [{"published": ts(-1000), "format": "long", "snaps": [(ts(-1000 + 400), 5)]} for _ in range(8)]
        self.assertEqual(M.outlier(self.target(30_000), far)["status"], "baseline_insufficient")


class Competitors(Base):
    def setUp(self):
        super().setUp()
        self.yt.chans = {"UCa": {"title": "Wild A", "handle": "@wilda", "subs": 5000},
                         "UCb": {"title": "Quiet B", "handle": "@quietb", "subs": 10}}
        self.yt.add("doc", 900, ch="UCa")
        self.yt.add("sh", 50, ch="UCa", dur="PT40S")
        self.cfg = copy.deepcopy(CFG)
        self.cfg["watchlists"]["africa"] = ["UCa", "@quietb"]

    def test_scan_then_reports_cost_nothing(self):
        M.competitors_scan(self.api(), self.cfg, "africa")
        n = len(self.yt.calls)
        for _ in range(2):
            self.t += timedelta(minutes=30)
            api = self.api()
            M.competitors_scan(api, self.cfg, "africa")
            api.offline = True
            s = M.competitors_report(api, self.cfg, "africa")
        self.assertEqual(len(self.yt.calls), n)
        a, b = s["items"]
        self.assertEqual((a["new_uploads"], a["formats"]["short"], [v["video_id"] for v in a["videos"]]), (2, 1, ["doc"]))
        self.assertEqual((b["channel"], b["new_uploads"]), ("Quiet B", 0))  # no upload is not an error

    def test_outliers_unverified_lists_candidates(self):
        M.competitors_scan(self.api(), self.cfg, "africa")
        s = M.outliers(self.api(offline=True), self.cfg, "africa", topic="lion")
        self.assertEqual([(x["video_id"], x["status"]) for x in s["items"]], [("doc", "approval_required")])
        self.assertTrue(all("ratio" not in x for x in s["items"]))

    def test_empty_watchlist_explains(self):
        with self.assertRaisesRegex(E.Stop, "empty"):
            M.competitors_report(self.api(), CFG, "africa")


class Cli(Base):
    def test_dry_run_leaves_store_untouched_and_top_has_no_per_day(self):
        self.yt.add("v", 7000)
        self.yt.search_map = {"lion": ["v"]}
        before = list(self.db.iterdump())
        a = argparse.Namespace(cmd="rising", preset="africa-wildlife", dry_run=True, cached_only=False, refresh=False,
                               days=10, top=None, ai=False, min=None)
        s, _ = cli.run_mode(a, CFG, self.db)
        self.assertEqual(s["api_usage"], {"search_queries": 4, "standard": 0})  # 4 queries x long bucket, nothing found
        self.assertEqual(list(self.db.iterdump()), before)
        s = M.top(self.api(), CFG, ["lion"], days=10, n=5, min_m=3)
        md = cli.markdown(s, "top lion")
        self.assertIn("| 1 | 7K |", md)
        self.assertNotIn("ngày |", md.lower().split("\n")[1].replace("đăng", ""))
        self.assertNotRegex(md, r"(?i)views/ng")

    def test_seo_digests_follow_policy(self):
        from dvr_cowork import seo
        from dvr_cowork.fullai import seo as seo_ai
        vids = [{"title": "Old Giant", "channel": "A", "views": 900000, "days": 300, "tags": []},
                {"title": "New Hit", "channel": "B", "views": 50000, "days": 1, "tags": []}]
        for mod in (seo, seo_ai):
            d = mod.trend_digest(vids, per_day=False)
            self.assertNotIn("/DAY", d.upper())
            self.assertLess(d.index("Old Giant"), d.index("New Hit"))
            self.assertIn("/DAY", mod.trend_digest(vids, per_day=True).upper())


if __name__ == "__main__":
    unittest.main()
