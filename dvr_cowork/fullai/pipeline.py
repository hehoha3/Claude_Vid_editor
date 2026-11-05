from __future__ import annotations

from datetime import datetime
import re
import subprocess
from pathlib import Path
from .core import (Stop, atomic_text, digest, event, frames, lock, numbered, object_hash,
                   probe, prod, read_json, run, stamp, unchanged, video_path, write_json, day_project)
from .story import bible, build, load_plan, pinned_profile, prompt_text, region_locks
from ..prompt_rules import csv_text, dur_s, shot_size


ROTATION=("migration","lost","predator","mother","throne")


def next_video(key, region="himalaya", base="D:/"):
    """One call for /create-doc-mov Chann_N: channel dir, next <region>_DDMMYY_N (user 2026-11-05; was vid_), recent
    archetypes/casts. Skips _pushed."""
    import re
    from datetime import datetime
    m=re.fullmatch(r"(?i)chann_(\d+)",key)
    if not m: raise Stop(f"Channel key must look like Chann_1, got {key!r}")
    roots=[p for p in Path(base).glob(f"Chann_{m[1]}_*") if p.is_dir()]
    if len(roots)!=1: raise Stop(f"Expected one {base}Chann_{m[1]}_* folder, found {[str(p) for p in roots]}")
    root=roots[0]; today=datetime.now().strftime("%d%m%y")
    folders=[p for d in (root,root/"_done") if d.is_dir() for p in d.iterdir() if p.is_dir() and p.name.lower()!="_pushed"]
    # one index per day across every channel and type, as create-doc-mov new_video.py (a name stays unique)
    every=[q for c in Path(base).glob("Chann_*") if c.is_dir() for d in (c,c/"_done") if d.is_dir()
           for q in d.iterdir() if q.is_dir() and q.name.lower()!="_pushed"]
    n=1+max([int(x[1] or 1) for p in every if (x:=re.fullmatch(rf"[a-z]+_{today}(?:_(\d+))?",p.name,re.I))],default=0)
    recent=[]
    for p in sorted(folders,key=lambda p:p.stat().st_mtime,reverse=True):
        src=p/".production/story.json"
        if src.is_file() and len(recent)<6:
            s=read_json(src)
            recent.append({"folder":p.name,"title":s.get("title"),"archetype":s.get("archetype"),
                           "cast":[c.get("species") for c in s.get("characters",[])]})
    last=next((r["archetype"] for r in recent if r["archetype"] in ROTATION),None)
    return {"channel_dir":str(root),"next_video":str(root/f"{region}_{today}_{n}"),"resolve_project":day_project(f"{region}_{today}_{n}"),
            "next_archetype":ROTATION[(ROTATION.index(last)+1)%5] if last else ROTATION[0],"recent":recent}


def initialize(video, minutes=None, title=None, region=None, profile="full_ai_mountain"):
    import math
    from ..profile import create
    v=video_path(video)
    source=prod(v)/"story.json"
    if source.exists():
        raise Stop(f"Already initialized: {source}")
    if minutes is not None and not math.isfinite(minutes):
        raise Stop("minutes must be a number")
    # Pins the profile first (video.project.json + .production/profile.lock.json): later profile edits never move this film.
    minutes=create(v,profile,region,minutes,title)["target_minutes"]
    # audios/ holds only the four compiled Markdown files; the user creates voice/ (MP3s) and music/ later.
    for folder in ("audios","shots",".production"):
        (v/folder).mkdir(parents=True,exist_ok=True)
    # This is deliberately a contract, not a machine-generated imitation of an existing film.
    write_json(source, {"schema":2,"title":title or v.name,"target_minutes":minutes,"fps":24,"wpm":155,
        "premise":"", "central_question":"", "payoff":"", "characters":[],"environment":"","geography":"",
        "synthetic_disclosure":"An original AI-generated wildlife dramatization; not footage of a documented event.",
        "scenes":[]})
    event(v,"WRITING_STORY")
    out={"source":str(source),"next":"Write complete original story and shot specifications, then build."}
    try: region_locks(read_json(v/"video.project.json").get("region_id"))
    except Stop as e: out["reminder"]=str(e)  # user 2026-11-05: remind until amazon / africa locks exist
    return out


