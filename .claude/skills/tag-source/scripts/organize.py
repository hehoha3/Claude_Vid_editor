"""Rename + file the tagged AI clips of D:\\AI_video\\_check into species folders (dry-run by default).

    .venv/Scripts/python .claude/skills/tag-source/scripts/organize.py            # dry-run: print the plan
    .venv/Scripts/python .claude/skills/tag-source/scripts/organize.py --apply    # move, verify every file
    .venv/Scripts/python .claude/skills/tag-source/scripts/organize.py --rename-stay [--apply]   # rename the clips that stay in _check
    .venv/Scripts/python .claude/skills/tag-source/scripts/organize.py --selftest

Only untitled clips (shot_*.*) in _check are handled; --all = every clip in _check (generator names like amazon-007). A clip stays in _check when it cannot be filed: no tags,
sure=false, a blocking issue (morph, unnatural, logo, watermark, text, dark, blur) or no folder for its species.
Name: <species>_<caption keywords>-<shot size>.mp4 (same style as the existing files).
Same drive -> Path.rename (atomic); never deletes. Run scan-source afterwards (hash keys keep the tags).
"""
import json, re, sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[4]), str(Path(__file__).resolve().parents[2] / "scan-source/scripts")]
from scan_source import ROOTS, index_of  # noqa: E402
ROOT = ROOTS["ai"][0]  # config.toml paths.ai_video
CHECK = ROOT / "_check"
BLOCK = {"morph", "unnatural", "logo", "watermark", "text", "dark", "blur"}
ALIAS = {"arapaima": "fish", "scarlet macaw": "bird", "buffalo": "forest_buffalo", "caiman": "crocodile_caiman", "crocodile": "crocodile_caiman", "howler monkey": "howler",
         "toucan": "toucan-bird", "giant otter": "otter", "river otter": "otter", "antelope": "deer",
         "muntjac": "deer", "red brocket deer": "brocket_deer", "brocket deer": "brocket_deer", "giant anteater": "anteater", "tapir calf": "tapir", "hippo calf": "hippo",
         "harpy eagle chick": "eagle", "python": "snake", "viper": "snake", "parrot": "bird", "macaw": "bird",
         "hornbill": "bird", "kingfisher": "bird", "songbird": "bird", "heron": "bird", "owl": "bird",
         "beetle": "insects", "termite": "insects", "ladybug": "insects", "bee": "insects", "wasp": "insects",
         "millipede": "insects", "praying mantis": "insects", "grasshopper": "insects", "tarantula": "spider",
         "piranha": "fish", "caracal": "wild_cat", "duiker": "red_duiker", "golden cat": "wild_cat", "wild cat": "wild_cat", "macaque": "monkey", "tamarin": "monkey"}
LAST = {"monkey", "eagle", "frog", "snake", "ant", "butterfly", "bird", "fish", "spider"}  # "spider monkey" -> monkey
LAST_TO = {"ant": "insects"}
STOP = set("a an the of on in at to and with its it is from into over under by for as near while then "
           "camera shot view close up wide medium aerial".split())


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def folder_for(sp, setting, folders):
    if not sp:  # landscape -> landscape/<setting>
        sub = next((s for s in setting if (ROOT / "landscape" / s).is_dir()), None)
        return f"landscape/{sub}" if sub else None
    main = sp[0].replace("_", " ")
    last = main.split()[-1]
    for c in (main.replace(" ", "_"), slug(main), ALIAS.get(main), LAST_TO.get(last), last if last in LAST else None):
        if c and c in folders:
            return c
    return None


def name_for(sp, t):
    words = [w for w in re.findall(r"[a-z]+", t["caption"].lower()) if w not in STOP]
    spw = set(" ".join(sp).replace("_", " ").split())
    words = [w for w in words if w not in spw][:6]
    head = slug(sp[0]) if sp else "landscape"
    return f"{head}_{'-'.join(words)}-{(t.get('shot_size') or 'medium').replace('_', '-')}"


def plan(clips, folders, every=False):
    moves, stay, taken = [], [], set()
    for c in clips:
        p = Path(c["path"])
        if p.parts[0] != "_check" or len(p.parts) != 2 or not (every or p.stem.startswith("shot_")):
            continue
        t = c.get("tags") or {}
        why = ("no tags" if not t.get("caption") else "sure=false" if not t.get("sure", True)
               else ",".join(sorted(BLOCK & set(t.get("issues", [])))))
        cap = t.get("caption", "").strip().lower()  # bare-setting captions ("canopy") name the landscape folder
        dest = None if why else folder_for(t.get("species", []), t.get("setting", []) + [{"undergrowth": "forest_floor"}.get(cap, cap)], folders)
        if not dest:
            stay.append((p.name, why or f"no folder for {t.get('species') or t.get('setting')}"))
            continue
        base = name_for(t.get("species", []), t)
        n, i = f"{base}{p.suffix}", 2
        while (ROOT / dest / n).exists() or f"{dest}/{n}" in taken:
            n, i = f"{base}-{i}{p.suffix}", i + 1
        taken.add(f"{dest}/{n}")
        moves.append((ROOT / p, ROOT / dest / n))
    return moves, stay


