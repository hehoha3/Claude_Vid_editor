r"""YouTube Data API (user 2026-10-31): OAuth login, channel check, upload of a finished video.

    .venv/Scripts/python.exe -m dvr_cowork.youtube login      browser login, pick ONE channel -> its token
    .venv/Scripts/python.exe -m dvr_cowork.youtube channels   every saved channel: name + ID (refreshes tokens)
    .venv/Scripts/python.exe -m dvr_cowork.youtube upload <video folder> [--thumb <image>] [--publish-at "YYYY-MM-DD HH:MM"] [--dry]

One OAuth token = one channel (the account / brand account picked in the browser): run `login` once per channel.
Client: input/client_secret.json (Desktop app). Tokens: input/youtube_tokens/<channel id>.json (input/ is
gitignored). Never prints the client secret or any token.
upload (also run by /doc-edit done after the render): <video folder>/Done_<video>.mp4 -> the channel that
input/youtube_channels.json maps the workspace's Chann_N to; title / description / tags / synthetic (AI footage
disclosure) from .work/doc_edit/<video>/youtube_meta.json (else title = the video name), English, Pets & Animals,
not for kids, PRIVACY. Uploaded once: .work/doc_edit/<video>/youtube.json.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from .config import ROOT

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]
SECRET = ROOT / "input" / "client_secret.json"
TOKENS = ROOT / "input" / "youtube_tokens"
CHANNELS = ROOT / "input" / "youtube_channels.json"  # {"Chann_1": "<channel id>"}
# an unaudited API project gets its uploads locked private anyway; switch to "public" after the YouTube audit
PRIVACY = "private"
THUMB_MAX = 2 * 1024 * 1024  # thumbnails.set limit


def my_channels(creds):
    """channels.list(mine=true) -> [(title, id)]."""
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    return [(c["snippet"]["title"], c["id"]) for c in yt.channels().list(part="snippet", mine=True).execute().get("items", [])]


def saved(path):
    """A saved token, refreshed (and re-saved) when expired; None when it needs a new login."""
    creds = Credentials.from_authorized_user_file(str(path), SCOPES)
    if not creds.has_scopes(SCOPES):
        return None
    if not creds.valid:
        try:
            creds.refresh(Request())
        except RefreshError:  # revoked / expired refresh token
            return None
        path.write_text(creds.to_json(), "utf-8")
    return creds


def login():
    flow = InstalledAppFlow.from_client_secrets_file(str(SECRET), SCOPES)
    # select_account: the account / brand account chooser every time; consent: a refresh token on every login
    creds = flow.run_local_server(port=0, access_type="offline", prompt="select_account consent", open_browser=True)
    chans = my_channels(creds)
    if not chans:
        sys.exit("logged in, but the account picked has no YouTube channel: nothing saved")
    TOKENS.mkdir(exist_ok=True)
    for title, cid in chans:
        (TOKENS / f"{cid}.json").write_text(creds.to_json(), "utf-8")
        print(f"channel: {title} | id: {cid} | token saved")


def channels():
    paths = sorted(TOKENS.glob("*.json")) if TOKENS.exists() else []
    if not paths:
        sys.exit("no channel logged in yet: run `login`")
    for p in paths:
        creds = saved(p)
        if not creds:
            print(f"{p.stem}: token invalid -> run `login` again and pick this channel")
            continue
        for title, cid in my_channels(creds):
            print(f"channel: {title} | id: {cid}")


def channel_of(vdir):
    """Channel ID for a video folder D:\\Chann_N_*\\[_done\\]<video>, None when Chann_N is not mapped."""
    m = re.search(r"(?i)\bchann_(\d+)", str(vdir))
    ids = json.loads(CHANNELS.read_text("utf-8")) if CHANNELS.exists() else {}
    return ids.get(f"Chann_{m[1]}") if m else None


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
    """Done_<video>.mp4 of the video folder -> its channel, once; already uploaded + --thumb = only the thumbnail.
    publish_at "YYYY-MM-DD HH:MM" (this PC's time zone): private now, public then (YouTube's schedule).
    -> line (also for a skip)."""
    vdir = Path(vdir)
    video, work = vdir / f"Done_{vdir.name}.mp4", ROOT / ".work" / "doc_edit" / vdir.name
    mark, cid = work / "youtube.json", channel_of(vdir)
    if mark.exists():
        up = json.loads(mark.read_text("utf-8"))
        line = f"youtube: already uploaded https://youtu.be/{up['id']}"
        if not thumb or dry:
            return line + ", skipped"
        creds = saved(TOKENS / f"{up['channel']}.json")
        if not creds:
            return line + f"; token of {up['channel']} invalid -> `login` again, thumbnail not set"
        return line + set_thumb(build("youtube", "v3", credentials=creds, cache_discovery=False), up["id"], thumb, work)
    if not cid:
        return f"youtube: no channel for {vdir.parent.name} in {CHANNELS.name}, upload skipped"
    if not video.exists():
        return f"youtube: {video.name} not found, upload skipped"
    if not (TOKENS / f"{cid}.json").exists():
        return f"youtube: channel {cid} not logged in (`python -m dvr_cowork.youtube login`), upload skipped"
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
        return f"youtube: token of {cid} invalid -> `login` again, upload skipped"
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


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # emoji / Vietnamese titles on the Windows console
    a = sys.argv[1:]
    if a[:1] == ["upload"] and len(a) >= 2:
        print(upload(a[1], a[a.index("--thumb") + 1] if "--thumb" in a else None, "--dry" in a,
                     a[a.index("--publish-at") + 1] if "--publish-at" in a else None))
    elif a in (["login"], ["channels"]):
        {"login": login, "channels": channels}[a[0]]()
    else:
        sys.exit(__doc__)
