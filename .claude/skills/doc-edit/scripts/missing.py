"""doc-edit: prompts for the THIẾU and WEAK slots of plan.json, to generate the missing / better footage.

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/missing.py <video>                 # list groups
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/missing.py <video> --check         # QC gates + preview
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/missing.py <video> --write         # QC, render prompts
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/missing.py --selftest

List mode groups THIẾU slots by character tag + species + action + setting + light and suggests how many
clips to generate (one generated clip ~CLIP_YIELD s of usable footage, cut into several shots), with the story
sentences of the group and the other characters' footage status in them (coverage: a chase whose hunter is
already OK needs only the prey clips). Claude writes .work/doc_edit/<video>/prompts.txt:
    ## G3
    prey_escape L>R | long telephoto lens with natural handheld tracking | <place> | bright daylight   <- one clip
    0-2s: <what happens, English>          <- beats, contiguous 0..CLIP_S s
    2-5s: ...
    ## +harpy_eagle                           <- extra group (not a THIẾU slot, e.g. daily life): saved to <AI_DIR>/<name>
--check / --write run the QC gates (references/missing-prompts.md); --write refuses on errors, writes HEAD + beats as
numbered prompts '1. ', '2. ' into <video>/missing_prompts.txt under '## THIEU' then '## WEAK' (G<n> / W<n> groups) and
.work/doc_edit/<video>/shot_manifest.csv (row n = prompt n).
"""
import csv, difflib, json, math, re, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".claude" / "skills" / "scan-source" / "scripts"))
from dvr_cowork.config import load_config  # noqa: E402
from scan_source import ROOTS  # noqa: E402
sys.path.insert(0, str(Path(__file__).parent))
from plan import AGE_CAP, KILL, SEX_CAP  # noqa: E402  the story-truth words plan.py checks, same in the prompts
# where the user saves generated clips, per plan.json region: amazon = AI root of this machine (config.toml);
# africa = D:\AI_video\_africa\_check (user 2026-10-22; organize.py --africa files them into _africa\<species>)
AI_DIR = {"amazon": load_config()["paths"]["ai_video"], "africa": str(ROOTS["africa_ai_check"][0] / "_check")}
# prompt format (user 2026-10-22): numbered '1. ' header paragraph + timed beats '0-2s: ...' covering 0..CLIP_S
CLIP_S = 10
HEAD = ("Photorealistic wildlife documentary video, {s} seconds, 16:9, shot on {cam}, {place}, {light}, "
        "National Geographic style, real animal anatomy and motion, no blood, no gore.")
BEAT = re.compile(r"(\d+)-(\d+)s:\s*(.+)")
CLIP_YIELD = 6.0  # usable seconds per generated clip (10 s clip minus morphing ends, cut into 2-3 shots)
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
    errs += [f"biome: '{w}'" for w in BAD_ENV if re.search(rf"\b{w}", pos)]
    for animal, gaits in NO_GAIT.items():
        if animal in species:
            errs += [f"biology: a {animal} does not '{w}'" for w in gaits if re.search(rf"\b{w}", pos)]
    name = species.split(",")[0].replace("_", " ")
    if name not in ("none", "-", "") and name not in low:
        errs.append(f"species '{name}' not named")
    return errs


def check(p, gs):
    """QC every line of prompts.txt; returns (errors, warnings)."""
    errs, warns, by = [], [], {g["id"]: g for g in gs}
    for gid, rows in p.items():
        g = by.get(gid)
        sp = gid[1:] if gid.startswith("+") else g["key"][1]
        for n, (role, vec, text) in enumerate(rows, 1):
            errs += [f"{gid}#{n}: {e}" for e in lint(sp, role, vec, text, g and g.get("truth"))]
        for a in range(len(rows)):
            for b in range(a + 1, len(rows)):
                if difflib.SequenceMatcher(None, rows[a][2], rows[b][2]).ratio() >= DUP:
                    errs.append(f"{gid}#{a + 1} and #{b + 1}: near-duplicate prompts, give each a distinct role/framing")
        if g and len(rows) > g["clips"] + 2:
            warns.append(f"{gid}: {len(rows)} prompts for {g['clips']} suggested clips (budget)")
        if sum(r[0] == "relationship_wide" for r in rows) > 1:
            warns.append(f"{gid}: more than one two-species relationship_wide clip")
    return errs, warns


