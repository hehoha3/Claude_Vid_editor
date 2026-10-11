"""doc-edit: prompts for the THIẾU slots of plan.json, to generate the missing footage.

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/missing.py <video>                 # list groups
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/missing.py <video> --write         # render prompts
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/missing.py --selftest

List mode groups THIẾU slots by character tag + species + action + setting + light and suggests how many
clips to generate (one generated clip ~CLIP_YIELD s of usable footage, cut into several shots).
Claude writes .work/doc_edit/<video>/prompts.txt:
    ## G3
    <shot_content, one species, English>      <- one line per clip to generate
    ## +harpy_eagle                           <- extra group (not a THIẾU slot, e.g. daily life): saved to D:/AI_video/<name>
Write mode prepends PREFIX to every line and writes <video>/missing_prompts.md.
"""
import json, math, re, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from dvr_cowork.config import load_config  # noqa: E402
AI = load_config()["paths"]["ai_video"]  # AI clips root of this machine (config.toml)
PREFIX = ("Cinematic nature documentary, BBC Earth style, 4k ultra-realistic, national geographic photography, "
          "high speed phantom camera, detailed animal textures, No text, no logo, No voiceover, "
          "no background music, natural sound, normal motion - ")
CLIP_YIELD = 6.0  # usable seconds per generated clip (8-10 s clip minus morphing ends, cut into 2-3 shots)


def groups(slots):
    g = defaultdict(list)
    for s in slots:
        if s["status"] != "THIEU":
            continue
        f = s["filter"]
        tag = re.match(r"\[([^\]]+)\]", s["need"])
        animal = f.get("sp", ["none"]) != ["none"]
        # animals: one group per character + main action (setting comes from the screenplay context);
        # no animal: one group per setting + light
        key = (tag[1] if tag else "-", ",".join(f.get("sp", ["none"])), (f.get("act") or ["-"])[0],
               "" if animal else (f.get("set") or ["-"])[0], "" if animal else (f.get("light") or ["-"])[0])
        g[key].append(s)
    out = []
    for i, (k, ss) in enumerate(sorted(g.items(), key=lambda kv: (kv[0][0] == "-", -len(kv[1]))), 1):
        sec = sum(s["dur"] for s in ss)
        out.append({"id": f"G{i}", "key": k, "slots": [s["slot"] for s in ss], "sec": round(sec, 1),
                    "clips": max(1, math.ceil(sec / CLIP_YIELD)),
                    "needs": list(dict.fromkeys(s["need"] for s in ss))})
    return out


def parse_prompts(text):
    p, cur = defaultdict(list), None
    for n, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if s.startswith("## "):
            cur = s[3:].strip()
        elif s and not s.startswith("#"):
            assert cur, f"prompts line {n}: text before any '## G<n>' header"
            assert not s.lower().startswith("cinematic nature documentary"), f"prompts line {n}: write only the shot content, the prefix is added"
            p[cur].append(s)
    return p


def main(video, write):
    work = ROOT / ".work" / "doc_edit" / video
    plan = json.loads((work / "plan.json").read_text("utf-8"))
    gs = groups(plan["slots"])
    if not write:
        print(f"{sum(len(g['slots']) for g in gs)} THIẾU slots, {sum(g['sec'] for g in gs):.0f}s -> "
              f"{len(gs)} groups, {sum(g['clips'] for g in gs)} clips suggested")
        for g in gs:
            tag, sp, act, st, li = g["key"]
            print(f"{g['id']} [{tag}] sp={sp} act={act or '-'} set={st or '-'} light={li or '-'} | "
                  f"{len(g['slots'])} slots {g['sec']}s -> {g['clips']} clips | " + " / ".join(g["needs"][:4]))
        return
    p = parse_prompts((work / "prompts.txt").read_text("utf-8"))
    ids = {g["id"] for g in gs}
    extra = [k for k in p if k.startswith("+")]
    assert set(p) - set(extra) <= ids, f"unknown groups in prompts.txt: {sorted(set(p) - set(extra) - ids)}"
    md = [f"# Prompt cho footage THIẾU — {video}\n",
          f"{sum(len(v) for v in p.values())} clip cần generate (mỗi clip chỉ 1 loài, cắt thành nhiều shot). "
          "Generate xong: lưu đúng thư mục ghi ở từng nhóm (tên thư mục = tên loài khi tag), chạy "
          "/process-ai-video, /scan-source ai, /tag-source, rồi /doc-edit plan + place --replace.\n"]
    for g in gs:
        if g["id"] not in p:
            continue
        tag, sp, act, st, li = g["key"]
        folder = "landscape" if sp == "none" else sp.split(",")[0].replace(" ", "_")  # tagger names species from it
        md += [f"## {g['id']} · [{tag}] {sp} · {act or '-'} · {st or '-'} · {li or '-'} — {len(g['slots'])} shot, {g['sec']}s",
               f"Lưu vào: `{AI}\\{folder}` · Slot: {', '.join(map(str, g['slots']))}",
               f"Cần: {' / '.join(g['needs'][:6])}", "", "```"]
        md += [PREFIX + x for x in p[g["id"]]] + ["```", ""]
    for k in extra:
        md += [PREFIX + x for x in p[k]]
    missing = [g["id"] for g in gs if g["id"] not in p]
    out = Path(plan["video_dir"]) / "missing_prompts.txt"  # user wants prompt lines only (2026-10-09)
    out.write_text("\n".join(l for l in md if l.startswith(PREFIX)) + "\n", "utf-8")
    print(f"{sum(len(v) for v in p.values())} prompts in {len(p)} groups -> {out}")
    for g in gs:
        if g["id"] in p:
            sp = g["key"][1]
            print(f"  {g['id']} {len(p[g['id']])} clips -> {AI}\\"
                  + ("landscape" if sp == "none" else sp.split(",")[0].replace(" ", "_")))
    for k in extra:
        print(f"  {k} {len(p[k])} clips -> {AI}\\{k[1:]}")
    print("groups without prompts:", missing)


def selftest():
    sl = [{"slot": 1, "status": "THIEU", "dur": 3.0, "need": "[C] Mèo lao", "filter": {"sp": ["golden cat"], "act": ["run"]}},
          {"slot": 2, "status": "THIEU", "dur": 4.0, "need": "[C] Mèo chạy", "filter": {"sp": ["golden cat"], "act": ["run"]}},
          {"slot": 3, "status": "OK", "dur": 2.0, "need": "x", "filter": {}},
          {"slot": 4, "status": "THIEU", "dur": 2.5, "need": "Tán rừng", "filter": {"sp": ["none"], "set": ["canopy"]}}]
    g = groups(sl)
    assert [x["slots"] for x in g] == [[1, 2], [4]] and g[0]["clips"] == 2 and g[1]["key"][0] == "-"
    p = parse_prompts("## G1\nA golden cat sprints\nA golden cat pauses\n## G2\nCanopy at dawn\n")
    assert len(p["G1"]) == 2 and p["G2"] == ["Canopy at dawn"]
    try:
        parse_prompts("## G1\nCinematic nature documentary, BBC Earth style - x\n"); raise SystemExit("prefix accepted")
    except AssertionError:
        pass
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    selftest() if "--selftest" in sys.argv else main(a[0], "--write" in sys.argv)
