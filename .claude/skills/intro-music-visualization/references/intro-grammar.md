# Intro grammar (music visualization)

Condensed from `input/SKILL_documentary_intro_beat_editor.md` (full theory there; read it only when the user asks why).
Music builds the rhythm, the story picks the shot, the beat picks the moment. Never "every bass = a cut".

## No fixed format (user rule 2026-10-11)
Every intro is designed from ITS music and ITS footage. The two reference intros below are a palette of moves, not a
template: never copy their structure (shot - black - shot opening, burst before the drop, face close-up first...) by
default. Each section picks the move that fits what the music does there.
- The first frame matters most: an image from the start (on or right after the first hit), chosen with the sound to
  make an impression - a big world shot, a predator reveal, a strange detail - whatever answers the first sound.
- Shot placement answers the sound: the size of the visual change follows the size of the musical change.
- Palette move "cold open on the climax" (WILD JAVARÍ, user choice 2026-10-13: it lives here in "Open", never in
  "Edit"): show the film's peak danger (hero caught, predator mid-strike) without its outcome, so the question is
  planted in the first seconds; the answer stays for the film. Use it when the music's first hit or the drop can
  carry it, not by default.

## Brief (user)
45 s - ~2 min; tense music, often slow first 8-15 s; mostly predators (faces, eyes, stalking, attacks, runs),
other animals less; ends on a still shot (sky, an animal looking at the camera...).

## Reference intros (measured, not listened)
**amazon_1** (`D:\Job_vid\amazon_1\Done_EN.mov` 0:00-1:34; music `openning/sigmamusicart-cinematic-tense-trailer`, 110 BPM,
D minor, drop 44.69 s, one piece, whole track):
- 1.0 s, first hit: sunset over the river, wide, held 3.8 s (world first, then the cast).
- Build 4.8-35 s: one shot per bar (2.18 s), cuts on the beat (+-0.02 s), mostly one beat before the measured bar line
  (pickup cut; or the bar phase is off by one - choose by ear). Predator / prey alternation that SETS UP the payoff:
  jaguar face, jaguar walking the trail, tapir eye ECU, jaguar stalking, peccary herd, tarantula flash (0.46 s),
  vine snake, anaconda strike, capybaras, jaguar eyes ECU, eagle in the sky, snake in water.
- Pre-drop 35-44.7 s (music dips): ONE long hold of 8 s (peccaries walking toward camera on the trail), then a 1.4 s jaguar
  close-up just before the drop: tension by holding, not by cutting.
- Drop 44.67 s (on the hit): the jaguar ambushes the same peccary herd from the log - the payoff of the set-up.
- Climax 44.7-57 s: action shots of 2 bars (~4.3 s): tiger vs leopard, eagles fighting, jaguar leaping a rock. Big action
  held longer, not cut faster.
- 57-85 s: one bar per shot again, attacks mixed with stalking and reactions (monkeys, elephants with calf).
- 85.5-92 s: the biggest fight held 6.5 s (jaguar vs anaconda in the river) on the last loud section; 92 s final:
  green snake face ECU staring, on the last hit while the music fades out.

**demo_2 "open"** (56.6 s, `openning/stockaudios-...-empire-awakens`, ~140 BPM):
- Slow opening: one shot per slow hit with black between (eyes / faces); burst of 5 short shots (0.4-0.9 s) then 1.7 s
  black before the drop; body one shot per 2 bars (3.4 s) cut on the bar line (+-0.1 s); black where the music drops
  out; frog staring at camera, sunset held to the end.

## Palette of moves (pick per section, from what the music does)
| music does | possible moves |
|---|---|
| first hit / opening sound | big world wide; predator reveal; extreme detail (eye, teeth); never a weak or random shot |
| slow sparse hits | one shot per hit, held; shot-black-shot; a slow push / drift held across several hits |
| steady build | one shot per bar (or 2 bars), alternate hunter / hunted to set up a payoff; scale steps wide -> close |
| fill / riser into a drop | burst of short shots on the fill; or one long hold with rising tension; or black for the last beat(s) |
| drop / B5 | the payoff of the set-up (strike, ambush, reveal), hard cut exactly on the hit |
| pulse of equal kicks | cut every 4-8 beats on the strongest; action inside the shot rides the other kicks |
| loud climax | strongest action, often held longer (2 bars); or the densest cutting if the footage is short bursts |
| dip / break | hold, black, close-up of a waiting predator, a still |
| final hit / fade | still: a stare into the lens, a sky, a landscape; hold through the fade |

