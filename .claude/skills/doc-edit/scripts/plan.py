"""doc-edit plan (new-video run B3, or /doc-edit plan): spec.txt -> footage + audio match (no tokens) -> plan.json + <video>/plan.md.

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/plan.py <audios-folder>
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/plan.py --selftest

Clips on timelines Edit/Open of the last N videos of the same workspace (ledger.py, /doc-edit check-timelines) are never matched.
Edit + Open of this video share one reuse budget: parts already on "Open" (read from Resolve when the open project is
this video) count toward REUSE_MAX and are never shown again on Edit.

spec.txt lives in .work/doc_edit/<video>/ (video = parent of the audios folder). Format:
    # END 29:50                optional timeline end; default = end of last sentence + 2 s
    # INTRO 0:20               intro length 0:15-0:30, chosen per video (side-shot rules start after it); default 0:15
    # REGION africa            footage of this region only (scan_source.REGION); /doc-edit <audios> <region> writes it.
                               no line = amazon (every video before 2026-10-20)
    ## <sentence number>
    <dur|*> | <shot needed, Vietnamese> | <real|ai|any|GFX> | <filter> | <audio>
filter: k=v1,v2 tokens, '_' = space. sp (species, hard; sp=none = no animal) act size light set mood cam dir
        count kw (caption words) no (species or caption word that must NOT be in the clip, hard) pin (path fragment, or pin=none = force THIẾU)
        look=green|dry (ground look of this line; '# LOOK dry' = the film's first look, see match())
        story truth, hard (hard()): sex=female|male age=young|adult (other one rejected, not visible -> WEAK
        'kiểm tra'), xact=rest,sleep (clip actions never allowed), out=kill (only then a caught / killed prey);
        a stalk / hunt / run / fight line never takes a clip that only rests / sleeps
    # STORY 2 06:30 no=river,crocodile   that story's slots never show these; # HOOK ... = cold-open blueprint
audio:  A3=forest,day A6=bird A8=branch,snap A7=off   (keywords matched against file paths; A2 forbidden)
'*' = rest of the sentence slot (sentence start -> next sentence start, pause included); exactly one per sentence.
'NxK' / '*xK' = N s (or the rest) as K shots of the same need + filter, uneven lengths, audio on the first part.
--yolo-cached: use the YOLO cache only (unmeasured clips rank by tags); yolo.py --warm measures the rest.
"""
import json, os, re, sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / ".claude/skills/scan-source/scripts")]
from dvr_cowork.timestamps import parse_timestamp_file  # noqa: E402
from dvr_cowork.timecode import parse_clock  # noqa: E402
from scan_source import REGIONS, ROOTS, audio_blocked, index_of, video_roots  # noqa: E402
import beats  # noqa: E402
import ledger  # noqa: E402

SRC = {"real", "ai", "any", "GFX"}
KEYS = {"sp", "act", "size", "light", "set", "mood", "cam", "ang", "dir", "count", "kw", "no", "pin", "look",
        "sex", "age", "xact", "out"}
TAG = {"act": "action", "xact": "action", "size": "shot_size", "set": "setting", "cam": "camera", "ang": "angle",
       "dir": "direction"}
# Story truth (input/plan.md, user 2026-10-23): checked before any score, a high fit never rescues a clip that breaks
# them. sex= / age= of the slot's own animal: the tag (tag-source, when it has the field) else caption words; the
# other sex / age = rejected, not visible (or both sexes in frame) = at most WEAK with a 'kiểm tra' marker note.
SEX_CAP = {"female": r"\b(lioness(es)?|females?|mothers?|her|she|cows?|doe|ewes?|hens?)\b",
           "male": r"\b(males?|maned|manes?|his|he|bulls?|rams?|stallions?)\b"}
AGE_CAP = {"young": r"\b(cubs?|calf|calves|foals?|juveniles?|young|youngsters?|bab(y|ies)|infants?|newborns?|pups?|"
                    r"chicks?|fawns?|kittens?|yearlings?)\b",
           "adult": r"\b(adults?|mothers?|bulls?|lioness(es)?|maned|matriarch)\b"}
# a caught / killed / eaten prey shows an outcome: only where the screenplay confirms it (out=kill) or the line is a
# meal (act=eat); a near miss or an unknown end never gets it (plan.md 8.1: no kill from another hunt)
KILL = re.compile(r"\b(kill(s|ed|ing)?|carcass(es)?|corpse|lifeless|catch(es|ing)?|caught|takes? down|brings? down|"
                  r"devour\w*|suffocat\w*|prey in (its|her|his) (jaws|mouth)|drags? (the |its )?(prey|kill))\b", re.I)
STILL = {"rest", "sleep"}  # a clip doing only these never stands in for a stalk / hide / hunt / chase / fight line
OPP = {"left": "right", "right": "left", "toward": "away", "away": "toward"}
MOVING = {"attack", "hunt", "chase", "fight", "run", "stalk", "jump", "walk", "swim", "fly"}
# tag-source 2026-10-23 split 'hunt' into chase / catch and added hide; clips tagged before keep 'hunt'
ACT_SYN = {"hunt": ("chase", "catch"), "chase": ("hunt",), "catch": ("hunt",), "hide": ("stalk",), "stalk": ("hide",)}
TAG_POS = (0.15, 0.40, 0.65, 0.90)  # = tag_source.POS: clip time of contact-sheet frames 1-4 ('phase' = action per frame)


def acts_of(want):
    return set(want) | {y for x in want for y in ACT_SYN.get(x, ())}
TRUTH_WHY = {"sex", "age", "kill", "resting", "xact"}  # hard() reasons the reports count (no= / biome / night: filters)
DIR_PEN = 0.15  # same sentence, moving subject, screen direction reversed against the previous shot
SIZES = ["extreme_close", "close_up", "medium", "wide", "aerial"]
OK_FIT, WEAK_FIT = 0.6, 0.35
FALLBACK_T = 300.0  # first 5 min: strict matches only; later THIẾU shots may use related/neutral clips
FALLBACK_FIT = 0.2
LATE_SUB = "--late-sub" in sys.argv or "--sub-all" in sys.argv  # best substitute for THIẾU slots from LATE_SUB_T s on (user 2026-10-16, demo_3)
LATE_SUB_T = 0.0 if "--sub-all" in sys.argv else next((float(a[13:]) for a in sys.argv if a.startswith("--late-sub-t=")), 600.0)  # --sub-all: every THIẾU slot; --late-sub-t=490: from 8:10; default after 10:00
LATE_COMPANION = {"chimpanzee": ("gorilla",), "gorilla": ("chimpanzee",), "spotted hyena": ("forest buffalo",),
                  "forest buffalo": ("spotted hyena",), "macaw": ("scarlet macaw",), "scarlet macaw": ("macaw",),
                  "red lechwe": ("impala", "kob")}  # africa_1: no wetland antelope in the library
SUB_GAP, SUB_MAX = 60.0, 8  # late substitutes only (user 2026-10-17, amazon_2): another part of a clip already on the
# timeline beats unrelated scenery, so the reuse limits loosen from 120 s / 3 uses to 60 s / 4 uses
# action shots (user rule 2026-10-12): a strike/chase shot prefers a clip that shows action; a same-species clip
# without it is capped at WEAK (yellow, below OK_FIT) instead of looking like a match; none at all -> THIẾU
STRIKE = {"attack", "hunt", "chase", "catch", "fight", "run", "stalk", "jump"}
NEUTRAL = {"landscape", "bird", "birds", "insects", "butterfly", "frog", "hummingbird", "toucan-bird", "spider",
           "supplementary_shots", "others"}  # folders of side shots: scenery, insects, birds, frogs
INTRO_MIN, INTRO_MAX = 15.0, 120.0  # '# INTRO m:ss': default INTRO_MIN; longer than INTRO_LEGACY = a cold-open hook
INTRO_LEGACY, INTRO_CHAR = 30.0, 0.5  # intro > 30 s: >= 50% of its footage time on [tag] character shots
BIOMES, OPENINGS = {"savanna", "rainforest"}, {"landscape", "action"}
# ground look from the caption (user 2026-10-22, africa_1: the opening jumped green grass -> dry grass -> desert sand).
# '# LOOK green' = the film's terrain, put on every slot; a line overrides it with look=dry. Desert never passes
# unless asked; the other look costs LOOK_PEN; mixed / unknown stays neutral. The look is measured from the tag sheet
# colours (ground_looks; captions say 'savanna' for golden and green grass alike), caption words only without a sheet.
LOOKS = {"green": r"\b(green|lush|flooded|floodwater|floodplain|wetland|marsh|swamp|reeds?|papyrus|delta|okavango)\b",
         "dry": r"\b(dry|dried|golden grass|golden savanna|dusty|dust|parched|brown grass|bare ground|bare earth|sandy|sand|straw|withered)\b",
         "desert": r"\b(desert|semi-desert|dunes?|kalahari|namib|arid)\b"}
LOOK_PEN = 0.3
HARD_MIN, HARD_MAX = 0.8, 10.0  # shots outside this are errors; SHOT_MIN-SHOT_MAX is only a warning (holds / flashes)
OPEN_ACT = {"run", "fight", "attack", "hunt", "chase", "catch", "stalk", "jump"}  # '# OPENING action': the first shot shows one of these
OPEN_WIDE_T = 20.0  # '# OPENING action': a wide/medium/aerial shot that places who is where starts within 20 s
SIDE_MAX = 0.3   # after the intro, side shots (anything without a [tag] main character) <= 30% of footage time
SIDE_RUN = 3     # max side shots in a row; a run of 3 is rare: at most one per RUN3_EVERY seconds
RUN3_EVERY = 300.0
SHOT_MIN, SHOT_MAX = 1.2, 6.0  # footage shot length bounds (s); longer = split into a sequence
FLAT = 4         # this many shots in a row whose lengths differ by < FLAT_SPAN s = flat, metronome rhythm
FLAT_SPAN = 0.4
SHORT_T, LONG_T = 2.0, 3.5  # rhythm needs both: >= 25% shots <= 2.0 s and >= 10% shots >= 3.5 s
OPEN_MIN, OPEN_MAX = 3.0, 4.0  # user rule 2026-10-13: the first shot of "Edit" is a landscape (sp=none, wide/aerial)
# of 3-4 s, longer than every other intro shot
HIT_WIN, BEAT_WIN = 0.45, 0.25  # intro cuts move onto a hit B3+ / bar line within HIT_WIN s, else a beat within BEAT_WIN
OUT = next((a[6:] for a in sys.argv if a.startswith("--out=")), None)  # benchmark: plan written there, not the video's
SPEC = next((a[7:] for a in sys.argv if a.startswith("--spec=")), None)  # benchmark: another spec than <work>/spec.txt
AI_TRIM = 0.3  # AI clips often morph in the first/last frames
YOLO_SEEN = 0.3  # YOLO saw the subject in >= 30% of samples: its window and size are trusted
# Reuse inside one video (user 2026-10-22, africa_1: save source, not too often, not too rarely): one clip serves up
# to REUSE_MAX slots, REUSE_GAP s apart on the timeline; another part of the clip first (SRC_MARGIN between parts),
# else the same frames again, but no frame on screen more than SAME_MAX times and those repeats SAME_GAP s apart.
# A fresh clip still wins over a reused one of similar fit (REUSE_PEN per use, SAME_PEN per frame repeat).
REUSE_MAX, REUSE_GAP, REUSE_PEN, SRC_MARGIN = 6, 90.0, 0.06, 1.0
SAME_MAX, SAME_GAP, SAME_PEN = 3, 300.0, 0.05
BIOME_NO = ("autumn", "snow", "conifer", "pine forest", "town", "city", "garden", "airport", "building", "boat",
            "zoo", "enclosure", "captive", "wildlife park", "bloody", "blood", "pronghorn", "everglades", "florida")
# caption words excluded for every slot: amazon_2 "dull autumn woodland" for a jungle trail; africa_1 a hippo "in a
# pond at a wildlife park" and a "bloody leg bone" (screenplays: no blood); a non-tropical channel would make this per workspace
BED_MIN = 20.0  # s: shortest file used as an A3-A5 bed / layer (africa_1: 1-6 s calls were picked and skipped by place)
WPS = 2.5  # narrator speed (words/s) for VO spans before the audio exists; tune if VO ● looks off after vo-sync
AUDIO_POOL = {3: ("ambience_sound", "Nature_sound"), 4: ("ambience_sound", "Nature_sound"),
              5: ("ambience_sound", "Nature_sound"), 6: ("Nature_sound", "SXF"),
              7: ("tense_music", "music"), 8: ("SXF", "Nature_sound"), 9: ("SXF", "Nature_sound")}


def tc(s):
    return f"{int(s // 60):02d}:{s % 60:04.1f}"


# ------------------------------------------------------------------ spec
def parse_filter(s, n):
    f = {}
    for tok in s.split():
        k, _, v = tok.partition("=")
        assert k in KEYS and v, f"spec line {n}: bad filter token {tok!r} (keys: {sorted(KEYS)})"
        f[k] = [x.replace("_", " ") if k in ("sp", "kw", "no") else x for x in v.split(",")]  # no=male_lion
        assert k != "look" or set(f[k]) <= set(LOOKS), f"spec line {n}: look={v} not in {sorted(LOOKS)}"
        assert k != "sex" or set(f[k]) <= set(SEX_CAP), f"spec line {n}: sex={v} not in {sorted(SEX_CAP)}"
        assert k != "age" or set(f[k]) <= set(AGE_CAP), f"spec line {n}: age={v} not in {sorted(AGE_CAP)}"
        assert k != "out" or f[k] == ["kill"], f"spec line {n}: out={v}: only out=kill (default = no kill on screen)"
    return f


def parse_audio(s, n):
    out = []
    for tok in s.split():
        if tok == "·":
            continue
        m = re.fullmatch(r"A(\d+)=(\S+)", tok)
        assert m, f"spec line {n}: bad audio token {tok!r} (use A6=bird,call)"
        assert 3 <= int(m[1]) <= 9, f"spec line {n}: audio only on A3-A9 (A2 = narration), got A{m[1]}"
        out.append({"track": int(m[1]), "kw": [k.replace("_", " ").lower() for k in m[2].split(",")]})
    return out


def parse_spec(text):
    end, intro, blocks, cur, errs = None, INTRO_MIN, {}, None, []
    for n, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        try:  # collect every bad line: one fix pass instead of one re-run per error
            if m := re.match(r"#\s*END\s+([\d:.]+)", s):
                end = parse_clock(m[1])
            elif m := re.match(r"#\s*INTRO\s+([\d:.]+)", s):
                intro = parse_clock(m[1])
                assert INTRO_MIN <= intro <= INTRO_MAX, f"spec line {n}: INTRO {m[1]} not in 0:15-2:00"
            elif s.startswith("## "):
                cur = int(s[3:]); blocks[cur] = []
            elif s and not s.startswith("#"):
                p = [x.strip() for x in s.split("|")]
                assert cur is not None and len(p) == 5, f"spec line {n}: need 'dur | shot | src | filter | audio' under '## N'"
                assert p[2] in SRC, f"spec line {n}: src {p[2]!r} not in {sorted(SRC)}"
                blocks[cur].append((p[0], p[1], p[2], parse_filter(p[3], n), parse_audio(p[4], n)))
        except AssertionError as e:
            errs.append(str(e))
    assert not errs, "\n".join(errs)
    return end, intro, blocks


def spec_meta(text, end=None, intro=INTRO_MIN):
    """Optional headers: '# OPENING landscape|action', '# BIOME savanna|rainforest', '# FAST_UNTIL m:ss',
    '# STORY n m:ss' (start of story n), '# TURN' under a '## N' (a change of advantage the author marked).
    Missing = old behaviour (landscape opening, one HOOK/BODY report)."""
    meta, errs, cur = {"opening": "landscape", "biome": None, "look": None, "fast": None, "stories": [], "turns": set(),
                       "story_no": {}, "hook": bool(re.search(r"^\s*#\s*HOOK\b", text, re.M))}, [], None
    for n, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        try:
            if m := re.match(r"#\s*OPENING\s+(\S+)", s):
                meta["opening"] = m[1].lower()
                assert meta["opening"] in OPENINGS, f"spec line {n}: OPENING {m[1]!r} not in {sorted(OPENINGS)}"
            elif m := re.match(r"#\s*BIOME\s+(\S+)", s):
                meta["biome"] = m[1].lower()
                assert meta["biome"] in BIOMES, f"spec line {n}: BIOME {m[1]!r} not in {sorted(BIOMES)}"
            elif m := re.match(r"#\s*LOOK\s+(\S+)", s):
                meta["look"] = m[1].lower()
                assert meta["look"] in LOOKS, f"spec line {n}: LOOK {m[1]!r} not in {sorted(LOOKS)}"
            elif m := re.match(r"#\s*FAST_UNTIL\s+([\d:.]+)", s):
                meta["fast"] = parse_clock(m[1])
            elif m := re.match(r"#\s*STORY\s+(\d+)\s+([\d:.]+)(.*)", s):
                meta["stories"].append((int(m[1]), parse_clock(m[2])))
                if m[3].strip():  # '# STORY 2 06:30 no=river,crocodile': what this story's place / time never shows
                    f = parse_filter(m[3], n)
                    assert set(f) == {"no"}, f"spec line {n}: a STORY line takes only no=..."
                    meta["story_no"][int(m[1])] = f["no"]
            elif s.startswith("## "):
                cur = int(s[3:])
            elif re.match(r"#\s*TURN\b", s):
                assert cur is not None, f"spec line {n}: '# TURN' belongs under a '## N'"
                meta["turns"].add(cur)
        except (AssertionError, ValueError) as e:
            errs.append(str(e))
    st = meta["stories"]
    if st:
        if [k for k, _ in st] != list(range(1, len(st) + 1)) or any(b[1] <= a[1] for a, b in zip(st, st[1:])):
            errs.append("spec: '# STORY n m:ss' must number 1, 2, 3... with rising times")
        elif st[0][1] < intro or (end and st[-1][1] >= end):
            errs.append(f"spec: STORY times must lie between INTRO ({tc(intro)}) and END")
    assert not errs, "\n".join(errs)
    return meta


