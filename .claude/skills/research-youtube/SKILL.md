---
model: sonnet
name: research-youtube
description: YouTube market research for wildlife documentaries - top (most viewed of a topic, last N days), rising candidates of a niche, competitor channels' new uploads, outliers of a watchlist; presets amazon-wildlife, africa-wildlife, ocean-wildlife, frozen-wildlife or any topic ("(ai)" = AI-made only). Use for /research-youtube, "tìm video nhiều view nhất tuần", "top video chủ đề X", "trend YouTube tuần này", "video đang lên", "đối thủ / kênh cạnh tranh đăng gì", "video outlier", or a niche check before a new video topic.
---

# research-youtube

One engine, one CLI call per request (`$R` = `.venv/Scripts/python.exe -m dvr_cowork.youtube_research`); Python
fetches, caches, filters and ranks; you read only its digest (≤ 12 rows). No vidIQ, browser, Gemini, MCP or subagent
unless the user asks; never open a video. Read-only YouTube: nothing here uploads or edits.

| User asks | Run |
|---|---|
| `/research-youtube <preset>` (legacy), "top / nhiều view nhất" | `$R top --preset <preset>` (>= 20 min, 30 rows) |
| other topic | `$R top -q "..." -q "..." [--ai] [--days 10] [--top 20] [--min 3]` (2–4 English queries the way creators title the niche; `(ai)` -> `--ai`) |
| `rising <preset>`, "video đang lên" | `$R rising --preset <preset> [--days 10]` (>= 30 min long-form + the preset's watchlist uploads) |
| `competitors --watchlist <w>`, "đối thủ" | `$R competitors --watchlist <w> [--days 30]` |
| `outliers --watchlist <w> [--topic "lion buffalo"]` | `$R outliers --watchlist <w> [--topic "..."]` |

Presets: amazon (jungle anywhere: Amazon, Congo, Borneo ...), africa (savanna / bush), ocean (research only; ocean
production stays off), frozen (mountain predator / prey). Numbers from the user override defaults. Unsure about quota
-> `--dry-run` first (0 requests); `--cached-only` = store only; `$R doctor` = budget, reset, watchlists.

Reply in Vietnamese: the table as printed (plain links), then 3–5 lines of semantic takeaways: species / conflict
motifs, title formulas, length; for outliers per row a `why_to_inspect` hypothesis + what NOT to copy (plot chain,
exact wording, footage). Drop clearly off-topic rows; fewer than asked = say so, never pad.

Honesty rules (YouTube API policy III.E.4.h, enforced by the engine): `metrics approval_required` = no views/day, VPH,
growth or outlier ratio exists; never estimate one yourself from views / age, never call raw totals "trending speed".
Rows marked `*` are the tool's own metric (only with approval in config). No CTR, retention, revenue or traffic of other
channels: not public. "Gaps" = angles missing from the rows seen, not the whole market.

Stops: `STOP: no valid YouTube token` -> the user runs `.venv/Scripts/python.exe -m dvr_cowork youtube login --key
Chann_N`. `STOP` quota / budget -> report the reset time it prints; no retry, never another key. Empty watchlist ->
ask the user for competitor channels (UC id or @handle) and add them to `config/research_youtube.toml [watchlists]`.
Limits: search returns ≤ 50 per query and length (the top of what search surfaces, not a census); `--ai` is a keyword
check. Scheduled scans (Task Scheduler, no Claude): `references/schedule.md`.
