"""Shared grapheme normalization and Unicode handling.

Functions here are used by all engine types. Engine-specific parsing
(sound name parsing, compositional decomposition) lives in the
respective engine module.
"""

from __future__ import annotations

import unicodedata

_IPA_EQUIVALENCES: dict[str, str] = {
    "ɡ": "g",
    "'": "ʼ",
    "’": "ʼ",
}

_IPA_REVERSE: dict[str, str] = {
    value: key for key, value in _IPA_EQUIVALENCES.items()
}

_TIE_BAR = "͡"
_RETRACTION = "̠"

_POSTALVEOLAR_FRICATIVES: frozenset[str] = frozenset({"ʃ", "ʒ"})
_AFFRICATE_STOPS: frozenset[str] = frozenset({"t", "d"})


def normalize_input_grapheme(grapheme: str) -> str:
    """Normalize lookup graphemes with NFD and IPA equivalences."""
    normalized = unicodedata.normalize("NFD", grapheme)
    return "".join(_IPA_EQUIVALENCES.get(char, char) for char in normalized)


def normalize_sequences(grapheme: str) -> list[str]:
    """Return candidate BIPA-style normalizations, in priority order.

    Handles tie-bar stripping and postalveolar affricate retraction
    (tʃ → t̠ʃ, dʒ → d̠ʒ). Returns an empty list if no normalizations
    apply.
    """
    candidates: list[str] = []
    without_tie = grapheme.replace(_TIE_BAR, "")
    if without_tie != grapheme:
        candidates.append(without_tie)
    base = without_tie if without_tie != grapheme else grapheme
    retracted = _insert_affricate_retraction(base)
    if retracted != base:
        candidates.append(retracted)
    return candidates


def _insert_affricate_retraction(text: str) -> str:
    chars = list(text)
    insertions: list[int] = []
    i = 0
    while i < len(chars) - 1:
        if chars[i] in _AFFRICATE_STOPS and chars[i + 1] in _POSTALVEOLAR_FRICATIVES:
            insertions.append(i + 1)
            i += 2
        else:
            i += 1
    if not insertions:
        return text
    for offset, pos in enumerate(insertions):
        chars.insert(pos + offset, _RETRACTION)
    return "".join(chars)


def normalize_output_grapheme(grapheme: str) -> str:
    """Map canonical output forms back to preferred IPA graphemes."""
    return "".join(_IPA_REVERSE.get(char, char) for char in grapheme)