def conform(video):
    v=video_path(video)
    with lock(prod(v)/"files.lock"):
        source=read_json(prod(v)/"story.json")
        if object_hash(source)==read_json(prod(v)/"plan.json")["source_hash"]:
            load_plan(v)  # guards hand-edited Markdown; an edited source (re-time) is rebuilt from real durations below
        folder=v/"voice" if (v/"voice").is_dir() or not (v/"audios/mp3").is_dir() else v/"audios/mp3"  # legacy folders
        paths=numbered(folder,".mp3",sum(len(sc["voice"]) for sc in source["scenes"]))
        media={}
        failures=[]
        for i,path in paths.items():
            try:
                m=probe(path,decode=True)
                if not m["audio"] or m["video"]:
                    raise Stop("Expected audio-only MP3")
                media[str(i)]={"path":str(path),**m}
            except Stop as e:
                failures.append(f"{path.name}: {e}")
        if failures:
            raise Stop("Audio problems:\n"+"\n".join(failures))
        new=build(v,[media[str(i)]["duration"] for i in paths])
        write_json(prod(v)/"voice_media.json",media)
        event(v,"VOICE_CONFORMED",plan_hash=object_hash(new),source_hash=new["source_hash"],voice_blocks=len(media))
        return {"blocks":len(media),"occupancy":new["voice_occupancy"],"runtime_s":new["runtime_f"]/new["fps"]}


def missing_prompts(video, reissue=False, only=None):
    v=video_path(video)
    plan=load_plan(v,conformed=True)
    receipt=prod(v)/"voice_receipt.json"
    if not receipt.exists():
        raise Stop("Place and verify narrator A2 before issuing generation prompts")
    vo=read_json(receipt)
    if vo.get("plan_hash")!=object_hash(plan) or vo.get("verified")!=len(plan["voice"]):
        raise Stop("Narrator A2 receipt does not match this conformed plan")
    assert_voice_media(v,plan)
    frozen=prod(v)/"manifest.json"
    if frozen.exists() and reissue:
        # Explicit user request only: same slot→ID mapping, new text; the old manifest is kept, never deleted.
        old=read_json(frozen)
        if [r["slot"] for r in old["rows"]]!=[s["id"] for s in plan["slots"] if s["prompt_id"]]:
            raise Stop("Reissue keeps the prompt-ID ↔ slot mapping; this plan changes it. Use a new video/version.")
        frozen.rename(frozen.with_name(f"manifest.{datetime.now():%Y%m%d_%H%M%S}.json"))
    if frozen.exists():
        # Issued prompts are immutable: a re-run re-renders them, even if prompt_text has changed since.
        manifest=read_json(frozen)
        if manifest["plan_hash"]!=object_hash(plan):
            raise Stop("Manifest already issued for generation. Do not renumber prompts; use a new video/version "
                       "(or prompts --reissue when the user asked for new prompt text on the same slots).")
        rows=manifest["rows"]
    else:
        ids=[c["id"] for c in plan["source"]["characters"]]
        rows=[]
        from ..profile import pinned
        region=(pinned(v)[0] or {}).get("region_id") or "himalaya"
        for sh in (s for s in plan["slots"] if s["prompt_id"]):
            i=sh["prompt_id"]; text=prompt_text(plan,sh,region)
            rows.append({"prompt_id":i,"title":sh["title"],"file":f"{i}.mp4","slot":sh["id"],"scene":sh["scene"],
                         "start_f":sh["start_f"],"end_f":sh["end_f"],"duration_s":(sh["end_f"]-sh["start_f"])/plan["fps"],
                         "dur_s":dur_s(sh["duration_s"]),
                         "hook_role":sh.get("hook_role","none"),"in_frame":" ".join(sh["characters"]),
                         "not_in_frame":" ".join(c for c in ids if c not in sh["characters"]),
                         "prompt_sha256":object_hash(text),"prompt":text})
        write_json(frozen,{"plan_hash":object_hash(plan),"rows":rows})
    if only:
        # Redo list (user 2026-11-05): the shots the user rejected on the timeline, same IDs, same issued text.
        unknown=sorted(set(only)-{r["prompt_id"] for r in rows})
        if unknown: raise Stop(f"No prompt with ID {unknown}")
        rows=[r for r in rows if r["prompt_id"] in set(only)]
    # Two files for the user (2026-11-05): missing-prompt.csv (19-column schema, shot_id = the file number to save
    # as shots/<id>.mp4) + lock-assets.md (character / environment / light locks for the generator project).
    fps,src=plan["fps"],plan["source"]
    by={s["id"]:s for s in plan["slots"]}; names={c["id"]:c["species"] for c in src["characters"]}
    table=[]
    for r in rows:
        sh=by.get(r["slot"],{}); cast=[names.get(c,c) for c in r.get("in_frame","").split()]
        table.append({"shot_id":r["prompt_id"],"cluster":r["scene"],"tc_in":stamp(r["start_f"]/fps),
                      "tc_out":stamp(r["end_f"]/fps),"dur_s":r.get("dur_s") or dur_s(r["duration_s"]),"kind":"ai_generated",
                      "animal":", ".join(cast),"action":sh.get("action",""),
                      "environment":sh.get("location") or src["geography"],"time_of_day":"daylight",
                      "shot_size":shot_size(sh.get("camera")),"camera_angle":sh.get("camera",""),
                      "direction":sh.get("direction",""),"mo_ta":r.get("title") or "",
                      "search_keywords":" ".join(cast+["snow mountain wildlife",shot_size(sh.get("camera"))]).strip(),
                      "generation_prompt":r["prompt"],
                      "reason":f"save as shots/{r['prompt_id']}.mp4"+(f"; hook candidate ({r['hook_role']})"
                                                                      if r.get("hook_role","none")!="none" else "")})
    atomic_text(v/"missing-prompt.csv",csv_text(table))
    atomic_text(v/"lock-assets.md",bible(src))
    if only: event(v,"WAITING_FOR_REDO",redo=sorted(only))
    else: event(v,"WAITING_FOR_SHOTS",prompt_count=len(rows))
    return {"prompts":len(rows),"path":str(v/"missing-prompt.csv"),"locks":str(v/"lock-assets.md"),"save_folder":str(v/"shots")}


