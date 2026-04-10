"""Preprocessing utilities for segmented phonological data."""

from __future__ import annotations

import re
import unicodedata

# Superscript Chao tone digits.
_SUPERSCRIPT_DIGITS: dict[str, int] = {
    "⁰": 0, "¹": 1, "²": 2, "³": 3, "⁴": 4, "⁵": 5,
}

_TONE_DIGIT_RE = re.compile(r"^[⁰¹²³⁴⁵]+$")

# Characters that indicate a syllabic segment (vowels + syllabic diacritic).
_VOWEL_CHARS: frozenset[str] = frozenset(
    "aeiouyɛɔəɨʉɯɵœæɐɑʌɪʊɤøɘɜɞɒɶɿʅ"
)
_SYLLABIC_COMBINING = "\u0329"  # combining vertical line below


def _is_syllabic(segment: str) -> bool:
    """Return whether *segment* looks syllabic (vowel or syllabic diacritic)."""
    if _SYLLABIC_COMBINING in segment:
        return True
    base = "".join(
        c for c in segment if not unicodedata.combining(c)
    )
    return bool(set(base.lower()) & _VOWEL_CHARS)


def _round_toward_neutral(value: float) -> int:
    """Round a non-integer Chao level toward neutral (level 3).

    Used for categorical systems when interpolating a midpoint produces
    a half-level: 1.5→2, 2.5→3, 3.5→3, 4.5→4.
    """
    if value == int(value):
        return int(value)
    if value < 3:
        return int(value + 0.5)  # round up toward 3
    return int(value)            # round down toward 3


def parse_chao_digits(tone: str) -> tuple[int, int, int] | None:
    """Parse a Chao digit string into (onset_level, mid_level, offset_level).

    Three-point model:
    - 1-digit (level): mid = onset = offset.
    - 2-digit (contour): mid = average of onset and offset, rounded
      toward neutral (level 3) when the average is non-integer.
    - 3+-digit: mid = second digit (explicit midpoint).

    Returns ``None`` for ``⁰`` (no tone) or empty strings.
    """
    digits = [_SUPERSCRIPT_DIGITS[ch] for ch in tone if ch in _SUPERSCRIPT_DIGITS]
    if not digits:
        return None
    # All zeros → no tone
    if all(d == 0 for d in digits):
        return None
    onset = digits[0]
    offset = digits[-1]
    # Single zero in a multi-digit string: treat as the non-zero value
    if onset == 0:
        onset = offset
    if offset == 0:
        offset = onset
    # Compute midpoint
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

    In CLDF/Lexibank segmented data, tone is typically encoded as a
    separate segment containing superscript Chao digits (e.g. ``³⁵``)
    placed after the tone-bearing syllable.  This function scans for
    such segments, finds the preceding syllabic nucleus (scanning
    backward past coda consonants, stopping at ``+`` morpheme
    boundaries), and concatenates the tone digits onto it.

    ``⁰`` (zero) is treated as "no tone" and is dropped silently.

    >>> merge_tone_digits(["tʰ", "o", "³¹", "+", "p", "e", "j", "¹³"])
    ['tʰ', 'o³¹', '+', 'p', 'e', 'j¹³']
    >>> merge_tone_digits(["k", "a", "n", "⁵⁵"])
    ['k', 'a⁵⁵', 'n']
    >>> merge_tone_digits(["a", "⁰"])
    ['a']
    """
    result = list(segments)

    # Process right-to-left so index shifts don't affect earlier entries.
    for i in range(len(result) - 1, -1, -1):
        if not _TONE_DIGIT_RE.match(result[i]):
            continue

        tone = result[i]
        parsed = parse_chao_digits(tone)

        # Remove the tone digit segment regardless.
        result.pop(i)

        if parsed is None:
            # ⁰ or unparseable → just drop
            continue

        # Scan backward for the syllabic nucleus.
        for j in range(i - 1, -1, -1):
            if result[j] == "+":
                break
            if _is_syllabic(result[j]):
                result[j] = result[j] + tone
                break

    return result
