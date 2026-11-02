# Canonical source contract

Store source in `<video>/.production/story.json`. A JSON document is a local file, not a database. Build outputs are regenerated together; do not edit the four Markdown files separately.

Top fields:

| Field | Meaning |
|---|---|
| schema | 2 |
| title, premise, central_question, payoff | Original film concept and visible outcome |
| archetype | `migration`, `lost`, `predator`, `mother` or `throne` (see narrative-dna.md); ignored by the compiler, read for rotation |
| target_minutes | 8, 11 or longer; includes first 60s |
| fps | Default 24; match Resolve before placement |
| wpm | Default 145; calibrate to actual voice |
| resolve_project | Optional explicit Resolve project name; default video folder name |
| characters | At least two `{id, species, lock}` entries; lock includes count, age/sex where known, coat/marks, anatomy |
| environment | Terrain, light, weather and color lock repeated in prompts |
| geography | Named landmarks, route, elevation, screen axis; no teleporting |
| synthetic_disclosure | Clear statement of original AI dramatization |
| scenes | Ordered contiguous scenes, no gaps |

Each scene contains `id`, `title`, `phase` (hook/setup/story/ending), `change` (what changes), `shots`, `voice`. First scene is exactly five `{duration_s:6}` hook placeholders. Second scene has five 6s generated shots for setup. Final scene is ending. Main scenes may have any number of 6–9s shots summing to target runtime. IDs must be unique.

Each **non-hook** shot:

```json
{
  "duration_s": 7,
  "characters": ["MOTHER", "KID"],
  "action": "Mother braces on a narrow shelf as the kid approaches a cracked step",
  "camera": "distant high-oblique telephoto, slow lateral pan",
  "direction": "left to right; upper wall stays behind the pair",
  "start_state": "Mother is one body length ahead of the kid on the lower shelf",
  "end_state": "Mother remains braced; the kid stops before the cracked step",
  "beats": [
    "Hold a wide view identifying both animals and the drop",
    "The kid advances cautiously toward the cracked step",
    "The mother plants her hooves and turns her head back",
    "The kid stops short; keep the gap unresolved"
  ],
  "hook_role": "obstacle",
  "intensity": 4,
  "spoiler": false
}
```

Allowed hook roles: threat, vulnerability, pursuit, obstacle, unanswered, none. Intensity is 0–5. Omission of `spoiler:false` makes a shot ineligible for hook selection. Mark the actual resolution as a spoiler. Metadata is a candidate hint; `shot_qc.json` supplies actual visual approval and a clean hook source-in later.

`voice` is a list of `{en: "one English paragraph", vi: "full Vietnamese translation"}`. No newlines inside a block. Several blocks in the same scene remain adjacent physical lines in transcript; blank lines separate scenes. **Global nonblank physical-line order** maps to `1.mp3…N.mp3`. Do not use rendered Markdown paragraph count. The compiler schedules their starts inside each scene from estimated or measured durations. It never cuts the source audio.

Default maximum inter-block/tail pause is 3s. A scene may set `pause_limit_s` up to 6 with an explicit `pause_reason`; use sparingly. A voice overflow is an error: shorten/re-record the affected approved block with the user, or revise that scene's shot budget in a new production version. Do not change picture durations after prompts have been issued.

After conform, `timestamp.md` uses exact frame-based millisecond onsets in `## English` and `## Vietnamese`; English equals transcript text exactly. SRT spans follow actual placed MP3 durations. Script math does not verify translation quality, factual accuracy, dramatic strength, internal silence or visual continuity; the agent must review them.
