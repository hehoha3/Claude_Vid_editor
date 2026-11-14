"""Resolve test double with explicit endpoint and source-rate semantics."""
class Clip:
    def __init__(self,path,fps=None): self.path=path;self.fps=fps or (30 if "clip30" in self.path else 24)
    def GetUniqueId(self): return str(id(self))
    def GetClipProperty(self,key): return {"File Path":self.path,"FPS":str(self.fps)}.get(key,"")


class Item:
    def __init__(self,clip,start,end,offset):
        self.clip,self.start,self.end,self.offset=clip,start,end,offset;self.properties={}
    def GetStart(self): return self.start
    def GetEnd(self): return self.end
    def GetLeftOffset(self): return self.offset
    def GetMediaPoolItem(self): return self.clip
    def GetProperty(self,k=None): return self.properties if k is None else self.properties.get(k)
    def GetName(self): return self.clip.path
    def SetProperty(self,k,v): self.properties[k]=v;return True
    def SetFades(self,fades): self.fades=dict(fades);return True
    def GetFades(self): return dict(getattr(self,"fades",{}))
    def SetSpeed(self,o):  # assumed: no ripple, record start kept, length = source length / speed (verify live)
        self.speed=o["Percentage"]/100;self.end=self.start+round((self.end-self.start)/self.speed);return True


class Folder:
    def __init__(self,name): self.name=name;self.subs=[];self.clips=[]
    def GetName(self): return self.name
    def GetSubFolderList(self): return self.subs[:]
    def GetClipList(self): return self.clips[:]
    def GetUniqueId(self): return str(id(self))


class Timeline:
    def __init__(self,project,name):
        self.project=project;self.name=name;self.clip=Clip(name);self.items={};self.tracks={"video":1,"audio":0,"subtitle":0}
        self.names={};self.linked=[]
    def GetName(self): return self.name
    def GetMediaPoolItem(self): return self.clip
    def GetStartFrame(self): return 86400
    def GetTrackCount(self,kind): return self.tracks[kind]
    def GetTrackName(self,kind,i): return self.names.get((kind,i),f"{kind.title()} {i}")
    def SetTrackName(self,kind,i,name): self.names[kind,i]=name;return True
    def GetItemListInTrack(self,kind,i): return self.items.get((kind,i),[])[:]
    def AddTrack(self,kind,*args): self.tracks[kind]+=1;return True
    def GetSetting(self,key): return "24" if key=="timelineFrameRate" else ""
    def SetClipsLinked(self,items,linked): self.linked.append(items);return True
    def DeleteClips(self,items,ripple=False):
        for k in self.items: self.items[k]=[x for x in self.items[k] if x not in items]
        return True
    def DuplicateTimeline(self,name):
        if self.project.fail_backup: return None
        t=Timeline(self.project,name);self.project.timelines.append(t);self.project.mp.current.clips.append(t.clip);return t


class Pool:
    def __init__(self,p): self.project=p;self.root=Folder("Master");self.current=self.root
    def GetRootFolder(self): return self.root
    def GetCurrentFolder(self): return self.current
    def SetCurrentFolder(self,f): self.current=f;return True
    def AddSubFolder(self,p,name): f=Folder(name);p.subs.append(f);return f
    def MoveClips(self,clips,dst):
        stack=[self.root]
        while stack:
            f=stack.pop();stack+=f.subs;f.clips=[c for c in f.clips if c not in clips]
        dst.clips+=clips;return True
    def CreateEmptyTimeline(self,name):
        if any(t.name==name for t in self.project.timelines): return None  # real API refuses a duplicate name
        t=Timeline(self.project,name);self.project.timelines.append(t);self.current.clips.append(t.clip);self.project.current=t;return t
    def ImportMedia(self,paths):
        clips=[Clip(p,self.project.fps_by_path.get(p)) for p in paths];self.current.clips+=clips;return clips
    def AppendToTimeline(self,ops):
        t=self.project.current;out=[]
        for op in ops:
            if op["mediaPoolItem"].path.endswith(".srt"): return []
            kind="video" if op["mediaType"]==1 else "audio"
            assert t.GetTrackCount(kind)>=op["trackIndex"]
            n=op["endFrame"]-op["startFrame"]+(self.project.end_mode=="inclusive")
            source_fps=float(op["mediaPoolItem"].GetClipProperty("FPS"))
            duration=round(n*24/source_fps)
            i=Item(op["mediaPoolItem"],op["recordFrame"],op["recordFrame"]+duration,op["startFrame"])
            for old in t.GetItemListInTrack(kind,op["trackIndex"]):
                assert not (old.start<i.end and i.start<old.end),"Unexpected overwrite"
            t.items.setdefault((kind,op["trackIndex"]),[]).append(i);out.append(i)
        return out


class Project:
    def __init__(self,name,end_mode="exclusive"):
        self.name=name;self.end_mode=end_mode;self.timelines=[];self.current=None;self.mp=Pool(self);self.fail_backup=False;self.fps_by_path={}
        self.render_running=False;self.render_settings={};self.jobs={}
    def GetName(self): return self.name
    def GetMediaPool(self): return self.mp
    def GetCurrentTimeline(self): return self.current
    def SetCurrentTimeline(self,t): self.current=t;return True
    def GetTimelineCount(self): return len(self.timelines)
    def GetTimelineByIndex(self,i): return self.timelines[i-1]
    def SetSetting(self,*args): return True
    def GetSetting(self,*args): return "24"
    def IsRenderingInProgress(self): return self.render_running
    def LoadRenderPreset(self,name): return name=="YouTube 1080 HEVC"
    def SetRenderSettings(self,settings): self.render_settings=settings;return True
    def AddRenderJob(self):
        i=f"job{len(self.jobs)+1}";self.jobs[i]={"JobStatus":"Ready"};return i
    def StartRendering(self,job): self.render_running=True;self.jobs[job]={"JobStatus":"Rendering"};return True
    def GetRenderJobStatus(self,job): return self.jobs[job]


class PM:
    def __init__(self,p): self.project=p
    def GetCurrentProject(self): return self.project
    def SaveProject(self): return True


class Resolve:
    def __init__(self,name,end_mode="exclusive"): self.project=Project(name,end_mode);self.pm=PM(self.project)
    def GetProjectManager(self): return self.pm
