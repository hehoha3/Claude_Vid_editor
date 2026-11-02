# Canonical source contract

Store source in `<video>/.production/story.json`. A JSON document is a local file, not a database. Build outputs are regenerated together; do not edit the four Markdown files separately.

Top fields:

| Field | Meaning |
|---|---|
| schema | 2 |
| title, premise, central_question, payoff | Original film concept and visible outcome |
| archetype | `migration`, `lost`, `predator`, `mother` or `throne` (see narrative-dna.md); ignored by the compiler, read for rotation |
| target_minutes | 8–15 (longer on request); includes first 60s |
| fps | Default 24; match Resolve before placement |
| wpm | Default 145; calibrate to actual voice |
| resolve_project | Leave unset: the project is the folder name `vid_DDMMYY_N`, shared by every channel's same-numbered video |
| reference_url, adaptation_note | Adapt mode only; ignored by the compiler |
| characters | At least two `{id, species, lock}` entries; lock includes count, age/sex where known, coat/marks, anatomy |
| environment | Terrain, light, weather and color lock repeated in prompts |
| geography | Named landmarks, route, elevation, screen axis; no teleporting |
| synthetic_disclosure | Clear statement of original AI dramatization |
| scenes | Ordered contiguous scenes, no gaps |

Each scene contains `id`, `title`, `phase` (hook/setup/story/ending), `change` (what changes), `shots`, `voice`. First scene is exactly five `{duration_s:6}` hook placeholders. Second scene has five 6s generated shots for setup. Final scene is ending. Main scenes may have any number of 6–9s shots summing to target runtime. IDs must be unique.

Each **non-hook** shot needs `duration_s, characters, action, camera, direction, start_state, end_state, beats`. A scene may set `camera`, `direction` and `characters` once as defaults; a shot's own value wins. If `beats` is omitted the compiler derives four (establish start state → `cause` or a tension build → `action` → settle into end state), which is right for routine shots. Write explicit beats where the motion inside the take matters.

Compact scene (preferred):

```json
{
  "id": "S04", "title": "The cracked step", "phase": "story", "change": "The lower shelf is no longer safe",
  "direction": "left to right; upper wall behind the pair", "characters": ["MOTHER", "KID"],
  "shots": [
    {"duration_s": 7, "camera": "high-oblique telephoto, slow pan",
     "cause": "A crack runs across the lower shelf", "action": "The kid edges toward the cracked step",
     "start_state": "Mother one body length ahead", "end_state": "Kid stops short of the crack",
     "beats": ["Wide: both animals and the drop readable", "Kid advances cautiously",
               "Mother plants her hooves and looks back", "Kid stops short; gap unresolved"],
     "hook_role": "obstacle", "intensity": 4, "spoiler": false},
    {"duration_s": 8, "camera": "medium side angle, locked",
     "cause": "Grit trickles from the crack", "action": "Mother steps back to block the kid",
     "start_state": "Kid at the crack", "end_state": "Mother between kid and crack"}
  ],
  "voice": [{"en": "...", "vi": "..."}]
}
```

Allowed hook roles: threat, vulnerability, pursuit, obstacle, unanswered, none. Intensity is 0–5. Omission of `spoiler:false` makes a shot ineligible for hook selection. Mark the actual resolution as a spoiler. Metadata is a candidate hint; `shot_qc.json` supplies actual visual approval and a clean hook source-in later.

`voice` is a list of `{en: "one English paragraph", vi: "full Vietnamese translation"}`. No newlines inside a block. Several blocks in the same scene remain adjacent physical lines in transcript; blank lines separate scenes. **Global nonblank physical-line order** maps to `1.mp3…N.mp3`. Do not use rendered Markdown paragraph count. The compiler schedules their starts inside each scene from estimated or measured durations. It never cuts the source audio.

The compiler stops at the first problem. Common ones and the cheap fix: `voice exceeds its picture window` → trim that scene's words or add a shot; `narrator gap` → add one short connected sentence to that scene; `Picture totals …` → adjust one shot's `duration_s` in the scene that is off; `Repeated body action` → make the two `action` strings describe distinct moments.

Default maximum inter-block/tail pause is 3s. A scene may set `pause_limit_s` up to 6 with an explicit `pause_reason`; use sparingly. A voice overflow is an error: shorten/re-record the affected approved block with the user, or revise that scene's shot budget in a new production version. Do not change picture durations after prompts have been issued.

After conform, `timestamp.md` uses exact frame-based millisecond onsets in `## English` and `## Vietnamese`; English equals transcript text exactly. SRT spans follow actual placed MP3 durations. Script math does not verify translation quality, factual accuracy, dramatic strength, internal silence or visual continuity; the agent must review them.
