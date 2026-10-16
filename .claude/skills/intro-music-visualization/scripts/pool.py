"""intro-music-visualization: candidate pool in bin "7. Open" (subbins attack / run) of the current Resolve project.

    .venv/Scripts/python.exe .claude/skills/intro-music-visualization/scripts/pool.py list
    .venv/Scripts/python.exe .claude/skills/intro-music-visualization/scripts/pool.py add --need 22 [--extra 20] [--cast jaguar,harpy_eagle] [--video <name>] [--dry-run]
    (--world-only = just the landscape / insect / bird inserts, other categories untouched)
    (--cast = the film's characters, library species names, '_' = space: ranked first in every category)
    .venv/Scripts/python.exe .claude/skills/intro-music-visualization/scripts/pool.py --selftest

list: every clip in the bin tree with its library tags (one line each, numbered P1..Pn) -> what Claude picks from.
add:  tops the bin up to need + extra clips from the tagged library (additive: imports only, never removes),
      by category quota: eyes = predator face / eye close-ups (root bin), attack = attack / hunt / fight / stalk
      (subbin "attack"), run = running / chasing (subbin "run"), other = other animals: prey, reactions (root),
      scenic = still wides (sunset, sky, river, canopy: opening world shot, breath, ending) and animals looking at
      camera (root).
      Only clips on timelines "Open" + "Edit" of the last N videos of the same workspace are banned (doc-edit
      ledger.py / check-timelines, <video> itself excluded; --video defaults to the project name). Clips with issues (logo...) rank lower, never banned.
"""
import json, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / ".claude/skills/doc-edit/scripts"), str(ROOT / ".claude/skills/scan-source/scripts")]
from plan import load_clips, usable  # noqa: E402
import ledger  # noqa: E402

BIN, SUBS = "7. Open", ("attack", "run")
PREDATORS = {"jaguar", "leopard", "lion", "tiger", "wild cat", "golden cat", "caracal", "ocelot", "puma", "spotted hyena",
             "caiman", "crocodile", "alligator", "anaconda", "snake", "python", "rock python", "green snake",
             "eagle", "harpy eagle", "owl", "hippo", "tarantula", "giant otter"}
QUOTA = {"eyes": 0.25, "attack": 0.25, "run": 0.20, "other": 0.15, "scenic": 0.15}
BIN_OF = {"attack": "attack", "run": "run"}  # other categories live in the root bin
MIN_LEN = 1.5      # s of usable picture
WORLD = {"landscape": 4, "insects": 3, "birds": 3}  # world / forest / insect / bird inserts, always added (user 2026-10-15)
SPECIES_MAX = 0.3  # share of one species inside a category: keeps the montage from being all jaguar


def category(c):
    t = c["tags"]
    act, sp, size = set(t.get("action") or []), set(t.get("species") or []), t.get("shot_size")
    pred = bool(sp & PREDATORS)
    if act & {"attack", "hunt", "fight", "stalk"} and t.get("count") != "none":
        return "attack"
    if "run" in act and t.get("count") != "none":
        return "run"
    if pred and size in ("extreme_close", "close_up"):
        return "eyes"
    if t.get("camera") == "static" and (t.get("count") == "none" or not sp) and size in ("wide", "aerial") \
            and t.get("mood") in ("calm", "majestic", "eerie"):
        return "scenic"
    if sp and "look" in act and t.get("direction") == "toward" and size in ("close_up", "medium", "extreme_close"):
        return "scenic"
    if sp and size in ("extreme_close", "close_up", "medium") and act & {"look", "call", "rest", "none", "jump", "climb"}:
        return "other"
    return None


def score(c, cat):
    t = c["tags"]
    s = 1.0 if t.get("mood") in ("tense", "dramatic", "eerie") else 0.3 if t.get("mood") == "majestic" else 0.0
    s += 1.0 if set(t.get("species") or []) & PREDATORS else 0.0
    s += 0.5 if cat == "eyes" and t.get("shot_size") == "extreme_close" else 0.0
    s += 1.0 if cat == "attack" and set(t.get("action") or []) & {"attack", "hunt", "fight"} else 0.0  # strikes for drops
    s += 0.5 if cat == "run" and t.get("mood") == "dramatic" else 0.0
    s += 0.5 if cat == "scenic" and t.get("direction") == "toward" else 0.0
    s += 1.5 if cat == "scenic" and not t.get("species") else 0.0  # landscapes compete with stares into the lens
    s += 0.3 if c["source"] == "real" else 0.0
    s += 0.3 if (c.get("yolo") or {}).get("seen", 0) >= 0.6 else 0.0
    s -= 0.4 * len(t.get("issues") or []) + (0.2 if not t.get("sure", True) else 0.0)
    return s


def world_kind(c):
    """'landscape' / 'insects' / 'birds' by library folder (supplementary_shots/insects), else None."""
    p = Path(c["path"].replace("\\", "/")).parts
    k = p[1] if p[0].lower() == "supplementary_shots" and len(p) > 1 else p[0]
    return k.lower() if k.lower() in WORLD else None