def assert_voice_media(video, plan):
    media=read_json(prod(video)/"voice_media.json")
    if len(media) != len(plan["voice"]):
        raise Stop("Voice media count changed; re-conform before touching Resolve")
    for m in media.values():
        if digest(m["path"]) != m["sha256"]:
            raise Stop(f"Voice changed after conform: {m['path']}")
    return media


def ingest(video):
    v=video_path(video)
    with lock(prod(v)/"files.lock"):
        plan=load_plan(v,conformed=True)
        manifest=read_json(prod(v)/"manifest.json")
        if manifest["plan_hash"] != object_hash(plan):
            raise Stop("Manifest and current plan differ")
        paths=numbered(v/"shots",".mp4",len(manifest["rows"]))
        media,errors,seen_hashes={},[],{}
        cached=read_json(prod(v)/"shot_media.json") if (prod(v)/"shot_media.json").exists() else {}
        reused=0
        for row in manifest["rows"]:
            i=row["prompt_id"]; path=paths[i]
            try:
                old=cached.get(str(i))
                if unchanged(path,old) and old.get("prompt_sha256")==row["prompt_sha256"]:
                    m={k:x for k,x in old.items() if k not in ("path","prompt_sha256")}; reused+=1
                else:
                    m=probe(path,decode=True)
                if not m["video"] or not m["audio"]:
                    raise Stop("Generated shot requires picture and natural sound for linked A1")
                if m["width"]*9 != m["height"]*16:
                    raise Stop("Expected 16:9 source; inspect/regenerate instead of stretching it")
                if m["duration"]+1/max(m["fps"],1) < row["duration_s"]:
                    raise Stop(f"Too short for {row['duration_s']:.3f}s slot")
                if m["sha256"] in seen_hashes:
                    raise Stop(f"Exact duplicate of prompt {seen_hashes[m['sha256']]}; verify generated download/file numbering")
                seen_hashes[m["sha256"]]=i
                media[str(i)]={"path":str(path),"prompt_sha256":row["prompt_sha256"],**m}
            except Stop as e:
                errors.append(f"{path.name}: {e}")
        if errors:
            raise Stop("Shot problems (no import performed):\n"+"\n".join(errors))
        old=read_json(prod(v)/"shot_qc.json") if (prod(v)/"shot_qc.json").exists() else {}
        qc={"plan_hash":object_hash(plan),"shots":{}}
        for i,m in media.items():
            before=old.get("shots",{}).get(i,{})
            same=before.get("sha256") == m["sha256"] and before.get("prompt_sha256") == m["prompt_sha256"]
            qc["shots"][i]=before if same else {"sha256":m["sha256"],"prompt_sha256":m["prompt_sha256"],
                "approved":False,"reviewer":"","notes":"","hook_ok":False,"hook_start_s":0,"evidence":[]}
        write_json(prod(v)/"shot_media.json",media)
        write_json(prod(v)/"shot_qc.json",qc)
        event(v,"READY_TO_ASSEMBLE",technical_pass=len(media))
        return {"technical_pass":len(media),"reused_unchanged":reused,"qc":str(prod(v)/"shot_qc.json"),
                "next":"assemble --apply (bin 1. Other_roll, V1/A1); the user reviews on the timeline."}


