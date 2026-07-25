"""Shared grapheme normalization, decomposition, and Unicode handling.

Functions here are used by all engine types. Engine-specific parsing
(sound name parsing) lives in the respective engine module.
"""

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING

from merkmal.diacritics import CHAO_SUPERSCRIPT_DIGITS, DEFAULT_DIACRITICS

if TYPE_CHECKING:
    from merkmal.representations import FeatureState

# Bidirectional canonical pairs: folded to the lookup form on input and mapped
# back to the preferred IPA glyph on output.
_IPA_EQUIVALENCES: dict[str, str] = {
    "ɡ": "g",
}

# One-directional input folds (NOT reversed on output): assorted apostrophes
# fold to the IPA modifier-letter apostrophe ʼ (U+02BC) used for ejectives.
# Reversing these would turn canonical ʼ into a typographic quote.
_IPA_INPUT_FOLDS: dict[str, str] = {
    "'": "ʼ",
    "’": "ʼ",
}

_IPA_INPUT_MAP: dict[str, str] = {**_IPA_EQUIVALENCES, **_IPA_INPUT_FOLDS}

_IPA_REVERSE: dict[str, str] = {
    value: key for key, value in _IPA_EQUIVALENCES.items()
}

# One-directional input normalizations (NOT reversed on output): deprecated
# single-codepoint affricate ligatures → digraph, and ASCII colon → IPA length.
_LIGATURE_EXPANSIONS: dict[str, str] = {
    "ʣ": "dz", "ʤ": "dʒ", "ʥ": "dʑ",
    "ʦ": "ts", "ʧ": "tʃ", "ʨ": "tɕ",
}
_ASCII_TO_IPA: dict[str, str] = {
    ":": "ː",  # ASCII colon frequently substitutes the IPA length mark
}

# Suprasegmental stress marks (primary, secondary). Stripped on input: they
# carry no segmental features, and feature-vector consumers ignore stress.
_STRESS_MARKS: frozenset[str] = frozenset({"ˈ", "ˌ"})

_TIE_BAR = "͡"
_RETRACTION = "̠"

_POSTALVEOLAR_FRICATIVES: frozenset[str] = frozenset({"ʃ", "ʒ"})
_AFFRICATE_STOPS: frozenset[str] = frozenset({"t", "d"})


def _resolve_slash(grapheme: str) -> str:
    """Resolve CLTS source/BIPA slash notation, keeping the post-slash value.

    CLTS writes ``source/bipa`` to record a literature grapheme before the
    slash and the BIPA value that tools (lingpy, …) consume after it.
    Returns the substring after the last slash when present and non-empty,
    otherwise the input unchanged.
    """
    if "/" in grapheme:
        post = grapheme.rsplit("/", 1)[1]
        if post:
            return post
    return grapheme


def normalize_input_grapheme(grapheme: str) -> str:
    """Normalize a lookup grapheme to its canonical BIPA segmental form.

    Resolves CLTS source/BIPA slash notation (``a/b`` → ``b``), strips
    leading suprasegmental stress marks, applies NFD, expands deprecated
    affricate ligatures (``ʤ`` → ``dʒ`` …), maps ASCII colon to the IPA
    length mark, and applies the reversible IPA equivalences (``ɡ`` → ``g``).
    """
    grapheme = _resolve_slash(grapheme)
    while grapheme[:1] in _STRESS_MARKS:
        grapheme = grapheme[1:]
    normalized = unicodedata.normalize("NFD", grapheme)
    out: list[str] = []
    for char in normalized:
        if char in _LIGATURE_EXPANSIONS:
            out.append(_LIGATURE_EXPANSIONS[char])
        elif char in _ASCII_TO_IPA:
            out.append(_ASCII_TO_IPA[char])
        else:
            out.append(_IPA_INPUT_MAP.get(char, char))
    return "".join(out)


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