def pick_world(lib, in_bin, banned):
    """WORLD quota of clips not in the bin yet: real first, no issues, at most 2 per subfolder (spread of places)."""
    out = {}
    for c in lib:
        k = world_kind(c)
        if k and norm(c["abs"]) not in in_bin and c["id"] not in banned and (lambda u: u[1] - u[0] >= MIN_LEN)(usable(c)):
            out.setdefault(k, []).append(c)
    add = []
    for k, n in WORLD.items():
        seen = Counter()
        for c in sorted(out.get(k, []), key=lambda c: (c["source"] != "real", len(c["tags"].get("issues") or []))):
            sub = Path(c["path"].replace("\\", "/")).parts[:-1]
            if len(add) < sum(list(WORLD.values())[:list(WORLD).index(k) + 1]) and seen[sub] < 2:
                add.append(c)
                seen[sub] += 1
    return add


def pick(clips, n, have=()):
    """n best clips of one category, species capped at SPECIES_MAX share (relaxed if the category runs short)."""
    have = list(have)
    cap = max(1, round(SPECIES_MAX * (n + len(have))))
    used = Counter(s for c in have for s in c["tags"].get("species", [])[:1])
    out, rest = [], []
    for c in sorted(clips, key=lambda c: -c["_score"]):
        sp = (c["tags"].get("species") or ["none"])[0]
        (out if used[sp] < cap and len(out) < n else rest).append(c)
        if c in out:
            used[sp] += 1
    return out + rest[:n - len(out)]


def bin_tree(mp):
    root = mp.GetRootFolder()
    top = next((f for f in root.GetSubFolderList() or [] if f.GetName() == BIN), None)
    if not top:
        top = mp.AddSubFolder(root, BIN)
    subs = {f.GetName(): f for f in top.GetSubFolderList() or []}
    return top, subs


def bin_clips(top, name=BIN):
    """-> [(bin name, MediaPoolItem)] for the whole folder tree under `top`."""
    out, todo = [], [(top, name)]
    while todo:
        f, name = todo.pop()
        out += [(name, it) for it in f.GetClipList() or [] if it.GetClipProperty("File Path")]
        todo += [(s, s.GetName()) for s in f.GetSubFolderList() or []]
    return out


def connect_mp():
    from dvr_cowork.config import load_config
    from dvr_cowork.resolve_conn import connect
    from dvr_cowork.resolve_ops import get_project
    pm, project = get_project(connect(load_config()))
    return pm, project, project.GetMediaPool()


def norm(p):
    return str(Path(p)).lower()


def cmd_list():
    pm, project, mp = connect_mp()
    top, _ = bin_tree(mp)
    lib = {norm(c["abs"]): c for c in load_clips()}
    rows = sorted(bin_clips(top), key=lambda x: (x[0] != BIN, x[0], x[1].GetName()))
    print(f'project "{project.GetName()}", bin "{BIN}": {len(rows)} clips '
          f'({", ".join(f"{k} {v}" for k, v in Counter(b for b, _ in rows).items())})')
    print("P# | bin | src | species | action | size | mood | dir | usable s | issues | file | caption")
    for k, (b, it) in enumerate(rows, 1):
        c = lib.get(norm(it.GetClipProperty("File Path")))
        if not c:
            print(f"P{k} | {b} | ? | untagged | | | | | {it.GetClipProperty('Duration')} | | {it.GetName()} |")
            continue
        t = c["tags"]; a, z = usable(c)
        print(f"P{k} | {b} | {c['source']} | {','.join(t.get('species') or ['-'])} | {','.join(t.get('action') or [])} | "
              f"{t.get('shot_size')} | {t.get('mood')} | {t.get('direction')} | {a:.1f}-{z:.1f} | "
              f"{','.join(t.get('issues') or [])} | {Path(c['path']).name[:60]} | {t['caption'][:90]}")


def plan_add(lib, in_bin, need, extra, banned=frozenset(), cast=frozenset()):
    """-> {category: [clips to add]} so that every category reaches its quota of need + extra."""
    total = need + extra
    have, pools = defaultdict(list), defaultdict(list)
    for c in lib:
        cat = category(c)
        if norm(c["abs"]) in in_bin:
            have[cat or "other"].append(c)
            continue
        a, z = usable(c)
        if cat and c["id"] not in banned and z - a >= MIN_LEN:
            sp = set(c["tags"].get("species") or [])
            c["_score"] = score(c, cat) + (1.5 if cast & sp else 0.0) - (1.5 if cast and (sp - cast) & PREDATORS else 0.0)
            # ponytail: a leopard tagged "jaguar,leopard" is still a leopard: off-cast predators sink when a cast is given
            pools[cat].append(c)
    add = {}
    for cat, q in QUOTA.items():
        want = max(6 if cat == "scenic" else 0, round(q * total)) - len(have[cat])
        add[cat] = pick(pools[cat], max(0, want), have[cat])
    add["world"] = pick_world(lib, in_bin, banned)
    return add, have


