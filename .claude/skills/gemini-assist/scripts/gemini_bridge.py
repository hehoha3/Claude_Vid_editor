#!/usr/bin/env python3
"""Minimal Gemini bridge for Claude Code: one REST call, no tools, response cache, usage log.

Calls the Gemini API directly (stdlib urllib) instead of Gemini CLI: no ~6k-token CLI system prompt or tool
declarations, capped thinking/output, nothing on disk or on the web for Gemini to touch. API key comes from Windows
Credential Manager via keyring and is only sent in a request header.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

SERVICE = "ClaudeVidEditor.Gemini"
USER = "api_key"
VERSION = "3.1.0"
API = "https://generativelanguage.googleapis.com/v1beta/models/"
# Stable prefix (system + sources first, task last) so Gemini's implicit cache can discount repeats.
SYSTEM = (
    "You are a specialist called by Claude, an AI agent, not by a human. Claude is the senior editor, colorist and "
    "re-recording mixer for BBC-style wildlife documentaries (AI clips + real footage, English narrator, DaVinci "
    "Resolve). You give a second opinion that Claude verifies before anything is changed.\n"
    "Rules:\n"
    "- Use only the SOURCE blocks. Never invent facts, file names, timecodes or species details.\n"
    "- Output exactly the format the TASK asks for. No preamble, no restating the task, no closing remarks, "
    "no markdown fences. Terse English.\n"
    "- Keep IDs, slot numbers, timecodes and file names exactly as given.\n"
    "- Mark any uncertain item with [?] at its end.\n"
    "- If the input is not enough to answer, reply only: INSUFFICIENT: <what is missing>."
)


def secret():
    try:
        import keyring
    except ImportError as e:
        raise RuntimeError("Run: .venv\\Scripts\\python.exe -m pip install keyring") from e
    token = keyring.get_password(SERVICE, USER)
    if not token:
        raise RuntimeError("No Gemini API key saved. Run this script with setup-key first.")
    return token


def cache_path(root, task, source, model, *flags):
    payload = json.dumps({"bridge_version": VERSION, "task": task.strip(), "source": source.strip(), "model": model,
                          "flags": [str(f) for f in flags]}, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return root / ".work" / "gemini" / "cache" / f"{digest}.json"


def call(api_key, url, body=None, timeout=60):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8") if body else None,
                                 headers={"x-goog-api-key": api_key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
        except ValueError:
            msg = ""
        raise RuntimeError(f"Gemini API HTTP {e.code}: {msg[:400]} (no automatic retry)") from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(f"Gemini API unreachable/timed out: {e} (no automatic retry)") from None


def extract(resp):
    """Answer text (thought parts skipped) + compact token stats."""
    cand = (resp.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []) if not p.get("thought"))
    u = resp.get("usageMetadata", {})
    stats = {"in": u.get("promptTokenCount", 0), "cached": u.get("cachedContentTokenCount", 0),
             "out": u.get("candidatesTokenCount", 0), "thoughts": u.get("thoughtsTokenCount", 0),
             "finish": cand.get("finishReason", "")}
    return text, stats


def build_source(files):
    """Each file as a labelled block so Gemini can cite it by name."""
    return "".join(f"=== SOURCE {f.name} ===\n{f.read_text(encoding='utf-8-sig').strip()}\n\n" for f in files)


def json_out(obj):
    print(json.dumps(obj, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description="Call Gemini API safely, returning short JSON to Claude")
    subs = p.add_subparsers(dest="cmd", required=True)
    subs.add_parser("setup-key", help="Save API key in OS credential store")
    c = subs.add_parser("check", help="Verify key + model with a free model lookup (no tokens used)")
    c.add_argument("--model", default="gemini-3.5-flash-lite")
    us = subs.add_parser("usage", help="Token totals from the usage log (no API call)")
    us.add_argument("--root", default=".")
    a = subs.add_parser("ask", help="Run one Gemini job")
    a.add_argument("--task", required=True, help="Question or work request, with the exact output format wanted")
    a.add_argument("--input", action="append", default=[], help="UTF-8 source text file (repeatable)")
    a.add_argument("--root", default=".", help="Claude project directory to write cache")
    a.add_argument("--model", default="gemini-3.5-flash-lite", help="Gemini model id (default: gemini-3.5-flash-lite)")
    a.add_argument("--thinking", default="minimal", choices=["minimal", "low", "medium", "high"],
                   help="Thinking level; thoughts are billed as output (default: minimal)")
    a.add_argument("--max-tokens", type=int, default=1024, help="Hard cap on answer tokens (default: 1024)")
    a.add_argument("--json", action="store_true", help="Force a valid JSON answer (describe the shape in --task)")
    a.add_argument("--timeout", type=int, default=90)
    a.add_argument("--max-input-chars", type=int, default=30000)
    a.add_argument("--max-output-chars", type=int, default=3500)
    a.add_argument("--no-cache", action="store_true")
    a.add_argument("--dry-run", action="store_true", help="Check input and cache without calling API")
    opts = p.parse_args()

    if opts.cmd == "setup-key":
        import getpass
        try:
            import keyring
        except ImportError:
            p.error("Install dependency: .venv\\Scripts\\python.exe -m pip install keyring")
        key = getpass.getpass("Paste Gemini API Key (hidden): ").strip()
        if not key:
            p.error("Empty key not saved")
        keyring.set_password(SERVICE, USER, key)
        json_out({"ok": True, "message": "Gemini API key saved to OS credential store"})
        return

    if opts.cmd == "check":
        info = call(secret(), API + opts.model, timeout=20)
        json_out({"ok": True, "api_key_found": True, "model": info.get("name"),
                  "input_limit": info.get("inputTokenLimit"), "output_limit": info.get("outputTokenLimit")})
        return

    root = Path(opts.root).expanduser().resolve()
    log = root / ".work" / "gemini" / "usage.jsonl"
    if opts.cmd == "usage":
        tot = {"calls": 0, "in": 0, "cached": 0, "out": 0, "thoughts": 0}
        for line in (log.read_text(encoding="utf-8").splitlines() if log.is_file() else []):
            row = json.loads(line)
            tot["calls"] += 1
            for k in tot.keys() - {"calls"}:
                tot[k] += row.get(k, 0)
        json_out({"ok": True, **tot})
        return

    files = []
    for name in opts.input:
        f = Path(name).expanduser().resolve()
        if not f.is_file():
            p.error(f"Input file not found: {f}")
        files.append(f)
    if sum(f.stat().st_size for f in files) > opts.max_input_chars * 4:
        p.error("Input is too large. Provide a condensed excerpt or increase limit explicitly.")
    src = build_source(files)
    if len(src) > opts.max_input_chars:
        p.error("Input exceeds max input characters. Chunk it before delegation.")
    cfile = cache_path(root, opts.task, src, opts.model, opts.thinking, opts.max_tokens, opts.json)
    if cfile.is_file() and not opts.no_cache:
        cached = json.loads(cfile.read_text(encoding="utf-8"))
        json_out({"ok": True, "cached": True, "preview": cached["response"][:opts.max_output_chars],
                  "full_result_path": str(cfile), "stats": cached.get("stats", {})})
        return
    if opts.dry_run:
        json_out({"ok": True, "dry_run": True, "input_chars": len(src), "cache_path": str(cfile)})
        return

    gen = {"maxOutputTokens": opts.max_tokens, "thinkingConfig": {"thinkingLevel": opts.thinking}}
    if opts.json:
        gen["responseMimeType"] = "application/json"
    body = {"systemInstruction": {"parts": [{"text": SYSTEM}]},
            "contents": [{"role": "user", "parts": [{"text": src + "TASK:\n" + opts.task.strip()}]}],
            "generationConfig": gen}
    t0 = time.time()
    resp = call(secret(), API + opts.model + ":generateContent", body, timeout=max(10, opts.timeout))
    response, stats = extract(resp)
    stats["ms"] = int((time.time() - t0) * 1000)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M"), "model": opts.model,
                             **{k: v for k, v in stats.items() if k != "finish"}}) + "\n")
    if not response.strip():
        block = resp.get("promptFeedback", {}).get("blockReason", "")
        raise RuntimeError(f"No text response (finish={stats['finish']} block={block}). Raise --max-tokens or check the prompt.")
    cfile.parent.mkdir(parents=True, exist_ok=True)
    cfile.write_text(json.dumps({"response": response, "stats": stats}, ensure_ascii=False, indent=2), encoding="utf-8")
    out = {"ok": True, "cached": False, "preview": response[:opts.max_output_chars], "full_result_path": str(cfile),
           "stats": stats}
    if stats["finish"] == "MAX_TOKENS":
        out["warning"] = "Answer cut at --max-tokens; raise it if the preview looks incomplete."
    if response.lstrip().startswith("INSUFFICIENT"):
        out["warning"] = "Gemini says the input is insufficient; add the missing source, do not just re-ask."
    json_out(out)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        json_out({"ok": False, "error": str(exc)})
        sys.exit(1)
