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
print("ok")
