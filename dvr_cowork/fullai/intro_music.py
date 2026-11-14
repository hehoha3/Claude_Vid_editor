"""Intro score (user 2026-11-05): one tense song cut into opening -> climax -> ending that tiles the hook exactly.
The film opens on the song's first sound, the middle is the song's loudest stretch, the hook ends on the song's own
ending. Every cut lands on the song's beat grid and crossfades over one beat (A7 / A8 alternate so the two sides
really overlap). The original licensed file is placed three times; no new file is made from it."""
from __future__ import annotations

import math
import subprocess

import numpy as np

from .core import Stop

SR, HOP = 22050, 512
FPS = SR / HOP  # analysis frames per second


def load(path):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def analyse(x):
    """(level dB per frame relative to the loudest, beat period s, beat phase s, low-band hit per frame).
    Low band = the FFT bins under ~150 Hz: kick, toms, bass."""
    n = len(x) // HOP
    if n < FPS * 4: raise Stop("Intro song is too short to analyse")
    fr = x[:n * HOP].reshape(n, HOP)
    rms = np.sqrt((fr ** 2).mean(1)) + 1e-9
    db = 20 * np.log10(rms / rms.max())
    mag = np.abs(np.fft.rfft(fr * np.hanning(HOP), axis=1))
    spec = np.log1p(mag)
    low = slice(1, max(2, int(150 / (SR / HOP)) + 1))
    hit = np.r_[0, np.maximum(np.diff(spec[:, low], axis=0), 0).sum(1)]  # a kick / tom / bass attack
    flux = np.r_[0, np.maximum(np.diff(spec, axis=0), 0).sum(1)]  # onset strength
    w = np.hanning(7); flux = np.convolve(flux, w / w.sum(), "same")  # a beat between two frames still correlates
    flux = flux - np.convolve(flux, np.ones(int(FPS)) / int(FPS), "same")  # drop the slow swell: only the pulses stay
    ac = lambda k: float(np.dot(flux[:-k], flux[k:])) / (n - k)
    lags = np.arange(int(FPS * 60 / 180), int(FPS * 60 / 60) + 1)  # 60-180 BPM
    score = np.array([ac(k) for k in lags])
    i = int(np.flatnonzero(score >= 0.7 * score.max())[0])  # shortest strong lag: the beat, not the bar (a bar lag is still on the grid)
    while i + 1 < len(score) and score[i + 1] > score[i]: i += 1  # climb to that peak
    k = float(lags[i])
    if 0 < i < len(score) - 1:  # parabolic peak between frames
        a, b, c = score[i - 1:i + 2]
        if a - 2 * b + c: k += 0.5 * (a - c) / (a - 2 * b + c)
    # refine over 16 beats (a frame is ~2 % of a beat); the window stays inside +-1/3 beat so it never jumps to 15 or 17
    m = min(16, max(1, int(n // (2 * k))))
    far = range(int(m * k - k / 3), int(m * k + k / 3) + 1)
    j = max(far, key=ac)
    a, b, c = ac(j - 1), ac(j), ac(j + 1)
    period = (j + (0.5 * (a - c) / (a - 2 * b + c) if a - 2 * b + c else 0)) / m
    grid = lambda p: flux[np.round(p + period * np.arange(int((n - 1 - p) / period) + 1)).astype(int)].mean()
    phase = max(np.arange(0, period, 0.25), key=grid)
    return db, period / FPS, phase / FPS, hit


def plan(path, total_s, open_s=8.0, end_s=9.0):
    """Three segments on the timeline (seconds from the hook start) for a total_s hook."""
    x = load(path)
    dur = len(x) / SR
    db, P, ph, hit = analyse(x)
    beat = lambda t: ph + round((t - ph) / P) * P
    s0 = np.flatnonzero(db > -40)[0] / FPS                # the song's first real sound
    dend = (np.flatnonzero(db > -50)[-1] + 1) / FPS       # where its own ending has decayed
    X = 1.0                                                # crossfade centred on the beat; long enough to be smooth
    e2 = beat(dend - end_s)                                # ending starts on a beat
    t1 = beat(s0 + open_s) - s0                            # opening hands over on a beat
    t2 = total_s - (dend - e2)
    t2 = t1 + math.ceil((t2 - t1) / P - 1e-9) * P          # whole beats: both cuts stay on the grid (tail trims <= 1 beat)
    span = t2 - t1
    if not (X < t1 and span > 2 * X and t2 + X / 2 < total_s and e2 - X / 2 > s0 + t1):
        raise Stop(f"Song ({dur:.0f}s, {60 / P:.0f} BPM) cannot give opening + climax + ending in {total_s:g}s; choose a longer song")
    # climax (user 2026-11-05): the whole-beat window whose kick / bass hits are strong on EVERY beat, not just loud.
    # Score = its weakest beats (10th percentile of the low-band hit per beat) x its mean hit; a sustained pad or
    # string swell adds nothing, a gap of a few weak beats costs the window.
    lo, hi = s0 + t1 + X, e2 - span - X
    starts = [b for b in np.arange(beat(lo), hi + 1e-9, P) if b >= lo]
    if not starts: raise Stop(f"Song ({dur:.0f}s) has no climax room between its opening and its ending; choose a longer song")
    on_beat = lambda t: float(hit[max(0, int(t * FPS) - 2):int(t * FPS) + 3].max(initial=0))  # +-2 frames around it
    ref = np.percentile([on_beat(t) for t in np.arange(ph, dur, P)], 90) or 1.0
    beats = lambda b: np.array([on_beat(t) for t in np.arange(b, b + span - 1e-9, P)]) / ref
    score = lambda b: float(np.percentile(beats(b), 10)) * float(beats(b).mean())
    b1 = max(starts, key=score)
    drive = float(np.mean(beats(b1) >= 0.5))  # share of the climax beats with a real kick / bass hit
    end_src = e2 + (total_s - t2)
    if end_src > dur + 1e-6: raise Stop("Song ending runs past the file; choose another song")
    return {"bpm": round(60 / P, 1), "crossfade_s": round(X, 3), "song_s": round(dur, 2),
            "climax_src_s": round(float(b1), 2), "climax_drive": round(drive, 2), "cuts_s": [round(float(t1), 3), round(float(t2), 3)],
            "segments": [
                {"label": "Music intro open", "track": 7, "start_s": 0.0, "end_s": t1 + X / 2,
                 "source_start_s": s0, "fade_in_s": 0.0, "fade_out_s": X},
                {"label": "Music intro climax", "track": 8, "start_s": t1 - X / 2, "end_s": t2 + X / 2,
                 "source_start_s": float(b1) - X / 2, "fade_in_s": X, "fade_out_s": X},
                {"label": "Music intro end", "track": 7, "start_s": t2 - X / 2, "end_s": float(total_s),
                 "source_start_s": e2 - X / 2, "fade_in_s": X, "fade_out_s": 0.5 if end_src < dend else 0.0},
            ]}
