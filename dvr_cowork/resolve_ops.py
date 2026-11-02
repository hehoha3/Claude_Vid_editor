"""Narrow, additive Resolve adapter. Never clear tracks or rewrite a manual edit."""
from __future__ import annotations

from datetime import datetime
import math
import re
from pathlib import Path
from .core import (ROOT, Stop, config, event, frames, lock, object_hash, probe, prod,
                   read_json, video_path, write_json)
from .pipeline import assert_voice_media, reviewed_media, subtitle_file
from .resolve_conn import connect
from .story import load_plan

BINS=("1. shots","2. Audio","2. Audio/Narrator","2. Audio/Music","3. Graphics","3. Graphics/sub-title","4. Timeline")
TRACKS={1:"Shot Sound",2:"Narrator Voice",3:"Music"}


def ensure_bin(mp,name,create=True):
    folder=mp.GetRootFolder()
    for part in name.split("/"):
        found=next((x for x in folder.GetSubFolderList() or [] if x.GetName()==part),None)
        if not found and not create: return None
        folder=found or mp.AddSubFolder(folder,part)
        if not folder: raise Stop(f"Could not create bin {name}")
    return folder


def channel(video):
    """Chann_N for D:\\Chann_N_<name>\\<video>; None for a folder outside a channel (legacy root-level bins)."""
    m=re.match(r"(?i)chann_(\d+)(?:_|$)",Path(video).parent.name)
    return f"Chann_{m[1]}" if m else None


def all_clips(folder):
    yield from folder.GetClipList() or []
    for sub in folder.GetSubFolderList() or []: yield from all_clips(sub)


def norm(p):
    import os
    return os.path.normcase(str(Path(p).resolve())) if p else ""


def item_path(item):
    mp=item.GetMediaPoolItem()
    return mp.GetClipProperty("File Path") if mp else ""


