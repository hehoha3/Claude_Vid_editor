"""Prompt rules shared by both engines (user 2026-11-05): footage+AI missing.py and full-AI dvr_cowork.fullai.story.

Every generated shot: no physical contact between animals, every animal in frame keeps moving, never a silent
stare-down. 8p prompts add the character / environment / light locks; 1h prompts do not. Every prompt carries the
shot_id + slot + length and the prompt as one paragraph, in missing-prompt.txt (user 2026-11-17).
"""
import csv
import io
import math
import re
from pathlib import Path

# Contact verbs (a keyword gate, not proof: QC still views the frames).
CONTACT = re.compile(r"\b(?:bit(?:e|es|ing|ten)|gor(?:e|es|ed|ing)|ram(?:s|med|ming)|headbutt\w*|tackl\w+|"
                     r"grab(?:s|bed|bing)?|seiz(?:e|es|ed|ing)|pins? (?:it|him|her|them|down)|(?<!ears )(?<!ear )pinned(?! back)|shov(?:e|es|ed|ing)|"
                     r"knock(?:s|ed)? (?:down|over|into)|kill(?:s|ed|ing)?|wound(?:s|ed)?|blood(?:y)?|"
                     r"makes? contact|jaws (?:close|clamp)\w*|claws? (?:rake|sink|into)\w*|horns (?:meet|lock|clash)\w*|"
                     r"collid\w+|wrestl\w+|grappl\w+|drags? (?:it|him|her|the (?:prey|carcass|body))|"
                     r"strikes? (?:it|him|her|the)|struck)\b", re.I)
# Silent stare-downs: two animals frozen, looking at each other.
STARE = re.compile(r"\b(?:star(?:e|es|ing)|gaz(?:e|es|ing)|look(?:s|ing)?|glar(?:e|es|ing)) at each other\b|"
                   r"\blocks? eyes\b|\beyes lock(?:ed)?\b|\bface to face\b|\bstare-?down\b|\bstand-?off\b", re.I)
# Words that make a pose instead of motion ("slow" stays allowed here: sloths, slow push-in camera moves). The
# adverb "still" ("the animal still clearly lit", 2026-11-05: 68 false errors) is not a pose: only "stands still" etc.
CALM = re.compile(r"\b(?:stillness|(?:stand|stay|hold|keep|remain|lie|sit|freez|stood|kept)\w*\s+(?:very\s+|perfectly\s+)?still|motionless|gentl[ey]|calm(?:ly)?|paus(?:e|es|ing)|wait(?:s|ing)?|"
                  r"rest(?:s|ing)?|settl(?:e|es|ing)|idle|freez(?:e|es|ing)|frozen|pos(?:e|es|ing)|"
                  r"stands? (?:still|watching)|small movement)\b", re.I)
NEG = re.compile(r"\b(?:no|not|never|without|avoid)\b[^,.;]*", re.I)  # "no standing still" is a request, not a pose
# User 2026-11-10: generated clips kept coming back in slow motion (both types). Said positively at the very start
# of every prompt (generators weight early text, "Cinematic / BBC Earth" wording pulls high-speed-camera looks); the
# one negative stays at the end of TAIL.
SPEED = "Real-time footage at true natural speed (1x playback, 24 fps, natural motion blur, every movement at its real-world pace)"
# Appended to every prompt of both engines, after the authored text (so the gates never read it).
TAIL = ("Every animal in frame keeps moving for the whole shot (running, turning, stepping, scanning, ears and tail "
        "alive); never standing still, never silently staring at each other. No physical contact between animals: "
        "every lunge, swipe or charge misses by a body length. Natural anatomy, consistent screen direction, one "
        "continuous shot with no cuts, no blood, no gore, no narration, no music, natural sound only, no text, "
        "no logos, no watermark, no slow motion, no speed ramp.")
