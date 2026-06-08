"""Uzbek command phrases from CSV and interactive wizards."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import data
import languages
import registration
import text_match
import tools

CSV_FILE = Path(__file__).resolve().parent / "uzbek commands.csv"

# phrase (normalized) -> internal action
PHRASE_ACTIONS: dict[str, str] = {
    "ishchini o'zchirib tashla": "delete_worker",
    "ishchini o'chirib tashla": "delete_worker",
    "avans berdim": "add_advance",
    "shtraf soldim": "add_penalty",
    "ishchilar ro'yxatini ber": "list_workers",
    "ishcilar ro'yxati": "list_workers",
    "ishchilar soni": "list_workers",
    "ishchilar royxati": "list_workers",
    "ishchilar royhati": "list_workers",
    "ishchilarmni ko'rsat": "list_workers",
    "ishchilrim": "list_workers",
    "ishchilarim": "list_workers",
}

INSTANT_ACTIONS = frozenset({"list_workers"})

PROMPTS: dict[str, dict[str, str]] = {
    "uz": {
        "delete_worker_name": "Qaysi ishchini o'chirmoqchisiz? (to'liq ism)",
        "delete_confirm": "{name} ni rostdan ham o'chirasizmi? (ha / yo'q)",
        "delete_done": "{name} ro'yxatdan o'chirildi.",
        "delete_cancelled": "O'chirish bekor qilindi.",
        "advance_worker": "Qaysi ishchiga avans berdingiz? (ism)",
        "advance_amount": "Qancha avans berildi? (masalan, 500000 yoki 500 ming)",
        "penalty_worker": "Qaysi ishchiga jarima (shtraf) qo'llanildi? (ism)",
        "penalty_amount": "Jarima summasi qancha? (masalan, 200000)",
        "invalid_amount": "Iltimos, to'g'ri summa kiriting.",
        "invalid_confirm": "Iltimos, 'ha' yoki 'yo'q' deb javob bering.",
        "cancelled": "Bekor qilindi.",
    },
    "en": {
        "delete_worker_name": "Which worker should be removed? (full name)",
        "delete_confirm": "Really delete {name}? (yes / no)",
        "delete_done": "{name} has been removed.",
        "delete_cancelled": "Deletion cancelled.",
        "advance_worker": "Which worker received the advance?",
        "advance_amount": "How much was the advance? (e.g. 500000)",
        "penalty_worker": "Which worker received the penalty?",
        "penalty_amount": "What is the penalty amount?",
        "invalid_amount": "Please enter a valid amount.",
        "invalid_confirm": "Please answer yes or no.",
        "cancelled": "Cancelled.",
    },
}

YES_WORDS = re.compile(r"(?i)^(ha|yes|haa|albatta|rozi|ok|да|confirm)$")
NO_WORDS = re.compile(r"(?i)^(yo'q|yoq|йўқ|no|bekor|отмена|cancel)$")

_sessions: dict[int, CommandSession] = {}


@dataclass
class UzbekCommand:
    """One row from the Uzbek commands CSV."""

    phrase: str
    means: str
    description: str
    action: str


@dataclass
class CommandSession:
    """In-progress Uzbek command wizard."""

    action: str
    step: str = "worker"
    data: dict[str, Any] = field(default_factory=dict)
    language: str = "uz"


def _lang(code: str | None) -> str:
    return code if code in ("en", "ru", "uz") else "uz"


def _t(lang: str, key: str, **kwargs: str) -> str:
    text = PROMPTS.get(_lang(lang), PROMPTS["uz"]).get(
        key, PROMPTS["en"].get(key, key)
    )
    return text.format(**kwargs) if kwargs else text


def _normalize_phrase(text: str) -> str:
    text = text.strip().lower().rstrip(".,!?")
    text = text.replace("ʻ", "'").replace("ʼ", "'").replace("`", "'")
    return text


def _normalize_for_match(text: str) -> str:
    """Looser match: ignore apostrophes (royxati == ro'yxati)."""
    return _normalize_phrase(text).replace("'", "")


def _infer_action(phrase: str, description: str) -> str:
    """Map CSV row to internal action."""
    key = _normalize_phrase(phrase)
    if key in PHRASE_ACTIONS:
        return PHRASE_ACTIONS[key]
    desc = description.lower()
    if "delete" in desc or "remove" in desc or "o'chir" in desc:
        return "delete_worker"
    if "advance" in desc or "avans" in desc:
        return "add_advance"
    if "penalty" in desc or "shtraf" in desc or "jarima" in desc:
        return "add_penalty"
    if (
        "list" in desc
        or "ro'yxat" in desc
        or "royxat" in desc
        or "soni" in desc
        or "ko'rsat" in desc
        or "count" in desc
    ):
        return "list_workers"
    return "unknown"


def load_commands() -> list[UzbekCommand]:
    """Load Uzbek commands from CSV file."""
    commands: list[UzbekCommand] = []
    if not CSV_FILE.exists():
        return commands

    with open(CSV_FILE, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            phrase = (row.get("Commands uzbek") or "").strip()
            if not phrase:
                continue
            means = (row.get("Means") or "").strip()
            description = (row.get("Do") or "").strip()
            commands.append(
                UzbekCommand(
                    phrase=phrase,
                    means=means,
                    description=description,
                    action=_infer_action(phrase, description),
                )
            )
    return commands


COMMANDS: list[UzbekCommand] = load_commands()


def reload_commands() -> None:
    """Reload commands from disk (e.g. after CSV edit)."""
    global COMMANDS
    COMMANDS = load_commands()


def match_command(text: str) -> UzbekCommand | None:
    """Return matching Uzbek command for user text, if any."""
    norm = _normalize_phrase(text)
    loose = _normalize_for_match(text)
    for cmd in COMMANDS:
        phrase = _normalize_phrase(cmd.phrase)
        phrase_loose = _normalize_for_match(cmd.phrase)
        if (
            norm == phrase
            or phrase in norm
            or loose == phrase_loose
            or phrase_loose in loose
        ):
            return cmd
    for phrase, action in PHRASE_ACTIONS.items():
        phrase_norm = _normalize_phrase(phrase)
        phrase_loose = _normalize_for_match(phrase)
        if (
            norm == phrase_norm
            or phrase_norm in norm
            or loose == phrase_loose
            or phrase_loose in loose
            or text_match.fuzzy_equals(text, phrase)
        ):
            return UzbekCommand(
                phrase=phrase,
                means="",
                description="",
                action=action,
            )
    all_phrases = [cmd.phrase for cmd in COMMANDS] + list(PHRASE_ACTIONS.keys())
    fuzzy_hit = text_match.fuzzy_match_phrase(text, all_phrases)
    if fuzzy_hit:
        for cmd in COMMANDS:
            if text_match.fuzzy_equals(fuzzy_hit, cmd.phrase):
                return cmd
        if fuzzy_hit in PHRASE_ACTIONS:
            return UzbekCommand(
                phrase=fuzzy_hit,
                means="",
                description="",
                action=PHRASE_ACTIONS[fuzzy_hit],
            )
    return None


def has_session(chat_id: int) -> bool:
    """Return True if a Uzbek command wizard is active."""
    return chat_id in _sessions


def clear_session(chat_id: int) -> None:
    """Cancel active Uzbek command wizard."""
    _sessions.pop(chat_id, None)


def _parse_amount(text: str) -> float | None:
    return registration.parse_salary(text)


def _resolve_worker_name(name: str) -> str:
    return data.resolve_worker_key(name.strip())


def _start_session(chat_id: int, action: str, language: str) -> str:
    session = CommandSession(action=action, language=_lang(language))
    if action == "delete_worker":
        session.step = "worker"
        _sessions[chat_id] = session
        return _t(language, "delete_worker_name")
    if action == "add_advance":
        session.step = "worker"
        _sessions[chat_id] = session
        return _t(language, "advance_worker")
    if action == "add_penalty":
        session.step = "worker"
        _sessions[chat_id] = session
        return _t(language, "penalty_worker")
    return ""


def _instant_response(action: str, language: str) -> str:
    """Return immediate reply for commands that need no wizard."""
    if action == "list_workers":
        return tools.tool_list_workers(_lang(language))
    return ""


def try_start(chat_id: int, user_text: str, language: str = "uz") -> str | None:
    """Start wizard if text matches a Uzbek command phrase."""
    cmd = match_command(user_text)
    if cmd is None or cmd.action == "unknown":
        return None
    lang = languages.get_language(chat_id) or language
    if cmd.action in INSTANT_ACTIONS:
        return _instant_response(cmd.action, lang)
    return _start_session(chat_id, cmd.action, lang)


def handle_message(chat_id: int, user_text: str) -> str | None:
    """Handle wizard step if session is active."""
    if NO_WORDS.match(user_text.strip()) and has_session(chat_id):
        lang = _sessions[chat_id].language
        clear_session(chat_id)
        return _t(lang, "cancelled")

    if not has_session(chat_id):
        return None

    session = _sessions[chat_id]
    lang = session.language
    text = user_text.strip()

    if session.action == "delete_worker":
        if session.step == "worker":
            try:
                key = _resolve_worker_name(text)
                worker = data.get_worker(key)
                if worker is None:
                    return f"Worker not found: {text}"
                session.data["worker_key"] = key
                session.data["worker_name"] = worker["full_name"]
                session.step = "confirm"
                return _t(lang, "delete_confirm", name=worker["full_name"])
            except ValueError as exc:
                return str(exc)

        if session.step == "confirm":
            if YES_WORDS.match(text):
                key = session.data["worker_key"]
                name = session.data["worker_name"]
                result = tools.tool_delete_worker(key)
                clear_session(chat_id)
                return result if result else _t(lang, "delete_done", name=name)
            if NO_WORDS.match(text):
                clear_session(chat_id)
                return _t(lang, "delete_cancelled")
            return _t(lang, "invalid_confirm")

    if session.action == "add_advance":
        if session.step == "worker":
            try:
                key = _resolve_worker_name(text)
                worker = data.get_worker(key)
                if worker is None:
                    return f"Worker not found: {text}"
                session.data["worker_key"] = key
                session.step = "amount"
                return _t(lang, "advance_amount")
            except ValueError as exc:
                return str(exc)

        if session.step == "amount":
            amount = _parse_amount(text)
            if amount is None:
                return _t(lang, "invalid_amount")
            result = tools.tool_add_advance(session.data["worker_key"], amount, "avans berdim")
            clear_session(chat_id)
            return result

    if session.action == "add_penalty":
        if session.step == "worker":
            try:
                key = _resolve_worker_name(text)
                worker = data.get_worker(key)
                if worker is None:
                    return f"Worker not found: {text}"
                session.data["worker_key"] = key
                session.step = "amount"
                return _t(lang, "penalty_amount")
            except ValueError as exc:
                return str(exc)

        if session.step == "amount":
            amount = _parse_amount(text)
            if amount is None:
                return _t(lang, "invalid_amount")
            result = tools.tool_add_penalty(session.data["worker_key"], amount, "shtraf")
            clear_session(chat_id)
            return result

    return None
