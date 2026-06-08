"""Date normalization for intent extraction and ledger entries."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PERIOD_PATTERN = re.compile(r"^\d{4}-\d{2}$")

_MONTH_NAMES: dict[str, int] = {
    "january": 1,
    "jan": 1,
    "yanvar": 1,
    "января": 1,
    "январь": 1,
    "february": 2,
    "feb": 2,
    "fevral": 2,
    "fev": 2,
    "февраля": 2,
    "февраль": 2,
    "march": 3,
    "mar": 3,
    "mart": 3,
    "марта": 3,
    "март": 3,
    "april": 4,
    "apr": 4,
    "aprel": 4,
    "апреля": 4,
    "апрель": 4,
    "may": 5,
    "mai": 5,
    "мая": 5,
    "june": 6,
    "jun": 6,
    "iyun": 6,
    "июня": 6,
    "июнь": 6,
    "july": 7,
    "jul": 7,
    "iyul": 7,
    "июля": 7,
    "июль": 7,
    "august": 8,
    "aug": 8,
    "avgust": 8,
    "августа": 8,
    "август": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "sentyabr": 9,
    "сентября": 9,
    "сентябрь": 9,
    "october": 10,
    "oct": 10,
    "oktyabr": 10,
    "октября": 10,
    "октябрь": 10,
    "november": 11,
    "nov": 11,
    "noyabr": 11,
    "ноября": 11,
    "ноябрь": 11,
    "december": 12,
    "dec": 12,
    "dekabr": 12,
    "декабря": 12,
    "декабрь": 12,
}

_THIS_YEAR = re.compile(
    r"(?i)\b(this\s+year|bu\s+yil|shu\s+yil|этом\s+году|в\s+этом\s+году)\b"
)
_ORDINAL_SUFFIX = r"(?:st|nd|rd|th)?"
_MONTH_TOKEN = r"[a-zа-яёʻʼ'\-]+"


def today_iso() -> str:
    return date.today().isoformat()


def yesterday_iso() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


def validate_date(value: str) -> str | None:
    """Return value if valid YYYY-MM-DD, else None."""
    if not DATE_PATTERN.match(value):
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None
    return value


def validate_period(value: str) -> str | None:
    """Return value if valid YYYY-MM, else None."""
    if not PERIOD_PATTERN.match(value):
        return None
    try:
        datetime.strptime(value + "-01", "%Y-%m-%d")
    except ValueError:
        return None
    return value


def date_to_period(value: str) -> str:
    """Convert YYYY-MM-DD to YYYY-MM."""
    validated = validate_date(value)
    if validated is None:
        raise ValueError(f"Invalid date: {value!r}")
    return validated[:7]


def _month_number(token: str) -> int | None:
    key = token.lower().strip().replace("ʻ", "'").replace("ʼ", "'")
    return _MONTH_NAMES.get(key)


def _make_date(year: int, month: int, day: int) -> str | None:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _default_year_for_text(text: str) -> int:
    if _THIS_YEAR.search(text):
        return date.today().year
    return date.today().year


def extract_date_from_text(text: str) -> str | None:
    """
    Parse natural-language dates from user text (offline fallback).

    Supports e.g. "This year in February 15th.", "2026 February 15",
    "February 15, 2026", "15-fevral", "15 февраля 2026".
    """
    if not text.strip():
        return None

    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if iso_match:
        return validate_date(iso_match.group(1))

    default_year = _default_year_for_text(text)
    lower = text.lower()

    patterns: list[tuple[str, str]] = [
        # 2026 February 15 / 2026 Feb 15th
        (
            rf"\b(\d{{4}})\s+({_MONTH_TOKEN})\s+(\d{{1,2}}){_ORDINAL_SUFFIX}\b",
            "year_month_day",
        ),
        # February 15 2026 / February 15th, 2026 / Feb 15
        (
            rf"\b({_MONTH_TOKEN})\s+(\d{{1,2}}){_ORDINAL_SUFFIX}(?:,)?\s*(\d{{4}})?\b",
            "month_day_year",
        ),
        # 15 February 2026 / 15th of February / 15th February
        (
            rf"\b(\d{{1,2}}){_ORDINAL_SUFFIX}\s+(?:of\s+)?({_MONTH_TOKEN})(?:\s+(\d{{4}}))?\b",
            "day_month_year",
        ),
        # 15-fevral 2026 / 15 fevral
        (
            rf"\b(\d{{1,2}})[-\s]({_MONTH_TOKEN})(?:\s+(\d{{4}}))?\b",
            "day_month_year",
        ),
    ]

    for pattern, kind in patterns:
        match = re.search(pattern, lower, flags=re.IGNORECASE)
        if not match:
            continue
        groups = match.groups()
        if kind == "year_month_day":
            year, month_tok, day_s = groups
            month = _month_number(month_tok)
            if month is None:
                continue
            return _make_date(int(year), month, int(day_s))
        if kind == "month_day_year":
            month_tok, day_s, year_s = groups
            month = _month_number(month_tok)
            if month is None:
                continue
            year = int(year_s) if year_s else default_year
            return _make_date(year, month, int(day_s))
        if kind == "day_month_year":
            day_s, month_tok, year_s = groups
            month = _month_number(month_tok)
            if month is None:
                continue
            year = int(year_s) if year_s else default_year
            return _make_date(year, month, int(day_s))

    return None


def normalize_intent_dates(
    intent: dict[str, Any], user_text: str = ""
) -> dict[str, Any]:
    """
    Validate and normalize date/period fields from Ollama intent.

    Derives period from date when only a specific day was given.
    Falls back to parsing dates from user_text when Ollama omits them.
    """
    raw_date = intent.get("date")
    if raw_date:
        intent["date"] = validate_date(str(raw_date))

    if not intent.get("date") and user_text:
        intent["date"] = extract_date_from_text(user_text)

    raw_period = intent.get("period")
    if raw_period:
        intent["period"] = validate_period(str(raw_period))

    if intent.get("date") and not intent.get("period"):
        intent["period"] = intent["date"][:7]

    return intent
