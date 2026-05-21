"""Preprocessing utilities for segmented phonological data."""

from __future__ import annotations

import re
import unicodedata

_SUPERSCRIPT_DIGITS: dict[str, int] = {
    "⁰": 0, "¹": 1, "²": 2, "³": 3, "⁴": 4, "⁵": 5,
}

_TONE_DIGIT_RE = re.compile(r"^[⁰¹²³⁴⁵]+$")

_VOWEL_CHARS: frozenset[str] = frozenset(
    "aeiouyɛɔəɨʉɯɵœæɐɑʌɪʊɤøɘɜɞɒɶɿʅ"
)
_SYLLABIC_COMBINING = "̩"


def _is_syllabic(segment: str) -> bool:
    if _SYLLABIC_COMBINING in segment:
        return True
    base = "".join(c for c in segment if not unicodedata.combining(c))
    return bool(set(base.lower()) & _VOWEL_CHARS)


def _round_toward_neutral(value: float) -> int:
    if value == int(value):
        return int(value)
    if value < 3:
        return int(value + 0.5)
    return int(value)


def parse_chao_digits(tone: str) -> tuple[int, int, int] | None:
    """Parse a Chao digit string into (onset, mid, offset) levels.

    Returns None for empty or all-zero input.

    >>> parse_chao_digits("³⁵")
    (3, 4, 5)
    >>> parse_chao_digits("⁵⁵")
    (5, 5, 5)
    >>> parse_chao_digits("⁰")
    """
    digits = [_SUPERSCRIPT_DIGITS[ch] for ch in tone if ch in _SUPERSCRIPT_DIGITS]
    if not digits:
        return None
    if all(d == 0 for d in digits):
        return None
    onset = digits[0]
    offset = digits[-1]
    if onset == 0:
        onset = offset
    if offset == 0:
        offset = onset
    if len(digits) == 1:
        mid = onset
    elif len(digits) == 2:
        mid = _round_toward_neutral((onset + offset) / 2)
    else:
        mid = digits[1]
        if mid == 0:
            mid = _round_toward_neutral((onset + offset) / 2)
    return (onset, mid, offset)


def merge_tone_digits(segments: list[str]) -> list[str]:
    """Merge Chao tone digit segments onto their syllabic nucleus.

    >>> merge_tone_digits(["tʰ", "o", "³¹", "+", "p", "e", "j", "¹³"])
    ['tʰ', 'o³¹', '+', 'p', 'e¹³', 'j']
    >>> merge_tone_digits(["k", "a", "n", "⁵⁵"])
    ['k', 'a⁵⁵', 'n']
    >>> merge_tone_digits(["a", "⁰"])
    ['a']
    """
    result = list(segments)
    for i in range(len(result) - 1, -1, -1):
        if not _TONE_DIGIT_RE.match(result[i]):
            continue
        tone = result[i]
        parsed = parse_chao_digits(tone)
        result.pop(i)
        if parsed is None:
            continue
        for j in range(i - 1, -1, -1):
            if result[j] == "+":
                break
            if _is_syllabic(result[j]):
                result[j] = result[j] + tone
                break
    return result
