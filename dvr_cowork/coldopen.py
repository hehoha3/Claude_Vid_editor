r"""Cold open: the first ~12 s of every footage+AI 1-3h film (user 2026-11-06; full-AI 8-15p keeps its 30 s hook
from 0:00, no cold open).

    0:00 -> at      black; a string riser into an impact (SFX_DIR, A9); the hit lands on `at` (<= IMPACT_MAX s)
    at   -> end     story 1's most tense moment (a stalk, a hunt, a danger closing in; user 2026-11-06, no thumbnail),
                    always full-AI clips (6-9 s each, cut on the timeline), never library footage: shot 1 an intense
                    close-up of an animal's eye / face; prey: its fear, then the danger it faces (a cliff edge, a ring
                    of wolves...); predator: the hard stare, the prey, then its teeth / hungry face; then the moment
                    builds, unresolved (never its outcome). No narrator; the intro music starts on the hit and ends
                    with the intro.
    end             the first narration onset (VO_START)

The impact and the music are placed with the film (plan.py / place.py); V1 at -> end waits for the clips. In the
first /doc-edit run Claude picks the moment from story 1 (brief.md), writes the spec (.work/doc_edit/<key>/coldopen.json),
then:

    python -m dvr_cowork coldopen prompts <video>            gates -> <video>\coldopen-prompt.csv; clips -> <video>\coldopen\1.mp4..
    python -m dvr_cowork coldopen place <video> [--apply]    clips -> V1 at..end, backup first
    python -m dvr_cowork coldopen impact <video>             the impact file of this film (picked once, kept)
    python -m dvr_cowork coldopen --selftest
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from .prompt_rules import csv_text, issues, render, shot_size
from .videokey import day_project, video_key

ROOT = Path(__file__).resolve().parents[1]
COLD_END = 12.0  # s: the cold open's nominal end (plan.py: narration starting after it = a cold-open film)
VO_START = 12.6  # s: footage+AI narrator start = cold open end (timestamps.VO_START)
IMPACT_MAX = 1.0  # s: the hit lands here at the latest; a longer riser starts part-way in
CLIP_MIN, CLIP_MAX = 6, 9  # s: generated clip length
CUT_IN = 1.0  # s into a clip: AI clips morph in their first frames
SHOTS = (3, 6)
FIRST = {"prey": "fear_closeup", "predator": "eye_closeup"}
SECOND = {"prey": "danger", "predator": "prey"}
ROLES = {"fear_closeup", "eye_closeup", "danger", "prey", "hunger_closeup", "escalation", "situation", "reaction"}
CLOSE = re.compile(r"\b(?:extreme close[- ]up|close[- ]up|macro)\b", re.I)
EYEFACE = re.compile(r"\b(?:eyes?|face|muzzle|snout|teeth|fangs|jaws?)\b", re.I)
WEIGHTS = (0.85, 0.9, 1.0, 1.1, 1.2, 1.3)  # cut lengths ramp into the situation
SFX_BIN = "4. Audio/SFX"
CLIP_BIN = "8. Cold open"  # its own bin: never a teaser / "7. Open" pick
IMPACT_TRACK = 9
REG = ROOT / ".work" / "library" / "impact.json"


class ColdError(Exception):
    pass


# ------------------------------------------------------------------ the impact (riser -> hit)
def sfx_dir():
    from .config import load_config
    return Path(load_config()["paths"]["audio_lib"]) / "SXF" / "impact"


def hit_of(samples, sr):
    """Time of the hit in a riser -> impact file: the biggest jump of the 20 ms RMS (vs the 60 ms before) up to its
    loudest point; the riser climbs smoothly, the hit jumps."""
    import numpy as np
    w = max(1, int(sr * 0.02))
    n = len(samples) // w
    if n < 6:
        return 0.0
    rms = np.sqrt((np.asarray(samples[:n * w], dtype=np.float64).reshape(n, w) ** 2).mean(1)) + 1e-9
    peak = int(rms.argmax())
    jump = np.zeros(n)
    jump[3:] = rms[3:] - rms[:-3]
    j = int(jump[:peak + 3].argmax()) if peak else 0
    return round(max(0, j - 1) * w / sr, 3)


def _reg():
    return json.loads(REG.read_text("utf-8")) if REG.exists() else {"hits": {}, "used": {}}


def impact(key, files=None, reg=None, save=True):
    """The film's impact: kept once picked; else the least used file no other film of the same day project has.
    -> {path, hit, src_in, at, dur}."""
    reg = reg if reg is not None else _reg()
    files = sorted(files if files is not None else
                   [p for p in sfx_dir().glob("*") if p.suffix.lower() in (".mp3", ".wav")], key=str)
    if not files:
        raise ColdError(f"no impact file in {sfx_dir()} (audio-expert fetch: string riser + impact)")
    used, day = reg["used"], day_project(key)
    path = used.get(key)
    if not path or not any(str(f) == path for f in files):
        busy = {p for k, p in used.items() if k != key and day_project(k) == day}
        count = {str(f): sum(p == str(f) for p in used.values()) for f in files}
        path = min((str(f) for f in files if str(f) not in busy), key=lambda p: (count[p], p), default=None) \
            or min(count, key=lambda p: (count[p], p))
    h = reg["hits"].get(path)
    if not h:
        from .transcribe import SR, load_audio
        a = load_audio(path)
        h = {"hit": hit_of(a, SR), "dur": round(len(a) / SR, 3)}
        reg["hits"][path] = h
    src_in = round(max(0.0, h["hit"] - IMPACT_MAX), 3)
    used[key] = path
    if save:
        REG.parent.mkdir(parents=True, exist_ok=True)
        REG.write_text(json.dumps(reg, ensure_ascii=False, indent=1), "utf-8")
    return {"path": path, "hit": h["hit"], "src_in": src_in, "at": round(h["hit"] - src_in, 3),
            "dur": round(h["dur"] - src_in, 3)}


# ------------------------------------------------------------------ the spec (Claude writes it from story 1)
def spec_path(v):
    v = Path(v)
    if (v / ".production" / "story.json").exists():
        raise ColdError("full-AI 8-15p films have no cold open: the 30 s hook starts at 0:00 (user 2026-11-06)")
    return ROOT / ".work" / "doc_edit" / video_key(v) / "coldopen.json"


def story1_window(v):
    """(start, end) s of story 1 on the timeline: intro end -> story 2 (plan.py open_ok)."""
    sl = json.loads((ROOT / ".work" / "doc_edit" / video_key(v) / "plan.json").read_text("utf-8"))["slots"]
    a = next((s["start"] for s in sl if not s.get("intro")), 0.0)
    b = next((s["start"] for s in sl if s.get("open_ok") is False), sl[-1]["start"] + sl[-1]["dur"])
    return a, b


def span(text):
    """'02:20-02:45' -> (140.0, 165.0), else None."""
    from .timecode import parse_clock
    m = re.fullmatch(r"\s*([\d:.]+)\s*[-–]\s*([\d:.]+)\s*", str(text or ""))
    try:
        return (parse_clock(m[1]), parse_clock(m[2])) if m else None
    except Exception:  # noqa: BLE001
        return None


def validate(spec, story1=None):
    """-> list of problems (empty = ok). `from` = the story-1 moment it comes from (mm:ss-mm:ss, inside story1 when
    given); 3-6 shots; shot 1 an eye / face close-up of the right kind; prey -> shot 2 the danger, predator -> shot 2
    the prey + a teeth / hungry-face close-up early; clips 6-9 s; shared prompt gates (no contact, keep moving, no
    stare-down)."""
    errs = []
    f = span(spec.get("from"))
    if not f or f[1] <= f[0]:
        errs.append(f"from: {spec.get('from')!r} must be the story-1 moment it shows, 'mm:ss-mm:ss' (a stalk, a hunt, a danger)")
    elif story1 and not (story1[0] - 0.5 <= f[0] and f[1] <= story1[1] + 0.5):
        errs.append(f"from: {spec['from']} lies outside story 1 ({story1[0]:.0f}-{story1[1]:.0f} s)")
    kind = spec.get("kind")
    if kind not in FIRST:
        return errs + [f"kind must be prey or predator, got {kind!r}"]
    for k in ("situation", "place", "light"):
        if not str(spec.get(k, "")).strip():
            errs.append(f"{k}: missing")
    sh = spec.get("shots") or []
    if not SHOTS[0] <= len(sh) <= SHOTS[1]:
        return errs + [f"{len(sh)} shots; the cold open takes {SHOTS[0]}-{SHOTS[1]}"]
    roles = [s.get("role") for s in sh]
    if roles[0] != FIRST[kind] or not CLOSE.search(sh[0].get("camera", "")) \
            or not EYEFACE.search(" ".join(sh[0].get("beats", []))):
        errs.append(f"shot 1: role {FIRST[kind]}, an (extreme) close-up camera, beats on the eye / face")
    if roles[1] != SECOND[kind]:
        errs.append(f"shot 2: role {SECOND[kind]} ({'the danger it faces' if kind == 'prey' else 'the prey it watches'})")
    if kind == "predator" and "hunger_closeup" not in roles[:4]:
        errs.append("predator: a hunger_closeup (teeth / drooling side face / battle-hungry face) within the first 4 shots")
    for i, s in enumerate(sh, 1):
        if s.get("role") not in ROLES:
            errs.append(f"shot {i}: role {s.get('role')!r} not in {sorted(ROLES)}")
        if not CLIP_MIN <= float(s.get("clip_s", 0)) <= CLIP_MAX:
            errs.append(f"shot {i}: clip_s {s.get('clip_s')} outside {CLIP_MIN}-{CLIP_MAX} s")
        if not s.get("subject") or not s.get("camera") or not 1 <= len(s.get("beats") or []) <= 4:
            errs.append(f"shot {i}: needs subject, camera and 1-4 beats")
        errs += [f"shot {i}: {x}" for x in issues(" ".join([s.get("subject", "")] + list(s.get("beats") or [])))]
    return errs


def layout(spec, at, end):
    """Timeline cuts: shot k from `at` on, lengths ramping (WEIGHTS) to fill at..end exactly, each taken from
    cut_in (default CUT_IN) of its clip. -> [(shot no, start s, length s, src_in s)]."""
    sh = spec["shots"]
    w = WEIGHTS[:len(sh)]
    total, out, t = end - at, [], at
    for k, (s, x) in enumerate(zip(sh, w), 1):
        ln = round(end - t, 3) if k == len(sh) else round(total * x / sum(w), 3)
        out.append((k, round(t, 3), ln, float(s.get("cut_in", CUT_IN))))
        t += ln
    return out


def prompt_rows(spec, v):
    rows = []
    for k, s in enumerate(spec["shots"], 1):
        d = float(s["clip_s"])
        rows.append({"shot_id": f"C{k}", "cluster": "COLD", "dur_s": f"{d:g}", "kind": "ai_generated",
                     "animal": s["subject"], "action": s["role"], "environment": spec["place"],
                     "time_of_day": spec["light"], "shot_size": shot_size(s["camera"]), "camera_angle": s["camera"],
                     "direction": s.get("vec", "static"), "mo_ta": spec["situation"],
                     "search_keywords": f"{s['subject']} {s['role']} cold open",
                     "generation_prompt": render(s["camera"], spec["place"], spec["light"], [s["subject"] + ": " + s["beats"][0]] + s["beats"][1:], d),
                     "reason": f"COLD OPEN (story 1 {spec['from']}): save as {v / 'coldopen' / f'{k}.mp4'}"})
    return rows


def load(v):
    p = spec_path(v)
    if not p.exists():
        raise ColdError(f"no cold-open spec {p}: pick story 1's tense moment, write it first (doc-edit references/coldopen.md)")
    return json.loads(p.read_text("utf-8"))


def prompts(v):
    v = Path(v)
    spec = load(v)
    if errs := validate(spec, story1_window(v)):
        raise ColdError(f"{len(errs)} cold-open problems:\n" + "\n".join(errs))
    out = v / "coldopen-prompt.csv"
    out.write_text(csv_text(prompt_rows(spec, v)), "utf-8", newline="")
    (v / "coldopen").mkdir(exist_ok=True)
    return {"prompts": len(spec["shots"]), "csv": str(out), "save": f"{v / 'coldopen'}\\1.mp4 .. {len(spec['shots'])}.mp4"}


# ------------------------------------------------------------------ placing V1 at..end
def window(v):
    """(at, end) of this film's cold open in seconds."""
    v = Path(v)
    at = impact(video_key(v))["at"]
    plan = json.loads((ROOT / ".work" / "doc_edit" / video_key(v) / "plan.json").read_text("utf-8"))
    s0 = plan["slots"][0]
    if not s0.get("cold"):
        raise ColdError("this film was planned without a cold open (narration from 0:03.6): nothing to place")
    return at, s0["start"] + s0["dur"]


