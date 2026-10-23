"""End-to-end tests without Resolve or a Whisper model.

Synthetic narration (noise bursts shaped like speech, real pauses between sentences) +
a fake Whisper transcript with recognition errors and +-120 ms timing jitter + a mock
Resolve API. Run:  .venv/Scripts/python.exe -m tests.test_pipeline
"""
from __future__ import annotations

import os
import random
import sys
import tempfile
import time
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dvr_cowork.align import match_cues, refine  # noqa: E402
from dvr_cowork.config import load_config  # noqa: E402
from dvr_cowork.layout import layout  # noqa: E402
from dvr_cowork.resolve_ops import OpsError, OverlapError, apply_plan  # noqa: E402
from dvr_cowork.timestamps import TimestampError, parse_timestamp_file  # noqa: E402
from dvr_cowork.transcribe import load_audio  # noqa: E402
from dvr_cowork.vosync import clips_segments  # noqa: E402

SR = 16000
LINES = [
    "As the first light touches the canopy, the harpy eagle is already watching.",
    "Forty metres below, a troop of brown capuchins moves through the figs.",
    "They are clever, quick, and never alone.",
    "But one juvenile has drifted to the edge of the group.",
    "The eagle shifts its weight.",
    "In 1998, researchers recorded a single pair taking 3 sloths in one week.",
    "Silence.",
    "Then the strike comes from above, faster than any alarm call.",
    "The troop scatters, screaming, and the mothers pull their young close.",
    "This time, the canopy keeps its secret.",
]


def synth(seed=1):
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    t = 0.6
    chunks = [nrng.normal(0, 0.0003, int(SR * t))]  # near-silent lead-in
    truth = []
    for line in LINES:
        n_words = len(line.split())
        dur = 0.32 * n_words + rng.uniform(0.0, 0.3)
        n = int(SR * dur)
        tt = np.arange(n) / SR
        env = 0.55 + 0.45 * np.sin(2 * np.pi * 4.0 * tt) ** 2  # syllable rhythm
        burst = nrng.normal(0, 0.12, n) * env
        for k in range(1, n_words):  # short intra-sentence dips (< min pause for a sentence)
            c = int(n * k / n_words)
            burst[c:c + int(0.03 * SR)] *= 0.05
        truth.append((t, t + dur))
        chunks.append(burst)
        t += dur
        pause = rng.uniform(0.35, 0.8)
        chunks.append(nrng.normal(0, 0.0003, int(SR * pause)))
        t += pause
    audio = np.concatenate(chunks).astype(np.float32)
    return audio, truth


def fake_whisper(truth, seed=2):
    rng = random.Random(seed)
    words = []
    subs = {"metres": "meters", "1998,": "nineteen ninety-eight,", "3": "three", "juvenile": "juvenal"}
    for (s, e), line in zip(truth, LINES):
        toks = line.split()
        step = (e - s) / len(toks)
        for k, tok in enumerate(toks):
            if line == "Silence." and rng.random() < 1.0:
                tok = "Science."  # a line Whisper gets wrong entirely
            tok = subs.get(tok, tok)
            ws = s + k * step + rng.uniform(-0.12, 0.12)
            we = s + (k + 1) * step + rng.uniform(-0.12, 0.12)
            words.append({"w": tok, "s": round(max(0, ws), 3), "e": round(max(ws + 0.05, we), 3), "p": 0.9})
    words.insert(5, {"w": "uh", "s": words[4]["e"], "e": words[4]["e"] + 0.05, "p": 0.3})  # extra word
    return words


def write_wav(path, audio):
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def write_ts(path, stamps):
    with open(path, "w", encoding="utf-8") as f:
        f.write("# test narration\n")
        for t, line in zip(stamps, LINES):
            f.write(f"[{int(t // 60):02d}:{int(t % 60):02d}] {line}\n")


# ------------------------------------------------------------------ mock Resolve
class MPI:
    def __init__(self, path, fps="24.000"):
        self.props = {"File Path": path, "FPS": fps, "Audio Ch": "1", "Clip Name": os.path.basename(path)}

    def GetClipProperty(self, k=None):
        return self.props.get(k) if k else dict(self.props)


