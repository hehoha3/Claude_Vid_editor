"""One Gemini call through the gemini-assist bridge (key, cache, usage log live there): text + token stats.
Used by seo.py, create-doc-mov translate_vi.py and doc-edit missing.py --draft (user 2026-10-31/11-01)."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / ".claude" / "skills" / "gemini-assist" / "scripts" / "gemini_bridge.py"


LITE = "gemini-3.5-flash-lite"


def ask(task, files, json_out=False, thinking="low", max_tokens=4096, max_input=30000, model=LITE):
    """-> (answer text, stats with "model" = who answered). Raises SystemExit with the bridge's error.
    model: flash-lite for short structured text (SEO); gemini-3.5-flash where wording quality matters (translation,
    prompts: flash-lite named a spectacled caiman "caiman tai tượng" in the 2026-11-01 test). flash busy (HTTP 503 /
    429, often on 2026-11-01) -> ONE call on flash-lite instead (bounded fallback, never a retry loop); the caller
    prints the model so Claude reviews a flash-lite answer harder."""
    try:
        return _ask(task, files, json_out, thinking, max_tokens, max_input, model)
    except SystemExit as e:
        if model == LITE or not any(f"HTTP {c}" in str(e) for c in (503, 429)):
            raise
        print(f"gemini: {model} busy ({str(e)[:60]}...), using {LITE} once", file=sys.stderr)
        return _ask(task, files, json_out, thinking, max_tokens, max_input, LITE)


FRAME_TASK = (
    "Each IMAGE is one graded frame of a BBC-style wildlife documentary (real footage mixed with AI-generated clips, "
    "16:9 UHD, one natural look per story). QA screen for the colorist/editor: flag only what must be fixed.\n"
    "Check: colour cast or look off vs the other frames; crushed blacks / clipped highlights / too dark or flat; "
    "logo, watermark, burnt-in text or subtitle; AI artefacts (melted or extra limbs, warped faces/eyes, smeared fur, "
    "morphing background, impossible anatomy); soft / out of focus / heavy noise; black, frozen or empty frame; "
    "letterbox or pillarbox bars; plastic/CG look next to real footage.\n"
    "One line per IMAGE, in the given order, exactly:\n<image name> | OK\nor\n<image name> | FLAG | <issue>: <where, "
    "max 12 words>\nAdd [?] when unsure. No other lines."
)


def screen_frames(paths, model="gemini-3.5-flash"):
    """Gemini vision pre-screen of exported stills -> ({file name: "OK" | "FLAG ..."}, stats). Claude then views only
    the flagged stills (+ one control). Raises SystemExit with the bridge error (no retry)."""
    cmd = [sys.executable, str(BRIDGE), "vision", "--task", FRAME_TASK, "--root", str(ROOT), "--model", model]
    for p in paths:
        cmd += ["--image", str(p)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       env=os.environ | {"PYTHONIOENCODING": "utf-8"})
    out = json.loads(r.stdout) if r.stdout.strip() else {"ok": False, "error": r.stderr.strip()[-300:] or "no output"}
    if not out.get("ok"):
        raise SystemExit(f"Gemini failed: {out.get('error')} (no retry)")
    verdicts = {}
    for line in out["preview"].splitlines():
        name, _, rest = line.partition("|")
        name, rest = name.strip(), rest.strip()
        if name and rest:
            verdicts[name] = "OK" if rest.upper() == "OK" else rest.replace("FLAG |", "FLAG").strip()
    stats = out.get("stats", {}) | {"model": out.get("model", model) + (" (cache)" if out.get("cached") else "")}
    if out.get("warning"):
        stats["warning"] = out["warning"]
    return verdicts, stats


def _ask(task, files, json_out, thinking, max_tokens, max_input, model):
    # bridge default timeout 90 s: a 32k-token flash draft (thinking medium) runs longer -> scale with the answer cap
    cmd = [sys.executable, str(BRIDGE), "ask", "--thinking", thinking, "--max-tokens", str(max_tokens),
           "--max-input-chars", str(max_input), "--task", task, "--root", str(ROOT), "--model", model,
           "--timeout", str(max(90, max_tokens // 60))]
    cmd += ["--json"] if json_out else []
    for f in files:
        cmd += ["--input", str(f)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       env=os.environ | {"PYTHONIOENCODING": "utf-8"})  # emoji / Vietnamese vs a cp1252 console
    # argparse refusals (input too large) go to stderr with an empty stdout: keep their message
    out = json.loads(r.stdout) if r.stdout.strip() else {"ok": False, "error": r.stderr.strip()[-300:] or "no output"}
    if not out.get("ok"):
        raise SystemExit(f"Gemini failed: {out.get('error')} (no retry)")
    if "MAX_TOKENS" in str(out.get("stats", {}).get("finish", "")):
        raise SystemExit(f"Gemini answer cut at {max_tokens} tokens: raise max_tokens")
    full = json.loads(Path(out["full_result_path"]).read_text("utf-8"))
    # a cache hit costs nothing: the caller's token line says so instead of repeating the old counts as spent
    return full["response"], out.get("stats", {}) | {"model": model + (" (cache, 0 tokens)" if out.get("cached") else "")}
