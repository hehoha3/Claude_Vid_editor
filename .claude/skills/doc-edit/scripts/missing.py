"""doc-edit: prompts for the THIẾU and WEAK slots of plan.json, to generate the missing / better footage.

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/missing.py <video>                 # list groups
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/missing.py <video> --check         # QC gates + preview
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/missing.py <video> --write         # QC, render prompts
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/missing.py --selftest

List mode groups THIẾU slots by character tag + species + action + setting + light and suggests how many
clips to generate (one generated clip ~CLIP_YIELD s of usable footage, cut into several shots), with the story
sentences of the group and the other characters' footage status in them (coverage: a chase whose hunter is
already OK needs only the prey clips). Claude writes .work/doc_edit/<video>/prompts.txt (user 2026-11-02: Claude, not
Gemini; per video a bank generator in .work/scripts/gen_prompts_<video>.py, one prompt per slot):
    ## G3
    prey_escape L>R | side-on 300mm telephoto pan | <place> | bright daylight   <- one clip = prompt k of the group
    - <what happens, English, one beat>                                         <- beats, untimed (the script times them)
    ## +harpy_eagle                           <- extra group (not a THIẾU slot, e.g. daily life): saved to <AI_DIR>/<name>
Prompt k of a group = slot k of the group (extras = the group's longest slot); clip length dur_s = the slot's next
half second (3.2 -> 3.5, 5 -> 5.5, user 2026-11-05); beats per clip: < 5 s one, < 8 s up to two, else up to four.
--check / --write run the QC gates (references/missing-prompts.md); --write refuses on errors and writes
<video>/missing-prompt.csv: the 19-column missing-scenes schema (prompt_rules.COLUMNS), THIEU rows then WEAK.
"""
import difflib, json, math, re, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".claude" / "skills" / "scan-source" / "scripts"))
from dvr_cowork.config import load_config  # noqa: E402
from scan_source import ROOTS  # noqa: E402
sys.path.insert(0, str(Path(__file__).parent))
from plan import AGE_CAP, KILL, SEX_CAP  # noqa: E402  the story-truth words plan.py checks, same in the prompts
from dvr_cowork.prompt_rules import TAIL, csv_text, dur_s, issues, shot_size  # noqa: E402  shared with full-AI
# where the user saves generated clips, per plan.json region: amazon = AI root of this machine (config.toml);
# africa = D:\AI_video\_africa\_check (user 2026-10-22; organize.py --africa files them into _africa\<species>)
AI_DIR = {"amazon": load_config()["paths"]["ai_video"], "africa": str(ROOTS["africa_ai_check"][0] / "_check"),
          "himalaya": str(Path(load_config()["paths"]["ai_video"]) / "_himalaya" / "_check")}
# prompt format (user 2026-11-05, input/SKILL.md formula): header with the clip's own length + untimed beats; the
# shared TAIL (prompt_rules: moving animals, no stare-down, no contact) closes every prompt. 1h prompts carry no locks.
HEAD = ("Cinematic wildlife documentary, ultra-photorealistic 4K, {s}single continuous shot, 16:9, shot on {cam}, "
        "{place}, {light}.")
BEAT = re.compile(r"-\s+(.+)")
OLD_BEAT = re.compile(r"\d+(?:\.\d+)?-\d+(?:\.\d+)?s:")
MAX_BEATS = ((5, 1), (8, 2), (math.inf, 4))  # clip < 5 s: one readable beat; < 8 s: two; longer: four
CLIP_YIELD = 6.0  # usable seconds per generated clip (10 s clip minus morphing ends, cut into 2-3 shots)
ARROW = {"L>R": "→", "R>L": "←", "away_UR": "away ↗", "away_UL": "away ↖", "toward": "toward camera", "static": ""}
# QC gates (PLAN missing-prompt V2, user 2026-10-13)
ROLES = {"predator_burst", "prey_escape", "relationship_wide", "reaction", "obstacle", "reacquisition", "aftermath",
         "environmental_speed", "action", "establishing", "detail"}
VECS = {"L>R": "left to right", "R>L": "right to left", "away_UR": "away", "away_UL": "away", "toward": "toward",
        "static": None}