# Real-speed verbs: a clip under 5 s with one beat needs one (or two actions joined by "then"), else the generator
# stretches a single small action over the clip = slow motion (user 2026-11-10). "spring" stays out: "frozen spring".
FAST = re.compile(r"\b(?:run|runs|running|ran|sprint\w*|bolt\w*|dash\w*|rac(?:e|es|ing)|gallop\w*|charg(?:e|es|ing)|"
                  r"lung(?:e|es|ing)|leap\w*|jump\w*|bound(?:s|ing)|pounc\w+|scrambl\w+|flee\w*|fled|chas(?:e|es|ing)|"
                  r"dart\w*|burst\w*|explod\w+|swerv\w+|veer\w*|wheel(?:s|ing)|whip\w*|spin\w*|plung\w+|div(?:e|es|ing)|"
                  r"dove|splash\w*|flap\w*|swoop\w*|launch\w*|scatter\w*|stamped\w+|hurtl\w+|careen\w*|skid\w*|"
                  r"tumbl\w+|surg(?:e|es|ing)|swing(?:s|ing)|swung|hop(?:s|ping)?|takes? off|taking off|zigzag\w*|"
                  r"accelerat\w+|full[- ]speed|flat out)\b", re.I)
THEN = re.compile(r"\bthen\b", re.I)
SIZES = re.compile(r"\b(extreme wide|very wide|wide|establishing|medium[- ]long|medium|close[- ]up|extreme close[- ]up|"
                   r"detail|aerial|top-down)\b", re.I)


# Header of every 1h prompt (input/SKILL.md formula): the clip's own length, camera, place, light.
HEAD = (SPEED + ". Wildlife documentary, ultra-photorealistic 4K, {s}single continuous shot, 16:9, shot on {cam}, "
        "{place}, {light}.")


def paced(beats, clip_s):
    """Pace gate shared by both engines: None, or the problem of a clip under 5 s carried by one slow beat."""
    if not clip_s or clip_s >= 5 or len(beats) != 1:
        return None
    b = NEG.sub("", beats[0])
    if FAST.search(b) or THEN.search(b):
        return None
    return (f"pace: one beat in a {clip_s:g} s clip needs a real-speed verb (sprints, bolts, leaps, scrambles...) or "
            "two actions joined by 'then'; one small action gets stretched into slow motion")


def shot_id(video, n):
    """shot_id = file name of the clip (user 2026-11-10): D:\\Chann_3_x\\africa_101126_6, shot 9 -> 'c3v6_9'.
    A folder outside a channel keeps the plain number."""
    from .videokey import timeline_name
    m = re.fullmatch(r"chann(\d+)_vid(\d+)", timeline_name(video) or "")
    return f"c{m[1]}v{m[2]}_{n}" if m else str(n)


def render(cam, place, light, beats, d=None):
    """Full prompt of one clip d seconds long (None: no number): header, beats (3+ beats on a known length are timed
    across the whole clip, no static hold), the shared TAIL."""
    head = HEAD.format(s=f"{d:g}-second " if d else "", cam=cam, place=place, light=light)
    beats = [b.rstrip(". ") + "." for b in beats]
    if d and len(beats) >= 3:
        ticks = [round(x * d * 2) / 2 for x in ([0, .3, .7, 1] if len(beats) == 3 else [0, .2, .5, .7, 1])]
        beats = [f"{ticks[i]:g}-{ticks[i + 1]:g}s: {b}" for i, b in enumerate(beats)]
    return " ".join([head] + beats + [TAIL])


def dur_s(seconds):
    """Generated clip length for a timeline slot: the slot + 1 s, up to the half second (user 2026-11-09, both video
    types: 4 -> 5, 3.2 -> 4.5, 8.7 -> 10)."""
    return math.ceil((float(seconds) + 1) * 2 - 1e-9) / 2


def issues(text):
    """Contact / stare / pose words in what the prompt asks for (its 'no ...' clauses removed)."""
    pos = NEG.sub("", text)
    out = [f"contact: '{m[0].lower()}' (animals never touch; write the miss)" for m in CONTACT.finditer(pos)]
    out += [f"stare: '{m[0].lower()}' (keep both animals moving)" for m in STARE.finditer(pos)]
    out += [f"motion: '{m[0].lower()}' (every animal keeps moving)" for m in CALM.finditer(pos)]
    return list(dict.fromkeys(out))


def shot_size(camera):
    m = SIZES.search(camera or "")
    return m[1].lower() if m else ""


# User 2026-11-17: the prompts file is a .txt (no CSV any more); videos prompted before keep their .csv (read only).
PROMPT_FILES = ("missing-prompt.txt", "missing-prompt.csv")