def cmd_add(need, extra, dry, video=None, cast=frozenset(), world_only=False):
    pm, project, mp = connect_mp()
    video = video or project.GetName()
    top, subs = bin_tree(mp)
    in_bin = {norm(it.GetClipProperty("File Path")) for _, it in bin_clips(top)}
    banned, vids = ledger.banned(video)
    add, have = plan_add(load_clips(), in_bin, need, extra, banned, cast)
    if world_only:  # bin already built / hand-edited: only the world inserts
        add = {"world": add["world"]}
    print(f"target {need} used + {extra} spare = {need + extra}; already in bin {len(in_bin)}; "
          f"banned {len(banned)} clips (Open + Edit of {', '.join(vids) or 'no checked video'} in this workspace)")
    for cat, cs in add.items():
        sp = Counter((c["tags"].get("species") or ["none"])[0] for c in cs).most_common(6)
        print(f"  {cat:6s} have {len(have[cat]):3d} + add {len(cs):3d} -> bin {BIN_OF.get(cat, BIN)} | {sp}")
    if dry:
        print("dry-run: nothing imported")
        return
    n = 0
    for cat, cs in add.items():
        if not cs:
            continue
        name = BIN_OF.get(cat)
        folder = top if not name else subs.get(name) or mp.AddSubFolder(top, name)
        subs[name] = folder
        mp.SetCurrentFolder(folder)
        n += len(mp.ImportMedia([c["abs"] for c in cs]) or [])
    pm.SaveProject()
    print(f"imported {n}/{sum(map(len, add.values()))} clips into {BIN} (+ {', '.join(SUBS)})")


def selftest():
    assert world_kind({"path": "supplementary_shots/insects/a.mp4"}) == "insects" and world_kind({"path": "landscape/river/a.mp4"}) == "landscape"
    assert world_kind({"path": "jaguar/a.mp4"}) is None and world_kind({"path": "birds/a.mp4"}) == "birds"
    def clip(i, sp, act, size, **kw):
        t = {"species": [sp] if sp else [], "action": act, "shot_size": size, "count": "one" if sp else "none",
             "mood": "tense", "caption": "x", "camera": "static", **kw}
        return {"abs": f"X:/c{i}.mp4", "id": str(i), "source": "real", "duration": 8.0, "tags": t, "path": f"c{i}.mp4"}
    assert category(clip(1, "jaguar", ["stalk"], "medium")) == "attack"
    assert category(clip(2, "jaguar", ["run"], "wide")) == "run"
    assert category(clip(3, "jaguar", ["look"], "extreme_close")) == "eyes"
    assert category(clip(4, None, ["none"], "wide", mood="calm")) == "scenic"
    assert category(clip(5, "frog", ["look"], "close_up", direction="toward")) == "scenic"
    assert category(clip(6, "capybara", ["look"], "close_up")) == "other"
    lib = [clip(i, "jaguar" if i % 2 else "caiman", ["look"], "close_up") for i in range(40)]
    lib += [clip(100 + i, "jaguar", ["attack"], "medium") for i in range(5)]
    lib.append(clip(200, "jaguar", ["attack"], "medium", issues=["logo"]))
    add, have = plan_add(lib, {norm("X:/c0.mp4")}, 10, 10)
    assert len(add["eyes"]) == 5 - 1, len(add["eyes"])  # 25% of 20, one already in the bin
    assert len(add["attack"]) == 5 and "200" not in {c["id"] for c in add["attack"]}  # logo clip ranks last...
    add, _ = plan_add(lib, set(), 12, 12)
    assert add["attack"][-1]["id"] == "200"                                         # ...but is not banned
    leo = clip(300, "jaguar", ["look"], "extreme_close"); leo["tags"]["species"] = ["jaguar", "leopard"]
    add, _ = plan_add(lib + [leo], set(), 10, 10, cast={"jaguar", "caiman"})
    assert "300" not in {c["id"] for c in add["eyes"]}  # off-cast predator (leopard) sinks below the cast
    stalk = [clip(400 + i, "jaguar", ["stalk"], "medium") for i in range(6)]
    add, _ = plan_add(stalk + lib[40:45], set(), 10, 10)
    assert {c["id"] for c in add["attack"]} == {str(100 + i) for i in range(5)}  # strikes rank above stalking
    add, _ = plan_add(lib, set(), 10, 10, banned={"100", "101"})
    assert not {"100", "101"} & {c["id"] for c in add["attack"]}  # only the ledger bans
    print("selftest ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["--selftest"]:
        selftest()
    elif a[:1] == ["list"]:
        cmd_list()
    elif a[:1] == ["add"]:
        cmd_add(int(a[a.index("--need") + 1]), int(a[a.index("--extra") + 1]) if "--extra" in a else 20, "--dry-run" in a,
                a[a.index("--video") + 1] if "--video" in a else None,
                {x.strip().replace("_", " ") for x in a[a.index("--cast") + 1].split(",")} if "--cast" in a else set(),
                "--world-only" in a)
    else:
        print(__doc__)