OPPOSITE = {"L>R": "right to left", "R>L": "left to right"}
BAD_MOVE = ("reverse", "backward", "turns around", "turning around", "u-turn", "mirrored", "flipped", "teleport",
            "orbit", "slow motion", "slow-motion")
BAD_ENV = ("snow", "alpine", "conifer", "pine", "autumn", "desert", "dust cloud", "dusty")
BAD_ENV_REGION = {"africa": ("snow", "alpine", "conifer", "pine", "autumn")}  # dry, dusty savanna is right there
NO_GAIT = {"sloth": ("run", "sprint", "gallop", "charge"), "snake": ("run", "sprint", "leg", "gallop"),
           "python": ("run", "sprint", "leg", "gallop"), "anaconda": ("run", "sprint", "leg", "gallop"),
           "fish": ("run", "walk", "sprint")}
NEG = re.compile(r"\b(?:no|not|never|without|avoid)\b[^,.;]*", re.I)  # "no reversing, no snow" are fine
# a direction glued to a non-travel verb ("rises left to right", "motionless right to left"): written to pass the
# vector gate, it makes the generator slide a still animal (Gemini draft 2026-11-01); still animal = vector static.
# Gaze is fine ("crouches, watching left to right": eyeline), so look / watch / face / turn are not in the list, and
# the direction must sit in the same clause (no comma between)
STILL_DIR = re.compile(r"\b(?:rises?|rising|crouch\w*|rest\w*|motionless|remains?|stays?|reach\w*|lowers?|lowering|"
                       r"settles?|settling|sits?|sitting|freez\w*|frozen|still|pauses?|listen\w*|lifts?|lifting)\b"
                       r"[^.,;]{0,30}?\b(?:from )?(?:left to right|right to left|away to (?:the )?upper (?:right|left))")
DUP = 0.9  # two prompts of one group this similar = the same shot twice


def groups(slots, status="THIEU", pre="G"):
    g = defaultdict(list)
    for s in slots:
        if s["status"] != status:
            continue
        f = s["filter"]
        tag = re.match(r"\[([^\]]+)\]", s["need"])
        animal = f.get("sp", ["none"]) != ["none"]
        # animals: one group per character + main action (setting comes from the screenplay context);
        # no animal: one group per setting + light
        key = (tag[1] if tag else "-", ",".join(f.get("sp", ["none"])), (f.get("act") or ["-"])[0],
               "" if animal else (f.get("set") or ["-"])[0], "" if animal else (f.get("light") or ["-"])[0])
        g[key].append(s)
    tag_of = lambda s: (re.match(r"\[([^\]]+)\]", s.get("need", "")) or [None, "-"])[1]  # noqa: E731
    out = []
    for i, (k, ss) in enumerate(sorted(g.items(), key=lambda kv: (kv[0][0] == "-", -len(kv[1]))), 1):
        sec = sum(s["dur"] for s in ss)
        lines = sorted({s["line"] for s in ss if "line" in s})
        # coverage: the other characters' footage in the same sentences (hunter OK -> only the prey is missing)
        others = Counter(f"{tag_of(s)}:{s['status']}" for s in slots
                         if s.get("line") in lines and tag_of(s) not in ("-", k[0]))
        # story truth of the slots (plan.py sex= / age= / out=) and what the library offered but the rules refused
        truth = {t: sorted({x for s in ss for x in s["filter"].get(t, [])}) for t in ("sex", "age", "out")}
        refused = sum((Counter(s.get("rej") or {}) for s in ss), Counter())
        out.append({"id": f"{pre}{i}", "status": status, "key": k, "truth": truth, "refused": dict(refused),
                    "slots": [s["slot"] for s in ss], "sec": round(sec, 1),
                    "durs": [s["dur"] for s in ss], "starts": [s.get("start") for s in ss],
                    # one prompt per THIẾU slot (user 2026-10-17: was ceil(sec / CLIP_YIELD); half the clips of a
                    # round fail tagging, so fewer clips left slots empty)
                    "clips": len(ss), "lines": lines, "others": dict(others),
                    "needs": list(dict.fromkeys(s["need"] for s in ss))})
    return out