class Session:
    def __init__(self,video,resolve=None):
        self.video=video_path(video)
        self.plan=load_plan(video,conformed=True)
        self.resolve=resolve or connect(config())
        self.pm=self.resolve.GetProjectManager()
        self.project=self.pm.GetCurrentProject()
        expected=self.plan["source"].get("resolve_project",self.video.name)
        if not self.project or self.project.GetName()!=expected:
            raise Stop(f"Open Resolve project {expected!r}; no other project is modified.")
        self.mp=self.project.GetMediaPool()
        self.previous=self.project.GetCurrentTimeline()
        self.previous_bin=self.mp.GetCurrentFolder()
        # One project can hold one video per channel: Chann_N/<bins>, each with its own Edit in Chann_N/4. Timeline.
        self.ch=channel(self.video)
        tls=[self.project.GetTimelineByIndex(i) for i in range(1,self.project.GetTimelineCount()+1)]
        matches=[t for t in tls if t and t.GetName()=="Edit"]
        if self.ch:
            home=ensure_bin(self.mp,self.bin("4. Timeline"),create=False)
            ids={c.GetUniqueId() for c in (home.GetClipList() or [])} if home else set()
            matches=[t for t in matches if t.GetMediaPoolItem() and t.GetMediaPoolItem().GetUniqueId() in ids]
        if len(matches)>1: raise Stop(f"More than one Edit timeline in {self.bin('4. Timeline')}; keep exactly one.")
        self.tl=matches[0] if matches else None
        if self.tl:
            fps=float(self.tl.GetSetting("timelineFrameRate") or self.project.GetSetting("timelineFrameRate"))
            if abs(fps-self.plan["fps"])>.001: raise Stop(f"Timeline fps {fps} != plan fps {self.plan['fps']}")
            if int(self.tl.GetTrackCount("audio") or 0)>3:
                raise Stop("Edit has more than 3 audio tracks. Use a clean project; existing tracks are not deleted.")
        self.end_mode=config().get("resolve",{}).get("source_end","exclusive")
        if self.end_mode not in ("exclusive","inclusive"): raise Stop("source_end must be exclusive or inclusive")

    def bin(self,name): return f"{self.ch}/{name}" if self.ch else name

    def restore(self):
        if self.previous: self.project.SetCurrentTimeline(self.previous)
        if self.previous_bin: self.mp.SetCurrentFolder(self.previous_bin)

    def prepare(self):
        for b in BINS: ensure_bin(self.mp,self.bin(b))
        dst=ensure_bin(self.mp,self.bin("4. Timeline"))
        self.mp.SetCurrentFolder(dst)
        if not self.tl:
            try: current=float(self.project.GetSetting("timelineFrameRate"))
            except (TypeError,ValueError): current=None
            # The project rate is shared by every channel's Edit; only set it when it differs.
            if current is None or abs(current-self.plan["fps"])>.001:
                fps=str(self.plan["fps"]).removesuffix(".0")
                if not self.project.SetSetting("timelineFrameRate",fps): raise Stop("Set project frame rate before creating Edit")
            self.tl=self.mp.CreateEmptyTimeline("Edit")
            if not self.tl: raise Stop(f"Could not create Edit in {self.bin('4. Timeline')}")
        elif not self.ch:
            timeline_clip=self.tl.GetMediaPoolItem()
            if timeline_clip and not any(c.GetUniqueId()==timeline_clip.GetUniqueId() for c in dst.GetClipList() or []):
                if not self.mp.MoveClips([timeline_clip],dst): raise Stop("Could not put Edit in 4. Timeline")
        if not self.project.SetCurrentTimeline(self.tl): raise Stop("Could not select Edit")
        while int(self.tl.GetTrackCount("video") or 0)<1:
            if not self.tl.AddTrack("video"): raise Stop("Could not create V1")
        while int(self.tl.GetTrackCount("audio") or 0)<3:
            if not self.tl.AddTrack("audio","stereo"): raise Stop("Could not create audio track")
        for i,name in TRACKS.items():
            if not self.tl.SetTrackName("audio",i,name): raise Stop(f"Could not name A{i}")
        self.t0=int(self.tl.GetStartFrame())

    def backup(self,label):
        name=f"Edit_bak_{label}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        self.mp.SetCurrentFolder(ensure_bin(self.mp,self.bin("4. Timeline")))
        if not self.tl.DuplicateTimeline(name): raise Stop("Backup failed; no timeline clips changed")
        self.project.SetCurrentTimeline(self.tl)
        return name

    def media(self,path,bin_name):
        key=norm(path)
        found=next((c for c in all_clips(self.mp.GetRootFolder()) if norm(c.GetClipProperty("File Path"))==key),None)
        if found: return found
        self.mp.SetCurrentFolder(ensure_bin(self.mp,self.bin(bin_name)))
        imported=self.mp.ImportMedia([str(Path(path).resolve())]) or []
        if len(imported)!=1: raise Stop(f"Failed to import {path}")
        return imported[0]

    def bounds(self,kind,track):
        return self.tl.GetItemListInTrack(kind,track) or [] if self.tl else []

    def classify(self,op):
        if not self.tl: return "add"
        a,b=op["start_f"]+int(self.tl.GetStartFrame()),op["end_f"]+int(self.tl.GetStartFrame())
        for item in self.bounds(op["kind"],op["track"]):
            x,y=int(item.GetStart()),int(item.GetEnd())
            if x<b and a<y:
                same=(x==a and y==b and norm(item_path(item))==norm(op["path"]))
                fps=float(op["source_fps"])
                offset=int(item.GetLeftOffset())
                if same and abs(offset-frames(op.get("source_start_s",0),fps))<=1:
                    return "already_present"
                raise Stop(f"Manual/foreign edit conflicts with {op['label']} on {op['kind']} {op['track']}, "
                           f"frame {a}. Kept untouched; inspect the timeline.")
        return "add"

    def append(self,op):
        mp=self.media(op["path"],op["bin"])
        fps=self.plan["fps"]
        raw_fps=mp.GetClipProperty("FPS")
        try: sfps=float(raw_fps) if raw_fps else float(op["source_fps"])
        except (TypeError,ValueError): sfps=float(op["source_fps"])
        if not math.isfinite(sfps) or sfps<=0: raise Stop(f"Invalid imported clip frame rate: {op['label']}")
        start=frames(op.get("source_start_s",0),sfps)
        duration=op["end_f"]-op["start_f"]
        n=round(duration*sfps/fps)
        end=start+n-(self.end_mode=="inclusive")
        result=self.mp.AppendToTimeline([{"mediaPoolItem":mp,"mediaType":1 if op["kind"]=="video" else 2,
            "trackIndex":op["track"],"recordFrame":self.t0+op["start_f"],"startFrame":start,"endFrame":end}]) or []
        if len(result)!=1: raise Stop(f"Append failed: {op['label']}; recover using backup, never clear tracks")
        item=result[0]
        if int(item.GetStart())!=self.t0+op["start_f"] or int(item.GetEnd())!=self.t0+op["end_f"]:
            raise Stop(f"Resolve frame convention/conform mismatch at {op['label']}. Partial edit kept with backup. "
                       "Check source_end and installed Scripting/README.txt; no automatic retry.")
        if abs(int(item.GetLeftOffset())-start)>1: raise Stop(f"Source-in mismatch at {op['label']}")
        return item

    def subtitles(self):
        path=subtitle_file(self.video,self.plan)
        try:
            imported=self.media(path,"3. Graphics/sub-title")
        except Stop:
            return f"SRT created at {path}; this Resolve API refused import. Import into {self.bin('3. Graphics/sub-title')} manually"
        if self.tl.GetTrackCount("subtitle") and self.tl.GetItemListInTrack("subtitle",1):
            return f"SRT in {self.bin('3. Graphics/sub-title')}; existing subtitle edits preserved"
        if not self.tl.GetTrackCount("subtitle") and not self.tl.AddTrack("subtitle"):
            return "SRT imported; add subtitle track manually (API refused)"
        # Resolve versions differ on SRT append support. Never report success without visible items.
        self.mp.AppendToTimeline([{"mediaPoolItem":imported,"recordFrame":self.t0}])
        got=self.tl.GetItemListInTrack("subtitle",1) or []
        if len(got)!=len(self.plan["voice"]): return "SRT imported; subtitle append unsupported/partial: drag SRT onto Subtitle 1 manually"
        return f"{len(got)} Vietnamese subtitle items placed"


