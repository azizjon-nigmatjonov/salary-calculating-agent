"""Multi-step worker registration wizard."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import amount_parse
import date_parse
import languages
import text_match
import tools

STEPS = ("full_name", "birthdate", "job_started_date", "fixed_salary")

# Uzbek apostrophe variants: ' ʻ ʼ ` (voice/text may differ)
_UZ_QOSH = r"q[o''ʻʼ`´]sh"

START_PATTERNS = re.compile(
    r"(?i)((add|and)\s+(a\s+)?new\s+worker|a\s+new\s+worker|register\s+(a\s+)?(new\s+)?worker|"
    r"\bnew\s+worker\b|new\s+employee|add\s+employee|"
    rf"yangi\s+ishchi(?:\s+{_UZ_QOSH})?|ishchi\s+{_UZ_QOSH}|yangi\s+ishchi\s+qosh|"
    r"добав(ить|ь)\s+работника|новый\s+работник|ro'yxatdan\s+o'tkaz)",
)

_VOICE_FIXES = (
    (re.compile(r"(?i)^and\s+a\s+new\s+worker"), "add a new worker"),
    (re.compile(r"(?i)^and\s+new\s+worker"), "add a new worker"),
    (re.compile(r"(?i)^a\s+new\s+worker"), "add a new worker"),
    (re.compile(r"(?i)^new\s+worker\.?$"), "add a new worker"),
)

PROMPTS: dict[str, dict[str, str]] = {
    "en": {
        "full_name": "What's the worker's full name?",
        "birthdate": "How old are they, or what's their birthdate? (e.g. 22 or 1990-05-15)",
        "job_started_date": "When did they start the job? (e.g. 2024-03-01 or today)",
        "fixed_salary": "What's their monthly fixed salary? (e.g. 5 million or 5000000)",
        "cancelled": "Registration cancelled.",
        "success_prefix": "Done!",
        "invalid_birthdate": "Please enter a valid age (16–100) or birthdate (YYYY-MM-DD).",
        "invalid_date": "Please enter a valid date (YYYY-MM-DD) or say 'today'.",
        "invalid_salary": "Please enter a valid salary amount (e.g. 5000000, 5 mln, or six million).",
        "invalid_name": "Please enter the worker's full name.",
    },
    "ru": {
        "full_name": "Как зовут работника (полное имя)?",
        "birthdate": "Сколько ему/ей лет или дата рождения? (напр. 22 или 1990-05-15)",
        "job_started_date": "Когда начал(а) работать? (напр. 2024-03-01 или сегодня)",
        "fixed_salary": "Какая фиксированная месячная зарплата? (напр. 5 млн или 5000000)",
        "cancelled": "Регистрация отменена.",
        "success_prefix": "Готово!",
        "invalid_birthdate": "Введите возраст (16–100) или дату рождения (ГГГГ-ММ-ДД).",
        "invalid_date": "Введите дату (ГГГГ-ММ-ДД) или напишите 'сегодня'.",
        "invalid_salary": "Введите сумму зарплаты (напр. 5000000, 5 млн или шесть миллионов).",
        "invalid_name": "Введите полное имя работника.",
    },
    "uz": {
        "full_name": "Ishchining to'liq ismi nima?",
        "birthdate": "Yoshi nechada yoki tug'ilgan sanasi? (masalan, 22 yoki 1990-05-15)",
        "job_started_date": "Ishni qachon boshlagan? (masalan, 2024-03-01 yoki bugun)",
        "fixed_salary": "Oylik maoshi qancha? (masalan, 5 mln yoki 5000000)",
        "cancelled": "Ro'yxatdan o'tkazish bekor qilindi.",
        "success_prefix": "Tayyor!",
        "invalid_birthdate": "Yosh (16–100) yoki tug'ilgan sana (YYYY-MM-DD) kiriting.",
        "invalid_date": "Sana (YYYY-MM-DD) kiriting yoki 'bugun' deb yozing.",
        "invalid_salary": "Maosh miqdorini kiriting (masalan, 5000000, 5 mln yoki olti million).",
        "invalid_name": "Ishchining to'liq ismini kiriting.",
    },
}

CANCEL_WORDS = re.compile(
    r"(?i)^(cancel|stop|bekor|отмена|отменить|yo'q|йўқ|no)$"
)

_sessions: dict[int, RegistrationSession] = {}


@dataclass
class RegistrationSession:
    """In-progress worker registration for a chat."""

    step: str = "full_name"
    data: dict[str, Any] = field(default_factory=dict)
    language: str = "en"


def _lang(language: str | None) -> str:
    """Normalize language code to supported prompt set."""
    if language in ("ru", "uz"):
        return language
    return "en"


def _prompt(session: RegistrationSession, key: str) -> str:
    """Get localized prompt text."""
    return PROMPTS[_lang(session.language)].get(key, PROMPTS["en"][key])


def has_session(chat_id: int) -> bool:
    """Return True if chat has an active registration wizard."""
    return chat_id in _sessions


def clear_session(chat_id: int) -> None:
    """Cancel and remove registration wizard for chat."""
    _sessions.pop(chat_id, None)


def detect_language(text: str) -> str:
    """Rough language detection from user text."""
    lower = text.lower()
    if re.search(r"[а-яё]", lower):
        return "ru"
    if re.search(r"['ʻʼ]", lower) or any(
        w in lower for w in ("qo'sh", "ishchi", "maosh", "mln", "ming", "bugun")
    ):
        return "uz"
    return "en"


def normalize_user_text(text: str) -> str:
    """Fix common speech-to-text misheard phrases before command matching."""
    normalized = text_match.normalize_typos(text.strip().rstrip(".,!?"))
    for pattern, replacement in _VOICE_FIXES:
        if pattern.search(normalized):
            return pattern.sub(replacement, normalized)
    return normalized


def wants_to_start(text: str) -> bool:
    """Return True if user wants to begin registering a new worker."""
    normalized = normalize_user_text(text)
    if START_PATTERNS.search(normalized):
        return True
    return text_match.fuzzy_match_phrase(normalized, text_match.REGISTER_PHRASES) is not None


def parse_salary(text: str) -> float | None:
    """Parse salary from digits or spoken numbers (e.g. six million, 5 mln)."""
    return amount_parse.parse_amount(text)


def parse_birthdate(text: str) -> str | None:
    """Parse birthdate from YYYY-MM-DD or age."""
    text = text.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text
    natural = date_parse.extract_date_from_text(text)
    if natural:
        return natural
    age_match = re.search(r"\b(\d{1,3})\b", text)
    if age_match:
        age = int(age_match.group(1))
        if 16 <= age <= 100:
            year = datetime.now().year - age
            return f"{year}-01-01"
    return None


def parse_date(text: str) -> str | None:
    """Parse job start date from YYYY-MM-DD or 'today' variants."""
    text = text.strip().lower()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text
    if text in ("today", "bugun", "сегодня", "hozir"):
        return datetime.now().strftime("%Y-%m-%d")
    return date_parse.extract_date_from_text(text)


def _next_step(current: str) -> str | None:
    """Return next wizard step or None if done."""
    try:
        idx = STEPS.index(current)
        return STEPS[idx + 1] if idx + 1 < len(STEPS) else None
    except ValueError:
        return STEPS[0]


def start_session(
    chat_id: int,
    language: str = "en",
    prefilled: dict[str, Any] | None = None,
) -> str:
    """Start registration wizard and return first question."""
    session = RegistrationSession(language=_lang(language))
    if prefilled:
        session.data.update({k: v for k, v in prefilled.items() if v is not None})
    for step in STEPS:
        if step not in session.data or session.data[step] is None:
            session.step = step
            break
    else:
        return _complete(chat_id, session)
    _sessions[chat_id] = session
    return _prompt(session, session.step)


def _complete(chat_id: int, session: RegistrationSession) -> str:
    """Register worker and end wizard."""
    result = tools.tool_register_worker(
        session.data["full_name"],
        session.data["job_started_date"],
        session.data["birthdate"],
        float(session.data["fixed_salary"]),
    )
    clear_session(chat_id)
    prefix = _prompt(session, "success_prefix")
    return f"{prefix} {result}"


def _advance(chat_id: int, session: RegistrationSession) -> str:
    """Move to next step or complete registration."""
    nxt = _next_step(session.step)
    if nxt is None:
        return _complete(chat_id, session)
    session.step = nxt
    _sessions[chat_id] = session
    return _prompt(session, nxt)


def handle_message(chat_id: int, user_text: str) -> str | None:
    """
    Process message if registration wizard is active.

    Returns reply string, or None if wizard is not active.
    """
    if CANCEL_WORDS.match(user_text.strip()):
        if has_session(chat_id):
            lang = _sessions[chat_id].language
            clear_session(chat_id)
            return PROMPTS[_lang(lang)]["cancelled"]
        return None

    if not has_session(chat_id):
        return None

    session = _sessions[chat_id]
    text = user_text.strip()
    step = session.step

    if step == "full_name":
        if len(text) < 2:
            return _prompt(session, "invalid_name")
        session.data["full_name"] = text
        return _advance(chat_id, session)

    if step == "birthdate":
        birthdate = parse_birthdate(text)
        if not birthdate:
            return _prompt(session, "invalid_birthdate")
        session.data["birthdate"] = birthdate
        return _advance(chat_id, session)

    if step == "job_started_date":
        job_date = parse_date(text)
        if not job_date:
            return _prompt(session, "invalid_date")
        session.data["job_started_date"] = job_date
        return _advance(chat_id, session)

    if step == "fixed_salary":
        salary = parse_salary(text)
        if salary is None:
            return _prompt(session, "invalid_salary")
        session.data["fixed_salary"] = salary
        return _advance(chat_id, session)

    return None


def extract_prefill_from_text(user_text: str) -> dict[str, Any]:
    """Extract registration fields from free-form user text."""
    prefilled: dict[str, Any] = {}
    text = user_text.strip()

    salary = parse_salary(text)
    if salary is not None:
        prefilled["fixed_salary"] = salary

    age_match = re.search(r"(?i)(?:age|yosh|лет|года?)\s*[:\-]?\s*(\d{1,3})", text)
    if age_match:
        birthdate = parse_birthdate(age_match.group(1))
        if birthdate:
            prefilled["birthdate"] = birthdate

    if "birthdate" not in prefilled:
        date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
        if date_match:
            prefilled["birthdate"] = date_match.group(1)

    start_match = re.search(
        r"(?i)(?:started|start|boshlagan|начал[аи]?)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|today|bugun|сегодня)",
        text,
    )
    if start_match:
        job_date = parse_date(start_match.group(1))
        if job_date:
            prefilled["job_started_date"] = job_date

    name_match = re.search(
        r"(?i)(?:worker|employee|ishchi|работник)[,\s]+([A-Za-zА-Яа-яЁёʻʼ'\-]+(?:\s+[A-Za-zА-Яа-яЁёʻʼ'\-]+)?)",
        text,
    )
    if name_match:
        prefilled["full_name"] = name_match.group(1).strip().title()
    elif re.search(r"(?i)register.*?,?\s*([A-Za-zА-Яа-яЁёʻʼ'\-]{2,})", text):
        m = re.search(r"(?i)register.*?,?\s*([A-Za-zА-Яа-яЁёʻʼ'\-]{2,})", text)
        if m:
            name = m.group(1).split(",")[0].strip()
            if name.lower() not in ("new", "a", "worker", "employee"):
                prefilled["full_name"] = name.title()

    return prefilled


def try_start_from_intent(
    chat_id: int,
    user_text: str,
    intent: dict[str, Any],
) -> str | None:
    """
    Start wizard from register intent or trigger phrase.

    Returns first question if wizard started, else None.
    """
    action = intent.get("action")
    is_register = action == "register" or wants_to_start(user_text)
    if not is_register:
        return None

    prefilled = {
        "full_name": intent.get("full_name"),
        "birthdate": intent.get("birthdate"),
        "job_started_date": intent.get("job_started_date"),
        "fixed_salary": intent.get("fixed_salary"),
    }

    for key, value in extract_prefill_from_text(user_text).items():
        if prefilled.get(key) is None and value is not None:
            prefilled[key] = value

    if intent.get("worker") and not prefilled["full_name"]:
        prefilled["full_name"] = intent["worker"].replace("_", " ").title()

    if all(prefilled.get(k) for k in STEPS):
        return None

    language = (
        languages.get_language(chat_id)
        or intent.get("language")
        or detect_language(user_text)
    )
    return start_session(chat_id, language, prefilled)
