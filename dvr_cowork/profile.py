"""Video-type router: profile registry, per-video descriptor + pinned snapshot, legacy detection, phase context.

`python -m dvr_cowork profile detect|context|backfill|list ...` from the workspace root. Prints short JSON; never touches
Resolve, media, narration or plans. Engines are looked up in ENGINES (never a command taken from JSON).
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys

from .fullai.core import ROOT, Stop, object_hash, prod, read_json, video_path, write_json

PROFILES = ROOT / "config" / "profiles"
ALIASES = {"full-ai": "full_ai_mountain", "8-15p": "full_ai_mountain", "8p": "full_ai_mountain",
           "8p-full-ai": "full_ai_mountain", "footage+ai": "footage_ai_long", "1-3h": "footage_ai_long",
           "1h": "footage_ai_long", "1h-footage+ai": "footage_ai_long", "long": "footage_ai_long", "ocean": "ocean_long"}
# engine_id -> how the agent runs it. Python owns this table; profiles only name an engine_id.
# engine ids are internal (pinned films hash them): mountain_ai = full-AI 8-15p of any region, footage_long = 1-3h.
ENGINES = {"mountain_ai": ".venv/Scripts/python.exe -m dvr_cowork ai", "footage_long": ".venv/Scripts/python.exe -m dvr_cowork"}
DESCRIPTOR = "video.project.json"
LOCK = "profile.lock.json"
PHASES = ("author", "voice", "prompts", "ingest", "intro", "sound", "done", "recovery", "edit")
# Legacy traces of each engine in a video folder without a descriptor.
# .production/ is 8p-only (1h folders hold renders, plan, srt, audios/); old 8p films may have only a journal there.
MOUNTAIN = (".production", "audios/visual_plan.md", "missing-prompt.md", "shot_manifest.csv")
LONG = ("plan.md", "missing_prompts.txt", "audios/four_files.src.md")
# 1h names are <Title>_Screenplay_EN.md...; 8p's lowercase screenplay.md must not match (Windows globs ignore case).
LONG_GLOBS = ("audios/*_Timestamp_EN_VI*.md", "audios/*_Screenplay_EN*.md", "audios/*_Visual_Edit_Plan*.md")


def profile_id(name):
    key = str(name).strip()
    return ALIASES.get(key.lower(), key)


def load(name, version=None, allow_disabled=False):
    pid = profile_id(name)
    files = {int(m[1]): p for p in PROFILES.glob(f"{pid}.v*.json") if (m := re.fullmatch(rf"{re.escape(pid)}\.v(\d+)\.json", p.name))}
    if not files:
        raise Stop(f"Unknown profile {name!r}; known: {', '.join(sorted(known()))} (aliases: {', '.join(ALIASES)})")
    v = int(version) if version is not None else max(files)
    if v not in files:
        raise Stop(f"{pid} has no version {v}; have {sorted(files)}")
    p = read_json(files[v])
    check(p, pid, v)
    if not p["enabled"] and not allow_disabled:
        raise Stop(f"Profile {pid} v{v} is disabled (reserved, no engine yet): " + ", ".join(p.get("missing_before_enable", [])))
    return p


def known():
    return {re.sub(r"\.v\d+$", "", p.stem) for p in PROFILES.glob("*.v*.json")}


def check(p, pid, version):
    """The checkable part of a profile; the story/prompt craft lives in the referenced Markdown."""
    bad = []
    if p.get("schema_version") != 1: bad.append("schema_version must be 1")
    if p.get("profile_id") != pid or p.get("profile_version") != version: bad.append("profile_id/version differ from file name")
    if not isinstance(p.get("enabled"), bool): bad.append("enabled must be true/false")
    if p.get("enabled") and p.get("engine_id") not in ENGINES: bad.append(f"engine_id {p.get('engine_id')!r} not in registry")
    rt = p.get("runtime", {})
    lo, hi = rt.get("min_minutes"), rt.get("max_minutes")
    if not isinstance(lo, (int, float)) or (hi is not None and not lo <= rt.get("default_minutes", lo) <= hi):
        bad.append("runtime min <= default <= max")
    intro = p.get("intro")
    if intro:
        a, b, d = intro.get("cut_min_s"), intro.get("cut_max_s"), intro.get("duration_s")
        if not (isinstance(a, (int, float)) and 0 < a <= b <= d):
            bad.append("intro needs 0 < cut_min_s <= cut_max_s <= duration_s")
        if intro.get("mode") != "cuts_from_body": bad.append("intro.mode must be cuts_from_body")
        s0, s1 = intro.get("selective_speed_range", [1, 1])
        if not 1 <= s0 <= s1 <= 1.5: bad.append("selective_speed_range within 1.0-1.5")
    body = p.get("body")
    if body and not 0 < body["shot_min_s"] <= body["shot_max_s"]: bad.append("body shot range")
    for phase, refs in p.get("refs", {}).items():
        if phase not in PHASES: bad.append(f"unknown ref phase {phase}")
        bad += [f"missing ref {r}" for r in refs if not (ROOT / r).is_file()]
    if bad:
        raise Stop(f"Profile {pid} v{version} invalid: " + "; ".join(bad))


def channel(video):
    m = re.match(r"(?i)chann_(\d+)(?:_|$)", Path(video).parent.name)
    return f"Chann_{m[1]}" if m else None


def create(video, name, region=None, minutes=None, title=None):
    """Descriptor + pinned snapshot, written once before authoring. Never overwrites."""
    v = video_path(video)
    if (v / DESCRIPTOR).exists():
        raise Stop(f"{v / DESCRIPTOR} exists; a pinned film is changed only by an explicit migration")
    p = load(name)
    region = region or p.get("default_region")
    if p.get("regions") and region not in p["regions"]:
        raise Stop(f"Region {region!r} not in {p['profile_id']} regions {p['regions']}")
    rt = p["runtime"]
    minutes = float(minutes if minutes is not None else rt["default_minutes"])
    if minutes < rt["min_minutes"] or (rt["max_minutes"] is not None and minutes > rt["max_minutes"]):
        raise Stop(f"{minutes:g} min outside {p['profile_id']} range {rt['min_minutes']}-{rt['max_minutes'] or 'open'}")
    ch = channel(v)
    lock = {"profile": p, "profile_sha256": object_hash(p), "pinned_at": datetime.now().isoformat(timespec="seconds")}
    desc = {"schema_version": 1, "video_id": f"{ch or 'root'}__{v.name}", "profile_id": p["profile_id"],
            "profile_version": p["profile_version"], "engine_id": p["engine_id"], "region_id": region,
            "channel_key": ch, "target_minutes": minutes, "profile_snapshot": f".production/{LOCK}",
            "profile_sha256": lock["profile_sha256"]}
    if title: desc["title"] = title
    write_json(prod(v) / LOCK, lock)
    write_json(v / DESCRIPTOR, desc)
    return desc


def pinned(video):
    """(descriptor, profile) of a film with a descriptor, else (None, None). Any mismatch stops: never silently fixed."""
    v = video_path(video)
    if not (v / DESCRIPTOR).exists():
        return None, None
    d = read_json(v / DESCRIPTOR)
    if d.get("schema_version") != 1:
        raise Stop(f"{DESCRIPTOR}: unsupported schema_version {d.get('schema_version')}")
    lp = v / d.get("profile_snapshot", f".production/{LOCK}")
    if not lp.is_file():
        raise Stop(f"Snapshot {lp} missing; restore it (never re-pinned from the workspace profile silently)")
    lock = read_json(lp)
    p = lock.get("profile") or {}
    if object_hash(p) != lock.get("profile_sha256") or lock.get("profile_sha256") != d.get("profile_sha256"):
        raise Stop(f"{lp.name} does not match its hash / the descriptor; inspect it, do not edit by hand")
    if (p.get("profile_id"), p.get("profile_version"), p.get("engine_id")) != (d["profile_id"], d["profile_version"], d["engine_id"]):
        raise Stop("Descriptor and snapshot name different profiles/engines")
    if not p.get("enabled"):
        raise Stop(f"Pinned profile {p.get('profile_id')} is disabled")
    return d, p


def traces(v):
    m = [t for t in MOUNTAIN if (v / t).exists()]
    l = [t for t in LONG if (v / t).exists()] + [g for g in LONG_GLOBS if any(v.glob(g))]
    return m, l


def detect(video):
    v = video_path(video)
    d, p = pinned(v)
    m, l = traces(v)
    if d:  # the snapshot itself lives in .production/, so that folder is no trace here
        other = l if p["engine_id"] == "mountain_ai" else [t for t in m if t != ".production"]
        if other:
            raise Stop(f"Descriptor says {d['profile_id']} but the folder also holds the other engine's files: {other}")
        return {"video": str(v), "source": "descriptor", "profile": d["profile_id"], "version": d["profile_version"],
                "engine": ENGINES[d["engine_id"]], "region": d.get("region_id"), "channel": d.get("channel_key")}
    if m and l:
        raise Stop(f"Both engines' files in {v}: mountain {m}, long {l}. Resolve by hand; nothing is built.")
    if not (m or l):  # CLAUDE.md rule 9: never guess a type
        return {"video": str(v), "source": "unknown", "profile": None, "channel": channel(v),
                "ask": "No descriptor and no engine files: ask full-AI 8-15p or footage+AI 1-3h (create-doc-mov pins it)"}
    pid = "full_ai_mountain" if m else "footage_ai_long"
    pre = v.name.split("_")[0].lower()  # region = the folder prefix (old congo_* = amazon); vid_* says none
    region = "amazon" if pre == "congo" else pre if pre in ("amazon", "africa", "himalaya", "ocean") else None
    return {"video": str(v), "source": "legacy-trace", "profile": pid, "version": 1,
            "engine": ENGINES[load(pid, 1)["engine_id"]], "region": region, "channel": channel(v), "traces": m or l}


def full_ai(video):
    return detect(video).get("engine") == ENGINES["mountain_ai"]


def context(video, phase):
    """Short pack for one phase: type, scope, stage, blockers, the refs to read (once per task)."""
    if phase not in PHASES:
        raise Stop(f"phase must be one of {PHASES}")
    info = detect(video)
    if not info["profile"]:
        raise Stop(info["ask"])
    v = Path(info["video"])
    _, p = pinned(v)
    p = p or load(info["profile"], info["version"])
    pack = {k: info[k] for k in ("profile", "version", "engine", "channel") if k in info}
    refs = load(info["profile"]).get("refs", {})  # docs come from the latest version; the pin holds the numbers
    pack["refs"] = refs.get(phase) or refs.get("edit", [])
    if p["engine_id"] == "mountain_ai":
        st = prod(v) / "state.json"
        state = read_json(st) if st.exists() else {}
        pack["stage"] = state.get("stage", "NO_STATE")
        intro = p.get("intro", {})
        pack["contract"] = {"runtime_min": [p["runtime"]["min_minutes"], p["runtime"]["max_minutes"]],
                            "body_s": [p["body"]["shot_min_s"], p["body"]["shot_max_s"]],
                            "intro": {k: intro.get(k) for k in ("mode", "duration_s", "cut_min_s", "cut_max_s",
                                                                "preferred_cut_count", "selective_speed_range") if k in intro},
                            "animal_contact": p.get("story", {}).get("animal_contact")}
        blockers = [f"{k}: {state[k]}" for k in ("error", "blocker") if state.get(k)]
        if phase in ("voice", "prompts") and not any((v / f).is_dir() for f in ("voice", "audios/mp3")):
            blockers.append("no voice/ folder with numbered MP3s")
        if phase in ("ingest", "intro") and not (v / "shots").is_dir():
            blockers.append("no shots/ folder")
        pack["blockers"] = blockers
    else:
        pack["stage"] = "run: .venv/Scripts/python.exe -m dvr_cowork.jobs status"
    return pack


def backfill(video, apply=False):
    """Pin a descriptor on a film made before profiles. Dry-run by default; never edits narration/plan/timeline/media."""
    info = detect(video)
    if info["source"] == "descriptor":
        return {"video": info["video"], "already": info["profile"]}
    if info["source"] == "unknown":
        raise Stop(info["ask"])
    p = load(info["profile"], 1)
    plan = {"video": info["video"], "would_pin": f"{p['profile_id']} v1", "writes": [DESCRIPTOR, f".production/{LOCK}"],
            "traces": info["traces"]}
    if info["profile"] == "footage_ai_long":
        plan["note"] = "1h folders stay clean (renders, plan, srt, audios/); a descriptor there needs the user's yes"
    if not apply:
        return {"dry_run": True, **plan}
    v = Path(info["video"])
    minutes = None
    if (prod(v) / "story.json").exists():
        minutes = read_json(prod(v) / "story.json").get("target_minutes")
    lock = {"profile": p, "profile_sha256": object_hash(p), "pinned_at": datetime.now().isoformat(timespec="seconds"),
            "backfilled": True}
    desc = {"schema_version": 1, "video_id": f"{channel(v) or 'root'}__{v.name}", "profile_id": p["profile_id"],
            "profile_version": 1, "engine_id": p["engine_id"], "region_id": p.get("default_region"),
            "channel_key": channel(v), "target_minutes": minutes, "profile_snapshot": f".production/{LOCK}",
            "profile_sha256": lock["profile_sha256"]}
    write_json(prod(v) / LOCK, lock)
    write_json(v / DESCRIPTOR, desc)
    return {"pinned": True, **plan}


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"): s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="dvr_cowork profile")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("detect").add_argument("video")
    q = sub.add_parser("context"); q.add_argument("video"); q.add_argument("--phase", required=True)
    q = sub.add_parser("backfill"); q.add_argument("video"); q.add_argument("--apply", action="store_true")
    sub.add_parser("list")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "detect": out = detect(a.video)
        elif a.cmd == "context": out = context(a.video, a.phase)
        elif a.cmd == "backfill": out = backfill(a.video, a.apply)
        else:
            out = []
            for pid in sorted(known()):
                p = load(pid, allow_disabled=True)
                out.append({"profile": pid, "version": p["profile_version"], "label": p.get("label"), "enabled": p["enabled"]})
        print(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
        return 0
    except (Stop, OSError, ValueError, KeyError) as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