def lint(species, role, vec, text, truth=None):
    """QC gates of one prompt line; returns the problems (empty = pass). truth = the group's sex / age / out."""
    errs, low = [], text.lower()
    pos = NEG.sub("", low)  # what the prompt asks for, without its "no ..." clauses
    for k, pats in (("sex", SEX_CAP), ("age", AGE_CAP)):
        for v in (truth or {}).get(k, []):
            if not re.search(pats[v], pos):  # the generator must be told: "a lioness", "a newborn calf"
                errs.append(f"truth: {k}={v} but the prompt never names it ({pats[v][4:40]}...)")
    if truth is not None and "kill" not in truth.get("out", []) and KILL.search(pos):
        errs.append(f"truth: '{KILL.search(pos)[0]}' shows an outcome the screenplay does not (no out=kill)")
    if role != "-":  # legacy lines have no role/vector
        if role not in ROLES:
            errs.append(f"role {role!r} not in {sorted(ROLES)}")
        if vec not in VECS:
            errs.append(f"travel vector {vec!r} not in {sorted(VECS)}")
        elif VECS[vec] and VECS[vec] not in low:
            errs.append(f"vector {vec} but the text never says '{VECS[vec]}'")
        if vec in OPPOSITE and OPPOSITE[vec] in pos:
            errs.append(f"vector {vec} contradicted by '{OPPOSITE[vec]}'")
    errs += [f"motion: '{w}'" for w in BAD_MOVE if w in pos]
    errs += [f"vector: '{m[0]}' gives a still action a direction (travel verb, or vector static)"
             for m in STILL_DIR.finditer(pos)]
    errs += [f"biome: '{w}'" for w in BAD_ENV if re.search(rf"\b{w}", pos)]
    for animal, gaits in NO_GAIT.items():
        if animal in species:
            errs += [f"biology: a {animal} does not '{w}'" for w in gaits if re.search(rf"\b{w}", pos)]
    name = species.split(",")[0].replace("_", " ")
    if name not in ("none", "-", "") and name not in low:
        errs.append(f"species '{name}' not named")
    return errs + issues(text)  # shared with 8p: no contact, no stare-down, every animal keeps moving


def slot_of(g, k):
    """Prompt k (0-based) of group g -> (slot, start s, timeline s). Extras beyond the slots: the longest slot."""
    if g and k < len(g["slots"]):
        return g["slots"][k], g["starts"][k], g["durs"][k]
    return None, None, (max(g["durs"]) if g else None)


def max_beats(seconds):
    return 4 if seconds is None else next(n for lim, n in MAX_BEATS if dur_s(seconds) < lim)


def check(p, gs):
    """QC every clip of prompts.txt; returns (errors, warnings)."""
    errs, warns, by = [], [], {g["id"]: g for g in gs}
    for gid, rows in p.items():
        g = by.get(gid)
        sp = gid[1:] if gid.startswith("+") else g["key"][1]
        for n, r in enumerate(rows, 1):
            errs += [f"{gid}#{n}: {e}" for e in lint(sp, r["role"], r["vec"], r["text"], g and g.get("truth"))]
            d = slot_of(g, n - 1)[2]
            if len(r["beats"]) > max_beats(d):
                errs.append(f"{gid}#{n}: {len(r['beats'])} beats for a {dur_s(d):g} s clip (max {max_beats(d)}: "
                            "one readable beat under 5 s, two under 8 s)")
        for a in range(len(rows)):
            for b in range(a + 1, len(rows)):
                if difflib.SequenceMatcher(None, rows[a]["text"], rows[b]["text"]).ratio() >= DUP:
                    errs.append(f"{gid}#{a + 1} and #{b + 1}: near-duplicate prompts, give each a distinct role/framing")
        if g and len(rows) > g["clips"] + 2:
            warns.append(f"{gid}: {len(rows)} prompts for {g['clips']} suggested clips (budget)")
        if sum(r["role"] == "relationship_wide" for r in rows) > 1:
            warns.append(f"{gid}: more than one two-species relationship_wide clip")
    return errs, warns


