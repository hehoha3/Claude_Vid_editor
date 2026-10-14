"""doc-edit step 2: spec.txt -> footage + audio match (no tokens) -> plan.json + <video>/plan.md.

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/plan.py <audios-folder>
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/plan.py --selftest

Clips on timelines Edit/Open of the last N videos of the same workspace (ledger.py, /doc-edit check-timelines) are never matched.

spec.txt lives in .work/doc_edit/<video>/ (video = parent of the audios folder). Format:
    # END 29:50                optional timeline end; default = end of last sentence + 2 s
    # INTRO 0:20               intro length 0:15-0:30, chosen per video (side-shot rules start after it); default 0:15
    ## <sentence number>
    <dur|*> | <shot needed, Vietnamese> | <real|ai|any|GFX> | <filter> | <audio>
filter: k=v1,v2 tokens, '_' = space. sp (species, hard; sp=none = no animal) act size light set mood cam dir
        count kw (caption words) no (species or caption word that must NOT be in the clip, hard) pin (path fragment, or pin=none = force THIẾU)
audio:  A3=forest,day A6=bird A8=branch,snap A7=off   (keywords matched against file paths; A2 forbidden)
'*' = rest of the sentence slot (sentence start -> next sentence start, pause included); exactly one per sentence.
"""
import json, os, re, sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / ".claude/skills/scan-source/scripts")]
from dvr_cowork.timestamps import parse_timestamp_file  # noqa: E402
from dvr_cowork.timecode import parse_clock  # noqa: E402
from scan_source import ROOTS, index_of  # noqa: E402
import ledger  # noqa: E402

SRC = {"real", "ai", "any", "GFX"}
KEYS = {"sp", "act", "size", "light", "set", "mood", "cam", "ang", "dir", "count", "kw", "no", "pin"}
TAG = {"act": "action", "size": "shot_size", "set": "setting", "cam": "camera", "ang": "angle", "dir": "direction"}
SIZES = ["extreme_close", "close_up", "medium", "wide", "aerial"]
OK_FIT, WEAK_FIT = 0.6, 0.35
FALLBACK_T = 300.0  # first 5 min: strict matches only; later THIẾU shots may use related/neutral clips
FALLBACK_FIT = 0.2
# action shots (user rule 2026-10-12): a strike/chase shot prefers a clip that shows action; a same-species clip
# without it is capped at WEAK (yellow, below OK_FIT) instead of looking like a match; none at all -> THIẾU
STRIKE = {"attack", "hunt", "fight", "run", "stalk", "jump"}
NEUTRAL = {"landscape", "bird", "birds", "insects", "butterfly", "frog", "hummingbird", "toucan-bird", "spider",
           "supplementary_shots", "others"}  # folders of side shots: scenery, insects, birds, frogs
INTRO_MIN, INTRO_MAX = 15.0, 30.0  # '# INTRO m:ss' in the spec: the intro may be all scenery; default INTRO_MIN
SIDE_MAX = 0.3   # after the intro, side shots (anything without a [tag] main character) <= 30% of footage time
SIDE_RUN = 3     # max side shots in a row; a run of 3 is rare: at most one per RUN3_EVERY seconds
RUN3_EVERY = 300.0
SHOT_MIN, SHOT_MAX = 1.2, 6.0  # footage shot length bounds (s); longer = split into a sequence
FLAT = 4         # this many shots in a row whose lengths differ by < FLAT_SPAN s = flat, metronome rhythm
FLAT_SPAN = 0.4
SHORT_T, LONG_T = 2.0, 3.5  # rhythm needs both: >= 25% shots <= 2.0 s and >= 10% shots >= 3.5 s
OPEN_MIN, OPEN_MAX = 3.0, 4.0  # user rule 2026-10-13: the first shot of "Edit" is a landscape (sp=none, wide/aerial)
# of 3-4 s, longer than every other intro shot
AI_TRIM = 0.3  # AI clips often morph in the first/last frames
YOLO_SEEN = 0.3  # YOLO saw the subject in >= 30% of samples: its window and size are trusted
REUSE_MAX, REUSE_GAP, REUSE_PEN, SRC_MARGIN = 3, 120.0, 0.1, 1.0  # one clip <= 3 slots per video, 2 min apart,
# different part of the clip each time (1 s apart), a fresh clip wins over a reused one of similar fit
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
        f[k] = [x.replace("_", " ") if k in ("sp", "kw") else x for x in v.split(",")]
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
                assert INTRO_MIN <= intro <= INTRO_MAX, f"spec line {n}: INTRO {m[1]} not in 0:15-0:30"
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


