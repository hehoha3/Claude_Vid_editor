#!/usr/bin/env python3
"""Keep the source indexes in sync with what the user sorted on disk. No vision, no file moves.

    scan_source.py            scan all roots
    scan_source.py video|ai|audio

video  Z:\\Unseen\\Amazona\\video  real stock footage  <subject>/ = still, <subject>/action/ = action,
                                                      birds/ insects/ flat, landscape/<setting>/
ai     config.toml paths.ai_video  AI-generated clips  same folder rules as video (default D:\\AI_video)
audio  Z:\\Unseen\\Amazona\\audio  music / ambience    <category>/
sfx / sound / animal  Z:\\Unseen\\SFX, Sound, Sound Animal V1
Drive Z: is READ + COPY only (user rule 2026-10-11). Every index lives in the workspace, .work/library/<name>_library.json
(committed to git, so the team shares the tags; paths inside are relative to the root).
Clips are keyed by a content hash, so moved/renamed files keep their entry (and any earlier tags)."""
import hashlib
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from dvr_cowork.config import load_config  # noqa: E402
# name -> (root, media kind, source label stored on every clip)
ROOTS = {"video": (Path(r"Z:\Unseen\Amazona\video"), "video", "real"),
         "ai": (Path(load_config()["paths"]["ai_video"]), "video", "ai"),  # config.toml, per machine
         "audio": (Path(r"Z:\Unseen\Amazona\audio"), "audio", None),
         "sfx": (Path(r"Z:\Unseen\SFX"), "audio", None),                 # animal foley + species calls (English names)
         "sound": (Path(r"Z:\Unseen\Sound"), "audio", None),             # licensed music, <mood>/ folders
         "animal": (Path(r"Z:\Unseen\Sound Animal V1"), "audio", None)}  # animal sounds (Vietnamese names)
# user rule 2026-10-11: drive Z: is READ + COPY only - nothing is ever written, moved or deleted on it (save() refuses)
WORK = Path(__file__).resolve().parents[4] / ".work" / "library"
EXTS = {"video": {".mp4", ".mov", ".mxf", ".mkv", ".m4v"}, "audio": {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}}
INDEX = "_library.json"
SHOW = 15
FLAT = {"birds", "insects", "flowers"}


def index_of(root):
    """Index file of a root: always in the workspace, .work/library/<name>_library.json."""
    return WORK / (root.name.replace(" ", "_") + INDEX)


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


def folder_info(kind, rel):
    parts = rel.parts[:-1]
    top = parts[0] if parts else None
    if kind == "audio":
        return {"category": top}
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
                        "tags where present; title_hint = stock file name"},
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
    p_idx = index_of(root)
    idx = json.loads(p_idx.read_text(encoding="utf-8")) if p_idx.exists() else {"clips": {}}
    clips = idx["clips"]
    seen, new, moved, dups = set(), [], [], []
    for p in sorted(root.rglob("*")):
        if p.suffix.lower() not in EXTS[kind] or not p.is_file() or {"_nologo", "_z_nologo"} & set(p.parts):  # logo-free copies (hide-logo)
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
        c.update(folder_info(kind, rel))
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


if __name__ == "__main__":
    for k in sys.argv[1:] or list(ROOTS):
        scan(k)
