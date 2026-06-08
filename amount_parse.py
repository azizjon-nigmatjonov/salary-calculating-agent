"""Parse monetary amounts from digits and spoken/written number words."""

from __future__ import annotations

import re
from typing import Any

_NUMBER_WORDS: dict[str, float] = {
    # English
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
    "half": 0.5,
    # Uzbek (Latin)
    "bir": 1,
    "ikki": 2,
    "uch": 3,
    "tort": 4,
    "to'rt": 4,
    "besh": 5,
    "olti": 6,
    "yetti": 7,
    "sakkiz": 8,
    "to'qqiz": 9,
    "on": 10,
    "yigirma": 20,
    "o'ttiz": 30,
    "qirq": 40,
    "ellik": 50,
    "oltmish": 60,
    "yetmish": 70,
    "sakson": 80,
    "to'qson": 90,
    "yuz": 100,
    "yarim": 0.5,
    # Russian
    "один": 1,
    "одна": 1,
    "два": 2,
    "две": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
    "десять": 10,
    "двадцать": 20,
    "тридцать": 30,
    "сорок": 40,
    "пятьдесят": 50,
    "шестьдесят": 60,
    "семьдесят": 70,
    "восемьдесят": 80,
    "девяносто": 90,
    "сто": 100,
    "пол": 0.5,
    "полтора": 1.5,
}

_MULTIPLIERS: dict[str, float] = {
    "thousand": 1_000,
    "k": 1_000,
    "ming": 1_000,
    "минг": 1_000,
    "тыс": 1_000,
    "тысяча": 1_000,
    "тысяч": 1_000,
    "million": 1_000_000,
    "millions": 1_000_000,
    "mln": 1_000_000,
    "млн": 1_000_000,
    "миллион": 1_000_000,
    "миллиона": 1_000_000,
    "миллионов": 1_000_000,
    "billion": 1_000_000_000,
    "mlrd": 1_000_000_000,
    "млрд": 1_000_000_000,
}

_CURRENCY_NOISE = re.compile(
    r"(?i)\b(som|so'm|sum|сум|сўм|uzs|dollars?|usd)\b"
)


def _to_float(number: str) -> float | None:
    try:
        value = float(number)
    except ValueError:
        return None
    return value if value > 0 else None


def _parse_digit_amount(text: str) -> float | None:
    """Parse amounts written with digits: 5000000, 5 mln, 500 ming."""
    compact = text.lower().replace(",", "")
    number = r"(\d+(?:\.\d+)?)"

    mln_match = re.search(rf"{number}\s*(mln|million|млн|миллион)", compact)
    if mln_match:
        base = _to_float(mln_match.group(1))
        return base * 1_000_000 if base is not None else None

    ming_match = re.search(rf"{number}\s*(ming|минг|тыс|k)\b", compact)
    if ming_match:
        base = _to_float(ming_match.group(1))
        return base * 1_000 if base is not None else None

    cleaned = _CURRENCY_NOISE.sub("", compact)
    num_match = re.search(rf"\b{number}\b", cleaned)
    if num_match:
        return _to_float(num_match.group(1))
    return None


def _tokenize_words(text: str) -> list[str]:
    text = text.lower().strip()
    text = text.replace("ʻ", "'").replace("ʼ", "'")
    text = re.sub(r"[^\w\s']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.split() if text else []


def _parse_word_amount(text: str) -> float | None:
    """
    Parse spoken amounts: 'six million', 'yarim mln', 'five hundred thousand'.
    """
    tokens = _tokenize_words(text)
    if not tokens:
        return None

    total = 0.0
    current: float | None = None
    found = False

    for raw in tokens:
        token = raw.replace("'", "")
        if token in _MULTIPLIERS:
            mult = _MULTIPLIERS[token]
            base = current if current is not None else 1.0
            total += base * mult
            current = None
            found = True
            continue

        if token in _NUMBER_WORDS:
            value = _NUMBER_WORDS[token]
            if value == 100 and current is not None:
                current *= 100
            elif current is not None and value < 100 and current >= 20:
                current += value
            else:
                if current is not None:
                    total += current
                current = value
            found = True
            continue

        if token.isdigit():
            if current is not None:
                total += current
            current = float(token)
            found = True

    if current is not None:
        total += current

    if not found or total <= 0:
        return None

    # Require a multiplier or digit — ignore stray number words in normal sentences.
    has_multiplier = any(t.replace("'", "") in _MULTIPLIERS for t in tokens)
    has_digit = any(t.isdigit() for t in tokens)
    if not has_multiplier and not has_digit:
        return None

    return total


def parse_amount(text: str) -> float | None:
    """Parse a monetary amount from digits or natural language words."""
    if not text or not text.strip():
        return None
    return _parse_digit_amount(text) or _parse_word_amount(text)


def normalize_intent_amount(intent: dict[str, Any], user_text: str = "") -> dict[str, Any]:
    """Fill or fix intent amount from user text when Ollama leaves it null."""
    amount = intent.get("amount")
    fixed_salary = intent.get("fixed_salary")

    if amount is None and user_text:
        parsed = parse_amount(user_text)
        if parsed is not None:
            intent["amount"] = parsed

    if fixed_salary is None and user_text:
        parsed = parse_amount(user_text)
        if parsed is not None:
            intent["fixed_salary"] = parsed

    return intent