def render(r, seconds):
    """Full prompt of one clip for a timeline slot of `seconds` (None = unknown length: no number is printed)."""
    d = dur_s(seconds) if seconds else None
    head = HEAD.format(s=f"{d:g}-second " if d else "", cam=r["cam"], place=r["place"], light=r["light"])
    beats = [b.rstrip(". ") + "." for b in r["beats"]]
    if d and len(beats) >= 3:  # long clips only: timed beats across the whole clip, no static hold
        ticks = [round(x * d * 2) / 2 for x in ([0, .3, .7, 1] if len(beats) == 3 else [0, .2, .5, .7, 1])]
        beats = [f"{ticks[i]:g}-{ticks[i + 1]:g}s: {b}" for i, b in enumerate(beats)]
    return " ".join([head] + beats + [TAIL])


def parse_prompts(text):
    """prompts.txt -> {group: [clip]}; clip = role, vec, cam, place, light, beats and `text` (what the gates read:
    camera + place + light + beats, without the fixed header / tail). One clip = 'role vec | camera | place | light'
    and its beat lines '- ...'; the script times the beats to the slot's clip length."""
    p, cur, clip, errs = defaultdict(list), None, None, []

    def close():
        if clip:
            if not clip["beats"]:
                errs.append(f"prompts line {clip['line']}: a clip needs at least one '- ' beat")
            clip["text"] = " ".join([clip["cam"], clip["place"], clip["light"]] + clip["beats"])
            p[cur].append(clip)

    for n, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if s.startswith("## "):
            close(); clip = None
            cur = s[3:].strip()
        elif s and not s.startswith("#"):
            if not cur:
                errs.append(f"prompts line {n}: text before any '## G<n>' header"); continue
            if OLD_BEAT.match(s):
                errs.append(f"prompts line {n}: timed beat; write '- <beat>' (the script times beats to the slot)"); continue
            if m := BEAT.match(s):
                if clip:
                    clip["beats"].append(m[1].strip())
                else:
                    errs.append(f"prompts line {n}: beat before its 'role vec | camera | place | light' line")
                continue
            f = [x.strip() for x in s.split("|")]
            rv = f[0].split()
            if len(f) != 4 or len(rv) != 2 or not all(f):
                errs.append(f"prompts line {n}: need 'role vec | camera | place | light' (or a beat '- ...')"); continue
            if f[1].lower().startswith(("photorealistic", "cinematic")):
                errs.append(f"prompts line {n}: write only the camera, the fixed header is added"); continue
            close()
            clip = {"line": n, "role": rv[0], "vec": rv[1], "cam": f[1], "place": f[2], "light": f[3], "beats": []}
    close()
    assert not errs, "\n".join(errs)
    return p


def tc(s):
    return f"{int(s // 60):02d}:{s % 60:04.1f}"


def secs(t):
    m, _, s = t.rpartition(":")
    return int(m or 0) * 60 + float(s)