def sheets(video):
    from PIL import Image,ImageDraw
    v=video_path(video)
    media=read_json(prod(v)/"shot_media.json")
    slot={str(r["prompt_id"]):r["duration_s"] for r in read_json(prod(v)/"manifest.json")["rows"]}
    folder=prod(v)/"review"; folder.mkdir(exist_ok=True)
    results,cuts=[],{}
    qc=read_json(prod(v)/"shot_qc.json").get("shots",{}) if (prod(v)/"shot_qc.json").exists() else {}
    approved=[i for i in media if qc.get(i,{}).get("approved")]  # reviewed + unchanged (ingest resets changed files)
    for i,m in media.items():
        if i in approved: continue
        used=min(m["duration"],slot[i])  # body slots use source 0…slot; frames past it never reach the timeline
        # scdet prints to stderr, which run() discards; a hard cut inside the slot breaks "one coherent take"
        err=subprocess.run(["ffmpeg","-nostdin","-i",m["path"],"-t",f"{used:.3f}","-an","-vf","scdet=threshold=8,metadata=print",
                            "-f","null","-"],capture_output=True,text=True,errors="replace").stderr
        if hits:=[round(float(x),2) for x in re.findall(r"lavfi\.scd\.time: ([\d.]+)",err)]: cuts[i]=hits
        pieces=[]
        for k,ratio in enumerate((.05,.50,.97)):
            t=ratio*used; p=folder/f"{i}_{k}.jpg"
            run(["ffmpeg","-nostdin","-v","error","-y","-ss",f"{t:.4f}","-i",m["path"],
                 "-frames:v","1","-vf","scale=480:-2",p])
            with Image.open(p) as im:
                pieces.append(im.convert("RGB").copy())
        sheet=Image.new("RGB",(1440,max(p.height for p in pieces)+44),"#202020")
        for k,p in enumerate(pieces): sheet.paste(p,(480*k,44))
        ImageDraw.Draw(sheet).text((10,12),f"{i}.mp4 | used 0-{used:.1f}s | frames at 5%, 50%, 97% of slot | cuts {cuts.get(i,'none')} | prompt {i}",fill="white")
        out=folder/f"{i}_sheet.jpg"; sheet.save(out,quality=88)
        results.append(str(out))
    return {"sheets":results,"skipped_approved":len(approved),"cuts_inside_slot":cuts,"note":"Sampling cannot prove absence of motion/anatomy errors; watch uncertain/action clips before approval. Check slot ends for extra animals."}


