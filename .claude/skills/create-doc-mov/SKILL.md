---
name: create-doc-mov
description: "Write, upgrade or re-time the four files of a long-form (30–60+ min) Africa / Amazon / Congo wildlife documentary in D:\\Chann_*\\<video>\\audios — Film_Slug_Screenplay_EN.md, transcript.md (English narrator lines for Genmax, one line = one mp3), Film_Slug_Timestamp_EN_VI.md (full Vietnamese translation on the same onsets) and Film_Slug_Visual_Edit_Plan_EN.md (per-shot cut map). Use for /create-doc-mov, a new film concept or script (\"viết kịch bản phim mới\", \"tạo Screenplay / transcript / Timestamp / Visual_Edit_Plan\"), revising or production-upgrading those files (cut map, voice-free passages, intro second by second, footage MUST/ALT/PENDING), or conforming them to real 1.mp3…N.mp3 durations (\"căn lại timestamp theo mp3\"); after the user's review it voices transcript.md in Genmax (one line = one mp3, mp3.zip -> audios\\mp3) and runs /doc-edit on those videos. The only skill allowed to write narration. Not for doc-edit steps that only read these files (plan, place, fill, color)."
---

# create-doc-mov

Make a **cuttable film**: every second of the runtime has a planned shot, the transcript renders line by line in
Genmax, the Vietnamese runs on the same onsets, and the plan feeds doc-edit. Narration is otherwise forbidden in this
project (CLAUDE.md); the user made this skill the single exception (2026-10-30). Nothing else may change these files.

All four files are **generated** by `scripts/build_four_files.py` from one source file, so they cannot contradict each
other. Work only in the source; never hand-edit or even open the generated files (≈120 KB each) — the build prints
everything you need.

