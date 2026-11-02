from __future__ import annotations

import csv
import io
from pathlib import Path
from .core import (Stop, atomic_text, digest, event, frames, lock, numbered, object_hash,
                   probe, prod, read_json, run, stamp, video_path, write_json)
from .story import build, load_plan, prompt_text


ROTATION=("migration","lost","predator","mother","throne")


def next_video(key, base="D:/"):
    """One call for /create-doc-mov Chann_N: channel dir, next vid_DDMMYY_N, recent archetypes/casts. Skips _pushed."""
    import re
    from datetime import datetime
    m=re.fullmatch(r"(?i)chann_(\d+)",key)
    if not m: raise Stop(f"Channel key must look like Chann_1, got {key!r}")
    roots=[p for p in Path(base).glob(f"Chann_{m[1]}_*") if p.is_dir()]
    if len(roots)!=1: raise Stop(f"Expected one {base}Chann_{m[1]}_* folder, found {[str(p) for p in roots]}")
    root=roots[0]; today=datetime.now().strftime("%d%m%y")
    folders=[p for d in (root,root/"_done") if d.is_dir() for p in d.iterdir() if p.is_dir() and p.name.lower()!="_pushed"]
    n=1+max([int(x[1]) for p in folders if (x:=re.fullmatch(rf"vid_{today}_(\d+)",p.name))],default=0)
    recent=[]
    for p in sorted(folders,key=lambda p:p.stat().st_mtime,reverse=True):
        src=p/".production/story.json"
        if src.is_file() and len(recent)<6:
            s=read_json(src)
            recent.append({"folder":p.name,"title":s.get("title"),"archetype":s.get("archetype"),
                           "cast":[c.get("species") for c in s.get("characters",[])]})
    last=next((r["archetype"] for r in recent if r["archetype"] in ROTATION),None)
    return {"channel_dir":str(root),"next_video":str(root/f"vid_{today}_{n}"),"resolve_project":f"vid_{today}_{n}",
            "next_archetype":ROTATION[(ROTATION.index(last)+1)%5] if last else ROTATION[0],"recent":recent}


def initialize(video, minutes=8, title=None):
    import math
    if not math.isfinite(minutes) or minutes<8:
        raise Stop("Choose 8 minutes, 11 minutes or a longer duration")
    v=video_path(video)
    source=prod(v)/"story.json"
    if source.exists():
        raise Stop(f"Already initialized: {source}")
    for folder in ("audios/mp3","audios/music","shots",".production"):
        (v/folder).mkdir(parents=True,exist_ok=True)
    # This is deliberately a contract, not a machine-generated imitation of an existing film.
    write_json(source, {"schema":2,"title":title or v.name,"target_minutes":minutes,"fps":24,"wpm":145,
        "premise":"", "central_question":"", "payoff":"", "characters":[],"environment":"","geography":"",
        "synthetic_disclosure":"An original AI-generated wildlife dramatization; not footage of a documented event.",
        "scenes":[]})
    event(v,"WRITING_STORY")
    return {"source":str(source),"next":"Write complete original story and shot specifications, then build."}


def conform(video):
    v=video_path(video)
    with lock(prod(v)/"files.lock"):
        plan=load_plan(v)
        paths=numbered(v/"audios/mp3",".mp3",len(plan["voice"]))
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
        event(v,"VOICE_CONFORMED",plan_hash=object_hash(new),voice_blocks=len(media))
        return {"blocks":len(media),"occupancy":new["voice_occupancy"],"runtime_s":new["runtime_f"]/new["fps"]}


def missing_prompts(video):
    v=video_path(video)
    plan=load_plan(v,conformed=True)
    receipt=prod(v)/"voice_receipt.json"
    if not receipt.exists():
        raise Stop("Place and verify narrator A2 before issuing generation prompts")
    vo=read_json(receipt)
    if vo.get("plan_hash")!=object_hash(plan) or vo.get("verified")!=len(plan["voice"]):
        raise Stop("Narrator A2 receipt does not match this conformed plan")
    assert_voice_media(v,plan)
    rows=[]
    body=[s for s in plan["slots"] if s["prompt_id"]]
    out=["# Generated shots — one numbered file per prompt", "",
         "Save as shots/1.mp4, shots/2.mp4… in this exact order. Five opening teasers reuse reviewed body sources; "
         "they do not consume or renumber body prompts.", ""]
    for sh in body:
        i=sh["prompt_id"]
        text=prompt_text(plan,sh)
        out += [f"## {i} — {sh['id']} · {stamp(sh['start_f']/plan['fps'])}–{stamp(sh['end_f']/plan['fps'])}","",text,""]
        rows.append({"prompt_id":i,"file":f"{i}.mp4","slot":sh["id"],"scene":sh["scene"],
                     "start_f":sh["start_f"],"end_f":sh["end_f"],"duration_s":(sh["end_f"]-sh["start_f"])/plan["fps"],
                     "hook_role":sh.get("hook_role","none"),"prompt_sha256":object_hash(text),"prompt":text})
    frozen=prod(v)/"manifest.json"
    manifest={"plan_hash":object_hash(plan),"rows":rows}
    if frozen.exists() and read_json(frozen) != manifest:
        raise Stop("Manifest already issued for generation. Do not renumber prompts; use a new video/version.")
    write_json(frozen,manifest)
    atomic_text(v/"missing-prompt.md","\n".join(out))
    table=io.StringIO(newline="")
    writer=csv.DictWriter(table,fieldnames=list(rows[0]))
    writer.writeheader(); writer.writerows(rows)
    atomic_text(v/"shot_manifest.csv",table.getvalue())
    event(v,"WAITING_FOR_SHOTS",prompt_count=len(rows))
    return {"prompts":len(rows),"path":str(v/"missing-prompt.md"),"save_folder":str(v/"shots")}


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
        for row in manifest["rows"]:
            i=row["prompt_id"]; path=paths[i]
            try:
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
        event(v,"SHOT_QC_REQUIRED",technical_pass=len(media),visual_pass=sum(q["approved"] for q in qc["shots"].values()))
        return {"technical_pass":len(media),"qc":str(prod(v)/"shot_qc.json"),"next":"View contact sheets, compare against prompt, complete shot_qc.json."}