def ingested_media(video):
    """User workflow 2026-11-05: the user reviews the shots on the timeline, so a per-shot approval is no gate for
    assemble. Still required: same plan, every ID ingested, each file unchanged since ingest."""
    plan=load_plan(video,conformed=True)
    media=read_json(prod(video)/"shot_media.json")
    qc=read_json(prod(video)/"shot_qc.json")
    if qc.get("plan_hash") != object_hash(plan): raise Stop("Stale ingest; run ingest again")
    wanted={str(s["prompt_id"]) for s in plan["slots"] if s["prompt_id"]}
    if set(media) != wanted or set(qc.get("shots",{})) != wanted: raise Stop("Incomplete media/QC IDs")
    for i,m in media.items():
        if digest(m["path"]) != m["sha256"]: raise Stop(f"Shot {i} changed since ingest; run ingest again")
    return plan,media,qc


def hook_ready(video,q):
    """A hook source is still viewed before use: hook_ok + reviewer, notes and evidence images under review/."""
    if not (q.get("hook_ok") and q.get("reviewer") and q.get("notes") and q.get("evidence")): return False
    root=prod(video).resolve()/"review"
    return all(Path(e).resolve().is_file() and Path(e).resolve().is_relative_to(root) for e in q["evidence"])


def hook(video):
    with lock(prod(video)/"files.lock"):
        return _hook(video)


ROLE_ORDER=("threat","vulnerability","pursuit","obstacle","unanswered")


def _hook(video):
    plan,media,qc=ingested_media(video)
    candidates=[s for s in plan["slots"] if s["prompt_id"] and s["phase"] == "story"
                and not s.get("spoiler",True) and s.get("hook_role","none") != "none"
                and hook_ready(video,qc["shots"][str(s["prompt_id"])])]
    return _hook_cuts(video,plan,media,qc,candidates,intro_rules(video,plan))


def intro_rules(video,plan):
    """Every 8p intro is 2–4 s cuts (user 2026-11-05); plans built before profiles (no rules) take the pinned
    profile's intro rules, so the old 5 × 6 s layout is gone."""
    return (plan.get("rules") or pinned_profile(video)).get("intro") or {}


def hook_window(plan):
    """(start_f, end_f) of the intro: the one HOOK slot, or the H001… slots of a plan built before profiles."""
    h=[s for s in plan["slots"] if s["phase"]=="hook"]
    return min(s["start_f"] for s in h),max(s["end_f"] for s in h)


