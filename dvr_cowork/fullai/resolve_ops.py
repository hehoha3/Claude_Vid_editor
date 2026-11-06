"""Narrow, additive Resolve adapter. Never clear tracks or rewrite a manual edit."""
from __future__ import annotations

from datetime import datetime
import math
import re
from pathlib import Path
from .core import (Stop, config, resolve_lock, event, frames, lock, object_hash, probe, prod, run,
                   read_json, video_path, write_json, day_project)
from .pipeline import assert_voice_media, hook_window, ingested_media, intro_gap_f, subtitle_file
from ..resolve_conn import connect
from .story import load_plan

# Same project layout as the 1h videos (user 2026-11-04): bins 1-7 per channel, "Edit" in 6. Timeline, A1-A9.
BINS=("1. Other_roll","2. Attack_roll","3. Run_roll","4. Audio","4. Audio/Narrator","4. Audio/Ambience","4. Audio/SFX",
      "4. Audio/Music","5. Graphics","6. Timeline")  # no "7. Open": footage+AI only (user 2026-11-05)
TIMELINE_BIN="6. Timeline"
LEGACY_TIMELINE_BIN="4. Timeline"  # 8p projects made before 2026-11-04
SHOT_BIN,NARRATOR_BIN,MUSIC_BIN,BED_BIN,SUB_BIN="1. Other_roll","4. Audio/Narrator","4. Audio/Music","4. Audio/Ambience","5. Graphics"
SHOT_A,VOICE_A,BED_A,BIRD_A,MUSIC_A=1,2,3,5,7  # A1 clip sound, A2 narrator, A3/A4 wind beds, A5 birds, A7/A8 intro song
AUDIO_TRACKS=9
TRACKS=dict(enumerate(("Audio v1","Narrator Voice","Ambience 1","Ambience 2","Ambience 3","Natural sounds","Music",
                        "SXF 1","SXF 2"),1))  # the 1h template's names; only Resolve defaults ("Audio 3") are renamed


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


def fkey(p):
    """Media-pool lookup key without touching the disk (norm() resolves: one NAS round trip per Z:\\ clip)."""
    import os
    return os.path.normcase(os.path.abspath(str(p))) if p else ""