def voice_operations(video,plan):
    media=assert_voice_media(video,plan)
    return [{"label":f"VO {v['id']}","kind":"audio","track":2,"bin":"2. Audio/Narrator",
             "path":media[str(v["id"])]["path"],"source_fps":plan["fps"],
             "start_f":v["start_f"],"end_f":v["end_f"],"source_start_s":0} for v in plan["voice"]]


def shot_operations(video):
    plan,media,qc=reviewed_media(video)
    selection=read_json(prod(video)/"hook.json")
    if selection["plan_hash"]!=object_hash(plan): raise Stop("Hook selection belongs to another plan")
    hooks={h["slot"]:h for h in selection["selections"]}
    if set(hooks)!={s["id"] for s in plan["slots"] if s["phase"]=="hook"}: raise Stop("Incomplete hook selection")
    out=[]
    for s in plan["slots"]:
        h=hooks.get(s["id"])
        pid=h["source_prompt"] if h else s["prompt_id"]
        m=media[str(pid)]
        if h and h["sha256"]!=m["sha256"]: raise Stop("Hook source changed since selection")
        if m["fps"]<=0: raise Stop(f"Cannot determine source fps: {m['path']}")
        start=h["source_start_s"] if h else 0
        for kind,track in (("video",1),("audio",1)):
            out.append({"label":s["id"],"kind":kind,"track":track,"bin":"1. shots","path":m["path"],
                        "source_fps":m["fps"],"start_f":s["start_f"],"end_f":s["end_f"],"source_start_s":start})
    return out


