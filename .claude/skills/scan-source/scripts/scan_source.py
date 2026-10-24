#!/usr/bin/env python3
"""Keep the source indexes in sync with what the user sorted on disk. No vision, no file moves.

    scan_source.py            scan all roots
    scan_source.py video|ai|audio|africa_video|africa_ai|africa_ai_check|savannah|sfx|sound

video  Z:\\Unseen\\Amazona\\video  real stock footage  <subject>/ = still, <subject>/action/ = action,
                                                      birds/ insects/ flat, landscape/<setting>/
ai     config.toml paths.ai_video  AI-generated clips  same folder rules as video (default D:\\AI_video)
africa_video  Z:\\Unseen\\Động vật\\AAA Trên cạn      real footage, <species folder (Vietnamese/English)>/...
africa_ai     ...\\AAA Trên cạn\\AI_copyright        AI clips, AI/<action>/<species>/, bản quyền/<channel>/
africa_ai_check  <ai_video>\\_africa                 Africa AI clips (user 2026-10-22): _check/ = new generated clips,
                                                      <species>/ = filed by organize.py --africa; excluded from `ai`
savannah      Z:\\Unseen\\savannah                    real landscape footage (subject = landscape)
audio  Z:\\Unseen\\Amazona\\audio  music / ambience    <category>/
sfx / sound  Z:\\Unseen\\SFX, Sound   (user 2026-10-20: the audio roots of every region; more will be added)
Video roots belong to one region (REGION: amazon | africa, user 2026-10-20: /doc-edit <audios> <region> uses only
that region's footage); audio roots are shared by every region.
Drive Z: is READ + COPY only (user rule 2026-10-11). Every index lives in the workspace, .work/library/<name>_library.json
(committed to git, so the team shares the tags; paths inside are relative to the root).
Clips are keyed by a content hash, so moved/renamed files keep their entry (and any earlier tags)."""
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from dvr_cowork.config import load_config  # noqa: E402
AFRICA = Path(r"Z:\Unseen\Động vật\AAA Trên cạn")
AI_VIDEO = Path(load_config()["paths"]["ai_video"])  # config.toml, per machine
# name -> (root, media kind, source label stored on every clip)
ROOTS = {"video": (Path(r"Z:\Unseen\Amazona\video"), "video", "real"),
         "ai": (AI_VIDEO, "video", "ai"),                                 # _africa inside it = africa_ai_check
         "africa_video": (AFRICA, "video", "real"),                       # AI_copyright inside it = africa_ai
         "africa_ai": (AFRICA / "AI_copyright", "video", "ai"),
         "africa_ai_check": (AI_VIDEO / "_africa", "video", "ai"),          # Africa AI: _check + species folders
         "savannah": (Path(r"Z:\Unseen\savannah"), "video", "real"),
         "audio": (Path(r"Z:\Unseen\Amazona\audio"), "audio", None),
         "sfx": (Path(r"Z:\Unseen\SFX"), "audio", None),                 # animal foley + species calls (English names)
         "sound": (Path(r"Z:\Unseen\Sound"), "audio", None)}             # licensed music, <mood>/ folders
# "animal" (Z:\Unseen\Sound Animal V1) dropped 2026-10-20: gone from Z:; its old index file is unused.
# video root -> region (user 2026-10-20); everything used so far (Amazon, Congo...) = amazon. Audio roots: no region.
REGION = {"video": "amazon", "ai": "amazon", "africa_video": "africa", "africa_ai": "africa",
          "africa_ai_check": "africa", "savannah": "africa"}
REGIONS = ("amazon", "africa")
# user rule 2026-10-11: drive Z: is READ + COPY only - nothing is ever written, moved or deleted on it (save() refuses)
WORK = Path(__file__).resolve().parents[4] / ".work" / "library"
EXTS = {"video": {".mp4", ".mov", ".mxf", ".mkv", ".m4v"}, "audio": {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}}
INDEX = "_library.json"
INDEX_NAME = {AFRICA: "africa_video", AFRICA / "AI_copyright": "africa_ai",  # ASCII index names for accented roots
              AI_VIDEO / "_africa": "africa_ai_check"}