class Session:
    def __init__(self,video,resolve=None):
        self.video=video_path(video)
        self.plan=load_plan(video,conformed=True)
        self.resolve=resolve or connect(config())
        self.pm=self.resolve.GetProjectManager()
        self.project=self.pm.GetCurrentProject()
        expected=self.plan["source"].get("resolve_project",day_project(self.video.name))
        if not self.project or self.project.GetName()!=expected:
            raise Stop(f"Open Resolve project {expected!r}; no other project is modified.")
        self.mp=self.project.GetMediaPool()
        self.previous=self.project.GetCurrentTimeline()
        self.previous_bin=self.mp.GetCurrentFolder()
        # One project can hold one video per channel: Chann_N/<bins>, each with its own Edit in Chann_N/6. Timeline.
        self.ch=channel(self.video)
        self.all_edits=[t for t in (self.project.GetTimelineByIndex(i) for i in range(1,self.project.GetTimelineCount()+1))
                        if t and t.GetName()=="Edit"]
        self.tl=None
        for name in (TIMELINE_BIN,LEGACY_TIMELINE_BIN):
            matches=self.all_edits
            if self.ch or name==LEGACY_TIMELINE_BIN:
                home=ensure_bin(self.mp,self.bin(name),create=False)
                ids={c.GetUniqueId() for c in (home.GetClipList() or [])} if home else set()
                matches=[t for t in matches if t.GetMediaPoolItem() and t.GetMediaPoolItem().GetUniqueId() in ids]
            if len(matches)>1: raise Stop(f"More than one Edit timeline in {self.bin(name)}; keep exactly one.")
            if matches: self.tl=matches[0]; break
        if self.tl:
            fps=float(self.tl.GetSetting("timelineFrameRate") or self.project.GetSetting("timelineFrameRate"))
            if abs(fps-self.plan["fps"])>.001: raise Stop(f"Timeline fps {fps} != plan fps {self.plan['fps']}")
        self._clips=None
        self.end_mode=config().get("resolve",{}).get("source_end","exclusive")
        if self.end_mode not in ("exclusive","inclusive"): raise Stop("source_end must be exclusive or inclusive")

    def bin(self,name): return f"{self.ch}/{name}" if self.ch else name

    def restore(self):
        if self.previous: self.project.SetCurrentTimeline(self.previous)
        if self.previous_bin: self.mp.SetCurrentFolder(self.previous_bin)

    def prepare(self):
        for b in BINS: ensure_bin(self.mp,self.bin(b))
        dst=ensure_bin(self.mp,self.bin(TIMELINE_BIN))
        self.mp.SetCurrentFolder(dst)
        if not self.tl:
            if self.all_edits:  # Resolve's API refuses a second timeline with the same name
                raise Stop(f"Another channel's Edit exists; create an empty Edit in {self.bin(TIMELINE_BIN)} by hand "
                           "(the Resolve UI allows the same name) or use the 1h project template, then rerun")
            try: current=float(self.project.GetSetting("timelineFrameRate"))
            except (TypeError,ValueError): current=None
            # The project rate is shared by every channel's Edit; only set it when it differs.
            if current is None or abs(current-self.plan["fps"])>.001:
                fps=str(self.plan["fps"]).removesuffix(".0")
                if not self.project.SetSetting("timelineFrameRate",fps): raise Stop("Set project frame rate before creating Edit")
            self.tl=self.mp.CreateEmptyTimeline("Edit")
            if not self.tl: raise Stop(f"Could not create Edit in {self.bin(TIMELINE_BIN)}")
        elif not self.ch:
            timeline_clip=self.tl.GetMediaPoolItem()
            if timeline_clip and not any(c.GetUniqueId()==timeline_clip.GetUniqueId() for c in dst.GetClipList() or []):
                if not self.mp.MoveClips([timeline_clip],dst): raise Stop(f"Could not put Edit in {TIMELINE_BIN}")
        if not self.project.SetCurrentTimeline(self.tl): raise Stop("Could not select Edit")
        while int(self.tl.GetTrackCount("video") or 0)<1:
            if not self.tl.AddTrack("video"): raise Stop("Could not create V1")
        while int(self.tl.GetTrackCount("audio") or 0)<AUDIO_TRACKS:
            n=int(self.tl.GetTrackCount("audio") or 0)
            if not (self.tl.AddTrack("audio","stereo") or self.tl.AddTrack("audio",{"audioType":"stereo"})) \
                    or int(self.tl.GetTrackCount("audio") or 0)<=n: raise Stop(f"Could not create audio track A{n+1}")
        for i,name in TRACKS.items():
            if re.fullmatch(r"(?i)audio\s*\d+",str(self.tl.GetTrackName("audio",i) or "")) \
                    and not self.tl.SetTrackName("audio",i,name): raise Stop(f"Could not name A{i}")
        self.t0=int(self.tl.GetStartFrame())

    def backup(self,label):
        name=f"Edit_bak_{label}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        self.mp.SetCurrentFolder(ensure_bin(self.mp,self.bin(TIMELINE_BIN)))
        if not self.tl.DuplicateTimeline(name): raise Stop("Backup failed; no timeline clips changed")
        self.project.SetCurrentTimeline(self.tl)
        return name

    @property
    def clips(self):
        """path -> MediaPoolItem; the whole pool is walked once per run (it was walked once per op)."""
        if self._clips is None:
            self._clips={}
            for c in all_clips(self.mp.GetRootFolder()):
                self._clips.setdefault(fkey(c.GetClipProperty("File Path")),c)
        return self._clips

    def preload(self,ops):
        """One ImportMedia per bin for every file of ops the pool lacks (shots -> 1. Other_roll in one call)."""
        need={}
        for op in ops:
            p=str(Path(op["path"]).resolve())
            if fkey(p) not in self.clips: need.setdefault(op["bin"],{})[fkey(p)]=p
        for bin_name,paths in need.items():
            self.mp.SetCurrentFolder(ensure_bin(self.mp,self.bin(bin_name)))
            for c in self.mp.ImportMedia(list(paths.values())) or []:
                self.clips.setdefault(fkey(c.GetClipProperty("File Path")),c)
            lost=[p for k,p in paths.items() if k not in self.clips]
            if lost: raise Stop(f"Failed to import {len(lost)} file(s): {lost[:3]}")

    def media(self,path,bin_name):
        self.preload([{"path":path,"bin":bin_name}])
        return self.clips[fkey(Path(path).resolve())]

    def bounds(self,kind,track):
        return self.tl.GetItemListInTrack(kind,track) or [] if self.tl else []

    def rows(self,kind,track):
        """One read of a track: (start, end, path, source-in, item) per item."""
        return [(int(i.GetStart()),int(i.GetEnd()),norm(item_path(i)),int(i.GetLeftOffset()),i)
                for i in self.bounds(kind,track)]

    def snap(self,ops):
        """Every track ops touch, read once; pass to classify() instead of re-reading a track per op."""
        return {(k,t):self.rows(k,t) for k,t in {(op["kind"],op["track"]) for op in ops}}

    def classify(self,op,snap=None):
        if not self.tl: return "add"
        a,b=op["start_f"]+int(self.tl.GetStartFrame()),op["end_f"]+int(self.tl.GetStartFrame())
        rows=snap[op["kind"],op["track"]] if snap is not None else self.rows(op["kind"],op["track"])
        for x,y,path,offset,_ in rows:
            if x<b and a<y:
                same=(x==a and y==b and path==norm(op["path"]))
                if same and abs(offset-frames(op.get("source_start_s",0),float(op["source_fps"])))<=1:
                    return "already_present"
                raise Stop(f"Manual/foreign edit conflicts with {op['label']} on {op['kind']} {op['track']}, "
                           f"frame {a}. Kept untouched; inspect the timeline.")
        return "add"

    def info(self,op):
        """AppendToTimeline clipInfo of op + the source-in frame it must land on."""
        mp=self.media(op["path"],op["bin"])
        fps=self.plan["fps"]
        raw_fps=mp.GetClipProperty("FPS")
        try: sfps=float(raw_fps) if raw_fps else float(op["source_fps"])
        except (TypeError,ValueError): sfps=float(op["source_fps"])
        if not math.isfinite(sfps) or sfps<=0: raise Stop(f"Invalid imported clip frame rate: {op['label']}")
        start=frames(op.get("source_start_s",0),sfps)
        speed=float(op.get("speed",1.0))  # intro cut retime: source span = timeline duration × speed
        n=round((op["end_f"]-op["start_f"])*speed*sfps/fps)
        end=start+n-(self.end_mode=="inclusive")
        return {"mediaPoolItem":mp,"mediaType":1 if op["kind"]=="video" else 2,"trackIndex":op["track"],
                "recordFrame":self.t0+op["start_f"],"startFrame":start,"endFrame":end},start

    def append_many(self,ops,progress,journal,chunk=50):
        """Unretimed ops in a few AppendToTimeline calls (was one call + readbacks per op). The caller verifies
        every op afterwards from a fresh read; a short result stops with the backup (rerun resumes: present
        items are kept)."""
        self.preload(ops)
        for i in range(0,len(ops),chunk):
            part=ops[i:i+chunk]
            progress["pending"]=[op["label"]+":"+op["kind"] for op in part]; write_json(journal,progress)
            infos=[self.info(op) for op in part]
            got=self.mp.AppendToTimeline([c for c,_ in infos]) or []
            if len(got)!=len(part):
                raise Stop(f"Append failed: {len(got)}/{len(part)} items from {part[0]['label']}; "
                           "recover using backup, never clear tracks")
            for op,(_,start),item in zip(part,infos,got):  # the returned items, no track re-read
                if abs(int(item.GetLeftOffset())-start)>1: raise Stop(f"Source-in mismatch at {op['label']}")
                if int(item.GetStart())!=self.t0+op["start_f"] or int(item.GetEnd())!=self.t0+op["end_f"]:
                    raise Stop(f"Resolve frame convention/conform mismatch at {op['label']}. Partial edit kept with "
                               "backup. Check source_end and installed Scripting/README.txt; no automatic retry.")
            progress["completed"]+=progress.pop("pending"); write_json(journal,progress)

    def append(self,op):
        """One op, read back at once (retimed intro cuts; music / beds)."""
        clip,start=self.info(op)
        duration=op["end_f"]-op["start_f"]
        speed=float(op.get("speed",1.0))
        if speed!=1.0:
            # Appended at source length first, then sped up in place: that span must be free on the track.
            a,b=self.t0+op["start_f"],self.t0+op["start_f"]+math.ceil(duration*speed)
            if any(int(x.GetStart())<b and a<int(x.GetEnd()) for x in self.bounds(op["kind"],op["track"])):
                raise Stop(f"No free room to retime {op['label']}; kept untouched")
        result=self.mp.AppendToTimeline([clip]) or []
        if len(result)!=1: raise Stop(f"Append failed: {op['label']}; recover using backup, never clear tracks")
        item=result[0]
        if abs(int(item.GetLeftOffset())-start)>1: raise Stop(f"Source-in mismatch at {op['label']}")
        if speed!=1.0:
            if not hasattr(item,"SetSpeed") or not item.SetSpeed({"Percentage":speed*100,"PitchCorrection":True,
                                                                   "RippleTimeline":False}):
                raise Stop(f"This Resolve API refused SetSpeed at {op['label']}; set hook_speed 1.0 or retime by hand")
        if int(item.GetStart())!=self.t0+op["start_f"] or int(item.GetEnd())!=self.t0+op["end_f"]:
            raise Stop(f"Resolve frame convention/conform{'/retime' if speed!=1.0 else ''} mismatch at {op['label']}. "
                       "Partial edit kept with backup. Check source_end and installed Scripting/README.txt; no automatic retry.")
        return item

    def subtitles(self):
        path=subtitle_file(self.video,self.plan)
        try:
            imported=self.media(path,SUB_BIN)
        except Stop:
            return f"SRT created at {path}; this Resolve API refused import. Import into {self.bin(SUB_BIN)} manually"
        if self.tl.GetTrackCount("subtitle") and self.tl.GetItemListInTrack("subtitle",1):
            return f"SRT in {self.bin(SUB_BIN)}; existing subtitle edits preserved"
        if not self.tl.GetTrackCount("subtitle") and not self.tl.AddTrack("subtitle"):
            return "SRT imported; add subtitle track manually (API refused)"
        # Resolve versions differ on SRT append support. Never report success without visible items.
        self.mp.AppendToTimeline([{"mediaPoolItem":imported,"recordFrame":self.t0}])
        got=self.tl.GetItemListInTrack("subtitle",1) or []
        if len(got)!=len(self.plan["voice"]): return "SRT imported; subtitle append unsupported/partial: drag SRT onto Subtitle 1 manually"
        return f"{len(got)} Vietnamese subtitle items placed"


