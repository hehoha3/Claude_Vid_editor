"""Match timestamp cues to Whisper words, then refine sentence boundaries on the audio itself.

Step 1  match_cues():  global token alignment (difflib) between the script lines and the
        Whisper transcript -> for every cue, the first/last transcript word that belongs to it.
Step 2  refine():      Whisper word times are only ~50-200 ms accurate, so each boundary is
        snapped to the real pause between the two sentences, found in the 10 ms energy
        envelope. Speech onset precision is ~10 ms.
"""
from __future__ import annotations

import difflib
import math
from collections import Counter

import numpy as np

from .textnorm import clean_cue_text, tokens

HOP = 0.01  # energy envelope resolution (s)


class AlignError(Exception):
    pass


# --------------------------------------------------------------------------- step 1
def match_cues(cues, words: list[dict]) -> list[dict]:
    s_tok: list[str] = []
    s_own: list[int] = []
    for ci, c in enumerate(cues):
        for t in tokens(clean_cue_text(c.text)):
            s_tok.append(t)
            s_own.append(ci)
    w_tok: list[str] = []
    w_idx: list[int] = []
    for wi, w in enumerate(words):
        for t in tokens(w["w"]):
            w_tok.append(t)
            w_idx.append(wi)

    n_tok = Counter(s_own)
    hits: list[list[int]] = [[] for _ in cues]
    if s_tok and w_tok:
        sm = difflib.SequenceMatcher(None, s_tok, w_tok, autojunk=False)
        for a, b, size in sm.get_matching_blocks():
            for k in range(size):
                hits[s_own[a + k]].append(w_idx[b + k])

    out: list[dict] = []
    for ci in range(len(cues)):
        nt = n_tok.get(ci, 0)
        h = sorted(hits[ci])
        rng = None
        conf = (len(h) / nt) if nt else 0.0
        if h:
            if h[-1] - h[0] > 2 * nt + 8:  # stray matches -> keep the densest cluster
                width = int(1.5 * nt + 5)
                best = (0, h[0], h[0])
                j = 0
                for i in range(len(h)):
                    while h[i] - h[j] > width:
                        j += 1
                    if i - j + 1 > best[0]:
                        best = (i - j + 1, h[j], h[i])
                rng = (best[1], best[2])
                conf = best[0] / nt if nt else 0.0
            else:
                rng = (h[0], h[-1])
        out.append({"rng": rng, "conf": min(conf, 1.0), "ntok": nt, "filled": False})

    # keep ranges strictly increasing
    last = -1
    for o in out:
        if o["rng"] and o["rng"][0] <= last:
            if o["rng"][1] <= last:
                o["rng"], o["conf"] = None, 0.0
            else:
                o["rng"] = (last + 1, o["rng"][1])
        if o["rng"]:
            last = o["rng"][1]

    # cues with no recognisable words: share the unclaimed transcript words between neighbours
    ci = 0
    while ci < len(out):
        if out[ci]["rng"] is not None:
            ci += 1
            continue
        cj = ci
        while cj < len(out) and out[cj]["rng"] is None:
            cj += 1
        prev = next((out[k]["rng"][1] for k in range(ci - 1, -1, -1) if out[k]["rng"]), -1)
        nxt = out[cj]["rng"][0] if cj < len(out) else len(words)
        lo, hi = prev + 1, nxt - 1
        group = list(range(ci, cj))
        avail = hi - lo + 1
        if avail >= len(group):
            total = sum(max(out[k]["ntok"], 1) for k in group)
            pos = lo
            for n, k in enumerate(group):
                if n == len(group) - 1:
                    end = hi
                else:
                    share = max(1, round(avail * max(out[k]["ntok"], 1) / total))
                    end = min(hi - (len(group) - 1 - n), pos + share - 1)
                out[k]["rng"] = (pos, end)
                out[k]["filled"] = True
                pos = end + 1
        ci = cj

    missing = [cues[i].index for i, o in enumerate(out) if o["rng"] is None]
    if missing:
        raise AlignError(
            "Could not find these lines in the audio (no words left to assign): "
            + ", ".join(f"#{m}" for m in missing)
            + ". Check that the audio and timestamp file belong together and are in the same order."
        )

    res = []
    for o in out:
        a, b = o["rng"]
        res.append({"start": float(words[a]["s"]), "end": float(words[b]["e"]),
                    "w0": a, "w1": b, "conf": round(o["conf"], 3), "filled": o["filled"]})
    return res