SHOW = 15
FLAT = {"birds", "insects", "flowers"}
SKIP_DIRS = {"_nologo", "_z_nologo", "__MACOSX"}  # logo-free copies (hide-logo); macOS zip leftovers ("._x.mov")
# Africa folders (Vietnamese / English, user-named) -> species name the tags use. A folder already named like a
# value ("lion") maps to itself; ambiguous ones (linh dương, báo, lợn rừng) and action folders map to nothing:
# the tagger names what it sees.
AFRICA_FOLDERS = {
    "hươu cao cổ": "giraffe", "linh dương impala": "impala", "sử tử": "lion", "sư tử": "lion",
    "báo săn - cheetah": "cheetah", "bọ lăn phân dung beetle": "dung beetle", "chim marabou stork": "marabou stork",
    "chim oxpecker": "oxpecker", "chim weaver": "weaver", "chó hoang": "wild dog", "cá sấu": "crocodile",
    "guinea fowl": "guineafowl", "hà mã": "hippo", "khỉ đầu chó": "baboon", "kền kền": "vulture", "linh cẩu": "hyena",
    "linh dương blesbok": "blesbok", "linh dương dik-dik": "dik-dik", "linh dương hartebeest": "hartebeest",
    "linh dương kudu": "kudu", "linh dương nyala": "nyala", "lửng mật": "honey badger", "ngựa vằn": "zebra",
    "rắn puff adder": "puff adder", "serectary bird": "secretary bird", "tê giác": "rhino", "voi": "elephant",
    "wildebeest linh dương đầu bò": "wildebeest", "đà điểu": "ostrich", "đại bàng": "eagle",
    "đại bàng bateleur": "bateleur eagle",
    # AI_copyright/AI/<action>/<species>
    "cheetah dry earth": "cheetah", "cheetah dry straw": "cheetah", "gemsbok chạy": "gemsbok", "kudu chay": "kudu",
    "linh cẩu chạy": "hyena", "linh duong impala chay": "impala", "lion dry earth": "lion", "lion dry straw": "lion",
    "su tu cai chay": "lion", "sư tử đực chạy": "lion", "zebra chay": "zebra", "đà điểu chạy": "ostrich"}
for _v in set(AFRICA_FOLDERS.values()) | {"leopard", "banded mongoose", "cape buffalo", "caracal", "eland", "jackal",
                                          "serval", "springbok", "thomson's gazelle", "topi", "warthog", "wild dog",
                                          # species folders of the Africa AI root (organize.py --africa, 2026-10-22)
                                          "red lechwe", "buffalo", "gazelle", "oryx", "antelope", "mongoose", "meerkat",
                                          "snake", "bird", "landscape"}:
    AFRICA_FOLDERS.setdefault(_v, _v)
AFRICA_ACTION = {"chạy", "rình", "đi bộ tới mồi", "hunting"}  # folders of clips where the animal does something


def video_roots(region):
    """{name: (root, kind, source)} of the video roots of one region."""
    assert region in REGIONS, f"region {region!r} not in {REGIONS}"
    return {n: ROOTS[n] for n, r in REGION.items() if r == region}


def index_of(root):
    """Index file of a root: always in the workspace, .work/library/<name>_library.json."""
    return WORK / (INDEX_NAME.get(root, root.name.replace(" ", "_")) + INDEX)


def fold(name):
    """Folder name -> lookup key: NFC (macOS copies may be NFD), lowercase, '_' = space."""
    return unicodedata.normalize("NFC", name).lower().replace("_", " ").strip()


def audio_blocked(path):
    """True if an audio path matches a line of .work/library/audio_blocked.txt (claimed tracks: never picked)."""
    f = WORK / "audio_blocked.txt"
    frags = [l.strip().lower() for l in f.read_text("utf-8").splitlines() if l.strip() and not l.startswith("#")] if f.exists() else []
    return any(x in str(path).lower().replace("\\", "/") for x in frags)


def fast_hash(p):
    """size + first/last MiB: stable across rename/move, ~1 ms per file even on a NAS."""
    size = p.stat().st_size
    h = hashlib.sha1(str(size).encode())
    with open(p, "rb") as f:
        h.update(f.read(1 << 20))
        f.seek(max(0, size - (1 << 20)))
        h.update(f.read(1 << 20))
    return h.hexdigest()[:16]


