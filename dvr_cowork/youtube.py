"""Optional YouTube delivery. OAuth secrets stay local; upload ambiguity blocks retries."""
from __future__ import annotations

from datetime import datetime,timezone
import json
from pathlib import Path
import re
from .core import ROOT,Stop,digest,event,lock,object_hash,prod,read_json,video_path,write_json

SCOPES=["https://www.googleapis.com/auth/youtube.upload","https://www.googleapis.com/auth/youtube.readonly"]
SECRETS=ROOT/".secrets/youtube"
TOKENS=SECRETS/"tokens"
CHANNELS=SECRETS/"channels.json"  # {"Chann_1": "UC..."}; video folders live under D:\Chann_N_*\<video>
LOGIN_TIMEOUT=300


def client(channel):
    from google.oauth2.credentials import Credentials
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    path=TOKENS/f"{channel}.json"
    if not path.is_file(): raise Stop(f"Log into the intended channel first (youtube-login): {channel}")
    creds=Credentials.from_authorized_user_file(str(path),SCOPES)
    if not creds.has_scopes(SCOPES): raise Stop(f"Token of {channel} lacks upload/readonly scope; run youtube-login again")
    if not creds.valid:
        try: creds.refresh(Request())
        except RefreshError: raise Stop(f"Token of {channel} was revoked or expired; run youtube-login and pick that channel")
        write_json(path,json.loads(creds.to_json()))
    return build("youtube","v3",credentials=creds,cache_discovery=False)


def owned_channels(yt):
    return [x["id"] for x in yt.channels().list(part="id",mine=True).execute().get("items",[])]


def channel_of(video):
    """Channel ID for D:\\Chann_N_*\\...\\<video> from channels.json; None when the folder or mapping is missing."""
    m=re.search(r"(?i)\bchann_(\d+)",str(video))
    return mapping().get(f"Chann_{m[1]}") if m else None


def mapping(): return read_json(CHANNELS) if CHANNELS.is_file() else {}


def login(key=None):
    """Browser login for ONE channel -> its token; key 'Chann_N' also maps it in channels.json."""
    if key and not re.fullmatch(r"Chann_\d+",key): raise Stop("Key must look like Chann_3")
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    secret=SECRETS/"client_secret.json"
    if not secret.is_file(): raise Stop("Place the Desktop OAuth client JSON at .secrets/youtube/client_secret.json")
    flow=InstalledAppFlow.from_client_secrets_file(str(secret),SCOPES)
    creds=flow.run_local_server(port=0,prompt="select_account consent",access_type="offline",timeout_seconds=LOGIN_TIMEOUT)
    if creds is None: raise Stop(f"No login within {LOGIN_TIMEOUT//60} min; nothing saved")
    yt=build("youtube","v3",credentials=creds,cache_discovery=False)
    items=yt.channels().list(part="snippet",mine=True).execute().get("items",[])
    if len(items)!=1: raise Stop("Select exactly one channel/Brand Account; no token saved for an ambiguous selection")
    cid,ids=items[0]["id"],mapping()
    if key and ids.get(key) not in (None,cid): raise Stop(f"{key} already maps to {ids[key]}: youtube-remove {key} first; nothing saved")
    TOKENS.mkdir(parents=True,exist_ok=True)
    write_json(TOKENS/f"{cid}.json",json.loads(creds.to_json()))
    if key: write_json(CHANNELS,ids|{key:cid})
    keys=[k for k,v in mapping().items() if v==cid]
    return {"channel":items[0]["snippet"]["title"],"channel_id":cid,"token_saved":True,
            "key":keys[0] if keys else f"not mapped: run youtube-login --key Chann_N again",
            "videos_go_in":f"D:\\{keys[0]}_<name>\\<video>" if keys else None}


def remove(key):
    """Forget a channel locally: its channels.json key and token. Google access stays until revoked in the account."""
    ids=mapping()
    if key not in ids: raise Stop(f"{key} is not in {CHANNELS.name}: {sorted(ids)}")
    cid=ids.pop(key)
    write_json(CHANNELS,ids)
    if cid not in ids.values(): (TOKENS/f"{cid}.json").unlink(missing_ok=True)
    return {"removed":key,"channel_id":cid,"also":"revoke the app at https://myaccount.google.com/permissions if no longer used"}


def channels():
    """Every saved token: live channel name, channels.json key, or the exact problem."""
    keys={v:k for k,v in mapping().items()}
    out=[]
    for p in sorted(TOKENS.glob("*.json")):
        try:
            items=client(p.stem).channels().list(part="snippet",mine=True).execute().get("items",[])
            row={"id":p.stem,"name":", ".join(x["snippet"]["title"] for x in items),"token_matches":[x["id"] for x in items]==[p.stem]}
        except Stop as e: row={"id":p.stem,"problem":str(e)}
        out.append(row|{"key":keys.get(p.stem,"not in channels.json")})
    if not out: raise Stop("No channel logged in yet: run youtube-login")
    return out


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
