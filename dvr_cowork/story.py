"""One canonical authoring source -> four Markdown files + deterministic shot IDs."""
from __future__ import annotations

import copy
import math
import re
from .core import Stop, atomic_text, event, frames, object_hash, prod, read_json, stamp, video_path, write_json

OUTPUTS = ("screenplay.md", "timestamp.md", "transcript.md", "visual_plan.md")
PHASES = {"hook", "setup", "story", "ending"}
ROLES = {"threat", "vulnerability", "pursuit", "obstacle", "unanswered", "none"}


def compile_story(source, durations=None):
    s = copy.deepcopy(source)
    required = ("title", "premise", "central_question", "payoff", "characters", "environment", "geography", "scenes")
    for key in required:
        if not s.get(key):
            raise Stop(f"Story source requires {key}")
    fps, target = float(s.get("fps", 24)), float(s.get("target_minutes", 8)) * 60
    if not 1 <= fps <= 120 or not math.isfinite(target) or target < 480:
        raise Stop("Use a valid frame rate and target_minutes >= 8 (8/11 or longer).")
    if len(s["characters"]) < 2 or any(not all(c.get(k) for k in ("id", "species", "lock")) for c in s["characters"]):
        raise Stop("Define at least two central roles with id, species and complete visual lock.")
    chars = {c["id"]: c for c in s["characters"]}
    if len(chars) != len(s["characters"]):
        raise Stop("Duplicate character IDs")
    wpm = float(s.get("wpm", 145))
    if not 120 <= wpm <= 180:
        raise Stop("wpm must be 120–180; default 145, calibrate to your actual voice.")
    cursor, ideal_time, prompt_id, voice_id, slots, voice, scenes = 0, 0.0, 0, 0, [], [], []
    for index, sc in enumerate(s["scenes"]):
        phase = sc.get("phase")
        if phase not in PHASES:
            raise Stop(f"Scene {index+1}: invalid phase")
        if not all(sc.get(k) for k in ("id", "title", "change", "shots", "voice")):
            raise Stop(f"Scene {index+1}: needs id/title/change/shots/voice")
        start, local = cursor, []
        for sh in sc["shots"]:
            d = float(sh.get("duration_s", 0))
            if not math.isfinite(d) or not 6 <= d <= 9:
                raise Stop(f"{sc['id']}: every shot must be 6–9 seconds, got {d}")
            ideal_time+=d
            end = frames(ideal_time, fps)
            # Rounding each boundary preserves real frame timing; don't silently add a short filler.
            if not math.floor(6*fps+1e-6) <= end-cursor <= math.ceil(9*fps-1e-6):
                raise Stop(f"{sc['id']}: shot length is outside 6–9s on this frame rate")
            if phase != "hook":
                # Scene-level camera/direction/characters are shot defaults; omitted beats derive from the shot's own
                # fields. Both only shorten the source the agent writes; the prompt still gets four timed beats.
                sh = {**{k: sc[k] for k in ("camera", "direction", "characters") if sc.get(k)}, **sh}
                if not sh.get("beats") and sh.get("action"):
                    sh["beats"] = ["Establish the start state; terrain and every listed animal readable",
                                   sh.get("cause") or "Small natural motion builds tension toward the action",
                                   sh["action"], "Settle into the end state and hold"]
                for k in ("characters", "action", "camera", "direction", "start_state", "end_state", "beats"):
                    if not sh.get(k):
                        raise Stop(f"{sc['id']}: shot requires {k}")
                if len(sh["beats"]) != 4 or any(not isinstance(b,str) or not b.strip() for b in sh["beats"]):
                    raise Stop("Every generated shot needs exactly four action beats.")
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
        if phase == "hook" and (index != 0 or len(local) != 5 or any(abs((x["end_f"]-x["start_f"])/fps-6)>1/fps for x in local)):
            raise Stop("Opening hook must be five 6-second slots (00:00–00:30).")
        if index == 0 and phase != "hook":
            raise Stop("The first scene must be hook.")
        if index == 1 and (phase != "setup" or abs(cursor/fps-60) > 1/fps):
            raise Stop("Scene 2 must be the 30-second setup (00:30–01:00).")
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
            raise Stop(f"{sc['id']}: voice exceeds its picture window; revise timing/source before generating shots. Never cut speech.")
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
            raise Stop(f"{sc['id']}: narrator gap {max_gap:.2f}s exceeds {limit}s; add meaningful narration or re-time.")
        onset = start + gaps[0]
        for j, v in enumerate(lines):
            v["start_f"], v["end_f"] = onset, onset+v["duration_f"]
            voice.append(v)
            onset = v["end_f"] + gaps[j+1]
        scenes.append(dict(id=sc["id"], title=sc["title"], phase=phase, change=sc["change"],
                           start_f=start, end_f=cursor, voice_ids=[v["id"] for v in lines],
                           shot_ids=[v["id"] for v in local], max_gap_s=max_gap))
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
    if not s.get("synthetic_disclosure"):
        raise Stop("State clearly that this is an AI-generated dramatization.")
    return {"schema":2,"source_hash":object_hash(source), "status":"CONFORMED" if durations is not None else "PLANNED",
            "title":s["title"],"fps":fps,"runtime_f":cursor,"voice_occupancy":coverage,
            "slots":slots,"voice":voice,"scenes":scenes,"source":s}