def txt_text(rows):
    """One block per prompt (user 2026-11-17): a label line 'shot_id | tc_in -> tc_out | dur_s s' (file name to save,
    timeline slot, clip length), then the prompt as ONE paragraph (no line break: copy-paste into the generator; it
    already says length, camera, place, light, the action + direction, the shared TAIL). A blank line between blocks."""
    out = []
    for r in rows:
        slot = f"{r['tc_in']} -> {r['tc_out']}" if r.get("tc_in") else "no slot"
        out.append(f"{r['shot_id']} | {slot} | {r.get('dur_s') or '?'} s\n" + " ".join(str(r["generation_prompt"]).split()))
    return "\n\n".join(out) + "\n"


def prompt_file(vdir):
    """<vdir>/missing-prompt.txt, else the .csv of a video prompted before 2026-11-17, else the .txt path."""
    return next((p for p in (Path(vdir) / n for n in PROMPT_FILES) if p.exists()), Path(vdir) / PROMPT_FILES[0])


def prompt_rows(vdir):
    """[{shot_id, tc_in, tc_out, dur_s, generation_prompt}] of the video's .txt (the old .csv: all its columns);
    [] when there is none."""
    p = prompt_file(vdir)
    if not p.exists():
        return []
    text = p.read_text("utf-8-sig")
    if p.suffix == ".csv":
        return list(csv.DictReader(io.StringIO(text)))
    rows = []
    for block in re.split(r"\n\s*\n", text.strip()):
        head, _, prompt = block.partition("\n")
        sid, slot, dur = (x.strip() for x in (head.split("|") + ["", ""])[:3])
        tin, _, tout = slot.partition("->")
        rows.append({"shot_id": sid, "tc_in": tin.strip() if tout else "", "tc_out": tout.strip(),
                     "dur_s": dur.removesuffix("s").strip(), "generation_prompt": " ".join(prompt.split())})
    return rows


if __name__ == "__main__":
    assert [dur_s(x) for x in (3.2, 5, 3.5, 6, 8.7, 2.0, 4)] == [4.5, 6.0, 4.5, 7.0, 10.0, 3.0, 5.0]
    assert issues("A lioness sprints left to right, no standing still, no bite") == []
    assert issues("the leopard bites the kid")[0].startswith("contact")
    assert issues("two ibex stare at each other on the ledge")[0].startswith("stare")
    assert issues("the fox stands still, watching")[0].startswith("motion")
    assert issues(TAIL) == []
    assert paced(["A golden cat trots left to right"], 4.5).startswith("pace")
    assert paced(["A golden cat bolts left to right"], 4.5) is None and paced(["trots, then turns"], 4.5) is None
    assert paced(["no running, it trots"], 4.5) and paced(["trots"], 6) is None and paced(["a", "b"], 4.5) is None
    assert shot_id(r"D:\Chann_3_Wild\africa_101126_6", 9) == "c3v6_9" and shot_id(r"C:\tmp\x", 9) == "9"
    assert render("long lens", "savanna", "daylight", ["a"], 4.5).startswith(SPEED + ". Wildlife documentary")
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        assert prompt_rows(d) == [] and prompt_file(d).name == "missing-prompt.txt"
        (Path(d) / "missing-prompt.csv").write_text("shot_id,tc_in\nc1v1_1,00:05\n", "utf-8-sig")
        assert prompt_rows(d) == [{"shot_id": "c1v1_1", "tc_in": "00:05"}]  # old videos' .csv still read
        src = [{"shot_id": "c1v1_1", "tc_in": "00:12.0", "tc_out": "00:15.5", "dur_s": 4.5, "generation_prompt": 'a | b\nc'},
               {"shot_id": "c1v1_2", "tc_in": "", "dur_s": "", "generation_prompt": "x"}]
        txt = txt_text(src)
        assert txt.startswith("c1v1_1 | 00:12.0 -> 00:15.5 | 4.5 s\na | b c\n\nc1v1_2 | no slot | ? s\nx")
        prompt_file(d).with_suffix(".txt").write_text(txt, "utf-8")
        rows = prompt_rows(d)  # .txt wins over the .csv
        assert rows[0] == {"shot_id": "c1v1_1", "tc_in": "00:12.0", "tc_out": "00:15.5", "dur_s": "4.5",
                           "generation_prompt": "a | b c"}
        assert rows[1]["shot_id"] == "c1v1_2" and rows[1]["tc_in"] == "" and rows[1]["generation_prompt"] == "x"
    print("prompt_rules ok")