class TItem:
    def __init__(self, mpi, start, dur, left):
        self.mpi, self.start, self.dur, self.left, self.color = mpi, start, dur, left, None

    def GetStart(self): return self.start
    def GetEnd(self): return self.start + self.dur
    def GetDuration(self): return self.dur
    def GetLeftOffset(self): return self.left
    def GetMediaPoolItem(self): return self.mpi
    def SetClipColor(self, c): self.color = c; return True


class Folder:
    def __init__(self, name):
        self.name, self.subs, self.clips = name, [], []

    def GetName(self): return self.name
    def GetSubFolderList(self): return list(self.subs)
    def GetClipList(self): return list(self.clips)


class Timeline:
    def __init__(self, name, fps="24", start=86400, audio_tracks=2):
        self.name, self.fps, self.start = name, fps, start
        self.tracks = {"video": 1, "audio": audio_tracks, "subtitle": 0}
        self.items = {("audio", i): [] for i in range(1, 9)}
        self.markers = {}

    def GetName(self): return self.name
    def GetSetting(self, k=None): return {"timelineFrameRate": self.fps, "timelineResolutionWidth": "1920", "timelineResolutionHeight": "1080"}.get(k)
    def GetStartFrame(self): return self.start
    def GetEndFrame(self): return self.start + 24 * 600
    def GetTrackCount(self, kind): return self.tracks[kind]
    def GetTrackName(self, kind, i): return f"{kind[0].upper()}{i}"
    def AddTrack(self, kind, sub=None): self.tracks[kind] += 1; return True
    def GetItemListInTrack(self, kind, i): return list(self.items.get((kind, i), []))
    def DeleteClips(self, items, ripple=False):
        for k in self.items: self.items[k] = [x for x in self.items[k] if x not in items]
        return True
    def DuplicateTimeline(self, name): self.project.timelines.append(Timeline(name)); return self.project.timelines[-1]
    def GetMarkers(self): return dict(self.markers)
    def AddMarker(self, f, c, n, note, d, cd=""): self.markers[f] = {"color": c, "name": n, "note": note, "customData": cd}; return True
    def DeleteMarkerAtFrame(self, f): self.markers.pop(f, None); return True


class MediaPool:
    def __init__(self, project):
        self.project, self.root = project, Folder("Master")
        self.current = self.root

    def GetRootFolder(self): return self.root
    def AddSubFolder(self, parent, name): f = Folder(name); parent.subs.append(f); return f
    def SetCurrentFolder(self, f): self.current = f; return True
    def ImportMedia(self, paths):
        out = [MPI(p) for p in paths]
        self.current.clips += out
        self.project.imports += len(out)
        return out
    def AppendToTimeline(self, infos):
        tl = self.project.current
        out = []
        for i in infos:
            assert i["mediaType"] == 2
            assert tl.tracks["audio"] >= i["trackIndex"], "track must exist before append"
            dur = i["endFrame"] - i["startFrame"] + 1  # inclusive semantics
            new = TItem(i["mediaPoolItem"], i["recordFrame"], dur, i["startFrame"])
            for other in tl.items[("audio", i["trackIndex"])]:
                assert not (new.start < other.GetEnd() and other.start < new.GetEnd()), "overlap on track"
            tl.items[("audio", i["trackIndex"])].append(new)
            out.append(new)
        return out


class Project:
    def __init__(self):
        self.timelines = [Timeline("Assembly"), Timeline("Edit")]
        for t in self.timelines: t.project = self
        self.current = self.timelines[0]
        self.pool = MediaPool(self)
        self.imports = 0

    def GetName(self): return "BBS_test"
    def GetSetting(self, k=None): return "24"
    def GetTimelineCount(self): return len(self.timelines)
    def GetTimelineByIndex(self, i): return self.timelines[i - 1]
    def GetCurrentTimeline(self): return self.current
    def SetCurrentTimeline(self, t): self.current = t; return True
    def GetMediaPool(self): return self.pool


