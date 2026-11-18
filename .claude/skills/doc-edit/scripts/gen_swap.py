"""/doc-edit after-gen-vid step (user 2026-11-08): every clip generated for this video goes onto V1 at the slot it was
made for. After plan.py --sub-broad + place.py --fill (empty slots filled), a generated slot (plan.json `gen`) still
covered by another clip gets the generated one: the V1 items inside the slot range go, the clip goes in frame-exact
(same record range), clip color Orange, doc_edit markers of that range go (a _check clip gets a yellow note).

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/gen_swap.py <video>            # dry run
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/gen_swap.py <video> --apply    # backup <timeline>_bak_gen_<stamp>
"""
import datetime as dt, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / ".claude/skills/doc-edit/scripts")]
sys.stdout.reconfigure(encoding="utf-8")
import place  # noqa: E402
from fallback_swap import put  # noqa: E402
from dvr_cowork.config import load_config  # noqa: E402
from dvr_cowork.resolve_conn import connect  # noqa: E402
from dvr_cowork.resolve_ops import _norm, backup_timeline, clip_fps, get_project, pool_root, use_channel, video_timeline  # noqa: E402
from dvr_cowork.videokey import video_key  # noqa: E402

COLOR, FPS, TOL = "Orange", 24.0, 0.07


def todo(slots, items):
    """(slot, [V1 items inside it]) for each generated slot whose range holds another file. items: (item, path, a, b)."""
    out = []
    for s in (x for x in slots if x.get("gen")):
        a, b = s["start"], s["start"] + s["dur"]
        over = [x for x in items if min(x[3], b) - max(x[2], a) > TOL]  # rounding: neighbours share ~1 frame
        inside = [x for x in over if x[2] > a - TOL and x[3] < b + TOL]
        if inside and len(inside) == len(over) and any(p != _norm(s["path"]) for _, p, _, _ in inside):
            out.append((s, inside))  # an item running over the slot edge = hand cut: left alone
    return out


def close_gaps(tl, mp, st):
    """Khe 1-3 frame giữa hai item V1 (clip gen ngắn hơn slot 1 frame): thêm vào frame cuối của shot trước, đúng khe đó.
    Không đụng item nào khác, không ripple. -> (closed, [mô tả lỗi])."""
    its = sorted(tl.GetItemListInTrack("video", 1) or [], key=lambda t: int(t.GetStart()))
    closed, bad = 0, []
    for a, b in zip(its, its[1:]):
        gap = int(b.GetStart()) - int(a.GetEnd())
        if not 0 < gap <= 3 or int(a.GetStart()) - st < 1:
            continue
        mpi = a.GetMediaPoolItem()
        cf = clip_fps(mpi, FPS) if mpi else 0
        if not cf or not put(mp, tl, mpi, 1, int(a.GetEnd()), gap, (int(a.GetSourceEndFrame()) - round(gap * cf / FPS)) / cf, FPS):
            bad.append(f"{(int(a.GetEnd()) - st) / FPS:.2f}s")
        else:
            closed += 1
    return closed, bad