def prompt_text(plan, shot):
    source, fps = plan["source"], plan["fps"]
    d = float(shot["duration_s"])
    chars = {c["id"]:c for c in source["characters"]}
    lock = "; ".join(chars[c]["lock"] for c in shot["characters"])
    ticks = [0,.2*d,.5*d,.7*d,d]
    beats = " ".join(f"{ticks[i]:.2f}–{ticks[i+1]:.2f}s: {b}" for i,b in enumerate(shot["beats"]))
    return (f"Photorealistic AI wildlife documentary, {d:.3f} seconds, 16:9. "
            f"{source['environment']} {source['geography']} Character lock: {lock}. "
            f"Camera: {shot['camera']}. Screen direction: {shot['direction']}, maintained throughout. "
            f"Start state: {shot['start_state']}. {beats} End state: {shot['end_state']}. "
            "One continuous take, realistic anatomy and normal motion. Natural location sound only. "
            "No narrator, music, text, subtitles, logos, watermark, blood or gore. "
            "No extra animals, identity changes, teleportation, direction reversal or camera orbit.")


def documents(plan):
    s,fps = plan["source"],plan["fps"]
    tc = lambda f: stamp(f/fps)
    bible = "\n".join(f"- **{c['id']} — {c['species']}**: {c['lock']}" for c in s["characters"])
    base = f"# {s['title']}\n\n{s['synthetic_disclosure']}\n\nRuntime: {tc(plan['runtime_f'])}; {plan['status']}.\n"
    sp = [base, f"Premise: {s['premise']}\n\nCentral question: {s['central_question']}\n\nPayoff: {s['payoff']}",
          "## Character lock\n\n"+bible, "## Environment and geography\n\n"+s["environment"]+"\n\n"+s["geography"]]
    vp = [base, "## Character lock\n\n"+bible,
          "## Tracks\n\nV1: picture; A1: linked V1 sound throughout the film; A2: Narrator Voice; A3: Music.\n",
          "## Opening\n\n00:00–00:30: five 6s teasers; select actual reviewed climax sources later, withhold the outcome. "
          "00:30–01:00: establish individuals, terrain, route and immediate stakes. No logo animation or 90s intro.\n",
          "| Slot | Start | End | File | Scene | Action / purpose | Hook role |\n|---|---|---|---|---|---|---|"]
    for sh in plan["slots"]:
        pid = sh["prompt_id"]
        vp.append(f"| {sh['id']} | {tc(sh['start_f'])} | {tc(sh['end_f'])} | {str(pid)+'.mp4' if pid else 'reviewed body source'} | "
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
    plan=compile_story(source,durations)
    if persist:
        if (prod(video)/"voice_receipt.json").exists():
            old=read_json(prod(video)/"plan.json")
            if object_hash(old) != object_hash(plan):
                raise Stop("A2 has already been placed. Do not rebuild/retime a reviewed timeline; create a new project/version.")
        for name,content in documents(plan).items():
            atomic_text(video/"audios"/name,content)
        write_json(prod(video)/"plan.json",plan)
        if durations is None:
            event(video,"WAITING_FOR_VOICE",source_hash=plan["source_hash"])
    return plan


def load_plan(video, conformed=False):
    p=read_json(prod(video)/"plan.json")
    if object_hash(read_json(prod(video)/"story.json")) != p["source_hash"]:
        raise Stop("story.json changed after build. Rebuild before proceeding.")
    if conformed and p["status"] != "CONFORMED":
        raise Stop("Measure and conform actual numbered MP3 files first.")
    expected=documents(p)
    for name,content in expected.items():
        if (video_path(video)/"audios"/name).read_text("utf-8") != content:
            raise Stop(f"{name} differs from canonical source. Update source and rebuild before recording/placing.")
    return p
