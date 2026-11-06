# Cold open 00:00–00:12 (every footage+AI 1-3h film; user 2026-11-06)

Full-AI 8-15p has none: its 30 s hook starts at 0:00 (user 2026-11-06; `coldopen` stops on a full-AI folder).

| time | picture | sound |
|---|---|---|
| 0:00 -> hit (~0:01) | black | A9: a string riser into an impact (`D:\Audio_lib\SXF\impact`, one per film, never two films of one day project) |
| hit -> 0:12 | 3-6 cuts of **full-AI** clips (each generated 6-9 s, never library footage) of story 1's most tense moment | the intro music starts on the hit (A7), no narrator |
| 0:12 -> | the teaser to ~1:30 (narrator from 0:12.6) | the intro music ends with the intro |

The impact and the music are placed with the film (plan.py / place.py); V1 hit -> 0:12 stays black with a
blue `COLD OPEN` marker until its clips exist. The prompts come with the film's first `/doc-edit` run, in step D (next to the intro +
story 1 prompts).
Engine: `dvr_cowork/coldopen.py`. Films built before 2026-11-06 (narration 0:03.6) have none.

## Steps
1. **Pick the moment** from story 1 (brief.md, already in context): its most tense stretch — a stalk,
   the start of a hunt, a danger closing in (a cliff edge, a ring of wolves, a rising river). Never its outcome,
   never a kill or a rescue. Story 1 = intro end -> story 2. `kind`:
   the animal the moment is about is the prey -> `prey`, the hunter -> `predator`. Cast truth from the bible (sex /
   age / counts), the moment's place and light.
2. Write the spec with the Write tool (`.work/doc_edit/<key>/coldopen.json`):

       {"from": "02:20-02:45", "kind": "predator",
        "situation": "Báo tuyết rình đàn dê núi trên vách đá dựng đứng",
        "place": "a steep scree slope under a rock wall, patches of snow", "light": "neutral daylight, true-white snow",
        "shots": [
         {"role": "eye_closeup", "subject": "A single adult snow leopard", "camera": "extreme close-up, 200mm, eye level",
          "vec": "static", "clip_s": 8, "beats": ["its pale green eyes narrow and track left to right, whiskers twitching"]},
         {"role": "prey", "subject": "A herd of seven Himalayan ibex", "camera": "telephoto wide from above, slow push-in",
          "vec": "L>R", "clip_s": 8, "beats": ["the ibex pick their way across loose scree, a kid slips and scrambles back"]},
         {"role": "hunger_closeup", "subject": "A single adult snow leopard", "camera": "side close-up, 135mm",
          "vec": "static", "clip_s": 8, "beats": ["its lips draw back from long canines, breath steaming, head low"]},
         {"role": "situation", "subject": "A single adult snow leopard", "camera": "low tracking medium shot, grass parallax",
          "vec": "L>R", "clip_s": 8, "beats": ["it slinks forward along the ledge, belly low, tail tip flicking"]}]}

   `from` = the story-1 span it shows (`mm:ss-mm:ss` on the timeline; `prompts` checks it lies inside story 1).
   Grammar (`coldopen.validate`): shot 1 = an intense (extreme) close-up of the eye / face — prey `fear_closeup`
   (wide eyes, flared nostrils, ears swivelling), predator `eye_closeup` (the hard, sharp stare); shot 2 = prey
   `danger` (the threat it faces) / predator `prey` (the prey it watches); a predator also gets a `hunger_closeup`
   within the first 4 (teeth, drooling side face, a battle-hungry face); then `escalation` / `reaction` /
   `situation` that build, unresolved. Every animal keeps moving, no contact, no stare-down (shared gates); one
   species per clip; `clip_s` 6-9; optional `cut_in` (s into the clip, default 1.0) after viewing the clip.
3. `.venv/Scripts/python.exe -m dvr_cowork coldopen prompts "<video>"` -> `<video>\coldopen-prompt.csv` (shot_id
   C1..Cn); the user saves the clips as `<video>\coldopen\1.mp4 … n.mp4`. Reply: the moment in one line (story 1
   mm:ss), n prompts, the save folder.
4. Clips there (the user says so, or a later `/doc-edit <video>` finds them) -> `coldopen place "<video>"` (dry run:
   the cuts, ramping ~2.3 -> 3.3 s from the hit to 0:12 / 0:12.6), view 2-3 frames if a cut_in needs moving
   (`dvr_cowork frames`), then `--apply` (backup `Edit_bak_coldopen_*`, V1 only where empty, bin `8. Cold open`).
   Reply: backup, cuts, what to listen to (`nghe lại 0:00–0:02`: riser, hit, music entry).