def main(video, apply):
    p = json.loads((ROOT / ".work/doc_edit" / video_key(video) / "plan.json").read_text("utf-8"))
    use_channel(p["video_dir"])
    pm, project = get_project(connect(load_config()))
    tl = video_timeline(project)
    assert tl, "the video's timeline channN_vidK is not in the open project"
    st = int(tl.GetStartFrame())
    items = []
    for ti in tl.GetItemListInTrack("video", 1) or []:
        mpi = ti.GetMediaPoolItem()
        items.append((ti, _norm(mpi.GetClipProperty("File Path")) if mpi else "",
                      (int(ti.GetStart()) - st) / FPS, (int(ti.GetEnd()) - st) / FPS))
    gen = [s for s in p["slots"] if s.get("gen")]
    work = todo(p["slots"], items)
    on = sum(any(x[1] == _norm(s["path"]) for x in items) for s in gen)
    print(f"generated slots {len(gen)}: on V1 already {on}, to swap {len(work)}")
    if "--close" in sys.argv:  # only close the 1-3 frame gaps (backup first)
        assert backup_timeline(project, tl, f"{tl.GetName()}_bak_gapclose_{dt.datetime.now():%Y%m%d_%H%M%S}"), "backup failed"
        c, bad = close_gaps(tl, project.GetMediaPool(), st)
        pm.SaveProject()
        print(f"gaps of 1-3 frames closed {c}" + (f", FAILED {bad}" if bad else ""))
        return
    if not apply or not work:
        print("dry run: nothing changed (--apply to swap)" if work else "nothing to swap")
        return
    orig = project.GetCurrentTimeline()
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    assert backup_timeline(project, tl, f"{tl.GetName()}_bak_gen_{stamp}"), "backup failed, nothing changed"
    project.SetCurrentTimeline(tl)
    print(f"backup: {tl.GetName()}_bak_gen_{stamp}")
    mp = project.GetMediaPool()
    have = place.bin_index(pool_root(mp))
    marks = tl.GetMarkers() or {}
    done, fail = 0, []
    for s, inside in work:
        it = have.get(_norm(s["path"]))
        if not it:
            mp.SetCurrentFolder(place.ensure_bin(mp, place.video_bin(s)))
            got = mp.ImportMedia([s["path"]]) or []
            it = have[_norm(s["path"])] = got[0] if got else None
        if not it:
            fail.append(f"import {Path(s['path']).name}"); continue
        # the removed items' own record range (frame-exact with the neighbours); the clip is cut to the slot, so a
        # range 1 frame longer than the file keeps a 1-frame gap instead of failing
        ra, rb = min(int(x[0].GetStart()) for x in inside), max(int(x[0].GetEnd()) for x in inside)
        clip_len = 2 * s["src_in"] + s["dur"]  # plan.py centred the slot in the clip
        n = min(rb - ra, int(clip_len * FPS + 1e-6))
        old_a1 = [x for x in tl.GetItemListInTrack("audio", 1) or [] if int(x.GetStart()) >= ra and int(x.GetEnd()) <= rb]
        tl.DeleteClips([x[0] for x in inside] + old_a1, False)  # the old shot's A1 audio goes too; place --a1-only re-adds
        new = put(mp, tl, it, 1, ra, n, max(0.0, min(s["src_in"], clip_len - n / FPS)), FPS)
        if not new:
            fail.append(f"place {Path(s['path']).name} at {s['start']:.1f}s (empty now, backup has the old shot)"); continue
        new.SetClipColor(COLOR)
        for fr, m in marks.items():
            if str(m.get("customData", "")).startswith("doc_edit") and ra - st <= fr < rb - st:
                tl.DeleteMarkerAtFrame(fr)
        if s["status"] == "WEAK":
            tl.AddMarker(ra - st, "Yellow", "WEAK", f"generated {s.get('why', '')}"[:200], rb - ra, "doc_edit gen")
        done += 1
    if orig:
        project.SetCurrentTimeline(orig)
    c, bad = close_gaps(tl, mp, st)
    pm.SaveProject()
    print(f"gaps of 1-3 frames closed {c}" + (f", FAILED {bad}" if bad else ""))
    print(f"swapped {done}/{len(work)}, color {COLOR}" + (f"; FAILED {len(fail)}: " + "; ".join(fail) if fail else ""))
    print(place.black_fades(video))  # a swapped shot comes in without its fade


def selftest():
    s = [{"start": 10.0, "dur": 2.0, "gen": True, "path": "g.mp4"}, {"start": 20.0, "dur": 2.0, "gen": True, "path": "h.mp4"},
         {"start": 30.0, "dur": 2.0, "gen": True, "path": "k.mp4"}]
    it = [(i, _norm(f), a, b) for i, f, a, b in
          [(1, "x.mp4", 10.0, 12.0), (2, "h.mp4", 20.0, 22.0), (3, "y.mp4", 29.0, 31.0), (4, "z.mp4", 31.0, 32.0)]]
    w = todo(s, it)
    assert [x[0]["path"] for x in w] == ["g.mp4"], w  # h already there; k covered by a hand cut across its edge
    print("selftest ok")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main(sys.argv[1], "--apply" in sys.argv)