# --------------------------------------------------------------------------- step 2
def energy_db(samples: np.ndarray, sr: int = 16000, hop: float = HOP) -> np.ndarray:
    h = int(round(sr * hop))
    n = len(samples) // h
    if n == 0:
        return np.zeros(0)
    fr = samples[: n * h].astype(np.float64).reshape(n, h)
    return 10.0 * np.log10((fr * fr).mean(axis=1) + 1e-12)


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    m = np.concatenate(([0], mask.astype(np.int8), [0]))
    d = np.diff(m)
    return list(zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist()))


def _first_voiced(silent, t0, t1):
    i0, i1 = max(0, int(t0 / HOP)), min(len(silent), int(math.ceil(t1 / HOP)))
    idx = np.flatnonzero(~silent[i0:i1])
    return (i0 + idx[0]) * HOP if len(idx) else None


def _last_voiced(silent, t0, t1):
    i0, i1 = max(0, int(t0 / HOP)), min(len(silent), int(math.ceil(t1 / HOP)))
    idx = np.flatnonzero(~silent[i0:i1])
    return (i0 + idx[-1] + 1) * HOP if len(idx) else None


def refine(cues, matches: list[dict], samples: np.ndarray, acfg: dict, sr: int = 16000):
    db = energy_db(samples, sr)
    dur = len(samples) / sr
    if len(db) == 0:
        raise AlignError("audio is empty")
    speech_lvl = float(np.percentile(db, 90))
    floor = float(np.percentile(db, 5))
    thr = max(floor + 6.0, speech_lvl - float(acfg["silence_db_below_speech"]))
    silent = db < thr
    min_run = max(1, round(float(acfg["min_silence"]) / HOP))
    runs = [(s, e) for s, e in _runs(silent) if e - s >= min_run]

    n = len(matches)
    onset: list[float] = [0.0] * n
    offset: list[float] = [0.0] * n
    flags: list[list[str]] = [[] for _ in range(n)]

    s0 = matches[0]["start"]
    v = _first_voiced(silent, max(0.0, s0 - 1.5), min(dur, s0 + 0.3))
    onset[0] = v if v is not None else s0

    for i in range(n - 1):
        a_t, b_t = matches[i]["end"], matches[i + 1]["start"]
        lo = max(min(a_t, b_t) - 0.3, matches[i]["start"] + 0.05)
        hi = min(max(a_t, b_t) + 0.3, matches[i + 1]["end"] - 0.05)
        cands = [r for r in runs if r[1] * HOP > lo and r[0] * HOP < hi]
        if cands:
            r = max(cands, key=lambda r: r[1] - r[0])
            offset[i], onset[i + 1] = r[0] * HOP, r[1] * HOP
            if onset[i + 1] > b_t + 0.6 or offset[i] < a_t - 0.6:
                flags[i + 1].append("boundary_uncertain")
        else:
            mid = (a_t + b_t) / 2.0
            offset[i] = onset[i + 1] = mid
            flags[i + 1].append("no_pause")

    e_n = matches[-1]["end"]
    v = _last_voiced(silent, max(0.0, e_n - 0.3), min(dur, e_n + 1.5))
    offset[-1] = v if v is not None else e_n

    head, tail = float(acfg["head_pad"]), float(acfg["tail_pad"])
    min_conf = float(acfg["min_confidence"])
    segs = []
    for i in range(n):
        if i > 0:
            gap = max(0.0, onset[i] - offset[i - 1])
            h = min(head, gap * 0.45)
        else:
            h = min(head, onset[i])
        if i < n - 1:
            gap = max(0.0, onset[i + 1] - offset[i])
            t = min(tail, gap * 0.55)
        else:
            t = min(tail, max(0.0, dur - offset[i]))
        f = flags[i]
        if matches[i]["filled"]:
            f.append("text_not_heard")
        elif matches[i]["conf"] < min_conf:
            f.append("low_confidence")
        if offset[i] - onset[i] < 0.2:
            f.append("very_short")
        segs.append({
            "i": cues[i].index, "ts": cues[i].t, "text": cues[i].text,
            "onset": round(onset[i], 3), "offset": round(offset[i], 3),
            "src_in": round(onset[i] - h, 3), "src_out": round(offset[i] + t, 3),
            "conf": matches[i]["conf"], "flags": f,
        })
    stats = {"duration": round(dur, 3), "threshold_db": round(thr, 1),
             "speech_db": round(speech_lvl, 1), "pauses_found": len(runs)}
    return segs, stats
