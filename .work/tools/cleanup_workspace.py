"""Remove what the workspace no longer needs (updated 2026-10-24). Dry run by default; --apply deletes (the user runs
it: Claude never deletes files). Files are unlinked one by one, folders removed with rmdir once empty (never rmtree).
Only paths inside this repo are touched (never D:, Z:, library, knowledge, memory, ledgers, tag sheets, the plan.json
of finished videos: plan.py's music history, the Postgres mirror and bench_story_first read them). Work of the active
videos (folders directly in D:\\Chann_*) is kept.
    .venv/Scripts/python.exe .work/tools/cleanup_workspace.py           # list
    .venv/Scripts/python.exe .work/tools/cleanup_workspace.py --apply   # delete
"""
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
W = ROOT / ".work"
# videos still being worked on = folders directly in D:\Chann_* (not _done / _pushed, never looked inside those);
# 2026-10-23: a hard-coded list would have deleted africa_2's narration job started in another session
ACTIVE = {re.sub(r"[^a-z0-9]", "", p.name.lower()) for ws in Path("D:/").glob("Chann_*") if ws.is_dir()
          for p in ws.iterdir() if p.is_dir() and not p.name.startswith("_")}
OLD = time.time() - 6 * 3600  # one-off scripts younger than 6 h may belong to a running session: kept
# 2026-10-24: the scripts the docs name moved into git (bench_story_first.py, make_africa_ai_folders.ps1 -> skill
# scripts, this file -> .work/tools); .work/scripts holds one-offs only; one naming an active video is kept
# tag_source/sheets stays: plan.py measures ground colour from them and the library retag waits at batch_601
PROTECTED = [W / "library", W / "knowledge", W / "memory", W / "tools", W / "doc_edit" / "ledgers",
             W / "tag_source" / "sheets", W / "cache"]


def done(p):
    """Work folder of a finished video: its name (c2_africa1, africa_1_mp3...) contains no active video's name."""
    n = re.sub(r"[^a-z0-9]", "", p.name.lower())
    return not any(a in n for a in ACTIVE)


TARGETS = [  # (path, why)
    *[(p, "dvr_cowork frames exports (one-off QC stills)") for p in sorted((W / "stills").glob("*"))],
    (W / "grade" / "frames320", "light.py / match.py frame cache (rebuilt on the next color run, ~1-3 min)"),
    *[(p, "grade plan / stdout of a finished video") for p in sorted((W / "grade").glob("*"))
      if p.name != "frames320" and done(p)],
    *[(p, "old copy of a plan folder") for p in sorted((W / "doc_edit").glob("*_old*"))],
    *[(p, "narration job of a finished video") for p in sorted(W.glob("*_mp3")) if done(p)],
    *[(W / n, "stdout dump") for n in ("plan_fill_stdout.txt",)],
    *[(p, "stdout dump") for p in sorted((W / "doc_edit").glob("*_stdout.txt"))],
    (W / "intro_mv", "work of the removed intro-music-visualization skill"),
    (W / "skill_snapshots", "old SKILL.md snapshot"),
    (W / "doc-edit-workspace", "old SKILL.md snapshot"),
    (W / "thumb_tune", "thumbnail tuning test renders (finals are in D:\\Thumbs)"),
    (W / "tmp", "one-off scripts, logs and test frames of past sessions"),
    *[(p, "tagger agent scratch script") for pat in ("_*.py", "b*_write.py", "mk*.py", "write_*.py", "batch_*_gen.py",
                                                     "__pycache__")
      for p in sorted((W / "tag_source").glob(pat))],
    *[(p, "one-off script (done once, or replaced by dvr_cowork at/find/offline / story.py / plan.py --spec --out)")
      for p in sorted((W / "scripts").glob("*")) if p.stat().st_mtime < OLD and done(p)],
    *[(p, "export / stdout / one-off script of a finished video, loose in .work")
      for pat in ("*.drt", "done_*", "grade_plan_*", "match_*_out.txt", "match_*_stdout.txt", "rerender_*",
                  "scripts_*.py", "lic_times.txt", "hide_logo_list.txt", "vosync_*.txt")
      for p in sorted(W.glob(pat)) if p.is_file() and done(p)],
    *[(p, "Whisper / stdout folder of a finished video") for pat in ("voice_*", "congo_1")
      for p in sorted(W.glob(pat)) if done(p)],
    *[(p, "audio-expert run of a finished video") for p in sorted((W / "audio_expert").glob("*"))
      if p.is_dir() and done(p)],
    *[(W / "hide_logo" / n, "hide-logo one-off output") for n in ("tmp", "quick_fix_unique.txt", "quick_run.txt")],
    (W / "process_ai_video" / "run_check.txt", "process-ai-video one-off output"),
    (W / "tmp_vosync_check", "vosync.py test files (2026-10-23)"),
    (W / "tmp_story_test", "story.py benchmark on africa_3 (2026-10-24, results in the handoff)"),
    (ROOT / ".claude" / "skills" / "hide-logo" / "run.sh", "in git, unused: calls python3 outside .venv"),
    (ROOT / ".claude" / "skills" / "hide-logo" / "evals", "in git, unused: evals of the old marker-based hide-logo"),
]


def files_of(p):
    return [p] if p.is_file() else sorted((f for f in p.rglob("*") if f.is_file()), key=lambda f: -len(f.parts))


def main(apply):
    total = 0
    for p, why in TARGETS:
        p = p.resolve()
        assert p.is_relative_to(ROOT) and p != W and not any(p.is_relative_to(k) or k.is_relative_to(p)
                                                            for k in PROTECTED), f"refused: {p}"
        if not p.exists():
            continue
        fs = files_of(p)
        size = sum(f.stat().st_size for f in fs)
        total += size
        print(f"{size / 1e6:8.1f} MB  {p.relative_to(ROOT)}  ({why})")
        if apply:
            for f in fs:
                f.unlink()
            for d in sorted((d for d in ([p] + list(p.rglob("*")) if p.is_dir() else []) if d.is_dir()),
                            key=lambda d: -len(d.parts)):
                d.rmdir()
            assert not p.exists(), f"still there: {p}"
    print(f"{'deleted' if apply else 'would free'} {total / 1e6:.0f} MB" + ("" if apply else "  (dry run: add --apply)"))


if __name__ == "__main__":
    main("--apply" in sys.argv)