def story_rules(slots, meta):
    """A story's no= (its '# STORY' line) joins the no= of every slot from that story's start to the next one."""
    for s in slots:
        k = max((k for k, t in meta["stories"] if t <= s["start"]), default=None)
        if extra := meta["story_no"].get(k):  # new dict: the parts of one line share their filter
            s["filter"] = {**s["filter"], "no": s["filter"].get("no", []) + [x for x in extra if x not in s["filter"].get("no", [])]}


def story_report(slots, meta, intro, end):
    """Per chapter (HOOK 0..STORY 1, STORY n..) numbers from the plan; what a machine cannot see says 'chưa xác minh'."""
    cuts = [0.0] + [t for _, t in meta["stories"]] + [end]
    names = ["HOOK"] + [f"STORY {k}" for k, _ in meta["stories"]]
    if not meta["stories"]:
        cuts, names = [0.0, intro, end], ["HOOK", "BODY"]
    out = []
    for name, a, b in zip(names, cuts, cuts[1:]):
        sh = [s for s in slots if a <= s["start"] < b and s["src"] != "GFX"]
        if not sh:
            continue
        foot = sum(s["dur"] for s in sh)
        turns = len({s["line"] for s in sh} & meta["turns"])
        out.append(f"{name} {tc(a)}-{tc(b)}: {len(sh)} shots / {foot:.0f}s footage, "
                   f"<=2s {sum(s['dur'] <= SHORT_T for s in sh) / len(sh):.0%}, >=3.5s {sum(s['dur'] >= LONG_T for s in sh) / len(sh):.0%}; "
                   f"side {sum(s['dur'] for s in sh if is_side(s)):.0f}s; no size/space filter {sum(not s['filter'].get('size') for s in sh)}; "
                   f"THIẾU {sum(s.get('status') == 'THIEU' for s in sh)}, audio THIẾU "
                   f"{sum(e.get('status') == 'THIEU' for s in sh for e in s['audio'])}; "
                   f"VO-free {sum(not s.get('vo') for s in sh)} shots; marked turns "
                   + (str(turns) if turns else "0 (chưa xác minh: add '# TURN' under the ## where advantage changes)"))
    return out


def spec_region(text):
    """'# REGION africa' in the spec -> 'africa'; no line -> 'amazon' (videos before 2026-10-20)."""
    m = re.search(r"^\s*#\s*REGION\s+(\S+)", text, re.M | re.I)
    region = m[1].lower() if m else "amazon"
    assert region in REGIONS, f"spec: REGION {region!r} not in {REGIONS}"
    return region


SEQ_W = (1.25, 0.8, 1.05, 0.9, 1.2, 0.85, 1.1, 0.75)  # 'NxK' sequence: uneven part lengths, never a metronome


def seq(d):
    """'3.5' -> ('3.5', 1); '12x4' / '*x5' -> 12 s (or the rest) as 4 / 5 shots of the same need and filter,
    each its own slot (different clips), audio on the first (africa_1, 2026-10-21: 45 s slots, half without voice).
    '12x4 same' (2026-10-23): the K shots are consecutive parts of ONE clip (one action that really continues:
    stalk -> lunge -> miss), cut where the parts meet; no clip long enough -> K separate picks as without 'same'."""
    m = re.fullmatch(r"(\*|[\d.]+)x(\d+)(\s+same)?", d)
    return (m[1], int(m[2]), bool(m[3])) if m else (d, 1, False)


