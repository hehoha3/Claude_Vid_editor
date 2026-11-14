"""Full-AI upload: verified .production/render.json -> the channel, private, once; ambiguity blocks retries.
Login / channels / tokens live in dvr_cowork.youtube (shared with footage+AI)."""
from __future__ import annotations

from datetime import datetime,timezone
from pathlib import Path
import re
from .core import Stop,digest,event,lock,object_hash,prod,read_json,video_path,write_json
from ..youtube import CHANNELS,channel_of,client


def owned_channels(yt):
    return [x["id"] for x in yt.channels().list(part="id",mine=True).execute().get("items",[])]


def upload_body(meta,publish_at=None):
    if not meta.get("title") or not meta.get("description") or not isinstance(meta.get("tags"),list):
        raise Stop("Metadata requires approved title, description, tags")
    if len(meta["title"])>100: raise Stop("YouTube title exceeds 100 characters")
    status={"privacyStatus":"private","selfDeclaredMadeForKids":False,"containsSyntheticMedia":True}
    if publish_at:
        t=datetime.fromisoformat(publish_at.replace("Z","+00:00"))
        if t.tzinfo is None: raise Stop("Supply an explicit time-zone offset, e.g. 2026-11-03T18:00:00+07:00")
        if t<=datetime.now(timezone.utc): raise Stop("Publish time is in the past; would publish immediately")
        status["publishAt"]=t.astimezone(timezone.utc).isoformat().replace("+00:00","Z")
    return {"snippet":{"title":meta["title"],"description":meta["description"],"tags":meta["tags"],
                       "categoryId":"15","defaultLanguage":"en","defaultAudioLanguage":"en"},"status":status}


def upload(video,channel=None,publish_at=None,apply=False,yt=None):
    v=video_path(video)
    channel=channel or channel_of(v)
    if not channel: raise Stop(f"No channel: put the video under D:\\Chann_N_*\\ mapped in {CHANNELS.name}, or pass --channel")
    if not re.fullmatch(r"UC[A-Za-z0-9_-]{22}",channel): raise Stop("Use an exact YouTube channel ID")
    meta=read_json(prod(v)/"youtube_meta.json")
    body=upload_body(meta,publish_at)
    render=read_json(prod(v)/"render.json")
    if render.get("status")!="VERIFIED": raise Stop("Verify completed render before uploading")
    path=Path(render["path"])
    if digest(path)!=render["sha256"]: raise Stop("Render changed after verification")
    request_hash=object_hash({"channel":channel,"body":body,"file":render["sha256"]})
    preview={"channel":channel,"path":str(path),"body":body,"request_hash":request_hash}
    if not apply: return preview
    if meta.get("approved_request_hash")!=request_hash:
        raise Stop("Show exact upload preview to the user; after approval record approved_request_hash in youtube_meta.json")
    with lock(prod(v)/"files.lock"):
        receipt=prod(v)/"youtube.json"
        if receipt.exists():
            old=read_json(receipt)
            if old.get("status")=="COMPLETE" and old.get("request_hash")==request_hash: return old
            raise Stop("Earlier upload exists or its outcome is uncertain. Check YouTube Studio; never upload a duplicate automatically")
        yt=yt or client(channel)
        if owned_channels(yt)!=[channel]: raise Stop("OAuth token belongs to another channel; no upload performed")
        from googleapiclient.http import MediaFileUpload
        state={"status":"STARTING","request_hash":request_hash,"channel":channel,"file":str(path)}
        write_json(receipt,state)
        try:
            req=yt.videos().insert(part="snippet,status",body=body,
                                  media_body=MediaFileUpload(str(path),resumable=True,chunksize=8*1024*1024))
            response=None
            while response is None:
                progress,response=req.next_chunk(num_retries=2)
                if progress: print(f"upload: {progress.progress():.0%}",flush=True)
            state.update(status="COMPLETE",id=response["id"],url=f"https://www.youtube.com/watch?v={response['id']}")
            write_json(receipt,state);event(v,"UPLOADED",youtube_id=response["id"])
            return state
        except Exception:
            state["status"]="UNKNOWN";write_json(receipt,state)
            raise
