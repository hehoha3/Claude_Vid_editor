r"""YouTube Data API for both video types (user 2026-11-05: one module, one CLI).

    .venv/Scripts/python.exe -m dvr_cowork youtube login --key Chann_N   browser login -> token, channels.json, D:\Chann_N_<Name>
    .venv/Scripts/python.exe -m dvr_cowork youtube remove Chann_N        forget Chann_N (key + token) on this PC
    .venv/Scripts/python.exe -m dvr_cowork youtube channels              every saved channel: name, id, Chann_N, problems
    .venv/Scripts/python.exe -m dvr_cowork youtube upload <video> [--thumb F] [--publish-at T] [--channel UC..] [--apply]
    .venv/Scripts/python.exe -m dvr_cowork youtube seo <video> [--force | --pick N | --write | --query Q]
    .venv/Scripts/python.exe -m dvr_cowork youtube trends Chann_N [--query Q] | reference Chann_N <url>   (full-AI)

One OAuth token = one channel (the account / brand account picked in the browser). Chann_N in use -> `remove` first.
Client: .secrets/youtube/client_secret.json (Desktop app). Tokens: .secrets/youtube/tokens/<channel id>.json,
channels.json maps Chann_N -> channel id; a video in D:\Chann_N_*\<video> goes to that channel. Never prints a secret.
upload / seo pick the engine by the video's pinned profile: footage+AI = this module's upload (Done_<video>.mp4,
.work/doc_edit/<video>/youtube_meta.json, also run by /doc-edit done) and dvr_cowork.seo; full-AI = fullai.youtube /
fullai.seo (.production/render.json + approved request hash). Without --apply upload only previews.
"""
import argparse
import json
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from .config import ROOT
from .fullai.core import Stop, read_json, write_json
from .profile import full_ai

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]
LOGIN_SCOPES = SCOPES + ["https://www.googleapis.com/auth/youtube"]  # "youtube": edit publishAt after upload
SECRETS = ROOT / ".secrets" / "youtube"  # not input/ (user 2026-10-31: input/ = files the user sends to read)
TOKENS = SECRETS / "tokens"
CHANNELS = SECRETS / "channels.json"  # {"Chann_1": "<channel id>"}
CHANNEL_ROOT = Path("D:/")
LOGIN_TIMEOUT = 300  # s to finish the browser login
# an unaudited API project gets its uploads locked private anyway; switch to "public" after the YouTube audit
PRIVACY = "private"
THUMB_MAX = 2 * 1024 * 1024  # thumbnails.set limit


def mapping():
    return read_json(CHANNELS) if CHANNELS.is_file() else {}


def relogin(cid="Chann_N"):
    key = next((k for k, v in mapping().items() if v == cid), "Chann_N")
    return f"youtube remove {key}, then youtube login --key {key} and pick that channel"


def saved(path):
    """A saved token, refreshed (and re-saved) when expired; None when it needs a new login."""
    creds = Credentials.from_authorized_user_file(str(path))  # the scopes saved in the file (a refresh asks for those)
    if not creds.has_scopes(SCOPES):
        return None
    if not creds.valid:
        try:
            creds.refresh(Request())
        except RefreshError:  # revoked / expired refresh token
            return None
        path.write_text(creds.to_json(), "utf-8")
    return creds


def client(cid):
    """API client of a logged-in channel id; Stop with the fix when the token is missing or broken."""
    path = TOKENS / f"{cid}.json"
    if not path.is_file():
        raise Stop(f"{cid} is not logged in: youtube login --key Chann_N")
    creds = saved(path)
    if not creds:
        raise Stop(f"Token of {cid} is revoked, expired or lacks upload scope: {relogin(cid)}")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def channel_of(vdir):
    """Channel ID for a video folder D:\\Chann_N_*\\[_done\\]<video>, None when Chann_N is not mapped."""
    m = re.search(r"(?i)\bchann_(\d+)", str(vdir))
    return mapping().get(f"Chann_{m[1]}") if m else None


def camel(title):
    """'Wild Peril' -> 'WildPeril': letters and digits only, so always a valid folder name."""
    return "".join(w[:1].upper() + w[1:] for w in re.split(r"[\W_]+", title))


def oauth(secret):
    """Browser login. run_local_server blocks Ctrl+C on Windows: wait in a daemon thread, poll from the main one."""
    from google_auth_oauthlib.flow import InstalledAppFlow, WSGITimeoutError
    flow = InstalledAppFlow.from_client_secrets_file(str(secret), LOGIN_SCOPES)
    out = {}

    def wait():
        try:  # select_account: the account / brand account chooser every time; consent: a refresh token every login
            out["creds"] = flow.run_local_server(port=0, prompt="select_account consent", access_type="offline",
                                                 timeout_seconds=LOGIN_TIMEOUT)
        except Exception as e:
            out["err"] = e

    t = threading.Thread(target=wait, daemon=True)
    t.start()
    try:
        while t.is_alive():
            t.join(0.5)
    except KeyboardInterrupt:
        raise Stop("Login stopped (Ctrl+C); nothing saved")
    if "err" in out and not isinstance(out["err"], WSGITimeoutError):
        raise out["err"]
    if not out.get("creds"):
        raise Stop(f"No login within {LOGIN_TIMEOUT // 60} min; nothing saved")
    return out["creds"]