def build(starts, end, blocks, intro=INTRO_MIN):
    """starts = sentence start times; returns slots filling [0 .. end] exactly."""
    assert sorted(blocks) == list(range(1, len(starts) + 1)), \
        f"spec must cover sentences 1..{len(starts)}, missing {sorted(set(range(1, len(starts) + 1)) - set(blocks))}"
    bounds = [0.0] + starts[1:] + [end]
    slots, errs = [], []
    for i in range(1, len(starts) + 1):
        t0, t1 = bounds[i - 1], bounds[i]
        rest = (t1 - t0) - sum(float(seq(b[0])[0]) for b in blocks[i] if seq(b[0])[0] != "*")
        stars = [seq(b[0])[1] for b in blocks[i] if seq(b[0])[0] == "*"]
        if len(stars) != 1:
            errs.append(f"## {i}: exactly one '*' shot")
        elif rest < SHOT_MIN * stars[0]:
            errs.append(f"## {i}: '*' shot only {rest:.1f}s for {stars[0]} shot(s) (slot {t1 - t0:.1f}s)")
        if errs:
            continue
        t = t0
        for d, need, src, flt, audio in blocks[i]:
            base, k, same = seq(d)
            total = rest if base == "*" else float(base)
            w = SEQ_W[:k] if k <= len(SEQ_W) else (SEQ_W * (k // len(SEQ_W) + 1))[:k]
            chain = f"{i}:{len(slots) + 1}" if same and k > 1 else None
            for j, x in enumerate(w if k > 1 else (1.0,)):
                dur = total * x / sum(w) if k > 1 else total
                slots.append({"slot": len(slots) + 1, "line": i, "start": round(t, 2), "dur": round(dur, 2),
                              "need": need, "src": src, "filter": flt, "audio": audio if j == 0 else [],
                              "intro": t < intro, **({"chain": chain} if chain else {})})
                t += dur
        assert abs(t - t1) < 1e-6
    assert not errs, "\n".join(errs)
    return slots


def is_side(s):
    """Side shot = footage without a [tag] main character: scenery, birds, insects, a friendly other species..."""
    return s["src"] != "GFX" and not s.get("need", "").startswith("[")


def check_side(slots):
    """Spec check after the intro: side shots stay a seasoning, the main characters carry the film."""
    ih = [s for s in slots if s.get("intro") and s["src"] != "GFX"]
    if sum(s["dur"] for s in ih) > INTRO_LEGACY:  # long cold open: scenery must not take it over
        tot, side = sum(s["dur"] for s in ih), sum(s["dur"] for s in ih if is_side(s))
        assert side <= (1 - INTRO_CHAR) * tot, (
            f"intro: {side:.0f}s of {tot:.0f}s are side shots; a long INTRO needs >= {INTRO_CHAR:.0%} on [tag] character "
            "shots (who, the threat, where, the open question)")
    body = [s for s in slots if not s.get("intro")]
    if not body:
        return 0.0
    total = sum(s["dur"] for s in body if s["src"] != "GFX")
    st = sum(s["dur"] for s in body if is_side(s))
    per = Counter()
    for s in body:
        per[s["line"]] += s["dur"] if is_side(s) else 0
    assert st <= SIDE_MAX * total, (f"side shots after the intro {st:.0f}s = {st / total:.0%} of footage "
                                    f"(max {SIDE_MAX:.0%}); turn some into character shots, most side time in ## "
                                    + ", ".join(f"{k} ({v:.0f}s)" for k, v in per.most_common(8)))
    run, run3 = [], []
    for s in body + [{"src": "GFX"}]:  # sentinel closes the last run
        if is_side(s):
            run.append(s); continue
        assert len(run) <= SIDE_RUN, (f"## {run[0]['line']}-{run[-1]['line']}: {len(run)} side shots in a row "
                                      f"(max {SIDE_RUN}); put a character shot between them")
        if len(run) == 3:
            run3.append(run[0])
        run = []
    span = body[-1]["start"] + body[-1]["dur"] - body[0]["start"]
    assert len(run3) <= max(1, span // RUN3_EVERY), (
        f"{len(run3)} runs of 3 side shots (## {', '.join(str(r['line']) for r in run3)}); "
        f"max one per {RUN3_EVERY / 60:.0f} min, make the others 1-2")
    return st / total


def check_rhythm(slots):
    """Spec check: shot lengths follow the story (hold, flash, burst), not a metronome. Only absurd lengths are errors;
    the rest (outside 1.2-6 s, flat runs, short/long mix) is returned as warnings -> (short, long_, warnings)."""
    sh = [s for s in slots if s["src"] != "GFX"]
    assert not (out := [f"{s['line']} ({s['dur']:.1f}s)" for s in sh if not HARD_MIN <= s["dur"] <= HARD_MAX]), \
        f"shots outside {HARD_MIN}-{HARD_MAX:.0f}s (split a long '*' into a sequence) in ## " + ", ".join(out)
    warn = []
    if out := [f"{s['line']} ({s['dur']:.1f}s)" for s in sh if not SHOT_MIN <= s["dur"] <= SHOT_MAX]:
        warn.append(f"shots outside {SHOT_MIN}-{SHOT_MAX}s (fine for a hold or a flash when the footage reads) in ## " + ", ".join(out))
    flat = [f"{sh[k]['line']}-{sh[k + FLAT - 1]['line']}" for k in range(len(sh) - FLAT + 1)
            if max(d := [s["dur"] for s in sh[k:k + FLAT]]) - min(d) < FLAT_SPAN]
    if flat:
        warn.append(f"{FLAT} shots of the same length in a row (metronome?) in ## " + ", ".join(flat))
    return (sum(s["dur"] <= SHORT_T for s in sh) / len(sh), sum(s["dur"] >= LONG_T for s in sh) / len(sh), warn)


def check_opening(slots, mode="landscape"):
    """Spec check. landscape (legacy default): the film opens on a landscape held a little longer than the shots after it.
    action ('# OPENING action'): the first footage shot is a real event (an animal doing run/fight/attack/hunt/stalk/jump)
    and a wide/medium/aerial shot with an animal that places who is where starts within OPEN_WIDE_T s."""
    sh = [s for s in slots if s["src"] != "GFX"]
    if not sh:
        return
    o, f = sh[0], sh[0]["filter"]
    if mode == "action":
        assert f.get("sp", ["none"]) != ["none"] and set(f.get("act", [])) & OPEN_ACT, (
            f"## {o['line']}: OPENING action: the first shot needs sp=<animal> and act in {sorted(OPEN_ACT)}; now filter {f}")
        assert any(s["start"] <= OPEN_WIDE_T and s["filter"].get("sp", ["none"]) != ["none"]
                   and set(s["filter"].get("size", [])) & {"wide", "medium", "aerial"} for s in sh[1:]), (
            f"OPENING action: no wide/medium/aerial shot with an animal before {OPEN_WIDE_T:.0f}s that shows where "
            "predator, prey and the way out are")
        return
    longest = max((s["dur"] for s in sh[1:] if s.get("intro")), default=0.0)
    assert f.get("sp") == ["none"] and set(f.get("size", [])) & {"wide", "aerial"} and not set(f.get("size", [])) - {"wide", "aerial"} \
        and OPEN_MIN <= o["dur"] <= OPEN_MAX and o["dur"] > longest, (
        f"## {o['line']}: first shot must be a landscape (sp=none size=wide/aerial) of {OPEN_MIN:.0f}-{OPEN_MAX:.0f}s, "
        f"longer than every other intro shot ({longest:.1f}s); now {o['dur']:.1f}s, filter {f}")


def snap_intro(slots, intro, m, t_m, opening="landscape"):
    """Beat cuts in the intro (user 2026-10-17): every cut from the music entry t_m to the first story shot moves onto
    the intro music - nearest hit B3+ (stronger wins a near tie), else bar line, else beat. The A7 entry, cuts before
    it and the slot end never move; every shot keeps >= SHOT_MIN; the opening-shot rule still holds. -> summary."""
    ok = m["conf"] >= 0.15  # below: free tempo, the grid is noise, trust the hits only
    # ponytail: 0.15 checked on 2 trailers only (100 / 170 BPM right at conf 0.16 / 0.25); raise it if bars land off
    hits = [(e["t"] + t_m, e["level"]) for e in m["events"] if e["level"] >= 3]
    bars, bts = ([x + t_m for x in m["bars"]], [x + t_m for x in m["beats"]]) if ok else ([], [])
    last = next((k for k, s in enumerate(slots) if not s.get("intro")), len(slots) - 1)
    a7 = {s["start"] for s in slots if any(e["track"] == 7 for e in s["audio"])}
    kinds, shifts, left = Counter(), [], []
    for k in range(1, last + 1):
        p, s, b = slots[k - 1], slots[k], slots[k]["start"]
        if b <= t_m + 0.5 or b in a7:
            continue
        lo, hi = p["start"] + SHOT_MIN, b + s["dur"] - SHOT_MIN
        opts = ([(abs(t - b) - 0.05 * lv, f"hit B{lv}", t) for t, lv in hits if abs(t - b) <= HIT_WIN]
                or [(abs(t - b), "bar", t) for t in bars if abs(t - b) <= HIT_WIN]
                or [(abs(t - b), "beat", t) for t in bts if abs(t - b) <= BEAT_WIN])
        for _, kind, t in sorted(o for o in opts if lo <= o[2] <= hi):
            old = (p["dur"], s["start"], s["dur"])
            p["dur"], s["start"], s["dur"] = round(t - p["start"], 2), round(t, 2), round(b + s["dur"] - t, 2)
            try:
                check_opening(slots, opening)
            except AssertionError:
                p["dur"], s["start"], s["dur"] = old
                continue
            kinds[kind.split()[0]] += 1; shifts.append(abs(t - b))
            break
        else:
            left.append(f"##{s['line']} {tc(b)}")
    n = sum(kinds.values())
    return (f"{n}/{n + len(left)} intro cuts on the music (" + ", ".join(f"{k} {v}" for k, v in kinds.items())
            + f"), max shift {max(shifts, default=0):.2f}s" + (f"; not on a beat: {', '.join(left)}" if left else ""))


CUT_MIN, CUT_MAX, CUT_AIM = 1.0, 2.2, 1.6  # intro animal shots: pieces of 1.0-2.2 s on the music (user 2026-10-22)


def split_intro(slots, m, t_m):
    """Epic intro (user 2026-10-22, africa_1): every intro shot with an animal longer than CUT_MAX after the music
    entry is cut into pieces of CUT_MIN-CUT_MAX s, each cut on the music: a hit B3+ (bonus), a bar line, a beat
    (bonus smaller), else the plain CUT_AIM point. Pieces keep need + filter (highlights() fills each with another
    later chase / fight); the audio cues stay on the first piece. -> number of new cuts."""
    pts = [(e["t"] + t_m, 0.35) for e in m["events"] if e["level"] >= 3]
    if m["conf"] >= 0.15:
        pts += [(x + t_m, 0.2) for x in m["bars"]] + [(x + t_m, 0.1) for x in m["beats"]]
    out, n = [], 0
    for s in slots:
        out.append(s)
        if not s.get("intro") or s["filter"].get("sp", ["none"]) == ["none"] or s["src"] == "GFX" or s["start"] < t_m:
            continue
        while out[-1]["dur"] > CUT_MAX:
            p = out[-1]
            lo, hi = p["start"] + CUT_MIN, min(p["start"] + CUT_MAX, p["start"] + p["dur"] - CUT_MIN)
            c = [(abs(t - p["start"] - CUT_AIM) - w, t) for t, w in pts if lo <= t <= hi]
            t = round(min(c)[1] if c else p["start"] + min(CUT_AIM, p["dur"] / 2), 2)
            end = p["start"] + p["dur"]
            p["dur"] = round(t - p["start"], 2)
            out.append(dict(p, start=t, dur=round(end - t, 2), audio=[]))
            n += 1
    slots[:] = out
    for k, s in enumerate(slots, 1):
        s["slot"] = k
    return n


LAND_OUT, FADE_OUT, FADE_IN = 4.0, 1.5, 2.5  # s: last intro landscape, its fade to black, story 1's fade from black


def intro_outro(slots, music_end):
    """Intro ends with its music (user 2026-10-22, africa_1): the intro's last LAND_OUT s become one landscape that
    fades to black at the music end; story 1's first shot (a landscape) starts there and fades in from black, held
    until its own end. Intro shots after the landscape start are dropped, their audio cues move onto it. -> summary."""
    first = next((k for k, s in enumerate(slots) if not s.get("intro")), None)
    if first is None or first == 0:
        return "intro outro: no story after the intro"
    F = slots[first]
    end = min(music_end, F["start"])
    cut = end - LAND_OUT
    keep = [s for s in slots[:first] if s["start"] + CUT_MIN <= cut]
    if not keep:
        return "intro outro: intro shorter than the landscape, left as is"
    keep[-1]["dur"] = round(cut - keep[-1]["start"], 2)
    gone = slots[len(keep):first]
    land = {"line": gone[0]["line"] if gone else keep[-1]["line"], "start": round(cut, 2), "dur": LAND_OUT,
            "need": "Landscape kết intro, tối dần khi nhạc intro hết", "src": "real", "intro": True,
            "filter": {"sp": ["none"], "size": ["aerial", "wide"]},
            "audio": [e for s in gone for e in s["audio"] if e["track"] != 7],  # an A7 'off' there would cut the music
            "fade_out": FADE_OUT}
    story_land = F["filter"].get("sp") == ["none"]
    if story_land:
        F["dur"], F["start"] = round(F["start"] + F["dur"] - end, 2), round(end, 2)
        F["fade_in"] = FADE_IN
    slots[:] = keep + [land] + slots[first:]
    for k, s in enumerate(slots, 1):
        s["slot"] = k
    return (f"intro outro: intro music ends {tc(music_end)}; landscape {tc(cut)}-{tc(end)} fades out {FADE_OUT}s; "
            + (f"story 1 opens on its landscape from {tc(end)} ({F['dur']}s, fade in {FADE_IN}s)" if story_land else
               f"story 1's first shot is not a landscape (spec ## {F['line']}): no fade-in, write one first"))


def intro_beats(slots, intro, opening="landscape"):
    """Snap the intro cuts to the A7 music plan.py picked for the intro (its own track, placed from the file start)."""
    cue = next(((s["start"], e) for s in slots if s["start"] < intro for e in s["audio"]
                if e["track"] == 7 and e.get("status") == "OK"), None)
    if not cue:
        return "intro beat: no A7 music under the intro (spec: A7 cue on the first intro shot); cuts as written"
    t_m, e = cue
    try:  # whole track (<= 4 min): a slow 15 s opening alone gives no tempo
        m = beats.analyse(beats.decode(e["path"], 0, 240.0))
    except Exception as x:  # noqa: BLE001  ffmpeg / file trouble: the plan still works, cuts stay as written
        return f"intro beat: {Path(e['path']).name} not readable ({x}); cuts as written"
    msg = snap_intro(slots, intro, m, t_m, opening)
    msg = (f"intro beat: {Path(e['path']).name} {m['bpm']} BPM (conf {m['conf']}) from {tc(t_m)}; {msg}; "
           f"{split_intro(slots, m, t_m)} extra cuts on the music in animal shots (pieces {CUT_MIN}-{CUT_MAX}s)")
    return msg + "\n" + intro_outro(slots, t_m + e["dur"])  # place.py plays A7 from the file start, e['dur'] long


# ------------------------------------------------------------------ footage match
BLOCK = {"morph", "unnatural", "logo", "watermark", "text", "dark", "blur"}  # = organize.py BLOCK
SHOWN = {"logo", "watermark", "text"}  # on screen in every frame: a _check clip with these is never planned (delogo first)
ALTS = 4  # alternative clips per slot imported into the bins next to the chosen one (user 2026-10-21: options to swap)


def load_clips(region):
    """Tagged clips of the region's video roots only (user 2026-10-20: an Africa film never gets Amazon footage)."""
    clips = []
    for name, (root, kind, source) in video_roots(region).items():
        if not index_of(root).exists():  # root never scanned yet (e.g. D:\AI_video\_africa before its first clip)
            continue
        for cid, c in json.loads(index_of(root).read_text("utf-8"))["clips"].items():
            t = c.get("tags") or {}
            # _check = holding folder (clips organize kept back: morph/blur/dark/unsure). User 2026-10-21: planned too,
            # by their tags, but never above WEAK (yellow marker = look first) and never with a logo/text on screen
            held = c["path"].replace("\\", "/").startswith("_check/")
            if held and SHOWN & set(t.get("issues") or []):
                continue
            if t.get("caption"):
                c["hold"] = held
                c["abs"] = str(root / c["path"]); c["source"] = source; c["id"] = cid  # id = content hash, survives moves
                c["tags"]["species"] = [x.replace("_", " ") for x in c["tags"].get("species", [])]  # folder names
                clips.append(c)
    return clips


def usable(c):
    a, b = c["tags"].get("best") or [0, c["duration"]]
    if c["source"] == "ai":
        a, b = max(a, AI_TRIM), min(b, c["duration"] - AI_TRIM)
    y = c.get("yolo")
    if y and y["seen"] >= YOLO_SEEN:  # cut only where the subject is in frame (YOLO); low 'seen' = unreliable, ignored
        a, b = max(a, y["in"][0]), min(b, y["in"][1])
    return a, b


def yolo_pass(clips, cached=False):
    """Measure the candidate clips with YOLO (cached, local GPU), then trust its shot size over the tag.
    cached = cache only: --yolo-cached, and always for africa (4K ProRes on the NAS, africa_1: 6 h unfinished)."""
    try:
        import yolo
        new, sec = yolo.measure(clips, not cached)
    except ImportError as e:
        return f"yolo: skipped ({e}); tags only"
    n = 0
    for c in clips:
        y, t = c.get("yolo"), c["tags"]
        if not y or y["seen"] < YOLO_SEEN:
            continue
        n += 1
        if t.get("shot_size") != "aerial":
            t["shot_size"] = y["size"]
    return (f"yolo: {len(clips)} candidate clips, {new} measured now ({sec}s), {n} with subject window + measured size"
            + (" (cache only: unmeasured clips use tags only; yolo.py --warm measures them)" if cached else ""))


# Meaning of the shot text (Vietnamese) vs the clip caption (English): multilingual-e5-small of the memory gateway
# captions embedded once (cache keyed by clip id + caption). Ranking only (+-SEM_W/2 inside a band, rank_key);
# fit, the status and the hard filters are the tags' alone.
SEM_W = 0.04
SEM_LO, SEM_HI = 0.731, 0.805  # e5 cosine sim -> 0..1: demo_5 candidates p10 / p90 (2026-10-14)
SEM_CACHE = ROOT / ".work" / "doc_edit" / "caption_emb_e5small.npz"
SEM = {"need": {}, "clip": {}}  # need text -> unit vector, clip id -> unit vector; empty = semantic off


def need_text(need):
    return re.sub(r"\[[^\]]+\]\s*", "", need).strip()


def semantic(slots, clips):
    """Fill SEM for the slots' shot texts and the clips' captions. Any failure -> off (tags only)."""
    try:
        import numpy as np
        sys.path.insert(0, str(ROOT / ".work" / "tools"))
        from memory_gateway import embed
        old = dict(np.load(SEM_CACHE, allow_pickle=False)) if SEM_CACHE.exists() else {}
        keys = {c["id"]: f"{c['id']}|{c['tags']['caption']}" for c in clips}
        hit = {k: old[k] for k in keys.values() if k in old}
        todo = [c for c in clips if keys[c["id"]] not in hit]
        for i in range(0, len(todo), 256):
            part = todo[i:i + 256]
            for c, v in zip(part, embed([c["tags"]["caption"] for c in part], "passage")):
                hit[keys[c["id"]]] = np.asarray(v, dtype=np.float32)
        if todo:
            SEM_CACHE.parent.mkdir(parents=True, exist_ok=True)
            np.savez(SEM_CACHE, **hit)
        unit = lambda v: v / (np.linalg.norm(v) or 1.0)  # noqa: E731
        SEM["clip"] = {cid: unit(hit[k]) for cid, k in keys.items()}
        needs = sorted({need_text(s["need"]) for s in slots if s["src"] != "GFX"} - {""})
        SEM["need"] = {n: unit(np.asarray(v, dtype=np.float32)) for n, v in zip(needs, embed(needs, "query"))}
        return f"semantic: {len(needs)} shot texts vs {len(clips)} captions ({len(todo)} embedded now), +-{SEM_W / 2}"
    except Exception as e:  # noqa: BLE001
        SEM["need"], SEM["clip"] = {}, {}
        return f"semantic: off ({type(e).__name__}: {e}); tags only"


def sem_bonus(c, need):
    q, e = SEM["need"].get(need_text(need)), SEM["clip"].get(c.get("id"))
    if q is None or e is None:
        return 0.0
    x = min(1.0, max(0.0, (float(q @ e) - SEM_LO) / (SEM_HI - SEM_LO)))
    return SEM_W * (x - 0.5)


def clip_look(caption, green=None):
    """'desert' / 'green' / 'dry', None = mixed / unknown. desert from the caption; else the measured green share of
    the ground (ground_looks) when there is one; else the caption words (None = no look words or both)."""
    t = caption.lower()
    if re.search(LOOKS["desert"], t):
        return "desert"
    if green is not None:
        return "green" if green >= GREEN_MIN else "dry" if green <= DRY_MAX else None
    g, d = (bool(re.search(LOOKS[k], t)) for k in ("green", "dry"))
    return None if g == d else "green" if g else "dry"


LOOK_CACHE = ROOT / ".work" / "library" / "look.json"  # clip id -> green share of the ground in its tag sheet
SHEETS = ROOT / ".work" / "tag_source" / "sheets"
GREEN_MIN, DRY_MAX = 0.3, 0.1  # africa library 2026-10-22: captions 'dry' median 0.01 (p90 0.08), 'green' median 0.45


def green_share(p):
    """Green / (green + yellow-brown) of the vegetation pixels in the lower half of the 4 frames of a 2x2 tag sheet;
    None = too few vegetation pixels (water, sky, night)."""
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(p).convert("HSV").resize((240, 136)), dtype=np.float32)
    h, s, v = a[..., 0] * (360 / 255), a[..., 1] / 255, a[..., 2] / 255
    rows = np.zeros(h.shape, bool)
    rows[34:68] = rows[102:136] = True
    veg = rows & (s > 0.18) & (v > 0.15) & (v < 0.97)
    g, y = (veg & (h >= 65) & (h <= 165)).sum(), (veg & (h >= 18) & (h < 65)).sum()
    return round(float(g / (g + y)), 3) if g + y > 200 else None


def ground_looks(clips):
    """c['green'] for every clip with a tag sheet; new sheets are measured once (~90 clips/s) and cached."""
    cache = json.loads(LOOK_CACHE.read_text("utf-8")) if LOOK_CACHE.exists() else {}
    new = 0
    for c in clips:
        if c.get("id") not in cache and (SHEETS / f"{c.get('id')}.jpg").exists():
            cache[c["id"]] = green_share(SHEETS / f"{c['id']}.jpg"); new += 1
        c["green"] = cache.get(c.get("id"))
    if new:
        LOOK_CACHE.write_text(json.dumps(cache, sort_keys=True), "utf-8")
    n = Counter(clip_look(c["tags"]["caption"], c["green"]) for c in clips)
    return (f"ground look: {sum(c['green'] is not None for c in clips)} clips measured ({new} new); "
            f"green {n['green']}, dry {n['dry']}, desert {n['desert']}, mixed/unknown {n[None]}")


def trait(c, key, pats):
    """'female' / 'male' / 'young' / 'adult', 'mixed' (both in frame) or None (not visible): the tag when there."""
    v = c["tags"].get(key)
    if v and v != "unknown":
        return v
    hit = [k for k, p in pats.items() if re.search(p, c["tags"]["caption"], re.I)]
    return hit[0] if len(hit) == 1 else "mixed" if hit else None


def hard(c, f, own=True):
    """Story truth, before any score -> (reject reason or None, unsure traits ''/'sex'/'age'/'sex,age').
    own=False: the caller picked the species itself (fallback tiers); species not checked."""
    t = c["tags"]
    sp, cap = set(t.get("species", [])), t["caption"].lower()
    if own and "sp" in f:
        if f["sp"] == ["none"]:
            if sp and t.get("count") != "none":
                return "species", ""
        elif not set(f["sp"]) & sp:
            return "species", ""
    if any(x in sp or x.lower() in cap for x in f.get("no", [])):
        return "no", ""
    if any(w in cap for w in BIOME_NO):  # temperate scenery never passes for a tropical film
        return "biome", ""
    if "light" in f and ("night" in f["light"]) != (t.get("light") == "night"):
        return "night", ""
    if "look" in f and clip_look(t["caption"], c.get("green")) == "desert" and "desert" not in f["look"]:
        return "desert", ""
    acts = set(t.get("action") or [])
    if acts & set(f.get("xact", [])):
        return "xact", ""
    if not (set(f.get("sp", [])) - {"none"}) & sp:  # the slot's own animal is not in frame (scenery, companion)
        return None, ""
    out = t.get("outcome")  # tag-source vision field when there; older clips: caption words
    killed = out in ("catch", "kill") if out and out != "unknown" else bool(KILL.search(cap))
    if killed and "kill" not in f.get("out", []) and "eat" not in f.get("act", []):
        return "kill", ""
    if acts and acts <= STILL and acts_of(f.get("act", [])) & (STRIKE | {"hide"}):
        return "resting", ""
    unsure = []
    for k, pats in (("sex", SEX_CAP), ("age", AGE_CAP)):
        if k in f:
            v = trait(c, k, pats)
            if k == "age" and v is None:  # captions name calves / cubs when they are in frame (africa 2026-10-23:
                v = "adult"               # 375 of 445 wildebeest captions name no age = adult herds)
            if v in pats and v not in f[k]:
                return k, ""
            if v is None or (v == "mixed" and k == "sex"):  # age 'mixed' = mother + calf: the young is in frame
                unsure.append(k)
    return None, ",".join(unsure)


def fit(c, f, prev_size):
    why, unsure = hard(c, f)
    if why:
        return None
    t = c["tags"]
    lk = clip_look(t["caption"], c.get("green")) if "look" in f else None
    pts = mx = 0
    for k, w in (("act", 3), ("set", 2), ("size", 2), ("light", 1), ("mood", 1), ("cam", 1), ("ang", 1), ("dir", 1), ("count", 1)):
        if k not in f:
            continue
        mx += w
        v = t.get(TAG.get(k, k))
        have = set(v) if isinstance(v, list) else {v}
        if k == "set":
            pts += min(w, len(have & set(f[k])))
        elif have & (acts_of(f[k]) if k == "act" else set(f[k])):
            pts += w
        elif k == "act" and set(f[k]) & STRIKE and have & STRIKE:  # lunge / chase for an attack: close enough
            pts += w - 1
        elif k == "size" and v in SIZES and any(abs(SIZES.index(v) - SIZES.index(x)) == 1 for x in f[k] if x in SIZES):
            pts += 1
    if "kw" in f:
        mx += len(f["kw"])
        pts += sum(k.lower() in t["caption"].lower() for k in f["kw"])
    s = pts / mx if mx else 1.0
    s -= 0.15 * len(t.get("issues", [])) + (0.1 if not t.get("sure", True) else 0)
    if c.get("hold") or unsure:
        s = min(s, OK_FIT - 0.05)   # _check clip / sex or age not visible: never OK, the user looks at it first
    if set(f.get("act", [])) & STRIKE and not acts_of(t.get("action") or []) & STRIKE:
        s = min(s, OK_FIT - 0.05)   # no action in the clip: never OK
    s -= 0.1 if prev_size and t.get("shot_size") == prev_size else 0
    s -= LOOK_PEN if lk and lk not in f["look"] else 0
    return s


def overlaps(uses, x, d):
    """Earlier uses that showed any frame of the source range [x, x + d)."""
    return [u for u in uses if u[1] < x + d and u[2] > x]


def focus(c, s):
    """Clip time where the slot's action happens: mean time of the tag-sheet frames whose 'phase' (tag-source, action per
    frame 1-4) is one the slot asks for; None = no phase, no act, or no frame shows it (centre of the free part)."""
    ph, want = c["tags"].get("phase"), acts_of(s["filter"].get("act", []))
    t = [p * c["duration"] for p, x in zip(TAG_POS, ph or ()) if x in want]
    return sum(t) / len(t) if t and want else None


def window(c, s, uses, gap=None, mx=None):
    """In-point for slot s from clip c, or None (REUSE_* / SAME_* above). Uses from timeline Open (start -1e9) are
    never shown again; frames already on Edit may come back, up to SAME_MAX times in all, SAME_GAP s apart."""
    if len(uses) >= (mx or REUSE_MAX) or any(abs(s["start"] - t) < (gap or REUSE_GAP) for t, _, _ in uses):
        return None
    a, b = usable(c)
    lo, gaps = a, []
    for _, i, o in sorted(uses, key=lambda u: u[1]):
        gaps.append((lo, i - SRC_MARGIN)); lo = max(lo, o + SRC_MARGIN)
    gaps.append((lo, b))
    if (x := focus(c, s)) is not None and (fits := [g for g in gaps if g[1] - g[0] >= s["dur"]]):
        lo, hi = min(fits, key=lambda g: max(g[0] - x, x - g[1], 0))  # the free part nearest the asked action
        return round(min(max(x - s["dur"] / 2, lo), hi - s["dur"]), 2)
    lo, hi = max(gaps, key=lambda g: g[1] - g[0])
    if hi - lo >= s["dur"]:
        return round(lo + (hi - lo - s["dur"]) / 2, 2)
    best = None  # no unseen part long enough: the same frames again, the least repeated in-point first
    for x in sorted({round(i, 2) for _, i, _ in uses} | {round(a, 2), round(b - s["dur"], 2)}):
        if x < a or x + s["dur"] > b:
            continue
        ov = overlaps(uses, x, s["dur"])
        if len(ov) < SAME_MAX and all(t > -1e8 and abs(s["start"] - t) >= SAME_GAP for t, _, _ in ov)                 and (best is None or len(ov) < best[0]):
            best = (len(ov), x)
    return best and best[1]


def rank_key(x, need=None):
    """Real footage first whenever it fits OK; AI where real footage cannot fill the shot. The semantic bonus only
    reorders clips inside the same band (OK / not OK): the status (OK, WEAK, THIẾU) stays the tags' verdict."""
    v, c = x[0], x[1]
    b = sem_bonus(c, need) if need else 0.0
    return v >= OK_FIT, c["source"] == "real" and v >= OK_FIT, v + (0.05 if c["source"] == "real" else 0) + b


def match(slots, clips, taken=None, look=None):
    """taken: {lower-case path: [(src_in, src_out)]} already on timeline Open: same budget, never the same part.
    look ('# LOOK'): ground look of the first shot; after it each shot wants the look of the last green/dry shot
    (neighbours never jump green -> dry -> desert), a line's own look= wins; the look changes only where no clip
    of it fits better than LOOK_PEN."""
    uses, prev_size, cur = {}, None, [look]  # clip path -> [(timeline start, src_in, src_out)]
    last = {}  # line + screen direction of the shot just taken
    for c in clips:  # start -1e9: another timeline, so the REUSE_GAP check never applies to these
        if u := (taken or {}).get(c["abs"].lower()):
            uses[c["abs"]] = [(-1e9, a, b) for a, b in u]

    def take(s, c, cin, **kw):
        if (lk := clip_look(c["tags"]["caption"], c.get("green"))) in ("green", "dry"):
            cur[0] = lk
        uses.setdefault(c["abs"], []).append((s["start"], cin, cin + s["dur"]))
        if c.get("hold"):
            kw.setdefault("why", "_check: " + (",".join(c["tags"].get("issues") or []) or "sure=false"))
        if unsure := hard(c, s["filter"], own=False)[1]:
            note = f"kiểm tra {unsure}: " + "/".join(sorted({x for k in unsure.split(",") for x in s["filter"][k]}))
            kw["why"] = "; ".join(filter(None, (kw.get("why"), note)))  # shown in plan.md and the marker note
        last.update(line=s.get("line"), dir=c["tags"].get("direction"))
        s.update(path=c["abs"], id=c.get("id"), source=c["source"], src_in=cin, src_out=round(cin + s["dur"], 2),
                 caption=c["tags"]["caption"], reuse=len(uses[c["abs"]]),
                 same=len(overlaps(uses[c["abs"]][:-1], cin, s["dur"])), **kw)

    def rank(s, prev, skip=()):
        f = s["filter"]
        if want := f.get("look") or (cur[0] and [cur[0]]):
            f = {**f, "look": want}
            s["want_look"] = want
        cands = [c for c in clips if s["src"] in ("any", c["source"]) and c["abs"] not in skip]
        if "pin" in f:
            hits = [(c, w) for c in cands if f["pin"][0].lower() in c["abs"].lower()
                    and (w := window(c, s, uses.get(c["abs"], ()))) is not None]
            assert len(hits) == 1, f"slot {s['slot']}: pin {f['pin'][0]!r} -> {len(hits)} usable clips"
            return [(1.0, *hits[0])]
        # truth + fit first (cheap, rejects most clips on species), window only for the survivors: ~10x fewer calls
        # ponytail: greedy in timeline order; a later slot may lose a clip it fits better (plan.md 8.3 beam search)
        out, rej = [], Counter()
        flip = OPP.get(last.get("dir")) if last.get("line") == s.get("line") and set(f.get("act", [])) & MOVING else None
        for c in cands:
            if why := hard(c, f)[0]:
                rej[why] += why in TRUTH_WHY  # the slot's own animal, refused by a story rule: the THIẾU report says why
                continue
            if (v := fit(c, f, prev)) is not None and (w := window(c, s, uses.get(c["abs"], ()))) is not None:
                u = uses.get(c["abs"], ())
                v -= DIR_PEN if flip and c["tags"].get("direction") == flip else 0
                out.append((v - REUSE_PEN * len(u) - SAME_PEN * len(overlaps(u, w, s["dur"])), c, w))
        s["rej"] = {k: n for k, n in rej.items() if n}
        return sorted(out, key=lambda x: rank_key(x, s.get("need")), reverse=True)

    def split(s, prev):
        """No single clip is long enough: 2, then 3 parts of >= SHOT_MIN, each from a different clip."""
        for k in (2, 3):
            if s["dur"] / k < SHOT_MIN:
                return None
            cuts = [round(s["start"] + s["dur"] * j / k, 2) for j in range(k)] + [round(s["start"] + s["dur"], 2)]
            parts, used, p = [], set(), prev
            for j in range(k):
                q = dict(s, start=cuts[j], dur=round(cuts[j + 1] - cuts[j], 2), part=f"{j + 1}/{k}",
                         audio=s.get("audio", []) if j == 0 else [])  # audio cues stay on the first part
                r = rank(q, p, used)
                if not r or r[0][0] < WEAK_FIT:
                    break
                used.add(r[0][1]["abs"]); p = r[0][1]["tags"].get("shot_size")
                parts.append((q, *r[0]))
            else:
                return parts
        return None

    out, run = [], None  # run: (chain, clip, next src_in, status, fit) after a part of a '12x4 same' chain
    for s in slots:
        f = s["filter"]
        out.append(s)
        if s["src"] == "GFX" or f.get("pin") == ["none"]:
            s["status"] = "GFX" if s["src"] == "GFX" else "THIEU"
            prev_size = None
            continue
        ch = s.get("chain")
        if ch and run and run[0] == ch and run[2] + s["dur"] <= usable(run[1])[1] + 0.01:  # the action goes on
            take(s, run[1], run[2], status=run[3], fit=run[4])
            run = (ch, run[1], round(run[2] + s["dur"], 2), run[3], run[4])
            continue
        # first part of a chain: one clip with room for the whole remaining chain, else parts picked one by one
        # ponytail: each part counts as one use toward REUSE_MAX
        q = dict(s, dur=round(sum(x["dur"] for x in slots if x.get("chain") == ch and x["start"] >= s["start"]), 2)) if ch else s
        ranked = rank(q, prev_size)
        if q is not s:
            s["rej"] = q.get("rej", {})
            if not ranked or ranked[0][0] < WEAK_FIT:
                ranked, ch = rank(s, prev_size), None
        run = None
        s["top3"] = [f"{v:.2f} {Path(c['path']).name[:40]} — {c['tags']['caption']}" for v, c, _ in ranked[:3]]
        s["alts"] = [[c["abs"], c["source"]] for _, c, _ in ranked[:ALTS + 1]]  # place.py imports these (minus the chosen) too
        if not ranked or ranked[0][0] < WEAK_FIT:
            if "pin" not in f and (parts := split(s, prev_size)):
                out[-1:] = [q for q, *_ in parts]
                for q, v, c, cin in parts:
                    take(q, c, cin, status="OK" if v >= OK_FIT else "WEAK", fit=round(v, 2))
                prev_size = parts[-1][2]["tags"].get("shot_size")
                continue
            s["status"] = "THIEU"
            prev_size = None
            continue
        v, c, cin = ranked[0]
        prev_size = c["tags"].get("shot_size")
        take(s, c, cin, status="OK" if v >= OK_FIT else "WEAK", fit=round(v, 2))
        if ch:
            run = (ch, c, round(cin + s["dur"], 2), s["status"], s["fit"])
    if len(out) != len(slots):  # some slots became 2-3 shots
        slots[:] = out
        for n, s in enumerate(slots, 1):
            s["slot"] = n
    # second pass, after every strict match has taken its clip: THIẾU shots after FALLBACK_T take a related clip
    # (same species, any action) or a neutral side shot (scenery, insects, birds...), same light/setting/size.
    # Side shots only in narration pauses, within the SIDE_MAX budget, in runs of at most 2; else it stays THIẾU.
    # ponytail: budget handed out in timeline order, late THIẾU slots get none once it is spent
    side = [is_side(s) for s in slots]
    body = [(s, f) for s, f in zip(slots, side) if not s.get("intro")]
    budget = SIDE_MAX * sum(s["dur"] for s, _ in body if s["src"] != "GFX") - sum(s["dur"] for s, f in body if f)

    def run_len(i):  # side run this slot would join
        n, j = 1, i - 1
        while j >= 0 and side[j]:
            n, j = n + 1, j - 1
        j = i + 1
        while j < len(side) and side[j]:
            n, j = n + 1, j + 1
        return n

    for i, s in enumerate(slots):
        f = s["filter"]
        if s["status"] != "THIEU" or s["start"] < FALLBACK_T or f.get("pin") == ["none"]:
            continue
        soft = {k: v for k, v in f.items() if k in ("size", "light", "set", "mood", "cam", "ang", "no", "look")}
        want = set(f.get("sp", [])) - {"none"}
        side_ok = not s.get("vo") and s["dur"] <= budget and run_len(i) <= 2  # never a cutaway over a narrated character line
        best = None
        for c in clips:
            if s["src"] not in ("any", c["source"]) or hard(c, f, own=False)[0] \
                    or (w := window(c, s, uses.get(c["abs"], ()))) is None:  # other action, never a contradicting one
                continue
            related =bool(want & set(c["tags"].get("species", [])))
            if not related and not (side_ok and ((c.get("subject") or "").lower() in NEUTRAL
                                                 or c["tags"].get("count") == "none")):
                continue
            v = fit(c, {**soft, "light": f["light"]} if "light" in f else soft, None)
            if v is None:
                continue
            v += (0.3 if related else 0) + (0.05 if c["source"] == "real" else 0) - REUSE_PEN * len(uses.get(c["abs"], ()))
            if best is None or v > best[0]:
                best = (v, c, related, w)
        if best and best[0] >= FALLBACK_FIT:
            v, c, related, cin = best
            if not related:
                side[i] = True; budget -= s["dur"]
            take(s, c, cin, status="FALLBACK", fit=round(v, 2),
                 why="same species, other action" if related else "side shot")
    if LATE_SUB:  # --late-sub: still THIẾU after LATE_SUB_T -> best substitute, tiers: same species (any look) >
        # companion species of the same scene > neutral scenery; user-requested, marked FALLBACK "late substitute"
        for s in slots:
            f = s["filter"]
            if s["status"] != "THIEU" or s["start"] < LATE_SUB_T or s["src"] == "GFX" or f.get("pin") == ["none"]:
                continue
            want = set(f.get("sp", [])) - {"none"}
            tiers = [want, {x for w in want for x in LATE_COMPANION.get(w, ())}, None]
            light = {"light": f["light"]} if "light" in f else {}
            for tier in tiers:
                best = None
                for c in clips:
                    if s["src"] not in ("any", c["source"]) or hard(c, f, own=False)[0] or \
                            (w := window(c, s, uses.get(c["abs"], ()), SUB_GAP, SUB_MAX)) is None:
                        continue
                    sp = set(c["tags"].get("species", []))
                    if tier is None:
                        if not ((c.get("subject") or "").lower() in NEUTRAL or c["tags"].get("count") == "none"):
                            continue
                    elif not tier or not tier & sp:
                        continue
                    if (v := fit(c, {**{k: x for k, x in f.items() if k in ("size", "set", "mood", "cam", "ang", "look", "no")},
                                     **light}, None)) is None:
                        continue
                    v -= REUSE_PEN * len(uses.get(c["abs"], ()))
                    if best is None or v > best[0]:
                        best = (v, c, w)
                if best:
                    v, c, cin = best
                    take(s, c, cin, status="FALLBACK", fit=round(v, 2), why="late substitute")
                    break

# ------------------------------------------------------------------ intro highlights (user 2026-10-22, africa_1)
HL_ACT = {"run", "fight", "attack", "hunt", "jump", "chase", "charge"}  # what a teaser shows: chases and fights
HL_SPEEDS = (1.4, 1.5, 1.36, 1.45)  # intro highlights play at 136-150 %, varied shot to shot
HL_NO = ("carcass", "meat", "kill", "dead", "eats", "eating", "feeding")  # the teaser shows the chase, not the meal


def highlights(slots, clips):
    """Intro shots with an animal show the film's later moments: the frames of an OK story shot of the same species
    (chase / fight first) >= SAME_GAP s later, sped up to HL_SPEEDS. Same-frame cap (SAME_MAX) still holds; each story
    shot and each clip feeds the intro once; no fitting story shot -> the intro keeps its own pick."""
    by = {c["abs"]: c for c in clips}
    uses = {}
    for s in slots:
        if s.get("path"):
            uses.setdefault(s["path"], []).append((s["start"], s["src_in"], s["src_out"], s["slot"]))
    acts = lambda s: set(by[s["path"]]["tags"].get("action") or [])  # noqa: E731  what the clip shows, not what was asked
    later = [s for s in slots if not s.get("intro") and s.get("status") == "OK" and s.get("path") in by]
    took, n = set(), 0
    for s in slots:
        want = set(s["filter"].get("sp", [])) - {"none"}
        if not s.get("intro") or not want or s["src"] == "GFX" or "pin" in s["filter"] or s.get("chain"):
            continue  # a '... same' chain keeps its one continuous clip
        v = HL_SPEEDS[n % len(HL_SPEEDS)]
        need = round(s["dur"] * v, 2)
        own = [u for u in uses.get(s.get("path"), ()) if u[3] != s["slot"]]
        best = None
        # tiers: the line's own species only (user 2026-10-23, input/plan.md: a teaser previews later threats, never
        # another animal standing in; the 2026-10-22 KIN / any-species tiers are gone): its chase / fight first, else
        # its calm footage; a line asking a calm act keeps calm footage. The intro line's sex / age / no= / kill hold.
        ask = set(s["filter"].get("act") or [])
        tiers = [(want, True), (want, False)] if not ask or ask & HL_ACT else [(want, False)]
        for tier, act_only in tiers:
            for L in later:
                c = by[L["path"]]
                cap, sp = c["tags"]["caption"].lower(), set(c["tags"].get("species", []))
                if L["start"] - s["start"] < SAME_GAP or L["slot"] in took or L["path"] in took \
                        or not tier & sp or (act_only and not acts(L) & HL_ACT) \
                        or any(w in cap for w in HL_NO) or hard(c, s["filter"])[0]:
                    continue
                a, b = usable(c)
                x = round(min(L["src_in"], b - need), 2)
                if x < a:
                    continue
                u = [w for w in uses.get(L["path"], ()) if w[3] != s["slot"]]
                ov = [w for w in u if w[1] < x + need and w[2] > x]
                if len(ov) >= SAME_MAX or any(abs(w[0] - s["start"]) < SAME_GAP for w in ov) \
                        or any(abs(w[0] - s["start"]) < REUSE_GAP for w in u if w not in ov):
                    continue
                k = (bool(acts(L) & HL_ACT), bool(set(s["filter"].get("act") or []) & acts(L)), c["source"] == "real", L["fit"])
                if best is None or k > best[0]:
                    best = (k, L, x, len(ov), len(u))
            if best:
                break
        if not best:
            continue
        _, L, x, same, ru = best
        c = by[L["path"]]
        if s.get("path"):
            uses[s["path"]] = own
        uses.setdefault(L["path"], []).append((s["start"], x, x + need, s["slot"]))
        took |= {L["slot"], L["path"]}
        n += 1
        unsure = hard(c, s["filter"])[1]
        s.update(path=L["path"], id=c.get("id"), source=c["source"], src_in=x, src_out=round(x + need, 2),
                 caption=c["tags"]["caption"], status="WEAK" if unsure else "OK", fit=L["fit"], reuse=ru + 1,
                 same=same, speed=v, highlight=L["slot"])
        s.pop("part", None); s.pop("why", None); s.pop("zoom", None)
        if unsure:
            s["why"] = f"kiểm tra {unsure}"
    hl = [s for s in slots if s.get("highlight")]
    empty = [tc(s["start"]) for s in slots if s.get("intro") and s["src"] != "GFX" and s.get("status") == "THIEU"]
    return (f"intro highlights: {len(hl)} of {sum(1 for s in slots if s.get('intro') and set(s['filter'].get('sp', [])) - {'none'})} "
            f"animal intro shots show later story shots of their own species at {min(HL_SPEEDS):.0%}-{max(HL_SPEEDS):.0%} "
            f"({sum(bool(acts(s) & HL_ACT) for s in hl)} chase/fight); intro THIẾU left: {', '.join(empty) or 'none'}")


# ------------------------------------------------------------------ zoom + speed (user 2026-10-22, africa_1)
TL_FPS = 24.0
SLOW_ACT = {"rest", "look", "walk", "eat", "drink", "swim", "perch", "sleep", "groom", "call", "fly", "none"}
SLOW_MIN, SLOW_EVERY = 0.4, 20.0  # true slow motion (<= 50 %): never slower than 40 %, one per 20 s at most
ZOOMS = (1.0, 1.2, 1.0, 1.12, 1.0, 1.25)  # n-th use of one clip: every other reuse gets a crop; same frames always
ZOOM_EVERY = 5                    # fresh clips: every 5th eligible shot gets ZOOM_FRESH
ZOOM_FRESH, FAST, FAST_EVERY = 1.15, 1.2, 2  # aerial scenery: every 2nd one 120 %


def vary(slots, clips):
    """Speed and zoom per placed shot, by rules (place.py applies them; plan.md marks ⏱ / 🔍):
    - speed: real clips shot above 25 fps play frame-exact at 24/fps (30 fps -> 80 %, 60 fps -> 40 %, floor 40 %) on
      shots without a strike action; below 50 % only on calm holds >= 3 s, one per SLOW_EVERY s, never in the hook.
      Aerial scenery of >= 4 s: every 2nd one at 120 % when the clip has the frames. AI clips and strikes stay 100 %.
    - zoom: 4K sources only, never on close-ups (the subject would be cut): every other reuse of a clip and every
      repeat of the same frames gets another crop (ZOOMS by use), fresh clips every ZOOM_EVERY-th eligible shot.
    Source used = dur * speed, so slow motion also saves footage."""
    by = {c["abs"]: c for c in clips}
    last_slow, n_zoom, n_fast, prev = -1e9, 0, 0, {}
    cnt = Counter()
    for s in slots:
        c = by.get(s.get("path"))
        if not c or s.get("status") not in ("OK", "WEAK", "FALLBACK"):
            continue
        f, t = s["filter"], c["tags"]
        acts = set(f.get("act") or []) | set(t.get("action") or [])
        size = (c.get("yolo") or {}).get("size") if (c.get("yolo") or {}).get("seen", 0) >= YOLO_SEEN else None
        size = size or t.get("shot_size")
        fps = float(c.get("fps") or TL_FPS)
        sp = s.get("speed", 1.0) if s.get("highlight") else 1.0  # highlights(): speed set already
        if s.get("highlight"):
            pass
        elif c["source"] == "real" and fps > 25.5 and not acts & STRIKE and s["dur"] >= 2.0 and not s.get("intro"):
            sp = max(SLOW_MIN, round(TL_FPS / fps, 4))
            if sp <= 0.5 and not (s["dur"] >= 3.0 and acts <= SLOW_ACT and s["start"] - last_slow >= SLOW_EVERY):
                sp = 1.0
        elif c["source"] == "real" and f.get("sp") == ["none"] and size == "aerial" and s["dur"] >= 4.0:
            n_fast += 1
            if n_fast % FAST_EVERY == 0 and s["src_in"] + s["dur"] * FAST <= usable(c)[1]:
                sp = FAST
        if s.get("chain") and prev.get("chain") == s["chain"] and prev.get("path") == s["path"]:
            sp = prev.get("speed", 1.0)  # '... same' chain: one speed, each part starts where the last one ended
            s["src_in"] = prev["src_out"]
            s["src_out"] = round(s["src_in"] + s["dur"] * sp, 2)
        prev = s
        if sp != 1.0:
            s["speed"] = sp
            s["src_out"] = round(s["src_in"] + s["dur"] * sp, 2)
            last_slow = s["start"] if sp <= 0.5 else last_slow
            cnt["intro highlight" if s.get("highlight") else "slow-mo <= 50%" if sp <= 0.5 else "fast" if sp > 1
                else "frame-exact 24/fps"] += 1
        if int(c.get("width") or 0) >= 3840 and size not in ("close_up", "extreme_close") and s["slot"] > 1:
            z = ZOOMS[(s.get("reuse", 1) - 1) % len(ZOOMS)] if s.get("reuse", 1) > 1 else None
            if s.get("same") and z == 1.0:  # the same frames again must not look like the same shot
                z = 1.18
            if z is None:
                n_zoom += 1
                z = ZOOM_FRESH if n_zoom % ZOOM_EVERY == 0 else 1.0
            if z != 1.0:
                s["zoom"] = z
                cnt["zoom"] += 1
    return "variety: " + ", ".join(f"{k} {v}" for k, v in sorted(cnt.items())) +         f" (of {sum('path' in s for s in slots)} shots; same frames again: {sum(bool(s.get('same')) for s in slots)})"


# ------------------------------------------------------------------ audio match
# English keywords for folders of the read-only roots (Vietnamese names, mood folders); matched on the lowercase path
EN_WORDS = {"mưa": "rain", "gió": "wind", "lửa": "fire", "nước chảy": "water stream river", "chim": "bird birds",
            "cỏ khô": "grass leaves rustle", "bước chân": "footsteps walk run", "thở": "breathing breath growl",
            "gầm": "growl", "uống nước": "drinking lapping", "dưới nước": "water swim splash crossing",
            "ăn thịt": "eating carnivore bite", "xé xác": "eating carnivore bite", "gặm cỏ": "eating herbivore",
            "gặm xương": "eating bone crunch", "báo săn": "cheetah big cat", "leopard": "leopard big cat attack",
            "cá sấu": "crocodile caiman", "hà mã": "hippo", "hươu cao cổ": "giraffe", "kền kền": "vulture",
            "linh cẩu": "hyena", "linh dương": "antelope", "ngựa vằn": "zebra", "rắn": "snake", "sư tử": "lion",
            "voi": "elephant", "đại bàng": "eagle", "cheetah": "big cat", "crocodile": "caiman", "dondap_kichtinh": "chase action epic intense",
            "rinhrap_nguyhiem": "tense danger stalk suspense", "emdiu_thugian": "calm gentle peaceful",
            "trungtinh_quansat": "neutral observe", "bian_khampha": "mystery explore wonder"}
CATEGORY = {"sfx": "Nature_sound", "sound": "music"}  # read-only roots -> AUDIO_POOL category (new audio root -> add it)
# Foley / SFX (A6, A8, A9) never substitute (user rule 2026-10-11): every keyword must hit, and a file naming an
# animal is only used on a slot of that animal or a close relative (no house-fly wings on an eagle, no hoof
# footsteps on a jaguar). No such file -> audio THIẾU, reported in the plan reply; the user downloads one or drops it.
STRICT = {6, 8, 9}
ANIMALS = set("fly insect insects bee wasp mosquito cricket crickets cicada frog bird birds parrot macaw owl eagle "
              "hawk raptor vulture baboon monkey primate ape chimp gorilla antelope deer giraffe zebra cheetah leopard "
              "lion tiger cat hyena wolf dog elephant hippo horse hoof cow pig boar crocodile alligator caiman snake "
              "carnivore herbivore whale dolphin seal otter capybara peccary jaguar anaconda fish rodent "
              "wildebeest buffalo rhino ostrich jackal warthog".split())
KIN = {"jaguar": "cat cheetah leopard lion tiger carnivore", "peccary": "pig boar hoof herbivore",
       "capybara": "herbivore rodent", "otter": "carnivore", "giant otter": "otter carnivore",
       "caiman": "crocodile alligator carnivore", "alligator": "crocodile caiman carnivore", "anaconda": "snake",
       "harpy eagle": "eagle bird birds raptor hawk carnivore", "capuchin monkey": "monkey primate",
       "capuchin": "monkey primate", "fish": "fish", "macaw": "parrot bird birds",
       "scarlet macaw": "macaw parrot bird birds", "tayra": "marten carnivore",
       # Africa (2026-10-20)
       "lion": "cat carnivore", "leopard": "cat carnivore", "cheetah": "cat carnivore",
       "hyena": "carnivore", "spotted hyena": "hyena carnivore", "wild dog": "dog carnivore", "jackal": "dog carnivore",
       "zebra": "horse hoof herbivore", "wildebeest": "antelope hoof herbivore", "impala": "antelope hoof herbivore",
       "gazelle": "antelope hoof herbivore", "springbok": "antelope hoof herbivore", "kudu": "antelope hoof herbivore",
       "cape buffalo": "buffalo cow hoof herbivore", "warthog": "pig boar hoof herbivore", "giraffe": "hoof herbivore",
       "elephant": "herbivore", "hippo": "herbivore", "rhino": "herbivore", "crocodile": "caiman alligator carnivore",
       "vulture": "bird birds raptor", "eagle": "bird birds raptor hawk", "ostrich": "bird birds",
       "baboon": "monkey primate herbivore",  # grazing warthog / baboon: herbivore chewing (2026-10-24)
       # africa_1 (2026-10-21): tag variants seen in the Africa library + its waterbirds
       "african wild dog": "wild dog dog carnivore", "lioness": "lion cat carnivore",
       "red lechwe": "antelope hoof herbivore", "lechwe": "antelope hoof herbivore",
       "heron": "bird birds", "egret": "bird birds", "cattle egret": "bird birds", "stork": "bird birds",
       "marabou stork": "bird birds", "yellow-billed stork": "bird birds", "fish eagle": "eagle bird birds raptor",
       # 2026-10-24: tagged species with no kin had no sound at all although relatives' files exist
       "thomson's gazelle": "gazelle antelope hoof herbivore", "blesbok": "antelope hoof herbivore",
       "nyala": "antelope hoof herbivore", "eland": "antelope hoof herbivore", "topi": "antelope hoof herbivore",
       "gemsbok": "antelope hoof herbivore", "hartebeest": "antelope hoof herbivore", "tapir": "hoof herbivore",
       "red river hog": "pig boar hoof herbivore", "serval": "cat carnivore", "ocelot": "cat carnivore",
       "bush dog": "dog carnivore", "banded mongoose": "carnivore", "gorilla": "ape primate",
       "chimpanzee": "chimp ape primate", "spider monkey": "monkey primate", "howler monkey": "monkey primate",
       "toucan": "bird birds", "hummingbird": "bird birds", "songbird": "bird birds", "guineafowl": "bird birds",
       "python": "snake", "forest buffalo": "buffalo cow hoof herbivore", "buffalo": "cow hoof herbivore",
       "caracal": "cat carnivore"}


def kin(sp):
    """Animal words a sound file may name on a slot of these species."""
    return {w for x in sp if x != "none" for w in (x + " " + KIN.get(x, "")).split()}


def load_audio():
    out = []
    for name, (root, kind, _) in ROOTS.items():
        if kind != "audio":
            continue
        for a in json.loads(index_of(root).read_text("utf-8"))["clips"].values():
            if audio_blocked(a["path"]):
                continue
            low = a["path"].lower()
            a["abs"] = str(root / a["path"])
            a["category"] = CATEGORY.get(name, a.get("category"))
            a["words"] = " ".join(re.split(r"[^a-z0-9]+", low) + [w for k, w in EN_WORDS.items() if k in low])
            out.append(a)
    return out


def match_audio(slots, lib, end):
    a7 = [(s["start"], e) for s in slots for e in s["audio"] if e["track"] == 7]
    for (t0, e), (t1, _) in zip(a7, a7[1:] + [(end, None)]):
        e["span"] = round(t1 - t0, 2)  # music plays until the next A7 entry
    used, last_music = Counter(), None
    for s in slots:
        for e in s["audio"]:
            if e["kw"] == ["off"]:
                continue

            def key(a):  # most keyword hits, then least used (variety); music (user 2026-10-24: the best fit, never
                # by how often a track was used): mood words, covers its span, closest length
                k = (sum(w in a["words"] for w in e["kw"]),)
                return k + (a["duration"] >= e["span"], -abs(a["duration"] - e["span"])) if "span" in e \
                    else k + (-used[a["abs"]],)
            pool = [a for a in lib if a["category"] in AUDIO_POOL[e["track"]]]
            if e["track"] == 7 and len(pool) > 1:  # never the same track twice in a row (edit-grammar)
                pool = [a for a in pool if a["abs"] != last_music]
            if e["track"] in (3, 4, 5):  # a bed / layer loops with 4 s crossfades: a 2 s bird call is a SFX, not a bed
                pool = [a for a in pool if a["duration"] >= BED_MIN]
                if "water" not in e["kw"]:  # no water file under a bed that is not about water
                    pool = [a for a in pool if not {"water", "river", "stream", "waterfall", "creek", "brook", "rain"} & set(a["words"].split())]
                if "birds" not in e["kw"]:  # user 2026-10-22: no birdsong in a bed that did not ask for birds
                    pool = [a for a in pool if "bird" not in a["words"]]
                # shared_* = foley of one action (steps, entering water), under_water, rain: never a bed (africa_1 2026-10-22)
                pool = [a for a in pool if not {"shared", "underwater", "under", "rain"} & set(a["words"].split())]
            if e["track"] in STRICT:
                ok = kin(s.get("filter", {}).get("sp", []))
                pool = [a for a in pool if all(w in a["words"] for w in e["kw"]) and set(a["words"].split()) & ANIMALS <= ok]
            a = max(pool, key=key, default=None)
            if not a or key(a)[0] <= 0:
                e["status"] = "THIEU"
                continue
            used[a["abs"]] += 1
            if e["track"] == 7:
                last_music = a["abs"]
            e.update(status="OK", path=a["abs"], dur=a["duration"])


WATER_SET = {"river", "riverbank", "lake", "swamp", "waterhole", "underwater"}
WATER_CAP = re.compile(r"\b(water|river|stream|lake|splash\w*|wade\w*|wading|flood\w*|marsh|swamp|waterfall|pond|waterhole|drinks?|drinking|puddle)\b", re.I)
WATER_MIN = 0.5  # share of the footage time under a water sound that must show water


def shows_water(c):
    return bool(WATER_SET & set(c["tags"].get("setting", [])) or WATER_CAP.search(c["tags"]["caption"]))


def fix_water(slots, clips, lib, end):
    """Water sound only over water pictures (user 2026-10-22: small-river on dry savanna). A3/A5 cue: its span (until
    the next cue of the track) must show water for >= WATER_MIN of the footage time; A6: its slot. Else 'water' ->
    'wind' (A3) / the cue is dropped (A5, A6) and the audio is matched again. -> summary."""
    by = {c["abs"]: c for c in clips}
    wet = lambda s: shows_water(by[s["path"]]) if s.get("path") in by else False  # noqa: E731
    fixed = dropped = 0
    for tr in (3, 5, 6):
        cues = [(s, e) for s in slots for e in s["audio"] if e["track"] in ((3, 4) if tr == 3 else (tr,)) and e["kw"] != ["off"]]
        for i, (s, e) in enumerate(cues):
            if "water" not in e["kw"] and not (e.get("path") and re.search(r"water|river|stream|brook|creek|waterfall", e["path"], re.I)):
                continue
            t1 = cues[i + 1][0]["start"] if tr != 6 and i + 1 < len(cues) else (s["start"] + s["dur"] if tr == 6 else end)
            sp = [x for x in slots if s["start"] <= x["start"] < t1 and x["src"] != "GFX"]
            if sum(x["dur"] for x in sp if wet(x)) >= WATER_MIN * max(sum(x["dur"] for x in sp), 1e-6):
                continue
            if tr == 3:
                e["kw"] = [("wind" if w == "water" else w) for w in e["kw"]] if "water" in e["kw"] else e["kw"] + ["wind"]
                e["kw"] = list(dict.fromkeys(e["kw"]))
                fixed += 1
            elif tr == 5:  # an 'off' entry ends the previous A5 layer here instead of letting it run on
                e.update(kw=["off"]); e.pop("path", None); e.pop("status", None); dropped += 1
            else:
                s["audio"].remove(e); dropped += 1
    if fixed:
        match_audio(slots, lib, end)  # again: same order and ranking, only the changed keywords pick another file
    return f"water sounds only over water: {fixed} beds -> wind, {dropped} A5/A6 layers dropped"


def audio_stats(slots, end):
    """One stdout line the agent can judge the sound design from without opening anything."""
    es = [e for s in slots for e in s["audio"] if e.get("status") == "OK"]
    mus = [e for e in es if e["track"] == 7]
    cover = sum(min(e["dur"], e["span"]) for e in mus) / end
    short = sum(e["span"] - e["dur"] > 3 for e in mus)
    n = Counter(e["track"] for e in es)
    return (f"audio: music {cover:.0%} of the film ({len(mus)} cues, {short} end > 3 s before the next cue), "
            f"SXF {n[8] + n[9]}, natural {n[6]}, bed changes {n[3] + n[4]}, A5 layers {n[5]}")


# ------------------------------------------------------------------ output
def write_md(path, title, slots):
    cnt = Counter(s["status"] for s in slots)
    md = [f"# Plan — {title}\n",
          f"{len(slots)} shot · {tc(slots[-1]['start'] + slots[-1]['dur'])} · "
          + " · ".join(f"{k} {cnt[k]}" for k in ("OK", "WEAK", "FALLBACK", "THIEU", "GFX")) + "\n",
          "| # | câu | giờ | dài | VO | shot cần | clip | fit | audio |", "|---|---|---|---|---|---|---|---|---|"]
    for s in slots:
        talk = "●" if s.get("vo") else ""
        clip = {"OK": "", "WEAK": "⚠ ", "FALLBACK": "↪ ", "THIEU": "**THIẾU**", "GFX": "GFX"}[s["status"]]
        if "path" in s:
            clip += f"{s['caption']} `{Path(s['path']).name[:30]}`" + (f" ↻{s['reuse']}" if s.get("reuse", 1) > 1 else "") + (" =frame" if s.get("same") else "") + (f" ★#{s['highlight']}" if s.get("highlight") else "")                     + (f" ⏱{s['speed'] * 100:.0f}%" if s.get("speed", 1) != 1 else "") + (f" 🔍{s['zoom']}" if s.get("zoom", 1) != 1 else "")                     + (f" ⧉{s['part']}" if "part" in s else "") + (" ⛓" if s.get("chain") else "") \
                    + (f" ({s['why']})" if re.search(r"_check|kiểm tra", str(s.get("why", ""))) else "")
        elif s.get("rej"):  # THIẾU although the animal is in the library: what the story rules refused
            clip += " (loại: " + ", ".join(f"{k} {n}" for k, n in s["rej"].items()) + ")"
        aud = " · ".join(f"A{e['track']} " + (Path(e["path"]).stem[:25] if e.get("status") == "OK"
                         else "off" if e["kw"] == ["off"] else f"**THIẾU** {','.join(e['kw'])}") for e in s["audio"])
        md.append(f"| {s['slot']} | {s['line']} | {tc(s['start'])} | {s['dur']:.1f} | {talk} | {s['need']} | {clip} "
                  f"| {s.get('fit', '')} | {aud} |")
    path.write_text("\n".join(md) + "\n", "utf-8")


def same_project(name, video):
    """Resolve project of <video>: its name, or the channel form 'c2_africa1' for folder africa_1 (c2_amazon2 ...)."""
    norm = lambda x: re.sub(r"^c\d+_", "", x.lower()).replace("_", "")  # noqa: E731
    return name.lower() == video.lower() or norm(name) == video.lower().replace("_", "")


def open_uses(video):
    """Parts of clips on timeline Open of Resolve project <video> (must be the open one; nothing is switched)."""
    try:
        from dvr_cowork.config import load_config
        from dvr_cowork.resolve_conn import connect
        pr = connect(load_config()).GetProjectManager().GetCurrentProject()
        if not pr or not same_project(pr.GetName(), video):
            return {}, f"open: not read (Resolve project {pr and pr.GetName()!r} is not {video!r}); Open parts not reserved"
        u = ledger.timeline_uses(pr, "Open")
    except Exception as e:  # noqa: BLE001  Resolve closed: plan still works, says so
        return {}, f"open: not read ({e}); Open parts not reserved"
    return u, f"open: {sum(map(len, u.values()))} parts of {len(u)} clips on timeline Open reserved (same reuse budget)"


def estimate_vo(cues):
    """(start, end) speech span per sentence from its word count, ending >= 0.3 s before the next sentence."""
    nxt = [c.t for c in cues[1:]] + [float("inf")]
    return [(c.t, max(c.t + 0.5, min(c.t + len(c.text.split()) / WPS, n - 0.3))) for c, n in zip(cues, nxt)]


def narration(folder, wait=True):
    """-> (cues, voice spans (start, end) per sentence, message): measured by vo-sync when the audio exists.
    wait=False (story.py): vo-sync not finished yet -> estimated spans instead of stopping."""
    ts = [p for p in folder.glob("*.md") if "timestamp" in p.name.lower()]
    assert len(ts) == 1, f"need exactly one *timestamp*.md in {folder}, found {[p.name for p in ts]}"
    cues = parse_timestamp_file(ts[0])
    audio = [p for p in folder.iterdir() if p.suffix.lower() in (".mp3", ".wav")]
    assert len(audio) <= 1, f"several narration audios in {folder}"
    if (folder / "mp3").is_dir():  # one file per sentence (user 2026-10-16): vo-sync job <video>_mp3
        audio = [folder / "mp3"]
        job = f"{folder.parent.name}_mp3"
    else:
        job = audio and audio[0].stem
    vp = ROOT / ".work" / str(job) / "plan.json"
    if audio and not wait and not vp.exists():
        audio = []
    if audio:  # measured speech spans: vo-sync analyze/run output (narration job A)
        assert vp.exists(), f"{vp} not there yet: vo-sync (narration) has not finished Whisper; wait for it, re-run"
        vplan = json.loads(vp.read_text("utf-8"))
        vo = [(s["ts"], s["ts"] + s["src_out"] - s["src_in"]) for s in vplan["segments"]]
        assert len(vo) == len(cues), "vo-sync plan.json and timestamp file disagree; re-run vo-sync"
        vmsg = "narration: measured (vo-sync)"
    else:  # no audio yet (user 2026-10-16: plan + prompts before the narration exists)
        vo = estimate_vo(cues)
        vmsg = f"narration: no audio yet, spans estimated at {WPS} words/s (VO ● approximate; /doc-edit plan after vo-sync = exact)"
    return cues, vo, vmsg


def main(folder, sem=True):
    folder = Path(folder)
    cues, vo, vmsg = narration(folder)
    video = folder.parent
    work = ROOT / ".work" / "doc_edit" / video.name
    spec = Path(SPEC) if SPEC else work / "spec.txt"
    assert spec.exists(), f"write {spec} first"
    end, intro, blocks = parse_spec(spec.read_text("utf-8"))
    region = spec_region(spec.read_text("utf-8"))
    end = end or vo[-1][1] + 2.0
    assert end > vo[-1][1], f"END {tc(end)} is before the last sentence ends ({tc(vo[-1][1])})"
    meta = spec_meta(spec.read_text("utf-8"), end, intro)
    cut = [f"STORY {k} at {tc(t)}" for k, t in meta["stories"] if any(a < t < b for a, b in vo)]
    assert not cut, f"{', '.join(cut)} falls inside a voice cue; move it to a pause or a cue start"

    slots = build([c.t for c in cues], end, blocks, intro)
    story_rules(slots, meta)
    clips = load_clips(region)
    looks = meta["look"] or any("look" in s["filter"] for s in slots)
    lmsg = ground_looks(clips) if looks else "ground look: off (no # LOOK / look=)"
    errs, side_share, short, long_, rwarn = [], 0, 0, 0, []
    try:
        side_share = check_side(slots)
    except AssertionError as e:
        errs.append(str(e))
    try:
        short, long_, rwarn = check_rhythm(slots)
    except AssertionError as e:
        errs.append(str(e))
    try:
        check_opening(slots, meta["opening"])
    except AssertionError as e:
        errs.append(str(e))
    species = Counter(x for c in clips for x in c["tags"].get("species", []))
    vocab = {k: {x for c in clips for x in (lambda v: v if isinstance(v, list) else [v])(c["tags"].get(TAG.get(k, k)))}
             for k in ("act", "xact", "size", "light", "set", "mood", "cam", "ang", "dir", "count")}
    for k in ("act", "xact"):  # hide / chase / catch are valid before the first clip carries them (ACT_SYN)
        vocab[k] |= set(ACT_SYN)
    for s in slots:
        for k, vals in s["filter"].items():
            if bad := [v for v in vals if k in vocab and v not in vocab[k]]:
                errs.append(f"slot {s['slot']} (## {s['line']}): {k}={bad} not in tag vocab {sorted(vocab[k])}")
    if errs:  # every problem at once: fix them all in one edit, then re-run
        raise SystemExit(f"{len(errs)} spec errors:\n" + "\n".join(errs))
    match_audio(slots, load_audio(), end)  # before the footage: the intro cuts follow the intro music
    bmsg = intro_beats(slots, intro, meta["opening"])
    for s in slots:
        s["vo"] = any(a < s["start"] + s["dur"] and s["start"] < b for a, b in vo)
    recent, rvids = ledger.banned(video.name, video)  # last N other videos of this workspace
    old = [c for c in clips if c["id"] in recent]
    pool = [c for c in clips if c["id"] not in recent]
    want = {x for s in slots for x in s["filter"].get("sp", []) if x != "none"}
    ymsg = yolo_pass([c for c in pool if want & set(c["tags"].get("species", []))],
                     "--yolo-cached" in sys.argv or region == "africa")
    smsg = semantic(slots, pool) if sem else "semantic: off (--no-sem); tags only"
    taken, omsg = open_uses(video.name)
    match(slots, pool, taken, meta["look"])
    hmsg = highlights(slots, pool)
    varmsg = vary(slots, pool)
    wmsg = fix_water(slots, pool, load_audio(), end)
    out = Path(OUT) if OUT else None  # --out=<dir>: plan.json + plan.md there (benchmark), the video's untouched
    if out:
        out.mkdir(parents=True, exist_ok=True)
    ((out or work) / "plan.json").write_text(json.dumps({"video": video.name, "video_dir": str(video), "region": region,
                                                "end": end, "intro": intro, "slots": slots},
                                               ensure_ascii=False, indent=1), "utf-8")
    write_md((out or video) / "plan.md", video.name, slots)

    tag = lambda s: re.match(r"\[([^\]]+)\]", s["need"])[1] if s["need"].startswith("[") else "-"  # noqa: E731
    cnt = Counter(s["status"] for s in slots)
    print(f"region: {region} ({', '.join(video_roots(region))}: {len(clips)} tagged clips)"
          + ("" if re.search(r"^\s*#\s*REGION", spec.read_text("utf-8"), re.M | re.I) else " - no # REGION line, default"))
    print(vmsg)
    print(f"slots={len(slots)} end={tc(end)} " + " ".join(f"{k}={v}" for k, v in cnt.items())
          + " src=" + str(dict(Counter(s["src"] for s in slots))))
    fb = sum(s["dur"] for s in slots if s.get("why") == "side shot")
    print(f"side shots after intro: spec {side_share:.0%} + fallback {fb:.0f}s (max {SIDE_MAX:.0%}, {SIDE_RUN} in a row)")
    print(f"rhythm: {short:.0%} shots <= {SHORT_T}s, {long_:.0%} >= {LONG_T}s (whole film, for info; judge per chapter below)")
    for w in rwarn:
        print("  rhythm warning:", w)
    print(f"opening: {meta['opening']}; biome: {meta['biome'] or '-'}; intro {tc(intro)}; fast until "
          f"{tc(meta['fast']) if meta['fast'] else '-'} (a story cue, not a cut-rate rule)")
    print("hook blueprint: " + ("ok (# HOOK lines)" if meta["hook"] else
                                "MISSING - write the # HOOK lines (edit-grammar 'Cold open') before judging the intro picks")
          if intro > INTRO_LEGACY else "hook blueprint: - (short intro)")
    print("\n".join(story_report(slots, meta, intro, end)))
    rej = Counter()
    for s in slots:
        rej.update(s.get("rej") or {})
    truth = [s for s in slots if s.get("status") == "THIEU" and s.get("rej")]
    print(f"truth: clips of the slot's animal refused {dict(rej)}; {sum('kiểm tra' in str(s.get('why', '')) for s in slots)} "
          f"picks capped WEAK (sex/age not visible: 'kiểm tra' marker); THIẾU because of them: "
          + (", ".join(f"#{s['slot']} {tc(s['start'])} {s['rej']}" for s in truth[:12]) or "none")
          + (f" (+{len(truth) - 12})" if len(truth) > 12 else ""))
    print(bmsg)
    print(ymsg)
    print(omsg)
    print(smsg)
    print(hmsg)
    print(varmsg)
    print(wmsg)
    if looks:
        gp = {c["abs"]: c.get("green") for c in pool}
        lk = [clip_look(s["caption"], gp.get(s["path"])) if s.get("path") else None for s in slots]
        off = sum(1 for s, x in zip(slots, lk) if x and s.get("want_look") and x not in s["want_look"])
        flips = sum(1 for a, b in zip(lk, lk[1:]) if a and b and a != b)
        lmsg += (f"; plan: green {lk.count('green')}, dry {lk.count('dry')}, {off} shots off the look they wanted, "
                 f"{flips} green<->dry cuts between neighbours")
    print(lmsg)
    print(audio_stats(slots, end))
    print(f"clip reuse in this video: {sum(s.get('reuse', 1) > 1 for s in slots)} slots (other part of the clip, >= {REUSE_GAP:.0f} s apart); "
          f"real footage {sum(s.get('source') == 'real' for s in slots)}, AI {sum(s.get('source') == 'ai' for s in slots)}; "
          f"{sum(s.get('part', '').startswith('1/') for s in slots)} shots too long for one clip filled by 2-3 clips (⧉)")
    # slots a ledger clip would have filled OK: the characters that need fresh footage
    blocked = Counter(tag(s) for s in slots if s["status"] in ("THIEU", "WEAK", "FALLBACK") and "pin" not in s["filter"]
                      and any(s["src"] in ("any", c["source"]) and usable(c)[1] - usable(c)[0] >= s["dur"]
                              and (fit(c, s["filter"], None) or 0) >= OK_FIT for c in old))
    print(f"recent ledger: {len(recent)} clips of {rvids} excluded; slots they would fill OK, by tag: {dict(blocked)}")
    absent = Counter(x for s in slots for x in s["filter"].get("sp", []) if x != "none" and x not in species)
    print("species not in library (slots):", dict(absent))
    print("thieu by tag:", dict(Counter(tag(s) for s in slots if s["status"] == "THIEU")))
    print("audio thieu (track kw: slots):", dict(Counter(f"A{e['track']} {','.join(e['kw'])}" for s in slots
                                                         for e in s["audio"] if e.get("status") == "THIEU")))
    # tag-by-species (user 2026-10-20): untagged footage of the cast = tag it (tag_source prepare --subject) before prompts
    unt = Counter(c.get("subject") or "?" for r, k, _ in video_roots(region).values() if index_of(r).exists()
                  for c in json.loads(index_of(r).read_text("utf-8"))["clips"].values()
                  if not c.get("tags", {}).get("caption") and c["duration"] <= 600)
    print(f"untagged clips skipped: {sum(unt.values())}; of the cast (folder species): "
          f"{ {x: unt[x] for x in sorted(want | ({'landscape'} if region == 'africa' else set())) if unt[x]} }")
    print(f"side-shot WEAK kept as is: {sum(s['status'] == 'WEAK' and is_side(s) for s in slots)}")
    print("character WEAK (judge: keep, pin=<file> or pin=none; chosen first, then alternatives):")
    for s in slots:
        if s["status"] == "WEAK" and not is_side(s):  # scenery near-misses don't hurt the story, characters do
            print(f"  {s['slot']} ##{s['line']} {s['dur']}s {s['need'][:70]}\n    " + "\n    ".join(x[:110] for x in s["top3"]))
    print(f"-> {(out or work) / 'plan.json'}\n-> {(out or video) / 'plan.md'}")


def selftest():
    end, intro, blocks = parse_spec("# END 00:20\n# INTRO 0:25\n## 1\n3 | a | real | sp=jaguar act=walk size=wide | A3=forest,day\n"
                             "* | b | any | sp=none | \n## 2\n2 | c | ai | pin=none | A8=branch\n* | d | GFX | | A7=off\n")
    s = build([0.0, 8.0], end, blocks)
    assert [x["dur"] for x in s] == [3, 5, 2, 10] and s[3]["start"] == 10
    from types import SimpleNamespace as C
    assert estimate_vo([C(t=0.0, text="a b c d e"), C(t=1.0, text="x"), C(t=9.0, text="one two")]) == \
        [(0.0, 0.7), (1.0, 1.5), (9.0, 9.8)]  # 5 words capped before the next cue; 1 word -> 0.5 s min
    for bad in ("## 1\n* | a | real | | A2=voice\n", "## 1\n* | a | stock | | \n", "## 1\n* | a | real | foo=1 | \n"):
        try:
            parse_spec(bad); raise SystemExit(f"bad spec accepted: {bad!r}")
        except AssertionError:
            pass
    mk = lambda p, src, **t: {"abs": p, "path": p, "source": src, "duration": 10.0,
                              "tags": {"caption": p, "best": [0, 10], "sure": True, "issues": [], **t}}
    clips = [mk("j_wide", "real", species=["jaguar"], action=["walk"], shot_size="wide"),
             mk("j_close", "ai", species=["jaguar"], action=["walk"], shot_size="medium"),
             mk("forest", "real", species=[], count="none", shot_size="wide")]
    sl = [{"slot": 1, "dur": 3, "src": "any", "filter": {"sp": ["jaguar"], "act": ["walk"], "size": ["wide"]}},
          {"slot": 2, "dur": 3, "src": "any", "filter": {"sp": ["jaguar"], "size": ["wide"]}},
          {"slot": 3, "dur": 3, "src": "real", "filter": {"sp": ["jaguar"]}},
          {"slot": 4, "dur": 12, "src": "any", "filter": {"sp": ["none"]}}]
    for x in sl:
        x["start"] = 0.0
    match(sl, clips)
    assert sl[0]["path"] == "j_wide" and sl[0]["status"] == "OK"
    assert sl[1]["path"] == "j_close" and sl[1]["status"] == "WEAK"  # adjacent size, no reuse
    assert sl[2]["status"] == "THIEU" and sl[3]["status"] == "THIEU"  # used up / too short
    assert sl[1]["src_in"] == 3.5  # centred in the AI-trimmed range 0.3..9.7
    assert sl[0]["alts"][0] == ["j_wide", "real"] and ["j_close", "ai"] in sl[0]["alts"]  # options for the bins
    # a _check clip that fits perfectly is still only WEAK, and says why
    h = [dict(mk("held", "ai", species=["jaguar"], action=["walk"], shot_size="wide", issues=["dark"]), hold=True)]
    hs = [{"slot": 1, "dur": 3, "src": "any", "filter": {"sp": ["jaguar"], "act": ["walk"]}, "start": 0.0}]
    match(hs, h)
    assert hs[0]["status"] == "WEAK" and hs[0]["why"] == "_check: dark", hs
    # a strike shot takes a walking animal only as WEAK (never OK); a lunging one is fine
    st = [{"slot": 1, "dur": 3, "src": "any", "need": "[J]", "filter": {"sp": ["jaguar"], "act": ["attack"]}, "start": 400.0}]
    match(st, clips[:2])
    assert st[0]["status"] in ("WEAK", "FALLBACK"), st
    st = [{"slot": 1, "dur": 3, "src": "any", "need": "[J]", "filter": {"sp": ["jaguar"], "act": ["attack"]}, "start": 400.0}]
    match(st, clips[:2] + [mk("j_lunge", "real", species=["jaguar"], action=["run"], shot_size="medium")])
    assert st[0]["path"] == "j_lunge", st
    # ground look: the first shot takes '# LOOK', the next ones follow it; desert never; a line's look= wins
    lc = [mk(p, "real", species=["impala"]) for p in ("i dry grass", "i green reeds", "i green plain", "i desert dune", "i dry plain")]
    ls = [{"slot": n, "dur": 3, "src": "any", "filter": {"sp": ["impala"]}, "start": 100.0 * n} for n in range(3)]
    ls[2]["filter"]["look"] = ["dry"]
    match(ls, lc, look="green")
    assert [x["path"] for x in ls] == ["i green reeds", "i green plain", "i dry grass"], [x["path"] for x in ls]
    # intro highlights: an animal intro shot takes a later chase shot of its species (>= SAME_GAP s on), at 140 %
    hc = [mk(p, "real", species=["impala"], action=[a]) for p, a in (("h_own", "walk"), ("h_run", "run"), ("h_eat", "eat"))]
    sh = lambda n, t, p, a, fit=1.0: {"slot": n, "start": t, "dur": 2.0, "src": "any", "status": "OK", "fit": fit,  # noqa: E731
                                      "intro": t < 90, "filter": {"sp": ["impala"], "act": [a]}, "path": p,
                                      "src_in": 4.0, "src_out": 6.0}
    hs = [sh(1, 0.0, "h_own", "walk"), sh(2, 200.0, "h_run", "run"), sh(3, 400.0, "h_run", "run", 0.7), sh(4, 500.0, "h_eat", "eat")]
    hs[1].update(src_in=0.0, src_out=2.0)  # other frames of h_run at 200 s: allowed (>= REUSE_GAP)
    msg = highlights(hs, hc)
    assert hs[0]["path"] == "h_run" and hs[0]["highlight"] == 3 and hs[0]["speed"] == 1.4 and hs[0]["src_out"] == 6.8, (hs[0], msg)
    assert "speed" not in hs[3] and hs[1].get("highlight") is None  # later shots untouched; 200 s on is too close
    # no footage of the species: no other animal stands in (2026-10-23), the intro slot stays THIẾU
    rc = [mk("l_imp", "real", species=["impala"], action=["run"]), mk("l_lion", "real", species=["lion"], action=["run"])]
    rs = [{"slot": 1, "start": 30.0, "dur": 2.0, "src": "any", "status": "THIEU", "intro": True, "filter": {"sp": ["red lechwe"]}},
          dict(sh(2, 400.0, "l_lion", "run"), fit=1.0), dict(sh(3, 500.0, "l_imp", "run"), fit=0.7)]
    highlights(rs, rc)
    assert rs[0]["status"] == "THIEU" and "path" not in rs[0], rs[0]
    # story truth (plan.md T11): "lionesses hiding to watch prey" never takes a resting male lion, even the best caption
    tc_ = [mk("male lion resting in the grass, watching", "real", species=["lion"], action=["rest"], shot_size="medium"),
           mk("maned lion crouches and stalks", "real", species=["lion"], action=["stalk"], shot_size="medium"),
           mk("lion lies low in tall grass", "real", species=["lion"], action=["stalk"], shot_size="wide"),
           mk("lioness crouches low in tall grass", "real", species=["lion"], action=["stalk"], shot_size="close_up")]
    lf = {"sp": ["lion"], "sex": ["female"], "act": ["stalk", "look"], "size": ["medium"]}
    assert [hard(c, lf)[0] for c in tc_] == ["resting", "sex", None, None] and hard(tc_[2], lf)[1] == "sex"
    ts = [{"slot": 1, "line": 1, "dur": 3, "src": "any", "need": "[L]", "filter": lf, "start": 0.0}]
    match(ts, tc_[:3])
    assert ts[0]["path"].startswith("lion lies") and ts[0]["status"] == "WEAK" and ts[0]["why"] == "kiểm tra sex: female", ts[0]
    ts = [{"slot": 1, "line": 1, "dur": 3, "src": "any", "need": "[L]", "filter": lf, "start": 0.0}]
    match(ts, tc_[:2])
    assert ts[0]["status"] == "THIEU" and ts[0]["rej"] == {"resting": 1, "sex": 1}, ts[0]
    # a kill only where the screenplay confirms it (out=kill) or the line is a meal; a near miss never shows one
    kc = mk("lioness catches a wildebeest calf", "real", species=["lion", "wildebeest"], action=["hunt"])
    assert hard(kc, {"sp": ["lion"], "act": ["hunt"]})[0] == "kill" and hard(kc, {"sp": ["lion"], "out": ["kill"]})[0] is None
    assert hard(kc, {"sp": ["none"]})[0] == "species" and hard(mk("calf", "real", species=["wildebeest"]), {"sp": ["wildebeest"], "age": ["young"]}) == (None, "")
    # fallback after 5 min: same species, other action, but never a contradicting one (resting for a chase)
    fl = [{"slot": 1, "line": 1, "dur": 3, "src": "any", "need": "[L]", "filter": {"sp": ["lion"], "act": ["run"], "kw": ["zzz"]}, "start": 400.0}]
    match(fl, tc_[:1])
    assert fl[0]["status"] == "THIEU", fl[0]
    # '# STORY 2 06:30 no=river': story 2's slots refuse river clips, the intro / story 1 do not
    mr = spec_meta("# STORY 1 01:30\n# STORY 2 06:30 no=river,crocodile\n", end=900.0, intro=90.0)
    rv = [{"start": 100.0, "filter": {"sp": ["lion"]}}, {"start": 400.0, "filter": {"sp": ["lion"], "no": ["hyena"]}}]
    story_rules(rv, mr)
    assert "no" not in rv[0]["filter"] and rv[1]["filter"]["no"] == ["hyena", "river", "crocodile"], rv
    # chase inside one sentence: screen direction kept (left -> left beats a better-sized right)
    dc = [mk("a", "real", species=["impala"], action=["run"], shot_size="wide", direction="left"),
          mk("b", "real", species=["impala"], action=["run"], shot_size="medium", direction="right"),
          mk("c", "real", species=["impala"], action=["run"], shot_size="close_up", direction="left")]
    ds = [{"slot": n, "line": 1, "dur": 2, "src": "any", "need": "[I]", "start": 0.0,
           "filter": {"sp": ["impala"], "act": ["run"], "size": z}} for n, z in ((1, ["wide"]), (2, ["medium", "close_up"]))]
    match(ds, dc)
    assert [x["path"] for x in ds] == ["a", "c"], [x["path"] for x in ds]
    # vision fields (tag-source 2026-10-23): outcome beats the caption; hide / chase / catch match old 'stalk' / 'hunt'
    assert hard(mk("lion catches nothing", "real", species=["lion"], action=["chase"], outcome="miss"), {"sp": ["lion"]})[0] is None
    assert hard(mk("lion runs", "real", species=["lion"], action=["chase"], outcome="catch"), {"sp": ["lion"]})[0] == "kill"
    assert hard(mk("lion lies", "real", species=["lion"], action=["rest"]), {"sp": ["lion"], "act": ["hide"]})[0] == "resting"
    assert fit(mk("x", "real", species=["lion"], action=["hunt"]), {"sp": ["lion"], "act": ["chase"]}, None) == 1.0
    assert fit(mk("x", "real", species=["lion"], action=["hide"]), {"sp": ["lion"], "act": ["stalk"]}, None) == 1.0
    # phase: the in-point goes where the asked action is (frames 3-4 run of a 20 s clip -> around 15.5 s)
    pc = dict(mk("p", "real", species=["impala"], action=["walk", "run"], phase=["walk", "walk", "run", "run"]), duration=20.0)
    pc["tags"]["best"] = [0, 20]
    ps = {"slot": 1, "dur": 3, "src": "any", "start": 0.0, "filter": {"sp": ["impala"], "act": ["run"]}}
    assert window(pc, ps, ()) == 14.0 and window(pc, dict(ps, filter={"sp": ["impala"]}), ()) == 8.5
    # '9x3 same': three consecutive parts of one long clip, cut where they meet; no long clip -> separate picks
    cs = build([0.0], 9.0, {1: [("*x3 same", "[I] chạy", "any", {"sp": ["impala"], "act": ["run"]}, [])]})
    assert len(cs) == 3 and len({x["chain"] for x in cs}) == 1
    match(cs, [pc, mk("short", "real", species=["impala"], action=["run"], shot_size="wide")])
    assert [x["path"] for x in cs] == ["p"] * 3 and all(abs(a["src_out"] - b["src_in"]) < 0.02 for a, b in zip(cs, cs[1:])), cs
    cs = build([0.0], 9.0, {1: [("*x3 same", "[I] chạy", "any", {"sp": ["impala"], "act": ["run"]}, [])]})
    match(cs, [mk(n, "real", species=["impala"], action=["run"]) for n in "abc"])  # 10 s clips hold the 9 s chain
    assert len({x["path"] for x in cs}) == 1, [x["path"] for x in cs]
    cs = build([0.0], 24.0, {1: [("*x3 same", "[I] chạy", "any", {"sp": ["impala"], "act": ["run"]}, [])]})
    match(cs, [mk(n, "real", species=["impala"], action=["run"]) for n in "abc"])  # 24 s > any clip: one by one
    assert len({x.get("path") for x in cs}) == 3, [x.get("path") for x in cs]
    # epic intro: animal shots cut into 1.0-2.2 s pieces on hits / bars; scenery and audio cues stay
    sp_ = [{"slot": 1, "start": 0.0, "dur": 5.0, "intro": True, "src": "any", "filter": {"sp": ["impala"]}, "audio": ["cue"]},
           {"slot": 2, "start": 5.0, "dur": 4.0, "intro": True, "src": "real", "filter": {"sp": ["none"]}, "audio": []}]
    assert split_intro(sp_, {"conf": 0.5, "events": [{"t": 1.5, "level": 4}], "bars": [3.0], "beats": []}, 0.0) == 2
    assert [(x["start"], x["dur"]) for x in sp_] == [(0.0, 1.5), (1.5, 1.5), (3.0, 2.0), (5.0, 4.0)], sp_
    assert [x["slot"] for x in sp_] == [1, 2, 3, 4] and sp_[0]["audio"] == ["cue"] and sp_[1]["audio"] == []
    # intro outro: music ends at 72 s -> landscape 68-72 fading out, story 1's landscape pulled back to 72, fading in
    io = [{"slot": 1, "line": 1, "start": 0.0, "dur": 40.0, "intro": True, "audio": []},
          {"slot": 2, "line": 2, "start": 40.0, "dur": 30.0, "intro": True, "audio": []},
          {"slot": 3, "line": 3, "start": 70.0, "dur": 10.0, "intro": True, "audio": [{"track": 3}, {"track": 7, "kw": ["off"]}]},
          {"slot": 4, "line": 4, "start": 80.0, "dur": 4.0, "intro": False, "audio": ["A7"], "filter": {"sp": ["none"]}}]
    intro_outro(io, 72.0)
    assert [(x["start"], x["dur"]) for x in io] == [(0.0, 40.0), (40.0, 28.0), (68.0, 4.0), (72.0, 12.0)], io
    assert io[2]["fade_out"] == FADE_OUT and io[2]["audio"] == [{"track": 3}] and io[3]["fade_in"] == FADE_IN and io[3]["slot"] == 4
    # after 5 min a THIẾU jaguar shot may take a neutral side shot; before 5 min it stays THIẾU
    clips2 = clips + [mk("moss", "real", species=[], count="none", shot_size="wide", subject="landscape")]
    late = [{"slot": 1, "dur": 3, "src": "any", "need": "[T]", "filter": {"sp": ["tapir"], "size": ["wide"]}, "start": 400.0},
            {"slot": 2, "dur": 3, "src": "any", "need": "[T]", "filter": {"sp": ["tapir"], "size": ["wide"]}, "start": 10.0}]
    big = [{"slot": 9, "dur": 9, "src": "any", "need": "[J] jaguar", "filter": {"pin": [p]}, "start": 500.0}
           for p in ("j_wide", "j_close")]  # character time after the intro so the 30% budget covers 3 s
    match(late + big, clips2)
    assert late[0]["status"] == "FALLBACK" and late[1]["status"] == "THIEU"
    # side fallback refused when the budget is spent (no character slot) or it would make a run of 3
    late = [{"slot": 1, "dur": 3, "src": "any", "need": "[T]", "filter": {"sp": ["tapir"]}, "start": 400.0}]
    match(late, clips2)
    assert late[0]["status"] == "THIEU"
    clips3 = clips2 + [mk("fern", "real", species=[], count="none", subject="landscape")]
    nb = lambda: [{"slot": 2, "dur": 2, "src": "any", "filter": {"sp": ["none"], "pin": [p]}, "start": 403.0}
                  for p in ("forest", "fern")]
    late = [{"slot": 1, "dur": 3, "src": "any", "need": "[T]", "filter": {"sp": ["tapir"]}, "start": 400.0}] + nb()
    match(late + [dict(x) for x in big], clips3)
    assert late[0]["status"] == "THIEU" and late[1]["status"] == "OK"
    late = [{"slot": 1, "dur": 3, "src": "any", "need": "[T]", "filter": {"sp": ["tapir"]}, "start": 400.0}] + nb()[:1]
    match(late + [dict(x) for x in big], clips3)
    assert late[0]["status"] == "FALLBACK"  # a run of 2 is fine
    late = [{"slot": 1, "dur": 3, "src": "any", "need": "[T]", "filter": {"sp": ["tapir"]}, "start": 400.0, "vo": True}]
    match(late + nb()[:1] + [dict(x) for x in big], clips3)
    assert late[0]["status"] == "THIEU"  # no scenery cutaway while the narrator talks about the tapir
    # spec check after the intro: side share, runs of 3 (rare), runs of 4 never; the intro is free
    sd = lambda n, need="": {"line": n, "dur": 2, "src": "any", "need": need, "filter": {}, "start": 200.0}
    ch = lambda k: [sd(9, "[J]") for _ in range(k)]
    for bad in ([sd(1), sd(1), sd(2, "[J]")],                     # 67% side
                [sd(1)] * 4 + ch(20),                              # run of 4
                [sd(1)] * 3 + ch(8) + [sd(2)] * 3 + ch(8)):        # two runs of 3 in < 5 min
        try:
            check_side(bad); raise SystemExit("side check passed a bad spec")
        except AssertionError:
            pass
    assert check_side([sd(1)] * 3 + ch(9)) == 0.25
    assert check_side([dict(sd(1), intro=True)] * 6 + ch(3)) == 0.0  # intro: anything goes
    one = {1: [("*", "a", "any", {}, [])], 2: [("5", "b", "any", {}, []), ("*", "c", "any", {}, [])]}
    assert intro == 25 and [x["intro"] for x in build([0.0, 20.0], 30.0, one, intro)] == [True, True, False]
    assert same_project("c2_africa1", "africa_1") and same_project("Amazon_2", "amazon_2") and not same_project("c2_africa2", "africa_1")
    sq = build([0.0], 20.0, {1: [("8x3", "a", "any", {}, [{"track": 6, "kw": ["x"]}]), ("*x4", "b", "any", {}, [])]})
    assert len(sq) == 7 and abs(sum(x["dur"] for x in sq) - 20) < 0.05 and [bool(x["audio"]) for x in sq[:3]] == [1, 0, 0]
    assert len({x["dur"] for x in sq[3:]}) == 4  # uneven parts
    parse_spec("# INTRO 1:30\n")  # long cold open allowed (legacy 0:15-0:30 default stays)
    for bad in ("# INTRO 0:10\n", "# INTRO 2:30\n"):
        try:
            parse_spec(bad); raise SystemExit(f"{bad.strip()} accepted")
        except AssertionError:
            pass
    # long intro (> 30 s): scenery may not take it over
    ib = lambda k, need: [dict(sd(1, need), intro=True, dur=10) for _ in range(k)]
    check_side(ib(4, "[J]") + ib(2, ""))
    try:
        check_side(ib(1, "[J]") + ib(5, "")); raise SystemExit("scenery-only long intro passed")
    except AssertionError:
        pass
    # headers: OPENING / BIOME / STORY ranges / TURN
    mt = spec_meta("# OPENING action\n# BIOME savanna\n# FAST_UNTIL 16:38\n# STORY 1 01:30\n# STORY 2 08:42\n# STORY 3 16:38\n"
                   "## 1\n# TURN\n* | a | any | | \n", end=1800.0, intro=90.0)
    assert mt["opening"] == "action" and mt["biome"] == "savanna" and mt["fast"] == 998 and \
        [t for _, t in mt["stories"]] == [90, 522, 998] and mt["turns"] == {1}
    assert spec_meta("## 1\n* | a | any | | \n")["opening"] == "landscape"  # old spec: unchanged
    for bad in ("# OPENING zoom\n", "# BIOME tundra\n", "# STORY 1 05:00\n# STORY 2 04:00\n", "# STORY 1 00:30\n"):
        try:
            spec_meta(bad, end=1800.0, intro=90.0); raise SystemExit(f"spec_meta accepted {bad!r}")
        except AssertionError:
            pass
    # rhythm: only absurd lengths are errors; a long hold, a flash and a flat run are warnings; no quota
    rs = lambda *d: [{"line": k, "dur": x, "src": "any"} for k, x in enumerate(d)]
    for bad in (rs(0.5, 2.5, 4.0), rs(1.5, 12.0, 2.0)):
        try:
            check_rhythm(bad); raise SystemExit(f"rhythm check passed {bad}")
        except AssertionError:
            pass
    assert check_rhythm(rs(1.6, 2.4, 4.2, 1.8))[2] == []
    w = check_rhythm(rs(2.5, 2.6, 2.4, 2.5, 1.0, 7.0))[2]
    assert len(w) == 2  # outside 1.2-6 s + metronome
    assert check_rhythm(rs(3.0, 3.1, 4.5, 3.0))[0] == 0.0  # no quota: a slow chapter passes
    # opening: landscape wide/aerial, >= 4 s, longer than the other intro shots; a GFX title before it is fine
    op = lambda d, sp="none", size="wide", src="real": {"line": 1, "dur": d, "src": src, "intro": True,
                                                       "filter": {"sp": [sp], "size": [size]}}
    # opening action: first shot an animal event, a wide/medium animal shot by 20 s
    ac = lambda start, sp, size, act=None: {"line": 1, "dur": 3, "src": "real", "start": start,
                                           "filter": dict({"sp": [sp], "size": [size]}, **({"act": [act]} if act else {}))}
    check_opening([ac(0, "lion", "medium", "attack"), ac(3, "buffalo", "wide")], "action")
    for bad in ([ac(0, "lion", "medium", "attack"), ac(3, "buffalo", "wide")][::-1],         # first shot has no action
                [ac(0, "lion", "medium", "attack"), ac(3, "buffalo", "close_up")],            # nothing places who/where
                [ac(0, "lion", "medium", "attack"), ac(25, "buffalo", "wide")],               # too late
                [ac(0, "none", "wide", "run"), ac(3, "buffalo", "wide")]):                    # landscape is no event
        try:
            check_opening(bad, "action"); raise SystemExit(f"action opening passed {bad}")
        except AssertionError:
            pass
    check_opening([op(3, src="GFX"), op(3.5, size="aerial"), op(2.5), op(2, "jaguar")])
    for bad in ([op(3.5, "jaguar"), op(2)], [op(3.5, size="close_up"), op(2)], [op(2.5), op(2)], [op(5), op(2)],
                [op(3.5), op(3.5)]):
        try:
            check_opening(bad); raise SystemExit(f"opening check passed {bad}")
        except AssertionError:
            pass
    # no= rejects a clip that also shows the excluded species
    mixed = [mk("cb_j", "ai", species=["capybara", "jaguar"])]
    nj = [{"slot": 1, "dur": 3, "src": "any", "filter": {"sp": ["capybara"], "no": ["jaguar"]}, "start": 0.0}]
    match(nj, mixed)
    assert nj[0]["status"] == "THIEU"
    # one long clip: <= REUSE_MAX slots >= REUSE_GAP apart; other parts first, then the same frames, no frame more
    # than SAME_MAX times and those repeats >= SAME_GAP apart; real beats a better AI clip
    long_ = [dict(mk("river", "real", species=[], count="none", shot_size="wide"), duration=30.0)]
    long_[0]["tags"]["best"] = [0, 30]
    rv = [{"slot": k, "dur": 8, "src": "any", "filter": {"sp": ["none"]}, "start": t} for k, t in enumerate(range(0, 1500, 100))]
    rv.insert(1, {"slot": 99, "dur": 8, "src": "any", "filter": {"sp": ["none"]}, "start": 50.0})
    match(rv, long_)
    got = [x for x in rv if "path" in x]
    assert len(got) == REUSE_MAX and rv[1]["status"] == "THIEU", [x["status"] for x in rv]  # 50 s: too close
    assert all(b["start"] - a["start"] >= REUSE_GAP for a, b in zip(got, got[1:]))
    assert any(x["same"] for x in got) and max(sum(x["src_in"] <= t < x["src_out"] for x in got) for t in range(30)) <= SAME_MAX
    assert all(abs(a["start"] - b["start"]) >= SAME_GAP for a in got for b in got
               if a is not b and a["src_in"] < b["src_out"] and b["src_in"] < a["src_out"])
    ra = [mk("ai_best", "ai", species=["jaguar"], action=["walk"], shot_size="wide"),   # fit 1.0
          mk("real_ok", "real", species=["jaguar"], action=["walk"], shot_size="medium"),  # fit 0.8
          mk("real_weak", "real", species=["jaguar"], action=["sleep"], shot_size="medium")]  # fit 0.2
    one = lambda: [{"slot": 1, "dur": 3, "src": "any", "filter": {"sp": ["jaguar"], "act": ["walk"], "size": ["wide"]},
                    "start": 0.0}]
    o = one(); match(o, ra)
    assert o[0]["path"] == "real_ok" and o[0]["status"] == "OK", o[0]
    o = one(); match(o, [ra[0], ra[2]])
    assert o[0]["path"] == "ai_best"  # real footage only weak -> AI
    # a part already on timeline Open counts toward REUSE_MAX and is never shown again
    rv = [{"slot": k, "dur": 4, "src": "any", "filter": {"sp": ["none"]}, "start": t} for k, t in enumerate(range(0, 1200, 100))]
    match(rv, long_, taken={"river": [(13.0, 17.0)]})
    assert sum("path" in x for x in rv) == REUSE_MAX - 1, [x["status"] for x in rv]
    assert all(x["src_out"] <= 13.0 or x["src_in"] >= 17.0 for x in rv if "path" in x), rv
    # vary: 30 fps real calm shot -> 80 %, a strike stays 100 %, 60 fps slow motion only on a calm hold, reuse -> zoom
    vc = {"abs": "v30", "source": "real", "fps": 30.0, "width": 3840, "duration": 20.0, "tags": {"shot_size": "wide"}}
    v60 = dict(vc, abs="v60", fps=60.0)
    vs = [{"slot": 2, "path": "v30", "status": "OK", "dur": 3.0, "start": 10.0, "src_in": 1.0, "filter": {"act": ["walk"]}},
          {"slot": 3, "path": "v30", "status": "OK", "dur": 3.0, "start": 200.0, "src_in": 5.0, "filter": {"act": ["run"]}, "reuse": 2},
          {"slot": 4, "path": "v60", "status": "OK", "dur": 4.0, "start": 300.0, "src_in": 1.0, "filter": {"act": ["rest"]}},
          {"slot": 5, "path": "v60", "status": "OK", "dur": 4.0, "start": 310.0, "src_in": 8.0, "filter": {"act": ["rest"]}}]
    vary(vs, [vc, v60])
    assert vs[0]["speed"] == 0.8 and vs[0]["src_out"] == 3.4 and "speed" not in vs[1] and vs[1]["zoom"] == 1.2
    assert vs[2]["speed"] == 0.4 and "speed" not in vs[3]  # one slow motion per SLOW_EVERY s
    # YOLO window: cut only where the subject is in frame; an unreliable measurement (seen < YOLO_SEEN) is ignored
    yc = dict(mk("yj", "real", species=["jaguar"]), yolo={"in": [2.0, 6.0], "seen": 0.8})
    assert usable(yc) == (2.0, 6.0) and usable(dict(yc, yolo={"in": [2.0, 6.0], "seen": 0.1})) == (0, 10)
    # every bad spec line is reported in one run
    try:
        parse_spec("## 1\n* | a | stock | | \n2 | b | real | foo=1 | \n"); raise SystemExit("bad spec accepted")
    except AssertionError as e:
        assert "line 2" in str(e) and "line 3" in str(e), e
    # music: the track that lasts until the next cue wins over a short one
    lib = [{"abs": p, "words": "tense music", "category": "tense_music", "duration": d} for p, d in (("m30", 30), ("m95", 95))]
    sl = [{"start": 0, "audio": [{"track": 7, "kw": ["tense"]}]}, {"start": 90, "audio": [{"track": 7, "kw": ["off"]}]}]
    match_audio(sl, lib, 200)
    assert sl[0]["audio"][0]["path"] == "m95" and sl[0]["audio"][0]["span"] == 90
    # SFX: no substitute - fly wings never on an eagle, every keyword must hit, a missing sound stays THIẾU
    lib = [{"abs": p, "words": w, "category": "Nature_sound", "duration": 2} for p, w in
           (("fly", "insects house fly wings"), ("flap", "shared wings flap"), ("hoof", "shared footsteps hoof run"))]
    sl = [{"start": 0, "filter": {"sp": ["harpy eagle"]}, "audio": [{"track": 8, "kw": ["wings"]}]},
          {"start": 5, "filter": {"sp": ["jaguar"]}, "audio": [{"track": 6, "kw": ["footsteps"]}]},
          {"start": 9, "filter": {"sp": ["peccary"]}, "audio": [{"track": 6, "kw": ["footsteps"]}]},
          {"start": 12, "filter": {"sp": ["otter"]}, "audio": [{"track": 6, "kw": ["otter", "call"]}]}]
    match_audio(sl, lib, 20)
    assert [s["audio"][0].get("path", "THIEU") for s in sl] == ["flap", "THIEU", "hoof", "THIEU"], sl
    # a slot no single clip covers is cut into 2-3 shots from different clips; audio stays on the first part
    sc = [dict(mk(f"j{k}", "real", species=["jaguar"]), duration=3.0) for k in range(5)]
    for c in sc:
        c["tags"]["best"] = [0, 3.0]
    lg = [{"slot": 1, "dur": 5.0, "src": "any", "filter": {"sp": ["jaguar"]}, "start": 0.0, "audio": [{"track": 6}]},
          {"slot": 2, "dur": 8.0, "src": "any", "filter": {"sp": ["jaguar"]}, "start": 300.0, "audio": []}]
    match(lg, sc)
    assert [(x["part"], x["dur"], x["start"]) for x in lg[:2]] == [("1/2", 2.5, 0.0), ("2/2", 2.5, 2.5)], lg[:2]
    assert lg[0]["audio"] and not lg[1]["audio"] and lg[0]["path"] != lg[1]["path"] and lg[2]["part"] == "1/3"
    assert [x["slot"] for x in lg] == [1, 2, 3, 4, 5]
    # intro beat cuts: hit B3+ first, else bar, else beat; A7 entry and opening rule hold; far cuts stay
    op = {"line": 1, "src": "real", "filter": {"sp": ["none"], "size": ["wide"]}, "audio": [{"track": 7}], "intro": True}
    sh = lambda ln, st, d, it=True: {"line": ln, "start": st, "dur": d, "src": "any", "filter": {}, "audio": [], "intro": it}  # noqa: E731
    sl = [dict(op, start=0.0, dur=3.5), sh(2, 3.5, 2.0), sh(3, 5.5, 2.5), sh(4, 8.0, 2.0), sh(5, 10.0, 3.0, False)]
    m = {"conf": 0.8, "events": [{"t": 3.7, "level": 4}, {"t": 5.4, "level": 2}], "bars": [7.85], "beats": [7.85, 10.2]}
    msg = snap_intro(sl, 10.0, m, 0.0)
    assert [x["start"] for x in sl] == [0.0, 3.7, 5.5, 7.85, 10.2] and sl[0]["dur"] == 3.7, (sl, msg)
    assert abs(sum(x["dur"] for x in sl) - 13.0) < 1e-6 and "3/4" in msg and "##3" in msg, msg
    sl = [dict(op, start=0.0, dur=3.5), sh(2, 3.5, 2.0, False)]
    snap_intro(sl, 3.0, {"conf": 0.8, "events": [{"t": 4.2, "level": 5}], "bars": [], "beats": []}, 0.0)
    assert sl[1]["start"] == 3.5, "opening shot may not grow past OPEN_MAX"
    assert spec_region("# END 1:00\n# REGION Africa\n## 1\n") == "africa" and spec_region("## 1\n") == "amazon"
    assert [clip_look(x) for x in ("impala in lush green grass", "impala on dry golden grass", "lion in the Kalahari desert",
                                   "green bush on dry grass", "impala at a waterhole")] == ["green", "dry", "desert", None, None]
    assert [clip_look("impala in green grass", g) for g in (0.02, 0.2, 0.6)] == ["dry", None, "green"]
    assert clip_look("lion on desert sand", 0.9) == "desert"
    cl = lambda cap: {"tags": {"caption": cap, "species": ["impala"]}}  # noqa: E731
    g = {"sp": ["impala"], "look": ["green"]}
    assert fit(cl("impala on dry sandy ground"), g, None) == 1.0 - LOOK_PEN and fit(cl("impala in green reeds"), g, None) == 1.0
    assert fit(cl("impala crosses desert dunes"), g, None) is None and fit(cl("impala crosses dry plain"), {"sp": ["impala"]}, None) == 1.0
    assert spec_meta("# LOOK green\n")["look"] == "green" and parse_filter("look=dry", 1) == {"look": ["dry"]}
    mk2 = lambda cap, st=(): {"tags": {"caption": cap, "setting": list(st)}}  # noqa: E731
    assert shows_water(mk2("Impala drinks", ())) and shows_water(mk2("x", ("river",))) and not shows_water(mk2("Lion walks on dry grass", ("savanna",)))
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:] == ["--selftest"]:
        selftest()
    elif sys.argv[1] == "--species":  # --species jaguar,otter,macaw --region amazon: species tags containing these words
        words = sys.argv[2].lower().split(",")
        assert "--region" in sys.argv, f"--species needs --region {'|'.join(REGIONS)}"
        region = sys.argv[sys.argv.index("--region") + 1]
        cnt = Counter((x, c["source"]) for c in load_clips(region) for x in c["tags"].get("species", []) if any(w in x for w in words))
        print(" ".join(f"{sp}({src}):{n}" for (sp, src), n in sorted(cnt.items())) or "none")
    else:
        main(sys.argv[1], "--no-sem" not in sys.argv)