def build(starts, end, blocks, intro=INTRO_MIN):
    """starts = sentence start times; returns slots filling [0 .. end] exactly."""
    assert sorted(blocks) == list(range(1, len(starts) + 1)), \
        f"spec must cover sentences 1..{len(starts)}, missing {sorted(set(range(1, len(starts) + 1)) - set(blocks))}"
    bounds = [0.0] + starts[1:] + [end]
    slots, errs = [], []
    for i in range(1, len(starts) + 1):
        t0, t1 = bounds[i - 1], bounds[i]
        rest = (t1 - t0) - sum(float(b[0]) for b in blocks[i] if b[0] != "*")
        if sum(b[0] == "*" for b in blocks[i]) != 1:
            errs.append(f"## {i}: exactly one '*' shot")
        elif rest < SHOT_MIN:
            errs.append(f"## {i}: '*' shot only {rest:.1f}s (slot {t1 - t0:.1f}s)")
        if errs:
            continue
        t = t0
        for d, need, src, flt, audio in blocks[i]:
            dur = rest if d == "*" else float(d)
            slots.append({"slot": len(slots) + 1, "line": i, "start": round(t, 2), "dur": round(dur, 2),
                          "need": need, "src": src, "filter": flt, "audio": audio, "intro": t < intro})
            t += dur
        assert abs(t - t1) < 1e-6
    assert not errs, "\n".join(errs)
    return slots


def is_side(s):
    """Side shot = footage without a [tag] main character: scenery, birds, insects, a friendly other species..."""
    return s["src"] != "GFX" and not s.get("need", "").startswith("[")


def check_side(slots):
    """Spec check after the intro: side shots stay a seasoning, the main characters carry the film."""
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
    """Spec check: shot lengths follow the story (short and long), not a metronome."""
    sh = [s for s in slots if s["src"] != "GFX"]
    errs = []
    if out := [f"{s['line']} ({s['dur']:.1f}s)" for s in sh if not SHOT_MIN <= s["dur"] <= SHOT_MAX]:
        errs.append(f"shots outside {SHOT_MIN}-{SHOT_MAX}s (split a long '*' into a sequence) in ## " + ", ".join(out))
    flat = [f"{sh[k]['line']}-{sh[k + FLAT - 1]['line']}" for k in range(len(sh) - FLAT + 1)
            if max(d := [s["dur"] for s in sh[k:k + FLAT]]) - min(d) < FLAT_SPAN]
    if flat:
        errs.append(f"{FLAT} shots of the same length in a row (vary them with the story) in ## " + ", ".join(flat))
    short = sum(s["dur"] <= SHORT_T for s in sh) / len(sh)
    long_ = sum(s["dur"] >= LONG_T for s in sh) / len(sh)
    if short < 0.25 or long_ < 0.1:
        errs.append(f"shots <= {SHORT_T}s: {short:.0%} (need >= 25%), >= {LONG_T}s: {long_:.0%} (need >= 10%); "
                    "cut tension shorter, hold beats longer")
    assert not errs, "\n".join(errs)
    return short, long_


def check_opening(slots):
    """Spec check: the film opens on a landscape held a little longer than the shots after it."""
    sh = [s for s in slots if s["src"] != "GFX"]
    if not sh:
        return
    o, f = sh[0], sh[0]["filter"]
    longest = max((s["dur"] for s in sh[1:] if s.get("intro")), default=0.0)
    assert f.get("sp") == ["none"] and set(f.get("size", [])) & {"wide", "aerial"} and not set(f.get("size", [])) - {"wide", "aerial"} \
        and OPEN_MIN <= o["dur"] <= OPEN_MAX and o["dur"] > longest, (
        f"## {o['line']}: first shot must be a landscape (sp=none size=wide/aerial) of {OPEN_MIN:.0f}-{OPEN_MAX:.0f}s, "
        f"longer than every other intro shot ({longest:.1f}s); now {o['dur']:.1f}s, filter {f}")


# ------------------------------------------------------------------ footage match
def load_clips():
    clips = []
    for root, kind, source in ROOTS.values():
        if kind != "video":
            continue
        for cid, c in json.loads(index_of(root).read_text("utf-8"))["clips"].items():
            # _check = holding folder: clips left there failed organize (morph/blur/dark/unsure), never planned
            if c.get("tags", {}).get("caption") and not c["path"].replace("\\", "/").startswith("_check/"):
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