def voice_operations(video,plan):
    media=assert_voice_media(video,plan)
    return [{"label":f"VO {v['id']}","kind":"audio","track":VOICE_A,"bin":NARRATOR_BIN,
             "path":media[str(v["id"])]["path"],"source_fps":plan["fps"],
             "start_f":v["start_f"],"end_f":v["end_f"],"source_start_s":0} for v in plan["voice"]]


def shot_operations(video):
    plan,media,qc=ingested_media(video)
    path=prod(video)/"hook.json"
    # No hook.json yet (user 2026-11-05): body slots go up first, the intro window stays empty until `hook`;
    # done's live_check refuses the V1 gap at frame 0, so nothing renders without the intro.
    selection=read_json(path) if path.exists() else None
    if selection and selection["plan_hash"]!=object_hash(plan): raise Stop("Hook selection belongs to another plan")
    cuts=selection.get("cuts") if selection else None  # intro = 2–4 s cuts from body sources (user 2026-11-05)
    if selection and cuts is None: raise Stop("hook.json is the old 6 s layout; rerun hook (2–4 s cuts), then assemble --rehook")
    out=[]
    if cuts:
        a,b=hook_window(plan)
        edges=[a]+[c["end_f"] for c in cuts]
        if [c["start_f"] for c in cuts]!=edges[:-1] or edges[-1]!=b-intro_gap_f(plan):
            raise Stop("hook.json cuts do not tile the intro window; rerun hook")
        for c in cuts:
            m=media[str(c["source_prompt"])]
            if c["sha256"]!=m["sha256"]: raise Stop("Hook source changed since selection")
            if c["source_start_s"]+c["source_span_s"]>m["duration"]+1/max(1,m["fps"]):
                raise Stop(f"Intro cut {c['cut']} runs past the end of {c['source_prompt']}.mp4")
            for kind,track in (("video",1),("audio",SHOT_A))[:2 if c["a1"]=="keep" else 1]:
                out.append({"label":f"HOOK.{c['cut']}","kind":kind,"track":track,"bin":SHOT_BIN,"path":m["path"],
                            "source_fps":m["fps"],"start_f":c["start_f"],"end_f":c["end_f"],
                            "source_start_s":c["source_start_s"],"speed":c["speed"]})
    for s in plan["slots"]:
        if s["phase"]=="hook": continue
        m=media[str(s["prompt_id"])]
        if m["fps"]<=0: raise Stop(f"Cannot determine source fps: {m['path']}")
        for kind,track in (("video",1),("audio",SHOT_A)):
            out.append({"label":s["id"],"kind":kind,"track":track,"bin":SHOT_BIN,"path":m["path"],
                        "source_fps":m["fps"],"start_f":s["start_f"],"end_f":s["end_f"],"source_start_s":0})
    return out