def main(video, mode, rng=None):
    global BAD_ENV
    from dvr_cowork.videokey import video_key
    work = ROOT / ".work" / "doc_edit" / video_key(video)
    plan = json.loads((work / "plan.json").read_text("utf-8"))
    slots = plan["slots"]
    region = plan.get("region", "amazon")  # plans before 2026-10-20 have no region: amazon
    AI, BAD_ENV = AI_DIR[region], BAD_ENV_REGION.get(region, BAD_ENV)
    if rng:  # --range=0:00-6:30: only THIẾU slots starting inside it (user asks per part of the film)
        a, b = (secs(x) for x in rng.split("-"))
        slots = [s for s in slots if a <= s.get("start", 0) < b]
    gs = groups(slots) + groups(slots, "WEAK", "W")  # always both parts (user 2026-10-27): G<n> THIẾU, W<n> WEAK
    at = {s["slot"]: s.get("start", 0) for s in slots}
    if mode == "list":
        for st in ("THIEU", "WEAK"):
            gg = [g for g in gs if g["status"] == st]
            print(f"{sum(len(g['slots']) for g in gg)} {st} slots, {sum(g['sec'] for g in gg):.0f}s -> "
                  f"{len(gg)} groups, {sum(g['clips'] for g in gg)} clips suggested")
        for g in gs:
            tag, sp, act, st, li = g["key"]
            print(f"{g['id']} [{tag}] sp={sp} act={act or '-'} set={st or '-'} light={li or '-'} | "
                  f"{len(g['slots'])} slots {g['sec']}s -> {g['clips']} clips | ## {','.join(map(str, g['lines']))} | "
                  f"others there: {g['others'] or '-'} | "
                  + "truth " + (" ".join(f"{t}={','.join(v)}" for t, v in g["truth"].items() if v) or "-")
                  + (f" | refused in library: {g['refused']}" if g["refused"] else "") + " | " + " / ".join(g["needs"][:4]))
            print("   at " + " ".join(tc(at[n]) for n in g["slots"]))
        return
    p = parse_prompts((work / "prompts.txt").read_text("utf-8"))
    ids = {g["id"] for g in gs}
    extra = [k for k in p if k.startswith("+")]
    assert set(p) - set(extra) <= ids, f"unknown groups in prompts.txt: {sorted(set(p) - set(extra) - ids)}"
    errs, warns = check(p, gs)
    by = {g["id"]: g for g in gs}
    for gid, rows in p.items():  # preview for the user's review, grouped by event
        g = by.get(gid)
        print(f"{gid} " + (f"[{g['key'][0]}] {g['key'][1]} ## {','.join(map(str, g['lines']))}" if g else gid[1:])
              + f" — {len(rows)} prompts: " + ", ".join(f"{r['role']} {r['vec']}" for r in rows))
    print("\n".join(["QC warnings:"] + warns) if warns else "QC warnings: none")
    if errs:
        raise SystemExit(f"{len(errs)} QC errors (fix prompts.txt, re-run):\n" + "\n".join(errs))
    print("QC: pass")
    if mode == "check":
        return
    missing = [g["id"] for g in gs if g["id"] not in p]
    sys.path.insert(0, str(Path(__file__).parent))
    import ledger  # video folder looked up in the workspaces (plan.json may hold a path from before a rename)
    vdir = Path(plan.get("video_dir", ""))  # plan.json knows the exact folder (same video name in two workspaces)
    out = (vdir if vdir.is_dir() else ledger.find_video(video)) / "missing-prompt.csv"
    # one row per prompt (user 2026-11-05): THIEU groups, extras, then WEAK; the 19-column missing-scenes schema
    order = [g["id"] for g in gs if g["status"] == "THIEU" and g["id"] in p] + extra \
        + [g["id"] for g in gs if g["status"] == "WEAK" and g["id"] in p]
    need = {s["slot"]: s for s in slots}
    table = []
    for gid in order:
        g = by.get(gid)
        sp = g["key"][1] if g else gid[1:]
        name = sp.split(",")[0].replace("_", " ")
        for k, r in enumerate(p[gid]):
            slot, start, sec = slot_of(g, k)
            refused = ", ".join(f"{a} {b}" for a, b in (g or {}).get("refused", {}).items())
            table.append({
                "shot_id": f"{gid}-S{slot:03d}" if slot else f"{gid}-X{k + 1}", "cluster": gid,
                "tc_in": tc(start) if slot else "", "tc_out": tc(start + sec) if slot else "",
                "dur_s": dur_s(sec) if sec else "", "kind": "ai_generated",
                "animal": "" if name == "none" else name, "action": r["role"], "environment": r["place"],
                "time_of_day": r["light"], "shot_size": shot_size(r["cam"]), "camera_angle": r["cam"],
                "direction": ARROW.get(r["vec"], r["vec"]),
                "mo_ta": need[slot]["need"] if slot else " / ".join((g or {}).get("needs", [])[:2]),
                "search_keywords": " ".join(x for x in (name if name != "none" else "landscape", r["role"],
                                                        (g["key"][2] if g else ""), shot_size(r["cam"]), r["light"]) if x and x != "-"),
                "generation_prompt": render(r, sec),
                "reason": ("THIẾU: không có trong kho" if not g or g["status"] == "THIEU" else "WEAK: clip trong kho chưa đạt")
                          + (f" (kho bị loại: {refused})" if refused else "")})
    out.write_text(csv_text(table), "utf-8", newline="")
    print(f"{len(table)} prompts in {len(p)} groups -> {out}")
    for g in gs:
        if g["id"] in p:
            sp = g["key"][1]
            name = "landscape" if sp == "none" else sp.split(",")[0].replace(" ", "_")
            # africa: flat into _africa\_check, organize.py --africa files them into _africa\<species> after tagging
            print(f"  {g['id']} {len(p[g['id']])} clips -> " + (f"{AI} (species {name})" if region == "africa" else f"{AI}\\{name}"))
    for k in extra:
        print(f"  {k} {len(p[k])} clips -> {AI}\\{k[1:]}")
    print("groups without prompts:", missing)