def sheets(video):
    from PIL import Image,ImageDraw
    v=video_path(video)
    media=read_json(prod(v)/"shot_media.json")
    folder=prod(v)/"review"; folder.mkdir(exist_ok=True)
    results=[]
    for i,m in media.items():
        pieces=[]
        for k,ratio in enumerate((.10,.50,.90)):
            t=ratio*m["duration"]; p=folder/f"{i}_{k}.jpg"
            run(["ffmpeg","-nostdin","-v","error","-y","-ss",f"{t:.4f}","-i",m["path"],
                 "-frames:v","1","-vf","scale=480:-2",p])
            with Image.open(p) as im:
                pieces.append(im.convert("RGB").copy())
        sheet=Image.new("RGB",(1440,max(p.height for p in pieces)+44),"#202020")
        for k,p in enumerate(pieces): sheet.paste(p,(480*k,44))
        ImageDraw.Draw(sheet).text((10,12),f"{i}.mp4 | frames at 10%, 50%, 90% | compare to prompt {i}",fill="white")
        out=folder/f"{i}_sheet.jpg"; sheet.save(out,quality=88)
        results.append(str(out))
    return {"sheets":results,"note":"Sampling cannot prove absence of motion/anatomy errors; watch uncertain/action clips before approval."}


def reviewed_media(video):
    plan=load_plan(video,conformed=True)
    media=read_json(prod(video)/"shot_media.json")
    qc=read_json(prod(video)/"shot_qc.json")
    if qc.get("plan_hash") != object_hash(plan): raise Stop("Stale visual QC")
    wanted={str(s["prompt_id"]) for s in plan["slots"] if s["prompt_id"]}
    if set(media) != wanted or set(qc.get("shots",{})) != wanted: raise Stop("Incomplete media/QC IDs")
    for i,m in media.items():
        q=qc["shots"][i]
        if not q.get("approved") or not q.get("reviewer") or not q.get("notes") or not q.get("evidence"):
            raise Stop(f"Shot {i} needs an actual visual review, notes, evidence paths and reviewer")
        if q.get("sha256") != m["sha256"] or q.get("prompt_sha256") != m["prompt_sha256"] or digest(m["path"]) != m["sha256"]:
            raise Stop(f"Shot {i} changed since review; ingest and review the new file")
        for evidence in q["evidence"]:
            p=Path(evidence).resolve()
            if not p.is_file() or not p.is_relative_to(prod(video).resolve()/"review"):
                raise Stop(f"Shot {i}: invalid/missing review evidence {evidence}")
    return plan,media,qc


def hook(video):
    with lock(prod(video)/"files.lock"):
        return _hook(video)


def _hook(video):
    plan,media,qc=reviewed_media(video)
    candidates=[s for s in plan["slots"] if s["prompt_id"] and s["phase"] == "story"
                and not s.get("spoiler",True) and s.get("hook_role","none") != "none"
                and qc["shots"][str(s["prompt_id"])].get("hook_ok")]
    chosen=[]
    # A dramatic micro-story, not the five largest metadata scores or the ending replayed.
    for role in ("threat","vulnerability","pursuit","obstacle","unanswered"):
        pool=[s for s in candidates if s.get("hook_role") == role and s not in chosen]
        pool.sort(key=lambda s:(-float(s.get("intensity",0)),s["prompt_id"]))
        if not pool: raise Stop(f"No reviewed, spoiler-free {role} source for hook; regenerate the required shot.")
        chosen.append(pool[0])
    selections=[]
    for h,s in zip([x for x in plan["slots"] if x["phase"] == "hook"],chosen):
        i=str(s["prompt_id"]); m,q=media[i],qc["shots"][i]
        start=float(q.get("hook_start_s",0))
        if not math_is_finite_nonnegative(start) or start+6 > m["duration"]+1/max(1,m["fps"]):
            raise Stop(f"Hook source {i} has no clean six-second range at {start}")
        selections.append({"slot":h["id"],"source_prompt":int(i),"source_start_s":start,
                           "role":s["hook_role"],"reason":q["notes"],"sha256":m["sha256"]})
    result={"plan_hash":object_hash(plan),"selections":selections,
            "intentional_reuse":"Each teaser references a body shot; every body slot still appears in narrative order."}
    write_json(prod(video)/"hook.json",result)
    atomic_text(video_path(video)/"hook_selection.md","# Hook 00:00–00:30\n\n"+"\n".join(
        f"- {x['slot']} → {x['source_prompt']}.mp4 at {x['source_start_s']:.3f}s for 6s: {x['role']}; {x['reason']}" for x in selections)+"\n")
    event(video,"READY_TO_ASSEMBLE",hook_sources=[x["source_prompt"] for x in selections])
    return result


def math_is_finite_nonnegative(value):
    import math
    return math.isfinite(value) and value >= 0


def subtitle_file(video,plan):
    def srt(f):
        ms=round(f*1000/plan["fps"])
        return f"{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}"
    rows=[f"{v['id']}\n{srt(v['start_f'])} --> {srt(v['end_f'])}\n{v['vi']}\n" for v in plan["voice"]]
    p=video_path(video)/"subtitles_vi.srt"; atomic_text(p,"\n".join(rows))
    return p