def normalize(grapheme: str) -> str:
    """Canonical NFC IPA form of a grapheme, suitable for storage.

    Applies the full input normalization (slash resolution, stress
    stripping, ligature/colon expansion, IPA equivalences), maps
    equivalences back to preferred IPA graphemes (``g`` → ``ɡ``), and
    recomposes to NFC. Returns ``""`` for input that normalizes away
    entirely (e.g. a bare stress mark).
    """
    norm = normalize_output_grapheme(normalize_input_grapheme(grapheme))
    return unicodedata.normalize("NFC", norm)


# ── Diacritic / tone / modifier composition ─────────────────────────────
#
# The feature-name mapping is data-drivable; see merkmal.diacritics. The
# module-level functions below operate on the built-in IPA/CLTS table and
# preserve the public API. Engines that carry a custom diacritic set call
# the corresponding DiacriticTable methods directly.

_CHAO_SUPERSCRIPT_DIGITS = CHAO_SUPERSCRIPT_DIGITS


def tone_features_for_levels(onset: int, mid: int, offset: int) -> frozenset[str]:
    return DEFAULT_DIACRITICS.tone_features_for_levels(onset, mid, offset)


def decompose_grapheme(grapheme: str) -> tuple[str, frozenset[str]]:
    """Extract base characters and modifier features from a grapheme."""
    return DEFAULT_DIACRITICS.decompose(grapheme)


def available_modifiers() -> tuple[str, ...]:
    return DEFAULT_DIACRITICS.available_modifiers()


def compose_grapheme(base: str, modifiers: frozenset[str]) -> str:
    """Reconstruct a grapheme from base + modifier features."""
    return DEFAULT_DIACRITICS.compose(base, modifiers)


def apply_modifier_effects(
    base_values: dict[str, FeatureState],
    modifiers: frozenset[str],
    model_features: set[str],
) -> dict[str, FeatureState]:
    """Apply modifier effects to a copy of base valued features."""
    return DEFAULT_DIACRITICS.apply_valued_effects(
        base_values, modifiers, model_features
    )


# ── IPA segmentation ──────────────────────────────────────────────────

_TIE_BARS: frozenset[str] = frozenset({"͡", "͜"})
_BOUNDARY_CHARS: frozenset[str] = frozenset({"+", ".", "|", "‖"})


def segment_ipa(ipa: str) -> list[str]:
    """Segment an IPA string into individual phones.

    Chao tone digits are emitted as separate tokens; use
    ``merge_tone_digits()`` to attach them to syllabic nuclei.

    >>> segment_ipa("tʰoŋ")
    ['tʰ', 'o', 'ŋ']
    >>> segment_ipa("t͡sʰa")
    ['t͡sʰ', 'a']
    """
    nfd = unicodedata.normalize("NFD", ipa)
    result: list[str] = []
    current: list[str] = []
    has_base = False
    after_tie = False

    def flush() -> None:
        nonlocal has_base, after_tie
        if current:
            result.append("".join(current))
            current.clear()
        has_base = False
        after_tie = False

    i = 0
    while i < len(nfd):
        ch = nfd[i]
        cp = ord(ch)
        cat = unicodedata.category(ch)

        if ch in _CHAO_SUPERSCRIPT_DIGITS:
            flush()
            start = i
            while i < len(nfd) and nfd[i] in _CHAO_SUPERSCRIPT_DIGITS:
                i += 1
            result.append(nfd[start:i])
            continue

        if ch == " ":
            flush()
            i += 1
            continue

        if ch in _BOUNDARY_CHARS:
            flush()
            result.append(ch)
            i += 1
            continue

        if ch in _TIE_BARS:
            current.append(ch)
            after_tie = True
            i += 1
            continue

        if cat.startswith("M"):
            current.append(ch)
            i += 1
            continue

        if cat in ("Lm", "Sk"):
            if has_base or cp in DEFAULT_DIACRITICS.prefix or cp in DEFAULT_DIACRITICS.suffix:
                current.append(ch)
            else:
                if has_base and not after_tie:
                    flush()
                current.append(ch)
                has_base = True
                after_tie = False
            i += 1
            continue

        if has_base and not after_tie:
            flush()
        current.append(ch)
        has_base = True
        after_tie = False
        i += 1

    flush()
    return result