def probe(p):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                   "stream=codec_type,width,height,r_frame_rate,sample_rate,channels"
                                   ":format=duration", "-of", "json", str(p)],
                                  capture_output=True, text=True).stdout or "{}")
    st = j.get("streams", [])
    dur = round(float(j.get("format", {}).get("duration") or 0), 2)
    v = next((s for s in st if s.get("codec_type") == "video"), None)
    a = next((s for s in st if s.get("codec_type") == "audio"), None)
    if v and v.get("width"):
        n, d = map(int, v.get("r_frame_rate", "0/1").split("/"))
        return {"width": v["width"], "height": v.get("height"), "fps": round(n / d, 3) if d else None,
                "duration": dur, "has_audio": a is not None}
    return {"duration": dur, "sample_rate": int(a["sample_rate"]) if a else None,
            "channels": a.get("channels") if a else None}


def title_hint(name):
    """Stock file names: Envato <slug>-YYYY-MM-DD-HH-MM-SS-utc, Storyblocks <slug>-SBA-<id> / -SBV-<id>-HD."""
    s = re.sub(r"-\d{4}(-\d{2}){5}-utc$", "", Path(name).stem)
    s = re.sub(r"-SB[AV]-\d+(-(HD|4K|UHD))?$", "", s, flags=re.I)
    if re.fullmatch(r"shot_\d+", s, re.I):   # AI shot numbers say nothing about content
        return None
    return s.replace("-", " ").replace("_", " ").strip()


def folder_info(kind, rel, name=None):
    parts = rel.parts[:-1]
    top = parts[0] if parts else None
    if kind == "audio":
        return {"category": top}
    if name == "savannah":   # scenery only, flat
        return {"subject": "landscape", "action": None, "setting_folder": None}
    if name in ("africa_video", "africa_ai", "africa_ai_check"):   # deepest folder that names a species wins
        keys = [fold(x) for x in parts]
        return {"subject": next((AFRICA_FOLDERS[k] for k in reversed(keys) if k in AFRICA_FOLDERS), None),
                "action": bool(AFRICA_ACTION & set(keys)), "setting_folder": None}
    if top == "landscape":
        return {"subject": top, "action": None, "setting_folder": parts[1] if len(parts) > 1 else None}
    if top == "supplementary_shots":   # small subjects for cutaways: frogs, insects, gecko, flowers...
        sub = parts[1] if len(parts) > 1 else None
        return {"subject": sub, "action": "action" in parts[2:] if sub not in FLAT else None,
                "setting_folder": None, "supplementary": True}
    if top in FLAT:
        return {"subject": top, "action": None, "setting_folder": None}
    return {"subject": top, "action": "action" in parts[1:], "setting_folder": None}


LAYOUT = {
    "video": {"<subject>/": "animal does nothing: rests, sleeps, looks around",
              "<subject>/action/": "animal does something: walks, runs, stalks, hunts, eats, flies, swims",
              "birds/, insects/": "all clips flat (action = null)",
              "landscape/<setting>/": "forest, water, sky_weather, detail, other",
              "supplementary_shots/<subject>/": "cutaway subjects (frogs, insects, gecko, flowers): "
                                                "subject = subfolder, supplementary = true",
              "fields": "subject/action/setting_folder from folders (user's decision); tags = older vision "
                        "tags where present; title_hint = stock file name",
              "africa": "subject = English species of the deepest species folder (AFRICA_FOLDERS), action = under "
                        "Chạy/Rình/Đi bộ tới mồi/Hunting; savannah: subject = landscape"},
    "audio": {"<category>/": "folder name as given by the user (ambience_sound, Nature_sound, tense_music...)",
              "fields": "category from folder; title_hint = stock file name"},
}


