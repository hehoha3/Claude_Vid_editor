---
name: memory-save
description: Save a confirmed project decision or verified lesson.
argument-hint: "[memory to save]"
disable-model-invocation: true
---

Save the information in $ARGUMENTS as project memory.
Procedure:
1. Check existing memories to avoid duplicates.
2. Save only confirmed, durable information.
3. Choose one category: decisions, incidents, workflows or handoffs.
4. Use memory_gateway.py save to create a new Markdown note.
5. Keep the note concise and factual.
6. Verify that the note is indexed and searchable.
Never store passwords, secrets, full transcripts, raw media, or speculative conclusions.
Never change existing CLAUDE.md safety rules.
Never write to Z:.