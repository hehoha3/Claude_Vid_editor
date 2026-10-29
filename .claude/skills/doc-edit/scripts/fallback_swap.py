"""/doc-edit fallback-species (user 2026-10-29): swap the FALLBACK V1 shots (scenery / other species) of a range for a
clip of the slot's own species (or its family when the library has none), action and setting ignored. Item ranges
unchanged; shots the user changed by hand (file or source-in differs from plan.json) are left alone; the last intro
shot / first story-1 shot keep their black fades. Swapped items Teal, reused frames zoom 1.15, AI clips get A1 at -12 dB.

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/fallback_swap.py <video> [--range=00:00-08:00]           # dry run
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/fallback_swap.py <video> [--range=...] --apply   # backup Edit_bak_fbspecies_<stamp>, swap
"""
import datetime as dt, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / ".claude/skills/doc-edit/scripts")]
sys.stdout.reconfigure(encoding="utf-8")
import place, plan  # noqa: E402
from dvr_cowork.config import load_config  # noqa: E402
from dvr_cowork.resolve_conn import connect  # noqa: E402
from dvr_cowork.resolve_ops import (_norm, backup_timeline, clip_fps, find_bin, find_timeline, get_project,  # noqa: E402
                                    pool_root, use_channel)

VIDEO = sys.argv[1]
_r = next((a[8:] for a in sys.argv if a.startswith("--range=")), "00:00-08:00").split("-")
T0, T1 = (int(x.split(":")[0]) * 60 + float(x.split(":")[1]) for x in _r)
FAMILY ={"zebra": {"zebra", "horse", "donkey"}, "elephant": {"elephant"}, "baboon": {"baboon", "monkey", "vervet monkey"},
          "wildebeest": {"wildebeest", "hartebeest", "topi", "blesbok", "buffalo", "cape buffalo", "eland", "kudu", "oryx",
                         "gemsbok", "impala", "springbok", "gazelle", "thomson's gazelle", "waterbuck", "lechwe", "antelope"}}
BAN = re.compile(r"\b(vehicles?|cars?|road|safari (jeep|truck)|jeep|zoo|enclosure|tourists?|people|person|human|man|woman|"
                 r"carcass|kill|dead)\b", re.I)
REUSE_GAP, REUSE_MAX = 30.0, 6
plan.SAME_GAP = 60.0
COLOR = "Teal"