class PM:
    def __init__(self): self.project = Project()
    def GetCurrentProject(self): return self.project
    def SaveProject(self): return True


class FakeResolve:
    def __init__(self): self.pm = PM()
    def GetProjectManager(self): return self.pm
    def OpenPage(self, p): return True
    def GetVersionString(self): return "20.2 mock"


# ------------------------------------------------------------------ tests
def build(tmp, stamps, cfg):
    audio, truth = synth()
    wav = Path(tmp) / "vo.wav"
    write_wav(wav, audio)
    ts = Path(tmp) / "vo.txt"
    write_ts(ts, stamps)
    cues = parse_timestamp_file(ts)
    words = fake_whisper(truth)
    samples = load_audio(wav)
    matches = match_cues(cues, words)
    segs, stats = refine(cues, matches, samples, cfg["align"])
    plan = {"version": 1, "audio": str(wav), "timestamps": str(ts), "model": "fake",
            "stats": stats, "segments": segs}
    return plan, truth, cues


def test_boundaries_and_flags(cfg, tmp):
    stamps = [3 + 6 * k for k in range(len(LINES))]
    plan, truth, _ = build(tmp, stamps, cfg)
    errs_on = [abs(s["onset"] - t[0]) for s, t in zip(plan["segments"], truth)]
    errs_off = [abs(s["offset"] - t[1]) for s, t in zip(plan["segments"], truth)]
    print(f"  onset error  max {max(errs_on) * 1000:.0f} ms, mean {np.mean(errs_on) * 1000:.0f} ms")
    print(f"  offset error max {max(errs_off) * 1000:.0f} ms")
    assert max(errs_on) <= 0.03, errs_on
    assert max(errs_off) <= 0.06, errs_off
    sil = plan["segments"][6]
    assert set(sil["flags"]) & {"low_confidence", "text_not_heard"}, sil
    for a, b in zip(plan["segments"], plan["segments"][1:]):
        assert a["src_out"] <= b["src_in"] + 1e-9, "source ranges must not overlap"
    return plan, truth


def test_layout_onset_on_stamp(cfg, plan):
    items, conflicts = layout(plan["segments"], 24.0, 24.0, cfg["align"])
    assert not conflicts
    for it, s in zip(items, plan["segments"]):
        onset_rec = it["rec_f"] + (s["onset"] * 24 - it["src_in_f"])
        assert abs(onset_rec - s["ts"] * 24) <= 0.5 + 1e-9, (it["i"], onset_rec, s["ts"] * 24)
    print(f"  onset lands on its stamp within <=0.5 frame for all {len(items)} lines")


def test_2398_clock(cfg, plan):
    items_tc, _ = layout(plan["segments"], 23.976, 23.976, cfg["align"])
    a2 = dict(cfg["align"], timestamp_clock="realtime")
    items_rt, _ = layout(plan["segments"], 23.976, 23.976, a2)
    last_tc, last_rt = items_tc[-1], items_rt[-1]
    assert abs(last_tc["target_f"] - plan["segments"][-1]["ts"] * 24) <= 1
    assert last_tc["target_f"] > last_rt["target_f"]
    print(f"  23.976: timecode-clock vs realtime differ by {last_tc['target_f'] - last_rt['target_f']} f at {plan['segments'][-1]['ts']}s (expected)")


def test_overlap(cfg, tmp):
    stamps = [2 + 2 * k for k in range(len(LINES))]  # far too tight
    plan, _, _ = build(tmp, stamps, cfg)
    items, conflicts = layout(plan["segments"], 24.0, 24.0, cfg["align"], "abort")
    assert conflicts
    items, conflicts = layout(plan["segments"], 24.0, 24.0, cfg["align"], "push")
    assert not conflicts and any("pushed" in it["flags"] for it in items)
    for a, b in zip(items, items[1:]):
        assert a["rec_f"] + a["dur_f"] <= b["rec_f"] - cfg["align"]["guard_frames"]
    print(f"  abort -> {len(layout(plan['segments'], 24.0, 24.0, cfg['align'], 'abort')[1])} conflicts; push -> no overlap, "
          f"{sum('pushed' in it['flags'] for it in items)} lines pushed")
    return plan


