"""transcript.md -> Genmax narrator, one transcript line = one mp3 -> <audios>\\mp3.zip -> extracted to <audios>\\mp3.

usage: genmax_audio.py AUDIOS [--profile mossbeard|callum] [--go]
Without --go: free preview (line/char count, cached, config ready?). --go = paid run, capped at exactly this
transcript's lines and characters (the user's "ok" after the review). Worker files stay in .work\\doc_edit\\<video>\\genmax.
Prints the worker's JSON, then one OK/STOP line.
"""
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
WORKER = ROOT / ".claude" / "skills" / "genmax" / "scripts" / "genmax_worker.py"
VOICE = {"Chann_1": "mossbeard", "Chann_2": "callum"}  # user 2026-10-30


def main():
    audios = Path(sys.argv[1]).resolve()
    video = audios.parent
    profile = (sys.argv[sys.argv.index("--profile") + 1] if "--profile" in sys.argv
               else VOICE.get("_".join(video.parent.name.split("_")[:2])))
    if not profile:
        sys.exit(f"STOP: no voice for {video.parent.name}; pass --profile mossbeard|callum")
    lines = [l.strip() for l in (audios / "transcript.md").read_text(encoding="utf-8-sig").splitlines() if l.strip()]
    work = ROOT / ".work" / "doc_edit" / video.name / "genmax"
    gen = work / "mp3"
    gen.mkdir(parents=True, exist_ok=True)
    src = work / "lines.md"  # the worker splits on blank lines; a blank line after every line = 1 line, 1 mp3
    src.write_text("\n\n".join(lines) + "\n", encoding="utf-8")

    def run(*a):
        r = subprocess.run([sys.executable, str(WORKER), *a, "--input", str(src), "--out", str(gen),
                            "--profile", profile], capture_output=True, text=True)
        print((r.stdout or r.stderr).strip())
        try:
            return json.loads((r.stdout or r.stderr).strip().splitlines()[-1])
        except (IndexError, ValueError):
            return {"status": "error"}

    if "--go" not in sys.argv:
        res = run("preview")
        print(("OK" if res.get("configuration_ready") else "STOP: Genmax config not verified (contract.json, voice_id, "
               "Natural)") + f" | {video.name} {profile} {len(lines)} lines {sum(map(len, lines))} chars")
        return
    zp, dst = audios / "mp3.zip", audios / "mp3"
    if zp.exists() or any(dst.glob("*.mp3")):
        sys.exit(f"STOP: {zp} or {dst} already has audio; never overwritten - ask the user")
    res = run("resume", "--confirm-spend", "--max-new", str(len(lines)),
              "--max-new-chars", str(sum(map(len, lines)) + len(lines)))
    if res.get("status") != "complete":
        sys.exit(f"STOP: Genmax {res.get('status')} - no retry, report it")
    res = run("verify")
    if res.get("status") != "pass" or res.get("valid") != len(lines):
        sys.exit(f"STOP: verify {res.get('status')} {res.get('issues')}")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_STORED) as z:  # mp3 is already compressed
        for i in range(1, len(lines) + 1):
            z.write(gen / f"{i}.mp3", f"{i}.mp3")
    with zipfile.ZipFile(zp) as z:
        z.extractall(dst)
    n = len(list(dst.glob("*.mp3")))
    print(("OK" if n == len(lines) else "STOP: extract count mismatch")
          + f" | {video.name} {profile} {n}/{len(lines)} mp3 {res.get('duration_s')} s -> {zp} -> {dst}")


if __name__ == "__main__":
    main()