def apply(video,stage,resolve=None):
    video=video_path(video)
    with lock(ROOT/".work/resolve.lock"),lock(prod(video)/"files.lock"):
        session=Session(video,resolve)
        s=session
        try:
            ops=voice_operations(video,s.plan) if stage=="voice" else shot_operations(video)
            if stage=="shots":
                voice_receipt=prod(video)/"voice_receipt.json"
                if not voice_receipt.exists(): raise Stop("Place and verify A2 before placing generated shots")
                for op in voice_operations(video,s.plan):
                    if s.classify(op)!="already_present": raise Stop("A2 is incomplete; resume the voice stage first")
            # Detect every overlap before changing any bin/track/timeline.
            todo=[op for op in ops if s.classify(op)=="add"]
            if s.tl:
                for kind,track in set((op["kind"],op["track"]) for op in ops):
                    expected={(int(s.tl.GetStartFrame())+op["start_f"],int(s.tl.GetStartFrame())+op["end_f"],norm(op["path"]))
                              for op in ops if (op["kind"],op["track"])==(kind,track)}
                    for item in s.bounds(kind,track):
                        if (int(item.GetStart()),int(item.GetEnd()),norm(item_path(item))) not in expected:
                            raise Stop(f"Unexpected existing item on {kind} {track}; preserve it and inspect this project before assembly")
            s.prepare()
            backup=s.backup(stage) if todo else None
            journal=prod(video)/f"{stage}_journal.json"
            progress={"status":"WRITING","backup":backup,"plan_hash":object_hash(s.plan),"completed":[]}
            write_json(journal,progress)
            for op in todo:
                progress["pending"]={"label":op["label"],"kind":op["kind"],"start_f":op["start_f"],"end_f":op["end_f"]}
                write_json(journal,progress)
                item=s.append(op)
                if op["kind"]=="audio" and op["track"]==1:
                    if not item.SetProperty("AudioVolume",float(config().get("audio",{}).get("shot_db",-12))):
                        raise Stop("Could not set A1 gain; listen and correct before continuing")
                progress["completed"].append(op["label"]+":"+op["kind"])
                progress.pop("pending",None)
                write_json(journal,progress)
            for op in ops:
                if s.classify(op)!="already_present": raise Stop(f"Post-write verification failed: {op['label']}")
            if stage=="shots":
                for shot in s.plan["slots"]:
                    a=s.t0+shot["start_f"]
                    v=next(t for t in s.bounds("video",1) if int(t.GetStart())==a)
                    au=next(t for t in s.bounds("audio",1) if int(t.GetStart())==a)
                    if not s.tl.SetClipsLinked([v,au],True): raise Stop(f"Could not link V1/A1: {shot['id']}")
            subs=s.subtitles() if stage=="voice" else None
            if not s.pm.SaveProject(): raise Stop("Resolve project could not be saved")
            progress["status"]="VERIFIED"; write_json(journal,progress)
            result={"plan_hash":object_hash(s.plan),"placed":len(todo),"verified":len(ops),"backup":backup,"subtitles":subs}
            write_json(prod(video)/f"{stage}_receipt.json",result)
            event(video,"VOICE_PLACED" if stage=="voice" else "WAITING_FOR_REVIEW",**result)
            return result
        finally:
            s.restore()


def info(video,resolve=None):
    s=Session(video,resolve)
    if not s.tl: return {"project":s.project.GetName(),"bin":s.bin("4. Timeline"),"timeline":"Edit not yet created"}
    return {"project":s.project.GetName(),"bin":s.bin("4. Timeline"),"timeline":"Edit","fps":s.plan["fps"],
            "tracks":{kind:[{"index":i,"name":s.tl.GetTrackName(kind,i),"items":len(s.bounds(kind,i))}
                             for i in range(1,int(s.tl.GetTrackCount(kind) or 0)+1)] for kind in ("video","audio","subtitle")}}