def black_fades(s):
    """The 1h black fades on V1 (user 2026-11-05, same as 1h): from black on the shot at 0:00 (1 s) and on the first
    story shot after the intro (2.5 s), to black on the last intro cut (1.5 s) and on the film's last shot
    (3 s, at most the shot - 7 f); the same fades on each one's A1 sound. Only a missing / shorter fade is set,
    then read back. -> report line."""
    fps=s.plan["fps"]; t0=int(s.tl.GetStartFrame()); f=lambda x:round(x*fps)
    v=sorted(s.bounds("video",1),key=lambda i:int(i.GetStart()))
    if not v: return "black fades: V1 empty"
    want=[(v[0],f(1.0),0)] if int(v[0].GetStart())==t0 else []
    want.append((v[-1],0,min(f(3.0),int(v[-1].GetEnd())-int(v[-1].GetStart())-7)))
    k=next((j for j,i in enumerate(v) if int(i.GetStart())==t0+hook_window(s.plan)[1]),0)
    if k: want+=[(v[k-1],0,f(1.5)),(v[k],f(2.5),0)]  # intro on the timeline: dip to black into the story
    # A1 (user 2026-11-06): each faded shot's own sound fades with its picture (retimed intro cuts have no A1).
    a1={(int(i.GetStart()),int(i.GetEnd())):i for i in s.bounds("audio",SHOT_A)}
    want+=[(a1[key],fi,fo) for it,fi,fo in list(want) if (key:=(int(it.GetStart()),int(it.GetEnd()))) in a1]
    fixed,bad=0,[]
    for it,fi,fo in want:
        g=it.GetFades() or {}
        old=(int(g.get("FadeIn",0)),int(g.get("FadeOut",0)))
        new=(max(old[0],fi),max(old[1],fo))
        if new==old: continue
        fixed+=1; it.SetFades({"FadeIn":new[0],"FadeOut":new[1]})
        g=it.GetFades() or {}
        if (int(g.get("FadeIn",0)),int(g.get("FadeOut",0)))!=new: bad.append(f"{(int(it.GetStart())-t0)/fps:.1f}s")
    return f"black fades: {len(want)} checked, {fixed} set"+(f", NOT SET at {bad}" if bad else "")


def stale_intro(s,video,ops):
    """V1 / A1 items inside the intro window that the new hook.json no longer wants (assemble --rehook). Only this
    video's own shots qualify; anything else inside the window stops the run untouched."""
    t0=int(s.tl.GetStartFrame()); a,b=(t0+x for x in hook_window(s.plan))
    want={(op["kind"],op["track"],t0+op["start_f"],t0+op["end_f"],norm(op["path"])):frames(op["source_start_s"],op["source_fps"])
          for op in ops}
    mine={norm(m["path"]) for m in read_json(prod(video)/"shot_media.json").values()}
    out=[]
    for kind,track in (("video",1),("audio",SHOT_A)):
        for it in s.bounds(kind,track):
            x,y,p=int(it.GetStart()),int(it.GetEnd()),norm(item_path(it))
            if x>=b or y<=a: continue
            k=(kind,track,x,y,p)
            if k in want and abs(int(it.GetLeftOffset())-want[k])<=1: continue
            if p not in mine or y>b: raise Stop(f"Foreign / manual item in the intro on {kind} {track} at frame {x-t0}; kept untouched")
            out.append(it)
    return out