def save(root, kind, idx):
    clips = idx["clips"]
    key = "category" if kind == "audio" else "subject"
    groups = {}
    for c in clips.values():
        groups[c.get(key) or "(root)"] = groups.get(c.get(key) or "(root)", 0) + 1
    idx.pop("vocab", None)
    idx.update({"kind": kind, "root": str(root), "updated": date.today().isoformat(), "layout": LAYOUT[kind],
                "stats": {"files": len(clips), "minutes": round(sum(c["duration"] for c in clips.values()) / 60, 1),
                          key: dict(sorted(groups.items()))}})
    idx["clips"] = dict(sorted(clips.items(), key=lambda kv: kv[1]["path"]))
    p = index_of(root)
    assert p.drive.upper() != "Z:", f"refusing to write on read-only drive Z: {p}"
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(idx, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def listing(label, names):
    if names:
        print(f"  {label} ({len(names)}): " + ", ".join(names[:SHOW])
              + (f" ... +{len(names) - SHOW}" if len(names) > SHOW else ""))


def scan(name):
    root, kind, source = ROOTS[name]
    if not root.is_dir():   # NAS offline / drive not mapped: an empty walk would drop every entry and its tags
        print(f"{name} ({root}): NOT REACHABLE, index left as is")
        return
    p_idx = index_of(root)
    idx = json.loads(p_idx.read_text(encoding="utf-8")) if p_idx.exists() else {"clips": {}}
    clips = idx["clips"]
    seen, new, moved, dups = set(), [], [], []
    inner = [r for r, _, _ in ROOTS.values() if root in r.parents]  # roots nested in this one have their own index
    for p in sorted(root.rglob("*")):
        if p.suffix.lower() not in EXTS[kind] or p.name.startswith("._") or SKIP_DIRS & set(p.parts) \
                or any(r in p.parents for r in inner) or not p.is_file():
            continue
        rel = p.relative_to(root)
        cid = fast_hash(p)
        c = clips.get(cid)
        # same content twice: keep the copy the index already points to, report the other one
        if cid in seen or (c and c["path"] != str(rel) and (root / c["path"]).exists()):
            if str(rel) != clips[cid]["path"]:
                dups.append(f"{rel} = {clips[cid]['path']}")
            seen.add(cid)
            continue
        seen.add(cid)
        if c is None:
            c = clips[cid] = {"path": str(rel), **probe(p), "title_hint": title_hint(p.name)}
            new.append(str(rel))
        elif c["path"] != str(rel):
            moved.append(f"{c['path']} -> {rel}")
            c["path"] = str(rel)
        c.pop("folder_sub", None)
        c.pop("supplementary", None)
        c["title_hint"] = title_hint(p.name)
        c.update(folder_info(kind, rel, name))
        if source:
            c["source"] = source
    removed = [clips.pop(k)["path"] for k in [k for k in clips if k not in seen]]
    save(root, kind, idx)
    print(f"{name} ({root}): {len(clips)} files | new {len(new)}, moved {len(moved)}, removed {len(removed)}, "
          f"duplicates {len(dups)}")
    listing("NEW", new)
    listing("MOVED", moved)
    listing("REMOVED", removed)
    listing("DUPLICATE (delete one)", dups)


def selftest():
    fi = lambda rel, n: folder_info("video", Path(rel), n)  # noqa: E731
    assert fi("Sử tử/Hunting/a.mov", "africa_video") == {"subject": "lion", "action": True, "setting_folder": None}
    assert fi(unicodedata.normalize("NFD", "hà mã") + "/a.mp4", "africa_video")["subject"] == "hippo"
    assert fi("AI/Chạy/cheetah_dry_earth/a.mp4", "africa_ai")["subject"] == "cheetah"
    assert fi("AI/Rình/Báo/a.mp4", "africa_ai") == {"subject": None, "action": True, "setting_folder": None}
    assert fi("lion/a.mp4", "africa_ai")["subject"] == "lion" and fi("New folder/a.mp4", "africa_video")["subject"] is None
    assert fi("Mist/a.mov", "savannah")["subject"] == "landscape"
    assert fi("jaguar/action/a.mp4", "video") == {"subject": "jaguar", "action": True, "setting_folder": None}
    assert not any(v.endswith("s") for v in AFRICA_FOLDERS.values()), "tag_source.folder_species strips a final s"
    assert index_of(ROOTS["africa_ai"][0]).name == "africa_ai_library.json" and index_of(ROOTS["video"][0]).name == "video_library.json"
    assert set(video_roots("africa")) == {"africa_video", "africa_ai", "africa_ai_check", "savannah"}
    assert ROOTS["ai"][0] in ROOTS["africa_ai_check"][0].parents  # scan() keeps _africa out of the amazon index
    assert set(REGION) == {n for n, (_, k, _) in ROOTS.items() if k == "video"}, "every video root needs a region"
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        selftest()
    else:
        for k in sys.argv[1:] or list(ROOTS):
            scan(k)
