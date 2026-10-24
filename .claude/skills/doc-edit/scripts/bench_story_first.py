"""Before / after benchmark of doc-edit shot choice (story first, 2026-10-23) on one finished video's plan.json.

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/bench_story_first.py africa_1

Reads .work/doc_edit/<video>/plan.json (the old plan.py's picks) + spec.txt, re-runs today's match() + highlights()
on the same slots and the same library, writes .work/doc_edit/<video>/bench_story_first.md. Nothing else is written
(plan.json, plan.md, Resolve untouched)."""
import copy, json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.argv += ["--yolo-cached"]
sys.path.insert(0, str(ROOT / ".claude/skills/doc-edit/scripts"))
import plan  # noqa: E402

video = sys.argv[1]
work = ROOT / ".work" / "doc_edit" / video
old = json.loads((work / "plan.json").read_text("utf-8"))
if late := [s["start"] for s in old["slots"] if s.get("why") == "late substitute"]:  # old run used --late-sub / --sub-all
    plan.LATE_SUB, plan.LATE_SUB_T = True, min(late)
text = (work / "spec.txt").read_text("utf-8")
end, intro, _ = plan.parse_spec(text)
meta = plan.spec_meta(text, old["end"], intro)
clips = plan.load_clips(old["region"])
recent, _ = plan.ledger.banned(video, Path(old["video_dir"]))
pool = [c for c in clips if c["id"] not in recent]
by = {c["abs"]: c for c in pool} | {c["abs"]: c for c in clips}
plan.yolo_pass([c for c in pool if {x for s in old["slots"] for x in s["filter"].get("sp", [])} & set(c["tags"].get("species", []))])
if meta["look"] or any("look" in s["filter"] for s in old["slots"]):
    plan.ground_looks(clips)

# 1. audit: the old picks under today's truth rules (filters as the spec wrote them, + the story no=)
keep = ("slot", "line", "start", "dur", "need", "src", "filter", "audio", "intro", "vo", "chain", "fade_in", "fade_out")
fresh = [{k: copy.deepcopy(s[k]) for k in keep if k in s} for s in old["slots"]]
plan.story_rules(fresh, meta)
audit, unsure, intro_other, bad = Counter(), 0, [], []
for s, f in zip(old["slots"], fresh):
    c = by.get(s.get("path"))
    if not c:
        continue
    why, u = plan.hard(c, f["filter"])
    if why == "species" and s.get("why") == "late substitute":
        why = None  # another species on purpose (--late-sub, user-requested), not a truth break
    if why:
        audit[why] += 1
        if why in plan.TRUTH_WHY:
            bad.append(f"#{s['slot']} {plan.tc(s['start'])} {why}: {s['need'][:50]} <- {c['tags']['caption'][:70]}")
    unsure += bool(u)
    if s.get("why") == "intro highlight, other species":
        intro_other.append(f"#{s['slot']} {plan.tc(s['start'])} wanted {','.join(s['filter'].get('sp', []))}, "
                           f"got {', '.join(c['tags'].get('species', []))}: {c['tags']['caption'][:70]}")

# 2. re-run: same slots, same library, today's rules
print(plan.semantic(fresh, pool))
plan.match(fresh, pool, None, meta["look"])
plan.highlights(fresh, pool)
oc, nc = Counter(s["status"] for s in old["slots"]), Counter(s["status"] for s in fresh)
changed = [(a, b) for a, b in zip(old["slots"], fresh) if a.get("path") != b.get("path")] if len(fresh) == len(old["slots"]) else []
rej = sum((Counter(s.get("rej") or {}) for s in fresh), Counter())
n_intro = lambda ss, st: sum(s.get("intro") and s["status"] == st for s in ss)  # noqa: E731

md = [f"# Benchmark story first — {video}", "",
      f"Same spec ({len(old['slots'])} slots), same library ({len(pool)} clips after the ledger); old = plan.json "
      "from the earlier plan.py, new = today's match() + highlights() (no audio / vary step).", "",
      "| | OK | WEAK | FALLBACK | THIẾU | intro THIẾU |", "|---|---|---|---|---|---|",
      f"| old | {oc['OK']} | {oc['WEAK']} | {oc['FALLBACK']} | {oc['THIEU']} | {n_intro(old['slots'], 'THIEU')} |",
      f"| new | {nc['OK']} | {nc['WEAK']} | {nc['FALLBACK']} | {nc['THIEU']} | {n_intro(fresh, 'THIEU')} |", "",
      f"**Old picks today's rules refuse:** {dict(audit) or 'none'} (of {sum(1 for s in old['slots'] if s.get('path'))} picks); "
      f"{unsure} old picks with the sex / age not visible (spec has no sex= / age= tokens: only lines that ask count).",
      f"**Intro shots that showed another species** (old KIN / any tier): {len(intro_other)}", ""]
md += [f"- {x}" for x in intro_other[:30]]
md += ["", f"**Old picks that broke a story rule** (kill / resting / sex / age): {len(bad)}", ""] + [f"- {x}" for x in bad[:30]]
md += ["", f"**New run, clips of the slot's animal refused:** {dict(rej)}; "
       f"{sum('kiểm tra' in str(s.get('why', '')) for s in fresh)} picks capped WEAK ('kiểm tra'); "
       f"{len(changed)} slots changed clip.", "", "## Changed slots (first 40)", "",
       "| # | giờ | shot cần | old | new |", "|---|---|---|---|---|"]
for a, b in changed[:40]:
    cap = lambda s: f"{s['status']} {s.get('caption', '')[:55]}" + (f" ({s['why']})" if s.get("why") else "")  # noqa: E731
    md.append(f"| {a['slot']} | {plan.tc(a['start'])} | {a['need'][:45]} | {cap(a)} | {cap(b)}"
              + (f" loại {b['rej']}" if b["status"] == "THIEU" and b.get("rej") else "") + " |")
out = work / "bench_story_first.md"
out.write_text("\n".join(md) + "\n", "utf-8")
print("\n".join(md[:16]))
print(f"-> {out}")