def _hook_cuts(video,plan,media,qc,candidates,intro):
    """v2 intro: cut_min–cut_max s cuts from reviewed, spoiler-free body sources, summing exactly to the hook window.
    One cut per source (no repeated range inside the intro); body slots are untouched. Retime is a cut property:
    source span = timeline duration × speed. QC per source: hook_start_s, optional hook_end_s (clean end),
    optional hook_speed (1.0, or inside selective_speed_range when the gait still looks natural)."""
    import math
    fps=plan["fps"]
    window=dict(zip(("start_f","end_f"),hook_window(plan)))
    total=window["end_f"]-window["start_f"]
    lo,hi=math.ceil(intro["cut_min_s"]*fps-1e-6),math.floor(intro["cut_max_s"]*fps+1e-6)
    s0,s1=intro.get("selective_speed_range",[1,1])
    pref=intro.get("preferred_cut_count",[10,12])
    pools,rejected={r:[] for r in ROLE_ORDER},[]
    for s in candidates:
        i=str(s["prompt_id"]); m,q=media[i],qc["shots"][i]
        speed=float(q.get("hook_speed",intro.get("default_speed",1.0)))
        a=float(q.get("hook_start_s",0)); b=float(q.get("hook_end_s") or m["duration"])
        if not (speed==1.0 or s0<=speed<=s1):
            raise Stop(f"Shot {i}: hook_speed {speed} must be 1.0 or within {s0}–{s1}")
        if not (math.isfinite(a) and 0<=a<b<=m["duration"]+1/max(1,m["fps"])):
            raise Stop(f"Shot {i}: clean hook range {a}–{b}s is outside the {m['duration']:.3f}s source")
        cap=min(hi,math.floor((b-a)/speed*fps+1e-6))  # timeline frames this clean range can give at this speed
        if cap<lo:
            rejected.append(f"{i}.mp4 ({b-a:.2f}s clean at {speed}x)"); continue
        if s.get("hook_role") in pools:
            pools[s["hook_role"]].append(dict(slot=s,id=i,speed=speed,start=a,cap=cap))
    for r in pools: pools[r].sort(key=lambda c:(-float(c["slot"].get("intensity",0)),c["slot"]["prompt_id"]))
    # Round-robin over roles so every role with a source is represented; a role may give several cuts.
    order=[pools[r][k] for k in range(max(map(len,pools.values()))) for r in ROLE_ORDER if k<len(pools[r])]
    n=min(len(order),pref[1],total//lo)
    while n<len(order) and n<total//lo and sum(c["cap"] for c in order[:n])<total: n+=1
    chosen=order[:n]
    if n<math.ceil(total/hi) or sum(c["cap"] for c in chosen)<total:
        need=[r for r in ROLE_ORDER if not pools[r]]
        raise Stop(f"Intro needs {math.ceil(total/hi)}+ reviewed, spoiler-free sources whose clean ranges fill "
                   f"{total/fps:g}s in {intro['cut_min_s']:g}–{intro['cut_max_s']:g}s cuts; have {n}. "
                   f"Mark more hook_ok sources / longer clean ranges in shot_qc.json"
                   + (f"; roles with no source: {', '.join(need)}" if need else "")
                   + (f"; too short: {', '.join(rejected)}" if rejected else ""))
    # ponytail: near-equal lengths (water-fill under each source's cap); hand-tune hook.json cut lengths if rhythm needs it
    for c in chosen: c["len"]=lo
    rest=total-n*lo
    while rest:
        for c in chosen:
            if rest and c["len"]<c["cap"]: c["len"]+=1; rest-=1
    # Story order: threat → vulnerability → pursuit → obstacle → unanswered (the cliffhanger lands last).
    chosen.sort(key=lambda c:(ROLE_ORDER.index(c["slot"]["hook_role"]),c["slot"]["prompt_id"]))
    cuts,cursor=[],window["start_f"]
    for k,c in enumerate(chosen,1):
        m,f=media[c["id"]],c["len"]
        cuts.append({"cut":k,"start_f":cursor,"end_f":cursor+f,"source_prompt":int(c["id"]),"source_start_s":c["start"],
                     "source_span_s":round(f/fps*c["speed"],6),"speed":c["speed"],
                     "a1":"keep" if c["speed"]==1.0 else intro.get("retimed_a1","mute"),
                     "role":c["slot"]["hook_role"],"reason":qc["shots"][c["id"]]["notes"],"sha256":m["sha256"]})
        cursor+=f
    missing=[r for r in ROLE_ORDER if not pools[r]]
    result={"plan_hash":object_hash(plan),"cuts":cuts,"missing_roles":missing,
            "intentional_reuse":"Each cut references a body shot; every body slot still appears in narrative order."}
    write_json(prod(video)/"hook.json",result)
    tc=lambda f:stamp(f/fps)
    atomic_text(video_path(video)/"hook_selection.md",f"# Hook {tc(window['start_f'])}–{tc(window['end_f'])} · {n} cuts\n\n"+"\n".join(
        f"- {tc(x['start_f'])}–{tc(x['end_f'])} {x['source_prompt']}.mp4 at {x['source_start_s']:.3f}s × {x['speed']:g}"
        f" (A1 {x['a1']}): {x['role']}; {x['reason']}" for x in cuts)
        +(f"\n\nRoles with no source: {', '.join(missing)}" if missing else "")+"\n")
    event(video,"READY_TO_ASSEMBLE",hook_sources=[x["source_prompt"] for x in cuts])
    return {"cuts":len(cuts),"lengths_s":[round((x["end_f"]-x["start_f"])/fps,3) for x in cuts],
            "missing_roles":missing,"path":str(video_path(video)/"hook_selection.md")}


def subtitle_file(video,plan):
    def srt(f):
        ms=round(f*1000/plan["fps"])
        return f"{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}"
    rows=[f"{v['id']}\n{srt(v['start_f'])} --> {srt(v['end_f'])}\n{v['vi']}\n" for v in plan["voice"]]
    p=video_path(video)/"subtitles_vi.srt"; atomic_text(p,"\n".join(rows))
    return p