def apply(video,stage,resolve=None,rehook=False):
    video=video_path(video)
    with resolve_lock(),lock(prod(video)/"files.lock"):
        session=Session(video,resolve)
        s=session
        try:
            ops=voice_operations(video,s.plan) if stage=="voice" else shot_operations(video)
            if stage=="shots":
                voice_receipt=prod(video)/"voice_receipt.json"
                if not voice_receipt.exists(): raise Stop("Place and verify A2 before placing generated shots")
                vops=voice_operations(video,s.plan); vsnap=s.snap(vops)
                for op in vops:
                    if s.classify(op,vsnap)!="already_present": raise Stop("A2 is incomplete; resume the voice stage first")
            key=lambda it:(int(it.GetStart()),int(it.GetEnd()),norm(item_path(it)))
            stale=stale_intro(s,video,ops) if rehook and s.tl else []
            gone={key(it) for it in stale}
            # Detect every overlap before changing any bin/track/timeline (stale intro items are replaced below).
            snap=s.snap(ops)
            todo=[] if stale else [op for op in ops if s.classify(op,snap)=="add"]
            if s.tl:
                for kind,track in snap:
                    expected={(int(s.tl.GetStartFrame())+op["start_f"],int(s.tl.GetStartFrame())+op["end_f"],norm(op["path"]))
                              for op in ops if (op["kind"],op["track"])==(kind,track)}
                    for row in snap[kind,track]:
                        if row[:3] not in expected and row[:3] not in gone:
                            raise Stop(f"Unexpected existing item on {kind} {track}; preserve it and inspect this project before assembly")
            s.prepare()
            backup=s.backup(stage) if todo or stale else None
            if stale:  # the old intro this engine placed; the backup above is the way back
                if not s.tl.DeleteClips(stale,False): raise Stop(f"Could not remove the old intro items; backup {backup}")
                snap=s.snap(ops)
                todo=[op for op in ops if s.classify(op,snap)=="add"]
            journal=prod(video)/f"{stage}_journal.json"
            progress={"status":"WRITING","backup":backup,"plan_hash":object_hash(s.plan),"completed":[]}
            write_json(journal,progress)
            s.preload(todo)  # every missing file in one ImportMedia per bin
            # Retimed intro cuts first, one by one: each needs free room past its end until it is sped up.
            for op in [o for o in todo if float(o.get("speed",1.0))!=1.0]:
                progress["pending"]=[op["label"]+":"+op["kind"]]; write_json(journal,progress)
                s.append(op)
                progress["completed"]+=progress.pop("pending"); write_json(journal,progress)
            s.append_many([o for o in todo if float(o.get("speed",1.0))==1.0],progress,journal)
            snap=s.snap(ops)  # fresh read = the truth for verify, gain and link
            for op in ops:
                if s.classify(op,snap)!="already_present": raise Stop(f"Post-write verification failed: {op['label']}")
            at={kt:{r[0]:r[4] for r in rows} for kt,rows in snap.items()}
            db=float(config().get("audio",{}).get("shot_db",-12))
            for op in todo:
                if op["kind"]=="audio" and op["track"]==SHOT_A and not at["audio",SHOT_A][s.t0+op["start_f"]].SetProperty("AudioVolume",db):
                    raise Stop("Could not set A1 gain; listen and correct before continuing")
            if stage=="shots":
                twins={op["label"] for op in ops if op["kind"]=="audio"}  # retimed intro cuts are muted: no A1
                for op in ops:
                    if op["kind"]!="video" or op["label"] not in twins: continue
                    a=s.t0+op["start_f"]
                    if not s.tl.SetClipsLinked([at["video",1][a],at["audio",SHOT_A][a]],True):
                        raise Stop(f"Could not link V1/A1: {op['label']}")
            subs=s.subtitles() if stage=="voice" else None
            fades=black_fades(s) if stage=="shots" else None
            if not s.pm.SaveProject(): raise Stop("Resolve project could not be saved")
            progress["status"]="VERIFIED"; write_json(journal,progress)
            result={"plan_hash":object_hash(s.plan),"placed":len(todo),"verified":len(ops),"backup":backup,"subtitles":subs}
            if fades: result["black_fades"]=fades
            write_json(prod(video)/f"{stage}_receipt.json",result)
            event(video,"VOICE_PLACED" if stage=="voice" else "WAITING_FOR_REVIEW",**result)
            return result
        finally:
            s.restore()


def voice_ready(video,write=False,resolve=None):
    """`/doc-edit <audios>` in one call: conform the real MP3s -> A2 + SRT placed and verified -> prompts for every
    non-hook slot. A voice problem stops inside conform, before Resolve is touched; reruns are idempotent."""
    from .pipeline import conform,missing_prompts
    c=conform(video)
    if not write:
        return {"conform":c,"dry_run":True,"next":"--apply: A2 + SRT (backup first), then the prompts"}
    vo=apply(video,"voice",resolve)
    with lock(prod(video)/"files.lock"):
        pr=missing_prompts(video)
    have=len(list((video_path(video)/"shots").glob("*.mp4")))
    return {"runtime_s":c["runtime_s"],"a2_placed":vo["placed"],"a2_verified":vo["verified"],"occupancy":c["occupancy"],
            "backup":vo["backup"],"subtitles":vo["subtitles"],**pr,"shots_present":have,
            "next":"ingest" if have>=pr["prompts"] else "stop: the user generates the shots"}


