"""Shared grapheme normalization, decomposition, and Unicode handling.

Functions here are used by all engine types. Engine-specific parsing
(sound name parsing) lives in the respective engine module.
"""

from __future__ import annotations

import unicodedata

from merkmal.representations import FeatureState
from merkmal.segmentation import parse_chao_digits

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


# ── Tone / combining / modifier tables ──────────────────────────────────

_CHAO_SUPERSCRIPT_DIGITS: frozenset[str] = frozenset("⁰¹²³⁴⁵")

_TONE_MARK_TO_LEVELS: dict[int, tuple[int, int, int]] = {
    0x030B: (5, 5, 5),
    0x0301: (4, 4, 4),
    0x0304: (3, 3, 3),
    0x0300: (2, 2, 2),
    0x030F: (1, 1, 1),
    0x0302: (4, 3, 2),
    0x030C: (2, 3, 4),
}

_LEVEL_TO_ONSET_FEATURES: dict[int, frozenset[str]] = {
    5: frozenset({"tone-onset-upper", "tone-onset-raised"}),
    4: frozenset({"tone-onset-upper", "tone-onset-lowered"}),
    3: frozenset(),
    2: frozenset({"tone-onset-lower", "tone-onset-raised"}),
    1: frozenset({"tone-onset-lower", "tone-onset-lowered"}),
}

_LEVEL_TO_MID_FEATURES: dict[int, frozenset[str]] = {
    5: frozenset({"tone-mid-upper", "tone-mid-raised"}),
    4: frozenset({"tone-mid-upper", "tone-mid-lowered"}),
    3: frozenset(),
    2: frozenset({"tone-mid-lower", "tone-mid-raised"}),
    1: frozenset({"tone-mid-lower", "tone-mid-lowered"}),
}

_LEVEL_TO_OFFSET_FEATURES: dict[int, frozenset[str]] = {
    5: frozenset({"tone-offset-upper", "tone-offset-raised"}),
    4: frozenset({"tone-offset-upper", "tone-offset-lowered"}),
    3: frozenset(),
    2: frozenset({"tone-offset-lower", "tone-offset-raised"}),
    1: frozenset({"tone-offset-lower", "tone-offset-lowered"}),
}


def tone_features_for_levels(
    onset: int, mid: int, offset: int,
) -> frozenset[str]:
    return (
        _LEVEL_TO_ONSET_FEATURES[onset]
        | _LEVEL_TO_MID_FEATURES[mid]
        | _LEVEL_TO_OFFSET_FEATURES[offset]
    )


_COMBINING_TO_FEATURE: dict[int, str] = {
    0x0325: "devoiced",
    0x030A: "devoiced",
    0x032C: "revoiced",
    0x0330: "creaky",
    0x0324: "breathy",
    0x0303: "nasalized",
    0x0329: "syllabic",
    0x030D: "syllabic",
    0x032F: "non-syllabic",
    0x032A: "dental",
    0x031F: "advanced",
    0x0320: "retracted",
    0x0318: "advanced-tongue-root",
    0x0319: "retracted-tongue-root",
    0x033A: "apical",
    0x033B: "laminal",
    0x033C: "linguolabial",
    0x031D: "raised",
    0x031E: "lowered",
    0x0308: "centralized",
    0x033D: "mid-centralized",
    0x031C: "less-rounded",
    0x0339: "more-rounded",
    0x0306: "ultra-short",
    0x031A: "unreleased",
    0x0348: "strong",
}

_SUFFIX_MODIFIER_TO_FEATURE: dict[int, str] = {
    0x02D0: "long",
    0x02D1: "mid-long",
    0x02B0: "aspirated",
    0x02B1: "breathy",
    0x02B2: "palatalized",
    0x02B7: "labialized",
    0x02E0: "velarized",
    0x02E4: "pharyngealized",
    0x02C0: "glottalized",
    0x02BC: "ejective",
    0x1DA3: "labio-palatalized",
    0x207F: "with-nasal-release",
    0x02DE: "rhotacized",
    0x02E1: "with-lateral-release",
}

_PREFIX_MODIFIER_TO_FEATURE: dict[int, str] = {
    0x02B0: "pre-aspirated",
    0x02C0: "pre-glottalized",
    0x207F: "pre-nasalized",
    0x02B7: "pre-labialized",
    0x02B2: "pre-palatalized",
}

_ALL_MODIFIER_CPS: frozenset[int] = frozenset(
    _SUFFIX_MODIFIER_TO_FEATURE.keys() | _PREFIX_MODIFIER_TO_FEATURE.keys()
)


