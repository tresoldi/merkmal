"""Shared grapheme normalization and Unicode handling.

Functions here are used by all engine types. Engine-specific parsing
(sound name parsing, compositional decomposition) lives in the
respective engine module.
"""

from __future__ import annotations

import unicodedata

_IPA_EQUIVALENCES: dict[str, str] = {
    "ɡ": "g",
    "’": "ʼ",
    "'": "ʼ",
}

_IPA_REVERSE: dict[str, str] = {
    value: key for key, value in _IPA_EQUIVALENCES.items()
}


def normalize_input_grapheme(grapheme: str) -> str:
    """Normalize lookup graphemes with NFD and IPA equivalences."""
    normalized = unicodedata.normalize("NFD", grapheme)
    return "".join(_IPA_EQUIVALENCES.get(char, char) for char in normalized)


def normalize_output_grapheme(grapheme: str) -> str:
    """Map canonical output forms back to preferred IPA graphemes."""
    return "".join(_IPA_REVERSE.get(char, char) for char in grapheme)
