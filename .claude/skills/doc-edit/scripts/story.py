"""doc-edit story tools (2026-10-24): read the film cheaply, write the spec from a beat sheet.

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/story.py brief <audios-folder>
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/story.py expand <audios-folder> [--out=<spec path>]
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/story.py --selftest

brief: .work/doc_edit/<video>/brief.md = the one reading pack for the spec, instead of opening the screenplay, the
Visual Edit Plan and the timestamp file (~40 % of their size): the screenplay as written, each beat's `*Narrator:*`
line replaced by its numbered sentences with timing, a `*Character lock:*` printed only when it changes, then the
Visual Edit Plan without its beat table (it repeats the screenplay beats). Sentence line: `12 01:23.4 4.1s vo2.6 | text` = sentence 12 starts 01:23.4, its slot
(until sentence 13) is 4.1 s, the voice 2.6 s (the rest is a voice-free pause). Unknown screenplay layout -> the
screenplay as is + the sentence table.

expand: .work/doc_edit/<video>/beats.txt (or beats_parts/*.txt joined in name order) -> spec.txt for plan.py. The
beat sheet holds what needs judgement (story, emotion, what each shot shows, truth tokens); the rules of edit-grammar
that are mechanical become code: shot lengths from the emotion (short and shortening under tension, a long hold after
the climax, never a metronome), side shots only in voice-free pauses of quiet beats, the music cue per change of
emotion, music off before a strike + a hit on it, a whoosh on a chase start, a riser before a strike, natural sound
from the action, `# TURN` on strikes.

    # REGION africa                 every '#' line goes to the spec unchanged (headers, FILM / BIBLE / HOOK lines)
    # CAST [L] sp=lion sex=female   tag -> tokens added to every shot line that starts with that one tag (truth tokens
                                    are never forgotten; a line's own token of the same key wins)
    # INTRO @16                     @N = start of sentence N (INTRO, STORY, FAST_UNTIL lines)
    # STORY 1 @16 no=lion,leopard
    >> 1-15 raw                     raw: the lines below are spec lines ('## n' blocks), copied as they are (the hook)
    >> 16-18 calm A3=water A5=water sentences 16-18, emotion, audio for the beat's first shot; 'turn' = # TURN here
    [W] Wildebeest wait on the bank | real | sp=wildebeest size=wide count=many    shot pool: used in order, cycling
    17: [CR] Crocodile surges | real | sp=crocodile act=attack size=medium | A8=splash   'N:' = sentence N first
    ~ Empty brown water | real | sp=none size=wide set=river                       side shot: a voice-free pause only

Shot line: `need | [real|ai|any|GFX] | filter [| audio]` (src default any). Emotions (mean shot length start -> end
of the beat, music cue): calm 4.5, wonder 5.0 -> 4.5, observe 3.2 -> 3.0, build 3.0 -> 1.8 (tense), tense 2.4 -> 2.0,
chase 1.8 -> 1.3, strike 1.6 -> 1.4 (music off, hit, turn), release 5.5 -> 3.5 (calm), sad 5.0 -> 4.5 (calm).
A7 written on a beat or a line wins over the automatic cue; plan.py still checks everything (rhythm, side share,
truth, audio) and picks the footage.
"""
import math, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import plan  # noqa: E402  spec parser, narration spans, tc

# emotion -> (mean shot length at the beat start, at its end, A7 keywords or None = no new cue)
# (africa_3 benchmark 2026-10-24: 3.2 / 2.4 / 1.8 gave 1352 shots vs 955 = +40% footage and THIẾU; these give ~1150)
EMO = {"calm": (4.5, 4.5, "calm"), "wonder": (5.0, 4.5, "wonder"), "observe": (3.6, 3.2, "neutral"),
       "build": (3.4, 1.8, "tense"), "tense": (3.0, 2.4, "tense"), "chase": (1.9, 1.4, "chase"),
       "strike": (1.6, 1.4, None), "release": (5.5, 3.5, "calm"), "sad": (5.0, 4.5, "calm")}
