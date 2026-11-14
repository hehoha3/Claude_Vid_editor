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


def image_parts(paths, side=1024):
    """Stills -> inline JPEG parts (long side <= side px: ~2 Gemini tiles each) + one digest for the cache key."""
    import base64
    import io
    from PIL import Image
    parts, h = [], hashlib.sha256()
    for f in paths:
        im = Image.open(f).convert("RGB")
        im.thumbnail((side, side))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
        data = buf.getvalue()
        h.update(Path(f).name.encode("utf-8") + data)
        parts += [{"text": f"=== IMAGE {Path(f).name} ==="},
                  {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(data).decode("ascii")}}]
    return parts, h.hexdigest()


def generate(root, task, src, model, thinking, max_tokens, as_json, timeout, no_cache=False, dry_run=False,
             cache_flags=(), images=()):
    """One cached generateContent call -> dict(response, stats, cfile, cached) or dict(dry_run, cfile).
    images: inline parts from image_parts() (their digest belongs in cache_flags)."""
    cfile = cache_path(root, task, src, model, thinking, max_tokens, as_json, *cache_flags)
    if cfile.is_file() and not no_cache:
        cached = json.loads(cfile.read_text(encoding="utf-8"))
        return {"response": cached["response"], "stats": cached.get("stats", {}), "cfile": cfile, "cached": True}
    if dry_run:
        return {"dry_run": True, "cfile": cfile}
    gen = {"maxOutputTokens": max_tokens, "thinkingConfig": {"thinkingLevel": thinking}}
    if as_json:
        gen["responseMimeType"] = "application/json"
    body = {"systemInstruction": {"parts": [{"text": SYSTEM}]},
            "contents": [{"role": "user", "parts": list(images) + [{"text": src + "TASK:\n" + task.strip()}]}],
            "generationConfig": gen}
    t0 = time.time()
    resp = call(secret(), API + model + ":generateContent", body, timeout=max(10, timeout))
    response, stats = extract(resp)
    stats["ms"] = int((time.time() - t0) * 1000)
    log = root / ".work" / "gemini" / "usage.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M"), "model": model,
                             **{k: v for k, v in stats.items() if k != "finish"}}) + "\n")
    if not response.strip():
        block = resp.get("promptFeedback", {}).get("blockReason", "")
        raise RuntimeError(f"No text response (finish={stats['finish']} block={block}). Raise --max-tokens or check the prompt.")
    cfile.parent.mkdir(parents=True, exist_ok=True)
    cfile.write_text(json.dumps({"response": response, "stats": stats}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"response": response, "stats": stats, "cfile": cfile, "cached": False}


LITE = "gemini-3.5-flash-lite"


def with_fallback(run, model):
    """run(model); flash busy (HTTP 503 / 429) -> one call on flash-lite. -> (result, model used, fell_back)."""
    try:
        return run(model), model, False
    except RuntimeError as e:
        if model == LITE or not any(f"HTTP {c}" in str(e) for c in (503, 429)):
            raise
        return run(LITE), LITE, True


# locate: Gemini reads whole code files (line-numbered) and returns only the line ranges Claude should Read.
LOCATE_EXT = {".py", ".md", ".toml", ".ps1", ".yaml", ".yml", ".ini", ".cfg"}
LOCATE_SKIP = {".venv", "__pycache__", ".git", ".secrets", "_pushed", "node_modules", "cache"}
LOCATE_TASK = (
    "The SOURCE blocks are code/doc files; every line starts with its line number and a tab.\n"
    "QUESTION: {q}\n"
    "Reply with the smallest line ranges Claude must read to answer or change this, most relevant first, "
    "max {n} lines, one per range, exactly:\n<file>:<start>-<end> | <function/section> | <why, max 12 words>\n"
    "<file> = the SOURCE name exactly as given. Ranges cover whole functions/blocks, each <= {span} lines. "
    "Nothing relevant -> reply only: NONE"
)


def locate_files(root, names):
    out = []
    for name in names:
        f = Path(name).expanduser()
        f = (f if f.is_absolute() else root / f).resolve()
        if root not in f.parents and f != root:
            raise RuntimeError(f"locate reads only inside the project: {f}")
        found = sorted(f.rglob("*")) if f.is_dir() else [f]
        for g in found:
            rel = g.relative_to(root)
            if g.is_file() and g.suffix.lower() in LOCATE_EXT and not LOCATE_SKIP & set(rel.parts):
                out.append(g)
        if not f.exists():
            raise RuntimeError(f"Not found: {f}")
    return list(dict.fromkeys(out))


def locate_source(root, files):
    blocks, lengths = [], {}
    for f in files:
        rel = f.relative_to(root).as_posix()
        lines = f.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        lengths[rel] = len(lines)
        blocks.append(f"=== SOURCE {rel} ===\n" + "\n".join(f"{i}\t{t}" for i, t in enumerate(lines, 1)) + "\n\n")
    return "".join(blocks), lengths


def parse_ranges(text, lengths, span):
    """Keep only ranges that name a sent file and real lines; clamp to the file end and to span."""
    ranges = []
    for line in text.splitlines():
        head, _, rest = line.strip().partition("|")
        loc, _, nums = head.strip().rpartition(":")
        a, _, b = nums.partition("-")
        loc = loc.strip().replace("\\", "/")
        if loc not in lengths or not a.strip().isdigit():
            continue
        start = max(1, int(a))
        end = int(b) if b.strip().isdigit() else start
        end = min(max(start, end), lengths[loc], start + span - 1)
        if start > lengths[loc]:
            continue
        ranges.append({"file": loc, "start": start, "end": end, "note": rest.strip()[:120]})
    return ranges


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
    lo = subs.add_parser("locate", help="Line ranges in code files that answer a question (Claude Reads only those)")
    lo.add_argument("--question", required=True, help="What Claude wants to find or change, in English")
    lo.add_argument("--file", action="append", required=True, help="Project file or folder (repeatable)")
    lo.add_argument("--root", default=".")
    lo.add_argument("--model", default="gemini-3.5-flash", help="flash busy (503/429) -> one call on flash-lite")
    lo.add_argument("--max-ranges", type=int, default=6)
    lo.add_argument("--span", type=int, default=120, help="Max lines per range (default 120)")
    lo.add_argument("--max-input-chars", type=int, default=600000)
    lo.add_argument("--timeout", type=int, default=120)
    lo.add_argument("--no-cache", action="store_true")
    lo.add_argument("--dry-run", action="store_true")
    v = subs.add_parser("vision", help="One Gemini look at still images (frame QA); answer like ask")
    v.add_argument("--task", required=True)
    v.add_argument("--image", action="append", required=True, help="PNG/JPG still (repeatable, max 24)")
    v.add_argument("--root", default=".")
    v.add_argument("--model", default="gemini-3.5-flash", help="flash busy (503/429) -> one call on flash-lite")
    v.add_argument("--thinking", default="low", choices=["minimal", "low", "medium", "high"])
    v.add_argument("--max-tokens", type=int, default=2048)
    v.add_argument("--side", type=int, default=1024, help="long side px sent per image (default 1024)")
    v.add_argument("--timeout", type=int, default=120)
    v.add_argument("--no-cache", action="store_true")
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

    if opts.cmd == "vision":
        imgs = [Path(f).expanduser().resolve() for f in opts.image]
        missing = [str(f) for f in imgs if not f.is_file()]
        if missing or len(imgs) > 24:
            raise RuntimeError(f"vision: {len(imgs)} images (max 24), missing: {missing[:3]}")
        parts, digest = image_parts(imgs, opts.side)
        r, model, fell_back = with_fallback(
            lambda m: generate(root, opts.task, "", m, opts.thinking, opts.max_tokens, False, opts.timeout,
                               opts.no_cache, cache_flags=("vision", digest, opts.side), images=parts), opts.model)
        out = {"ok": True, "cached": r["cached"], "model": model, "preview": r["response"][:6000],
               "full_result_path": str(r["cfile"]), "stats": r["stats"]}
        if fell_back:
            out["warning"] = "flash busy: answered by flash-lite, trust its flags less"
        if r["stats"].get("finish") == "MAX_TOKENS":
            out["warning"] = "Answer cut at --max-tokens; raise it."
        json_out(out)
        return

    if opts.cmd == "locate":
        files = locate_files(root, opts.file)
        if not files:
            raise RuntimeError("No readable code/doc files in --file")
        src, lengths = locate_source(root, files)
        if len(src) > opts.max_input_chars:
            raise RuntimeError(f"Sources {len(src)} chars > --max-input-chars {opts.max_input_chars}; name fewer files")
        task = LOCATE_TASK.format(q=opts.question.strip(), n=opts.max_ranges, span=opts.span)
        r, model, fell_back = with_fallback(
            lambda m: generate(root, task, src, m, "low", 1024, False, opts.timeout, opts.no_cache, opts.dry_run,
                               ("locate",)), opts.model)
        if r.get("dry_run"):
            json_out({"ok": True, "dry_run": True, "files": len(files), "input_chars": len(src),
                      "cache_path": str(r["cfile"])})
            return
        ranges = parse_ranges(r["response"], lengths, opts.span)[:opts.max_ranges]
        out = {"ok": True, "cached": r["cached"], "model": model, "ranges": ranges,
               "read_lines": sum(x["end"] - x["start"] + 1 for x in ranges), "of_lines": sum(lengths.values()),
               "stats": r["stats"]}
        if fell_back:
            out["warning"] = "flash busy: answered by flash-lite, check the ranges harder"
        if not ranges:
            out["warning"] = ("Gemini found nothing relevant" if r["response"].strip().startswith("NONE")
                              else "No valid range in the answer: " + r["response"][:200]) + "; use Grep instead"
        json_out(out)
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
    r = generate(root, opts.task, src, opts.model, opts.thinking, opts.max_tokens, opts.json, opts.timeout,
                 opts.no_cache, opts.dry_run)
    cfile = r["cfile"]
    if r.get("dry_run"):
        json_out({"ok": True, "dry_run": True, "input_chars": len(src), "cache_path": str(cfile)})
        return
    response, stats = r["response"], r["stats"]
    if r["cached"]:
        json_out({"ok": True, "cached": True, "preview": response[:opts.max_output_chars],
                  "full_result_path": str(cfile), "stats": stats})
        return
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
