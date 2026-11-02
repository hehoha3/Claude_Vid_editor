"""Fill the Vietnamese of the source's narrator lines with Gemini (user 2026-11-01: Claude writes the English, Gemini
translates, Claude reviews). Only lines whose VI is empty, a copy of the EN or still ASCII (build_four_files' own
"untranslated" test) are sent; EN, weight and pin stay byte-identical; nothing else in the source changes.

    .venv/Scripts/python.exe .claude/skills/create-doc-mov/scripts/translate_vi.py <four_files.src.md> --glossary "spectacled caiman=cá sấu caiman kính; hoatzin=chim hoatzin" [--dry]
    .venv/Scripts/python.exe .claude/skills/create-doc-mov/scripts/translate_vi.py --selftest

--glossary (required): Claude's Vietnamese name of every species / place of the BIBLE, so one animal is named one way
(the 2026-11-01 test without it: "spectacled caiman" -> "caiman tai tượng", a fish). Context sent with every batch:
META + BIBLE, the glossary, every EN line in order (pronouns and names carry across lines), up to 40 lines already
translated (tone). Batches of BATCH lines, one gemini-3.5-flash call each (thinking medium), JSON {"<line n>": "<vi>"}.
Prints only the new lines with a FLAG (digits lost, length far off, glossary name missing) or a glossary name as
`n | EN => VI` (user 2026-11-02, token saving); every new line goes to .work/gemini/<video>/review.txt. Claude fixes
meaning, names, spelling of the printed ones with Edit in the source.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BATCH = 100  # every call re-sends lines.txt (implicit cache discounts it); fewer, larger batches = fewer calls
TASK = """Translate the English narrator lines numbered {nums} (lines.txt) into Vietnamese subtitles for this film.
Natural spoken Vietnamese in a calm BBC documentary narrator tone; the whole meaning of each line, never shortened, nothing added; one line each, no line breaks.
Keep every number and unit as written in digits or words. Species and place names: exactly the GLOSSARY of context.txt, the same way in every line; "chick" = chim non, "calf"/"cub"/"pup" = the young of that animal.
Correct Vietnamese spelling and diacritics (khoảnh khắc, not khoảng khắc).
JSON object, only those numbers: {{"<n>": "<Vietnamese>"}}"""


def lines_of(src):
    """[(file line index, n, en, vi, rest fields)] of every '> EN || VI || weight || @pin' line, n = 1.. in film order."""
    out = []
    for i, line in enumerate(src.splitlines()):
        if line.startswith("> "):
            bits = [x.strip() for x in line[2:].split("||")]
            out.append((i, len(out) + 1, bits[0], bits[1] if len(bits) > 1 else "", bits[2:]))
    return out


def untranslated(en, vi):
    return not vi or vi == en or vi.isascii()  # same test as build_four_files.build


def with_vi(en, vi, rest):
    """The source line again with a new VI; trailing empty fields after VI dropped, inner ones kept ('||  || @2')."""
    while rest and not rest[-1]:
        rest = rest[:-1]
    return "> " + " || ".join([en, vi] + rest)


def section(src, name):
    m = re.search(rf"^=== {name}\s*$(.*?)(?=^=== |\Z)", src, re.M | re.S)
    return m[1].strip() if m else ""


def parse_glossary(s):
    """'spectacled caiman=cá sấu caiman kính; hoatzin=chim hoatzin' -> {en lower: vi}."""
    return {a.strip().lower(): b.strip() for a, _, b in (x.partition("=") for x in s.split(";")) if a.strip() and b.strip()}


def flags(en, vi, gloss=None):
    f = [f"'{k}' not as '{v}'" for k, v in (gloss or {}).items()
         if re.search(rf"\b{re.escape(k)}s?\b", en.lower()) and v.lower() not in vi.lower()]
    if set(re.findall(r"\d+", en)) - set(re.findall(r"\d+", vi)):
        f.append("digits lost")
    if not 0.6 <= len(vi) / max(1, len(en)) <= 2.2:
        f.append(f"length {len(vi)} vs EN {len(en)}")
    return f


def review_row(n, en, vi, gloss):
    """-> ('n | EN => VI  FLAG ...', shown in stdout?). Shown = a FLAG or a glossary name in the line (user 2026-11-02:
    Claude reads those, the rest only in review.txt, ~700 lines of a 1 h film were ~40k Claude tokens)."""
    fl = flags(en, vi, gloss)
    named = any(re.search(rf"\b{re.escape(k)}s?\b", en.lower()) for k in gloss)
    return f"{n} | {en} => {vi}" + "".join(f"  FLAG {f}" for f in fl), bool(fl or named)


def run(path, glossary, dry=False):
    sys.path.insert(0, str(ROOT))
    from dvr_cowork.gemini import ask
    path = Path(path)
    src = path.read_text("utf-8")
    ls = lines_of(src)
    todo = [x for x in ls if untranslated(x[2], x[3])]
    gloss = parse_glossary(glossary)
    print(f"translate_vi {path.parent.name}: {len(ls)} lines, {len(todo)} to translate, glossary {len(gloss)} names")
    if not todo or dry:
        return
    if not gloss:
        sys.exit('translate_vi: --glossary "english name=tên tiếng Việt; ..." is required (every species / place of the BIBLE)')
    gdir = ROOT / ".work" / "gemini" / path.parent.name
    gdir.mkdir(parents=True, exist_ok=True)
    done = [x for x in ls if not untranslated(x[2], x[3])][:40]
    (gdir / "context.txt").write_text("\n\n".join([section(src, "META"), "BIBLE:\n" + section(src, "BIBLE"),
                                                   "GLOSSARY (English = Vietnamese):\n" + "\n".join(f"{k} = {v}" for k, v in gloss.items()),
                                                   "TRANSLATED EXAMPLES:\n" + "\n".join(f"{x[2]} => {x[3]}" for x in done)]),
                                      "utf-8")
    (gdir / "lines.txt").write_text("\n".join(f"{n}: {en}" for _, n, en, _, _ in ls), "utf-8")
    vi, used, models = {}, [0, 0], set()
    for b in range(0, len(todo), BATCH):
        part = todo[b:b + BATCH]
        try:
            text, st = ask(TASK.format(nums=", ".join(str(x[1]) for x in part)), [gdir / "context.txt", gdir / "lines.txt"],
                           json_out=True, thinking="medium", max_tokens=24000, max_input=120000, model="gemini-3.5-flash")
            got = {int(k): v.strip() for k, v in json.loads(text).items() if isinstance(v, str)}
        except (SystemExit, ValueError, AttributeError) as e:  # keep the batches already paid for; a re-run does the rest
            print(f"batch {b // BATCH + 1} failed: {str(e)[:200]}; stopped, writing what is done")
            break
        vi |= {k: v for k, v in got.items() if k in {x[1] for x in part}}
        if "cache" not in st["model"]:
            used[0] += st.get("in", 0)
            used[1] += st.get("out", 0) + st.get("thoughts", 0)
        models.add(st["model"])
    rows = src.splitlines()
    for i, n, en, _, rest in todo:
        if n in vi and not untranslated(en, vi[n]):
            rows[i] = with_vi(en, vi[n], rest)
    path.write_text("\n".join(rows) + ("\n" if src.endswith("\n") else ""), "utf-8")
    missing = [x[1] for x in todo if x[1] not in vi or untranslated(x[2], vi[x[1]])]
    print(f"{', '.join(sorted(models))} in {used[0]} out {used[1]} tokens; written {len(todo) - len(missing)}")
    rev = [review_row(n, en, vi[n], gloss) for _, n, en, _, _ in todo if n in vi and n not in missing]
    (gdir / "review.txt").write_text("\n".join(r for r, _ in rev) + "\n", "utf-8")
    for r, show in rev:
        if show:
            print(r)
    print(f"shown {sum(s for _, s in rev)} of {len(rev)} (FLAG or a glossary name); every line: {gdir / 'review.txt'}")
    if missing:
        print(f"NOT translated (re-run translate_vi.py for them, else write them by hand): {missing}")


def selftest():
    src = ("=== META\ntitle: T\n=== BIBLE\nJG jaguar = báo đốm\n=== SCENES\n@ 1 | 00:00 | 00:10 | A\n"
           "> The river is calm. || Dòng sông yên ả.\n> The wake stops. ||  ||  || @2\n> It misses. || It misses.\n"
           "> Ten metres. 10 m. || \n")
    ls = lines_of(src)
    assert [(n, en) for _, n, en, _, _ in ls][:2] == [(1, "The river is calm."), (2, "The wake stops.")]
    assert [x[1] for x in ls if untranslated(x[2], x[3])] == [2, 3, 4]
    assert with_vi("The wake stops.", "Vệt sóng dừng lại.", ["", "@2"]) == "> The wake stops. || Vệt sóng dừng lại. ||  || @2"
    assert with_vi("It misses.", "Nó vồ trượt.", []) == "> It misses. || Nó vồ trượt."
    assert with_vi("Ten metres. 10 m.", "Mười mét.", [""]) == "> Ten metres. 10 m. || Mười mét."
    assert section(src, "BIBLE") == "JG jaguar = báo đốm"
    assert flags("Ten metres. 10 m.", "Mười mét. Mười mét.") == ["digits lost"]
    assert flags("It misses.", "Nó vồ trượt.") == []
    assert flags("The wake stops.", "Vệt") == ["length 3 vs EN 15"]
    g = parse_glossary("spectacled caiman=cá sấu caiman kính; hoatzin = chim hoatzin;")
    assert g == {"spectacled caiman": "cá sấu caiman kính", "hoatzin": "chim hoatzin"}, g
    assert flags("Spectacled caimans haul out here.", "Caiman tai tượng bò lên đây.", g) == \
        ["'spectacled caiman' not as 'cá sấu caiman kính'"]
    assert flags("Spectacled caimans haul out here.", "Cá sấu caiman kính bò lên đây.", g) == []
    assert review_row(5, "Spectacled caimans haul out here.", "Cá sấu caiman kính bò lên đây.", g) == \
        ("5 | Spectacled caimans haul out here. => Cá sấu caiman kính bò lên đây.", True)  # glossary name -> shown
    assert review_row(6, "It misses.", "Nó vồ trượt.", g) == ("6 | It misses. => Nó vồ trượt.", False)
    assert review_row(7, "The wake stops.", "Vệt", g)[1] is True  # FLAG -> shown
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if "--selftest" in a:
        selftest()
    elif a:
        run(a[0], a[a.index("--glossary") + 1] if "--glossary" in a else "", "--dry" in a)
    else:
        sys.exit(__doc__)
