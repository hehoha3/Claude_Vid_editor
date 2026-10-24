#!/usr/bin/env python3
"""Content tags for every clip of the scan-source video indexes (one vision pass per clip, kept by hash).

    tag_source.py status                         tagged / untagged per root
    tag_source.py prepare [<video root>...] [--limit N] [--sample N] [--subject lion,hyena]
                                                 default: every video root; --sample = per root, or per root and
                                                 subject with --subject (folder species, scan-source `subject`)
                                                 contact sheets + batch files of 20 for the Sonnet taggers
    tag_source.py prepare ... --retag action,sex,age,outcome,phase
                                                 tagged clips missing these fields (tags["rt"]): the tagger writes only
                                                 them, apply merges them (caption, best, YOLO kept)
    tag_source.py apply <batch_NN>... [--no-yolo] validate the tagger's result file, merge into the root's index,
                                                 then YOLO-measure the clips just tagged (doc-edit/scripts/yolo.py)
    tag_source.py review <batch_NN>...           markdown table for the user to check

A contact sheet = 4 frames at 15/40/65/90 % of the clip (AI clips morph at the very start/end), 2x2,
numbered 1-4 left-to-right, top-to-bottom. Tags live in clip["tags"] with "v": 2; untagged = no v2 tags."""
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scan-source" / "scripts"))
from scan_source import ROOTS, index_of, save  # noqa: E402

WORK = Path(__file__).resolve().parents[4] / ".work" / "tag_source"
POS = (0.15, 0.40, 0.65, 0.90)
BATCH = 20
V = 2
LONG = 600.0  # s: longer files are whole films (AI_copyright\bản quyền: 40 min-3 h), not clips: never tagged, so never planned
VOCAB = {
    "count": {"none", "one", "two", "few", "many"},
    # 2026-10-23 (doc-edit story first): hunt -> chase / catch, + hide; 'hunt' stays valid for clips tagged before
    "action": {"rest", "sleep", "look", "walk", "run", "stalk", "hide", "chase", "catch", "hunt", "attack", "eat", "feed",
               "drink", "swim", "fly", "perch", "climb", "hang", "jump", "fight", "groom", "play", "call", "carry_young",
               "none"},
    "sex": {"female", "male", "mixed", "unknown"},       # of the main animal; plan.py sex= / age= / out= are hard
    "age": {"adult", "young", "mixed", "unknown"},
    "outcome": {"none", "miss", "catch", "kill", "unknown"},
    "shot_size": {"extreme_close", "close_up", "medium", "wide", "aerial"},
    "angle": {"eye", "low", "high", "top_down"},
    "camera": {"static", "moving"},
    "light": {"day", "golden", "dusk", "night", "moon"},
    "setting": {"canopy", "forest", "forest_floor", "undergrowth", "river", "riverbank", "lake", "swamp",
                "waterfall", "underwater", "grassland", "rock", "cave", "sky", "moon", "mountain", "village",
                "savanna", "waterhole", "desert"},   # last three: Africa (2026-10-20)
    "weather": {"clear", "mist", "rain", "storm", "none"},
    "mood": {"calm", "tense", "dramatic", "playful", "majestic", "eerie"},
    "direction": {"left", "right", "toward", "away", "none"},
    "issues": {"logo", "text", "morph", "unnatural", "blur", "dark", "watermark", "frame_cut"},
}
LISTS = {"action", "setting", "issues", "good"}
# fields of the 2026-10-23 tagger: a clip tagged before gets them with 'prepare --retag' (tags["rt"] = fields done)
RETAG = ("action", "sex", "age", "outcome", "phase")
GENERIC = {"landscape", "bird", "birds", "insects", "flowers"}
# folder name -> species name used in tags, where they differ
FOLDER_SPECIES = {"howler": "howler monkey", "toucan-bird": "toucan", "crocodile_caiman": "crocodile",
                  "frogs": "frog", "spider": "spider"}


def folder_species(folder):
    if not folder or folder.lower() in GENERIC or folder.startswith("_") or folder.lower() == "others":
        return None  # _check etc. = holding folders, not a species
    f = folder.lower()
    return FOLDER_SPECIES.get(f, f[:-1] if f.endswith("s") and not f.endswith("ss") else f)


def load(root):
    p = index_of(root)
    return json.loads(p.read_text(encoding="utf-8"))


def untagged(idx):
    return {k: c for k, c in idx["clips"].items() if (c.get("tags") or {}).get("v") != V}


def needs_retag(idx, fields):
    """Tagged clips still missing one of these fields (rt = the fields the current tagger already gave)."""
    return {k: c for k, c in idx["clips"].items() if (c.get("tags") or {}).get("v") == V
            and set(fields) - set(c["tags"].get("rt") or [])}


