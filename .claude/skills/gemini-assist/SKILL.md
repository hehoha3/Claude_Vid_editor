---
name: gemini-assist
description: Delegate short, read-only script analysis, footage metadata review, and QA summaries to Gemini via a low-token local Python bridge. Use when the user explicitly wants Gemini assistance.
argument-hint: <task or question>
---

# Gemini Assist for Claude_Vid_editor

When user calls `/gemini-assist`, use the local bridge at `.claude/skills/gemini-assist/scripts/gemini_bridge.py`.
It calls the Gemini REST API directly (no Gemini CLI, no tools, no web: Gemini only sees the text sent), ~1 s per
call. Gemini already knows (system prompt): it is called by Claude, the project is BBC-style wildlife docs in
Resolve, answers are terse English in the exact format asked, `[?]` = uncertain, `INSUFFICIENT: ...` = missing input.

## Writing the call (the contract)
- `--task` = goal + exact output shape, one line each, in English (fewer tokens than Vietnamese). Example:
  `Check narration lines vs shot tags. Per mismatch one line: <line#> | <shot> | <why>. Max 10 lines.`
  Never restate project background; never paste what the system prompt already says.
- Sources go in files under `.work/gemini/<video or topic>/`, passed with `--input` (repeatable; each arrives as
  `=== SOURCE <filename> ===`, so name files meaningfully and refer to them by name in the task). Claude passes the
  path and never opens the file itself (CLAUDE.md rule 6 still applies to Claude). Never Z:, `_pushed`, a video
  folder, secrets, whole indexes.
- Want to parse the answer -> `--json` and give the JSON shape in the task. Want prose -> ask for numbered lines.
- Several questions on the same sources -> one call with a numbered task list. Follow-up questions on the same
  sources: keep the same `--input` files in the same order (sources come before the task, so Gemini's implicit
  cache discounts the repeated prefix; `stats.cached` shows it).
- Gemini has no web access (Search grounding is off by the user's choice, 2026-10-31). A task that needs current
  facts: Claude searches with its own WebSearch/WebFetch, saves the relevant excerpt (+ URLs) to a source file, and
  Gemini only analyses that file.

## Command
`.venv/Scripts/python.exe .claude/skills/gemini-assist/scripts/gemini_bridge.py ask --task "..." [--input F]... --root .`
Defaults: `gemini-3.5-flash-lite`, `--thinking minimal`, `--max-tokens 1024`. Raise `--thinking low|medium` only
for real reasoning (thoughts are billed as output); raise `--max-tokens` only after a MAX_TOKENS `warning`.
`check` = free key + model lookup. `usage` = token totals from `.work/gemini/usage.jsonl` (no call).
`--dry-run` = cache path, no call.

## Rules
1. Never read, print, log, or transmit API keys to Claude. Secret lives in OS credential store (keyring), sent only
   in the request header by Python.
2. Read only `preview` (+ `warning`). Open `full_result_path` only if the preview is cut. A repeat of the
   same task + inputs + flags is served from cache (free); no `--no-cache` unless the user asks.
3. `warning` INSUFFICIENT -> add the missing source, never re-ask the same thing.
4. Gemini is a second opinion. Claude validates every proposal against the project rules, narration, and story;
   `[?]` items are checked or dropped, never passed on as fact.
5. Gemini may never write Resolve timelines, move media, change `.claude/skills`, or render. All DaVinci actions
   remain in current project skills and Python engine.
6. Do not invoke Gemini for simple file copying, import, scan, rename, FFmpeg, generation, or regular expressions.
7. No discussion loops between Claude and Gemini. One Gemini attempt per task, unless explicitly re-requested.
8. If the bridge returns an error, report it without retrying blindly (it never retries itself).
9. Keep the two videos' inputs/results independently scoped. Do not mix channel IDs or `THIEU` slots.

You are operating under the current user's task: `$ARGUMENTS`.