def yolo_pass(clips):
    """Measure the candidate clips with YOLO (cached, local GPU), then trust its shot size over the tag."""
    try:
        import yolo
        new, sec = yolo.measure(clips)
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
    return f"yolo: {len(clips)} candidate clips, {new} measured now ({sec}s), {n} with subject window + measured size"


def fit(c, f, prev_size):
    t = c["tags"]
    if "sp" in f:
        if f["sp"] == ["none"]:
            if t.get("species") and t.get("count") != "none":
                return None
        elif not set(f["sp"]) & set(t.get("species", [])):
            return None
    if any(x in t.get("species", []) or x.lower() in t["caption"].lower() for x in f.get("no", [])):
        return None
    if "light" in f and ("night" in f["light"]) != (t.get("light") == "night"):
        return None
    pts = mx = 0
    for k, w in (("act", 3), ("set", 2), ("size", 2), ("light", 1), ("mood", 1), ("cam", 1), ("ang", 1), ("dir", 1), ("count", 1)):
        if k not in f:
            continue
        mx += w
        v = t.get(TAG.get(k, k))
        have = set(v) if isinstance(v, list) else {v}
        if k == "set":
            pts += min(w, len(have & set(f[k])))
        elif have & set(f[k]):
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
    if set(f.get("act", [])) & STRIKE and not set(t.get("action") or []) & STRIKE:
        s = min(s, OK_FIT - 0.05)   # no action in the clip: never OK
    s -= 0.1 if prev_size and t.get("shot_size") == prev_size else 0
    return s


def window(c, s, uses):
    """In-point for slot s from clip c, or None. One clip serves at most REUSE_MAX slots of a video, REUSE_GAP s
    apart on the timeline, each from a part of the clip not shown before (SRC_MARGIN between the parts)."""
    if len(uses) >= REUSE_MAX or any(abs(s["start"] - t) < REUSE_GAP for t, _, _ in uses):
        return None
    lo, b = usable(c)
    gaps = []
    for _, i, o in sorted(uses, key=lambda u: u[1]):
        gaps.append((lo, i - SRC_MARGIN)); lo = max(lo, o + SRC_MARGIN)
    lo, hi = max(gaps + [(lo, b)], key=lambda g: g[1] - g[0])
    return round(lo + (hi - lo - s["dur"]) / 2, 2) if hi - lo >= s["dur"] else None


def rank_key(x):
    """Real footage first whenever it fits OK; AI where real footage cannot fill the shot."""
    v, c = x[0], x[1]
    return v >= OK_FIT, c["source"] == "real" and v >= OK_FIT, v + (0.05 if c["source"] == "real" else 0)


def match(slots, clips):
    uses, prev_size = {}, None  # clip path -> [(timeline start, src_in, src_out)]

    def take(s, c, cin, **kw):
        uses.setdefault(c["abs"], []).append((s["start"], cin, cin + s["dur"]))
        s.update(path=c["abs"], id=c.get("id"), source=c["source"], src_in=cin, src_out=round(cin + s["dur"], 2),
                 caption=c["tags"]["caption"], reuse=len(uses[c["abs"]]), **kw)

    def rank(s, prev, skip=()):
        f = s["filter"]
        pool = [(c, w) for c in clips if s["src"] in ("any", c["source"]) and c["abs"] not in skip
                and (w := window(c, s, uses.get(c["abs"], ()))) is not None]
        if "pin" in f:
            hits = [(c, w) for c, w in pool if f["pin"][0].lower() in c["abs"].lower()]
            assert len(hits) == 1, f"slot {s['slot']}: pin {f['pin'][0]!r} -> {len(hits)} usable clips"
            return [(1.0, *hits[0])]
        # ponytail: greedy in timeline order; a later slot may lose a clip it fits better
        return sorted(((v - REUSE_PEN * len(uses.get(c["abs"], ())), c, w) for c, w in pool
                       if (v := fit(c, f, prev)) is not None), key=rank_key, reverse=True)

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

    out = []
    for s in slots:
        f = s["filter"]
        out.append(s)
        if s["src"] == "GFX" or f.get("pin") == ["none"]:
            s["status"] = "GFX" if s["src"] == "GFX" else "THIEU"
            prev_size = None
            continue
        ranked = rank(s, prev_size)
        s["top3"] = [f"{v:.2f} {Path(c['path']).name[:40]} — {c['tags']['caption']}" for v, c, _ in ranked[:3]]
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
        soft = {k: v for k, v in f.items() if k in ("size", "light", "set", "mood", "cam", "ang", "no")}
        want = set(f.get("sp", [])) - {"none"}
        side_ok = not s.get("vo") and s["dur"] <= budget and run_len(i) <= 2  # never a cutaway over a narrated character line
        best = None
        for c in clips:
            if s["src"] not in ("any", c["source"]) or (w := window(c, s, uses.get(c["abs"], ()))) is None:
                continue
            related = bool(want & set(c["tags"].get("species", [])))
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
CATEGORY = {"sfx": "Nature_sound", "animal": "Nature_sound", "sound": "music"}  # read-only roots -> AUDIO_POOL category
# Foley / SFX (A6, A8, A9) never substitute (user rule 2026-10-11): every keyword must hit, and a file naming an
# animal is only used on a slot of that animal or a close relative (no house-fly wings on an eagle, no hoof
# footsteps on a jaguar). No such file -> audio THIẾU, reported in the plan reply; the user downloads one or drops it.
STRICT = {6, 8, 9}
ANIMALS = set("fly insect insects bee wasp mosquito cricket crickets cicada frog bird birds parrot macaw owl eagle "
              "hawk raptor vulture baboon monkey primate ape chimp gorilla antelope deer giraffe zebra cheetah leopard "
              "lion tiger cat hyena wolf dog elephant hippo horse hoof cow pig boar crocodile alligator caiman snake "
              "carnivore herbivore whale dolphin seal otter capybara peccary jaguar anaconda fish rodent".split())
