"""Per-chat language preferences and localized UI strings."""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import threading

import config

logger = logging.getLogger(__name__)

SUPPORTED = ("en", "ru", "uz")

# Chat language choices persist to config.LANG_FILE so they survive restarts.
# _awaiting_selection is a transient mid-conversation flag and stays in memory.
_STORE_LOCK = threading.RLock()
_user_languages: dict[int, str] = {}
_awaiting_selection: set[int] = set()
_loaded = False


def _ensure_loaded() -> None:
    """Load saved language choices from disk on first access."""
    global _loaded
    with _STORE_LOCK:
        if _loaded:
            return
        try:
            with open(config.LANG_FILE, encoding="utf-8") as f:
                raw = json.load(f)
        except FileNotFoundError:
            raw = {}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read %s: %s", config.LANG_FILE, exc)
            raw = {}
        parsed: dict[int, str] = {}
        for key, value in raw.items():
            try:
                chat_id = int(key)
            except (TypeError, ValueError):
                continue
            if value in SUPPORTED:
                parsed[chat_id] = value
        _user_languages.clear()
        _user_languages.update(parsed)
        _loaded = True


def _save() -> None:
    """Persist language choices to disk atomically (write temp, then replace)."""
    with _STORE_LOCK:
        target = config.LANG_FILE
        directory = os.path.dirname(os.path.abspath(target)) or "."
        payload = {str(k): v for k, v in sorted(_user_languages.items())}
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".languages-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, target)
        except BaseException:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise


def reload_from_disk() -> None:
    """Discard in-memory state and reload from disk (used by tests)."""
    global _loaded
    with _STORE_LOCK:
        _loaded = False
        _awaiting_selection.clear()
        _ensure_loaded()


TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "choose_language": "Welcome! Which language do you want to use?",
        "welcome": (
            "Hey! I'm your salary assistant. Just tell me what you need — register workers, "
            "add bonuses or advances, calculate net salary, or check everyone's status. "
            "Voice or text, your choice!"
        ),
        "language_set": "Language set to English.",
        "reset": "Fresh start! What do you need?",
        "invalid_language": "Please choose a language using the buttons below, or type: English, Russian, or Uzbek.",
    },
    "ru": {
        "choose_language": "Добро пожаловать! На каком языке вы хотите общаться?",
        "welcome": (
            "Привет! Я помощник по зарплатам. Скажите, что нужно — зарегистрировать работника, "
            "добавить бонус или аванс, рассчитать зарплату или посмотреть список сотрудников. "
            "Текст или голос — как удобно!"
        ),
        "language_set": "Язык установлен: русский.",
        "reset": "Начнём сначала! Чем могу помочь?",
        "invalid_language": "Выберите язык кнопками ниже или напишите: English, Russian или Uzbek.",
    },
    "uz": {
        "choose_language": "Xush kelibsiz! Qaysi tilda gaplashmoqchisiz?",
        "welcome": (
            "Salom! Men maosh yordamchisiman. Nima kerakligini ayting — ishchi qo'shish, "
            "bonus yoki avans qo'shish, maoshni hisoblash yoki barcha ishchilarni ko'rish. "
            "Matn yoki ovoz — qulayingizga qarab!"
        ),
        "language_set": "Til o'zbekchaga o'rnatildi.",
        "reset": "Qaytadan boshlaymiz! Nima kerak?",
        "invalid_language": "Quyidagi tugmalardan tilni tanlang yoki yozing: English, Russian yoki Uzbek.",
    },
}

BUTTON_LABELS = {
    "en": "English",
    "ru": "Русский",
    "uz": "O'zbek",
}

LANGUAGE_ALIASES: dict[str, str] = {
    "en": "en",
    "english": "en",
    "ingliz": "en",
    "английский": "en",
    "ru": "ru",
    "russian": "ru",
    "русский": "ru",
    "rus": "ru",
    "uz": "uz",
    "uzbek": "uz",
    "o'zbek": "uz",
    "узбекский": "uz",
    "1": "en",
    "2": "ru",
    "3": "uz",
}


def get_language(chat_id: int) -> str | None:
    """Return saved language for chat, or None if not chosen yet."""
    _ensure_loaded()
    return _user_languages.get(chat_id)


def set_language(chat_id: int, language: str) -> None:
    """Save language choice and mark selection complete."""
    _ensure_loaded()
    with _STORE_LOCK:
        _user_languages[chat_id] = language if language in SUPPORTED else "en"
        _awaiting_selection.discard(chat_id)
        _save()


def clear_language(chat_id: int) -> None:
    """Remove saved language and selection state."""
    _ensure_loaded()
    with _STORE_LOCK:
        existed = _user_languages.pop(chat_id, None) is not None
        _awaiting_selection.discard(chat_id)
        if existed:
            _save()


def start_language_selection(chat_id: int) -> None:
    """Prompt user to pick a language on next interaction."""
    _ensure_loaded()
    with _STORE_LOCK:
        _awaiting_selection.add(chat_id)
        if _user_languages.pop(chat_id, None) is not None:
            _save()


def is_awaiting_language(chat_id: int) -> bool:
    """Return True if chat is waiting for language selection."""
    return chat_id in _awaiting_selection


def parse_language_choice(text: str) -> str | None:
    """Parse language from button callback or user text."""
    key = text.strip().lower()
    key = re.sub(r"\s+", " ", key)
    if key in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[key]
    if key in SUPPORTED:
        return key
    return None


def t(chat_id: int, key: str, *, lang: str | None = None) -> str:
    """Get localized string for chat or explicit language."""
    code = lang or get_language(chat_id) or "en"
    return TEXTS.get(code, TEXTS["en"]).get(key, TEXTS["en"][key])