def test_apply_mock(cfg, plan, tight_plan):
    vo = cfg["resolve"]["audio_track"]
    r = FakeResolve()
    proj = r.pm.project
    res = apply_plan(r, plan, cfg, log=lambda m: None)
    tl = proj.timelines[1]
    vo_items = tl.GetItemListInTrack("audio", vo)
    assert tl.GetTrackCount("audio") >= vo, "VO track should exist"
    assert proj.pool.root.subs[0].GetName() == "4. Audio" and proj.imports == 1
    assert [f.GetName() for f in proj.pool.root.subs[0].subs] == ["Narrator"]
    assert len(vo_items) == len(plan["segments"]) and res["placed"] == len(vo_items)
    assert all(ti.GetMediaPoolItem() is vo_items[0].GetMediaPoolItem() for ti in vo_items), "one source clip"
    assert res["max_start_dev"] == 0 and res["max_in_dev"] == 0
    assert res["backup"] and any(t.name == res["backup"] for t in proj.timelines)
    # re-run: no re-import, old pieces replaced, still no overlaps
    res2 = apply_plan(r, plan, cfg, log=lambda m: None, backup=False)
    assert proj.imports == 1 and res2["removed"] == len(vo_items)
    assert len(tl.GetItemListInTrack("audio", vo)) == len(plan["segments"])
    # foreign clip on the VO track -> refuse unless force_clear
    tl.items[("audio", vo)].append(TItem(MPI("C:/other.wav"), 86400 + 99999, 10, 0))
    try:
        apply_plan(r, plan, cfg, log=lambda m: None, backup=False)
        raise AssertionError("should refuse")
    except OpsError:
        pass
    apply_plan(r, plan, cfg, log=lambda m: None, backup=False, force_clear=True)
    # tight timestamps with push -> placed without overlap (mock asserts), pushed items coloured
    apply_plan(r, tight_plan, cfg, log=lambda m: None, backup=False, force_clear=True, markers=True)
    colored = [ti for ti in tl.GetItemListInTrack("audio", vo) if ti.color == cfg["align"]["color_pushed"]]
    assert colored and len(tl.markers) == len(tight_plan["segments"])
    try:
        apply_plan(r, tight_plan, cfg, log=lambda m: None, backup=False, force_clear=True, on_overlap="abort")
        raise AssertionError("should raise overlap")
    except OverlapError:
        pass
    # dry run changes nothing
    before = len(tl.GetItemListInTrack("audio", vo))
    apply_plan(r, plan, cfg, log=lambda m: None, dry_run=True, force_clear=True)
    assert len(tl.GetItemListInTrack("audio", vo)) == before
    print(f"  mock Resolve: bin+import+A{vo} ok, {res['placed']} items from 1 source clip, rerun idempotent, "
          f"guards ok, {len(colored)} pushed items coloured")


def test_clips_mode(cfg, tmp):
    """audios/mp3/1.wav ... one file per sentence: no Whisper, one A2 item per file, onset on its stamp."""
    audio, truth = synth()
    d = Path(tmp) / "mp3"
    d.mkdir()
    for k, (s, e) in enumerate(truth, 1):  # each sentence with 0.2 s of near-silence around it
        write_wav(d / f"{k}.wav", audio[int((s - 0.2) * SR):int((e + 0.2) * SR)])
    ts = Path(tmp) / "ts.txt"
    write_ts(ts, [3 + 6 * k for k in range(len(LINES))])
    cues = parse_timestamp_file(ts)
    segs, _ = clips_segments(str(d), cues, cfg["align"])
    assert all(abs(s["onset"] - 0.2) <= 0.03 for s in segs), [s["onset"] for s in segs]
    plan = {"audio": str(d), "timestamps": str(ts), "segments": segs}
    r = FakeResolve()
    res = apply_plan(r, plan, cfg, log=lambda m: None)
    proj = r.pm.project
    vo_items = proj.timelines[1].GetItemListInTrack("audio", cfg["resolve"]["audio_track"])
    assert res["placed"] == len(LINES) == proj.imports == len({id(ti.GetMediaPoolItem()) for ti in vo_items})
    assert proj.pool.root.subs[0].subs[0].GetName() == "Narrator" and res["max_start_dev"] == 0
    (d / "3.wav").unlink()
    try:
        clips_segments(str(d), cues, cfg["align"])
        raise AssertionError("should refuse a missing sentence file")
    except ValueError as e:
        assert "missing [3]" in str(e)
    print(f"  per-sentence files: {len(LINES)} files -> {res['placed']} A2 items, own source each, bin 4. Audio/Narrator")