KIN = {"jaguar": "cat cheetah leopard lion tiger carnivore", "peccary": "pig boar hoof herbivore",
       "capybara": "herbivore rodent", "otter": "carnivore", "giant otter": "otter carnivore",
       "caiman": "crocodile alligator carnivore", "alligator": "crocodile caiman carnivore", "anaconda": "snake",
       "harpy eagle": "eagle bird birds raptor hawk carnivore", "capuchin monkey": "monkey primate",
       "capuchin": "monkey primate", "fish": "fish"}


def kin(sp):
    """Animal words a sound file may name on a slot of these species."""
    return {w for x in sp if x != "none" for w in (x + " " + KIN.get(x, "")).split()}


def load_audio():
    out = []
    for name, (root, kind, _) in ROOTS.items():
        if kind != "audio":
            continue
        for a in json.loads(index_of(root).read_text("utf-8"))["clips"].values():
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
    used = Counter()
    for s in slots:
        for e in s["audio"]:
            if e["kw"] == ["off"]:
                continue

            def key(a):  # most keyword hits, then least used (variety); music: covers its span, then closest length
                k = (sum(w in a["words"] for w in e["kw"]), -used[a["abs"]])
                return k + (a["duration"] >= e["span"], -abs(a["duration"] - e["span"])) if "span" in e else k
            pool = [a for a in lib if a["category"] in AUDIO_POOL[e["track"]]]
            if e["track"] in STRICT:
                ok = kin(s.get("filter", {}).get("sp", []))
                pool = [a for a in pool if all(w in a["words"] for w in e["kw"]) and set(a["words"].split()) & ANIMALS <= ok]
            a = max(pool, key=key, default=None)
            if not a or key(a)[0] <= 0:
                e["status"] = "THIEU"
                continue
            used[a["abs"]] += 1
            e.update(status="OK", path=a["abs"], dur=a["duration"])


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
            clip += f"{s['caption']} `{Path(s['path']).name[:30]}`" + (f" ↻{s['reuse']}" if s.get("reuse", 1) > 1 else "")                     + (f" ⧉{s['part']}" if "part" in s else "")
        aud = " · ".join(f"A{e['track']} " + (Path(e["path"]).stem[:25] if e.get("status") == "OK"
                         else "off" if e["kw"] == ["off"] else f"**THIẾU** {','.join(e['kw'])}") for e in s["audio"])
        md.append(f"| {s['slot']} | {s['line']} | {tc(s['start'])} | {s['dur']:.1f} | {talk} | {s['need']} | {clip} "
                  f"| {s.get('fit', '')} | {aud} |")
    path.write_text("\n".join(md) + "\n", "utf-8")


