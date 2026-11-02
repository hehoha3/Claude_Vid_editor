---
name: research-youtube
description: Top 20 most-viewed YouTube videos of the last 10 days for a topic, with links (presets amazon-wildlife, africa-wildlife; or any topic, "(ai)" = AI-made only). Use for /research-youtube, "tìm video nhiều view nhất tuần", "top video chủ đề X", "trend YouTube tuần này", or a niche check before a new video topic.
---

# research-youtube

One script run (two at most); no vidIQ, browser or other API calls; never open a video.

1. **Preset** (user 2026-11-01): `amazon-wildlife` = jungle documentaries anywhere (Amazon, Congo, Borneo, Central
   America ...), `africa-wildlife` = savanna / bush (Serengeti, Mara, Kruger, Okavango ...); AI or real footage.
   Run `.venv/Scripts/python.exe .claude/skills/research-youtube/scripts/top_videos.py <preset>` (its own queries,
   >= 20 min, 30 rows) and keep 20: a narrated predator / survival story. Drop the other region, other habitats
   (Arctic, North America ...), relax 4K footage without a story, movies.
2. **Other topic**: 2-4 English queries the way creators title that niche (100 quota units each, 200 under 20 min):
   `top_videos.py -q "..." -q "..." [--ai] [--days 10] [--n 20] [--min 3]`. `(ai)` / "AI" in the topic -> `--ai` and
   "AI" in half the queries. Numbers from the user override the defaults.
3. Drop clearly off-topic rows (search drift: "amazon" -> shopping); too few left -> one re-run with tighter queries.
   Fewer than 20 = say so, never pad.
4. Reply in Vietnamese: the table as printed (plain `https://youtu.be/...` links), then at most 3 lines of takeaways
   (dominant channels, title / length patterns, views/ngày standouts).

Errors: `no valid YouTube token` -> the user runs `.venv/Scripts/python.exe -m dvr_cowork.youtube login`. Quota error
-> stop, it resets ~14:00-15:00 giờ VN; no retry.
Limits (say when relevant): `--ai` is a keyword check, AI videos that never say so are missed; search returns at most
50 per query and length, so this is the top of what search surfaces, not a census.
