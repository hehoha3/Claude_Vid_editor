"""YouTube SEO: cached trend search -> compact digest for Claude -> deterministic youtube_meta.json.

`youtube-seo <video>` prints film facts + trend digest (~1k tokens). Claude writes .production/seo_draft.json
(3 full titles, hook, summary, tags, hashtags, optional chapter names/pick). `youtube-seo <video> --write` builds
the description (chapters from plan.json, the story's AI disclosure), trims tags to 500 chars and flags animals the
film doesn't have. No Gemini (workspace rule): the long text is assembled by code, Claude writes ~1k tokens.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections import Counter
from datetime import datetime,timedelta,timezone
from .core import ROOT,Stop,prod,read_json,video_path,write_json

CACHE=ROOT/".work/seo/cache"
CACHE_DAYS,DAYS_BACK=7,90
STOP=set("a an the of and or in on at to for with from by is are was be it its this that how why what who when where vs "
         "into out up as their they them his her he she you your we our can do will just not no full documentary hd 4k "
         "wildlife".split())
# ponytail: fixed mountain list; Claude still reads every title against the film
ANIMALS=set("leopard lynx wolf wolves bear eagle vulture fox ibex markhor chamois goat goats tahr yak puma cougar deer "
            "sheep bharal".split())
GOATS={"ibex","markhor","chamois","tahr","bharal"}  # the niche titles these "mountain goat"


def clock(s):
    s=int(s)
    return f"{s//3600}:{s//60%60:02d}:{s%60:02d}" if s>=3600 else f"{s//60:02d}:{s%60:02d}"


def film(v):
    """story.json + plan.json -> (story, common species names, [(seconds, chapter name)])."""
    s,p=read_json(prod(v)/"story.json"),read_json(prod(v)/"plan.json")
    # "Snow leopard (Panthera uncia), adult" -> "snow leopard"
    species=list(dict.fromkeys(re.split(r"[,(;]",c["species"])[0].strip().lower() for c in s["characters"]))
    chapters=[]
    for sc in p["scenes"]:
        t=sc["start_f"]/p["fps"]
        if sc["phase"]=="setup" or (chapters and t-chapters[-1][0]<10): continue  # YouTube: >=10s each
        chapters.append((t,"Opening" if sc["phase"]=="hook" else sc["title"]))
    return s,species,chapters


def search(yt,q):
    """Most viewed 4–20 min videos of the last DAYS_BACK days -> ([{title,channel,views,days,tags}], quota used)."""
    CACHE.mkdir(parents=True,exist_ok=True)
    cf=CACHE/(hashlib.sha256(q.lower().encode()).hexdigest()[:16]+".json")
    if cf.exists() and time.time()-cf.stat().st_mtime<CACHE_DAYS*86400 and (cached:=json.loads(cf.read_text("utf-8"))):
        return cached,0  # an empty result is never reused: a bad query shouldn't block a week
    now=datetime.now(timezone.utc)
    after=(now-timedelta(days=DAYS_BACK)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids=[x["id"]["videoId"] for x in yt.search().list(part="id",q=q,type="video",order="viewCount",publishedAfter=after,
         videoDuration="medium",relevanceLanguage="en",maxResults=25).execute().get("items",[])]
    items=yt.videos().list(part="snippet,statistics",id=",".join(ids)).execute().get("items",[]) if ids else []
    out=[{"title":x["snippet"]["title"],"channel":x["snippet"]["channelTitle"],"views":int(x["statistics"].get("viewCount",0)),
          "days":max(1,(now-datetime.fromisoformat(x["snippet"]["publishedAt"].replace("Z","+00:00"))).days),
          "tags":x["snippet"].get("tags",[])} for x in items]
    cf.write_text(json.dumps(out,ensure_ascii=False),"utf-8")
    return out,101


def trend_digest(videos,top=30):
    """Text for Claude: top titles by views/day, title patterns, view-weighted words, frequent tags."""
    seen,vids=set(),[]
    for x in sorted(videos,key=lambda x:-x["views"]/x["days"]):
        if x["title"] not in seen: seen.add(x["title"]); vids.append(x)
    vids=vids[:top]
    if not vids: return "NO TREND DATA"
    words,tags=Counter(),Counter()
    for x in vids:
        for w in set(re.findall(r"[a-z']+",x["title"].lower()))-STOP:
            if len(w)>2: words[w]+=math.log10(x["views"]+10)
        tags.update({t.lower().strip() for t in x["tags"]})
    pat={"|":lambda t:"|" in t,"question":lambda t:"?" in t,"vs":lambda t:re.search(r"(?i)\bvs\.?\b",t),
         "mother/baby":lambda t:re.search(r"(?i)\b(mother|baby|kid|cub)\b",t),"cliff":lambda t:re.search(r"(?i)cliff",t)}
    n=len(vids)
    return "\n".join([f"TOP {n} BY VIEWS/DAY (views/day | views | title | channel):"]
                     +[f"{x['views']//x['days']} | {x['views']} | {x['title']} | {x['channel']}" for x in vids[:15]]
                     +["PATTERNS: "+", ".join(f"{k} {sum(bool(f(x['title'])) for x in vids)}/{n}" for k,f in pat.items())
                       +f", avg {sum(len(x['title']) for x in vids)//n} chars",
                       "WORDS BY VIEWS: "+", ".join(w for w,_ in words.most_common(25)),
                       "FREQUENT TAGS: "+", ".join(t for t,_ in tags.most_common(30))])


def research(video,queries=None,yt=None):
    v=video_path(video)
    s,species,chapters=film(v)
    queries=queries or ([f"{species[0]} {species[1]}"] if len(species)>1 else [])+[f"{species[0]} wildlife documentary"]
    if yt is None:
        from .youtube import TOKENS,channel_of,client
        cid=channel_of(v) or next((p.stem for p in sorted(TOKENS.glob("*.json"))),None)
        if not cid: raise Stop("No YouTube token: run youtube-login")
        yt=client(cid)
    videos,units=[],0
    for q in queries:
        found,u=search(yt,q); videos+=found; units+=u
    return "\n".join([f"FILM: {s['title']} | archetype {s.get('archetype','?')}",f"PREMISE: {s['premise']}",
                      f"PAYOFF (do not reveal): {s['payoff']}","CAST: "+", ".join(species),
                      f"CHAPTERS ({len(chapters)}): "+" / ".join(f"{clock(t)} {n}" for t,n in chapters),
                      f"QUERIES: {'; '.join(queries)} ({units} quota units; 0 = 7-day cache)","",trend_digest(videos)])


TREND_QUERIES=["snow leopard ibex","wolf pack mountain goat","eagle mountain goat cliff","markhor lynx","wolves hunting sheep mountain"]


def channel_client(key):
    from .youtube import client,mapping
    cid=mapping().get(key)
    if not cid: raise Stop(f"{key} is not logged in: run youtube-login --key {key}")
    return client(cid)


def trends(key,queries=None,yt=None):
    """Concept research for /create-doc-mov Chann_N without a video folder: same cached search, same digest."""
    yt=yt or channel_client(key)
    videos,units=[],0
    for q in queries or TREND_QUERIES:
        found,u=search(yt,q); videos+=found; units+=u
    return f"QUERIES: {'; '.join(queries or TREND_QUERIES)} ({units} quota units; 0 = 7-day cache)\n\n"+trend_digest(videos)


def reference(key,url,yt=None):
    """Official-API facts about a reference video. The Data API cannot download another channel's captions."""
    m=re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([\w-]{11})",url) or re.fullmatch(r"([\w-]{11})",url)
    if not m: raise Stop(f"Not a YouTube video link: {url}")
    yt=yt or channel_client(key)
    items=yt.videos().list(part="snippet,statistics,contentDetails",id=m[1]).execute().get("items",[])
    if not items: raise Stop(f"Video {m[1]} not found or private")
    x=items[0];sn=x["snippet"]
    days=max(1,(datetime.now(timezone.utc)-datetime.fromisoformat(sn["publishedAt"].replace("Z","+00:00"))).days)
    return {"id":m[1],"title":sn["title"],"channel":sn["channelTitle"],"duration":x["contentDetails"]["duration"],
            "views":int(x["statistics"].get("viewCount",0)),"days":days,"tags":sn.get("tags",[]),
            "description":sn.get("description",""),"transcript":"not available via the official API"}


