r"""YouTube SEO for a finished video (user 2026-10-31): trend research with the YouTube Data API, text by Gemini.

    .venv/Scripts/python.exe -m dvr_cowork.seo <video folder> [--force]   -> .work/doc_edit/<video>/youtube_meta.json
    .venv/Scripts/python.exe -m dvr_cowork.seo <video folder> --pick 2    the 2nd title option becomes the title
    .venv/Scripts/python.exe -m dvr_cowork.seo --selftest

1. Film facts from .work/doc_edit/<video>/spec.txt (# FILM, # REGION, # INTRO, # BIBLE = chapters, # CAST = species):
   no transcript is read.
2. Trend: 3 search.list (region + "wildlife documentary", the 2 main species + "documentary"; long videos of the last
   90 days, most viewed; 100 units each, cached 7 days) + videos.list -> views per day, title patterns, the words and
   tags of the most viewed titles.
3. One Gemini call (gemini-assist bridge, JSON): the 3 most trending titles (user 2026-10-31; most clicks first),
   hook, story bullets, summary, chapter names, tags, hashtags.
4. Python builds the description (chapter times from the spec, fixed AI disclosure), trims tags to 500 chars and
   flags animals that are not in the cast. Title 1 is the default; youtube.upload reads the file.
Exists already -> skipped (--force: old one kept as youtube_meta_prev.json).
"""
import datetime as dt
import hashlib
import json
import math
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # not .config: tests run this file as a script for --selftest
CACHE = ROOT / ".work" / "seo" / "cache"
CACHE_DAYS, DAYS_BACK = 7, 90
STOP = set("a an the of and or in on at to for with from by is are was be it its this that how why what who when "
           "where vs x into out up as their they them his her he she you your we our i my me one two not no can "
           "do does did will just most more full documentary hd 4k".split())
# ponytail: fixed list, catches the usual big names only; Claude still reads the 3 titles against the film
ANIMALS = set("jaguar lion lioness tiger leopard cheetah puma cougar hyena wolf wolves bear crocodile croc caiman "
              "alligator anaconda python cobra snake shark orca eagle hawk elephant hippo rhino buffalo gorilla "
              "chimp chimpanzee monkey piranha otter dolphin boto zebra wildebeest giraffe deer capybara sloth "
              "harpy tapir turtle frog".split())
DISCLOSURE = ("This film combines real wildlife footage with AI-generated imagery. The scenes are based on documented "
              "animal behaviour; some encounters are dramatized reconstructions and were not filmed as one event.")


def clock(s):
    s = int(s)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


def secs(t):
    m, s = t.split(":")
    return int(m) * 60 + float(s)


def film_facts(spec_text):
    """spec.txt -> {film, region, species[], chapters[(seconds, bible text)]} (chapter 0 = cold open at 0)."""
    f = {"film": "", "region": "amazon", "species": [], "chapters": [(0, "cold open / intro")]}
    for line in spec_text.splitlines():
        if m := re.match(r"# FILM (.*)", line):
            f["film"] = m[1].strip()
        elif m := re.match(r"# REGION (\w+)", line):
            f["region"] = m[1].lower()
        elif m := re.match(r"# BIBLE \d+ (\d+:\d+)-\S+ (.*)", line):
            f["chapters"].append((secs(m[1]), m[2].strip()[:300]))
        elif m := re.match(r"# CAST \[\w+\] sp=([\w,]+)", line):
            sp = m[1].split(",")[0].replace("_", " ")
            if sp not in f["species"]:
                f["species"].append(sp)
    f["chapters"] = [c for i, c in enumerate(f["chapters"]) if i == 0 or c[0] > 0]  # a story at 00:00 replaces intro
    return f


def queries(f):
    region = {"africa": "african savanna"}.get(f["region"], f["region"])
    return [f"{region} wildlife documentary"] + [f"{sp} documentary" for sp in f["species"][:2]]


def youtube_client(vdir):
    """API client on the video's channel token (else any saved token: search needs no channel) + channel name."""
    from googleapiclient.discovery import build
    from . import youtube
    cid = youtube.channel_of(vdir)
    paths = ([youtube.TOKENS / f"{cid}.json"] if cid else []) + sorted(youtube.TOKENS.glob("*.json"))
    for p in paths:
        if p.exists() and (creds := youtube.saved(p)):
            yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
            chans = yt.channels().list(part="snippet", id=cid).execute().get("items", []) if cid else []
            return yt, chans[0]["snippet"]["title"] if chans else ""
    sys.exit("seo: no valid YouTube token: run `python -m dvr_cowork.youtube login` once")


