# Sourcing a concept: trend recommendations and YouTube adaptation

Both `Chann_N` modes end at the same place: one approved concept, an approved cast, a runtime and a new `vid_DDMMYY_N` folder, reached in **one round of questions**. Report what was actually retrieved and from which source; never claim to have watched images you did not analyse.

## Channel, folder and rotation: one call

`.venv/Scripts/python.exe -m dvr_cowork next-video Chann_N` returns `channel_dir` (the single `D:\Chann_N_*`), `next_video` (`vid_DDMMYY_N`, N = 1 + highest of today in the channel root and `_done/`), `next_archetype` (rotation migration → lost → predator → mother → throne) and the last films' title/archetype/cast. Use it instead of listing folders or opening sibling story.json files. It never enters `_pushed`; never write to `Z:`. It stops if zero or several channel folders match: ask the user.

The Resolve project has the same name as the folder and holds one video per channel (`D:\Chann_1_*\vid_021126_1` and `D:\Chann_2_*\vid_021126_1` both edit in project `vid_021126_1`, each in its own `Chann_N/` bin), so leave `resolve_project` unset. Create the folder (via `init`) only after approval; never reuse an existing one.

## Research sources and budget

| Source | What it gives | Cost |
|---|---|---|
| `dvr_cowork youtube-trends Chann_N [--query "..."]...` | Most viewed 4–20 min videos of the last 90 days by views/day, title patterns, tags; compact digest | 101 YouTube quota units per new query, 0 cached (7 days); no Claude-heavy output |
| `dvr_cowork youtube-reference Chann_N <url>` | Title, channel, duration, views, age, tags, description | 1 unit. No captions: the official API can't download another channel's captions |
| vidIQ `vidiq_outliers` | Videos beating their channel's average (what's breaking out) | credits; one call |
| vidIQ `vidiq_video_transcript` | Reference captions | ≈5 credits; one call |

Use both sources, but at most **one vidIQ call per run**. Run research calls in the same turn as `next-video` and the reference reads. If vidIQ fails for credits/quota/auth, say so in one line and continue on the YouTube API alone; don't retry. Without captions in adapt mode, summarise the reference from title/description/tags and offer that the user paste the transcript (YouTube "Show transcript") for a beat-level comparison; never invent the reference's plot. If the YouTube API fails too (revoked token: `youtube-login --key Chann_N`; quota), stop and report. Skip vidIQ visual analysis unless the user asks.

## Mode A: `/create-doc-mov Chann_N` (recommend)

1. One parallel turn: `next-video`, `youtube-trends Chann_N` (default five mountain predator/prey queries; add `--query` only for an angle worth testing), optionally one `vidiq_outliers` (e.g. "mountain goat predator", long-form). Avoid repeating the archetype/cast of `recent`.
2. Present 3 concepts (up to 5 only if trends clearly support more) in one compact table: working title, archetype, protagonist side, antagonist side, dual peril, clock, chokepoint, runtime + one-line reason, trend evidence (1–2 videos with views/day). Concepts are original; trends inform species pairing, setting and angle, not plots.
3. In the **same** AskUserQuestion call, ask two questions: (a) which concept (one option per concept; free text for their own idea), (b) the cast question below, phrased for "the chosen concept's cast".

## Mode B: `/create-doc-mov Chann_N <youtube_url>` (adapt)

1. One parallel turn: `next-video`, `youtube-reference Chann_N <url>`, `vidiq_video_transcript`.
2. Summarise the reference in ≤6 lines: archetype, protagonist side, antagonist side, tension mechanics (dual peril, clock, chokepoint, role reversal, hook angle), beat order. Then ask the cast question (and confirm the proposed runtime as a second question if it isn't obvious).
3. **Keep** the archetype and the tension mechanics, i.e. the *kind* of danger and pressure. **Replace** geography, season, event chain, set pieces, escape method, all narration wording and the title. Pacing and runtime follow this workspace; the cast follows the user's answer.
4. Before writing, compare your beat outline with the reference beat order. If a viewer of the reference could predict your next scene, change the obstacle or the turn. No names, signature lines or distinctive images carried over. Record `"reference_url"` and a one-line `"adaptation_note"` (kept / changed) in story.json.

## Cast question

AskUserQuestion, current main cast in the question text as two sides:

- **Protagonist side**: e.g. ibex mother + one kid; a herd of 9 markhor descending; a lone young chamois.
- **Antagonist side**: e.g. a pack of 4 wolves; one snow leopard; a lone wolf; a golden eagle.

Question: "Bạn có muốn thay đổi dàn nhân vật hay không? Dàn hiện tại — Chính: … / Phản diện: …". Options: "Giữ nguyên dàn nhân vật" and "Claude đề xuất dàn mới"; the automatic free-text "Other" is the input field for their own cast. Only if they pick "Claude đề xuất dàn mới", offer 2–3 concrete casts and ask once more. The answer becomes the locked cast: exact counts, sex/age, readable markings, IDs. Don't reopen the concept.

## Choosing runtime (8–15 min)

Count the distinct turns the story can carry (new obstacle, changed tactic, clock shrinking, reversal, decisive attempt): roughly one per 1.5–2 minutes after the first 60s. 4–5 turns ≈ 8–9 min, 6 ≈ 10–11, 7–8 ≈ 12–15. Longer films cost proportionally more to write and to generate shots for, so don't stretch a 5-turn story to 12 minutes. State minutes and why in one line; the user may override. Longer than 15 only on request; never pad with repeated attacks or slower narration.
