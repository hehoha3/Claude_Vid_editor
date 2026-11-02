"""research-youtube: most-viewed videos of a topic published in the last N days (YouTube Data API).

    .venv/Scripts/python.exe .claude/skills/research-youtube/scripts/top_videos.py amazon-wildlife | africa-wildlife
    .venv/Scripts/python.exe .claude/skills/research-youtube/scripts/top_videos.py -q "deep house mix" -q "..." [--ai] [--days 10] [--n 20] [--min 3]
    .venv/Scripts/python.exe .claude/skills/research-youtube/scripts/top_videos.py --selftest

Per query: search.list order=viewCount, one call per length bucket (medium 4-20 min unless --min >= 20, long > 20 min;
100 of 10,000 daily quota units each), then videos.list (1 unit / 50 ids) for real numbers. Drops videos under --min
minutes and live / upcoming; --ai keeps titles / descriptions / tags naming AI or an AI generator. Prints one
markdown table. Uses any saved OAuth token (.secrets/youtube/tokens, `python -m dvr_cowork.youtube login`).
"""
import argparse, re, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

# user 2026-11-01: narrated predator / survival documentaries >= 20 min, AI or real footage; preset = these
# queries, --min 20 (long bucket only: half the quota and time), 30 rows for Claude's keep rule
PRESETS = {
    "amazon-wildlife": ["amazon jungle predators documentary", "congo jungle wildlife documentary",
                        "rainforest predators nature documentary", "brutal jungle survival animals documentary"],
    "africa-wildlife": ["african savannah predators documentary", "lion survival africa wildlife documentary",
                        "africa predators vs prey full episode", "brutal africa nature documentary"],
}
# ponytail: keyword heuristic; YouTube's "altered or synthetic" label is not in the API, unlabelled AI videos slip through
AI_RE = re.compile(r"(?i)(\bA\.?I\b|#ai\w*|ai[- ]?(generated|made|art|video|film|animation)|\bveo\s?\d?\b|kling|"
                   r"\bsora\b|midjourney|runway\s?(gen|ml)|hailuo|minimax|\bluma\b|pika\s?labs|seedance|wan\s?2)")


def secs(iso):
    """ISO 8601 duration (PT1H2M3S, P1DT2H) -> seconds; P0D (live / upcoming) -> 0."""
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60 + s


def is_ai(sn):
    return bool(AI_RE.search(" ".join([sn.get("title", ""), sn.get("description", ""), *sn.get("tags", [])])))


def short(n):
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1e3:.0f}K" if n >= 1e3 else str(n)


def hms(s):
    h, r = divmod(s, 3600)
    return f"{h}:{r // 60:02d}:{r % 60:02d}" if h else f"{r // 60}:{r % 60:02d}"


def buckets(min_m):
    return ("long",) if min_m >= 20 else ("medium", "long")


def creds():
    from dvr_cowork.youtube import TOKENS, saved
    for p in sorted(TOKENS.glob("*.json")) if TOKENS.exists() else []:
        if c := saved(p):
            return c
    sys.exit("no valid YouTube token: run `.venv/Scripts/python.exe -m dvr_cowork.youtube login`")


def run(queries, days, n, ai, min_m):
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    yt = build("youtube", "v3", credentials=creds(), cache_discovery=False)
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    ids, calls = [], 0
    try:
        for q in queries:
            for dur in buckets(min_m):
                r = yt.search().list(part="id", type="video", q=q, order="viewCount", maxResults=50, videoDuration=dur,
                                     publishedAfter=since.strftime("%Y-%m-%dT%H:%M:%SZ")).execute()
                ids += [i["id"]["videoId"] for i in r.get("items", [])]
                calls += 1
        ids = list(dict.fromkeys(ids))
        items = []
        for k in range(0, len(ids), 50):
            items += yt.videos().list(part="snippet,statistics,contentDetails", id=",".join(ids[k:k + 50])).execute()["items"]
    except HttpError as e:
        sys.exit(f"YouTube API error {e.resp.status}: {'quota hết, thử lại sau 14:00 (giờ VN)' if 'quota' in str(e) else e}")
    rows = []
    for v in items:
        sn, st = v["snippet"], v.get("statistics", {})
        pub = datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))
        s = secs(v["contentDetails"].get("duration"))
        if pub < since or s < min_m * 60 or sn.get("liveBroadcastContent") != "none" or (ai and not is_ai(sn)):
            continue
        age = max((now - pub).total_seconds() / 86400, 0.5)
        views = int(st.get("viewCount", 0))
        rows.append((views, views / age, age, s, sn["channelTitle"], sn["title"], v["id"]))
    rows.sort(reverse=True)
    print(f"{len(ids)} candidates, {len(rows)} kept (>= {min_m} min, last {days} d{', AI' if ai else ''}), "
          f"quota ~{calls * 100 + len(ids) // 50 + 1}")
    print("| # | Views | Views/ngày | Ngày | Dài | Kênh | Tiêu đề | Link |\n|---|---|---|---|---|---|---|---|")
    for i, (views, vpd, age, s, ch, title, vid) in enumerate(rows[:n], 1):
        t = title.replace("|", "/")
        print(f"| {i} | {short(views)} | {short(int(vpd))} | {age:.0f} | {hms(s)} | {ch.replace('|', '/')[:25]} | "
              f"{t[:70] + '…' if len(t) > 70 else t} | https://youtu.be/{vid} |")


def selftest():
    assert secs("PT1H2M3S") == 3723 and secs("PT4M") == 240 and secs("P1DT1S") == 86401 and secs("P0D") == 0
    assert is_ai({"title": "Jaguar vs Anaconda | AI Wildlife"}) and is_ai({"title": "x", "tags": ["veo3"]})
    assert is_ai({"title": "x", "tags": ["Veo 3"]}) and is_ai({"title": "made with Kling"})
    assert not is_ai({"title": "Amazon Rainforest 4K - Wild Animals", "description": "Jaguars hunting caimans"})
    assert not is_ai({"title": "Daily vlog: said goodbye to my airbnb"})
    assert short(1_234_567) == "1.2M" and short(45_600) == "46K" and hms(3723) == "1:02:03" and hms(245) == "4:05"
    assert buckets(20) == ("long",) and buckets(3) == ("medium", "long")
    print("selftest ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("preset", nargs="?", choices=sorted(PRESETS))
    ap.add_argument("-q", "--query", action="append", default=[])
    ap.add_argument("--days", type=int, default=10)
    ap.add_argument("--n", type=int)
    ap.add_argument("--min", type=int, help="shortest video in minutes (default 3, preset 20)")
    ap.add_argument("--ai", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # Windows console = cp1252; titles are any language
    if a.selftest:
        selftest()
    elif not (a.preset or a.query):
        ap.error("a preset or at least one -q")
    else:
        run(a.query or PRESETS[a.preset], a.days, a.n or (30 if a.preset else 20), a.ai, a.min or (20 if a.preset else 3))
