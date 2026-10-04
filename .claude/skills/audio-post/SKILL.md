---
name: audio-post
description: Audio post-production for narrated wildlife documentaries in DaVinci Resolve Fairlight - narrator voice chain (EQ, de-ess, compression), music editing and ducking under narration, sound effects and ambience design for animals and environments, track/bus layout, loudness targets for YouTube (LUFS, true peak), fixing clicks, gaps and harsh AI voices. Use for any question about sound, mix, levels, music, SFX, narration quality, or "why does the audio feel cheap/flat/too loud".
---

# Audio post

## Track and bus layout (matches the user's A4 = narration convention)
| track | content | bus |
|---|---|---|
| A1 | ambience beds (forest, river, wind) | AMB |
| A2 | sound effects / foley (calls, splashes, impacts, wing beats) | SFX |
| A3 | music | MUS |
| A4 | narration (vo-sync pieces) | VO |
All buses -> Main. Processing on buses keeps settings consistent across hundreds of clips.

## Loudness targets
- Main: about -14 LUFS integrated, true peak <= -1 dBTP (YouTube normalises louder content down;
  quieter content stays quiet, so do not deliver at -23).
- Narration level is the anchor: mix the VO first to sit around -16 to -14 LUFS short-term when
  alone, then build music/effects under it.
- Fairlight has a loudness meter in the meter panel; set the target in its options and measure the
  whole programme, then the rendered file.
- Final limiter on the Main bus: ceiling -1 dBTP, gain reduction only on rare peaks (<= 2-3 dB).

## Narrator chain (VO bus), starting points
1. High-pass 70-90 Hz (12-18 dB/oct): removes rumble without thinning a deep voice.
2. Subtractive EQ: if boxy, -2 to -4 dB around 250-400 Hz (narrow-ish Q); if harsh, small cut
   2.5-4 kHz.
3. Character EQ: "deep gravelly" narrator - low shelf/bell +1 to +2 dB around 100-180 Hz for weight,
   gentle presence +1 to +2 dB at 3-5 kHz for intelligibility over music.
4. De-esser 5-8 kHz: AI voices are often bright and sibilant; aim for 2-4 dB reduction on "s".
5. Compressor 2:1 to 3:1, medium attack (10-30 ms), release 80-150 ms, 3-6 dB gain reduction.
   ElevenLabs output is already processed and fairly consistent - use the lighter end.
6. Optional Dialogue Leveler / clip gain to even out individual lines.
Check the pieces vo-sync placed: if any edge clicks, add a 2-4 frame fade at that edge (the tool
keeps 0.10 s head and 0.25 s tail of room, so fades never touch the words).

## Music
- Edit music on bars/phrases (cut at downbeats, crossfade 5-20 frames). Use the music's own
  ending, not a fade-out, when possible; back-time the ending to land on the final image.
- Under narration the music typically sits ~10-15 dB below the voice; between lines it can rise.
  Automate (draw volume) for important moments, or duck with a compressor on the MUS bus keyed
  (sidechained) from the VO bus: fast attack, release 300-600 ms, ~6-10 dB reduction.
- EQ the music to make room: a gentle dip of 2-3 dB around 1-4 kHz on the MUS bus helps diction.
- Drop the music out entirely just before a strike/climax; silence + one effect is stronger than
  a louder cue. Bring music back for the aftermath.

## Effects and ambience (wildlife)
- AI clips have no usable sync sound: everything is designed. Build three layers per scene:
  ambience bed (continuous), specific effects (calls, footsteps, splashes), and low-end/weight for
  impacts (a sub layer, short and controlled).
- Ambience bed runs across cuts inside a location, crossfaded 1-2 s at location changes; it hides
  the visual joins between generated clips.
- Use the correct species where possible. Well-known trap: the "eagle scream" in films is usually
  a red-tailed hawk; harpy eagles and most large eagles sound quite different. Mismatched calls
  undermine authority with an informed audience.
- Perspective: distant animals = less high end, more reverb, lower level; close = full spectrum,
  dry. Match the shot size.
- Panning: follow the animal's screen position for moving effects; keep VO centered.
- Leave space: an effect peak should not land under a key narration word.

## Common problems -> fixes
| problem | fix |
|---|---|
| VO drowned in places | automate music down, or sidechain duck; check 1-4 kHz masking |
| mix feels flat | more ambience depth (reverb send on AMB), contrast between quiet and loud moments |
| loudness too low after limiter | raise VO and mix bus gain, not the limiter threshold alone |
| clicks at piece edges | 2-4 frame fades; check edges land in silence (vo-sync pads) |
| harsh AI voice | de-esser + small 3-4 kHz cut; avoid heavy compression |
| pumping music | slower release on the ducker, less reduction |

## Fairlight facts
- Each track and bus has EQ and Dynamics (compressor, expander/gate, limiter) built in; Fairlight
  FX and VST3 plugins can be inserted.
- Clip gain vs track fader: fix clip-to-clip level differences with clip gain, mix with faders.
- Voice Isolation (Studio) removes background noise from voice; not needed for clean TTS.
- Render audio check: measure the exported file's integrated loudness.