def main(apply):
    p = json.loads((ROOT / ".work/doc_edit" / VIDEO / "plan.json").read_text("utf-8"))
    use_channel(p["video_dir"])
    slots = [s for s in p["slots"] if s["status"] == "FALLBACK" and T0 - 0.1 <= s["start"] < T1]
    edge = (p["intro"] - 2.1, p["intro"] + 0.7) if p.get("intro") else (-1, -1)  # last intro / first story-1 shot: fades
    pt = ROOT / ".work/doc_edit" / VIDEO / "project.txt"
    want = pt.read_text("utf-8").split("/")[0].strip() if pt.exists() else VIDEO
    clips = plan.load_clips(p["region"])
    pool = [c for c in clips if c["tags"].get("species") and not c["tags"].get("issues") and not c.get("hold")
            and not BAN.search(c["tags"].get("caption", ""))]
    resolve = connect(load_config())
    pm, project = get_project(resolve)
    tl = find_timeline(project, "Edit")
    assert tl and tl.GetName().lower() != "master" and project.GetName() == want, f"open project {want}"
    mp = project.GetMediaPool()
    root = pool_root(mp)
    obin = set(place.bin_index(find_bin(root, plan.OPEN_BIN)))
    st, fps = int(tl.GetStartFrame()), 24.0
    rows, uses = [], {}
    for ti in tl.GetItemListInTrack("video", 1) or []:
        mpi = ti.GetMediaPoolItem()
        path = _norm(mpi.GetClipProperty("File Path")) if mpi else ""
        a, b = (int(ti.GetStart()) - st) / fps, (int(ti.GetEnd()) - st) / fps
        sin = int(ti.GetLeftOffset()) / clip_fps(mpi, fps) if mpi else 0
        rows.append((ti, path, a, b))
        uses.setdefault(path, []).append([a, sin, sin + (b - a), ti])
    todo, hand = [], []
    for ti, path, a, b in rows:
        if a >= T1 - 0.05 or a < max(T0, 0.05) - 0.05 or edge[0] <= a <= edge[1]:
            continue
        s = next((x for x in slots if abs(x["start"] - a) < 0.1), None)
        if not s:
            continue
        sin = int(ti.GetLeftOffset()) / clip_fps(ti.GetMediaPoolItem(), fps)
        if path != _norm(s["path"]) or abs(sin - s["src_in"]) > 0.5:
            hand.append(a)  # the user changed this shot in Resolve: left alone
            continue
        todo.append((ti, path, a, b, dict(s, start=a, dur=b - a)))
    print(f"{len(slots)} FALLBACK slots in the plan {_r[0]}-{_r[1]}, {len(todo)} found on V1 untouched by the user; {len(hand)} changed by hand, left alone: "
          + " ".join(f"{int(x // 60):02d}:{x % 60:04.1f}" for x in hand))

    picks = []
    for ti, path, a, b, s in todo:
        sp = s["filter"]["sp"][0]
        fam = FAMILY.get(sp, {sp})
        best = None
        for c in pool:
            cs = set(c["tags"]["species"])
            tier = 1.0 if sp in cs else 0.5 if cs & fam else 0
            if not tier or (c.get("duration") or 0) < s["dur"] + 0.5 or _norm(c["abs"]) == path:
                continue
            u = [(x[0], x[1], x[2]) for x in uses.get(_norm(c["abs"]), []) if x[3] is not ti]
            sin = plan.window(c, s, u, REUSE_GAP, REUSE_MAX)
            if sin is None:
                continue
            sc = tier + 0.3 * (plan.fit(c, s["filter"], None) or 0) - 0.08 * len(u) - 0.3 * len(cs - fam - {sp}) \
                + (0.1 if _norm(c["abs"]) in obin else 0) + (0.03 if c["source"] == "real" else 0)
            if best is None or sc > best[0]:
                best = (sc, c, sin, len(u), tier)
        tc = f"{int(a // 60):02d}:{a % 60:05.2f}"
        if not best:
            print(f"{tc} l{s['line']} KEEP {Path(path).stem[:40]}: no {sp} clip fits {s['dur']:.1f}s")
            continue
        sc, c, sin, n, tier = best
        uses.setdefault(_norm(c["abs"]), []).append([a, sin, sin + s["dur"], None])
        uses[path] = [x for x in uses.get(path, []) if x[3] is not ti]
        picks.append((ti, path, a, b, c, sin, n))
        print(f"{tc} l{s['line']} [{sp}] {Path(path).stem[:34]} -> {Path(c['abs']).stem[:44]}"
              f"{' (family)' if tier < 1 else ''} [{','.join(c['tags'].get('action') or [])}]{' reuse' if n else ''}")
    print(f"swaps {len(picks)}/{len(todo)}")
    if not apply:
        print("dry run: nothing changed (--apply to swap)")
        return

    orig = project.GetCurrentTimeline()
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    assert backup_timeline(project, tl, f"Edit_bak_fbspecies_{stamp}"), "backup failed, nothing changed"
    project.SetCurrentTimeline(tl)
    print(f"backup: Edit_bak_fbspecies_{stamp}")
    have = place.bin_index(root)
    done = fail = a1_n = 0
    for ti, path, a, b, c, sin, n in picks:
        ra, rb = int(ti.GetStart()), int(ti.GetEnd())
        it = have.get(_norm(c["abs"]))
        if not it:
            mp.SetCurrentFolder(place.ensure_bin(mp, place.video_bin({"path": c["abs"], "source": c["source"]})))
            got = mp.ImportMedia([c["abs"]]) or []
            it = have[_norm(c["abs"])] = got[0] if got else None
        if not it:
            print(f"FAILED import {c['abs']}"); fail += 1; continue
        old_a1 = [x for x in tl.GetItemListInTrack("audio", 1) or [] if int(x.GetStart()) >= ra and int(x.GetEnd()) <= rb]
        tl.DeleteClips([ti] + old_a1, False)
        new = put(mp, tl, it, 1, ra, rb - ra, sin, fps)
        if not new:
            print(f"FAILED place {Path(c['abs']).name} at {a:.2f}s (slot now empty, backup has the old shot)"); fail += 1; continue
        new.SetClipColor(COLOR)
        if n:
            new.SetProperty("ZoomX", 1.15) and new.SetProperty("ZoomY", 1.15)
        if c["source"] == "ai":
            au = put(mp, tl, it, 2, ra, rb - ra, sin, fps)
            a1_n += bool(au and au.SetProperty("AudioVolume", place.A1_DB))
        done += 1
    if orig:
        project.SetCurrentTimeline(orig)
    pm.SaveProject()
    print(f"swapped {done}, failed {fail}, A1 AI audio {a1_n} at {place.A1_DB} dB, color {COLOR}")




def put(mp, tl, it, media, rec, n, sin, fps):
    """n timeline frames at rec (absolute) from source second sin; conformed fps measured and corrected (as place.put)."""
    cf = clip_fps(it, fps)
    a, k = round(sin * cf), round(n * cf / fps)
    for _ in range(3):
        res = mp.AppendToTimeline([{"mediaPoolItem": it, "startFrame": a, "endFrame": a + k, "mediaType": media,
                                    "trackIndex": 1, "recordFrame": rec}])
        ti = res[0] if res else None
        if not ti:
            return None
        d = int(ti.GetEnd()) - int(ti.GetStart())
        if d == n:
            return ti
        tl.DeleteClips([ti], False)
        k += round((n - d) * cf / fps) or (1 if n > d else -1)
    return None


if __name__ == "__main__":
    main("--apply" in sys.argv)
