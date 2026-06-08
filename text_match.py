"""Typo-tolerant phrase matching for Uzbek commands and voice input."""

from __future__ import annotations

import difflib
import re

# Common Uzbek typos, keyboard slips, and speech-to-text mistakes (Latin script).
# Whisper often outputs Turkish orthography when it mis-detects Uzbek speech.
_WHISPER_TURKISH_FIXES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\bişçi\b"), "ishchi"),
    (re.compile(r"(?i)\bişçiler\b"), "ishchilar"),
    (re.compile(r"(?i)\byanke\b"), "yangi"),
    (re.compile(r"(?i)\byenge\b"), "yangi"),
)

_TYPO_FIXES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\byengi\b"), "yangi"),
    (re.compile(r"(?i)\byagni\b"), "yangi"),
    (re.compile(r"(?i)\byangi\b"), "yangi"),
    (re.compile(r"(?i)\bishci\b"), "ishchi"),
    (re.compile(r"(?i)\bishci"), "ishchi"),
    (re.compile(r"(?i)\bavns\b"), "avans"),
    (re.compile(r"(?i)\bqosh\b"), "qo'sh"),
    (re.compile(r"(?i)\boyxat"), "o'yxat"),
    (re.compile(r"(?i)\boychir"), "o'chir"),
    (re.compile(r"(?i)\boyzchirib\b"), "o'chirib"),
    (re.compile(r"(?i)\broyxat"), "ro'yxat"),
)

# Short phrases where fuzzy match is safe (whole-message commands).
REGISTER_PHRASES: tuple[str, ...] = (
    "yangi ishchi",
    "yangi ishchi qo'sh",
    "ishchi qo'sh",
    "add a new worker",
    "register new worker",
    "new worker",
    "новый работник",
)


def normalize_typos(text: str) -> str:
    """Apply known typo corrections before phrase matching."""
    result = text.strip()
    for pattern, replacement in _WHISPER_TURKISH_FIXES:
        result = pattern.sub(replacement, result)
    for pattern, replacement in _TYPO_FIXES:
        result = pattern.sub(replacement, result)
    return result


def normalize_transcription(text: str) -> str:
    """Fix common Whisper mis-hearings (Turkish script, Uzbek typos)."""
    return normalize_typos(text)


def _match_key(text: str) -> str:
    """Normalize text for fuzzy comparison."""
    text = normalize_typos(text).lower().strip().rstrip(".,!?")
    text = text.replace("ʻ", "'").replace("ʼ", "'").replace("`", "'")
    return text.replace("'", "")


def fuzzy_equals(text: str, phrase: str, *, cutoff: float = 0.82) -> bool:
    """Return True if text is close enough to phrase (typo-tolerant)."""
    a = _match_key(text)
    b = _match_key(phrase)
    if not a or not b:
        return False
    if a == b or b in a or a in b:
        return True
    if max(len(a), len(b)) > 48:
        return False
    return difflib.SequenceMatcher(None, a, b).ratio() >= cutoff


def fuzzy_match_phrase(
    text: str, phrases: tuple[str, ...] | list[str], *, cutoff: float = 0.82
) -> str | None:
    """Return the best matching canonical phrase, if any."""
    key = _match_key(text)
    if not key:
        return None
    normalized = [_match_key(p) for p in phrases]
    matches = difflib.get_close_matches(key, normalized, n=1, cutoff=cutoff)
    if matches:
        return phrases[normalized.index(matches[0])]
    return None