QUIET = {"calm", "wonder", "observe", "release", "sad"}  # side shots allowed in their voice-free pauses
W = (1.25, 0.8, 1.05, 0.9, 1.15, 0.85, 1.1, 0.75)  # uneven lengths inside a sentence (plan.SEQ_W idea)
WR = (1.45, 0.8, 1.15, 0.75, 1.35, 0.85, 1.05, 0.7)  # build / chase: flashes of ~0.9 s next to 2 s images
SIDE_PAUSE, SIDE_MIN, SIDE_MAX, SIDE_SHARE = 3.0, 2.5, 5.0, 0.22  # pause (s) that takes a side shot; its length;
# share of the beat (one shot always allowed) and of the film so far
NAT_GAP = 8.0  # s between two automatic natural sounds
# act -> A6 keywords (Z:\Unseen\SFX shared_* files: footsteps_walk_grass, grass_rustle, drinking_lapping...)
NAT = (("drink", "drinking"), ("eat", "eating"), ("feed", "eating"), ("swim", "water"), ("fly", "wings"),
       ("chase", "footsteps"), ("run", "footsteps"), ("attack", "footsteps"), ("stalk", "grass,rustle"),
       ("hide", "grass,rustle"), ("walk", "footsteps,grass"))
HEAD = re.compile(r">>\s*(\d+)(?:\s*-\s*(\d+))?\s+(\w+)(.*)$")
AT = re.compile(r"^(#\s*(?:STORY|INTRO|FAST_UNTIL)\b.*?)@(\d+)")


def clock(t):
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


# ------------------------------------------------------------------ brief
def brief(folder):
    folder = Path(folder)
    cues, vo, vmsg = plan.narration(folder, wait=False)
    nxt = [c.t for c in cues[1:]] + [vo[-1][1] + 2.0]
    line = {c.index: f"{c.index} {plan.tc(c.t)} {n - c.t:.1f}s vo{b - a:.1f} | {c.text}"
            for c, n, (a, b) in zip(cues, nxt, vo)}
    sp = [p for p in folder.glob("*.md") if "screenplay" in p.name.lower()]
    vp = [p for p in folder.glob("*.md") if "visual" in p.name.lower() and "plan" in p.name.lower()]
    out, done, beats, lock = [], set(), 0, None
    beat = re.compile(r"\*\*(\d+)\s*·\s*([\d:.]+)\s*[–-]\s*([\d:.]+)\*\*")
    cur = None

    def flush():
        if cur:
            a, b = cur
            ids = [c.index for c in cues if a - 0.05 <= c.t < b - 0.05 and c.index not in done]
            out.extend("  " + line[i] for i in ids)
            done.update(ids)

    if len(sp) == 1:
        for raw in sp[0].read_text("utf-8").splitlines():
            s = raw.rstrip()
            if m := beat.match(s):
                flush()
                beats += 1
                cur = (plan.parse_clock(m[2]), plan.parse_clock(m[3]))
                out.append(s)
            elif s.startswith("*Narrator:*"):
                flush()
                cur = None
            elif s.startswith("*Character lock:*"):
                if s != lock:
                    out.append(s)
                lock = s
            else:
                if s.startswith("#"):
                    flush()
                    cur = None
                if s or (out and out[-1]):
                    out.append(s)
        flush()
    left = [line[c.index] for c in cues if c.index not in done]
    if left:
        out += ["", f"## Sentences{' outside the screenplay beats' if beats else ''} (n start slot voice | text)"] + left
    if len(vp) == 1:
        out += ["", "=" * 20 + f" {vp[0].name} (beat table left out: it repeats the screenplay beats)"]
        skip = False
        for raw in vp[0].read_text("utf-8").splitlines():
            s = raw.rstrip()
            if s.startswith("## "):
                skip = "beat" in s.lower() and ("ledger" in s.lower() or "index" in s.lower() or "level" in s.lower())
            if not skip and (s or (out and out[-1])):
                out.append(s)
    src = sum(len(p.read_text("utf-8")) for p in sp + vp + [x for x in folder.glob("*.md") if "timestamp" in x.name.lower()])
    text = "\n".join(out) + "\n"
    dst = plan.ROOT / ".work" / "doc_edit" / folder.parent.name / "brief.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, "utf-8")
    print(f"brief: {len(cues)} sentences, {beats} screenplay beats, {len(left)} sentences outside them; {vmsg}; "
          f"{len(text)} chars instead of {src} (screenplay + visual plan + timestamp file), {text.count(chr(10))} lines"
          f"\n-> {dst}")