def channel_folder(key, title, base=CHANNEL_ROOT):
    """Create D:\\Chann_N_<CamelTitle>, or rename the one existing D:\\Chann_N_* to it."""
    new = base / f"{key}_{camel(title)}"
    if new.name == f"{key}_":
        raise Stop(f"Channel name {title!r} has no letters or digits for a folder name")
    old = [p for p in base.glob(f"{key}_*") if p.is_dir()]
    if len(old) > 1:
        raise Stop(f"More than one {key}_* folder: {[str(p) for p in old]}; keep one, nothing saved")
    if not old:
        new.mkdir()
        return {"folder": str(new), "action": "created"}
    if old[0].name == new.name:
        return {"folder": str(new), "action": "kept"}
    try:
        old[0].rename(new)
    except OSError as e:
        raise Stop(f"Cannot rename {old[0]} -> {new} ({e}): close Resolve / Explorer windows using it; nothing saved")
    return {"folder": str(new), "action": f"renamed from {old[0]}",
            "resolve": f"media under the old path goes offline: dvr_cowork offline --relink {old[0]} {new}"}


def login(key):
    """Browser login for ONE channel -> its token, Chann_N in channels.json, folder D:\\Chann_N_<CamelTitle>."""
    if not re.fullmatch(r"Chann_\d+", key):
        raise Stop("Key must look like Chann_3")
    ids = mapping()
    if key in ids:
        raise Stop(f"{key} is in use ({ids[key]}): youtube remove {key} first")
    secret = SECRETS / "client_secret.json"
    if not secret.is_file():
        raise Stop("Place the Desktop OAuth client JSON at .secrets/youtube/client_secret.json")
    creds = oauth(secret)
    items = build("youtube", "v3", credentials=creds, cache_discovery=False).channels().list(
        part="snippet", mine=True).execute().get("items", [])
    if len(items) != 1:
        raise Stop("Select exactly one channel/Brand Account; nothing saved")
    cid, title = items[0]["id"], items[0]["snippet"]["title"]
    if cid in ids.values():
        raise Stop(f"{title} is already {next(k for k, v in ids.items() if v == cid)}; nothing saved")
    folder = channel_folder(key, title)  # first: a locked folder stops before anything is saved
    TOKENS.mkdir(parents=True, exist_ok=True)
    write_json(TOKENS / f"{cid}.json", json.loads(creds.to_json()))
    write_json(CHANNELS, ids | {key: cid})
    return {"key": key, "channel": title, "channel_id": cid} | folder


def remove(key):
    """Forget a channel locally: its channels.json key and token. Google access stays until revoked in the account."""
    ids = mapping()
    if key not in ids:
        raise Stop(f"{key} is not in {CHANNELS.name}: {sorted(ids)}")
    cid = ids.pop(key)
    write_json(CHANNELS, ids)
    if cid not in ids.values():
        (TOKENS / f"{cid}.json").unlink(missing_ok=True)
    return {"removed": key, "channel_id": cid, "folder": "kept",
            "also": "revoke the app at https://myaccount.google.com/permissions if no longer used"}


def channels():
    """Every saved token: live channel name, channels.json key, or the exact problem."""
    keys = {v: k for k, v in mapping().items()}
    out = []
    for p in sorted(TOKENS.glob("*.json")) if TOKENS.exists() else []:
        try:
            items = client(p.stem).channels().list(part="snippet", mine=True).execute().get("items", [])
            row = {"id": p.stem, "name": ", ".join(x["snippet"]["title"] for x in items),
                   "token_matches": [x["id"] for x in items] == [p.stem]}
        except Stop as e:
            row = {"id": p.stem, "problem": str(e)}
        out.append(row | {"key": keys.get(p.stem, "not in channels.json")})
    if not out:
        raise Stop("No channel logged in yet: youtube login --key Chann_1")
    return out


def thumb_file(thumb, work):
    """The thumbnail as given, or a 1920x1080 JPEG copy in work/ when it is over the 2 MB API limit."""
    if Path(thumb).stat().st_size <= THUMB_MAX:
        return Path(thumb)
    from PIL import Image
    out = work / "youtube_thumb.jpg"
    Image.open(thumb).convert("RGB").resize((1920, 1080), Image.LANCZOS).save(out, "JPEG", quality=90)
    return out


def set_thumb(yt, vid, thumb, work):
    try:
        yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumb_file(thumb, work)))).execute()
        return ", thumbnail set"
    except Exception as e:  # unverified channel / bad image: the video stays uploaded
        return f", thumbnail NOT set ({e})"