def shots_ready(video,write=False,resolve=None):
    """`/doc-edit <video>` once shots/ is complete: ingest -> body on V1/A1 -> contact sheets for the hook review.
    Claude views the sheets and marks hook_ok, then `finish`. Reruns keep unchanged files and items."""
    from .pipeline import ingest,sheets
    i=ingest(video)
    if not write:
        return {"ingest":i,"dry_run":True,"next":"--apply: body on V1/A1 (backup first), then the sheets"}
    return {"ingest":i,"assemble":apply(video,"shots",resolve),"sheets":sheets(video),
            "next":"view the sheets, mark hook_ok in shot_qc, then finish <video> <song> --apply"}


def finish(video,song,write=False,resolve=None,**sound):
    """Hook 30 s -> intro cuts on V1 -> intro song + wind beds + birds -> check; then the user reviews (no colour)."""
    from .pipeline import hook
    h=hook(video)
    if not write:
        return {"hook":h,"dry_run":True,"next":"--apply: intro on V1, song A7/A8, beds A3/A4, birds A5 (backup first)"}
    a=apply(video,"shots",resolve)
    m=music(video,song,resolve=resolve,**sound)
    return {"hook":h,"assemble":a,"music":m,"check":check(video,resolve),
            "next":"stop: the user reviews on the timeline, then /doc-edit done"}


def info(video,resolve=None):
    s=Session(video,resolve)
    if not s.tl: return {"project":s.project.GetName(),"bin":s.bin(TIMELINE_BIN),"timeline":"Edit not yet created"}
    return {"project":s.project.GetName(),"bin":s.bin(TIMELINE_BIN),"timeline":"Edit","fps":s.plan["fps"],
            "tracks":{kind:[{"index":i,"name":s.tl.GetTrackName(kind,i),"items":len(s.bounds(kind,i))}
                             for i in range(1,int(s.tl.GetTrackCount(kind) or 0)+1)] for kind in ("video","audio","subtitle")}}


def live_check(session):
    s=session
    if not s.tl: raise Stop("Edit does not exist")
    fps=s.plan["fps"]; t0=int(s.tl.GetStartFrame())
    video=sorted(s.bounds("video",1),key=lambda x:int(x.GetStart()))
    if not video: raise Stop("V1 is empty")
    from .pipeline import intro_rules
    rules=s.plan.get("rules") or {}
    intro=intro_rules(s.video,s.plan)
    lo,hi=(rules.get("body") or {}).get("shot_min_s",6),(rules.get("body") or {}).get("shot_max_s",9)
    # Inside the hook window V1 holds intro cuts (cut_min–cut_max s); a retimed cut may have no A1 (muted).
    window=t0+hook_window(s.plan)[1]
    cursor=t0; rows=[]; matched=0
    for item in video:
        a,b=int(item.GetStart()),int(item.GetEnd())
        gap=intro_gap_f(s.plan)  # the planned black before story 1 is the one allowed V1 gap
        if a!=cursor and not (gap and cursor==window-gap and a==window):
            raise Stop(f"V1 gap/overlap at frame {cursor-t0} after manual edit")
        x,y=(intro["cut_min_s"],intro["cut_max_s"]) if b<=window else (lo,hi)
        if not math.floor(x*fps+1e-6)<=b-a<=math.ceil(y*fps-1e-6):
            raise Stop(f"V1 {'intro cut' if b<=window else 'shot'} at {a-t0} is outside {x:g}–{y:g} seconds (one-frame quantization allowed)")
        path=item_path(item)
        if not Path(path).is_file(): raise Stop(f"Offline/missing V1 media: {path}")
        au=[x for x in s.bounds("audio",SHOT_A) if int(x.GetStart())==a and int(x.GetEnd())==b and norm(item_path(x))==norm(path)]
        if (au or b>window) and (len(au)!=1 or abs(int(au[0].GetLeftOffset())-int(item.GetLeftOffset()))>1):
            raise Stop(f"A1 no longer matches V1 at frame {a-t0}")
        matched+=len(au)
        rows.append({"start":a-t0,"end":b-t0,"path":norm(path),"in":item.GetLeftOffset(),
                     "properties":item.GetProperty()})
        cursor=b
    if len(s.bounds("audio",SHOT_A))!=matched: raise Stop("A1 contains extra unmatched audio")
    minimum=(rules.get("runtime") or {}).get("min_minutes",8)*60
    if (cursor-t0)/fps<minimum-1/fps: raise Stop(f"Final timeline is under {minimum/60:g} minutes")
    a2=sorted(s.bounds("audio",VOICE_A),key=lambda x:int(x.GetStart()))
    if not a2: raise Stop("Narrator A2 is empty")
    for a,b in zip(a2,a2[1:]):
        if int(a.GetEnd())>int(b.GetStart()): raise Stop("A2 narration overlaps")
    audio=[]
    for tr in range(1,int(s.tl.GetTrackCount("audio") or 0)+1):
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


def license_note(path):
    """<file>.license.txt, <stem>.license.txt (D:\\Audio_lib Epidemic/Suno), or a Pixabay note named
    *-<id>-license.txt next to <artist>-<slug>-<id>.mp3."""
    p=Path(path); exact=Path(str(p)+".license.txt")
    if exact.is_file(): return exact
    if p.with_suffix(".license.txt").is_file(): return p.with_suffix(".license.txt")
    m=re.search(r"-(\d+)$",p.stem)
    hits=sorted(p.parent.glob(f"*-{m[1]}-license.txt")) if m else []
    if len(hits)==1: return hits[0]
    raise Stop(f"Add the actual license/registration note: {exact}")


