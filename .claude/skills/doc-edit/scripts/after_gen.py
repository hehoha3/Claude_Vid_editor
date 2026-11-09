"""/doc-edit after-gen-vid <video> (user 2026-11-08): ingest the generated clips -> fill-THIEU on the whole V1 (every
generated clip at its own slot) -> color, one summary. The tag step needs Claude's tagger agents in between, so two calls:

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/after_gen.py prep <video folder>
        jobs check (+ decide ingest) -> scan -> tag prepare: prints `batches: batch_NN ...` (none -> `batches: -`)
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/after_gen.py finish <video folder> [batch_NN ...]
        tag apply -> organize --apply -> scan -> plan --sub-broad -> place --fill -> gen_swap --apply -> gaps ->
        fill-report -> light.py plan + apply (each Resolve write backs up first)

Prints only summary lines (token cost, user 2026-11-08). A step that fails stops the run with its last lines.
"""
import csv, os, re, subprocess, sys
from itertools import islice
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT)]
sys.stdout.reconfigure(encoding="utf-8")
from dvr_cowork import jobs  # noqa: E402
from dvr_cowork.resolve_ops import use_channel  # noqa: E402
from dvr_cowork.videokey import video_key  # noqa: E402

PY = str(ROOT / ".venv/Scripts/python.exe")
SK = ROOT / ".claude/skills"
ROOTS = {"amazon": ("ai", []), "africa": ("africa_ai_check", ["--africa"])}  # region -> scan root, organize flag


def run(args, keep=r".", last=6, env=None):
    """Run a step; print its lines matching `keep` (regex), or the last `last` lines on failure. -> stdout."""
    r = subprocess.run([PY, *map(str, args)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8", **(env or {})})
    out = r.stdout + r.stderr
    if r.returncode:
        print("\n".join(out.strip().splitlines()[-last:]))
        raise SystemExit(f"STOP: {Path(str(args[0])).name} {' '.join(map(str, args[1:3]))} failed")
    for ln in out.splitlines():
        if re.search(keep, ln):
            print("  " + ln.strip()[:240])
    return out


def region_root(key):
    reg = jobs.plan_of(key).get("region", "amazon")
    if reg not in ROOTS:
        raise SystemExit(f"STOP: region {reg}: no AI root for after-gen-vid yet")
    return ROOTS[reg]


def prompt_ids(vdir):
    p = vdir / "missing-prompt.csv"
    return {r["shot_id"] for r in csv.DictReader(p.open(encoding="utf-8-sig"))} if p.exists() else set()


def prep(vdir):
    use_channel(vdir)
    key = video_key(vdir)
    root, _ = region_root(key)
    print(f"[1] jobs check {key}")
    out = jobs.check(key)
    if out["copying"] or out["broken"]:
        raise SystemExit("STOP: files still copying / broken (list above): wait or remove them, then call again")
    ids = prompt_ids(vdir)
    foreign = [n for n in out["ok"] if Path(n).stem not in ids]
    if foreign:  # not named after this video's prompts: whose? ask (rows dropped so the next check sees them again)
        with jobs.db() as c:
            for n in foreign:
                c.execute("delete from checked where video=? and path like ?", (key, f"%{n}"))
        raise SystemExit(f"STOP: {len(foreign)} new clips are not shot_ids of {vdir.name}'s missing-prompt.csv: "
                         + ", ".join(foreign[:20]) + " -> which video are they for? ask the user")
    jobs.decide(key, "ingest", "after-gen-vid")
    print(f"[2] scan {root}")
    run([SK / "scan-source/scripts/scan_source.py", root], keep=r"files \|")
    print("[3] tag prepare")
    o = run([SK / "tag-source/scripts/tag_source.py", "prepare", root], keep=r"clips in|nothing|no untagged")
    b = re.findall(r"batch_\d+", o)
    print("batches: " + (" ".join(b) or "-"))


def finish(vdir, batches):
    use_channel(vdir)
    key = video_key(vdir)
    root, flag = region_root(key)
    tl = os.environ["DVR_TIMELINE"]
    if batches:
        print("[4] tag apply")
        run([SK / "tag-source/scripts/tag_source.py", "apply", *batches], keep=r"applied|MISSING|off-vocab|yolo")
    print("[5] organize")
    run([SK / "tag-source/scripts/organize.py", *flag, "--apply"], keep=r"^moved|^stay in|failed")
    run([SK / "scan-source/scripts/scan_source.py", root], keep=r"files \|")
    print("[6] plan --sub-broad (whole V1)")
    run([SK / "doc-edit/scripts/plan.py", vdir / "audios", "--sub-broad"], keep=r"^generated|spec errors|WARNING slot",
        last=15)  # DVR_CHANNEL: set by use_channel, inherited
    md = vdir / "plan.md"
    if md.exists():  # its 3rd line = the status counts; read only the head of a long plan.md
        with md.open(encoding="utf-8") as f:
            print("  " + next(islice(f, 2, 3), "").strip())
    print("[7] place --fill")
    run([SK / "doc-edit/scripts/place.py", vdir, "--fill"],
        keep=r"^backup|^V1 placed|^V1 still empty|^black fades|FAILED|failed: \[.+\]")
    print("[8] generated clips onto their slots")
    run([SK / "doc-edit/scripts/gen_swap.py", vdir, "--apply"], keep=r".")
    print("[9] check")
    try:  # gaps exits non-zero when it finds gaps: report them, still colour
        run(["-m", "dvr_cowork", "gaps"], keep=r"gaps to fill|^\s+\d\d:\d\d", env={"DVR_TIMELINE": tl})
    except SystemExit as e:
        print(f"  {e} (gaps listed by `dvr_cowork gaps`)")
    o = run(["-m", "dvr_cowork.jobs", "fill-report", key], keep=r"slots \||THIEU:")
    print(f"  FALLBACK 'any light' to look at: {o.count('any light: look')}")
    print("[10] color (light pass)")
    run([SK / "colorist/scripts/light.py", "plan"], keep=r"^V1 |^story |^golden|^slope", env={"DVR_TIMELINE": tl}, last=15)
    run([SK / "colorist/scripts/light.py", "apply"], keep=r"^backup", env={"DVR_TIMELINE": tl}, last=15)
    print(f"after-gen-vid {vdir.name} ({tl}): done -> view >= 12 frames (dvr_cowork frames --stats), then report")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2 or a[0] not in ("prep", "finish"):
        raise SystemExit(__doc__)
    v = Path(a[1])
    v = v.parent if v.name.lower() == "audios" else v
    prep(v) if a[0] == "prep" else finish(v, a[2:])