def live_check(session):
    s=session
    if not s.tl: raise Stop("Edit does not exist")
    fps=s.plan["fps"]; t0=int(s.tl.GetStartFrame())
    video=sorted(s.bounds("video",1),key=lambda x:int(x.GetStart()))
    if not video: raise Stop("V1 is empty")
    cursor=t0; rows=[]
    for item in video:
        a,b=int(item.GetStart()),int(item.GetEnd())
        if a!=cursor: raise Stop(f"V1 gap/overlap at frame {cursor-t0} after manual edit")
        if not math.floor(6*fps+1e-6)<=b-a<=math.ceil(9*fps-1e-6): raise Stop(f"V1 shot at {a-t0} is outside 6–9 seconds (one-frame quantization allowed)")
        path=item_path(item)
        if not Path(path).is_file(): raise Stop(f"Offline/missing V1 media: {path}")
        au=[x for x in s.bounds("audio",1) if int(x.GetStart())==a and int(x.GetEnd())==b and norm(item_path(x))==norm(path)]
        if len(au)!=1 or abs(int(au[0].GetLeftOffset())-int(item.GetLeftOffset()))>1:
            raise Stop(f"A1 no longer matches V1 at frame {a-t0}")
        rows.append({"start":a-t0,"end":b-t0,"path":norm(path),"in":item.GetLeftOffset(),
                     "properties":item.GetProperty()})
        cursor=b
    if len(s.bounds("audio",1))!=len(video): raise Stop("A1 contains extra unmatched audio")
    if (cursor-t0)/fps<480-1/fps: raise Stop("Final timeline is under 8 minutes")
    a2=sorted(s.bounds("audio",2),key=lambda x:int(x.GetStart()))
    if not a2: raise Stop("Narrator Voice A2 is empty")
    for a,b in zip(a2,a2[1:]):
        if int(a.GetEnd())>int(b.GetStart()): raise Stop("A2 narration overlaps")
    audio=[]
    for tr in (1,2,3):
        for item in s.bounds("audio",tr):
            if int(item.GetStart())<t0 or int(item.GetEnd())>cursor: raise Stop(f"A{tr} extends beyond picture")
            path=item_path(item)
            if not Path(path).is_file(): raise Stop(f"Offline audio: {path}")
            audio.append({"track":tr,"path":norm(path),"start":item.GetStart(),"end":item.GetEnd(),
                          "in":item.GetLeftOffset(),"properties":item.GetProperty()})
    # These properties are stable enough for diagnostics, not an assertion that every Fusion/grade edit is captured.
    return {"runtime_f":cursor-t0,"runtime_s":(cursor-t0)/fps,"v1_shots":len(video),"a2_items":len(a2),
            "snapshot_hash":object_hash({"video":rows,"audio":audio}),"picture":rows,"audio":audio}


def check(video,resolve=None):
    s=Session(video,resolve)
    report=live_check(s)
    write_json(prod(video)/"timeline_check.json",report)
    return {k:v for k,v in report.items() if k not in ("picture","audio")}


def music(video,path,start_s=0,resolve=None):
    """Place only an explicitly selected, locally licensed music file on A3."""
    m=probe(path,decode=True)
    if not m["audio"]: raise Stop("Music file has no audio")
    license_path=Path(str(path)+".license.txt")
    if not license_path.is_file(): raise Stop(f"Add the actual license/registration note: {license_path}")
    with lock(ROOT/".work/resolve.lock"),lock(prod(video)/"files.lock"):
        s=Session(video,resolve)
        try:
            end=min(s.plan["runtime_f"],frames(start_s+m["duration"],s.plan["fps"]))
            op={"label":"Music","kind":"audio","track":3,"bin":"2. Audio/Music","path":str(Path(path).resolve()),
                "source_fps":s.plan["fps"],"start_f":frames(start_s,s.plan["fps"]),"end_f":end,"source_start_s":0}
            if op["start_f"]<0 or end<=op["start_f"]: raise Stop("Invalid music range")
            needed=s.classify(op)=="add"; s.prepare()
            backup=s.backup("music") if needed else None
            if needed:
                item=s.append(op)
                if not item.SetProperty("AudioVolume",float(config().get("audio",{}).get("music_db",-24))):
                    raise Stop("Could not set starting music gain")
            if not s.pm.SaveProject(): raise Stop("Could not save project")
            return {"placed":needed,"backup":backup,"license":str(license_path),"note":"Starting gain only; listen to voice/music balance."}
        finally: s.restore()