def sheet(src, dur, dst):
    ins = sum((["-ss", f"{dur * t:.2f}", "-i", str(src)] for t in POS), [])
    # setparams: some ProRes .mov carry no transfer tag and swscale then refuses them (rhino/warthog/ostrich clips)
    fc = "".join(f"[{i}:v]setparams=color_trc=bt709,scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:-1:-1,"
                 f"drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text={i + 1}:x=8:y=6:fontsize=30:"
                 f"fontcolor=yellow:box=1:boxcolor=black@0.7:boxborderw=6[f{i}];" for i in range(4))
    fc += "[f0][f1][f2][f3]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0[v]"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", fc, "-map", "[v]",
                        "-frames:v", "1", "-q:v", "4", "-strict", "unofficial", str(dst)],
                       capture_output=True, text=True)  # unofficial: mjpeg refuses limited-range YUV otherwise
    return r.returncode == 0 and dst.exists()


def no_animal(c):
    return not [s for s in (c.get("tags") or {}).get("species", []) if s and s != "none"]


def fill_no_animal(names):
    """Story fields of a clip without an animal need no vision (user 2026-10-23: tokens): written directly, and their
    retag rows leave every batch file not tagged yet (an emptied batch stays as [], skip it)."""
    ids, n = set(), 0
    for name in names:
        root, kind, _ = ROOTS[name]
        if not index_of(root).exists():
            continue
        idx = load(root)
        ids |= {k for k, c in idx["clips"].items() if (c.get("tags") or {}).get("v") == V and no_animal(c)}
        todo = [c for c in needs_retag(idx, RETAG).values() if no_animal(c)]
        for c in todo:
            c["tags"].update(sex="unknown", age="unknown", outcome="none", phase=None,
                             rt=sorted(set(c["tags"].get("rt") or []) | set(RETAG)))
        n += len(todo)
        if todo:
            save(root, kind, idx)
    empty = []
    for p in WORK.glob("batch_*.json"):
        if "result" in p.stem or (WORK / f"{p.stem}_result.json").exists():
            continue
        rows = json.loads(p.read_text(encoding="utf-8"))
        keep = [r for r in rows if not (r.get("fields") and r["id"] in ids)]
        if len(keep) != len(rows):
            p.write_text(json.dumps(keep, indent=1, ensure_ascii=False), encoding="utf-8")
        if not keep:
            empty.append(p.stem)
    print(f"no-animal clips filled without vision: {n}; empty batches (skip): {len(empty)}")