def selftest():
    sl = [{"slot": 1, "status": "THIEU", "dur": 3.0, "need": "[C] Mèo lao", "filter": {"sp": ["golden cat"], "act": ["run"]}},
          {"slot": 2, "status": "THIEU", "dur": 4.0, "need": "[C] Mèo chạy", "filter": {"sp": ["golden cat"], "act": ["run"]}},
          {"slot": 3, "status": "OK", "dur": 2.0, "need": "x", "filter": {}},
          {"slot": 4, "status": "THIEU", "dur": 2.5, "need": "Tán rừng", "filter": {"sp": ["none"], "set": ["canopy"]}}]
    g = groups(sl)
    assert [x["slots"] for x in g] == [[1, 2], [4]] and g[0]["clips"] == 2 and g[1]["key"][0] == "-"
    p = parse_prompts("## G1\naction L>R | long lens | dry savanna | bright daylight\n- A golden cat trots left to right.\n"
                      "action R>L | drone | dry savanna | dusk\n- x\n- y\n## G2\n"
                      "establishing static | drone | canopy | dawn\n- Mist rolls over the canopy.\n")
    assert len(p["G1"]) == 2 and (p["G2"][0]["role"], p["G2"][0]["vec"]) == ("establishing", "static")
    assert render(p["G1"][0], 3.2) == ("Cinematic wildlife documentary, ultra-photorealistic 4K, 3.5-second single "
                                       "continuous shot, 16:9, shot on long lens, dry savanna, bright daylight. "
                                       "A golden cat trots left to right. " + TAIL), render(p["G1"][0], 3.2)
    assert "5.5-second" in render(p["G1"][0], 5) and "-second" not in render(p["G1"][0], None)
    four = dict(p["G1"][1], beats=["a", "b", "c", "d"])
    assert "0-2s: a. 2-5s: b. 5-6.5s: c. 6.5-9.5s: d." in render(four, 9), render(four, 9)  # 9 s slot -> 9.5 s clip
    g1 = {"id": "G1", "key": ("C", "golden cat", "run", "", ""), "clips": 2, "lines": [1], "slots": [1, 2],
          "durs": [3.2, 9.0], "starts": [0, 3.2]}
    assert slot_of(g1, 1) == (2, 3.2, 9.0) and slot_of(g1, 2) == (None, None, 9.0)
    e, _ = check({"G1": [dict(p["G1"][1], text=p["G1"][1]["text"] + " golden cat")]}, [g1])
    assert any("2 beats for a 3.5 s clip" in x for x in e), e   # prompt 1 sits on the 3.2 s slot: one beat only
    for bad in ("## G1\nCinematic nature documentary, BBC Earth style - x\n",                          # old one-line prompt
                "## G1\naction L>R | Photorealistic wildlife | x | y\n- a\n",                          # header written by hand
                "## G1\naction L>R | lens | x | y\n0-2s: a\n2-10s: b\n",                               # old timed beats
                "## G1\naction L>R | lens | x | y\n",                                                  # clip without a beat
                "## G1\n- a\n"):                                                                       # beat without a clip
        try:
            parse_prompts(bad); raise SystemExit(f"accepted {bad!r}")
        except AssertionError:
            pass
    # coverage: the other character's status in the same sentence
    cov = groups([{"slot": 1, "line": 5, "status": "THIEU", "dur": 3, "need": "[P] heo chạy", "filter": {"sp": ["peccary"], "act": ["run"]}},
                  {"slot": 2, "line": 5, "status": "OK", "dur": 3, "need": "[J] báo lao", "filter": {"sp": ["jaguar"]}}])
    assert cov[0]["lines"] == [5] and cov[0]["others"] == {"J:OK": 1}
    good = ("A single jaguar explodes into a full-speed sprint along a muddy rainforest corridor, running left to right; "
            "distant high-oblique telephoto camera pans hard, no reversing, no snow, no slow motion")
    assert lint("jaguar", "predator_burst", "L>R", good) == []
    bad = [("jaguar", "predator_burst", "L>R", "A single jaguar runs right to left"),           # vector never stated / contradicted
           ("jaguar", "chase", "L>R", good),                                                    # unknown role
           ("jaguar", "predator_burst", "L>R", good + ", then turns around"),                   # reversal
           ("jaguar", "predator_burst", "L>R", good + ", snow on the ground"),                  # biome
           ("sloth", "action", "L>R", "A single sloth sprints left to right along a branch"),   # biology
           ("jaguar", "predator_burst", "L>R", "A single ocelot runs left to right")]           # wrong species
    bad += [("agouti", "action", "L>R", "A single agouti rises onto its hind legs from left to right to listen"),
            ("agouti", "action", "R>L", "A single agouti walks right to left, then remains crouched and motionless right to left")]
    for a in bad:
        assert lint(*a), f"lint passed {a}"
    assert lint("agouti", "action", "L>R", "A single agouti trots left to right, stops short and listens, ears "
                "swivelling") == []  # a direction on the travel verb, the stop without one: fine
    # shared rules (user 2026-11-05): no contact, no silent stare-down, every animal keeps moving
    assert any(x.startswith("contact") for x in lint("lion", "action", "L>R", "A single lion leaps left to right and bites the zebra"))
    assert any(x.startswith("stare") for x in lint("lion", "action", "static", "A single lion and a hyena stare at each other"))
    assert any(x.startswith("motion") for x in lint("lion", "action", "static", "A single lion stands still in the grass"))
    assert lint(*good_args) == [] if (good_args := ("jaguar", "predator_burst", "L>R", good)) else 0
    # story truth: a lioness / calf group must name them; no kill unless out=kill; slot refusals summed per group
    tr = {"sex": ["female"], "age": [], "out": []}
    ln = "A single adult lioness crouches low in tall grass, watching left to right"
    assert lint("lion", "action", "L>R", ln, tr) == []
    assert lint("lion", "action", "L>R", ln.replace("adult lioness", "lion"), tr)[0].startswith("truth: sex=female")
    assert any("outcome" in x for x in lint("lion", "action", "L>R", ln + ", then catches a calf", tr))
    assert lint("lion", "action", "L>R", ln + ", then catches a calf", dict(tr, out=["kill"])) == []
    gt = groups([{"slot": 1, "status": "THIEU", "dur": 3, "need": "[L] x", "filter": {"sp": ["lion"], "sex": ["female"]}, "rej": {"sex": 4}},
                 {"slot": 2, "status": "THIEU", "dur": 3, "need": "[L] y", "filter": {"sp": ["lion"]}, "rej": {"sex": 1, "kill": 2}}])
    assert gt[0]["truth"]["sex"] == ["female"] and gt[0]["refused"] == {"sex": 5, "kill": 2}, gt
    clip = lambda t: {"role": "predator_burst", "vec": "L>R", "text": t, "beats": ["x"]}  # noqa: E731
    e, _ = check({"G1": [clip(good), clip(good + ".")]},
                 [{"id": "G1", "key": ("J", "jaguar", "run", "", ""), "clips": 2, "lines": [1], "slots": [1],
                   "durs": [4.0], "starts": [0]}])
    assert any("near-duplicate" in x for x in e)
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    rng = next((x[8:] for x in sys.argv if x.startswith("--range=")), None)
    if "--selftest" in sys.argv:
        selftest()
    else:
        main(a[0], "write" if "--write" in sys.argv else "check" if "--check" in sys.argv else "list", rng)
