---
name: thumbnail
description: Finish a YouTube wildlife thumbnail from an image the user gives - 16:9 crop, bright vivid grade, headline + red line + channel logo - with headless PhotoCraft into D:\Thumbs\<stem>\ (layered PSD, clean PNG 3840x2160, final JPG 3840x2160). Use for /thumbnail, "làm thumbnail", "chỉnh ảnh thumbnail", "thêm chữ/logo vào thumbnail".
---

# Thumbnail finish

`/thumbnail <image> "<headline>" <logo>`: all three required; ask for a missing one (no default logo).
- Logo shorthand (user 2026-10-16): `avaN` (ava1, ava2, ...) = `D:\Thumbs\_channel_medias\avaN_gif.gif`, one per
  channel; file missing -> say so, ask. Every `avaN` run gets `--prefix channN_` (-> `chann1_thumb_7.psd` ...).
- `ava1+ava2[+avaN...]` (user 2026-10-20) = one run per logo, same image / headline / flags; runs after the first use
  the moved source `D:\Thumbs\<stem>\<stem>.<ext>`.
- Headline: always UPPERCASE (user 2026-10-16: pass `--text` upper-cased), otherwise exactly as typed, never
  "corrected"; a likely typo -> mention it, don't fix.

## Fast path: 1 command, 1 image look, ~15 s
1. Run directly (no preflight; the script checks files and stops with a clear error):

       .venv/Scripts/python.exe .claude/skills/thumbnail/scripts/thumb.py finish "<image>" --text "<headline>" --logo "<logo>"

   No other flags: the rest is the user's confirmed taste (2026-10-15): centred 16:9 crop -> 3840x2160, layout A, WB
   neutralises the R/B cast, BRIGHTNESS + VIBRANCE auto-target `references/look-ref.png` (bright daylight, vivid:
   p50 0.34 / sat 0.50) with one measured correction, Montserrat Black white text auto-sized, thin outline, light
   shadow, red line under the text, logo top-left. Headline block sits LOW: red line bottom 108 px (at 3840) above the
   frame edge = the left margin (`--bottom N` moves it; larger = higher).
   **Africa** (user 2026-10-22): file name with `_africa_` -> automatic golden-hour savannah ADN of the user's
   reference frame (bright luminous lime-gold grass, lifted shadows, warm light; target p50 0.58 / sat 0.59, NOT the
   old muddy olive soft/vivid looks). One look, one file per logo: auto WB keeps warmth, WARM Photo Filter warming85
   20, yellows +8, greens +10, gamma 1.3, curve 3, BG_DARKEN 0 (`AFRICA`, `AFRICA_TARGET` in thumb.py; `--warm`,
   `--yellow-sat`, `--green-sat`, `--gamma`, `--curve`, `--bg-ev` override).
2. JSON: `warnings` empty, `final_vs_target` close (within ~0.03 / 0.05).
3. Look at `<folder>\<final>` once. QC: who does what in 1 s; text / line / logo cover no face, mouth, claw or contact
   point; no halo or ugly cast; anatomy believable.
4. Reply in 3-4 lines: folder + file names, final_vs_target, one QC line. No stats dump, no extra images.

Step 2/3 fails -> ONE correction run (writes `_v2`, never overwrites), changing only the failing thing:
- text / line covers the action -> `--layout B` (left 30% rail, text top-left under the logo);
- centred crop cuts eyes / mouth / claws / coil -> `--crop x,y,w,h` (source px, 16:9);
- `headline overflows` -> `--size <smaller pt>`; `\n` in `--text` = line break;
- user wants another look: `--exposure EV`, `--vibrance N`, `--wb c,m,y`, `--yellow-sat`, `--stroke 0`, `--line none`,
  `--vignette` (see `thumb.py finish -h`).
Still wrong -> stop, say what is off; the user fixes it in the PSD.

## Output: `D:\Thumbs\<stem>\` (`--out-dir` changes the root)
- the source, MOVED in by the script (`D:\Thumbs\thumb_1.png` -> `D:\Thumbs\thumb_1\thumb_1.png`; user 2026-10-16, a
  copy until then); a different image under that name there -> the script stops;
- `<stem>.psd`: named layers (WB_NEUTRAL, BRIGHTNESS, CURVE_GLOBAL, HSL_YELLOW_GREEN, VIBRANCE, SUBJECT_POP,
  BG_DARKEN/BG_DESAT neutral, VIGNETTE, SAFE_GUIDE hidden, LOGO, HEADLINE, RED_LINE) for hand tweaks in PhotoCraft;
- `<stem>_clean.png` 3840x2160 without LOGO / HEADLINE / RED_LINE;
- `<stem>_final.jpg` 3840x2160 for YouTube (user 2026-10-21, was 1280x720). JPG on purpose (user 2026-10-15): quality
  90 -> 70 until under YouTube's 2 MB limit (`final_quality`, `final_mb` in the JSON). Never PNG unless asked;
- name taken -> `<stem>_v2`, `_v3`...

## Rules
- Never edit, overwrite or delete the source (moving it into its folder is the only exception); outputs are never
  overwritten.
- `D:\Thumbs\_done` and `_channel_medias` are the user's: read a file there only when the user names it (`avaN` names
  the logo).
- Grade / crop / text only: never add, remove or redraw animals. Broken anatomy -> tell the user, stop.
- photocraft-cli error -> report the printed error, stop; never rerun the same command unchanged.
- `references/visual-dna.md` (composition / anatomy notes) only when the user asks why a thumbnail is weak.
- Ideas / generation (Google Flow, ArtCraft): not built yet.