def search(yt, q):
    """Most viewed long videos of the last DAYS_BACK days for q -> [{title, views, days, tags}], cached CACHE_DAYS."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cf = CACHE / (hashlib.sha256(q.encode()).hexdigest()[:16] + ".json")
    if cf.exists() and time.time() - cf.stat().st_mtime < CACHE_DAYS * 86400:
        return json.loads(cf.read_text("utf-8")), 0
    after = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=DAYS_BACK)).strftime("%Y-%m-%dT%H:%M:%SZ")
    res = yt.search().list(part="snippet", q=q, type="video", order="viewCount", publishedAfter=after,
                           videoDuration="long", relevanceLanguage="en", maxResults=25).execute()
    ids = [i["id"]["videoId"] for i in res.get("items", [])]
    items = yt.videos().list(part="snippet,statistics", id=",".join(ids)).execute().get("items", []) if ids else []
    today = dt.datetime.now(dt.timezone.utc)
    out = [{"title": v["snippet"]["title"], "views": int(v["statistics"].get("viewCount", 0)),
            "days": max(1, (today - dt.datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00"))).days),
            "tags": v["snippet"].get("tags", [])} for v in items]
    cf.write_text(json.dumps(out, ensure_ascii=False), "utf-8")
    return out, 101


def trend_digest(videos, top=30):
    """Text for Gemini: the most viewed per day titles, title patterns, weighted words, frequent tags."""
    seen, vids = set(), []
    for v in sorted(videos, key=lambda v: -v["views"] / v["days"]):
        if v["title"] not in seen:
            seen.add(v["title"])
            vids.append(v)
    vids = vids[:top]
    if not vids:
        return "NO TREND DATA"
    n = len(vids)
    words, tags = Counter(), Counter()
    for v in vids:
        w = math.log10(v["views"] + 10)
        for t in set(re.findall(r"[a-z']+", v["title"].lower())) - STOP:
            if len(t) > 2:
                words[t] += w
        tags.update({t.lower().strip() for t in v["tags"]})
    pat = {"has |": lambda t: "|" in t, "has :": lambda t: ":" in t,
           "question (?, why, how, what)": lambda t: "?" in t or re.match(r"(?i)(why|how|what|who)\b", t),
           "number": lambda t: re.search(r"\d", t), "ALL CAPS first word": lambda t: t.split()[0].isupper(),
           "vs": lambda t: re.search(r"(?i)\bvs\.?\b", t)}
    lines = [f"TOP {n} BY VIEWS/DAY (views/day | views | title):"]
    lines += [f"{v['views'] // v['days']} | {v['views']} | {v['title']}" for v in vids[:15]]
    lines.append(f"TITLE PATTERNS (of {n}): " + ", ".join(f"{k} {sum(bool(f(v['title'])) for v in vids)}"
                                                         for k, f in pat.items())
                 + f", avg length {sum(len(v['title']) for v in vids) // n} chars")
    lines.append("WORDS WEIGHTED BY VIEWS: " + ", ".join(w for w, _ in words.most_common(25)))
    lines.append("FREQUENT TAGS: " + ", ".join(t for t, _ in tags.most_common(30)))
    return "\n".join(lines)


TASK = """Write YouTube metadata for the film in film.txt, using the trends in trend.txt. English.
Hard rules: only species, places and events in film.txt; never promise a kill, fight or outcome film.txt does not have; no URLs; no emoji in titles.
titles: exactly 3, the 3 most trending you can make (closest to the top trend titles' words), most clicks first, 3 different angles.
 Write ONLY the middle part, <= 55 chars, no "|", no "Wild ..." and no "Documentary": code wraps it as "WILD <REGION> | <middle> | Wildlife Documentary".
 Middle part examples: "Lion vs Hyena: The Pups Are Still Waiting", "Who Hunts the River's Deadliest Predators?".
hook: 2-3 sentences that open the description. bullets: one line per story, emoji first. summary: 2-3 sentences.
chapters: a short name per chapter index of film.txt (same count, same order).
tags: 25-30 search phrases (trend tags that fit + species + place), lowercase. hashtags: exactly 3, CamelCase with #.
JSON: {"titles":["","",""],"hook":"","bullets":[""],"summary":"","chapters":[""],"tags":[""],"hashtags":[""]}"""


def ask_gemini(gdir, film_txt, trend_txt):
    from dvr_cowork.gemini import ask
    gdir.mkdir(parents=True, exist_ok=True)
    (gdir / "film.txt").write_text(film_txt, "utf-8")
    (gdir / "trend.txt").write_text(trend_txt, "utf-8")
    text, stats = ask(TASK, [gdir / "film.txt", gdir / "trend.txt"], json_out=True)
    g = json.loads(text)
    g = g[0] if isinstance(g, list) and g else g  # flash-lite sometimes wraps the object in a list (2026-11-01)
    if not isinstance(g, dict) or not isinstance(g.get("titles"), list) or len(g["titles"]) < 3:
        sys.exit(f"seo: Gemini answer is not the asked JSON ({text[:120]!r}); run again or write youtube_meta.json")
    return g, stats


def tag_budget(tags, limit=500):
    """Unique tags in order, cut where YouTube's 500-char count (quotes around tags with spaces, commas) would pass."""
    out, used = [], 0
    for t in dict.fromkeys(t.strip().lower() for t in tags if t.strip()):
        n = len(t) + (2 if " " in t else 0) + (1 if out else 0)
        if used + n > limit:
            break
        out.append(t)
        used += n
    return out


def full_title(mid, region):
    """The user's format (2026-10-31): WILD <REGION> | <middle> | Wildlife Documentary; a frame Gemini added is dropped."""
    parts = [p.strip() for p in mid.split("|")]
    mid = " ".join(p for p in parts if p and not re.fullmatch(r"(?i)wild \w+|(wildlife )?documentary", p))
    return f"WILD {region.upper()} | {mid} | Wildlife Documentary"[:100]


def assemble(g, f, channel):
    """Gemini parts + spec facts -> youtube_meta dict + flags."""
    flags = []
    titles = [{"text": full_title(t["text"] if isinstance(t, dict) else t, f["region"])} for t in g["titles"][:3]]
    names = g.get("chapters", [])
    if len(names) != len(f["chapters"]):
        flags.append(f"chapter names {len(names)} != {len(f['chapters'])} chapters: generic names used for the rest")
    chap = [f"{clock(s)} {names[i] if i < len(names) else f'Part {i}'}" for i, (s, _) in enumerate(f["chapters"])]
    if len(chap) < 3:
        flags.append("fewer than 3 chapters: YouTube shows none")
    body = [g["hook"], "\n".join(g.get("bullets", [])), g["summary"]]
    desc = "\n\n".join([titles[0]["text"], *body, "Chapters\n" + "\n".join(chap), "About this film\n" + DISCLOSURE,
                        f"Subscribe to {channel} for more stories from the wild." if channel else "",
                        " ".join(h for h in g.get("hashtags", [])[:3] if re.fullmatch(r"#\w+", h))]).strip()
    if "http" in desc:
        flags.append("description has a URL Gemini made up: remove it")
    cast = " ".join(f["species"]).lower()
    for t in titles:
        if extra := {w for w in re.findall(r"[a-z]+", t["text"].lower()) if w in ANIMALS and w not in cast}:
            flags.append(f"title '{t['text']}' names {', '.join(sorted(extra))}: not in the cast")
    meta = {"title": titles[0]["text"], "titles": titles, "description": desc[:5000], "tags": tag_budget(g["tags"]),
            "synthetic": True}
    return meta, flags


def run(vdir, force=False):
    vdir = Path(vdir)
    from dvr_cowork.videokey import video_key
    work = ROOT / ".work" / "doc_edit" / video_key(vdir)
    meta_f = work / "youtube_meta.json"
    if meta_f.exists() and not force:
        return f"seo: {meta_f.name} already there (title: {json.loads(meta_f.read_text('utf-8'))['title']}), --force to redo"
    if not (work / "spec.txt").exists():
        sys.exit(f"seo: {work / 'spec.txt'} not found")
    f = film_facts((work / "spec.txt").read_text("utf-8"))
    yt, channel = youtube_client(vdir)
    videos, units = [], 0
    for q in queries(f):
        vs, u = search(yt, q)
        videos += vs
        units += u
    film_txt = "\n".join([f"FILM: {f['film']}", f"REGION: {f['region']}", "CAST: " + ", ".join(f["species"]),
                          "CHAPTERS:"] + [f"{i} {clock(s)} {t}" for i, (s, t) in enumerate(f["chapters"])])
    g, stats = ask_gemini(ROOT / ".work" / "gemini" / vdir.name, film_txt, trend_digest(videos))
    meta, flags = assemble(g, f, channel)
    if meta_f.exists():
        meta_f.replace(work / "youtube_meta_prev.json")
    work.mkdir(parents=True, exist_ok=True)
    meta_f.write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    quota = f"~{units + 1} quota units" if units else "trend cached (1 quota unit)"  # +1 = channels.list
    lines = [f"seo {vdir.name}: {len(videos)} trend videos, {quota}, Gemini in {stats.get('in', 0)} "
             f"out {stats.get('out', 0) + stats.get('thoughts', 0)} tokens -> {meta_f}"]
    lines += [f"  {i}. {t['text']}" + ("  <- title" if i == 1 else "") for i, t in enumerate(meta["titles"], 1)]
    lines.append(f"  tags {len(meta['tags'])}, chapters {len(f['chapters'])}, synthetic yes")
    return "\n".join(lines + [f"  FLAG {x}" for x in flags])


def pick(vdir, n):
    from dvr_cowork.videokey import video_key
    meta_f = ROOT / ".work" / "doc_edit" / video_key(vdir) / "youtube_meta.json"
    meta = json.loads(meta_f.read_text("utf-8"))
    new = meta["titles"][n - 1]["text"]
    meta["description"] = meta["description"].replace(meta["title"], new, 1)
    meta["title"] = new
    meta_f.write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    return f"seo: title = {new}"


def selftest():
    spec = ("# REGION amazon\n# INTRO 01:34.50\n# FILM question: where does each animal stand?\n"
            "# BIBLE 1 01:34-08:03 channel bank, jaguar\n# BIBLE 2 08:03-21:03 drowned forest, boto\n"
            "# CAST [JG] sp=jaguar\n# CAST [JS] sp=jaguar out=kill\n# CAST [BT] sp=pink_river_dolphin,boto\n")
    f = film_facts(spec)
    assert f["species"] == ["jaguar", "pink river dolphin"] and f["region"] == "amazon", f
    assert [s for s, _ in f["chapters"]] == [0, 94, 483], f["chapters"]
    assert queries(f) == ["amazon wildlife documentary", "jaguar documentary", "pink river dolphin documentary"]
    assert clock(94) == "01:34" and clock(3725) == "1:02:05"
    vids = [{"title": "WILD AMAZON | Why Jaguars Climb", "views": 900000, "days": 30, "tags": ["Jaguar", "amazon"]},
            {"title": "Jaguar vs Caiman: 5 Hunts", "views": 50000, "days": 10, "tags": ["jaguar"]},
            {"title": "WILD AMAZON | Why Jaguars Climb", "views": 900000, "days": 30, "tags": []}]
    d = trend_digest(vids)
    assert d.startswith("TOP 2") and "30000 | 900000 | WILD AMAZON" in d and "jaguar" in d.split("TAGS: ")[1], d
    assert "has | 1" in d and "vs 1" in d and "ALL CAPS first word 1" in d, d
    assert trend_digest([]) == "NO TREND DATA"
    t = tag_budget(["A b", "a b", "x" * 495, "c"])
    assert t == ["a b"], t  # duplicate dropped; "a b" = 5 + comma + 495 = 501 > 500 -> cut there
    assert full_title("WILD AMAZON | Who Hunts? | Wildlife Documentary", "amazon") == \
        full_title("Who Hunts?", "amazon") == "WILD AMAZON | Who Hunts? | Wildlife Documentary"
    assert full_title("Lion vs Hyena: The Pups Are Still Waiting", "africa").startswith("WILD AFRICA | Lion vs")
    g = {"titles": ["Why the Jaguar Climbs", "The Lion Waits", "Where the River Goes"], "hook": "H.", "bullets": ["🐆 jaguar"],
         "summary": "S.", "chapters": ["Cold open", "The bank", "The forest"], "tags": ["jaguar"],
         "hashtags": ["#WildAmazon", "bad tag", "#Jaguar"]}
    meta, flags = assemble(g, f, "Shadow Canopy")
    assert meta["title"] == "WILD AMAZON | Why the Jaguar Climbs | Wildlife Documentary" and meta["synthetic"] is True
    assert "00:00 Cold open\n01:34 The bank\n08:03 The forest" in meta["description"], meta["description"]
    assert meta["description"].endswith("#WildAmazon #Jaguar") and "Shadow Canopy" in meta["description"]
    assert flags == ["title 'WILD AMAZON | The Lion Waits | Wildlife Documentary' names lion: not in the cast"], flags
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if "--selftest" in a:
        selftest()
    elif a and "--pick" in a:
        print(pick(a[0], int(a[a.index("--pick") + 1])))
    elif a:
        print(run(a[0], "--force" in a))
    else:
        sys.exit(__doc__)