def test_timestamp_errors(tmp):
    p = Path(tmp) / "bad.txt"
    p.write_text("[00:10] a\n[00:09] b\nno stamp here\n[00:75] c\n", encoding="utf-8")
    try:
        parse_timestamp_file(p)
        raise AssertionError
    except TimestampError as e:
        assert "not after" in str(e) and ">= 60" in str(e)
    p.write_text("\ufeff[01:02.5] \u201cQuoted line\u201d\n  wrapped continuation\n[1:05:00] later\n", encoding="utf-8")
    cues = parse_timestamp_file(p)
    assert cues[0].t == 62.5 and cues[0].text == "Quoted line wrapped continuation" and cues[1].t == 3900
    p.write_text("## English\n[00:01] one\n[00:05] two\n## Vietnamese\n[00:01] mot\n[00:05] hai\n", encoding="utf-8")
    assert [c.text for c in parse_timestamp_file(p)] == ["one", "two"]
    assert [c.text for c in parse_timestamp_file(p, "vietnamese")] == ["mot", "hai"]
    # africa_1 layout: English cues before any heading, Vietnamese as `###### 001 · [mm:ss] text`
    p.write_text("# Title\n[00:01] one\n[00:05] two\n## Vietnamese\n###### 001 · [00:01] mot\n"
                 "###### 002 · [00:05] hai\n", encoding="utf-8")
    assert [c.text for c in parse_timestamp_file(p)] == ["one", "two"]
    assert [c.text for c in parse_timestamp_file(p, "vietnamese")] == ["mot", "hai"]
    print("  timestamp parser: errors reported with line numbers, BOM/quotes/wrapping/hh:mm:ss/EN+VI sections ok")


def test_scale():
    rng = random.Random(5)
    vocab = [f"w{i}" for i in range(400)] + ["the", "a", "of", "and", "to"] * 40

    class C:
        def __init__(self, i, text): self.index, self.t, self.text = i, i * 5.0, text
    cues, words, t = [], [], 0.0
    for i in range(700):  # ~40 min narration
        toks = [rng.choice(vocab) for _ in range(rng.randint(5, 14))]
        cues.append(C(i + 1, " ".join(toks)))
        for tok in toks:
            if rng.random() < 0.07:
                tok = "zz"  # recognition error
            words.append({"w": tok, "s": t, "e": t + 0.3})
            t += 0.33
        t += 0.5
    t0 = time.time()
    m = match_cues(cues, words)
    dt = time.time() - t0
    assert len(m) == 700 and all(a["w1"] < b["w0"] for a, b in zip(m, m[1:]))
    print(f"  700 lines / {len(words)} words matched in {dt:.2f}s")


def main():
    cfg = load_config()
    with tempfile.TemporaryDirectory() as tmp:
        print("boundaries + flags");   plan, _ = test_boundaries_and_flags(cfg, tmp)
        print("layout");               test_layout_onset_on_stamp(cfg, plan)
        print("23.976 clock");         test_2398_clock(cfg, plan)
        with tempfile.TemporaryDirectory() as tmp2:
            print("overlap");          tight = test_overlap(cfg, tmp2)
            print("apply (mock)");     test_apply_mock(cfg, plan, tight)
        with tempfile.TemporaryDirectory() as tmp3:
            print("per-sentence files"); test_clips_mode(cfg, tmp3)
        print("timestamp parser");     test_timestamp_errors(tmp)
        print("scale");                test_scale()
    print("\nALL TESTS PASSED")


if __name__ == "__main__":
    main()
