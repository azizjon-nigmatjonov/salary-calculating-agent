"""Whisper-based offline speech-to-text for Telegram voice messages."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess

import whisper

import config

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    """Load Whisper model on first use."""
    global _model
    if _model is None:
        _model = whisper.load_model(config.WHISPER_MODEL)
    return _model


def transcribe_audio(ogg_path: str) -> str:
    """
    Transcribe an OGG audio file to text.

    Converts OGG to WAV via ffmpeg, transcribes with Whisper (auto language detect),
    cleans up temp files, and returns stripped text.
    """
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg is not installed or not on PATH. "
            "Install ffmpeg and try again."
        )

    wav_path = ogg_path.rsplit(".", 1)[0] + ".wav"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", ogg_path, wav_path],
            check=True,
            capture_output=True,
        )
        result = _get_model().transcribe(wav_path)
        return result["text"].strip()
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