def a3_fades(op,fps):
    """Fade handles in frames (seconds on the op): crossfades between beds, the first bed rises out of the song's decay."""
    return {"FadeIn":frames(op["fade_in_s"],fps),"FadeOut":frames(op["fade_out_s"],fps)}


def bed_file(video,src,seconds,fps):
    """An original licensed recording long enough for the span is placed as-is; a short one (or none = synthesized
    wind) is looped into <video>/music, named by its inputs so a re-run reuses it."""
    w=probe(src,decode=True) if src else None
    if w and not w["audio"]: raise Stop(f"Bed file has no audio: {src}")
    if w and w["duration"]>=seconds: license_note(src); return str(src)
    note=license_note(src).read_text(encoding="utf-8",errors="replace") if src else \
        "Synthesized locally with FFmpeg anoisesrc (brown noise); no third-party material.\n"
    key=object_hash({"wind":w["sha256"] if w else "synth","s":round(seconds*fps),"fps":fps,"fades":"resolve"})[:10]
    out=video_path(video)/"music"; out.mkdir(exist_ok=True)
    bed=out/f"a3_wind_{key}.wav"
    if not bed.exists():
        # asetpts: -stream_loop leaves pts gaps between mp3 loops, so -t would cut the bed short of the slot
        args=["-stream_loop","-1","-i",src,"-af","asetpts=N/SR/TB"] if src else ["-filter_complex",
            # two seeds = decorrelated L/R; lowpass + slow tremolo reads as gusting mountain wind
            "anoisesrc=c=brown:r=48000:a=0.5:s=1[l];anoisesrc=c=brown:r=48000:a=0.5:s=2[r];"
            "[l][r]join=inputs=2:channel_layout=stereo,highpass=f=60,lowpass=f=700,tremolo=f=0.12:d=0.5"]
        run(["ffmpeg","-nostdin","-v","error",*args,"-t",f"{seconds:.4f}","-ar","48000","-ac","2","-c:a","pcm_s16le",bed],timeout=600)
    Path(str(bed)+".license.txt").write_text(note,encoding="utf-8")
    return str(bed)


def a3_beds(video,plan,intro,wind=None,beds=None,birds=None):
    """A7/A8: the original intro song cut opening -> climax -> ending under the hook (intro_music.plan; the file
    itself, three times). A3/A4: one wind / ambience bed per scene after the hook, alternating with crossfades;
    beds = {scene id: licensed file}, a scene without one gets `wind` (else synthesized wind).
    A5: birds = {prompt id: licensed bird file} on the calm shots, one item per slot (user 2026-11-05)."""
    from . import intro_music
    a=config().get("audio",{}); fps=plan["fps"]
    cut=hook_window(plan)[1]; end=plan["runtime_f"]
    license_note(intro)
    score=intro_music.plan(intro,cut/fps)
    ops=[{"label":g["label"],"kind":"audio","track":g["track"],"bin":MUSIC_BIN,"path":str(intro),"source_fps":fps,
          "start_f":frames(g["start_s"],fps),"end_f":min(cut,frames(g["end_s"],fps)),"source_start_s":g["source_start_s"],
          "db":"music_db","fade_in_s":g["fade_in_s"],"fade_out_s":g["fade_out_s"],"score":score}
         for g in score["segments"]]
    fade=a.get("fade_s",2); xf=a.get("bed_crossfade_s",4); half=frames(xf/2,fps)
    scenes=[sc for sc in plan["scenes"] if sc["end_f"]>cut]
    unknown=set(beds or {})-{sc["id"] for sc in scenes}
    if unknown: raise Stop(f"Beds for unknown / hook scenes: {sorted(unknown)}")
    for k,sc in enumerate(scenes):
        first,last=k==0,k==len(scenes)-1
        a0=max(cut,sc["start_f"]) if first else sc["start_f"]-half
        b0=end if last else sc["end_f"]+half
        path=bed_file(video,(beds or {}).get(sc["id"]) or wind,(b0-a0)/fps,fps)
        ops.append({"label":f"Bed {sc['id']}","kind":"audio","track":BED_A if k%2==0 else BED_A+1,"bin":BED_BIN,
                    "path":path,"source_fps":fps,"start_f":a0,"end_f":b0,"source_start_s":0,"db":"wind_db",
                    "fade_in_s":a.get("wind_fade_in_s",fade) if first else xf,"fade_out_s":fade if last else xf})
    p=frames(a.get("prelap_s",0),fps)
    if p and scenes:  # 1h pre-lap (user 2026-11-06): story 1's wind on A5 bridges the black gap, intro -> story
        a0,b0=max(0,cut-intro_gap_f(plan)-p),cut+p
        src=(beds or {}).get(scenes[0]["id"]) or wind
        path=bed_file(video,src,(b0-a0)/fps,fps)
        tail=max(0.0,probe(path)["duration"]-(b0-a0)/fps-0.1)  # the file's end: not the same sound A3 starts with
        ops.append({"label":f"Prelap {scenes[0]['id']}","kind":"audio","track":BIRD_A,"bin":BED_BIN,"path":path,
                    "source_fps":fps,"start_f":a0,"end_f":b0,"source_start_s":round(tail,3),"db":"wind_db",
                    "fade_in_s":a.get("prelap_s"),"fade_out_s":a.get("prelap_s")})
    slots={str(s["prompt_id"]):s for s in plan["slots"] if s["prompt_id"] and s["start_f"]>=cut}
    unknown=set(birds or {})-set(slots)
    if unknown: raise Stop(f"Birds for unknown / hook shots: {sorted(unknown)}")
    early=[i for i in birds or {} if p and scenes and slots[i]["start_f"]<cut+p]
    if early: raise Stop(f"Birds on {early} overlap the A5 pre-lap into story 1; pick later calm shots")
    for i,src in sorted((birds or {}).items(),key=lambda kv:slots[kv[0]]["start_f"]):
        sh=slots[i]
        ops.append({"label":f"Birds {i}","kind":"audio","track":BIRD_A,"bin":BED_BIN,
                    "path":bed_file(video,src,(sh["end_f"]-sh["start_f"])/fps,fps),"source_fps":fps,
                    "start_f":sh["start_f"],"end_f":sh["end_f"],"source_start_s":0,"db":"bird_db",
                    "fade_in_s":1,"fade_out_s":1})
    return ops


