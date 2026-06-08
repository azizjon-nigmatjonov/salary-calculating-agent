"""Whisper-based offline speech-to-text for Telegram voice messages."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import wave

import numpy as np
import whisper

import config

logger = logging.getLogger(__name__)

_model = None


def _get_ffmpeg_path() -> str:
    """Return ffmpeg executable path from PATH or bundled imageio-ffmpeg."""
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    raise RuntimeError(
        "ffmpeg is not installed or not on PATH. "
        "Run: pip install imageio-ffmpeg  (or install ffmpeg manually)."
    )


def _load_wav_as_float32(wav_path: str) -> np.ndarray:
    """Load WAV file as mono float32 numpy array for Whisper."""
    with wave.open(wav_path, "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        frames = wf.readframes(wf.getnframes())

    if sample_width == 2:
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    elif sample_width == 4:
        audio = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise RuntimeError(f"Unsupported WAV sample width: {sample_width}")

    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio


def _get_model():
    """Load Whisper model on first use."""
    global _model
    if _model is None:
        _model = whisper.load_model(config.WHISPER_MODEL)
    return _model


def transcribe_audio(ogg_path: str) -> str:
    """
    Transcribe an OGG audio file to text.

    Converts OGG to 16kHz mono WAV via ffmpeg, loads audio in Python
    (so Whisper does not need ffmpeg on PATH), transcribes with auto language detect.
    """
    ffmpeg = _get_ffmpeg_path()
    wav_path = ogg_path.rsplit(".", 1)[0] + ".wav"

    try:
        subprocess.run(
            [ffmpeg, "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", wav_path],
            check=True,
            capture_output=True,
        )
        audio = _load_wav_as_float32(wav_path)
        result = _get_model().transcribe(audio, fp16=False)
        text = result["text"].strip()
        if not text:
            raise RuntimeError("Could not understand the voice message. Please try again.")
        return text
    except subprocess.CalledProcessError as exc:
        logger.error("ffmpeg failed: %s", exc.stderr)
        raise RuntimeError("Failed to convert audio file.") from exc
    finally:
        for path in (ogg_path, wav_path):
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    logger.warning("Could not remove temp file: %s", path)