def upload(vdir, thumb=None, dry=False, publish_at=None):
    """Footage+AI: Done_<video>.mp4 of the video folder -> its channel, once; already uploaded + --thumb = only the
    thumbnail. publish_at "YYYY-MM-DD HH:MM" (this PC's time zone): private now, public then. -> line (also a skip)."""
    vdir = Path(vdir)
    from .videokey import video_key
    video, work = vdir / f"Done_{vdir.name}.mp4", ROOT / ".work" / "doc_edit" / video_key(vdir)
    mark, cid = work / "youtube.json", channel_of(vdir)
    if mark.exists():
        up = json.loads(mark.read_text("utf-8"))
        line = f"youtube: already uploaded https://youtu.be/{up['id']}"
        if not thumb or dry:
            return line + ", skipped"
        creds = saved(TOKENS / f"{up['channel']}.json")
        if not creds:
            return line + f"; token of {up['channel']} invalid -> {relogin(up['channel'])}, thumbnail not set"
        return line + set_thumb(build("youtube", "v3", credentials=creds, cache_discovery=False), up["id"], thumb, work)
    if not cid:
        return f"youtube: no channel for {vdir.parent.name} in {CHANNELS.name}, upload skipped"
    if not video.exists():
        return f"youtube: {video.name} not found, upload skipped"
    if not (TOKENS / f"{cid}.json").exists():
        return f"youtube: channel {cid} not logged in ({relogin(cid)}), upload skipped"
    meta = json.loads((work / "youtube_meta.json").read_text("utf-8")) if (work / "youtube_meta.json").exists() else {}
    body = {"snippet": {"title": meta.get("title", vdir.name), "description": meta.get("description", ""),
                        "tags": meta.get("tags", []), "categoryId": "15", "defaultLanguage": "en",
                        "defaultAudioLanguage": "en"},
            # synthetic: realistic AI footage must be disclosed (YouTube "altered or synthetic content")
            "status": {"privacyStatus": PRIVACY, "selfDeclaredMadeForKids": False,
                       "containsSyntheticMedia": meta.get("synthetic", False)}}
    when = ""
    if publish_at:
        t = datetime.fromisoformat(publish_at).astimezone(timezone.utc)
        if t <= datetime.now(timezone.utc):
            return f"youtube: publish time {publish_at} already passed, upload skipped (give a new time)"
        body["status"] |= {"privacyStatus": "private", "publishAt": t.strftime("%Y-%m-%dT%H:%M:%SZ")}
        when = f", scheduled public {publish_at}"
    if dry:
        return f"youtube (dry): {video} -> {cid}, {body}, thumb {thumb or 'none'}"
    creds = saved(TOKENS / f"{cid}.json")
    if not creds:
        return f"youtube: token of {cid} invalid -> {relogin(cid)}, upload skipped"
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(video), chunksize=64 * 1024 * 1024, resumable=True))
    res, shown = None, -10
    while res is None:
        st, res = req.next_chunk(num_retries=5)
        if st and st.progress() * 100 >= shown + 10:
            shown = int(st.progress() * 100)
            print(f"youtube: uploading {shown}%", flush=True)
    work.mkdir(parents=True, exist_ok=True)
    mark.write_text(json.dumps({"id": res["id"], "channel": cid, "file": str(video)}), "utf-8")
    line = f"youtube: https://youtu.be/{res['id']} ({body['status']['privacyStatus']}{when}, channel {cid})"
    return line + (set_thumb(yt, res["id"], thumb, work) if thumb else "")


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")  # emoji / Vietnamese titles on the Windows console
    ap = argparse.ArgumentParser(prog="dvr_cowork youtube")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login").add_argument("--key", required=True)
    sub.add_parser("remove").add_argument("key")
    sub.add_parser("channels")
    q = sub.add_parser("upload")
    q.add_argument("video"); q.add_argument("--thumb"); q.add_argument("--publish-at"); q.add_argument("--channel")
    q.add_argument("--apply", action="store_true", help="upload for real; without it only a preview")
    q = sub.add_parser("seo")
    q.add_argument("video"); q.add_argument("--force", action="store_true"); q.add_argument("--pick", type=int)
    q.add_argument("--write", action="store_true"); q.add_argument("--query", action="append")
    q = sub.add_parser("trends"); q.add_argument("channel"); q.add_argument("--query", action="append")
    q = sub.add_parser("reference"); q.add_argument("channel"); q.add_argument("url")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "login": out = login(a.key)
        elif a.cmd == "remove": out = remove(a.key)
        elif a.cmd == "channels": out = channels()
        elif a.cmd == "upload" and full_ai(a.video):
            from .fullai.youtube import upload as upload_ai
            out = upload_ai(a.video, a.channel, a.publish_at, a.apply)
        elif a.cmd == "upload": out = upload(a.video, a.thumb, not a.apply, a.publish_at)
        elif a.cmd == "seo" and full_ai(a.video):
            from .fullai import seo as seo_ai
            out = seo_ai.assemble(a.video) if a.write else seo_ai.research(a.video, a.query)
        elif a.cmd == "seo":
            from . import seo as seo_1h
            out = seo_1h.pick(a.video, a.pick) if a.pick else seo_1h.run(a.video, a.force)
        else:
            from .fullai import seo as seo_ai
            out = seo_ai.trends(a.channel, a.query) if a.cmd == "trends" else seo_ai.reference(a.channel, a.url)
        print(out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, indent=2, default=str))
        return 0
    except (Stop, OSError, ValueError, KeyError) as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