def clips(v, spec, cuts):
    from .fullai.core import probe
    out, errs = {}, []
    for k, _, ln, a in cuts:
        p = Path(v) / "coldopen" / f"{k}.mp4"
        try:
            m = probe(p)
            if m["duration"] < a + ln + 0.2:
                errs.append(f"{p.name}: {m['duration']:.1f}s, needs {a + ln + 0.2:.1f}s (cut_in {a} + {ln:.2f})")
            out[k] = (p, m)
        except Exception as e:  # noqa: BLE001
            errs.append(f"{p.name}: {e}")
    if errs:
        raise ColdError("cold-open clips:\n" + "\n".join(errs))
    return out


def place(v, apply=False):
    v = Path(v)
    spec = load(v)
    if errs := validate(spec):
        raise ColdError(f"{len(errs)} cold-open problems:\n" + "\n".join(errs))
    at, end = window(v)
    cuts = layout(spec, at, end)
    media = clips(v, spec, cuts)
    plan = [f"C{k} {t:.2f}-{t + ln:.2f}s from {media[k][0].name} @{a:g}s" for k, t, ln, a in cuts]
    if not apply:
        return {"dry_run": True, "window": [at, end], "cuts": plan, "next": "--apply (backup first)"}
    from .config import load_config
    from .resolve_conn import connect
    from .resolve_ops import backup_timeline, clip_fps, ensure_bin, find_timeline, timeline_fps, use_channel
    use_channel(v)
    pm = connect(load_config()).GetProjectManager()
    pr = pm.GetCurrentProject()
    tl = find_timeline(pr, "Edit")
    if not tl:
        raise ColdError(f"no Edit in {pr.GetName()} for {v}")
    fps, t0 = timeline_fps(tl, pr), int(tl.GetStartFrame())
    f = lambda s: round(s * fps)  # noqa: E731
    busy = [i for i in tl.GetItemListInTrack("video", 1) or [] if int(i.GetStart()) - t0 < f(end) and int(i.GetEnd()) - t0 > f(at)]
    if busy:
        raise ColdError(f"V1 {at:.2f}-{end:.2f}s already holds {len(busy)} item(s): kept untouched (additive only)")
    prev = pr.GetCurrentTimeline()
    pr.SetCurrentTimeline(tl)
    bak = f"Edit_bak_coldopen_{datetime.now():%Y%m%d_%H%M%S}"
    if not backup_timeline(pr, tl, bak):
        raise ColdError("backup failed: nothing placed")
    mp = pr.GetMediaPool()
    mp.SetCurrentFolder(ensure_bin(mp, CLIP_BIN))
    items = {k: (mp.ImportMedia([str(p)]) or [None])[0] for k, (p, _) in media.items()}
    placed, failed = [], []
    for k, t, ln, a in cuts:
        it = items[k]
        if not it:
            failed.append(f"C{k} import"); continue
        cf = clip_fps(it, fps)
        n = f(t + ln) - f(t)
        res = mp.AppendToTimeline([{"mediaPoolItem": it, "startFrame": round(a * cf), "endFrame": round(a * cf) + round(n * cf / fps),
                                    "mediaType": 1, "trackIndex": 1, "recordFrame": t0 + f(t)}])  # V1 only: A1 stays empty
        ti = res[0] if res else None
        if not ti:
            failed.append(f"C{k} V1"); continue
        placed.append(f"C{k} {t:.2f}s {(int(ti.GetEnd()) - int(ti.GetStart())) / fps:.2f}s")
    pm.SaveProject()
    if prev:
        pr.SetCurrentTimeline(prev)
    spec["placed"] = {"at": at, "end": end, "backup": bak, "items": placed}
    spec_path(v).write_text(json.dumps(spec, ensure_ascii=False, indent=1), "utf-8")
    return {"backup": bak, "placed": placed, "failed": failed, "window": [at, end]}


