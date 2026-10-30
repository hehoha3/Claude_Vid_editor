# Timing and narrator planning

## First calculate a film budget

Set target seconds T, measured or estimated words per minute R, voice word count W, planned nonvoice holds H and transitions X. Estimate V = 60W/R and check T ≈ V + H + X. At 60:00 with R = 125:

| W | Approximate spoken duration | Picture/sound time left |
| --- | ---: | ---: |
| 3,000 | 24:00 | 36:00 |
| 4,500 | 36:00 | 24:00 |
| 6,000 | 48:00 | 12:00 |

These are estimates; punctuation and TTS speed change them. If the user wants restrained voice at roughly 50 words per finished minute, specify the ~35–36 minutes of natural-sound/picture-led scenes and enough distinct footage for them. Prefer 55–75% voiced runtime when there is no stronger user direction. Do not equate chapter end time with voice duration.

## Generate onsets

- Default first spoken onset = 0.6 s.
- For each voice block, assign start, approximate spoken duration and intended after-block hold. The next onset must be after the previous block ends.
- Use shorter intervals over a map, chase or urgent discovery when useful; use 6–15 second rests after reveal, failed strike or reversal; occasionally longer verified observational passages when the visual genuinely advances the story.
- Density must be variable. Never set identical gaps across a long film without examining the emotional beat.
- Avoid one timestamp holding an unmanageably long paragraph. Aim roughly 15–45 words per voice block, sometimes shorter for a key question. If the engine produces unexpectedly long audio, split the block and add a matching timestamp and VI line.
- Do not make precise delivery promises from word count alone.
- Set the visual end of each story independently from the last voice onset. The narrator may finish earlier, with meaningful environment/sound action carrying the remainder.

## Measure generated voice when possible

For the user's Genmax workflow, each nonblank transcript line maps in order to 1.mp3, 2.mp3, … N.mp3. Probe each duration, then lay it from the corresponding onset to onset + actual length. Revise the next onset if there is unintended overlap, or edit the voice block/hold if a boundary spills into the next story. Align to picture lock in DaVinci. The optional validator manifest is a JSON array of durations in transcript order, in seconds:

    [5.42, 7.61, 4.88]

Alternatively accept an object keyed by 1-based line numbers:

    {"1": 5.42, "2": 7.61, "3": 4.88}

The validator confirms one duration for every block and flags any overlap or final overflow. It cannot judge whether a hold is emotionally effective or the footage really exists.

## Chapter example

For a 60-minute film, an editorial option is 00:00–01:30 intro, 01:30–07:30 fast Story 1, 07:30–21:00 Story 2, 21:00–35:00 Story 3, 35:00–52:00 Story 4, 52:00–60:00 finale. This is a design example, never a fixed requirement. The first two stories may be faster when requested; later stories should develop different stakes, not replay the same chase with different animals.
