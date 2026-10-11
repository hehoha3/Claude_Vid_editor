"""audio-expert plan: cues.txt -> placement_plan.json + placement_report.md + mix_notes.md (read-only on Resolve).

    .venv/Scripts/python.exe .claude/skills/audio-expert/scripts/plan.py <video> [--run RUN_ID]
    .venv/Scripts/python.exe .claude/skills/audio-expert/scripts/plan.py --selftest

<video> = .work/audio_expert/<video>/cues.txt. Cue format is documented at the top of that file. Timing is
converted to timeline-relative frames (end exclusive) with the real fps; the Resolve timeline is only READ (snapshot
of A2 + existing audio, used for narrator overlap and conflicts). Output: .work/audio_expert/<video>/runs/<run_id>/.
"""
import datetime as dt, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
import index as ix  # noqa: E402

PROTECTED = (3, 4)  # tracks never written (ambience beds placed by doc-edit)


def tc(sec):
    m, s = divmod(sec, 60)
    return f"{int(m)}:{s:04.1f}"


def secs(t):
    m, s = t.split(":")
    return int(m) * 60 + float(s)


def parse(text):
    rows = []
    for n, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = [x.strip() for x in line.split("|")]
        assert len(p) == 6, f"cues.txt line {n}: need 6 columns, got {len(p)}"
        tr = int(p[0][1:])
        kv = dict(x.split("=") for x in p[1].split())
        rows.append({"line": n, "track": tr, "kv": kv, "frag": p[2], "seq": p[3], "purpose": p[4], "cls": p[5]})
    return rows


def resolve_asset(frag, index):
    f = frag.lower().replace("\\", "/")
    hit = [e for e in index if f in e["path"].lower().replace("\\", "/")]
    if len(hit) != 1:
        raise SystemExit(f'asset "{frag}": {len(hit)} matches {[e["path"] for e in hit[:5]]}')
    return hit[0]


def build(rows, index, fps, end_s, a2, prof):
    """-> placements (dict list), problems (str list)."""
    out, bad = [], []
    for r in rows:
        e = resolve_asset(r["frag"], index)
        dur, kv = e["duration_seconds"], r["kv"]
        src_in = float(kv.get("in", 0))
        if "peak" in kv:
            anchor = secs(kv["peak"])
            pk = prof(e)
            start = anchor - max(0.0, pk - src_in)
            src_in = src_in if start >= 0 else src_in + (-start)
            start = max(start, 0.0)
            ln = dur - src_in
        else:
            start = secs(kv["at"])
            ln = dur - src_in
        if "end" in kv:
            ln = min(ln, secs(kv["end"]) - start)
        if src_in + ln > dur + 1e-6 or ln <= 0:
            bad.append(f"line {r['line']} {r['frag']}: source {dur}s too short for in={src_in} len={ln}")
            continue
        if start + ln > end_s + 1e-6:
            bad.append(f"line {r['line']} {r['frag']}: ends {tc(start + ln)} after timeline end {tc(end_s)}")
            continue
        vof = lambda s: sum(max(0.0, min(s + ln, b) - max(s, a)) for a, b in a2) / ln  # noqa: E731
        shift = 0.0
        if r["cls"] == "flexible" and vof(start) > 0.2:  # flexible cue -> nearest narrator gap, -6..+3 s
            cand = [(round(vof(start + d), 2), abs(d), d) for d in (x / 5 for x in range(-30, 16))
                    if start + d >= 0 and start + d + ln <= end_s]
            best = min(cand)
            if best[0] < vof(start) - 0.1:
                shift = best[2]
                start += shift
        f0, f1 = round(start * fps), round((start + ln) * fps)
        vo = vof(start)
        out.append({
            "placement_id": f"{r['seq']}_L{r['line']:03d}", "sequence_id": r["seq"], "track_index": r["track"],
            "asset_id": e["asset_id"], "source_path": str(ix.AUDIO / e["path"]),
            "source_in_seconds": round(src_in, 3), "source_out_seconds": round(src_in + (f1 - f0) / fps, 3),
            "timeline_start_frame_relative": f0, "timeline_end_frame_relative_exclusive": f1,
            "start_tc": tc(f0 / fps), "end_tc": tc(f1 / fps), "timing_class": r["cls"], "purpose": r["purpose"],
            "vo_overlap": round(vo, 2), "shift_s": shift, "review_method": e["review_method"], "confidence": e["confidence"],
            "natural_end": src_in + ln >= dur - e.get("quiet_tail", 0) - 0.05, "status": "planned"})
    for tr in {p["track_index"] for p in out}:
        s = sorted((p for p in out if p["track_index"] == tr), key=lambda p: p["timeline_start_frame_relative"])
        for a, b in zip(s, s[1:]):
            if a["timeline_end_frame_relative_exclusive"] > b["timeline_start_frame_relative"]:
                bad.append(f'A{tr} overlap {a["placement_id"]} / {b["placement_id"]}')
    for p in out:
        if p["track_index"] in PROTECTED or p["track_index"] in (1, 2):
            bad.append(f'{p["placement_id"]}: A{p["track_index"]} is protected')
    return sorted(out, key=lambda p: (p["timeline_start_frame_relative"], p["track_index"])), bad


