"""Application configuration loaded from .env."""

import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv

_BASE_DIR = Path(__file__).resolve().parent
load_dotenv(_BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
DB_FILE = str(_BASE_DIR / "salaries.json")
AUDIO_TMP_DIR = os.getenv("AUDIO_TMP_DIR", tempfile.gettempdir())
CONVERSATION_HISTORY_LIMIT = int(os.getenv("CONVERSATION_HISTORY_LIMIT", "10"))