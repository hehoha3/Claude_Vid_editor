---
name: create-doc-mov
description: "The only narration writer, two video types of any region (amazon / africa / himalaya): footage+AI 1-3h = the four files (Screenplay, transcript.md, Timestamp_EN_VI, Visual_Edit_Plan) of a 30–180 min wildlife film in <video>\\audios (write, upgrade, re-time to real 1..N.mp3, then voicing + /doc-edit); full-AI 8-15p = an 8–15 min full-AI survival film (story.json + four files, `dvr_cowork ai`, early climax and nonstop action). Use for /create-doc-mov, \"viết kịch bản phim mới\", \"video 8p núi tuyết\", \"tạo Screenplay / transcript / Timestamp\", \"căn lại timestamp theo mp3\", or a pasted wildlife YouTube link to adapt. Not for doc-edit steps that only read them."
---

# create-doc-mov

## Start of a new film: type -> trends -> 3 options -> changes? -> write (user 2026-11-04)

An existing source (`.production\story.json` = full-AI, `four_files.src.md` = footage+AI) is jobs A/B of its type: skip this.
0. **Channel list** (`/create-doc-mov chann1 chann2 chann3 …`, user 2026-11-05): one new film per named channel, no
   limit on channels or films (a channel named twice = two films; each extra film = its own `new_video.py` call / its
   own `next-video`). Step 1 for all films first (one question per film, AskUserQuestion holds 4: more films = more
   calls), then steps 2–4 + write + review stop film by film in the order given, each film fully separate.
