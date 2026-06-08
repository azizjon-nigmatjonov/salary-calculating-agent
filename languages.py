"""Per-chat language preferences and localized UI strings."""

from __future__ import annotations

import re

SUPPORTED = ("en", "ru", "uz")

_user_languages: dict[int, str] = {}
_awaiting_selection: set[int] = set()

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
    return _user_languages.get(chat_id)


def set_language(chat_id: int, language: str) -> None:
    """Save language choice and mark selection complete."""
    _user_languages[chat_id] = language if language in SUPPORTED else "en"
    _awaiting_selection.discard(chat_id)


def clear_language(chat_id: int) -> None:
    """Remove saved language and selection state."""
    _user_languages.pop(chat_id, None)
    _awaiting_selection.discard(chat_id)


def start_language_selection(chat_id: int) -> None:
    """Prompt user to pick a language on next interaction."""
    _awaiting_selection.add(chat_id)
    _user_languages.pop(chat_id, None)


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