| What | Path |
| --- | --- |
| Source of truth (story, EN/VI lines, shots, pins) | `.work\doc_edit\<video>\four_files.src.md` |
| Four outputs (the only .md files there) | `D:\Chann_<n>_<name>\<video>\audios\` |
| Genmax audio (job D) | `…\audios\mp3.zip` + extracted `…\audios\mp3\1.mp3 … N.mp3`; worker state in `.work\doc_edit\<video>\genmax` → `durations.json` next to the source after conform |

Scripts (run with `.venv\Scripts\python.exe`, from the workspace root):
`build_four_files.py SRC OUT [--check | --report | --mp3 DIR | --selftest]`, `check_refs.py DOI… ["query"] [--abstract]`,
`new_video.py CHANN:TYPE… [--date DDMMYY] [--apply | --selftest]` and `genmax_audio.py AUDIOS [--profile P] [--go]`.

## Pick the job

**A. Conform to audio** ("có mp3 rồi", "căn lại timestamp"): no reading, no writing — run
`build_four_files.py <src> <audios> --mp3 <audios>\mp3`. It keeps the cut map and pinned onsets, re-times the rest,
rebuilds, re-runs the validator. If it stops on a block that no longer fits, split that line in the source (EN + VI)
or move its pin, rebuild. Report the PASS line and any onset that moved past its scene's hooks (`--report`).

**B. Revise / upgrade an existing film** (keep every line byte-identical unless the user asks): read
[production.md](references/production.md), `--report` for the timing table, edit the source with Edit, `--check`,
build. Prove the narration did not change: `cmp` old/new transcript.md and diff the timestamp text with onsets
stripped. A film without a source file: rebuild one from its transcript + timestamp first (scenes = blank-line groups).

**C. New film(s):** the user writes `/create-doc-mov Chann1 sẽ làm về <topic> trong khoảng 1h, Chann2 sẽ làm <topic>
trong khoảng 30p`. Per film take channel number, story type (`amazon` / `africa` / `congo`, from the topic) and
runtime in minutes (1h = 60, 30p = 30); ask if any is unclear. Name + create the folders in one call:
`scripts\new_video.py 1:amazon 2:africa` (dry run: `<type>_DDMMYY_<n>`, n = one daily index across all channels in
the order given), then the same with `--apply` (creates `<video>\audios` + `.work\doc_edit\<video>`, prints OK).
Set `target: <minutes>` in the source header. Several films = write them one after another, each through steps 1–6,
then one review stop (step 7) with a summary per film. For every film:
1. Read [storycraft.md](references/storycraft.md) and production.md. One central question, 3–5 stories that each
   answer a different part; Story 1 fastest, its first attack ~3–4 min in.
2. Research: `check_refs.py` every DOI (and `--abstract` when a sentence carries a number). Say only what the source
   supports; write each source's limit in SP_HEAD. No thoughts, kinship, kills or "deciding" without evidence.
3. Cast bible (male / female / young, markers, continuity limit, one-line metaphor).
4. Write the source: scenes, `EN || VI` lines, then the shot list of every scene, pins, `need:` MUST / ALT /
   PENDING, alternates (EN + VI) for uncertain outcomes. Draft lines first and use `--report` to see where the voice
   falls before writing shots; write `{{shot:…}}` placeholders instead of typed times.
5. `--check` until there are no ERRORs or WARNs, then build (the validator runs inside the build; it must PASS).
6. Organize: `<video>\audios` must hold exactly the four `.md` files (one glob per film). A copy that landed anywhere
   else (workspace, `.work`, another video) is moved in with Python `Path` and checked after; never overwrite one there.
7. **Review stop.** Reply per film with the short summary below — the user reviews the intro and Story 1 (user
   2026-10-30); the other stories get only their names — from the source you wrote, never by opening the generated
   files, then stop and wait. Changes the user asks for = job B (together with the user), rebuild,
   summary again. Only the user's "xong / ok / generate đi" starts job D, for exactly the films of this
   `/create-doc-mov` call (1 film → 1, 2 films → both; max 2).

   ```
   **<video>** · Chann_<n> · <type> · <target> min — <title>
   Intro 00:00–01:30: 2–3 lines (what is seen + the hook)
   Story 1 (mm:ss–mm:ss): 3–5 short beat lines (who, what happens, first attack at mm:ss, outcome)
   Sau đó: Story 2 <name> · Story 3 <name> · … · <lines> dòng (= mp3) · voice <x> % · MUST/PENDING: …
   File: [Screenplay](…) · [transcript](…) · [Timestamp](…) · [Visual_Edit_Plan](…)
   ```

**D. Voice + edit** (after the review stop, or the user names videos whose four files are done):
1. Preflight in one call: `genmax_audio.py <audios>` per film (free preview; voice Chann_1 = `mossbeard`,
   Chann_2 = `callum`, user 2026-10-30; other channel → ask). A `STOP` line → tell the user what is missing
   (`.claude\skills\genmax\config\contract.json`, voice IDs + Natural in `profiles.json`, key in keyring — see
   genmax `references/API_SETUP.md`; never ask for or read the key) and stop.
2. `genmax_audio.py <audios> --go` per film, Bash `run_in_background` (films in parallel, never poll). It sends one
   Genmax request per transcript line, capped at that transcript, then verifies, writes `mp3.zip` and extracts it to
   `audios\mp3`. It refuses if `mp3.zip` or `mp3\*.mp3` already exist. A `STOP` line = no retry: report it as printed
   (an `unknown` segment = the user checks Genmax history, then genmax `reconcile`). Denied → give the user the
   PowerShell command.
3. `OK` line → job A (conform the four files to the real mp3), PASS.
4. Invoke `/doc-edit <audios> <region>` with exactly those films' audios folders (2 films = one call, both folders),
   region = the folder prefix (`amazon` / `africa`; `congo` → ask). doc-edit's own rules then apply (it stops after
   the prompts, CLAUDE.md rule 11).

Finish every job with one line in `.work\knowledge\handoffs\current.md` and a short Vietnamese summary: file links,
line/word count, voice share, MUST / PENDING scenes, planned vs conformed.

## Channel conventions (the plans encode them)

- Genmax ≈ 150 wpm (measured). Channel films: 2,850–3,450 words / 60 min ≈ 35–40 % voice; the validator warns
  under 55 % — state the share, the cut map carries the rest. Only use timing-and-voice.md if the user wants another density.
- Intro 00:00–01:30: 00:00–00:15 gentle, slow shots of place and animal routine **under soft music** (the intro
  track, low, no drums); 00:15–01:15 the drum rises, cuts on the beat grid, action teasers at 136–150 % (first 5 and
  last 2 intro shots calm) using other frames than their story shots, no kill; 01:15–01:30 breath. Fade from black on
  the first shot, to black on the last intro shot, 0.6 s black slug, Story 1's first shot fades in. `/doc-edit intro`
  fits the real track later.
- Ending: last line ends by ~59:32; ~8 s silent final wide; 59:40–60:00 end-screen zone of moving shots, fade out.
- Other runtimes scale from the end: last line by target − 0:28 (`vend:`), end screen the last 20 s; words scale
  with minutes (30 min ≈ 1,425–1,725 words, 2–3 stories). Intro stays 00:00–01:30.
- Plan tracks: A2 narrator, A3/A4 ambience, A5 natural, A6 music, A7/A8 SFX (Resolve "Edit": A5→A6, A6→A7,
  A7/A8→A8/A9; A1 = AI clip audio −12 dB before 08:00).
- Screenplay beats `**NNN · mm:ss.s–mm:ss.s**` + `*Narrator:*` lines are what doc-edit `story.py brief` reads.

## Pitfalls

- Bash heredocs collapse `\\`: Windows paths in Python fix-ups go through the Write tool.
- No static or repeated shot to fill time; a voice-free stretch needs new action, sound or information.
- A footage gap is an editorial branch: change voice + VI + plans in the source before recording, never after.
