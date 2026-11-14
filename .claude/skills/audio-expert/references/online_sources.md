# Online sources: Epidemic Sound + Suno (set up 2026-11-04)

Replaces `Z:\Unseen\Sound` (dropped 2026-11-04). Everything lands in `audio_lib` (config.toml `paths.audio_lib`,
default `D:\Audio_lib`), a scan-source audio root like Amazona `audio`: the doc-edit pools and this skill pick from
the LOCAL index. The MCPs are only for what the library lacks.

## Cost order (cheapest first, stop at the first that works)
1. Local library: `plan.py` / `index.py` already search it. `fetch.py --have` = counts per folder + ids, no MCP call.
2. Epidemic search + download: free with the subscription, but every search result costs tokens (~1.5 KB per
   recording incl. stems/cover URLs, ~0.6 KB per SFX). `first` <= 5, filters always, never re-search an id that
   `--have` lists.
3. Epidemic `EditRecording`: exact-length version (<= 300 s) of a track you already chose -> intro / a span that
   must end on a cue.
4. Suno `audio-create`: costs generation credits of the SHARED team account (`taikhoanteamtrung`): only when the user
   asked for a Suno track, or 1-3 fail; say the credits (`account-usage`) before generating.

## Shopping list = what doc-edit could not fill
`plan.py` prints `audio thieu (track kw: slots): {...}` and `species not in library`. Fetch exactly those cues:

| cue | tool | query |
|---|---|---|
| A7 music `<mood kw>` | SearchRecordings | term from the mood table, `vocals: false`, `duration: {min: 60000, max: 300000}`, first 5 |
| A6/A8/A9 species/foley `<species> <action>` | SearchSoundEffects | term `"<species> <call/roar/growl/footsteps>"`, first 5 |
| A3-A5 bed `<biome>` | SearchSoundEffects | term `"<savanna/rainforest/river> ambience"`, `duration: {min: 60000}`, first 5 |
| intro (0:00 -> story 1) | EditRecording of a picked track, or Suno | `targetDurationMs` = intro length; Suno: `instrumental`, `duration` |

Epidemic SFX catalog (tested 2026-11-04): HAS leopard, lion/lioness, vulture, howler monkey, toucan, chimpanzee,
tamarin/titi monkeys, hoof gallops (horse), splashes, savanna / rainforest / night / river / dry-grass-rustle beds.
HAS NONE (returns coyote, donkey, pig, cartoon laughs: never use): African wild dog, wildebeest, impala / antelope,
zebra, rhino, warthog, jackal, hyena, giraffe, ostrich, jaguar (puma only), macaw (cartoon parrot), fish eagle -> do
not search these again; report them missing (Z:\Unseen\SFX has hyena, zebra x1, buffalo, antelope x1).
Intro (A7 intro, `dest: intro`): `tribal drums african percussion intense epic` / `cinematic tense trailer
percussion build`; skip hits tagged "vocal presence" even with `vocals: false`.

Mood terms (tested 2026-11-04, good hits): DonDap_KichTinh `wildlife hunt chase epic drums` · RinhRap_NguyHiem
`predator stalking suspense dark tension` · EmDiu_ThuGian `nature documentary peaceful calm` · TrungTinh_Quansat
`nature documentary underscore observational` (weakest: skip corporate / nu jazz / beats hits) · BiAn_KhamPha
`mysterious exploration wonder discovery`. Skip tags that break a BBC wildlife film: corporate, happy, pop, jazz,
vocals, a foreign "world country" tag (japan...).

## Layout (folder = plan.py pool; words in the file name = what plan.py matches)
- `music/<DonDap_KichTinh|RinhRap_NguyHiem|EmDiu_ThuGian|TrungTinh_Quansat|BiAn_KhamPha>/` -> A7 (plan.py EN_WORDS
  maps these folder names to mood words)
- `intro/` -> intro.py candidates only (never the body pool)
- `Nature_sound/<species>/` -> A6, A8/A9 fallback, beds. STRICT tracks need EVERY cue keyword and the species (or kin)
  in the name: put them in `tags` ("lion call roar growl").
- `SXF/<riser|hit|whoosh>/` -> A8/A9 (index.py classifies by those words)
- `ambience_sound/<savanna|rainforest|night|river|wind_rustle>/` -> A3-A5 beds (>= 20 s, no water/bird/rain words
  unless the bed is about them); `wind_rustle` = the "xì xào" layer (dry grass, leaves, reeds)
- `Nature_sound/foley/` -> hooves / paws running, splashes (no species name: generic foley; a "cat"/"hoof" word limits
  it to that kin)

## Download (one Bash call per batch)
1. Epidemic `DownloadRecording {fileType: MP3, stemType: FULL}` / `DownloadSoundEffect {fileType: MP3}` /
   `DownloadRecordingEdit` -> signed URL (valid ~1 h). Suno `audio-download`: a song made by us costs 1 download
   credit (tested 2026-11-04: `requires_credit`, 6 left/month; `status: ok` only for songs already downloaded) -> ask
   the user, then `confirm: true`; never more than once a second (rate_limited). Several Epidemic calls in parallel.
2. Write `.work/audio_expert/fetch.jsonl`, one line per file:
   `{"source": "epidemic"|"suno", "id", "dest": "music/RinhRap_NguyHiem", "title", "author", "bpm", "tags", "url"}`
   (an Epidemic edit: `id` = the edit id, not the recording's, or the dedupe skips it).
3. `.venv/Scripts/python.exe .claude/skills/audio-expert/scripts/fetch.py --batch .work/audio_expert/fetch.jsonl`
   -> file + `<stem>.license.txt` (ledger.py / intro.py read it for audio_licenses.md); ids already there = skip.
4. `scan_source.py audio_lib` (doc-edit sees it) then `scripts/index.py` (audio-expert sees it).

## Suno (intro or a custom motif only)
`audio-create {instrumental: true, style, title, duration: <s>, lyrics: "[Intro: ...]\n[Build: ...]\n[Drop: ...]",
negative_style}` (structure tags in `lyrics` work with instrumental; no `description`, no Max Mode unless the user
names it) -> `audio-wait {ids, until: complete}` (~1-2 min) -> `audio-analysis` per take (free but ~8 KB: every beat
listed; read only `sections`, `labels`, `terms`, `bpm`; the 2nd take may say `processing`, call once more) -> pick the
take whose first section change is ~15-20 s (soft intro, drums after) -> user's ok for 1 download credit ->
`audio-download {confirm: true}` -> fetch.py with `dest: intro`. Each create = 2 takes; download only the one used.
Tested prompt 2026-11-04 ("Savanna War Drums Intro", 100 s, 107/105 BPM D minor): labels said techno 0.5 next to
epic/orchestral -> add "techno, electronic, synth" to `negative_style` next time.

## Rules
- Licenses: Epidemic = subscription; the YouTube channel MUST be whitelisted in the Epidemic account or Content ID
  claims the video. A claimed track -> its `[es-xxxxxxxx]` tag into `.work/library/audio_blocked.txt`.
- Never vocals; never stems unless the user asks (they cost the same calls for no gain here).
- `audio_lib` is on D:, Claude never deletes there (CLAUDE.md rule 5): an unwanted track -> audio_blocked.txt or give
  the user the path.