def prepare(names, limit, sample, subjects=None, fields=None):
    """fields (--retag sex,age,...): tagged clips missing those fields; the tagger writes only them (rows 'fields')."""
    if fields:
        fill_no_animal(names)
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "sheets").mkdir(exist_ok=True)
    todo, long_ = [], 0
    # resume-safe: a clip already waiting in a batch file (prepare stopped, batch not applied yet) is never batched twice
    # (retag: only retag rows count; old full-tag batch files stay on disk after apply)
    queued = {r["id"] for p in WORK.glob("batch_*.json") if "result" not in p.stem
              for r in json.loads(p.read_text(encoding="utf-8")) if bool(r.get("fields")) == bool(fields)}
    for name in names:
        root = ROOTS[name][0]
        if not index_of(root).exists():
            continue
        idx = load(root)
        items = sorted((needs_retag(idx, fields) if fields else untagged(idx)).items(), key=lambda kv: kv[1]["path"])
        long_ += sum(c["duration"] > LONG for _, c in items)
        items = [(k, c) for k, c in items if c["duration"] <= LONG and k not in queued]
        # tag by species (user 2026-10-20: cheap, only what a film needs): one group per folder species
        groups = [[kv for kv in items if kv[1].get("subject") == s] for s in subjects] if subjects else [items]
        for g in groups:
            if sample:   # spread over the folder (sorted by path): every k-th clip
                g = g[::max(1, len(g) // sample)][:sample]
            todo += [(name, k, c) for k, c in g]
    todo = todo[:limit] if limit else todo
    nums = [int(p.stem.split("_")[1]) for p in WORK.glob("batch_*.json") if "result" not in p.stem]
    n0, made, failed = max(nums, default=0) + 1, [], []
    for b in range(0, len(todo), BATCH):
        rows = []
        for name, k, c in todo[b:b + BATCH]:
            dst = WORK / "sheets" / f"{k}.jpg"
            if dst.exists() or sheet(ROOTS[name][0] / c["path"], c["duration"], dst):
                rows.append({"id": k, "root": name, "source": ROOTS[name][2], "image": str(dst), "folder": c.get("subject"),
                             "folder_action": c.get("action"), "title_hint": c.get("title_hint"),
                             "duration": c["duration"]})
                if fields:  # retag: only these keys; the old caption is context, the image decides
                    rows[-1].update(fields=list(fields), old_caption=c["tags"].get("caption"))
            else:
                failed.append(c["path"])
        if rows:
            bp = WORK / f"batch_{n0 + len(made):02d}.json"
            bp.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
            made.append(bp.stem)
    print(f"{len(todo) - len(failed)} clips in {len(made)} batches: {', '.join(made)}"
          + (f" | {long_} files > {LONG:.0f} s skipped (films, not clips)" if long_ else ""))
    for f in failed:
        print("FAILED sheet:", f)


def clean(t):
    """Keep only vocabulary values; return (tags, dropped values)."""
    out, bad = {}, []
    for k, allowed in VOCAB.items():
        v = t.get(k)
        if k in LISTS:
            v = [v] if isinstance(v, str) else v   # a single value instead of a list
            v = [x for x in (v or []) if x in allowed or bad.append(f"{k}={x}")]
        elif isinstance(v, list) or v not in allowed:
            if v is not None:
                bad.append(f"{k}={v}")
            v = None
        out[k] = v
    sp = t.get("species") or []
    out["species"] = sorted({s.strip().lower() for s in ([sp] if isinstance(sp, str) else sp) if s.strip()})
    out["good"] = sorted({int(g) for g in t.get("good") or [] if str(g) in "1234"})
    out["caption"] = (t.get("caption") or "").strip()
    out["sure"] = bool(t.get("sure"))
    ph = t.get("phase")  # action of the main subject in frames 1-4 (plan.py puts the in-point where the asked one is)
    out["phase"] = [x if x in VOCAB["action"] else None for x in ph] if isinstance(ph, list) and len(ph) == 4 else None
    if ph is not None and out["phase"] is None:
        bad.append(f"phase={ph}")
    return out, bad


def best_range(good, dur):
    """Longest run of consecutive good frames -> in/out seconds (half way to the neighbouring frames)."""
    if not good:
        return None
    runs, cur = [], [good[0]]
    for g in good[1:]:
        cur = cur + [g] if g == cur[-1] + 1 else (runs.append(cur) or [g])
    run = max(runs + [cur], key=len)
    edge = [0.03] + [(POS[i] + POS[i + 1]) / 2 for i in range(3)] + [0.97]
    return [round(edge[run[0] - 1] * dur, 2), round(edge[run[-1]] * dur, 2)]


def apply(batch):
    rows = json.loads((WORK / f"{batch}.json").read_text(encoding="utf-8"))
    res = json.loads((WORK / f"{batch}_result.json").read_text(encoding="utf-8"))
    by_root, missing, dropped = {}, [], []
    for r in rows:
        t = res.get(r["id"])
        if r.get("fields"):  # retag row: merge only its fields into the clip's tags (in the write loop below)
            if not t or not any(k in t for k in r["fields"]):
                missing.append(r["id"])
                continue
            tags, bad = clean(t)
            by_root.setdefault(r["root"], []).append((r["id"], {k: tags[k] for k in r["fields"] if k in t}))
            dropped += [f"{r['id'][:6]}:{b}" for b in bad if b.split("=")[0] in r["fields"]]
            continue
        if not t or not t.get("caption"):
            missing.append(r["id"])
            continue
        tags, bad = clean(t)
        tags["rt"] = list(RETAG)  # the current tagger gives every new field
        if ROOTS[r["root"]][2] == "real" and "morph" in tags["issues"]:   # camera footage cannot morph
            tags["issues"].remove("morph")
            tags["good"] = tags["good"] or [1, 2, 3, 4]
        # the user's folder is the truth for the main animal; a different vision guess is kept for review
        fs = folder_species(r.get("folder"))
        if fs and fs not in tags["species"]:  # always searchable by the folder name ("lioness" alone missed sp=lion)
            if not any(fs in sp or sp in fs for sp in tags["species"]):
                tags["vision_species"] = tags["species"]
            tags["species"] = [fs] + tags["species"]
        tags["best"] = best_range(tags["good"], r["duration"])
        tags["v"] = V
        by_root.setdefault(r["root"], []).append((r["id"], tags))
        dropped += [f"{r['id'][:6]}:{b}" for b in bad]
    done = []
    for name, items in by_root.items():
        root, kind, _ = ROOTS[name]
        idx = load(root)
        for k, tags in items:
            if k not in idx["clips"]:
                continue
            if "v" not in tags:  # retag fields: merged, rt grows; YOLO already measured this clip
                old = idx["clips"][k].get("tags") or {}
                idx["clips"][k]["tags"] = {**old, **tags, "rt": sorted(set(old.get("rt") or []) | set(tags))}
                continue
            idx["clips"][k]["tags"] = tags
            done.append({"id": k, "abs": str(root / idx["clips"][k]["path"]), "tags": tags})
        save(root, kind, idx)
    print(f"{batch}: applied {sum(len(v) for v in by_root.values())}/{len(rows)}"
          + (f" | MISSING {len(missing)}: {', '.join(m[:8] for m in missing)}" if missing else "")
          + (f" | dropped off-vocab: {', '.join(dropped[:12])}" if dropped else ""))
    return done


def measure(clips):
    """YOLO-World subject window + shot size for the clips just tagged (local GPU, cached by content hash, so a
    later organize move/rename keeps it); /doc-edit plan then never waits on them. The old backlog is not touched."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "doc-edit" / "scripts"))
    try:
        import yolo
    except ImportError as e:
        print(f"yolo: skipped ({e})")
        return
    new, sec = yolo.measure(clips)
    print(f"yolo: {new} new clips measured ({sec}s) -> {yolo.CACHE}")


def review(batches):
    lines = ["| clip | caption | species | action | sex/age/outcome | phase | size/angle | light | setting | issues | best |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for b in batches:
        for r in json.loads((WORK / f"{b}.json").read_text(encoding="utf-8")):
            c = load(ROOTS[r["root"]][0])["clips"].get(r["id"], {})
            t = c.get("tags") or {}
            lines.append(f"| {r['root']}:{c.get('path')} | {t.get('caption')} | {', '.join(t.get('species') or [])} | "
                         f"{', '.join(t.get('action') or [])} | {t.get('sex')}/{t.get('age')}/{t.get('outcome')} | "
                         f"{' '.join(map(str, t.get('phase') or []))} | {t.get('shot_size')}/{t.get('angle')} | {t.get('light')} | "
                         f"{', '.join(t.get('setting') or [])} | {', '.join(t.get('issues') or [])}"
                         + (f" ⚠ vision: {', '.join(t['vision_species'])}" if t.get('vision_species') else '') + f" | {t.get('best')} |")
    out = WORK / "review.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(lines) - 2} rows -> {out}")


def status():
    for name, (root, kind, _) in ROOTS.items():
        if kind == "video" and index_of(root).exists():
            idx = load(root)
            print(f"{name}: {len(idx['clips']) - len(untagged(idx))}/{len(idx['clips'])} tagged v{V}")


if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0] if a else "status"
    opt = lambda f: int(a[a.index(f) + 1]) if f in a else 0  # noqa: E731
    if cmd == "prepare":
        names = [x for x in a[1:] if x in ROOTS and ROOTS[x][1] == "video"] or [n for n, r in ROOTS.items() if r[1] == "video"]
        subj = a[a.index("--subject") + 1].lower().replace("_", " ").split(",") if "--subject" in a else None
        fields = a[a.index("--retag") + 1].split(",") if "--retag" in a else None
        assert not fields or set(fields) <= set(RETAG), f"--retag fields: {','.join(RETAG)}"
        prepare(names, opt("--limit"), opt("--sample"), subj, fields)
    elif cmd == "apply":   # --no-yolo: tags only
        done = [c for b in a[1:] if not b.startswith("--") for c in apply(b)]
        if done and "--no-yolo" not in a:
            measure(done)
    elif cmd == "no-animal":   # story fields of scenery clips without vision; drops their rows from untagged batches
        fill_no_animal([n for n, r in ROOTS.items() if r[1] == "video"])
    elif cmd == "review":
        review(a[1:])
    else:
        status()
    assert clean({"action": "perch", "species": "toucan"})[0]["action"] == ["perch"]
    t_, b_ = clean({"sex": "female", "age": "calf", "outcome": "miss", "phase": ["hide", "hide", "chase", "x"]})
    assert (t_["sex"], t_["age"], t_["outcome"], t_["phase"]) == ("female", None, "miss", ["hide", "hide", "chase", None])
    assert b_ == ["age=calf"] and clean({"phase": ["run"]})[1] == ["phase=['run']"]
    ix = {"clips": {"a": {"tags": {"v": V}}, "b": {"tags": {"v": V, "rt": list(RETAG)}}, "c": {"tags": {}}}}
    assert list(needs_retag(ix, ["sex"])) == ["a"]
    assert no_animal({"tags": {"species": ["none"]}}) and not no_animal({"tags": {"species": ["lion"]}})
    assert folder_species("Eagle") == "eagle" and folder_species("frogs") == "frog" and folder_species("birds") is None
    assert folder_species("_check") is None
    assert best_range([2, 3], 10.0) == [2.75, 7.75] and best_range([1, 3, 4], 10.0) == [5.25, 9.7]