1. **Type + region**: unless the user's words say it (`--type full-AI` / 8p / 8-15p / full AI, or `--type
   footage+AI` / 1h / 3h / 30+ min / footage; `--minutes N` = runtime; region amazon (jungle, Congo too) / africa
   (desert, savanna) / himalaya (snow, high mountains)), AskUserQuestion type + region once; never re-asked per phase.
   Any type goes with any region (user 2026-11-05); folder `<region>_DDMMYY_N`. Full-AI: `$E8 init --region` pins
   the profile (`video.project.json` + `.production/profile.lock.json`, full_ai_mountain v2: 8–15 min, default 10)
   before any authoring, and its `reminder` (amazon / africa: no prompt locks yet) goes to the user at once. Full-AI
   -> `references/full-ai.md` (`$E8` = `.venv/Scripts/python.exe -m dvr_cowork ai`, `$Y` = `... -m dvr_cowork youtube` there) for steps 2–4 and after; nothing after this section applies. Footage+AI
   -> everything below (himalaya: no footage roots yet, every slot will be THIẾU: say so).
2. **Trends, one parallel turn**, at most one vidIQ call (credit error -> one line, YouTube API alone; no retry):
   full-AI = `$E8 next-video Chann_N --region <r>` + `$Y trends Chann_N` + `vidiq_outliers` (the region's predator /
   prey, long-form); footage+AI = research-youtube `top_videos.py <amazon-wildlife|africa-wildlife>` + `vidiq_outliers` (region).
   Read only the digests; trends steer species pairing, setting, title angle — never copy a plot.
3. **Three options** (user 2026-11-04: 3 are enough), the strongest by trend evidence, each in a short text card
   with 1–2 trend proofs (title, views/day), then one AskUserQuestion (free text = own idea):
   - full-AI: 3 story ideas. Card: working title · archetype · cast (protagonist / antagonist, exact counts) · dual peril ·
     clock · chokepoint · 30 s highlight hook · 3–4 action passages one line each · runtime (8–11 min default).
   - footage+AI: 3 format (1) central-question ideas. Card: the question · story names · Story 1 idea (species, goal, first
     attack, action passages). 4th choice "Multi-story (Claude tự làm)": no card; if picked, Claude designs every
     story itself (format (2)), Story 1 always the most gripping (storycraft.md Story 1), and shows the plan in the
     step-4 question.
4. **Changes?** After the pick, always one AskUserQuestion with the chosen option's facts in the text (cast + counts,
   runtime, format / archetype): "Giữ nguyên, viết luôn" / "Đổi dàn nhân vật" / free text. This is the only question
   left (it is also the cast question); answer applied -> write the content + four .md files, no more asks.

Make a **cuttable film**: every second of the runtime has a planned shot, the transcript is voiced line by line (the user
records it), the Vietnamese runs on the same onsets, and the plan feeds doc-edit. Narration is otherwise forbidden in this
project (CLAUDE.md); the user made this skill the single exception (2026-10-30). Nothing else may change these files.

All four files are **generated** by `scripts/build_four_files.py` from one source file, so they cannot contradict each
other. Work only in the source; never hand-edit or even open the generated files (≈120 KB each) — the build prints
everything you need.

| What | Path |
| --- | --- |
| Source of truth (story, EN/VI lines, shots, pins) | `.work\doc_edit\<key>\four_files.src.md` (`<key>` = `<video>__Chann_N` when the name is in 2+ channels, else `<video>`; `dvr_cowork/videokey.py`) |
| Four outputs (the only .md files there) | `D:\Chann_<n>_<name>\<video>\audios\` |
| Narrator audio (the user's, job D) | `…\audios\mp3\1.mp3 … N.mp3` (one per transcript line) → `durations.json` next to the source after conform |

Scripts (run with `.venv\Scripts\python.exe`, from the workspace root):
`build_four_files.py SRC OUT [--check | --report | --mp3 DIR | --selftest]`, `check_refs.py DOI… ["query"] [--abstract]` and
`new_video.py CHANN:TYPE… [--date DDMMYY] [--apply | --selftest]`.

## Pick the job

**A. Conform to audio** ("có mp3 rồi", "căn lại timestamp"): no reading, no writing — run
`build_four_files.py <src> <audios> --mp3 <audios>\mp3`. It keeps the cut map and pinned onsets, re-times the rest,
rebuilds, re-runs the validator. If it stops on a block that no longer fits, split that line in the source (EN + VI)
or move its pin, rebuild. Report the PASS line and any onset that moved past its scene's hooks (`--report`).

**B. Revise / upgrade an existing film** (keep every line byte-identical unless the user asks): read
[production.md](references/production.md), `--report` for the timing table, edit the source with Edit (a rewritten
EN line: rewrite its VI yourself as in C 4b), `--check`, build. Prove the narration did not change: `cmp` old/new transcript.md and diff the timestamp text with onsets
stripped. A film without a source file: rebuild one from its transcript + timestamp first (scenes = blank-line groups).

**C. New film(s):** the user writes `/create-doc-mov Chann1 sẽ làm về <topic> trong khoảng 1h, Chann2 sẽ làm <topic>
trong khoảng 30p`. Per film take channel number, region (`amazon` / `africa` / `himalaya`, from the topic; Congo =
amazon) and runtime in minutes (1h = 60, 3h = 180, 30p = 30); ask if any is unclear. Name + create the folders in one call:
`scripts\new_video.py 1:africa 2:africa` (dry run: `<region>_DDMMYY_<n>`; one call = one day project, so every
channel of the call gets the same n, user 2026-11-02: `africa_051126_1` in Chann_1 and Chann_2; one film per channel
per call), then the same with `--apply` (creates `<video>\audios` + `.work\doc_edit\<key>`, prints OK; a name shared
by 2+ channels -> `<key>` = `<video>__Chann_N`, which doc-edit's `video_key` finds).
Set `target: <minutes>` in the source header. Several films = write them one after another, each through steps 1–6,
then one review stop (step 7) with a summary per film. For every film:
1. Read [storycraft.md](references/storycraft.md) and production.md. Format (user 2026-11-03; not given -> ask):
   **(1) central question** (3–5 stories, each answers a part) or **(2) multi-story** (3–5 stories, linked or not, each
   its own question + ending). Both: Story 1 = 8–15 min, fast action within its first 30 s, first attack by ~03:00;
   intro + Story 1 mostly strong motion shots; no slow motion in shot text (feeds AI prompts), animals always moving (storycraft.md "Motion").
2. Research: `check_refs.py` every DOI (and `--abstract` when a sentence carries a number). Say only what the source
   supports; write each source's limit in SP_HEAD. No thoughts, kinship, kills or "deciding" without evidence.
3. Cast bible (male / female / young, markers, continuity limit, one-line metaphor).
4. Write the source: scenes, `EN ||` lines (VI may stay empty while drafting, step 4b), then the shot list of every
   scene, pins, `need:` MUST / ALT / PENDING, alternates (EN; their VI by hand) for uncertain outcomes. Draft lines
   first and use `--report` to see where the voice falls before writing shots; write `{{shot:…}}` placeholders
   instead of typed times.
   4b. **Vietnamese by Claude** (user 2026-11-05: no Gemini, no translation script): once the EN lines are final,
   write every VI yourself, as the second field of each `>` line (`> EN || VI || weight || pin`; never touch EN,
   weight or pin). Fix one Vietnamese name per species + place of the BIBLE first (e.g. `spectacled caiman` = "cá sấu
   caiman kính") and use it on every line. Check: meaning complete, young = "con non / chim non" of the right animal,
   pronouns of the bible's sex, spelling and diacritics, the narrator's calm tone, every VI line carries a
   Vietnamese word (a bare place name like "Serengeti, Tanzania." fails the gate: "Đồng cỏ Serengeti, Tanzania.").
5. `--check` until there are no ERRORs or WARNs, then build (the validator runs inside the build; it must PASS).
6. Organize: `<video>\audios` must hold exactly the four `.md` files (one glob per film). A copy that landed anywhere
   else (workspace, `.work`, another video) is moved in with Python `Path` and checked after; never overwrite one there.
7. **Review stop.** Reply per film with the short summary below — the user reviews the intro and Story 1 (user
   2026-10-30); the other stories get only their names — from the source you wrote, never by opening the generated
   files, then stop and wait. Changes the user asks for = job B (together with the user), rebuild,
   summary again. The user then records the voice themselves; their "có mp3 rồi / voice xong" starts job D.

   ```
   **<video>** · Chann_<n> · <type> · <target> min — <title>
   Intro 00:00–01:30: 2–3 lines (what is seen + the hook)
   Story 1 (mm:ss–mm:ss): 3–5 short beat lines (who, what happens, first attack at mm:ss, outcome)
   Sau đó: Story 2 <name> · Story 3 <name> · … · <lines> dòng (= mp3) · voice <x> % · MUST/PENDING: …
   File: [Screenplay](…) · [transcript](…) · [Timestamp](…) · [Visual_Edit_Plan](…)
   ```

**D. Edit after voice** (the user recorded `audios\mp3\1.mp3 … N.mp3` themselves; Claude never generates voice):
1. Count check: N mp3 = nonblank lines of transcript.md; a mismatch -> tell the user which, stop.
2. Job A (conform the four files to the real mp3), PASS.
3. Invoke `/doc-edit <audios> <region>` with exactly those films' audios folders (2 films = one call, both folders),
   region = the folder prefix (`amazon` / `africa` / `himalaya`; an old `congo_*` = amazon). doc-edit's own rules then apply (it stops after
   the prompts, CLAUDE.md rule 11).

Finish every job with one line in `.work\knowledge\handoffs\current.md` and a short Vietnamese summary: file links,
line/word count, voice share, MUST / PENDING scenes, planned vs conformed.

## Channel conventions (the plans encode them)

- Narrator ≈ 150 wpm (measured). Channel films: 2,850–3,450 words / 60 min ≈ 35–40 % voice; the validator warns
  under 55 % — state the share, the cut map carries the rest. Only use timing-and-voice.md if the user wants another density.
- Intro 00:00–01:30: 00:00–00:15 gentle shots of place and animals moving in routine **under soft music** (the intro
  track, low, no drums); 00:15–01:15 the drum rises, cuts on the beat grid, action teasers at 136–150 % (first 5 and
  last 2 intro shots calm) using other frames than their story shots, no kill; 01:15–01:30 breath. Fade from black on
  the first shot, to black on the last intro shot, 0.6 s black slug, Story 1's first shot fades in. `/doc-edit intro`
  fits the real track later.
- Ending: last line ends by ~59:32; ~8 s silent final wide; 59:40–60:00 end-screen zone of moving shots, fade out.
- Other runtimes scale from the end: last line by target − 0:28 (`vend:`), end screen the last 20 s; words scale
  with minutes (30 min ≈ 1,425–1,725 words, 2–3 stories). Intro stays 00:00–01:30.
- Plan tracks: A2 narrator, A3/A4 ambience, A5 natural, A6 music, A7/A8 SFX (Resolve "Edit": A5→A6, A6→A7,
  A7/A8→A8/A9; A1 empty, user 2026-11-05).
- Screenplay beats `**NNN · mm:ss.s–mm:ss.s**` + `*Narrator:*` lines are what doc-edit `story.py brief` reads.

## Pitfalls

- Bash heredocs collapse `\\`: Windows paths in Python fix-ups go through the Write tool.
- No static or repeated shot to fill time; a voice-free stretch needs new action, sound or information.
- A footage gap is an editorial branch: change voice + VI + plans in the source before recording, never after.