def parse_prompts(text):
    """prompts.txt -> {group: [(role, vec, full prompt text)]}. One clip = 'role vec | camera | place | light' and its
    beat lines 'a-bs: ...' (contiguous, 0 .. CLIP_S); the script writes the fixed HEAD around camera / place / light."""
    p, cur, clip, errs = defaultdict(list), None, None, []

    def close():
        if clip:
            n, role, vec, head, beats = clip
            t = [(int(a), int(b)) for a, b, _ in beats]
            if len(t) < 2 or t[0][0] != 0 or t[-1][1] != CLIP_S or any(a >= b for a, b in t) \
                    or any(x[1] != y[0] for x, y in zip(t, t[1:])):
                errs.append(f"prompts line {n}: beats {[f'{a}-{b}s' for a, b in t]} must be 2+ beats running 0-{CLIP_S}s without gaps")
            p[cur].append((role, vec, "\n\n".join([head] + [f"{a}-{b}s: {x.strip()}" for a, b, x in beats])))

    for n, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if s.startswith("## "):
            close(); clip = None
            cur = s[3:].strip()
        elif s and not s.startswith("#"):
            if not cur:
                errs.append(f"prompts line {n}: text before any '## G<n>' header"); continue
            if m := BEAT.match(s):
                if clip:
                    clip[4].append(m.groups())
                else:
                    errs.append(f"prompts line {n}: beat before its 'role vec | camera | place | light' line")
                continue
            f = [x.strip() for x in s.split("|")]
            rv = f[0].split()
            if len(f) != 4 or len(rv) != 2 or not all(f):
                errs.append(f"prompts line {n}: need 'role vec | camera | place | light' (or a beat 'a-bs: ...')"); continue
            if f[1].lower().startswith(("photorealistic", "cinematic")):
                errs.append(f"prompts line {n}: write only the camera, the fixed header is added"); continue
            close()
            clip = (n, rv[0], rv[1], HEAD.format(s=CLIP_S, cam=f[1], place=f[2], light=f[3]), [])
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
    work = ROOT / ".work" / "doc_edit" / video
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
              + f" — {len(rows)} prompts: " + ", ".join(f"{r} {v}" for r, v, _ in rows))
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
    out = (vdir if vdir.is_dir() else ledger.find_video(video)) / "missing_prompts.txt"
    # headers "## THIEU" / "## WEAK" always (user 2026-10-27; extras count as THIEU), numbering '1. ' runs on
    part = {st: [x[2] for g in gs if g["status"] == st and g["id"] in p for x in p[g["id"]]] for st in ("THIEU", "WEAK")}
    part["THIEU"] += [x[2] for k in extra for x in p[k]]
    lines, n, blocks = part["THIEU"] + part["WEAK"], 0, []
    for name, ts in part.items():
        blocks.append(f"## {name}\n\n" + ("\n\n".join(f"{n + i}. {t}" for i, t in enumerate(ts, 1)) or "(none)"))
        n += len(ts)
    out.write_text("\n\n".join(blocks) + "\n", "utf-8")
    # manifest: row n = prompt line n of missing_prompts.txt (same order as the loop above)
    rows = [(gid, r) for g in gs if g["id"] in p for gid, r in [(g["id"], x) for x in p[g["id"]]]] \
        + [(k, x) for k in extra for x in p[k]]
    rows = [r for r in rows if r[0][0] != "W"] + [r for r in rows if r[0][0] == "W"]  # file order: THIEU, then WEAK
    assert len(rows) == len(lines)
    with open(work / "shot_manifest.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["line", "group", "shot_role", "travel_vector", "species", "save_folder", "slots", "sentences",
                    "seconds_needed", "needs", "prompt"])
        for n, (gid, (role, vec, text)) in enumerate(rows, 1):
            g = by.get(gid)
            sp = g["key"][1] if g else gid[1:]
            w.writerow([n, gid, role, vec, sp, "landscape" if sp == "none" else sp.split(",")[0].replace(" ", "_"),
                        " ".join(map(str, g["slots"])) if g else "", " ".join(map(str, g["lines"])) if g else "",
                        g["sec"] if g else "", " / ".join(g["needs"][:6]) if g else "", text])
    print(f"{len(lines)} prompts in {len(p)} groups -> {out}\nmanifest -> {work / 'shot_manifest.csv'}")
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
    p = parse_prompts("## G1\naction L>R | long lens | dry savanna | bright daylight\n0-4s: A golden cat walks left to right.\n"
                      "4-10s: It stops.\naction R>L | drone | dry savanna | dusk\n0-3s: x\n3-10s: y\n## G2\n"
                      "establishing static | drone | canopy | dawn\n0-5s: Mist.\n5-10s: Sun.\n")
    assert len(p["G1"]) == 2 and p["G2"][0][:2] == ("establishing", "static")
    assert p["G1"][0][2] == ("Photorealistic wildlife documentary video, 10 seconds, 16:9, shot on long lens, dry savanna, "
                             "bright daylight, National Geographic style, real animal anatomy and motion, no blood, no gore."
                             "\n\n0-4s: A golden cat walks left to right.\n\n4-10s: It stops."), p["G1"][0][2]
    for bad in ("## G1\nCinematic nature documentary, BBC Earth style - x\n",                          # old one-line prompt
                "## G1\naction L>R | Photorealistic wildlife | x | y\n0-10s: a\n",                     # header written by hand
                "## G1\naction L>R | lens | x | y\n0-2s: a\n3-10s: b\n",                               # gap in the beats
                "## G1\naction L>R | lens | x | y\n0-2s: a\n2-8s: b\n",                                # ends before 10 s
                "## G1\n0-2s: a\n"):                                                                   # beat without a clip
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
    for a in bad:
        assert lint(*a), f"lint passed {a}"
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
    e, _ = check({"G1": [("predator_burst", "L>R", good), ("predator_burst", "L>R", good + ".")]},
                 [{"id": "G1", "key": ("J", "jaguar", "run", "", ""), "clips": 2, "lines": [1], "slots": [1]}])
    assert any("near-duplicate" in x for x in e)
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    rng = next((x[8:] for x in sys.argv if x.startswith("--range=")), None)
    selftest() if "--selftest" in sys.argv else main(
        a[0], "write" if "--write" in sys.argv else "check" if "--check" in sys.argv else "list", rng)
