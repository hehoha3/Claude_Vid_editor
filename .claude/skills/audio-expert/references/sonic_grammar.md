# Sonic grammar (a way to think, not a preset)

| state | intent | V1 placement |
|---|---|---|
| CALM | stable world | A3/A4 continuous, A5 light, music optional |
| DISCOVERY | new information | one sound is the attention point |
| WONDER | scale / beauty | room for the picture to breathe; music may lift |
| CURIOSITY | unclear what happens | one unusual detail, no big accent, no early reveal |
| SUSPICION | normal is broken | remove one familiar layer; grounded offscreen movement |
| TENSION | threat approaches | fewer layers, sparse unpredictable detail |
| DANGER | threat is clear | concrete natural cue, selective music, leave room for the event |
| PRE_ATTACK | waiting for the turn | stop music/SXF at a sensible point; keep a detail or minimal bed |
| ACTION | it happens | A6 follows movement; A7 optional; A8/A9 accent only the main beats |
| AFTERMATH | consequence lingers | music stops, residual movement and breath |
| RELEASE | tension drops | restore layers one by one; music not required |

Cue types
- Sync cue: visible source (step, impact, splash, wingbeat). Align the sound peak (plan.py `peak=`) with the beat; never
  slide it to dodge the narrator, flag the conflict instead.
- Flexible cue: offscreen movement, environment detail, state-change drop. May move into a narrator gap if the source and
  story order stay valid (plan.py does this within -6..+3 s).
- Narrator gaps (heuristic): ~2 s one natural cue, ~4 s an action can speak, ~8 s a small audio scene. A silence may be the
  right content. A2 item spans are speech windows; do not cut or move A2.

Selection filters before any score: wrong track, missing media, too short, wrong species, needs processing outside V1.
Rank by story function 30, emotion 25, environment 15, intensity 10, distance 5, rhythm 5, track fit 5, avoid accidental
repeats 5 (heuristic only, never a probability). Keep 2-3 candidates for important beats.
Do not loop music, risers or animal calls; loop only checked ambience.
