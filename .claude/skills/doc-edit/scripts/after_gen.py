"""/doc-edit after-gen-vid <video> (user 2026-11-08): the clips generated for this video -> fill-THIEU on the whole V1
(every generated clip at its own slot) -> color, one summary.

User 2026-11-13: the generated clips of a video live ONLY in its own <video>\\shots (named by the missing-prompt.txt
shot_id; one-time: never tagged, never filed, never another video's slot). The region _check is the shared library
folder (`/doc-edit ingest`), never read here.

    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/after_gen.py finish <video folder>
        prep, then plan --sub-broad -> place --fill -> gen_swap --apply -> gaps -> fill-report -> reframe --fill-only (letterbox zoom) -> light.py plan + apply
        (each Resolve write backs up first)
    .venv/Scripts/python.exe .claude/skills/doc-edit/scripts/after_gen.py prep <video folder>
        only the check: jobs check of <video>\\shots (still copying / broken / not a prompt of this video) + decide ingest

Prints only summary lines (token cost, user 2026-11-08). A step that fails stops the run with its last lines.
"""
import os, re, subprocess, sys
from itertools import islice
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT)]
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)  # a log file shows each step as it ends
from dvr_cowork import jobs  # noqa: E402
from dvr_cowork.prompt_rules import prompt_rows  # noqa: E402  missing-prompt.txt (or an older video's .csv)
from dvr_cowork.resolve_ops import use_channel  # noqa: E402
from dvr_cowork.videokey import video_key  # noqa: E402
from dvr_cowork.vtypes import shot_media  # noqa: E402

PY = str(ROOT / ".venv/Scripts/python.exe")
SK = ROOT / ".claude/skills"


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


def prompt_ids(vdir):
    return {r["shot_id"] for r in prompt_rows(vdir)}


def prep(vdir):
    use_channel(vdir)
    key = video_key(vdir)
    sh = vdir / "shots"
    if not sh.is_dir():
        raise SystemExit(f"STOP: {sh} missing: the generated clips of this video go there (named by shot_id)")
    print(f"[1] jobs check {key} ({sh})")
    out = jobs.check(key, d=sh)
    if out["copying"] or out["broken"]:
        raise SystemExit("STOP: files still copying / broken (list above): wait or remove them, then call again")
    ids = prompt_ids(vdir)
    clips = shot_media(vdir)
    stray = [f.name for f in clips if f.stem not in ids]
    print(f"  shots/ clips: {len(clips)}, named by a prompt of this video: {len(clips) - len(stray)}/{len(ids)} prompts"
          + (f"; NOT a prompt of this video (left out, ask whose): {', '.join(stray[:8])}" if stray else ""))
    jobs.decide(key, "ingest", "after-gen-vid")
    return key  # shots\ clips are never tagged (user 2026-11-12 / 2026-11-13)


def finish(vdir):
    key = prep(vdir)  # one call (2026-11-14): the check stops the run on copying / broken clips
    tl = os.environ["DVR_TIMELINE"]
    print("[2] plan --sub-broad (whole V1)")
    run([SK / "doc-edit/scripts/plan.py", vdir / "audios", "--sub-broad"], keep=r"^generated|^shots/|spec errors|WARNING slot",
        last=15)  # DVR_CHANNEL: set by use_channel, inherited
    md = vdir / "plan.md"
    if md.exists():  # its 3rd line = the status counts; read only the head of a long plan.md
        with md.open(encoding="utf-8") as f:
            print("  " + next(islice(f, 2, 3), "").strip())
    print("[3] place --fill")
    run([SK / "doc-edit/scripts/place.py", vdir, "--fill"],
        keep=r"^backup|^V1 placed|^V1 still empty|^black fades|FAILED|failed: \[.+\]")
    print("[4] generated clips onto their slots")
    run([SK / "doc-edit/scripts/gen_swap.py", vdir, "--apply"], keep=r".")
    try:  # user 2026-11-17: 1-3 h films keep the AI clips' own audio on A1 in the intro + story 1 (free A1 only)
        run([SK / "doc-edit/scripts/place.py", vdir, "--a1-only"], keep=r"A1 audio|no AI clips|FAILED|failed: \[.+\]")
    except SystemExit as e:
        print(f"  A1: {e}")
    print("[5] check")
    try:  # gaps exits non-zero when it finds gaps: report them, still colour
        run(["-m", "dvr_cowork", "gaps"], keep=r"gaps to fill|^\s+\d\d:\d\d", env={"DVR_TIMELINE": tl})
    except SystemExit as e:
        print(f"  {e} (gaps listed by `dvr_cowork gaps`)")
    o = run(["-m", "dvr_cowork.jobs", "fill-report", key], keep=r"slots \||THIEU:")
    print(f"  FALLBACK 'any light' to look at: {o.count('any light: look')}")
    print("[6] letterbox fill (top/bottom bars -> light zoom, user 2026-11-15)")
    run([SK / "doc-edit/scripts/reframe.py", vdir, "--fill-only", "--apply"], keep=r"^V1 |fill  |^backup|failed")
    print("[7] color (light pass)")
    run([SK / "colorist/scripts/light.py", "plan"], keep=r"^V1 |^story |^golden|^slope", env={"DVR_TIMELINE": tl}, last=15)
    run([SK / "colorist/scripts/light.py", "apply"], keep=r"^backup", env={"DVR_TIMELINE": tl}, last=15)
    print(f"after-gen-vid {vdir.name} ({tl}): done -> frame check (doc-edit SKILL.md: frames --stats --gemini), then report")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2 or a[0] not in ("prep", "finish"):
        raise SystemExit(__doc__)
    v = Path(a[1])
    v = v.parent if v.name.lower() == "audios" else v
    prep(v) if a[0] == "prep" else finish(v)