def music(video,path,wind=None,replace=False,resolve=None,beds=None,birds=None):
    """A7/A8 intro song cut opening -> climax -> ending under the hook; A3/A4 one wind bed per scene to the end
    (beds.json, else wind); A5 birds on the calm shots (birds.json). replace=True swaps only items an earlier
    `music` run placed (music_receipt.json), after a backup, keeping their gains."""
    if beds is None and (prod(video)/"beds.json").exists(): beds=prod(video)/"beds.json"
    if beds is not None and not isinstance(beds,dict): beds=read_json(beds)
    if birds is None and (prod(video)/"birds.json").exists(): birds=prod(video)/"birds.json"
    if birds is not None and not isinstance(birds,dict): birds=read_json(birds)
    with resolve_lock(),lock(prod(video)/"files.lock"):
        s=Session(video,resolve)
        try:
            ops=a3_beds(video,s.plan,path,wind,beds,birds)
            receipt=prod(video)/"music_receipt.json"
            mine={norm(p) for p in read_json(receipt)["paths"]} if receipt.exists() else set()
            t0=int(s.tl.GetStartFrame()) if s.tl else 0
            exact=lambda it,tr:any((tr,int(it.GetStart()),int(it.GetEnd()),norm(item_path(it)))==(op["track"],t0+op["start_f"],t0+op["end_f"],norm(op["path"]))
                                   and abs(int(it.GetLeftOffset())-frames(op["source_start_s"],op["source_fps"]))<=1 for op in ops)
            # music owns A3 / A4 / A5 and A7 / A8 under the hook; A7-A9 after the hook stay whoever placed them
            cut=t0+hook_window(s.plan)[1]
            old=[(tr,it) for tr in (BED_A,BED_A+1,BIRD_A,MUSIC_A,MUSIC_A+1) for it in s.bounds("audio",tr)
                 if not exact(it,tr) and (tr<MUSIC_A or int(it.GetStart())<cut)]
            if any(norm(item_path(it)) not in mine for _,it in old):
                raise Stop("A3-A5 / A7-A8 (hook) hold an item `music` did not place; kept untouched")
            if old and not replace: raise Stop("A3-A5 / A7-A8 already hold other music / beds; rerun with --replace to swap them (backup first, gains kept)")
            gains={(tr,int(it.GetStart())):it.GetProperty("AudioVolume") for tr,it in old}
            old=[it for _,it in old]
            todo=ops if old else [op for op in ops if s.classify(op)=="add"]
            s.prepare()
            backup=s.backup("music") if todo else None
            if old and not s.tl.DeleteClips(old,False): raise Stop(f"Could not remove the old A7 / A3 items; backup {backup}")
            todo=[op for op in ops if s.classify(op)=="add"]
            a=config().get("audio",{})
            for op in todo:
                item=s.append(op)
                db=gains.get((op["track"],s.t0+op["start_f"]),a.get(op["db"],-24))
                if not item.SetProperty("AudioVolume",float(db)): raise Stop(f"Could not set starting gain: {op['label']}")
                if not item.SetFades(a3_fades(op,s.plan["fps"])): raise Stop(f"Could not set fades: {op['label']}")
            for op in ops:
                if s.classify(op)!="already_present": raise Stop(f"Post-write verification failed: {op['label']}")
            if not s.pm.SaveProject(): raise Stop("Could not save project")
            write_json(receipt,{"paths":[op["path"] for op in ops],"backup":backup})
            return {"placed":[op["label"] for op in todo],"replaced":[it.GetName() for it in old],"backup":backup,
                    "beds":[op["path"] for op in ops],"wind":"recording" if wind else "synthesized",
                    "score":{k:v for k,v in ops[0]["score"].items() if k!="segments"},
                    "birds":[op["label"] for op in ops if op["track"]==BIRD_A],
                    "note":"Starting gain only; listen to voice/music/wind balance."}
        finally: s.restore()


def render_start(video,resolve=None):
    v=video_path(video)
    with resolve_lock(),lock(prod(video)/"files.lock"):
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
            used_music=sorted({x["path"] for x in report["audio"] if x["track"] not in (SHOT_A,VOICE_A)})
            lines=["# Music license records from the live Edit timeline", ""]
            for path in used_music:
                try: note=license_note(path)
                except Stop: note="MISSING license record; user must verify rights"
                lines.append(f"- {path} — {note}")
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
    with resolve_lock(),lock(prod(v)/"files.lock"):
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
