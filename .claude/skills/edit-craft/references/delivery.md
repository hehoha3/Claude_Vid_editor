# Delivery for YouTube (Deliver page)

## Video
- Frame rate: keep the timeline rate (24 or 23.976 for AI footage). Never change it at render.
- Resolution: rendering the master at 2160p (even from 1080p sources) makes YouTube encode with its
  higher-quality codecs, which usually looks better even for 1080p viewers. Upscale inside Resolve
  (Super Scale is Studio; otherwise standard scaling with grain added afterwards).
- Codec: H.264 or H.265 (MP4 or MOV). Quality over size: YouTube re-encodes everything.
  YouTube's recommended SDR upload bitrates are roughly 8 Mbps for 1080p and 35-45 Mbps for 2160p
  at 24-30 fps; uploading higher (e.g. 20-40 Mbps 1080p, 60-100 Mbps 2160p) is fine and safer for
  grain and foliage detail.
- Color: Rec.709 Gamma 2.4 output; data levels Auto (video). Keep color tags consistent
  (Rec.709 / Rec.709 / Rec.709) so players do not reinterpret the image.
- Grain and fine foliage are the hardest things for YouTube's encoder: higher upload bitrate and
  2160p help more than anything else.

## Audio
- AAC 320 kbps (or PCM in MOV), 48 kHz, stereo.
- Mix to about -14 LUFS integrated, true peak <= -1 dBTP (see audio-expert skill). YouTube turns
  louder uploads down; it does not turn quieter ones up.

## Before upload checklist
- Watch the full render once at 1x (not the timeline): flash frames, gaps, missing media,
  black frames between pieces, audio pops at VO piece edges.
- Check loudness of the rendered file, not just the timeline meter.
- Check on a phone and on a TV-sized screen if possible.
- Chapters: list the chapter start times (first at 00:00) for the YouTube description.
- Export a 1280x720+ thumbnail still from the grade (Gallery > export still) if needed.
