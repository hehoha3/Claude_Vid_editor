"""Work key of a video (user 2026-11-02): one day's videos may share a folder name across channels
(D:\\Chann_1_*\\africa_021126_1 and D:\\Chann_2_*\\africa_021126_1). Such a name gets the key <video>__Chann_N, so
.work/doc_edit/<key> and the vo-sync job .work/<key>_mp3 never mix the two films; a name in one channel only keeps
the plain key (every video before keeps its work folder)."""
from __future__ import annotations

import os
import re
from glob import glob
from pathlib import Path

_CHANN = re.compile(r"(?i)\bchann_(\d+)")
SEP = "__"


def channel_of(path) -> str | None:
    r"""D:\Chann_2_UntamedEmpire\africa_1 -> 'Chann_2'."""
    m = _CHANN.search(str(path or ""))
    return f"Chann_{m[1]}" if m else None


def day_project(name: str) -> str:
    """<region>_DDMMYY_N (or its work key <video>__Chann_N) -> the day project vid_DDMMYY that holds every film of
    every channel of that day (user 2026-11-06; before: vid_DDMMYY_N); any other name, vid_* included, stays itself."""
    m = re.fullmatch(r"(?!vid_)[a-z]+_(\d{6})(?:_\d+)?", str(name).split(SEP)[0], re.I)
    return f"vid_{m[1]}" if m else str(name).split(SEP)[0]


def timeline_name(video) -> str | None:
    r"""The video's one timeline (user 2026-11-06, replaces "Edit"): D:\Chann_2_x\africa_061126_3[\audios] or the key
    africa_061126_3__Chann_2 -> 'chann2_vid3' (video number = the folder's _N, none -> 1). No channel -> None."""
    p = Path(str(video or ""))
    i = next((k for k, s in enumerate(p.parts) if _CHANN.match(s)), None)
    rest = [s for s in p.parts[i + 1:] if s.lower() != "_done"] if i is not None else []
    name, ch = split(rest[0] if rest else p.name)
    ch = ch or channel_of(video)
    if not ch:
        return None
    m = re.search(r"_\d{6}_(\d+)$", name)
    return f"chann{ch.split('_')[1]}_vid{m[1] if m else 1}"


def homes(name: str, globs=None) -> list[Path]:
    """Every folder <workspace>/<name> or <workspace>/_done/<name> (case-insensitive)."""
    if globs is None:
        from .config import load_config
        globs = load_config().get("workspaces", {}).get("globs", [r"D:\Chann_*"])
    out = []
    for ws in sorted({Path(p) for g in globs for p in glob(g) if Path(p).is_dir()}):
        for base in (ws, ws / "_done"):
            if base.is_dir():
                out += [d for d in base.iterdir() if d.is_dir() and d.name.lower() == name.lower()]
    return out


def split(video) -> tuple[str, str | None]:
    """'africa_1__Chann_2' -> ('africa_1', 'Chann_2'); a video folder path -> (its name, its channel)."""
    s = str(video)
    name = Path(s).name
    if SEP in name:
        n, ch = name.split(SEP, 1)
        return n, channel_of(ch)
    return name, channel_of(s) if os.path.isabs(s) else None


def video_key(video, globs=None) -> str:
    """Work key of <video>: a name, a <name>__Chann_N key, or the video folder (D:\\Chann_N_*\\<video>).
    A name in 2+ channels needs its channel: from the key, the folder, or DVR_CHANNEL; none -> stop, never a guess."""
    name, ch = split(video)
    chans = {channel_of(h) for h in homes(name, globs)}
    if len(chans) < 2:
        return name
    ch = ch or os.environ.get("DVR_CHANNEL")
    if not ch:
        raise SystemExit(f'video "{name}" exists in {", ".join(sorted(c or "?" for c in chans))}: '
                         f"pass {name}{SEP}Chann_N or run with DVR_CHANNEL=Chann_N")
    return f"{name}{SEP}{ch}"


def selftest():
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        for d in ("Chann_1_a/v1", "Chann_2_b/v1", "Chann_2_b/solo", "Chann_1_a/_done/old"):
            (t / d).mkdir(parents=True)
        g = [str(t / "Chann_*")]
        os.environ.pop("DVR_CHANNEL", None)
        assert video_key("solo", g) == "solo" and video_key("old", g) == "old"
        assert video_key(t / "Chann_2_b" / "v1", g) == "v1__Chann_2"
        assert video_key("v1__Chann_1", g) == "v1__Chann_1"
        try:
            video_key("v1", g)
            raise AssertionError("ambiguous name must stop")
        except SystemExit:
            pass
        os.environ["DVR_CHANNEL"] = "Chann_1"
        assert video_key("v1", g) == "v1__Chann_1"
        os.environ.pop("DVR_CHANNEL")
    assert day_project("africa_061126_3__Chann_2") == "vid_061126" and day_project("vid_051126_1") == "vid_051126_1"
    assert timeline_name(r"D:\Chann_2_x\africa_061126_3\audios") == "chann2_vid3"
    assert timeline_name("africa_061126_7__Chann_1") == "chann1_vid7" and timeline_name("africa_061126_2") is None
    assert timeline_name(r"D:\Chann_3_y\_done\himalaya_061126_4") == "chann3_vid4"
    assert timeline_name(r"D:\Chann_1_a\amazon_311026") == "chann1_vid1"
    print("videokey selftest ok")


if __name__ == "__main__":  # python dvr_cowork/videokey.py --selftest
    selftest()