def main(folder):
    folder = Path(folder)
    ts = [p for p in folder.glob("*.md") if "timestamp" in p.name.lower()]
    assert len(ts) == 1, f"need exactly one *timestamp*.md in {folder}, found {[p.name for p in ts]}"
    cues = parse_timestamp_file(ts[0])
    audio = [p for p in folder.iterdir() if p.suffix.lower() in (".mp3", ".wav")]
    assert len(audio) == 1, f"need exactly one narration audio in {folder}"
    vplan = json.loads((ROOT / ".work" / audio[0].stem / "plan.json").read_text("utf-8"))  # step 1 output
    vo = [(s["ts"], s["ts"] + s["src_out"] - s["src_in"]) for s in vplan["segments"]]
    assert len(vo) == len(cues), "vo-sync plan.json and timestamp file disagree; re-run step 1"

    video = folder.parent
    work = ROOT / ".work" / "doc_edit" / video.name
    spec = work / "spec.txt"
    assert spec.exists(), f"write {spec} first"
    end, intro, blocks = parse_spec(spec.read_text("utf-8"))
    end = end or vo[-1][1] + 2.0
    assert end > vo[-1][1], f"END {tc(end)} is before the last sentence ends ({tc(vo[-1][1])})"

    slots = build([c.t for c in cues], end, blocks, intro)
    for s in slots:
        s["vo"] = any(a < s["start"] + s["dur"] and s["start"] < b for a, b in vo)
    clips = load_clips()
    errs, side_share, short, long_ = [], 0, 0, 0
    try:
        side_share = check_side(slots)
    except AssertionError as e:
        errs.append(str(e))
    try:
        short, long_ = check_rhythm(slots)
    except AssertionError as e:
        errs.append(str(e))
    try:
        check_opening(slots)
    except AssertionError as e:
        errs.append(str(e))
    species = Counter(x for c in clips for x in c["tags"].get("species", []))
    vocab = {k: {x for c in clips for x in (lambda v: v if isinstance(v, list) else [v])(c["tags"].get(TAG.get(k, k)))}
             for k in ("act", "size", "light", "set", "mood", "cam", "ang", "dir", "count")}
    for s in slots:
        for k, vals in s["filter"].items():
            if bad := [v for v in vals if k in vocab and v not in vocab[k]]:
                errs.append(f"slot {s['slot']} (## {s['line']}): {k}={bad} not in tag vocab {sorted(vocab[k])}")
    if errs:  # every problem at once: fix them all in one edit, then re-run
        raise SystemExit(f"{len(errs)} spec errors:\n" + "\n".join(errs))
    recent, rvids = ledger.banned(video.name, video)  # last N other videos of this workspace
    old = [c for c in clips if c["id"] in recent]
    pool = [c for c in clips if c["id"] not in recent]
    want = {x for s in slots for x in s["filter"].get("sp", []) if x != "none"}
    ymsg = yolo_pass([c for c in pool if want & set(c["tags"].get("species", []))])
    match(slots, pool)
    match_audio(slots, load_audio(), end)
    (work / "plan.json").write_text(json.dumps({"video": video.name, "video_dir": str(video), "end": end, "slots": slots},
                                               ensure_ascii=False, indent=1), "utf-8")
    write_md(video / "plan.md", video.name, slots)

    tag = lambda s: re.match(r"\[([^\]]+)\]", s["need"])[1] if s["need"].startswith("[") else "-"  # noqa: E731
    cnt = Counter(s["status"] for s in slots)
    print(f"slots={len(slots)} end={tc(end)} " + " ".join(f"{k}={v}" for k, v in cnt.items())
          + " src=" + str(dict(Counter(s["src"] for s in slots))))
    fb = sum(s["dur"] for s in slots if s.get("why") == "side shot")
    print(f"side shots after intro: spec {side_share:.0%} + fallback {fb:.0f}s (max {SIDE_MAX:.0%}, {SIDE_RUN} in a row)")
    print(f"rhythm: {short:.0%} shots <= {SHORT_T}s, {long_:.0%} >= {LONG_T}s")
    print(ymsg)
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
    print("untagged clips skipped:", sum(1 for r, k, _ in ROOTS.values() if k == "video"
                                        for c in json.loads(index_of(r).read_text("utf-8"))["clips"].values()
                                        if not c.get("tags", {}).get("caption")))
    print(f"side-shot WEAK kept as is: {sum(s['status'] == 'WEAK' and is_side(s) for s in slots)}")
    print("character WEAK (judge: keep, pin=<file> or pin=none; chosen first, then alternatives):")
    for s in slots:
        if s["status"] == "WEAK" and not is_side(s):  # scenery near-misses don't hurt the story, characters do
            print(f"  {s['slot']} ##{s['line']} {s['dur']}s {s['need'][:70]}\n    " + "\n    ".join(x[:110] for x in s["top3"]))
    print(f"-> {work / 'plan.json'}\n-> {video / 'plan.md'}")