# ------------------------------------------------------------------ expand
def parse_shot(s, n, cast):
    """'need | [src] | filter [| audio]' -> (need, src, filter tokens, audio tokens)."""
    p = [x.strip() for x in s.split("|")]
    if len(p) >= 3 and p[1] in plan.SRC:
        need, src, flt, aud = p[0], p[1], p[2], (p[3] if len(p) > 3 else "")
    else:
        need, src, flt, aud = p[0], "any", (p[1] if len(p) > 1 else ""), (p[2] if len(p) > 2 else "")
    assert need and len(p) <= 4, f"beats line {n}: need 'shot | [src] | filter [| audio]'"
    m = re.match(r"\[(\w+)\](?!\s*\[)", need)
    if m and m[1] in cast:  # one tag: its cast tokens, unless the line has that key itself
        have = {t.split("=")[0] for t in flt.split()}
        flt = " ".join(flt.split() + [t for t in cast[m[1]] if t.split("=")[0] not in have])
    plan.parse_filter(flt, n)
    plan.parse_audio(aud, n)
    return need, src, flt, aud


def read_beats(text):
    """-> (items, cast): items = ('#', line) | beat dicts in file order."""
    items, cast, errs, b = [], {}, [], None
    for n, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        try:
            if m := re.match(r"#\s*CAST\s+\[(\w+)\]\s+(.*)$", s):
                plan.parse_filter(m[2], n)
                cast[m[1]] = m[2].split()
                items.append(("#", s))
            elif b and b["emo"] == "raw" and not s.startswith(">>"):
                b["raw"].append(raw.rstrip())
            elif s.startswith("#"):
                items.append(("#", s))
            elif m := HEAD.match(s):
                a, z = int(m[1]), int(m[2] or m[1])
                assert m[3] in EMO or m[3] == "raw", f"beats line {n}: emotion {m[3]!r} not in {sorted(EMO) + ['raw']}"
                assert z >= a, f"beats line {n}: sentences {a}-{z}"
                rest = m[4].split()
                aud = " ".join(t for t in rest if re.match(r"A\d=", t))
                assert all(t == "turn" or re.match(r"A\d=", t) for t in rest), f"beats line {n}: unknown {rest}"
                plan.parse_audio(aud, n)
                b = {"a": a, "z": z, "emo": m[3], "turn": "turn" in rest, "aud": aud, "pool": [], "side": [],
                     "at": {}, "raw": [], "n": n}
                items.append(b)
            elif s:
                assert b, f"beats line {n}: shot line before the first '>>' beat"
                if s.startswith("~"):
                    b["side"].append(parse_shot(s[1:].strip(), n, cast))
                elif m := re.match(r"(\d+):\s*(.*)$", s):
                    assert b["a"] <= int(m[1]) <= b["z"], f"beats line {n}: sentence {m[1]} outside beat {b['a']}-{b['z']}"
                    b["at"].setdefault(int(m[1]), []).append(parse_shot(m[2], n, cast))
                else:
                    b["pool"].append(parse_shot(s, n, cast))
        except AssertionError as e:
            errs.append(str(e))
    beats = [x for x in items if isinstance(x, dict)]
    seen = [i for x in beats for i in range(x["a"], x["z"] + 1)]
    if dup := sorted({i for i in seen if seen.count(i) > 1}):
        errs.append(f"sentences in two beats: {dup[:20]}")
    for x in beats:
        if x["emo"] != "raw" and not x["pool"] and set(x["at"]) != set(range(x["a"], x["z"] + 1)):
            errs.append(f"beats line {x['n']}: beat {x['a']}-{x['z']} has no shot pool and not every sentence has 'N:' shots")
    assert not errs, f"{len(errs)} beat sheet errors:\n" + "\n".join(errs)
    return items, cast