def decompose_grapheme(grapheme: str) -> tuple[str, frozenset[str]]:
    """Extract base characters and modifier features from a grapheme."""
    features: set[str] = set()

    prefix_end = 0
    for i, ch in enumerate(grapheme):
        cp = ord(ch)
        if (
            unicodedata.category(ch) in ("Lm", "Sk")
            and cp in _PREFIX_MODIFIER_TO_FEATURE
        ):
            features.add(_PREFIX_MODIFIER_TO_FEATURE[cp])
            prefix_end = i + 1
        else:
            break

    base_chars: list[str] = []
    chao_chars: list[str] = []
    remainder = grapheme[prefix_end:]

    tail_start = len(remainder)
    for k in range(len(remainder) - 1, -1, -1):
        if remainder[k] in _CHAO_SUPERSCRIPT_DIGITS:
            tail_start = k
        else:
            break

    for idx, ch in enumerate(remainder):
        if idx >= tail_start:
            chao_chars.append(ch)
            continue
        cp = ord(ch)
        cat = unicodedata.category(ch)
        if cp in _TONE_MARK_TO_LEVELS:
            onset, mid, offset = _TONE_MARK_TO_LEVELS[cp]
            features |= tone_features_for_levels(onset, mid, offset)
        elif cat.startswith("M") and cp in _COMBINING_TO_FEATURE:
            features.add(_COMBINING_TO_FEATURE[cp])
        elif cat in ("Lm", "Sk") and cp in _SUFFIX_MODIFIER_TO_FEATURE:
            features.add(_SUFFIX_MODIFIER_TO_FEATURE[cp])
        else:
            base_chars.append(ch)

    if chao_chars:
        parsed = parse_chao_digits("".join(chao_chars))
        if parsed is not None:
            onset, mid, offset = parsed
            features |= tone_features_for_levels(onset, mid, offset)

    return "".join(base_chars), frozenset(features)


def _build_feature_to_modifier() -> dict[str, str]:
    result: dict[str, str] = {}
    for cp, feat in _COMBINING_TO_FEATURE.items():
        result.setdefault(feat, chr(cp))
    for cp, feat in _SUFFIX_MODIFIER_TO_FEATURE.items():
        result[feat] = chr(cp)
    return result


_FEATURE_TO_MODIFIER: dict[str, str] = _build_feature_to_modifier()


def available_modifiers() -> tuple[str, ...]:
    return tuple(sorted(_FEATURE_TO_MODIFIER))


def compose_grapheme(base: str, modifiers: frozenset[str]) -> str:
    """Reconstruct a grapheme from base + modifier features."""
    suffix: list[str] = []
    for feat in sorted(modifiers):
        char = _FEATURE_TO_MODIFIER.get(feat)
        if char is not None:
            suffix.append(char)
    return base + "".join(suffix)


# ── Valued-feature modifier effects ────────────────────────────────────

_MODIFIER_TO_VALUED_EFFECT: dict[str, tuple[tuple[str, ...], FeatureState]] = {
    "devoiced": (("periodicGlottalSource", "voice", "voiced"), FeatureState.NEGATIVE),
    "revoiced": (("periodicGlottalSource", "voice", "voiced"), FeatureState.POSITIVE),
    "aspirated": (("spreadGlottis", "spread"), FeatureState.POSITIVE),
    "breathy": (("spreadGlottis", "spread"), FeatureState.POSITIVE),
    "creaky": (("constrictedGlottis", "constr"), FeatureState.POSITIVE),
    "nasalized": (("nasal",), FeatureState.POSITIVE),
    "long": (("long", "LONG"), FeatureState.POSITIVE),
    "dental": (("distributed",), FeatureState.POSITIVE),
    "syllabic": (("syllabic", "SYLLABIC"), FeatureState.POSITIVE),
    "non-syllabic": (("syllabic", "SYLLABIC"), FeatureState.NEGATIVE),
    "ejective": (("raisedLarynxEjective", "constrictedGlottis", "constr"), FeatureState.POSITIVE),
    "glottalized": (("constrictedGlottis", "constr"), FeatureState.POSITIVE),
    "palatalized": (("high",), FeatureState.POSITIVE),
    "labialized": (("round",), FeatureState.POSITIVE),
    "more-rounded": (("round",), FeatureState.POSITIVE),
    "less-rounded": (("round",), FeatureState.NEGATIVE),
    "velarized": (("dorsal",), FeatureState.POSITIVE),
    "pharyngealized": (("retractedTongueRoot",), FeatureState.POSITIVE),
    "advanced-tongue-root": (("advancedTongueRoot", "ATR"), FeatureState.POSITIVE),
    "retracted-tongue-root": (("retractedTongueRoot",), FeatureState.POSITIVE),
}


def apply_modifier_effects(
    base_values: dict[str, FeatureState],
    modifiers: frozenset[str],
    model_features: set[str],
) -> dict[str, FeatureState]:
    """Apply modifier effects to a copy of base valued features.

    For each modifier, looks up the first matching feature name from
    the model's feature set and sets it to the target state.
    """
    result = dict(base_values)
    for modifier in modifiers:
        effect = _MODIFIER_TO_VALUED_EFFECT.get(modifier)
        if effect is None:
            continue
        alternatives, target_state = effect
        for feat_name in alternatives:
            if feat_name in model_features:
                result[feat_name] = target_state
                break
    return result


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
            if has_base or cp in _PREFIX_MODIFIER_TO_FEATURE or cp in _SUFFIX_MODIFIER_TO_FEATURE:
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
