"""Build the four wildlife-documentary files from one production source file.

usage: python build_four_files.py SOURCE.src.md OUT_DIR [--wpm 150] [--mp3 DIR | --durations-json FILE] [--check]

Source = '=== NAME' sections: META, BIBLE, SP_HEAD, SP_TAIL, VP_HEAD, VP_TAIL, SCENES.
SCENES, per scene:
  @ 1.4 | 04:30 | 05:30 | Title
  key: value          see, animals, sound, fn, clips, gate, audio, need (MUST/ALT/PENDING ...),
                      lead (s before first voice), tail (hold weight after last line), vend (mm:ss voice end limit),
                      music (intro per-second table), grid (bar start s + bar length s, intro only)
  - dur | size | picture / observable action | A5 natural sound | why the viewer keeps watching | flags
                      dur in s or '*' (= rest of the scene span, once); flags: ! key shot, long (<= 12 s),
                      black, cb (callback: other frames of a used clip)
  > EN || VI || hold weight || @shot+offset
                      weight = share of the scene's spare time after this line; @3+0.5 pins the onset
                      0.5 s after shot 3 starts (picture-locked line; unpinned lines float around pins)
Onsets: planned from words at --wpm (+0.4 s) or conformed to measured 1.mp3..N.mp3 durations (--mp3 / --durations-json).
Placeholders in the text sections: {{shot:1.4-09}} = shot in-time, {{line:12}} = onset, {{budget}}, {{status}}, {{lastend}}.
--check: run every gate and print the report without writing files.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

TARGET = 3600.0
SHOT_MAX, LONG_MAX, SHOT_MIN = 8.0, 12.0, 0.8
REST_LIST, REST_HOOK = 3.0, 6.0
MIN_GAP, PIN_SLIP, HEADROOM = 0.2, 1.5, 0.10


def secs(t):
    m, s = t.split(":")
    return int(m) * 60 + float(s)


def stamp(x):
    x = int(round(x * 10, 6)) / 10  # floor to 0.1 so an onset is never later than planned
    return f"{int(x // 60):02d}:{x % 60:04.1f}"


def parse(src):
    parts = re.split(r"^=== (\w+)\s*$", src, flags=re.M)
    sec = {parts[i]: parts[i + 1].strip("\n") for i in range(1, len(parts), 2)}
    meta = dict(l.split(": ", 1) for l in sec["META"].splitlines() if l.strip())
    scenes = []
    for line in sec["SCENES"].splitlines():
        if line.startswith("@ "):
            sid, a, b, title = [x.strip() for x in line[2:].split("|")]
            scenes.append({"id": sid, "start": secs(a), "end": secs(b), "title": title, "lines": [], "shots": []})
        elif line.startswith("> "):
            bits = [x.strip() for x in line[2:].split("||")] + ["", ""]
            pin = re.fullmatch(r"@(\d+)([+-][\d.]+)?", bits[3]) if bits[3] else None
            scenes[-1]["lines"].append({"en": bits[0], "vi": bits[1], "w": float(bits[2] or 1),
                                        "pin": (int(pin[1]), float(pin[2] or 0)) if pin else None})
        elif line.startswith("- "):
            f = [x.strip() for x in line[2:].split("|")] + ["", "", ""]
            scenes[-1]["shots"].append({"dur": f[0], "size": f[1], "act": f[2], "snd": f[3], "hook": f[4],
                                        "flags": f[5].split()})
        elif re.match(r"^\w+: ", line):
            k, v = line.split(": ", 1)
            scenes[-1][k] = v.strip()
    return meta, sec, scenes


def probe(mp3_dir, n):
    out = []
    for i in range(1, n + 1):
        p = Path(mp3_dir) / f"{i}.mp3"
        if not p.is_file():
            sys.exit(f"missing {p}: need 1.mp3 .. {n}.mp3 in transcript order")
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                           capture_output=True, text=True)
        out.append(float(r.stdout.strip()))
    return out


def time_shots(sc, err):
    span = sc["end"] - sc["start"]
    fixed = sum(float(s["dur"]) for s in sc["shots"] if s["dur"] != "*")
    stars = [s for s in sc["shots"] if s["dur"] == "*"]
    if len(stars) > 1:
        err.append(f"{sc['id']}: more than one '*' shot")
    for s in stars:
        s["dur"] = round(span - fixed, 3)
    t = sc["start"]
    for i, s in enumerate(sc["shots"], 1):
        s["dur"] = float(s["dur"])
        s["id"] = f"{sc['id']}-{i:02d}"
        s["t"], t = t, t + s["dur"]
        lim = LONG_MAX if "long" in s["flags"] else SHOT_MAX
        lo = 0.5 if "black" in s["flags"] else SHOT_MIN
        if not lo <= s["dur"] <= lim + 1e-6:
            err.append(f"{s['id']}: {s['dur']:.1f} s outside {lo}-{lim} s")
    if sc["shots"] and abs(t - sc["end"]) > 0.05:
        err.append(f"{sc['id']}: shots sum {t - sc['start']:.1f} s, span {span:.1f} s")
    if not sc["shots"]:
        err.append(f"{sc['id']}: no shots")


def time_voice(sc, first, err, warn=None, planned=True):
    """Onsets: pinned lines on their shot; the others share the spare time between anchors by weight.
    A pin is 'at or just after its shot': real audio may push it up to PIN_SLIP later (warning), more is an error.
    While planning, each pinned segment keeps HEADROOM of its voice time free so slower audio still fits."""
    warn = [] if warn is None else warn
    L = sc["lines"]
    if not L:
        return
    vend = secs(sc["vend"]) if sc.get("vend") else sc["end"]
    for l in L:
        if l["pin"]:
            k, off = l["pin"]
            if not 1 <= k <= len(sc["shots"]):
                err.append(f"{sc['id']}: pin @{k} has no shot")
                l["pin"] = None
            else:
                l["fix"] = sc["shots"][k - 1]["t"] + off
    if "fix" not in L[0]:
        L[0]["fix"] = sc["start"] + (0.6 if first else float(sc.get("lead", 1.5)))
    anchors = [i for i, l in enumerate(L) if "fix" in l] + [len(L)]
    for a, b in zip(anchors, anchors[1:]):
        t_b = L[b]["fix"] if b < len(L) else vend
        seg = L[a:b]
        weights = [l["w"] for l in seg]
        if b == len(L):
            weights[-1] = float(sc.get("tail", 1.5))
        voice = sum(l["d"] for l in seg)
        spare = t_b - L[a]["fix"] - voice
        if planned and b < len(L) and spare < HEADROOM * voice:
            warn.append(f"{sc['id']}: only {spare:.1f} s free before the pin of line {L[b]['n']} "
                        f"(< {HEADROOM:.0%} of {voice:.1f} s voice): slower audio would push it off its shot")
        t = L[a]["fix"]
        for l, w in zip(seg, weights):
            l["t"] = t
            t += l["d"] + max(spare, 0) * w / sum(weights)
    for prev, l in zip(L, L[1:]):  # real audio longer than planned: slide forward, never overlap
        need = prev["t"] + prev["d"] + MIN_GAP
        if l["t"] < need:
            slip = need - l["t"]
            if l["pin"] and slip > PIN_SLIP:
                err.append(f"{sc['id']}: line {l['n']} would start {slip:.1f} s after its shot (max {PIN_SLIP} s): "
                           "split/shorten an earlier block (EN + VI) or move the pin")
            elif l["pin"]:
                warn.append(f"{sc['id']}: line {l['n']} slips {slip:.1f} s after its pinned shot")
            l["t"] = need


def rests(scenes, lines):
    """Voice-free intervals, cut at scene boundaries; each with the shots that play in it."""
    busy = [(l["t"], l["t"] + l["d"]) for l in lines]
    free, cur = [], 0.0
    for a, b in busy:
        if a > cur:
            free.append((cur, a))
        cur = max(cur, b)
    free.append((cur, TARGET))
    for sc in scenes:
        sc["rests"] = []
        for a, b in free:
            a2, b2 = max(a, sc["start"]), min(b, sc["end"])
            if b2 - a2 >= REST_LIST:
                shots = [s for s in sc["shots"] if s["t"] < b2 - 0.05 and s["t"] + s["dur"] > a2 + 0.05]
                sc["rests"].append((a2, b2, shots))


def build(src_path, out, check=False):
    global TARGET
    meta, sec, scenes = parse(Path(src_path).read_text(encoding="utf-8"))
    TARGET = float(meta.get("target", 60)) * 60
    err, warn = [], []
    check = check or "--report" in sys.argv
    wpm = float(sys.argv[sys.argv.index("--wpm") + 1]) if "--wpm" in sys.argv else 150.0
    lines = [l for sc in scenes for l in sc["lines"]]
    for n, l in enumerate(lines, 1):
        l["n"] = n
        l["d"] = len(l["en"].split()) * 60 / wpm + 0.4
        if not l["vi"] or l["vi"] == l["en"] or l["vi"].isascii():
            err.append(f"line {n}: Vietnamese missing or untranslated: {l['vi'][:60]!r}")
    status = f"PLANNED — onsets estimated from word counts at {wpm:.0f} wpm (+0.4 s per block); not yet conformed to audio"
    meas = None
    if "--mp3" in sys.argv:
        meas = probe(sys.argv[sys.argv.index("--mp3") + 1], len(lines))
    elif "--durations-json" in sys.argv:
        raw = json.loads(Path(sys.argv[sys.argv.index("--durations-json") + 1]).read_text(encoding="utf-8"))
        meas = [float(raw[str(i)]) for i in range(1, len(lines) + 1)] if isinstance(raw, dict) else [float(x) for x in raw]
    if meas:
        if len(meas) != len(lines):
            sys.exit(f"{len(meas)} durations for {len(lines)} voice blocks")
        for l, d in zip(lines, meas):
            l["d"] = d
        if not check:
            Path(src_path).with_name("durations.json").write_text(json.dumps(meas), encoding="utf-8")
        status = f"CONFORMED — onsets re-timed to the measured durations of 1.mp3 … {len(lines)}.mp3"

    prev = 0.0
    for i, sc in enumerate(scenes):
        if abs(sc["start"] - prev) > 0.01:
            err.append(f"{sc['id']}: starts {stamp(sc['start'])}, previous ended {stamp(prev)}")
        prev = sc["end"]
        time_shots(sc, err)
        time_voice(sc, i == 0, err, warn, planned=not meas)
        if sc["lines"] and sc["lines"][-1]["t"] + sc["lines"][-1]["d"] > (secs(sc["vend"]) if sc.get("vend") else sc["end"]) + 0.05:
            err.append(f"{sc['id']}: last voice block runs past the scene's voice end")
        if not sc.get("need"):
            warn.append(f"{sc['id']}: no footage status (need:)")
    if abs(prev - TARGET) > 0.01:
        err.append(f"scenes end at {stamp(prev)}, target {stamp(TARGET)}")
    for a, b in zip(lines, lines[1:]):
        if a["t"] + a["d"] > b["t"] + 0.05:
            err.append(f"voice block {a['n']} overlaps block {b['n']} by {a['t'] + a['d'] - b['t']:.1f} s")
    seen = {}
    shots = [s for sc in scenes for s in sc["shots"]]
    for s in shots:
        key = re.sub(r"\W+", " ", s["act"].lower()).strip()
        if key in seen:
            err.append(f"{s['id']} repeats {seen[key]} (same picture): no repeated footage as filler")
        seen[key] = s["id"]
    rests(scenes, lines)
    for sc in scenes:
        for a, b, ss in sc["rests"]:
            if b - a >= REST_HOOK and not any(s["hook"] for s in ss):
                warn.append(f"{sc['id']} rest {stamp(a)}–{stamp(b)}: no shot says why the viewer keeps watching")
    longest = max(shots, key=lambda s: s["dur"])
    words = sum(len(l["en"].split()) for l in lines)
    voiced = sum(l["d"] for l in lines)
    last_end = lines[-1]["t"] + lines[-1]["d"]
    allrests = [r for sc in scenes for r in sc["rests"]]
    qa = [f"- Status: **{status}**.",
          f"- Scenes: {len(scenes)}, contiguous 00:00.0–{stamp(prev)}; every scene's shots add up to its span (checked to 0.05 s).",
          f"- Shots: {len(shots)}; median {sorted(s['dur'] for s in shots)[len(shots) // 2]:.1f} s; longest {longest['id']} {longest['dur']:.1f} s; "
          f"no shot over {SHOT_MAX:.0f} s unless marked long (≤ {LONG_MAX:.0f} s, continuous action); no repeated picture.",
          f"- Voice: {len(lines)} blocks, {words} words, {voiced / 60:.1f} min ({voiced / TARGET:.0%} of runtime); "
          f"{sum(1 for l in lines if l['pin'])} blocks pinned to picture; no overlaps; last block ends {stamp(last_end)}.",
          f"- Rests without narrator ≥ {REST_LIST:.0f} s: {len(allrests)}, total {sum(b - a for a, b, _ in allrests) / 60:.1f} min; "
          f"each listed with its shots, sound and viewer hook (rests ≥ {REST_HOOK:.0f} s are checked for a hook)."]
    qa += [f"- WARN: {w}" for w in warn] or ["- Warnings: none."]
    report = "\n".join(qa)
    if "--report" in sys.argv:  # planning table: what a writer needs to place shots and hooks, nothing else
        for sc in scenes:
            print(f"{sc['id']} {stamp(sc['start'])}-{stamp(sc['end'])} lines "
                  + " ".join(f"#{l['n']}@{l.get('t', 0) - sc['start']:.1f}+{l['d']:.1f}" for l in sc["lines"]))
            for a, b, ss in sc.get("rests", []):
                if b - a >= REST_HOOK and not any(s["hook"] for s in ss):
                    print(f"   no hook {stamp(a)}-{stamp(b)}: " + " / ".join(f"{s['id']} {s['act'][:40]}" for s in ss))
    if err:
        sys.exit("ERRORS:\n" + "\n".join(err) + "\n\n" + report)
    if check:
        print(report)
        return

    shot_at = {s["id"]: s for s in shots}

    def fill(text):
        def rep(m):
            k, v = m[1], m[2]
            if k == "shot":
                return stamp(shot_at[v]["t"])
            if k == "line":
                return stamp(lines[int(v) - 1]["t"])
            return {"budget": f"{words:,} words in {len(lines)} Genmax blocks ≈ {voiced / 60:.1f} min of voice "
                              f"({voiced / TARGET:.0%} of runtime); the other {(TARGET - voiced) / 60:.1f} min are the picture-and-sound "
                              f"passages listed under every scene",
                    "status": status, "lastend": stamp(last_end)}[k]
        return re.sub(r"\{\{(\w+)(?::([\w.-]+))?\}\}", rep, text)

    for sc in scenes:
        for k in ("see", "animals", "sound", "fn", "clips", "gate", "audio", "need"):
            sc[k] = fill(sc.get(k, ""))

    slug, out = meta["slug"], Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "transcript.md").write_text(
        "\n\n".join("\n".join(l["en"] for l in sc["lines"]) for sc in scenes if sc["lines"]) + "\n", encoding="utf-8")

    ts = [f"# {meta['title']} — Timestamp EN / VI", "",
          f"{status}. One onset per Genmax block (1.mp3 … {len(lines)}.mp3). "
          f"{sum(1 for l in lines if l['pin'])} onsets are locked to picture events; the others float inside their scene "
          f"and are re-timed by `build_four_files.py --mp3 <mp3 folder>` once the audio exists.", "",
          "## English", ""]
    ts += [f"[{stamp(l['t'])}] {l['en']}" for l in lines]
    ts += ["", "## Vietnamese", ""]
    ts += [f"[{stamp(l['t'])}] {l['vi']}" for l in lines]
    (out / f"{slug}_Timestamp_EN_VI.md").write_text("\n".join(ts) + "\n", encoding="utf-8")

    def shot_txt(s):
        return f"{s['id']} {stamp(s['t'])} {s['dur']:.1f} s {s['size']} — {s['act']}"

    sp = [fill(sec["SP_HEAD"]), "", "## Animal bible", "", sec["BIBLE"], "", "## Timed screenplay", "",
          "Beat line = `**NNN · in–out**`; every rest without narrator lists its shots (id, in, duration, size), the natural sound "
          "and why the viewer keeps watching. `*Narrator:*` lines carry the planned onsets.", ""]
    for n, sc in enumerate(scenes, 1):
        keys = [s for s in sc["shots"] if "!" in s["flags"]]
        sp += [f"**{n:03d} · {stamp(sc['start'])}–{stamp(sc['end'])}** — {sc['id']} {sc['title']}. {sc.get('see', '')}", "",
               f"*Animals / sex / young:* {sc.get('animals', '')}", "",
               f"**Sound / music:** {sc.get('sound', '')}", "",
               f"**Footage:** {sc.get('need', '')}", "",
               f"**Shots:** {len(sc['shots'])} ({min(s['dur'] for s in sc['shots']):.1f}–{max(s['dur'] for s in sc['shots']):.1f} s)"
               + (f"; key shots: " + "; ".join(f"{s['id']} {stamp(s['t'])} {s['act']}" for s in keys) if keys else "") + ".", ""]
        if sc["rests"]:
            sp += ["**Without narrator:**", ""]
            for a, b, ss in sc["rests"]:
                hooks = [s["hook"] for s in ss if s["hook"]]
                snd = "; ".join(dict.fromkeys(s["snd"] for s in ss if s["snd"]))
                sp.append(f"- {stamp(a)}–{stamp(b)} ({b - a:.1f} s): " + " → ".join(
                    f"{s['id']} ({s['dur']:.1f} s) {s['act']}" for s in ss)
                    + f". *Sound:* {snd or 'scene bed'}. *Why watch:* {' / '.join(hooks) or 'continuation of the action above'}.")
            sp.append("")
        sp += [f"*Narrator:* [{stamp(l['t'])}] {l['en']}" for l in sc["lines"]] + [""] if sc["lines"] else \
            ["*Narrator:* none — picture and natural sound only.", ""]
    sp += [fill(sec["SP_TAIL"])]
    (out / f"{slug}_Screenplay_EN.md").write_text("\n".join(sp) + "\n", encoding="utf-8")

    # intro: one row per second
    intro = [sc for sc in scenes if sc["id"].startswith("0.")]
    vp = [fill(sec["VP_HEAD"]), "", "## Animal bible", "", sec["BIBLE"], ""]
    if intro:
        vp += [f"## Intro cut map, every second ({stamp(intro[0]['start'])}–{stamp(intro[-1]['end'])})", "",
               "Shot = what is on screen during that second (a cut inside the second is shown as `→`). "
               "Music bars are a 120 BPM planning grid; `/doc-edit intro` fits the real track and moves cuts onto its beats.", "",
               "| s | Shot | Picture | Narrator | Music |", "| --- | --- | --- | --- | --- |"]
        ishots = [s for sc in intro for s in sc["shots"]]
        for t in range(int(intro[0]["start"]), int(intro[-1]["end"])):
            on = [s for s in ishots if s["t"] < t + 1 - 1e-6 and s["t"] + s["dur"] > t + 1e-6]
            sc = next(x for x in intro if x["start"] <= t < x["end"])
            vo = next((l for l in lines if l["t"] <= t + 0.95 and l["t"] + l["d"] > t), None)
            vtxt = "" if not vo else (f"#{vo['n']} starts {stamp(vo['t'])}: {vo['en']}" if int(vo["t"]) == t else f"#{vo['n']} …")
            if sc.get("grid"):
                g0, gl = map(float, sc["grid"].split())
                mus = f"bar {int((t - g0) // gl) + 1}" + (" ↓downbeat" if abs((t - g0) % gl) < 1e-6 else "")
            else:
                mus = sc.get("music", "")
            pic = " → ".join(s["act"] for s in on if s["t"] >= t - 1e-6) or "(continues)"
            vp.append(f"| {t // 60:02d}:{t % 60:02d} | {' → '.join(s['id'] for s in on)} | {pic} | {vtxt} | {mus} |")
        vp.append("")
    vp += ["## Footage status", "",
           "MUST = the scene cannot be cut as written without this footage. ALT = a named fallback keeps the voice. "
           "PENDING = cannot be locked before the clips exist (outcome, species name or callbacks decide the wording or the cut).", "",
           "| Status | Scenes |", "| --- | --- |"]
    for tag in ("MUST", "ALT", "PENDING"):
        vp.append(f"| {tag} | " + "; ".join(f"{sc['id']} {sc['need']}" for sc in scenes if tag in sc.get("need", "").split("—")[0]) + " |")
    vp += ["", "## Cut map, every shot (00:00–60:00)", "",
           "Flags: ! key shot (must exist), long = continuous take up to 12 s, cb = callback (other frames of a clip used earlier, never the same frames), black = black slug. "
           "Voice = narrator blocks heard over the shot (planned).", "",
           "| Shot | In | Out | Dur | Size | Picture / observable action | A5 natural sound | Voice | Flags |",
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for sc in scenes:
        for s in sc["shots"]:
            vo = [str(l["n"]) for l in sc["lines"] if l["t"] < s["t"] + s["dur"] and l["t"] + l["d"] > s["t"]]
            vp.append(f"| {s['id']} | {stamp(s['t'])} | {stamp(s['t'] + s['dur'])} | {s['dur']:.1f} | {s['size']} | {s['act']} | "
                      f"{s['snd']} | {','.join(vo) or '—'} | {' '.join(s['flags'])} |")
    vp += ["", "## Beat table (footage index)", "",
           "| Beat / time | Clip requirements and direction | Animals / sex / young | Story function | Source and continuity gate | Audio and fallback | Footage |",
           "| --- | --- | --- | --- | --- | --- | --- |"]
    for sc in scenes:
        vp.append(f"| {sc['id']} {stamp(sc['start'])[:5]}–{stamp(sc['end'])[:5]} {sc['title']} | {sc.get('clips', '')} | "
                  f"{sc.get('animals', '')} | {sc.get('fn', '')} | {sc.get('gate', '')} | {sc.get('audio', '')} | {sc.get('need', '')} |")
    vp += ["", "## Production QA (generated)", "", report, "", fill(sec["VP_TAIL"])]
    (out / f"{slug}_Visual_Edit_Plan_EN.md").write_text("\n".join(vp) + "\n", encoding="utf-8")
    print(report)
    # the skill's own contract check, run on what was just written
    cmd = [sys.executable, str(Path(__file__).with_name("validate_four_files.py")), str(out),
           "--target-minutes", f"{TARGET / 60:g}", "--wpm", f"{wpm:g}"]
    if meas:
        cmd += ["--durations-json", str(Path(src_path).with_name("durations.json"))]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    print("validator:", (r.stdout + r.stderr).strip().replace("\n", " | "))
    if r.returncode:
        sys.exit("validator failed")


SELFTEST = """=== META
slug: Test_Film
title: Test Film
target: 0.5
=== BIBLE
| ID | Species | Sex / age | Young | Markers | metaphor |
=== SP_HEAD
# Test — strike at {{shot:1.1-03}}, {{budget}}
=== SP_TAIL
end {{lastend}}
=== VP_HEAD
# Test plan
=== VP_TAIL
tail
=== SCENES
@ 0.1 | 00:00 | 00:10 | Open
need: ALT — any
grid: 0 2
- 5.0 | W | river at dawn | water | calm start |
- * | M | herd walking | hooves | |
> The river is calm. || Dòng sông yên ả.
@ 1.1 | 00:10 | 00:30 | Strike
need: MUST — the lunge
- 4.0 | W | herd drinking | lapping | |
- 4.0 | C | wake closing | hiss | tension |
- 3.0 | W | the lunge | splash | climax | !
- 4.0 | M | herd scattering | hooves | relief |
- * | W | river smoothing over | lapping | |
> The wake stops. || Vệt sóng dừng lại. ||  || @2
> It misses. || Nó vồ trượt. ||  || @4+0.2
"""


def selftest():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "t.src.md"
        src.write_text(SELFTEST, encoding="utf-8")
        build(src, Path(d) / "out")
        ts = (Path(d) / "out" / "Test_Film_Timestamp_EN_VI.md").read_text(encoding="utf-8")
        assert "[00:00.6] The river is calm." in ts and "[00:14.0] The wake stops." in ts, ts
        assert "[00:21.2] Nó vồ trượt." in ts  # pinned 0.2 s after shot 1.1-04 (00:21.0)
        sp = (Path(d) / "out" / "Test_Film_Screenplay_EN.md").read_text(encoding="utf-8")
        assert "strike at 00:18.0" in sp and "**002 · 00:10.0–00:30.0**" in sp
        vp = (Path(d) / "out" / "Test_Film_Visual_Edit_Plan_EN.md").read_text(encoding="utf-8")
        assert "| 00:00 | 0.1-01 |" in vp and "| MUST | 1.1" in vp
        bad = SELFTEST.replace("|| @4+0.2", "|| @2+0.1")  # second line pinned 0.1 s after the first: slips 1.7 s
        src.write_text(bad, encoding="utf-8")
        try:
            build(src, Path(d) / "out2", check=True)
            raise AssertionError("a pin pushed 1.7 s off its shot was not caught")
        except SystemExit as e:
            assert "after its shot" in str(e), e
        src.write_text(SELFTEST.replace("Nó vồ trượt.", "It misses."), encoding="utf-8")  # VI left in English
        try:
            build(src, Path(d) / "out3", check=True)
            raise AssertionError("untranslated Vietnamese was not caught")
        except SystemExit as e:
            assert "untranslated" in str(e), e
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    if "--selftest" in sys.argv:
        selftest()
    else:
        build(sys.argv[1], sys.argv[2], check="--check" in sys.argv)