def tag_budget(tags,limit=500):
    """Unique lowercase tags in order, cut before YouTube's 500-char count (quotes around spaced tags, commas)."""
    out,used=[],0
    for t in dict.fromkeys(t.strip().lower() for t in tags if t.strip()):
        n=len(t)+(2 if " " in t else 0)+(1 if out else 0)
        if used+n>limit: break
        out.append(t); used+=n
    return out


def full_title(t):
    """The user's reference shape: '<story line> | <short label>' (Wildlife Documentary / Wild Animals / channel name)."""
    t=re.sub(r"\s+"," ",t).strip()
    parts=[p.strip() for p in t.split("|")]
    if len(parts)!=2 or not all(parts): raise Stop(f"Title needs exactly '<story line> | <label>': {t}")
    if len(t)>100: raise Stop(f"Title over 100 chars ({len(t)}): {t}")
    return " | ".join(parts)


def assemble(video,d=None):
    """seo_draft.json -> youtube_meta.json; returns the titles and FLAG lines."""
    v=video_path(video)
    if (prod(v)/"youtube.json").exists(): raise Stop("Already uploaded (or outcome unknown): change metadata in Studio")
    s,species,chapters=film(v)
    d=d or read_json(prod(v)/"seo_draft.json")
    if len(d.get("titles",[]))!=3 or not d.get("hook") or not d.get("tags"): raise Stop("Draft needs 3 titles, hook, tags")
    titles=[full_title(t) for t in d["titles"]]
    names=d.get("chapters") or [n for _,n in chapters]
    if len(names)!=len(chapters): raise Stop(f"Draft chapters: give {len(chapters)} names in order, or omit them")
    hashtags=" ".join(h for h in d.get("hashtags",[])[:3] if re.fullmatch(r"#\w+",h))
    desc="\n\n".join(x for x in [d["hook"],d.get("summary",""),
                                 "Chapters\n"+"\n".join(f"{clock(t)} {n}" for (t,_),n in zip(chapters,names)),
                                 "About this film\n"+s["synthetic_disclosure"],hashtags] if x)
    flags=["fewer than 3 chapters: YouTube shows none"] if len(chapters)<3 else []
    if "http" in desc: flags.append("description contains a URL: remove it")
    cast=" ".join(species)
    for t in titles:
        words={{"wolves":"wolf","goats":"goat"}.get(w,w) for w in re.findall(r"[a-z]+",t.lower()) if w in ANIMALS}
        extra={w for w in words if w not in cast and not (w=="goat" and GOATS & set(cast.split()))}
        if extra: flags.append(f"'{t}' names {', '.join(sorted(extra))}: not in the cast")
    tags=tag_budget(d["tags"])
    if len(tags)<len(set(d["tags"])): flags.append(f"tags trimmed to {len(tags)} (500-char limit)")
    pick=int(d.get("pick",1))
    write_json(prod(v)/"youtube_meta.json",{"title":titles[pick-1],"titles":titles,"description":desc[:5000],"tags":tags})
    return "\n".join([f"youtube_meta.json written ({len(tags)} tags, {len(chapters)} chapters)"]
                     +[f"  {i}. {t}"+("  <- title" if i==pick else "") for i,t in enumerate(titles,1)]
                     +[f"  FLAG {x}" for x in flags])
