#!/usr/bin/env python3
"""Content tags for every clip of the scan-source video indexes (one vision pass per clip, kept by hash).

    tag_source.py status                         tagged / untagged per root
    tag_source.py prepare [video|ai] [--limit N] [--sample N]
                                                 contact sheets + batch files of 20 for the Sonnet taggers
    tag_source.py apply <batch_NN>... [--no-yolo] validate the tagger's result file, merge into _library.json,
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
VOCAB = {
    "count": {"none", "one", "two", "few", "many"},
    "action": {"rest", "sleep", "look", "walk", "run", "stalk", "hunt", "attack", "eat", "feed", "drink", "swim", "fly",
               "perch", "climb", "hang", "jump", "fight", "groom", "play", "call", "carry_young", "none"},
    "shot_size": {"extreme_close", "close_up", "medium", "wide", "aerial"},
    "angle": {"eye", "low", "high", "top_down"},
    "camera": {"static", "moving"},
    "light": {"day", "golden", "dusk", "night", "moon"},
    "setting": {"canopy", "forest", "forest_floor", "undergrowth", "river", "riverbank", "lake", "swamp",
                "waterfall", "underwater", "grassland", "rock", "cave", "sky", "moon", "mountain", "village"},
    "weather": {"clear", "mist", "rain", "storm", "none"},
    "mood": {"calm", "tense", "dramatic", "playful", "majestic", "eerie"},
    "direction": {"left", "right", "toward", "away", "none"},
    "issues": {"logo", "text", "morph", "unnatural", "blur", "dark", "watermark", "frame_cut"},
}
LISTS = {"action", "setting", "issues", "good"}
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


def sheet(src, dur, dst):
    ins = sum((["-ss", f"{dur * t:.2f}", "-i", str(src)] for t in POS), [])
    fc = "".join(f"[{i}:v]scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:-1:-1,"
                 f"drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text={i + 1}:x=8:y=6:fontsize=30:"
                 f"fontcolor=yellow:box=1:boxcolor=black@0.7:boxborderw=6[f{i}];" for i in range(4))
    fc += "[f0][f1][f2][f3]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0[v]"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", fc, "-map", "[v]",
                        "-frames:v", "1", "-q:v", "4", str(dst)], capture_output=True, text=True)
    return r.returncode == 0 and dst.exists()


def prepare(names, limit, sample):
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "sheets").mkdir(exist_ok=True)
    todo = []
    for name in names:
        root = ROOTS[name][0]
        items = sorted(untagged(load(root)).items(), key=lambda kv: kv[1]["path"])
        if sample:   # spread over subjects: every k-th clip
            items = items[::max(1, len(items) // sample)][:sample]
        todo += [(name, k, c) for k, c in items]
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
            else:
                failed.append(c["path"])
        if rows:
            bp = WORK / f"batch_{n0 + len(made):02d}.json"
            bp.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
            made.append(bp.stem)
    print(f"{len(todo) - len(failed)} clips in {len(made)} batches: {', '.join(made)}")
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
        elif v not in allowed:
            if v is not None:
                bad.append(f"{k}={v}")
            v = None
        out[k] = v
    sp = t.get("species") or []
    out["species"] = sorted({s.strip().lower() for s in ([sp] if isinstance(sp, str) else sp) if s.strip()})
    out["good"] = sorted({int(g) for g in t.get("good") or [] if str(g) in "1234"})
    out["caption"] = (t.get("caption") or "").strip()
    out["sure"] = bool(t.get("sure"))
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
        if not t or not t.get("caption"):
            missing.append(r["id"])
            continue
        tags, bad = clean(t)
        if ROOTS[r["root"]][2] == "real" and "morph" in tags["issues"]:   # camera footage cannot morph
            tags["issues"].remove("morph")
            tags["good"] = tags["good"] or [1, 2, 3, 4]
        # the user's folder is the truth for the main animal; a different vision guess is kept for review
        fs = folder_species(r.get("folder"))
        if fs and not any(fs in sp or sp in fs for sp in tags["species"]):
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
            if k in idx["clips"]:
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
    lines = ["| clip | caption | species | action | size/angle | light | setting | issues | best |",
             "|---|---|---|---|---|---|---|---|---|"]
    for b in batches:
        for r in json.loads((WORK / f"{b}.json").read_text(encoding="utf-8")):
            c = load(ROOTS[r["root"]][0])["clips"].get(r["id"], {})
            t = c.get("tags") or {}
            lines.append(f"| {r['root']}:{c.get('path')} | {t.get('caption')} | {', '.join(t.get('species') or [])} | "
                         f"{', '.join(t.get('action') or [])} | {t.get('shot_size')}/{t.get('angle')} | {t.get('light')} | "
                         f"{', '.join(t.get('setting') or [])} | {', '.join(t.get('issues') or [])}"
                         + (f" ⚠ vision: {', '.join(t['vision_species'])}" if t.get('vision_species') else '') + f" | {t.get('best')} |")
    out = WORK / "review.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(lines) - 2} rows -> {out}")


def status():
    for name, (root, kind, _) in ROOTS.items():
        if kind == "video":
            idx = load(root)
            print(f"{name}: {len(idx['clips']) - len(untagged(idx))}/{len(idx['clips'])} tagged v{V}")


if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0] if a else "status"
    opt = lambda f: int(a[a.index(f) + 1]) if f in a else 0  # noqa: E731
    if cmd == "prepare":
        names = [x for x in a[1:] if x in ROOTS and ROOTS[x][1] == "video"] or ["video", "ai"]
        prepare(names, opt("--limit"), opt("--sample"))
    elif cmd == "apply":   # --no-yolo: tags only
        done = [c for b in a[1:] if not b.startswith("--") for c in apply(b)]
        if done and "--no-yolo" not in a:
            measure(done)
    elif cmd == "review":
        review(a[1:])
    else:
        status()
    assert clean({"action": "perch", "species": "toucan"})[0]["action"] == ["perch"]
    assert folder_species("Eagle") == "eagle" and folder_species("frogs") == "frog" and folder_species("birds") is None
    assert folder_species("_check") is None
    assert best_range([2, 3], 10.0) == [2.75, 7.75] and best_range([1, 3, 4], 10.0) == [5.25, 9.7]
