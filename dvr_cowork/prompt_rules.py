"""Prompt rules shared by both engines (user 2026-11-05): footage+AI missing.py and full-AI dvr_cowork.fullai.story.

Every generated shot: no physical contact between animals, every animal in frame keeps moving, never a silent
stare-down. 8p prompts add the character / environment / light locks; 1h prompts do not. CSV = the 19-column
missing-scenes schema (input/missing-scenes-2-cinematic-revised.csv).
"""
import csv
import io
import math
import re

# Contact verbs (a keyword gate, not proof: QC still views the frames).
CONTACT = re.compile(r"\b(?:bit(?:e|es|ing|ten)|gor(?:e|es|ed|ing)|ram(?:s|med|ming)|headbutt\w*|tackl\w+|"
                     r"grab(?:s|bed|bing)?|seiz(?:e|es|ed|ing)|pins? (?:it|him|her|them|down)|pinned|shov(?:e|es|ed|ing)|"
                     r"knock(?:s|ed)? (?:down|over|into)|kill(?:s|ed|ing)?|wound(?:s|ed)?|blood(?:y)?|"
                     r"makes? contact|jaws (?:close|clamp)\w*|claws? (?:rake|sink|into)\w*|horns (?:meet|lock|clash)\w*|"
                     r"collid\w+|wrestl\w+|grappl\w+|drags? (?:it|him|her|the (?:prey|carcass|body))|"
                     r"strikes? (?:it|him|her|the)|struck)\b", re.I)
# Silent stare-downs: two animals frozen, looking at each other.
STARE = re.compile(r"\b(?:star(?:e|es|ing)|gaz(?:e|es|ing)|look(?:s|ing)?|glar(?:e|es|ing)) at each other\b|"
                   r"\blocks? eyes\b|\beyes lock(?:ed)?\b|\bface to face\b|\bstare-?down\b|\bstand-?off\b", re.I)
# Words that make a pose instead of motion ("slow" stays allowed here: sloths, slow push-in camera moves).
CALM = re.compile(r"\b(?:still(?:ness)?|motionless|gentl[ey]|calm(?:ly)?|paus(?:e|es|ing)|wait(?:s|ing)?|"
                  r"rest(?:s|ing)?|settl(?:e|es|ing)|idle|freez(?:e|es|ing)|frozen|pos(?:e|es|ing)|"
                  r"stands? (?:still|watching)|small movement)\b", re.I)
NEG = re.compile(r"\b(?:no|not|never|without|avoid)\b[^,.;]*", re.I)  # "no standing still" is a request, not a pose
# Appended to every prompt of both engines, after the authored text (so the gates never read it).
TAIL = ("Every animal in frame keeps moving for the whole shot (running, turning, stepping, scanning, ears and tail "
        "alive); never standing still, never silently staring at each other. No physical contact between animals: "
        "every lunge, swipe or charge misses by a body length. Natural anatomy, consistent screen direction, one "
        "continuous shot with no cuts, no blood, no gore, no narration, no music, natural sound only, no text, "
        "no logos, no watermark.")
COLUMNS = ("shot_id,cluster,tc_in,tc_out,dur_s,kind,animal,action,environment,time_of_day,shot_size,camera_angle,"
           "direction,position,keep_whole,mo_ta,search_keywords,generation_prompt,reason").split(",")
SIZES = re.compile(r"\b(extreme wide|very wide|wide|establishing|medium[- ]long|medium|close[- ]up|extreme close[- ]up|"
                   r"detail|aerial|top-down)\b", re.I)


def dur_s(seconds):
    """Generated clip length for a timeline slot: the next half second above it (3.2 -> 3.5, 5 -> 5.5)."""
    return (math.floor(float(seconds) * 2 + 1e-9) + 1) / 2


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


def csv_text(rows):
    """19-column CSV, UTF-8 BOM (Excel), every field quoted where needed."""
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=COLUMNS, extrasaction="raise")
    w.writeheader()
    for r in rows:
        w.writerow({k: "" if r.get(k) is None else r.get(k) for k in COLUMNS})
    return "﻿" + buf.getvalue()


if __name__ == "__main__":
    assert [dur_s(x) for x in (3.2, 5, 3.5, 6, 8.7, 2.0)] == [3.5, 5.5, 4.0, 6.5, 9.0, 2.5]
    assert issues("A lioness sprints left to right, no standing still, no bite") == []
    assert issues("the leopard bites the kid")[0].startswith("contact")
    assert issues("two ibex stare at each other on the ledge")[0].startswith("stare")
    assert issues("the fox stands still, watching")[0].startswith("motion")
    assert issues(TAIL) == []
    rows = list(csv.DictReader(io.StringIO(csv_text([{"shot_id": "1", "generation_prompt": 'a, "b"'}])[1:])))
    assert list(rows[0]) == COLUMNS and rows[0]["generation_prompt"] == 'a, "b"'
    print("prompt_rules ok")