def main(apply, every=False):
    d = json.loads(index_of(ROOT).read_text("utf-8"))["clips"]
    folders = {p.name for p in ROOT.iterdir() if p.is_dir() and not p.name.startswith("_")}
    moves, stay = plan(d.values() if isinstance(d, dict) else d, folders, every)
    by = {}
    for _, dst in moves:
        by[dst.parent.relative_to(ROOT).as_posix()] = by.get(dst.parent.relative_to(ROOT).as_posix(), 0) + 1
    print(f"move {len(moves)} -> {dict(sorted(by.items()))}")
    for s, dst in moves[:8]:
        print(f"  {s.name} -> {dst.relative_to(ROOT)}")
    reasons = {}
    for _, why in stay:
        k = why.split(" [")[0] if why.startswith("no folder") else why
        reasons[k] = reasons.get(k, 0) + 1
    print(f"stay in _check {len(stay)}: {reasons}")
    if not apply:
        print("dry-run: nothing moved (--apply to move)")
        return
    bad = []
    for s, dst in moves:
        assert s.exists() and not dst.exists(), f"refusing: {s} / {dst}"
        s.rename(dst)
        if not dst.exists() or s.exists():
            bad.append(s.name)
    print(f"moved {len(moves) - len(bad)}/{len(moves)}; failed: {bad}")


def rename_stay(apply, every=False):
    """Rename leftover shot_* clips in _check in place (same name style, no species -> 'unknown')."""
    d = json.loads(index_of(ROOT).read_text("utf-8"))["clips"]
    ren, taken = [], set()
    for c in (d.values() if isinstance(d, dict) else d):
        p = Path(c["path"])
        t = c.get("tags") or {}
        if p.parts[0] != "_check" or len(p.parts) != 2 or not (every or p.stem.startswith("shot_")) or not t.get("caption"):
            continue
        base = name_for(t.get("species", []), t)
        n, i = f"{base}{p.suffix}", 2
        while (CHECK / n).exists() or n in taken:
            n, i = f"{base}-{i}{p.suffix}", i + 1
        taken.add(n)
        ren.append((CHECK / p.name, CHECK / n))
    for a, b in ren[:6]:
        print(f"  {a.name} -> {b.name}")
    print(f"rename {len(ren)} in _check" + ("" if apply else " (dry-run, --apply to rename)"))
    if apply:
        bad = []
        for a, b in ren:
            assert a.exists() and not b.exists(), f"refusing: {a} / {b}"
            a.rename(b)
            if not b.exists() or a.exists():
                bad.append(a.name)
        print(f"renamed {len(ren) - len(bad)}/{len(ren)}; failed: {bad}")


def selftest():
    folders = {"crocodile_caiman", "monkey", "insects", "eagle", "deer"}
    f = lambda sp, st=(): folder_for(sp, list(st), folders)  # noqa: E731
    assert f(["caiman"]) == "crocodile_caiman" and f(["spider monkey"]) == "monkey"
    assert f(["leafcutter ant"]) == "insects" and f(["harpy eagle"]) == "eagle" and f(["caracal"]) is None
    assert f(["golden_cat"]) is None
    t = {"caption": "Spider monkey leaps between branches in the canopy at dawn", "shot_size": "close_up"}
    assert name_for(["spider monkey"], t) == "spider-monkey_leaps-between-branches-canopy-dawn-close-up"
    cl = [{"path": "_check\\shot_001.mp4", "tags": {"caption": "x", "sure": False, "species": ["caiman"]}},
          {"path": "_check\\shot_002.mp4", "tags": {"caption": "x", "sure": True, "issues": ["morph"], "species": ["caiman"]}},
          {"path": "_check\\named_clip.mp4", "tags": {"caption": "x", "sure": True, "species": ["caiman"]}}]
    m, s = plan(cl, folders)
    assert not m and [w for _, w in s] == ["sure=false", "morph"]
    m, s = plan(cl, folders, every=True)
    assert [d.parent.name for _, d in m] == ["crocodile_caiman"] and len(s) == 2
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--allow-blur-dark" in sys.argv:  # file blur/dark clips too (issues stay in the tags)
        BLOCK -= {"blur", "dark"}
    selftest() if "--selftest" in sys.argv else rename_stay("--apply" in sys.argv, "--all" in sys.argv) if "--rename-stay" in sys.argv         else main("--apply" in sys.argv, "--all" in sys.argv)