def render_start(video,resolve=None):
    v=video_path(video)
    with lock(ROOT/".work/resolve.lock"),lock(prod(video)/"files.lock"):
        s=Session(v,resolve)
        try:
            state=read_json(prod(v)/"state.json")
            if state.get("stage") not in ("WAITING_FOR_REVIEW","RENDERED","UPLOADED"):
                raise Stop("Assemble and review the video first; /doc-edit done is the review approval")
            if s.project.IsRenderingInProgress(): raise Stop("Resolve is already rendering; no second job started")
            report=live_check(s)
            existing=prod(v)/"render.json"
            if existing.exists() and read_json(existing).get("status") in ("STARTING","RUNNING","UNKNOWN"):
                raise Stop("An earlier render is pending/uncertain; inspect render-status, do not duplicate the job")
            s.project.SetCurrentTimeline(s.tl)
            preset=config().get("resolve",{}).get("render_preset","YouTube 1080 HEVC")
            if not s.project.LoadRenderPreset(preset): raise Stop(f"Create Resolve render preset {preset!r}")
            if not s.pm.SaveProject(): raise Stop("Save project failed before render")
            from .core import atomic_text
            used_music=sorted({x["path"] for x in report["audio"] if x["track"]==3})
            lines=["# Music license records from the live Edit timeline", ""]
            for path in used_music:
                note=Path(path+".license.txt")
                lines.append(f"- {path} — {note if note.is_file() else 'MISSING license record; user must verify rights'}")
            atomic_text(v/"audio_licenses.md","\n".join(lines)+"\n")
            n=1; stem=f"Done_{v.name}"
            while (v/(stem+".mp4")).exists():
                n+=1; stem=f"Done_{v.name}_v{n}"
            if not s.project.SetRenderSettings({"SelectAllFrames":False,"MarkIn":int(s.tl.GetStartFrame()),
                "MarkOut":int(s.tl.GetStartFrame())+report["runtime_f"]-1,"TargetDir":str(v),"CustomName":stem,
                "ExportVideo":True,"ExportAudio":True}): raise Stop("Resolve refused render settings")
            # Subtitle export is configured in the named preset; do not change the user's subtitle track state.
            job=s.project.AddRenderJob()
            if not job: raise Stop("Could not create render job")
            result={"status":"STARTING","job":job,"path":str(v/(stem+".mp4")),"preset":preset,
                    "project":s.project.GetName(),"runtime_s":report["runtime_s"],"snapshot_hash":report["snapshot_hash"]}
            write_json(existing,result)
            if not s.project.StartRendering(job):
                result["status"]="UNKNOWN";write_json(existing,result)
                raise Stop("StartRendering refused; inspect Resolve render queue before retrying")
            result["status"]="RUNNING";write_json(existing,result)
            event(v,"RENDERING",render_job=job)
            return result
        finally: s.restore()


def render_status(video,resolve=None):
    v=video_path(video); receipt=prod(v)/"render.json"
    with lock(ROOT/".work/resolve.lock"),lock(prod(v)/"files.lock"):
        result=read_json(receipt)
        if result["status"]=="VERIFIED": return result
        r=resolve or connect(config()); p=r.GetProjectManager().GetCurrentProject()
        if not p or p.GetName()!=result["project"]: raise Stop("Open the project that owns this render")
        status=p.GetRenderJobStatus(result["job"]) or {}
        if status.get("JobStatus")!="Complete":
            if status.get("JobStatus") in ("Failed","Cancelled"):
                result["status"]="FAILED"; write_json(receipt,result)
                event(v,"RENDER_FAILED",error=status)
            return {**result,"resolve_status":status}
        m=probe(result["path"],decode=True)
        if not m["video"] or not m["audio"] or abs(m["duration"]-result["runtime_s"])>.15:
            raise Stop("Rendered output is incomplete or has the wrong duration; not marked complete")
        result.update(status="VERIFIED",sha256=m["sha256"],duration=m["duration"])
        write_json(receipt,result); event(v,"RENDERED",render_file=result["path"])
        return result