## Reading music_map.py
- `bars` = downbeats of a fitted beat grid (beats every 60/BPM s between them). Cuts on bar lines (or one beat early)
  read as "on the music" even where no hit is printed. Tempo confidence < 0.3 = free tempo: use the hits.
- `t` = loudness peak of a hit = cut point; `on` = first onset of the cluster.
- B5 = biggest hits -> reserve the best story moments; B4 = strong hits; B3 = optional; B1-B2 = no cut.
- `entry` = hit after >= 1 s of quiet (drop after a break); `exit` = hit followed by a fall-off (final hit).
- `breaks` = near silence; `arc` (dB vs median per s) -> sections: low = OPEN / BREATH, rising = BUILD, flat high =
  PULSE, highest = CLIMAX, falling = RELEASE. Labels are Claude's reading, never "listened".

## Choosing / shaping the music (music_pick.py)
- Prefer one whole track that fits the length (FITS) and has a slow 8-15 s opening.
- Too long: end on an exit hit inside the range (a final-drop-like hit followed by a fall-off), keep ~2 s after it for
  the ring-out; build fades the tail (END_FADE).
- Too short / no good shape: splice. Join on B's entry hit (a drop after a break), cut A right after one of its exit hits,
  so the cut hides inside the impact. Tempo within 4 % (or half / double) and compatible key (same, relative, fifth);
  key confidence < 0.5 (percussion only) = key does not matter. Max 3 pieces. Never splice in the middle of a melody
  phrase; listen-check the join ("nghe lại join ở 01:12").
- The pieces stay separate clips on A7 (no rendered / merged audio file); gains and fades are clip properties.

## Building the shot plan
1. Sections from the arc and bars, then hero reservation: B5 / drop times paired with the strongest visuals (strike,
   ambush, jaws, chase burst, reveal). The best shot never goes on an early weak beat.
2. Set-up -> payoff: show the hunted and the hunter before the drop, the clash on it. Never show the kill in full.
3. Density curve with contrast: somewhere the cutting must slow (hold, black, long take) so the climax lands.
4. Shot scale is a beat: ECU -> wide on a big hit; avoid 4 same-size shots in a row.
5. Screen direction holds inside a chase; eye-trace breaks only for a shock.
6. Readability: a busy wide needs >= 1.5 s, an eye ECU reads in 0.5 s, a flash insert >= 0.4 s.
7. Action sync beats a hard cut: set the source in so the lunge / splash / landing hits `t`
   (source in = action time in the clip - (t - shot in)).
8. Hard cuts only. No dissolves, flashes, glitches, whips unless the user asks.
9. Bar-by-bar cutting for > 3 shots turns into a metronome: cut some on the pickup hit one beat early (the user's
   amazon_1 habit), hold some for 2 bars, or accelerate on beats (2.0 -> 1.7 -> 0.9 -> 2.8 into a burst).
10. Pre-drop valley: scale closes in shot by shot (wide watcher -> face -> eye ECU), then a held breath (~2 beats of
   black or the eye) and the payoff on the drop. A motif (eyes) can open and close the intro.

## QC before reporting
- First frame is a strong image on or right after the first sound.
- Every B5 / drop has a hero visual; cut count well below hit count (no beat slideshow).
- At least one place where the cutting slows before the climax; the climax is stronger than the build.
- Predators dominate (~70 % of shots), other animals seasoning; no species above ~30 % of shots.
- Muted test: the picture alone reads as threat -> action -> question.
- Nothing outside the new timeline changed; every black has a reason in the blueprint.