def lengths(total, mean, k, ramp=False):
    """total s as shots of about `mean` s: uneven (W rotated by k), each >= ~1.2 s and <= ~6 s; ramp = getting
    shorter across the shots (tension) and still uneven, never a sorted metronome run."""
    n = max(1, round(total / mean), math.ceil(total / 5.5))  # a shot of up to ~6 s stays whole
    n = max(1, min(n, int(total // 1.6)))
    v = WR if ramp else W  # fast cuts: a wider swing, else 4 cuts of ~1.5 s read as a metronome (plan.py FLAT)
    w = [v[(k + j) % len(v)] * ((1.25 - 0.45 * j / (n - 1)) if ramp and n > 1 else 1) for j in range(n)]
    return [total * x / sum(w) for x in w]


def nat(flt):
    """filter tokens -> automatic A6 keywords from its action (None: no sound to add)."""
    f = dict(t.split("=", 1) for t in flt.split())
    acts = f.get("act", "").split(",")
    if f.get("sp", "none") == "none":
        return None
    if {"rest", "sleep"} & set(acts) and "close_up" in f.get("size", ""):
        return "breathing"
    return next((kw for a in acts for k, kw in NAT if a == k), None)


def expand(text, starts, vo, end=None):
    """beat sheet text, sentence starts, voice spans -> (spec text, summary dict)."""
    items, _ = read_beats(text)
    n = len(starts)
    beats = [x for x in items if isinstance(x, dict)]
    covered = {i for x in beats for i in range(x["a"], x["z"] + 1)}
    assert covered == set(range(1, n + 1)), \
        f"beats must cover sentences 1-{n}: missing {sorted(set(range(1, n + 1)) - covered)[:30]}, extra {sorted(covered - set(range(1, n + 1)))[:10]}"
    m = re.search(r"^\s*#\s*END\s+([\d:.]+)", text, re.M)
    end = end or (plan.parse_clock(m[1]) if m else vo[-1][1] + 2.0)
    bounds = [0.0] + starts[1:] + [end]
    out, sm = [], {"shots": 0, "side": 0, "side_s": 0.0, "foot_s": 0.0, "a7": 0, "off": 0, "hit": 0, "whoosh": 0,
                   "riser": 0, "a6": 0, "turns": 0, "emo": {}, "repeat": []}
    music, last_nat, last_nat_kw, prev = None, -1e9, None, None  # prev = last written shot (dict, mutable)

    def at(s):  # '# STORY 1 @16' -> '# STORY 1 01:31.75' (start of sentence 16)
        if a := AT.match(s.strip()):
            k = int(a[2])
            assert 1 <= k <= n, f"{s}: sentence {k} not in 1-{n}"
            return AT.sub(lambda m_: m_[1] + clock(starts[k - 1]), s.strip())
        return s
    for it in items:
        if not isinstance(it, dict):
            out.append(at(it[1]))
            continue
        b = it
        if b["emo"] == "raw":
            out.extend(at(x) for x in b["raw"])
            if a7 := re.findall(r"A7=(\S+)", "\n".join(b["raw"])):
                music = a7[-1]
            prev = None
            continue
        l0, l1, mood = EMO[b["emo"]]
        t0, t1 = bounds[b["a"] - 1], bounds[b["z"]]
        sm["emo"][b["emo"]] = sm["emo"].get(b["emo"], 0) + 1
        if b["emo"] == "strike" and prev is not None:  # silence before the strike: music off on the shot before it
            if music != "off":
                prev["aud"]["7"] = "off"; sm["off"] += 1
            if prev["emo"] == "build" and "8" not in prev["aud"]:
                prev["aud"]["8"] = "riser"; sm["riser"] += 1
            music = "off"
        pi = si = side_t = 0
        first = True
        for i in range(b["a"], b["z"] + 1):
            ts, te = bounds[i - 1], bounds[i]
            d = te - ts
            out.append(f"## {i}")
            if (b["turn"] or b["emo"] == "strike") and i == b["a"]:
                out.append("# TURN"); sm["turns"] += 1
            p = ((ts + te) / 2 - t0) / max(t1 - t0, 1e-6)
            mean = l0 + (l1 - l0) * p
            pause = te - max(vo[i - 1][1], ts)
            side = (b["emo"] in QUIET and b["side"] and pause >= SIDE_PAUSE and d - pause >= 1.5
                    and (prev is None or not prev["side"])
                    and (side_t == 0 or side_t + min(pause, SIDE_MAX) <= SIDE_SHARE * (t1 - t0))
                    and sm["side_s"] + min(pause, SIDE_MAX) <= SIDE_SHARE * te)  # plan.py's limit is 30%
            side_len = min(max(pause, SIDE_MIN), SIDE_MAX) if side else 0.0
            main = d - side_len
            fixed = b["at"].get(i, [])
            ls = lengths(main, mean, i, ramp=b["emo"] in ("build", "chase"))  # shorter and shorter as tension rises
            if b["emo"] == "release" and i == b["a"]:  # the shot right after the climax is the long one
                ls.insert(0, ls.pop(ls.index(max(ls))))
            if len(ls) < len(fixed) and main / len(fixed) >= 1.2:
                ls = [main / len(fixed)] * len(fixed)
            shots = []
            for j, x in enumerate(ls):
                if j < len(fixed):
                    tpl = fixed[j]
                elif b["pool"]:
                    tpl = b["pool"][pi % len(b["pool"])]; pi += 1
                else:
                    tpl = fixed[j % len(fixed)]
                shots.append((x, tpl, False))
            if side:
                shots.append((side_len, b["side"][si % len(b["side"])], True)); si += 1
                side_t += side_len
            t, star = ts, max(range(len(shots)), key=lambda j_: shots[j_][0])  # '*' on the longest: rounding lands there
            for j, (x, (need, src, flt, aud), is_side) in enumerate(shots):
                a = {m_[0]: m_[1] for m_ in re.findall(r"A(\d)=(\S+)", aud)}
                if first:
                    a = {**{m_[0]: m_[1] for m_ in re.findall(r"A(\d)=(\S+)", b["aud"])}, **a}
                    if "7" not in a and mood and mood != music:
                        a["7"] = mood
                    if b["emo"] == "strike" and "8" not in a:
                        a["8"] = "hit"; sm["hit"] += 1
                    if b["emo"] == "chase" and "8" not in a:
                        a["8"] = "whoosh"; sm["whoosh"] += 1
                    first = False
                if not is_side and "6" not in a and t - last_nat >= NAT_GAP and x >= 1.5 and (kw := nat(flt)) \
                        and kw != last_nat_kw:
                    a["6"] = kw; last_nat, last_nat_kw = t, kw; sm["a6"] += 1
                elif "6" in a:
                    last_nat, last_nat_kw = t, a["6"]
                if "7" in a:
                    music = a["7"]
                same = prev is not None and prev["need"] == need
                shot = {"dur": "*" if j == star else f"{x:.1f}", "need": need, "src": src, "flt": flt,
                        "aud": a, "side": is_side, "emo": b["emo"], "rep": prev["rep"] + 1 if same else 1}
                if shot["rep"] == 3:
                    sm["repeat"].append(f"{b['a']}-{b['z']}")
                out.append(shot)
                prev = shot
                t += x
                sm["shots"] += 1
                sm["foot_s"] += x
                if is_side:
                    sm["side"] += 1; sm["side_s"] += x
    lines = []
    for x in out:
        if isinstance(x, dict):
            sm["a7"] += "7" in x["aud"] and x["aud"]["7"] != "off"
            aud = " ".join(f"A{k}={v}" for k, v in sorted(x["aud"].items()))
            lines.append(f"{x['dur']} | {x['need']} | {x['src']} | {x['flt']} | {aud}".rstrip())
        else:
            lines.append(x)
    return "\n".join(lines) + "\n", sm


def beats_text(work):
    parts = sorted((work / "beats_parts").glob("*.txt")) if (work / "beats_parts").is_dir() else []
    files = parts or [work / "beats.txt"]
    assert files[0].exists(), f"write {work / 'beats.txt'} (or beats_parts/01.txt ...) first"
    return "".join(p.read_text("utf-8").rstrip("\n") + "\n" for p in files)


def main_expand(folder):
    folder = Path(folder)
    cues, vo, vmsg = plan.narration(folder, wait=False)
    work = plan.ROOT / ".work" / "doc_edit" / folder.parent.name
    out = next((Path(a[6:]) for a in sys.argv if a.startswith("--out=")), work / "spec.txt")
    spec, sm = expand(beats_text(work), [c.t for c in cues], vo)
    out.write_text("# generated by story.py expand from the beat sheet: edit the beats, expand again\n" + spec, "utf-8")
    emo = ", ".join(f"{k} {v}" for k, v in sm["emo"].items())
    print(f"expand: {len(cues)} sentences -> {sm['shots']} shots (beats: {emo}); side shots {sm['side']} "
          f"({sm['side_s']:.0f}s = {sm['side_s'] / max(sm['foot_s'], 1):.0%}); music cues {sm['a7']}, off before a strike "
          f"{sm['off']}, hits {sm['hit']}, whoosh {sm['whoosh']}, riser {sm['riser']}, natural A6 {sm['a6']}, turns "
          f"{sm['turns']}; {vmsg}\n-> {out}")
    if sm["repeat"]:
        print("same shot line 3+ times in a row (give the beat more lines) in beats: " + ", ".join(sm["repeat"]))


def selftest():
    text = """# REGION africa
# CAST [L] sp=lion sex=female
# INTRO @3
# STORY 1 @3 no=river
>> 1-2 raw
## 1
* | hook a | real | sp=none size=wide | A7=tense
## 2
* | hook b | any | sp=lion act=run |
>> 3-4 calm A3=wind
[L] Lioness rests in the shade | sp=lion act=rest size=close_up
[L] Lioness watches the herd | size=wide sex=male
~ Grass in the wind | real | sp=none size=wide
>> 5 build
[L] Lioness stalks | act=stalk size=medium
>> 6 strike
6: [L] Lioness bursts out | real | act=attack size=medium
>> 7-8 release
[L] Lioness pants | act=rest size=close_up
"""
    starts = [0.0, 8.0, 16.0, 26.0, 35.0, 40.0, 44.0, 54.0]
    vo = [(t, t + 2.0) for t in starts]
    spec, sm = expand(text, starts, vo, end=64.0)
    end, intro, blocks = plan.parse_spec(spec)
    slots = plan.build(starts, end or 64.0, blocks, intro)  # the expanded spec is valid for plan.py
    assert intro == 16.0 and "# STORY 1 00:16.00 no=river" in spec
    assert abs(sum(s["dur"] for s in slots) - 64.0) < 1e-6
    assert "sp=lion act=rest size=close_up sex=female" in spec  # cast tokens added
    assert "sex=male" in spec and "sex=male sp=lion sex=female" not in spec  # the line's own sex wins
    s5 = [s for s in slots if s["line"] == 5]
    assert s5[-1]["audio"] and {"track": 7, "kw": ["off"]} in s5[-1]["audio"]  # music off before the strike
    assert {"track": 8, "kw": ["riser"]} in s5[-1]["audio"]
    s6 = [s for s in slots if s["line"] == 6]
    assert {"track": 8, "kw": ["hit"]} in s6[0]["audio"] and "## 6\n# TURN" in spec
    assert any(e["track"] == 7 and e["kw"] == ["calm"] for s in slots if s["line"] == 7 for e in s["audio"])
    side = [s for s in slots if s["need"] == "Grass in the wind"]
    assert side and all(s["start"] >= starts[s["line"] - 1] + 2.0 - 1e-6 for s in side)  # in the voice-free pause
    assert [e for s in slots if s["line"] == 3 for e in s["audio"] if e["track"] == 3] == [{"track": 3, "kw": ["wind"]}]
    s3 = [s for s in slots if s["line"] in (3, 4)]
    assert any(e["track"] == 6 for s in s3 for e in s["audio"])  # breathing on the resting close-up
    assert all(1.2 <= s["dur"] <= 6.5 for s in slots if s["line"] > 2), [s["dur"] for s in slots]
    assert sm["turns"] == 1 and sm["hit"] == 1 and sm["off"] == 1
    for bad, why in (("# REGION africa\n>> 1-7 calm\nx | sp=none\n", "missing [8]"),
                     (">> 1-8 calm\nx | sp=none\n>> 8 tense\ny | sp=none\n", "two beats"),
                     (">> 1-8 happy\nx | sp=none\n", "emotion")):
        try:
            expand(bad, starts, vo, end=64.0)
            raise SystemExit(f"selftest: no error for {why}")
        except AssertionError as e:
            assert why.split()[0] in str(e) or why in str(e), (why, str(e))
    hl = lengths(9.0, 1.5, 0)
    assert len(hl) >= 5 and abs(sum(hl) - 9.0) < 1e-9 and min(hl) >= 1.2 and max(hl) - min(hl) > 0.4
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if a[:1] == ["--selftest"]:
        selftest()
    elif a[:1] == ["brief"] and len(a) > 1:
        brief(a[1])
    elif a[:1] == ["expand"] and len(a) > 1:
        main_expand(a[1])
    else:
        print(__doc__)
