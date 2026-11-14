"""Offline checks for gemini_bridge.py: .venv/Scripts/python.exe .claude/skills/gemini-assist/scripts/test_gemini_bridge.py"""
import importlib.util
from pathlib import Path
import tempfile

spec = importlib.util.spec_from_file_location("bridge", Path(__file__).with_name("gemini_bridge.py"))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

r = Path("x")
assert b.cache_path(r, "Task", "one", "m") == b.cache_path(r, " Task\n", "one ", "m")  # whitespace-insensitive
assert b.cache_path(r, "Task", "one", "m") != b.cache_path(r, "Task", "two", "m")
assert b.cache_path(r, "Task", "one", "m", "low") != b.cache_path(r, "Task", "one", "m", "high")
assert b.cache_path(r, "Task", "one", "m", False) != b.cache_path(r, "Task", "one", "m", True)  # --json

text, stats = b.extract({
    "candidates": [{"content": {"parts": [{"text": "hidden", "thought": True}, {"text": "A"}, {"text": "B"}]},
                    "finishReason": "STOP"}],
    "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 2, "thoughtsTokenCount": 9,
                      "cachedContentTokenCount": 3}})
assert text == "AB", text
assert stats == {"in": 5, "cached": 3, "out": 2, "thoughts": 9, "finish": "STOP"}, stats
assert b.extract({})[0] == ""

with tempfile.TemporaryDirectory() as tmp:
    f = Path(tmp, "tags.txt")
    f.write_text("﻿shot_01: jaguar \n", encoding="utf-8")
    assert b.build_source([f]) == "=== SOURCE tags.txt ===\nshot_01: jaguar\n\n"  # BOM + edges stripped, labelled

    # locate: numbered sources, only project files, ranges validated + clamped
    root = Path(tmp).resolve()
    (root / "pkg" / "__pycache__").mkdir(parents=True)
    (root / "pkg" / "a.py").write_text("x = 1\ndef f():\n    return x\n", encoding="utf-8")
    (root / "pkg" / "__pycache__" / "a.py").write_text("junk\n", encoding="utf-8")
    (root / "pkg" / "data.json").write_text("{}", encoding="utf-8")
    files = b.locate_files(root, ["pkg"])
    assert [p.name for p in files] == ["a.py"], files  # __pycache__ and .json skipped
    src, lengths = b.locate_source(root, files)
    assert src.startswith("=== SOURCE pkg/a.py ===\n1\tx = 1\n2\tdef f():"), src
    assert lengths == {"pkg/a.py": 3}
    got = b.parse_ranges("pkg/a.py:2-99 | f | returns x\nother.py:1-2 | ? | ?\npkg/a.py:9-9 | x | x\nNONE", lengths, 120)
    assert got == [{"file": "pkg/a.py", "start": 2, "end": 3, "note": "f | returns x"}], got
    assert b.parse_ranges("pkg\\a.py:1-3 | m", lengths, 2)[0]["end"] == 2  # backslash path, span cap
    try:
        b.locate_files(root, [str(root.parent)])
        raise AssertionError("outside root accepted")
    except RuntimeError:
        pass


def busy(m):  # flash busy -> one flash-lite call; any other error is raised
    if m != b.LITE:
        raise RuntimeError("HTTP 503 busy")
    return "lite"


assert b.with_fallback(busy, "gemini-3.5-flash") == ("lite", b.LITE, True)
assert b.with_fallback(lambda m: m, "gemini-3.5-flash") == ("gemini-3.5-flash", "gemini-3.5-flash", False)
for model, err in (("gemini-3.5-flash", "HTTP 400 bad"), (b.LITE, "HTTP 503 busy")):
    try:
        b.with_fallback(lambda m: (_ for _ in ()).throw(RuntimeError(err)), model)
        raise AssertionError(f"{model} {err} swallowed")
    except RuntimeError as e:
        assert str(e) == err, e
print("ok")
