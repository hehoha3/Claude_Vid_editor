---
name: memory-save
description: Save a confirmed project decision or verified lesson.
argument-hint: "[memory to save]"
disable-model-invocation: true
---

Save the information in $ARGUMENTS as project memory.
Procedure:
1. Search first (`memory_gateway.py search "..." --limit 3`) to avoid duplicates.
2. Save only confirmed, durable information.
3. Choose one category: decisions, incidents, workflows or handoffs (video state = edit `handoffs/current.md`).
4. Same fact already there (decision changed, path renamed) -> `memory_gateway.py save --update <path from search>
   --title .. --text ..` (full new text, add "was X until <date>"); otherwise `save --type <category> --title .. --text ..`.
5. Keep the note concise and factual.
6. Verify that the note is indexed and searchable.
Never store passwords, secrets, full transcripts, raw media, or speculative conclusions.
Never change existing CLAUDE.md safety rules.
Never write to Z:.