def selftest():
    end, intro, blocks = parse_spec("# END 00:20\n# INTRO 0:25\n## 1\n3 | a | real | sp=jaguar act=walk size=wide | A3=forest,day\n"
                             "* | b | any | sp=none | \n## 2\n2 | c | ai | pin=none | A8=branch\n* | d | GFX | | A7=off\n")
    s = build([0.0, 8.0], end, blocks)
    assert [x["dur"] for x in s] == [3, 5, 2, 10] and s[3]["start"] == 10
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
    # a strike shot takes a walking animal only as WEAK (never OK); a lunging one is fine
    st = [{"slot": 1, "dur": 3, "src": "any", "need": "[J]", "filter": {"sp": ["jaguar"], "act": ["attack"]}, "start": 400.0}]
    match(st, clips[:2])
    assert st[0]["status"] in ("WEAK", "FALLBACK"), st
    st = [{"slot": 1, "dur": 3, "src": "any", "need": "[J]", "filter": {"sp": ["jaguar"], "act": ["attack"]}, "start": 400.0}]
    match(st, clips[:2] + [mk("j_lunge", "real", species=["jaguar"], action=["run"], shot_size="medium")])
    assert st[0]["path"] == "j_lunge", st
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
    try:
        parse_spec("# INTRO 0:45\n"); raise SystemExit("INTRO 0:45 accepted")
    except AssertionError:
        pass
    # rhythm: bounds, flat runs, short/long mix
    rs = lambda *d: [{"line": k, "dur": x, "src": "any"} for k, x in enumerate(d)]
    for bad in (rs(2.5, 2.6, 2.4, 2.5, 1.5, 4.0), rs(1.0, 2.5, 4.0), rs(1.5, 7.0, 2.0), rs(2.5, 3.0, 2.2, 3.0, 2.6)):
        try:
            check_rhythm(bad); raise SystemExit(f"rhythm check passed {bad}")
        except AssertionError:
            pass
    check_rhythm(rs(1.6, 2.4, 4.2, 1.8, 2.2, 3.0, 1.4, 5.0))
    # opening: landscape wide/aerial, >= 4 s, longer than the other intro shots; a GFX title before it is fine
    op = lambda d, sp="none", size="wide", src="real": {"line": 1, "dur": d, "src": src, "intro": True,
                                                       "filter": {"sp": [sp], "size": [size]}}
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
    # one long clip serves up to 3 slots >= 2 min apart, each from a different part; real beats a better AI clip
    long_ = [dict(mk("river", "real", species=[], count="none", shot_size="wide"), duration=30.0)]
    long_[0]["tags"]["best"] = [0, 30]
    rv = [{"slot": k, "dur": 4, "src": "any", "filter": {"sp": ["none"]}, "start": t} for k, t in enumerate((0, 50, 130, 260, 400))]
    match(rv, long_)
    assert [x["status"] for x in rv] == ["OK", "THIEU", "OK", "OK", "THIEU"], [x["status"] for x in rv]
    parts = sorted((x["src_in"], x["src_out"]) for x in rv if "path" in x)
    assert all(p[1] + 1.0 <= q[0] for p, q in zip(parts, parts[1:])), parts
    ra = [mk("ai_best", "ai", species=["jaguar"], action=["walk"], shot_size="wide"),   # fit 1.0
          mk("real_ok", "real", species=["jaguar"], action=["walk"], shot_size="medium"),  # fit 0.8
          mk("real_weak", "real", species=["jaguar"], action=["sleep"], shot_size="medium")]  # fit 0.2
    one = lambda: [{"slot": 1, "dur": 3, "src": "any", "filter": {"sp": ["jaguar"], "act": ["walk"], "size": ["wide"]},
                    "start": 0.0}]
    o = one(); match(o, ra)
    assert o[0]["path"] == "real_ok" and o[0]["status"] == "OK", o[0]
    o = one(); match(o, [ra[0], ra[2]])
    assert o[0]["path"] == "ai_best"  # real footage only weak -> AI
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
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:] == ["--selftest"]:
        selftest()
    else:
        main(sys.argv[1])
