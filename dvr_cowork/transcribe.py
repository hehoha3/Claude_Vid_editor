"""Audio decoding + word-level transcription (faster-whisper) with an on-disk cache."""
from __future__ import annotations

import hashlib
import json
import os
import time
import wave
from pathlib import Path

import numpy as np

from .config import models_dir

SR = 16000
CACHE_VERSION = "v1"


def load_audio(path: str | Path) -> np.ndarray:
    """Mono float32 @16 kHz for any format PyAV/FFmpeg reads (mp3, wav, m4a, flac...).

    Own decoder instead of faster_whisper.decode_audio: PyAV 19 removed an argument that
    faster-whisper 1.2.x passes, and this version works with PyAV 11..19+."""
    try:
        import av
    except ImportError:
        return _load_wav(path)
    resampler = av.AudioResampler(format="s16", layout="mono", rate=SR)
    chunks: list[np.ndarray] = []
    try:
        container = av.open(str(path))
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"cannot open audio file {path}: {e}") from e
    with container:
        if not container.streams.audio:
            raise ValueError(f"no audio stream in {path} - is this really the narration file?")
        stream = container.streams.audio[0]
        for frame in container.decode(stream):
            for f in resampler.resample(frame) or []:
                chunks.append(f.to_ndarray().reshape(-1))
        for f in resampler.resample(None) or []:
            chunks.append(f.to_ndarray().reshape(-1))
    if not chunks:
        raise ValueError(f"no audio decoded from {path}")
    return np.concatenate(chunks).astype(np.float32) / 32768.0


def _load_wav(path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        data = w.readframes(n)
    if sw == 2:
        x = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
    elif sw == 4:
        x = np.frombuffer(data, dtype="<i4").astype(np.float32) / 2147483648.0
    elif sw == 3:
        b = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        i = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        i = np.where(i & 0x800000, i - 0x1000000, i)
        x = i.astype(np.float32) / 8388608.0
    elif sw == 1:
        x = (np.frombuffer(data, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError(f"unsupported WAV sample width {sw}")
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if sr != SR:
        t_old = np.arange(len(x)) / sr
        t_new = np.arange(int(len(x) * SR / sr)) / SR
        x = np.interp(t_new, t_old, x).astype(np.float32)
    return x


def file_sha1(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def load_model(cfg: dict):
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError("faster-whisper is not installed. Run setup.ps1 first.") from e
    w = cfg["whisper"]
    kw = dict(device=w["device"], compute_type=w["compute_type"], download_root=str(models_dir(cfg)))
    if int(w.get("cpu_threads") or 0) > 0:
        kw["cpu_threads"] = int(w["cpu_threads"])
    return WhisperModel(w["model"], **kw)


def transcribe(audio_path: str | Path, cfg: dict, cache_dir: Path, log=print, samples=None) -> dict:
    w = cfg["whisper"]
    key_src = f"{file_sha1(audio_path)}|{w['model']}|{w['language']}|{CACHE_VERSION}"
    key = hashlib.sha1(key_src.encode()).hexdigest()[:16]
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / f"transcript_{key}.json"
    if cache.exists():
        log(f"transcript: cache hit ({cache.name})")
        return json.loads(cache.read_text(encoding="utf-8"))

    log(f"transcript: loading model {w['model']} ({w['device']}/{w['compute_type']})")
    model = load_model(cfg)
    t0 = time.time()
    if samples is None:
        samples = load_audio(audio_path)
    segments, info = model.transcribe(
        samples,  # decoded by us (16 kHz mono float32) -> independent of PyAV API changes
        language=(w.get("language") or None),
        word_timestamps=True,
        vad_filter=False,  # keep the real timeline; pauses are handled by our own energy analysis
        beam_size=int(w.get("beam_size", 5)),
        condition_on_previous_text=False,  # avoids repetition loops on long narration
    )
    words = []
    last = -10
    total = max(float(info.duration), 1e-6)
    for seg in segments:
        for wd in seg.words or []:
            words.append({"w": wd.word.strip(), "s": round(float(wd.start), 3),
                          "e": round(float(wd.end), 3), "p": round(float(wd.probability), 3)})
        pct = int(100 * seg.end / total)
        if pct >= last + 10:
            log(f"  transcribing... {min(pct, 100)}%")
            last = pct
    data = {"model": w["model"], "language": info.language, "duration": float(info.duration),
            "elapsed_s": round(time.time() - t0, 1), "words": words}
    cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    log(f"transcript: {len(words)} words in {data['elapsed_s']}s (cached)")
    return data