def snapshot(tl, fps):
    t0 = int(tl.GetStartFrame())
    snap = {"fps": fps, "start_frame": t0, "end_rel": int(tl.GetEndFrame()) - t0, "audio": {}, "video1": []}
    for n in range(1, int(tl.GetTrackCount("audio")) + 1):
        snap["audio"][n] = [[int(i.GetStart()) - t0, int(i.GetEnd()) - t0, i.GetName()]
                            for i in sorted(tl.GetItemListInTrack("audio", n) or [], key=lambda i: i.GetStart())]
    snap["video1"] = [[int(i.GetStart()) - t0, int(i.GetEnd()) - t0]
                      for i in sorted(tl.GetItemListInTrack("video", 1) or [], key=lambda i: i.GetStart())]
    return snap


def report(video, run, plan, bad, snap, music_s, end_s):
    L = [f"# Placement report - {video} ({run})", "",
         f"{len(plan)} placements planned | music coverage {music_s:.0f}s of {end_s:.0f}s ({music_s / end_s:.0%}) | "
         f"review_method: music = waveform_analysis (mood from filename), everything else filename_only. "
         "Nothing was listened to; confidence is capped at 0.5-0.6.", ""]
    if bad:
        L += ["## Unresolved"] + [f"- {b}" for b in bad] + [""]
    L += ["| id | track | start | end | class | VO overlap | shift | asset | purpose |", "|---|---|---|---|---|---|---|---|---|"]
    for p in plan:
        L.append(f"| {p['placement_id']} | A{p['track_index']} | {p['start_tc']} | {p['end_tc']} | {p['timing_class']} | "
                 f"{p['vo_overlap']:.0%} | {p['shift_s']:+.1f}s | {Path(p['source_path']).name} | {p['purpose']} |")
    return "\n".join(L) + "\n"


def mix_notes(plan, fps):
    N = ["# Mix notes (V1 does not mix; to do by ear in Fairlight)", "",
         "Starting levels and short edge fades come from doc-edit's tables; everything below needs a listen.", ""]
    for p in plan:
        i = f"{p['placement_id']} A{p['track_index']} {p['start_tc']}-{p['end_tc']}"
        if p["track_index"] == 7 and not p["natural_end"]:
            N.append(f"- {i}: music is cut before its natural end -> fade out over ~2-3 s ({p['purpose']}).")
        if p["track_index"] == 7:
            N.append(f"- {i}: music over narration ({p['vo_overlap']:.0%} of the clip) -> check it does not mask the voice.")
        if p["timing_class"] == "sync" and p["track_index"] in (6, 8, 9):
            N.append(f"- {i}: sync cue timed from the screenplay beat, not from the picture -> nudge to the frame.")
        if p["timing_class"] == "flexible" and p["vo_overlap"] > 0.5:
            N.append(f"- {i}: flexible cue sits under the narrator ({p['vo_overlap']:.0%}) -> lower level or move into a gap.")
    return "\n".join(N) + "\n"


