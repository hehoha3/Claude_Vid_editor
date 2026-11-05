"""One canonical authoring source -> four Markdown files + deterministic shot IDs."""
from __future__ import annotations

import copy
import math
import re
from .core import Stop, atomic_text, config, event, frames, object_hash, prod, read_json, stamp, video_path, write_json
from ..prompt_rules import TAIL, dur_s, issues

OUTPUTS = ("screenplay.md", "timestamp.md", "transcript.md", "visual_plan.md")
PHASES = {"hook", "setup", "story", "ending"}
ROLES = {"threat", "vulnerability", "pursuit", "obstacle", "unanswered", "none"}


def compile_story(source, durations=None, profile=None):
    """profile = the film's pinned profile (dvr_profile), else the workspace one. One contract (user 2026-11-05):
    the hook scene is voice only, one 30 s HOOK window that `hook` cuts later from reviewed body sources."""
    s = copy.deepcopy(source)
    required = ("title", "premise", "central_question", "payoff", "characters", "environment", "geography", "scenes")
    for key in required:
        if not s.get(key):
            raise Stop(f"Story source requires {key}")
    if profile is None:
        from ..profile import load
        profile = load("full_ai_mountain")
    p = profile
    intro, rt, rules = p["intro"], p["runtime"], p.get("story") or {}
    lo_s, hi_s = p["body"]["shot_min_s"], p["body"]["shot_max_s"]
    fps, target = float(s.get("fps", 24)), float(s.get("target_minutes", 8)) * 60
    if not 1 <= fps <= 120 or not math.isfinite(target) or target < rt["min_minutes"] * 60 \
            or (rt["max_minutes"] is not None and target > rt["max_minutes"] * 60):
        raise Stop(f"Use a valid frame rate and target_minutes {rt['min_minutes']}–{rt['max_minutes'] or 'open'} "
                   "(this film's pinned profile).")
    if len(s["characters"]) < 2 or any(not all(c.get(k) for k in ("id", "species", "lock", "terms")) for c in s["characters"]):
        raise Stop("Define at least two central roles with id, species, complete visual lock and terms (names used in shot text).")
    chars = {c["id"]: c for c in s["characters"]}
    if len(chars) != len(s["characters"]):
        raise Stop("Duplicate character IDs")
    for c in s["characters"]:
        if type(c.get("count")) is not int or not 1 <= c["count"] <= 50:
            raise Stop(f"{c['id']}: count must be the exact number of animals this entry puts in frame (1–50)")
        if not isinstance(c["terms"], list) or any(not isinstance(t, str) or not t.strip() for t in c["terms"]):
            raise Stop(f"{c['id']}: terms must be a list of non-empty words/phrases")
    bad = [c["id"] for c in s["characters"] if not strings(c.get("details"))]
    bad += [k for k in BIBLE if not strings(s.get(k))]
    if bad:
        raise Stop("Production bible incomplete (written to lock-assets.md): "
                   "each character needs details[] and the source needs count_lock[], zones[], terrain_lock[], light_lock[]. "
                   "Missing: " + ", ".join(bad))
    if tint := sorted({m.lower() for k in ("environment", "geography") for m in TINT.findall(s[k])}):
        raise Stop("environment/geography are in every prompt; remove light words that render a blue grade: " + ", ".join(tint))
    terms = [t.strip().lower() for c in s["characters"] for t in c["terms"]]
    if len(set(terms)) != len(terms):
        raise Stop("A term belongs to two characters; give each character its own distinct names")
    wpm = float(s.get("wpm", 155))  # measured 2026-11-05: Chann_3 narrator 157 wpm (140 left 3-5 s gaps)
    if not 120 <= wpm <= 180:
        raise Stop("wpm must be 120–180; default 155, calibrate to your actual voice.")
    cursor, ideal_time, prompt_id, voice_id, slots, voice, scenes = 0, 0.0, 0, 0, [], [], []
    timing = []  # collect every scene's timing problem so one conform run reports them all
    words = []  # likewise every calm / blue-light word: one build lists them all (2026-11-04: one fix round, not N)
    for index, sc in enumerate(s["scenes"]):
        phase = sc.get("phase")
        if phase not in PHASES:
            raise Stop(f"Scene {index+1}: invalid phase")
        window = phase == "hook"  # no hook shots; `hook` cuts the window from reviewed body sources
        if not all(sc.get(k) for k in ("id", "title", "change", "voice") + (() if window else ("shots",))):
            raise Stop(f"Scene {index+1}: needs id/title/change/shots/voice")
        if window and sc.get("shots"):
            raise Stop(f"{sc['id']}: this film's intro is cut from reviewed body sources at /doc-edit hook; "
                       "the hook scene has voice only, no shots")
        start, local = cursor, []
        if window:
            ideal_time += float(intro["duration_s"])
            end = frames(ideal_time, fps)
            slot = {"duration_s": float(intro["duration_s"]), "id": "HOOK", "prompt_id": None,
                    "start_f": cursor, "end_f": end, "phase": phase, "scene": sc["id"]}
            local.append(slot)
            slots.append(slot)
            cursor = end
        for sh in [] if window else sc["shots"]:
            d = float(sh.get("duration_s", 0))
            if not math.isfinite(d) or not lo_s <= d <= hi_s:
                raise Stop(f"{sc['id']}: every shot must be {lo_s}–{hi_s} seconds, got {d}")
            ideal_time+=d
            end = frames(ideal_time, fps)
            # Rounding each boundary preserves real frame timing; don't silently add a short filler.
            if not math.floor(lo_s*fps+1e-6) <= end-cursor <= math.ceil(hi_s*fps-1e-6):
                raise Stop(f"{sc['id']}: shot length is outside {lo_s}–{hi_s}s on this frame rate")
            if phase != "hook":
                # Scene-level camera/direction/characters are shot defaults; omitted beats derive from the shot's own
                # fields. Both only shorten the source the agent writes; the prompt still gets four timed beats.
                sh = {**{k: sc[k] for k in ("camera", "direction", "characters", "location") if sc.get(k)}, **sh}
                for k in ("title", "characters", "action", "camera", "direction", "start_state", "end_state", "beats"):
                    if not sh.get(k):
                        raise Stop(f"{sc['id']}: shot requires {k}")
                if len(sh["beats"]) != 4 or any(not isinstance(b,str) or not b.strip() for b in sh["beats"]):
                    raise Stop("Every generated shot needs exactly four action beats.")
                # Derived "opening frame / small movement / hold" beats rendered gentle, near-static clips.
                calm = sorted({m.lower() for b in sh["beats"] for m in CALM.findall(b)})
                if calm:
                    words.append(f"{sc['id']} '{sh['title']}': beats must be fast, continuous action; rewrite without: "
                                 + ", ".join(calm))
                tint = sorted({m.lower() for k in ("location", "camera", "direction") for m in TINT.findall(sh.get(k) or "")}
                              | {m.lower() for b in sh["beats"] for m in TINT.findall(b)})
                if tint:
                    words.append(f"{sc['id']} '{sh['title']}': light words that render a blue grade; use neutral "
                                 "daylight or warm low sun instead of: " + ", ".join(tint))
                # Shared with 1h (prompt_rules): no contact, no silent stare-down, in action / end state / beats.
                touch = sorted({x for t in [sh.get("action"), sh.get("end_state"), *sh["beats"]] if t
                                for x in issues(t) if not x.startswith("motion")})
                if touch:
                    words.append(f"{sc['id']} '{sh['title']}': " + "; ".join(touch))
                if any(c not in chars for c in sh["characters"]):
                    raise Stop(f"Unknown character in {sc['id']}")
                if sh.get("hook_role", "none") not in ROLES:
                    raise Stop("Invalid hook_role")
                intensity=float(sh.get("intensity",0))
                if not math.isfinite(intensity) or not 0<=intensity<=5:
                    raise Stop("Shot intensity must be finite and between 0 and 5")
                prompt_id += 1
            slot = dict(sh, id=f"H{len(local)+1:03d}" if phase == "hook" else f"S{prompt_id:03d}",
                        prompt_id=None if phase == "hook" else prompt_id,
                        start_f=cursor, end_f=end, phase=phase, scene=sc["id"])
            local.append(slot)
            slots.append(slot)
            cursor = end
        if index == 0 and phase != "hook":
            raise Stop("The first scene must be hook.")
        opening = float(intro["duration_s"]) + float(p.get("setup_s", 30))
        if index == 1 and (phase != "setup" or abs(cursor/fps-opening) > 1/fps):
            raise Stop(f"Scene 2 must be the {p.get('setup_s', 30)}-second setup (ending at {opening:g}s).")
        if index == 1 and rules.get("setup_min_intensity") and \
                max(float(x.get("intensity", 0)) for x in local) < rules["setup_min_intensity"]:
            raise Stop(f"{sc['id']}: the setup needs action that changes the situation (a shot with intensity >= "
                       f"{rules['setup_min_intensity']}), not a calm landscape opening")
        if index > 1 and phase in ("hook", "setup"):
            raise Stop("Hook/setup may appear only once at the beginning.")
        if index == len(s["scenes"])-1 and phase != "ending":
            raise Stop("The final scene must be ending.")
        lines = []
        for block in sc["voice"]:
            en, vi = str(block.get("en", "")).strip(), str(block.get("vi", "")).strip()
            if not en or "\n" in en or not vi or "\n" in vi or vi == en or vi.isascii():
                raise Stop(f"{sc['id']}: each voice block needs one English paragraph and full Vietnamese translation.")
            voice_id += 1
            duration = float(durations[voice_id-1]) if durations is not None and voice_id <= len(durations) else len(en.split())*60/wpm
            if not math.isfinite(duration) or duration <= 0:
                raise Stop(f"Invalid voice duration #{voice_id}")
            lines.append(dict(id=voice_id, en=en, vi=vi, duration_f=math.ceil(duration*fps-1e-8), scene=sc["id"]))
        spare = cursor-start-sum(v["duration_f"] for v in lines)
        if spare < len(lines)-1:
            timing.append(f"{sc['id']}: voice {(cursor-start-spare)/fps:.2f}s exceeds picture window {(cursor-start)/fps:.2f}s "
                          f"(needs +{(len(lines)-1-spare)/fps:.2f}s)")
            continue
        lead = min(frames(.3,fps), spare//(len(lines)+1))
        tail = min(frames(.5,fps), spare-lead)
        # Spread remaining time evenly; report/reject long gaps instead of padding a sparse script.
        gaps = [lead] + [0]*(len(lines)-1) + [tail]
        remainder = spare-sum(gaps)
        if len(lines) == 1:
            gaps[-1] += remainder
        else:
            for j in range(1,len(lines)):
                gaps[j] = remainder//(len(lines)-1) + (j <= remainder%(len(lines)-1))
        max_gap = max(gaps)/fps
        limit = float(sc.get("pause_limit_s", 3))
        if limit > 3 and not sc.get("pause_reason"):
            raise Stop(f"{sc['id']}: a longer intentional pause needs pause_reason")
        if limit > 6 or max_gap > limit + 1/fps:
            timing.append(f"{sc['id']}: narrator gap {max_gap:.2f}s exceeds {limit}s (spare {spare/fps:.2f}s)")
            continue
        onset = start + gaps[0]
        for j, v in enumerate(lines):
            v["start_f"], v["end_f"] = onset, onset+v["duration_f"]
            voice.append(v)
            onset = v["end_f"] + gaps[j+1]
        scenes.append(dict(id=sc["id"], title=sc["title"], phase=phase, change=sc["change"],
                           start_f=start, end_f=cursor, voice_ids=[v["id"] for v in lines],
                           shot_ids=[v["id"] for v in local], max_gap_s=max_gap))
    if words:
        raise Stop("\n".join(words))
    cast_leaks(s, slots)
    if timing:
        raise Stop("Voice timing problems; revise timing/source before generating shots; never cut speech:\n" + "\n".join(timing))
    if abs(cursor-frames(target,fps)) > 1:
        raise Stop(f"Picture totals {cursor/fps:.3f}s; target {target:.3f}s. Fix scene lengths.")
    if durations is not None and len(durations) != len(voice):
        raise Stop(f"{len(durations)} audio durations for {len(voice)} voice blocks")
    coverage = sum(v["duration_f"] for v in voice)/cursor
    if not .80 <= coverage <= .98:
        raise Stop(f"Voice-file occupancy {coverage:.1%}; target 80–98%, recommended 85–92%.")
    if len({c["id"] for c in scenes}) != len(scenes):
        raise Stop("Duplicate scene IDs")
    actions=[re.sub(r"\W+"," ",x["action"].lower()).strip() for x in slots if x["prompt_id"]]
    if len(set(actions))!=len(actions):
        raise Stop("Repeated body action descriptions; each generated shot must add a distinct moment")
    body=[x for x in slots if x["prompt_id"]]
    same=[f"{a['id']}/{b['id']}: {a['camera']}" for a,b in zip(body,body[1:]) if a["camera"].strip().lower()==b["camera"].strip().lower()]
    if same:
        raise Stop("Consecutive shots share one camera, so they read as the same scene; give each its own framing:\n"+"\n".join(same))
    if not s.get("synthetic_disclosure"):
        raise Stop("State clearly that this is an AI-generated dramatization.")
    plan = {"schema":2,"source_hash":object_hash(source), "status":"CONFORMED" if durations is not None else "PLANNED",
            "title":s["title"],"fps":fps,"runtime_f":cursor,"voice_occupancy":coverage,
            "slots":slots,"voice":voice,"scenes":scenes,"source":s}
    plan["rules"] = profile  # plans built before 2026-11-04 have no rules: read-only, they finish on their own layout
    return plan


def cast_leaks(source, slots):
    """Every prompt repeats environment + geography + its shot fields; naming an absent character there
    makes generators draw it (e.g. "the Saddle where the herd waits" put the herd into every shot)."""
    pats = {c["id"]: re.compile(r"\b(?:" + "|".join(re.escape(t.strip()) for t in c["terms"]) + r")(?:e?s)?\b", re.I)
            for c in source["characters"]}
    problems = {}
    for sh in slots:
        if not sh["prompt_id"]:
            continue
        fields = {"environment": source["environment"], "geography": source["geography"], "beats": " ".join(sh["beats"]),
                  **{k: sh.get(k) for k in ("camera", "direction", "location", "start_state", "end_state", "action", "cause")}}
        for cid, pat in pats.items():
            if cid in sh["characters"]:
                continue
            for name, text in fields.items():
                if text and (m := pat.search(text)):
                    where = name if name in ("environment", "geography") else f"{sh['id']} ({sh['scene']})"
                    problems.setdefault((where, cid, m[0].lower()), {})[name] = None
    if problems:
        raise Stop("Absent characters named in prompt text. Add the character to that shot's characters if it must be "
                   "visible; otherwise rewrite without naming it (off-screen sound: 'a distant call'). "
                   "Environment/geography are in every prompt, so they must never name a character:\n"
                   + "\n".join(f"{w}: '{t}' names {c} (not in frame) in {', '.join(f)}" for (w, c, t), f in problems.items()))


SNOW = {"alps", "andes", "rockies", "tibet", "generic_snow"}  # v1 mountain regions share the himalaya locks


def region_locks(region="himalaya"):
    """{motion, color} of a region (config.toml [prompts.regions.<region>]); missing -> Stop with the reminder."""
    region = "himalaya" if region in SNOW or not region else region
    locks = config().get("prompts", {}).get("regions", {}).get(region)
    if not locks:
        raise Stop(f"No full-AI prompt locks for region {region!r} yet: write [prompts.regions.{region}] motion + color "
                   "in dvr_cowork/fullai/config.toml before issuing prompts")
    return locks


def prompt_text(plan, shot, region="himalaya"):
    source, fps = plan["source"], plan["fps"]
    d = float(shot["duration_s"])
    cast = [c for c in source["characters"] if c["id"] in shot["characters"]]
    absent = [c for c in source["characters"] if c["id"] not in shot["characters"]]
    total = sum(c["count"] for c in cast)
    p = config().get("prompts", {}) | region_locks(region)
    g = dur_s(d)  # clip length = the slot's next half second (6 -> 6.5, 8.7 -> 9.0), user 2026-11-05
    # Cast first: generators weight early text, and the absent list is the only thing stopping them adding the rest.
    cast_text = "; ".join(c["lock"] + (f" (ABSOLUTE: {c['absolute_lock']})" if c.get("absolute_lock") else "") for c in cast)
    absent_text = ("NOT IN FRAME: " + "; ".join(c["species"] for c in absent) + " — absent from the entire take, "
                   "not in the background or distance, not as silhouettes, shadows or reflections. ") if absent else ""
    # Beats span the whole clip (20/50/70 % ticks): no static hold; the story moment lands by the middle.
    ticks = [round(x * g * 2) / 2 for x in (0, .2, .5, .7, 1)]
    beats = " ".join(f"{ticks[i]:g}-{ticks[i+1]:g}s: {b}." for i, b in enumerate(b.rstrip(". ") for b in shot["beats"]))
    # Generators drift through every place a prompt names, so a shot gets only its own location, never the whole route.
    place = shot.get("location") or source["geography"]
    return (f"{p.get('style', 'Cinematic nature documentary, natural sound, normal motion')}, {GRADE} - "
            f"{g:g}-second 16:9 photorealistic wildlife documentary shot, {shot['camera']}, ONE SINGLE CONTINUOUS TAKE "
            "with no cuts, transitions or change of location or light, of exactly "
            f"{total} animal{'s' * (total > 1)} for the whole take, no more and no fewer: {cast_text}. {absent_text}"
            f"Location: {place} {source['environment']} Screen direction: {shot['direction']}, maintained throughout. "
            f"{p.get('motion', '')} {beats} "
            "Real-time 1x speed for the whole take: no slow motion, no speed ramp, no high-frame-rate look. "
            f"{p['color']} "
            "No captions, place names or subtitles. "
            "No animals beyond those listed, no duplicated individuals, identity or marking changes, "
            "teleportation, direction reversal or camera orbit. " + TAIL)


BIBLE = ("count_lock", "zones", "terrain_lock", "light_lock")
# Said up front in every prompt: generated clips came back in slow motion and with a strong blue cast.
GRADE = "No slow-motion, The video must not have a blue tint"
# Prompt light words that pushed generators into a blue grade ("blue dusk", "cold color", "first stars").
TINT = re.compile(r"\b(?:blue|bluish|cyan|teal|cold colou?r|dusk|twilight|night|moon(?:lit|light)?|stars?)\b", re.I)
# Words that turn a beat into a pose; terrain words like "frozen spring" stay allowed.
CALM = re.compile(r"\b(?:still(?:ness)?|motionless|slow(?:ly|s|er|ing)?|gentl[ey]|careful(?:ly)?|calm(?:ly)?|"
                  r"paus(?:e|es|ing)|wait(?:s|ing)?|rest(?:s|ing)?|settl(?:e|es|ing)|idle|freez(?:e|es|ing)|"
                  r"hold(?:s|ing)? (?:still|position)|small movement)\b", re.I)


def strings(value):
    return isinstance(value, list) and bool(value) and all(isinstance(x, str) and x.strip() for x in value)


def bible(source):
    """Production bible printed above the prompts: the locks a generator project keeps for every shot."""
    out = [f"# Production bible — {source['title']}", "",
           "Keep these locks for every generation. Zone names are for reference only; prompts describe the place, "
           "never print a name on screen.", "", "## 1. CỐ ĐỊNH NHÂN VẬT — CHARACTER LOCK", ""]
    for n, c in enumerate(source["characters"]):
        out += [f"### {chr(65+n)}. {c.get('name') or c['species']} ({c['id']})", "", c["lock"]]
        out += [f"- {d}" for d in c["details"]]
        if c.get("absolute_lock"):
            out += ["", f"**ABSOLUTE LOCK:** {c['absolute_lock']}"]
        out.append("")
    sections = (("2. COUNT LOCK", "count_lock", "-"), ("3. CỐ ĐỊNH MÔI TRƯỜNG — ENVIRONMENT LOCK", "zones", "1."),
                ("4. TERRAIN LOCK", "terrain_lock", "-"), ("5. ÁNH SÁNG — LIGHT LOCK", "light_lock", "-"))
    for title, key, mark in sections:
        out += [f"## {title}", ""] + [f"{i+1}. {x}" if mark == "1." else f"- {x}" for i, x in enumerate(source[key])] + [""]
    return "\n".join(out)


def documents(plan):
    s,fps = plan["source"],plan["fps"]
    tc = lambda f: stamp(f/fps)
    bible = "\n".join(f"- **{c['id']} — {c['species']}**: {c['lock']}" for c in s["characters"])
    base = f"# {s['title']}\n\n{s['synthetic_disclosure']}\n\nRuntime: {tc(plan['runtime_f'])}; {plan['status']}.\n"
    sp = [base, f"Premise: {s['premise']}\n\nCentral question: {s['central_question']}\n\nPayoff: {s['payoff']}",
          "## Character lock\n\n"+bible, "## Environment and geography\n\n"+s["environment"]+"\n\n"+s["geography"]]
    intro = (plan.get("rules") or {}).get("intro")
    opening = ("## Opening\n\n00:00–00:30: five 6s teasers; select actual reviewed climax sources later, withhold the outcome. "
               "00:30–01:00: establish individuals, terrain, route and immediate stakes. No logo animation or 90s intro.\n")
    if intro and intro.get("mode") == "cuts_from_body":
        n = intro.get("preferred_cut_count", [10, 12])
        opening = (f"## Opening\n\n00:00–{tc(plan['slots'][0]['end_f'])}: {n[0]}–{n[1]} cuts of {intro['cut_min_s']:g}–"
                   f"{intro['cut_max_s']:g}s from reviewed body sources (selected at /doc-edit hook, no extra prompts), "
                   "withhold the outcome. Then the setup: individuals, terrain, route and immediate stakes through action. "
                   "No logo animation or 90s intro.\n")
    vp = [base, "## Character lock\n\n"+bible,
          "## Tracks\n\nV1: picture; A1: linked V1 sound throughout the film; A2: Narrator Voice; A3: Music.\n",
          opening,
          "| Slot | Start | End | File | Scene | Action / purpose | Hook role |\n|---|---|---|---|---|---|---|"]
    for sh in plan["slots"]:
        pid = sh["prompt_id"]
        src = f"{pid}.mp4" if pid else ("intro cuts (hook_selection.md)" if sh["id"] == "HOOK" else "reviewed body source")
        vp.append(f"| {sh['id']} | {tc(sh['start_f'])} | {tc(sh['end_f'])} | {src} | "
                  f"{sh['scene']} | {sh.get('action','Tease danger without revealing the resolution')} | {sh.get('hook_role','none')} |")
    transcript=[]
    for sc in plan["scenes"]:
        vv=[v for v in plan["voice"] if v["scene"] == sc["id"]]
        transcript.append("\n".join(v["en"] for v in vv))
        sp += [f"## {sc['id']} · {tc(sc['start_f'])}–{tc(sc['end_f'])} — {sc['title']}",
               f"Change: {sc['change']}", "\n\n".join(v["en"] for v in vv)]
    ts=[base,"## English\n"]+[f"[{tc(v['start_f'])}] {v['en']}" for v in plan["voice"]]
    ts += ["\n## Vietnamese\n"]+[f"[{tc(v['start_f'])}] {v['vi']}" for v in plan["voice"]]
    vp += [f"\nVoice-file occupancy: {plan['voice_occupancy']:.1%}. This measures scheduled audio duration, not detected speech. "
           "Listen to generated files for internal silence. Prompt metadata predicts hook potential; actual images require QC."]
    return dict(zip(OUTPUTS,["\n\n".join(sp)+"\n","\n".join(ts)+"\n","\n\n".join(transcript)+"\n","\n".join(vp)+"\n"]))


def build(video, durations=None, persist=True):
    video=video_path(video)
    source=read_json(prod(video)/"story.json")
    plan=compile_story(source,durations,pinned_profile(video))
    if persist:
        if (prod(video)/"voice_receipt.json").exists():
            old=read_json(prod(video)/"plan.json")
            # Shot wording may change on the placed timeline; any slot or narration frame may not.
            timing=lambda p:([(x["id"],x["start_f"],x["end_f"],x["prompt_id"]) for x in p["slots"]],
                             [(v["id"],v["start_f"],v["end_f"],v["en"]) for v in p["voice"]],p["runtime_f"])
            if timing(old) != timing(plan):
                raise Stop("A2 has already been placed. Do not rebuild/retime a reviewed timeline; create a new project/version.")
        for name,content in documents(plan).items():
            atomic_text(video/"audios"/name,content)
        write_json(prod(video)/"plan.json",plan)
        if durations is None:
            event(video,"WAITING_FOR_VOICE",source_hash=plan["source_hash"])
    return plan


def pinned_profile(video):
    """The film's pinned profile (video.project.json + .production/profile.lock.json), else the workspace one."""
    from ..profile import load, pinned
    return pinned(video)[1] or load("full_ai_mountain")


def load_plan(video, conformed=False):
    p=read_json(prod(video)/"plan.json")
    if object_hash(read_json(prod(video)/"story.json")) != p["source_hash"]:
        raise Stop("story.json changed after build. Rebuild before proceeding.")
    if conformed and p["status"] != "CONFORMED":
        raise Stop("Measure and conform actual numbered MP3 files first.")
    if p.get("rules") is not None and object_hash(p["rules"]) != object_hash(pinned_profile(video)):
        raise Stop("plan.json was built under another profile than the film's pinned snapshot; rebuild (never re-pin silently).")
    expected=documents(p)
    for name,content in expected.items():
        if (video_path(video)/"audios"/name).read_text("utf-8") != content:
            raise Stop(f"{name} differs from canonical source. Update source and rebuild before recording/placing.")
    return p
