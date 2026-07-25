"""Diacritic / modifier / tone feature tables (data-drivable).

Diacritic composition turns a grapheme such as ``tʰ`` into a base
(``t``) plus modifier features (``aspirated``). Which feature *names*
those modifiers produce is part of a feature system's vocabulary, so it
must be configurable when a user brings their own model.

This module defines :class:`DiacriticTable`, which bundles the
codepoint→feature maps, the tone-level→feature maps, and the valued
modifier effects, together with the decomposition / composition logic
that uses them. :data:`DEFAULT_DIACRITICS` is the built-in IPA/CLTS set;
:func:`load_diacritics` loads alternative sets from
``diacritics/<name>.json`` on the layered data search path.

The Unicode *recognition* of modifiers (which codepoints are tie bars,
combining marks, etc.) and IPA input normalization remain global and
live in :mod:`merkmal.grapheme`; only the feature-name mapping is
parameterized here.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from functools import cache
from typing import Any

from merkmal.representations import FeatureState
from merkmal.segmentation import parse_chao_digits

CHAO_SUPERSCRIPT_DIGITS: frozenset[str] = frozenset("⁰¹²³⁴⁵")


@dataclass
class DiacriticTable:
    """A named set of diacritic/modifier/tone → feature mappings."""

    name: str
    combining: dict[int, str]
    suffix: dict[int, str]
    prefix: dict[int, str]
    tone_marks: dict[int, tuple[int, int, int]]
    tone_onset: dict[int, frozenset[str]]
    tone_mid: dict[int, frozenset[str]]
    tone_offset: dict[int, frozenset[str]]
    valued_effects: dict[str, tuple[tuple[str, ...], FeatureState]]

    _feature_to_modifier: dict[str, str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        rev: dict[str, str] = {}
        for cp, feat in self.combining.items():
            rev.setdefault(feat, chr(cp))
        for cp, feat in self.suffix.items():
            rev[feat] = chr(cp)
        self._feature_to_modifier = rev

    # ── Tone ─────────────────────────────────────────────────────────
    def tone_features_for_levels(
        self, onset: int, mid: int, offset: int
    ) -> frozenset[str]:
        return (
            self.tone_onset[onset]
            | self.tone_mid[mid]
            | self.tone_offset[offset]
        )

    # ── Decomposition ────────────────────────────────────────────────
    def decompose(self, grapheme: str) -> tuple[str, frozenset[str]]:
        """Extract base characters and modifier features from a grapheme."""
        features: set[str] = set()

        prefix_end = 0
        for i, ch in enumerate(grapheme):
            cp = ord(ch)
            if unicodedata.category(ch) in ("Lm", "Sk") and cp in self.prefix:
                features.add(self.prefix[cp])
                prefix_end = i + 1
            else:
                break

        base_chars: list[str] = []
        chao_chars: list[str] = []
        remainder = grapheme[prefix_end:]

        tail_start = len(remainder)
        for k in range(len(remainder) - 1, -1, -1):
            if remainder[k] in CHAO_SUPERSCRIPT_DIGITS:
                tail_start = k
            else:
                break

        for idx, ch in enumerate(remainder):
            if idx >= tail_start:
                chao_chars.append(ch)
                continue
            cp = ord(ch)
            cat = unicodedata.category(ch)
            if cp in self.tone_marks:
                onset, mid, offset = self.tone_marks[cp]
                features |= self.tone_features_for_levels(onset, mid, offset)
            elif cat.startswith("M") and cp in self.combining:
                features.add(self.combining[cp])
            elif cat in ("Lm", "Sk") and cp in self.suffix:
                features.add(self.suffix[cp])
            else:
                base_chars.append(ch)

        if chao_chars:
            parsed = parse_chao_digits("".join(chao_chars))
            if parsed is not None:
                onset, mid, offset = parsed
                features |= self.tone_features_for_levels(onset, mid, offset)

        return "".join(base_chars), frozenset(features)

    # ── Composition ──────────────────────────────────────────────────
    def available_modifiers(self) -> tuple[str, ...]:
        return tuple(sorted(self._feature_to_modifier))

    def compose(self, base: str, modifiers: frozenset[str]) -> str:
        """Reconstruct a grapheme from base + modifier features."""
        suffix: list[str] = []
        for feat in sorted(modifiers):
            char = self._feature_to_modifier.get(feat)
            if char is not None:
                suffix.append(char)
        return base + "".join(suffix)

    # ── Valued effects ───────────────────────────────────────────────
    def apply_valued_effects(
        self,
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
            effect = self.valued_effects.get(modifier)
            if effect is None:
                continue
            alternatives, target_state = effect
            for feat_name in alternatives:
                if feat_name in model_features:
                    result[feat_name] = target_state
                    break
        return result


# ── Built-in IPA / CLTS default ─────────────────────────────────────────

_DEFAULT_COMBINING: dict[int, str] = {
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

_DEFAULT_SUFFIX: dict[int, str] = {
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

_DEFAULT_PREFIX: dict[int, str] = {
    0x02B0: "pre-aspirated",
    0x02C0: "pre-glottalized",
    0x207F: "pre-nasalized",
    0x02B7: "pre-labialized",
    0x02B2: "pre-palatalized",
}

_DEFAULT_TONE_MARKS: dict[int, tuple[int, int, int]] = {
    0x030B: (5, 5, 5),
    0x0301: (4, 4, 4),
    0x0304: (3, 3, 3),
    0x0300: (2, 2, 2),
    0x030F: (1, 1, 1),
    0x0302: (4, 3, 2),
    0x030C: (2, 3, 4),
}


def _tone_levels(prefix: str) -> dict[int, frozenset[str]]:
    return {
        5: frozenset({f"tone-{prefix}-upper", f"tone-{prefix}-raised"}),
        4: frozenset({f"tone-{prefix}-upper", f"tone-{prefix}-lowered"}),
        3: frozenset(),
        2: frozenset({f"tone-{prefix}-lower", f"tone-{prefix}-raised"}),
        1: frozenset({f"tone-{prefix}-lower", f"tone-{prefix}-lowered"}),
    }


_DEFAULT_VALUED_EFFECTS: dict[str, tuple[tuple[str, ...], FeatureState]] = {
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
    "ejective": (
        ("raisedLarynxEjective", "constrictedGlottis", "constr"),
        FeatureState.POSITIVE,
    ),
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

DEFAULT_DIACRITICS_NAME = "ipa-clts"

DEFAULT_DIACRITICS = DiacriticTable(
    name=DEFAULT_DIACRITICS_NAME,
    combining=dict(_DEFAULT_COMBINING),
    suffix=dict(_DEFAULT_SUFFIX),
    prefix=dict(_DEFAULT_PREFIX),
    tone_marks=dict(_DEFAULT_TONE_MARKS),
    tone_onset=_tone_levels("onset"),
    tone_mid=_tone_levels("mid"),
    tone_offset=_tone_levels("offset"),
    valued_effects=dict(_DEFAULT_VALUED_EFFECTS),
)


# ── Loading from JSON ────────────────────────────────────────────────────

def _parse_cp_map(raw: dict[str, str]) -> dict[int, str]:
    return {int(k, 16): v for k, v in raw.items()}


def _parse_levels(raw: dict[str, list[str]]) -> dict[int, frozenset[str]]:
    return {int(k): frozenset(v) for k, v in raw.items()}


def _parse_valued_effects(
    raw: dict[str, Any],
) -> dict[str, tuple[tuple[str, ...], FeatureState]]:
    out: dict[str, tuple[tuple[str, ...], FeatureState]] = {}
    for modifier, spec in raw.items():
        feats = tuple(spec["features"])
        out[modifier] = (feats, FeatureState(spec["state"]))
    return out


def parse_diacritics(data: dict[str, Any], name: str) -> DiacriticTable:
    """Build a :class:`DiacriticTable` from parsed JSON data."""
    tone = data.get("tone_levels", {})
    return DiacriticTable(
        name=data.get("name", name),
        combining=_parse_cp_map(data.get("combining", {})),
        suffix=_parse_cp_map(data.get("suffix", {})),
        prefix=_parse_cp_map(data.get("prefix", {})),
        tone_marks={
            int(k, 16): tuple(v) for k, v in data.get("tone_marks", {}).items()
        },
        tone_onset=_parse_levels(tone.get("onset", {})),
        tone_mid=_parse_levels(tone.get("mid", {})),
        tone_offset=_parse_levels(tone.get("offset", {})),
        valued_effects=_parse_valued_effects(data.get("valued_effects", {})),
    )


@cache
def load_diacritics(name: str | None) -> DiacriticTable:
    """Load a diacritic table by name from the layered search path.

    ``None`` or the default name returns the built-in IPA/CLTS table
    unless an override file of that name is found on the search path.
    """
    from merkmal import paths

    if not name:
        return DEFAULT_DIACRITICS
    path = paths.resolve_file("diacritics", f"{name}.json")
    if path is None:
        if name == DEFAULT_DIACRITICS_NAME:
            return DEFAULT_DIACRITICS
        roots = paths.data_roots("diacritics")
        msg = f"Diacritic set not found: {name} (looked in {roots})"
        raise FileNotFoundError(msg)
    data = json.loads(path.read_text(encoding="utf-8"))
    return parse_diacritics(data, name)