def main(video, run):
    work = ROOT / ".work" / "audio_expert" / video
    rows = parse((work / "cues.txt").read_text("utf-8"))
    index = [json.loads(l) for l in ix.OUT.read_text("utf-8").splitlines() if l]
    from dvr_cowork.config import load_config
    from dvr_cowork.resolve_conn import connect
    from dvr_cowork.resolve_ops import find_timeline, get_project, timeline_fps
    cfg = load_config()
    resolve = connect(cfg)
    _, project = get_project(resolve)
    tl = find_timeline(project, cfg["resolve"]["timeline_name"])
    fps = timeline_fps(tl, project)
    rate = round(fps)
    snap = snapshot(tl, fps)
    end_s = snap["end_rel"] / rate
    a2 = [(a / rate, b / rate) for a, b, _ in snap["audio"].get(2, [])]
    cache = {}

    def prof(e):
        if e["asset_id"] not in cache:
            cache[e["asset_id"]] = (e.get("peak_s") if e.get("peak_s") is not None else
                                    ix.profile(ix.AUDIO / e["path"])["peak_s"])
        return cache[e["asset_id"]]

    plan, bad = build(rows, index, rate, end_s, a2, prof)
    for p in plan:  # media must exist
        if not Path(p["source_path"]).exists():
            bad.append(f'{p["placement_id"]}: media missing {p["source_path"]}')
    rd = work / "runs" / run
    rd.mkdir(parents=True, exist_ok=True)
    music_s = sum((p["timeline_end_frame_relative_exclusive"] - p["timeline_start_frame_relative"]) / rate
                  for p in plan if p["track_index"] == 7)
    (rd / "timeline_snapshot_before.json").write_text(json.dumps(snap), "utf-8")
    (rd / "placement_plan.json").write_text(json.dumps({"run_id": run, "fps": rate, "placements": plan}, indent=1), "utf-8")
    (rd / "placement_report.md").write_text(report(video, run, plan, bad, snap, music_s, end_s), "utf-8")
    (rd / "mix_notes.md").write_text(mix_notes(plan, rate), "utf-8")
    by = {}
    for p in plan:
        by[f"A{p['track_index']}"] = by.get(f"A{p['track_index']}", 0) + 1
    print(f"run {run}: {len(plan)} placements {by}; music {music_s:.0f}s/{end_s:.0f}s ({music_s / end_s:.0%}); "
          f"unresolved {len(bad)}")
    for b in bad:
        print("  !", b)
    print("->", rd.relative_to(ROOT))


def selftest():
    idx = [{"asset_id": "m", "path": "tense_music\\m.mp3", "duration_seconds": 60.0, "review_method": "waveform_analysis",
            "confidence": 0.5, "quiet_tail": 4.0},
           {"asset_id": "h", "path": "SXF\\HITS\\Hit.wav", "duration_seconds": 2.0, "review_method": "filename_only",
            "confidence": 0.4}]
    rows = parse("A7 | at=0:10.0 end=0:40.0 | m.mp3 | s1 | x | bed\nA8 | peak=0:30.0 | Hit.wav | s1 | y | sync\n"
                 "A7 | at=0:35.0 | m.mp3 | s1 | z | bed\nA6 | at=0:30.0 | Hit.wav | s1 | w | flexible")
    plan, bad = build(rows, idx, 24, 100.0, [(25.0, 45.0)], lambda e: 0.5)
    assert any("overlap" in b for b in bad)
    hit = next(p for p in plan if p["track_index"] == 8)
    assert hit["timeline_start_frame_relative"] == round(29.5 * 24) and hit["vo_overlap"] == 1.0
    m = next(p for p in plan if p["placement_id"] == "s1_L001")
    assert m["timeline_end_frame_relative_exclusive"] == 40 * 24 and not m["natural_end"]
    assert next(p for p in plan if p["track_index"] == 6)["shift_s"] == -6.0
    assert resolve_asset("hit", idx)["asset_id"] == "h"
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    run = sys.argv[sys.argv.index("--run") + 1] if "--run" in sys.argv else dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    if "--run" in sys.argv:
        a = [x for x in a if x != run]
    selftest() if "--selftest" in sys.argv else main(a[0], run)