# ------------------------------------------------------------------ CLI + selftest
def selftest():
    import numpy as np
    import tempfile
    sr = 16000
    t = np.arange(int(sr * 3)) / sr
    riser = np.where(t < 1.4, 0.05 + 0.25 * t / 1.4, 0.0) * np.sin(2 * np.pi * 900 * t)
    hit = np.where(t >= 1.4, np.exp(-(t - 1.4) * 3), 0.0) * np.sin(2 * np.pi * 60 * t)
    assert abs(hit_of(riser + hit, sr) - 1.4) <= 0.06, hit_of(riser + hit, sr)
    files = ["a.mp3", "b.mp3", "c.mp3"]
    reg = {"hits": {f: {"hit": 1.5, "dur": 8.0} for f in files}, "used": {"africa_061126_1__Chann_1": "a.mp3"}}
    x = impact("africa_061126_1__Chann_2", files, reg, save=False)
    assert x["path"] == "b.mp3" and (x["src_in"], x["at"], x["dur"]) == (0.5, 1.0, 7.5), x  # never the day's other film
    assert impact("africa_061126_1__Chann_2", files, reg, save=False)["path"] == "b.mp3"  # kept once picked
    with tempfile.TemporaryDirectory() as d:
        sh = lambda r, cam, b: {"role": r, "subject": "A single adult snow leopard", "camera": cam, "beats": [b], "clip_s": 8}  # noqa: E731
        spec = {"from": "02:20-02:45", "kind": "predator", "situation": "báo tuyết rình đàn dê", "place": "a steep scree slope",
                "light": "neutral daylight", "shots": [sh("eye_closeup", "extreme close-up 100mm", "its pale eyes narrow, ears flick"),
                                                      sh("prey", "telephoto wide", "a herd of ibex picks across the scree"),
                                                      sh("hunger_closeup", "side close-up", "lips draw back from long teeth, breath steams"),
                                                      sh("situation", "low tracking medium", "it slinks forward along the ledge")]}
        assert validate(spec) == [], validate(spec)
        assert validate(spec, (100.0, 900.0)) == [] and any("outside story 1" in e for e in validate(spec, (200.0, 900.0)))
        assert any(e.startswith("from:") for e in validate(dict(spec, **{"from": "thumbnail.jpg"})))  # story 1, not a thumbnail
        bad = dict(spec, kind="prey")
        assert any("shot 1" in e for e in validate(bad)) and any("shot 2" in e for e in validate(bad))
        assert any("contact" in e for e in validate(dict(spec, shots=spec["shots"][:3] + [sh("situation", "wide", "it bites the ibex")])))
        cuts = layout(spec, 1.0, 12.0)
        assert cuts[0][1] == 1.0 and abs(cuts[-1][1] + cuts[-1][2] - 12.0) < 1e-6 and cuts[0][2] < cuts[-1][2]
        rows = prompt_rows(spec, Path(d))
        assert len(rows) == 4 and rows[0]["shot_id"] == "C1" and "8-second" in rows[0]["generation_prompt"]
    print("coldopen selftest ok")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--selftest" in argv:
        return selftest()
    if len(argv) < 2 or argv[0] not in ("prompts", "place", "impact"):
        print(__doc__); return 2
    v = Path(argv[1])
    v = v.parent if v.name.lower() == "audios" else v
    try:
        out = prompts(v) if argv[0] == "prompts" else place(v, "--apply" in argv) if argv[0] == "place" \
            else impact(video_key(v))
    except ColdError as e:
        print(f"STOP: {e}"); return 1
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
