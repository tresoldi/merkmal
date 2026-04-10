"""Shared base class for categorical feature systems (IPA, Tresoldi, Distinctive)."""

from __future__ import annotations

import unicodedata
from functools import cached_property
from typing import TYPE_CHECKING

import merkmal.common as common
from merkmal.representations import CategoricalFeatures

if TYPE_CHECKING:
    from merkmal.dataset import FeatureDataset


def resolve_alias(feature: str) -> str:
    """Resolve a feature alias to its canonical form."""
    return FEATURE_ALIASES.get(feature, feature)


FEATURE_ALIASES: dict[str, str] = {
    "plosive": "stop",
}

FEATURE_CATEGORIES: dict[str, str] = {
    "plosive": "manner",
    "stop": "manner",
    "fricative": "manner",
    "affricate": "manner",
    "nasal": "manner",
    "approximant": "manner",
    "trill": "manner",
    "tap": "manner",
    "lateral": "manner",
    "click": "manner",
    "implosive": "manner",
    "nasal-click": "manner",
    "non-pulmonic": "airstream",
    "bilabial": "place",
    "labio-dental": "place",
    "labio-velar": "place",
    "labio-palatal": "place",
    "dental": "place",
    "alveolar": "place",
    "post-alveolar": "place",
    "alveolo-palatal": "place",
    "retroflex": "place",
    "palatal": "place",
    "palatal-velar": "place",
    "velar": "place",
    "uvular": "place",
    "pharyngeal": "place",
    "epiglottal": "place",
    "glottal": "place",
    "linguolabial": "place",
    "labial": "place",
    "close": "height",
    "near-close": "height",
    "close-mid": "height",
    "mid": "height",
    "open-mid": "height",
    "near-open": "height",
    "open": "height",
    "front": "centrality",
    "near-front": "centrality",
    "central": "centrality",
    "near-back": "centrality",
    "back": "centrality",
    "rounded": "roundedness",
    "unrounded": "roundedness",
    "less-rounded": "rounding",
    "more-rounded": "rounding",
    "voiced": "phonation",
    "voiceless": "phonation",
    "consonant": "type",
    "vowel": "type",
    "long": "duration",
    "mid-long": "duration",
    "ultra-long": "duration",
    "ultra-short": "duration",
    "nasalized": "nasalization",
    "labialized": "labialization",
    "palatalized": "palatalization",
    "labio-palatalized": "palatalization",
    "velarized": "velarization",
    "pharyngealized": "pharyngealization",
    "aspirated": "aspiration",
    "glottalized": "glottalization",
    "breathy": "breathiness",
    "creaky": "creakiness",
    "ejective": "ejection",
    "rhotacized": "rhotacization",
    "syllabic": "syllabicity",
    "non-syllabic": "syllabicity",
    "sibilant": "sibilancy",
    "devoiced": "voicing",
    "revoiced": "voicing",
    "advanced": "relative_articulation",
    "retracted": "relative_articulation",
    "centralized": "relative_articulation",
    "mid-centralized": "relative_articulation",
    "raised": "raising",
    "lowered": "raising",
    "strong": "articulation",
    "unreleased": "release",
    "with-lateral-release": "release",
    "with-nasal-release": "release",
    "with-mid-central-vowel-release": "release",
    "with-frication": "frication",
    "advanced-tongue-root": "tongue_root",
    "retracted-tongue-root": "tongue_root",
    "apical": "laminality",
    "laminal": "laminality",
    "pre-aspirated": "preceding",
    "pre-glottalized": "preceding",
    "pre-labialized": "preceding",
    "pre-nasalized": "preceding",
    "pre-palatalized": "preceding",
    "primary-stress": "stress",
    "secondary-stress": "stress",
    "tone-onset-upper": "tone",
    "tone-onset-lower": "tone",
    "tone-onset-raised": "tone",
    "tone-onset-lowered": "tone",
    "tone-mid-upper": "tone",
    "tone-mid-lower": "tone",
    "tone-mid-raised": "tone",
    "tone-mid-lowered": "tone",
    "tone-offset-upper": "tone",
    "tone-offset-lower": "tone",
    "tone-offset-raised": "tone",
    "tone-offset-lowered": "tone",
}


def parse_sound_name(
    name: str, *, filter_categories: bool = True,
) -> frozenset[str]:
    """Parse a sound NAME string from sounds.tsv into a feature set.

    When *filter_categories* is ``True`` (default), only words present
    in ``FEATURE_CATEGORIES`` are kept.  When ``False``, all words are
    kept (the Tresoldi system's broader representation).
    """
    features: set[str] = set()
    for word in name.split():
        value = word.lower().strip().replace("_", "-")
        if value and (not filter_categories or value in FEATURE_CATEGORIES):
            features.add(value)
    return frozenset(features)


# ---------------------------------------------------------------------------
# Compositional decomposition: combining marks and modifier letters
# ---------------------------------------------------------------------------

# Tone combining marks → (onset, mid, offset) on a 1-5 Chao scale.
# Level tones: mid = onset = offset.  Contour tones: mid = average
# rounded toward neutral (3).  circumflex (4,2) → mid=3; caron (2,4) → mid=3.
# Superscript Chao tone digits (used in CLDF/Lexibank segmented data).
_CHAO_SUPERSCRIPT_DIGITS: frozenset[str] = frozenset("⁰¹²³⁴⁵")

_TONE_MARK_TO_LEVELS: dict[int, tuple[int, int, int]] = {
    0x030B: (5, 5, 5),  # double acute  → extra-high
    0x0301: (4, 4, 4),  # acute         → high
    0x0304: (3, 3, 3),  # macron        → mid
    0x0300: (2, 2, 2),  # grave         → low
    0x030F: (1, 1, 1),  # double grave  → extra-low
    0x0302: (4, 3, 2),  # circumflex    → falling (mid=3)
    0x030C: (2, 3, 4),  # caron         → rising  (mid=3)
}

# Binary register/height features for each Chao level (Yip 1980 / Bao 1999).
# Mid (level 3) is underspecified (empty set).
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
    """Return the tonal feature set for a given onset/mid/offset level triple."""
    return (
        _LEVEL_TO_ONSET_FEATURES[onset]
        | _LEVEL_TO_MID_FEATURES[mid]
        | _LEVEL_TO_OFFSET_FEATURES[offset]
    )


# Combining marks (Unicode category M*) → feature they add to the base.
# Applied after NFD normalization decomposes the grapheme.
# NOTE: tone diacritics are handled separately via _TONE_MARK_TO_LEVELS.
_COMBINING_TO_FEATURE: dict[int, str] = {
    # Phonation
    0x0325: "devoiced",               # ring below
    0x030A: "devoiced",               # ring above
    0x032C: "revoiced",               # caron below
    0x0330: "creaky",                 # tilde below
    0x0324: "breathy",                # diaeresis below
    # Nasalization
    0x0303: "nasalized",              # tilde
    # Syllabicity
    0x0329: "syllabic",              # vertical line below
    0x030D: "syllabic",              # vertical line above
    0x032F: "non-syllabic",          # inverted breve below
    # Place modifiers
    0x032A: "dental",                # bridge below
    0x031F: "advanced",              # plus sign below
    0x0320: "retracted",             # minus sign below
    0x0318: "advanced-tongue-root",  # left tack below
    0x0319: "retracted-tongue-root", # right tack below
    0x033A: "apical",                # inverted bridge below
    0x033B: "laminal",               # square below
    0x033C: "linguolabial",          # seagull below
    # Height / centrality modifiers
    0x031D: "raised",                # up tack below
    0x031E: "lowered",               # down tack below
    0x0308: "centralized",           # diaeresis (above)
    0x033D: "mid-centralized",       # x above
    # Rounding modifiers
    0x031C: "less-rounded",          # left half ring below
    0x0339: "more-rounded",          # right half ring below
    # Length
    0x0306: "ultra-short",           # breve
    # Release / strength
    0x031A: "unreleased",            # left angle above
    0x0348: "strong",                # double vertical line below
}

# Modifier letters (Unicode category Lm/Sk) appearing *after* the base.
_SUFFIX_MODIFIER_TO_FEATURE: dict[int, str] = {
    0x02D0: "long",                  # ː triangular colon
    0x02D1: "mid-long",              # ˑ half triangular colon
    0x02B0: "aspirated",             # ʰ
    0x02B1: "breathy",               # ʱ
    0x02B2: "palatalized",           # ʲ
    0x02B7: "labialized",            # ʷ
    0x02E0: "velarized",             # ˠ
    0x02E4: "pharyngealized",        # ˤ
    0x02C0: "glottalized",           # ˀ
    0x02BC: "ejective",              # ʼ
    0x1DA3: "labio-palatalized",     # ᶣ
    0x207F: "with-nasal-release",    # ⁿ
    0x02DE: "rhotacized",            # ˞
    0x02E1: "with-lateral-release",  # ˡ
}

# Same modifier letters when they appear *before* the base get a ``pre-`` prefix.
_PREFIX_MODIFIER_TO_FEATURE: dict[int, str] = {
    0x02B0: "pre-aspirated",         # ʰ
    0x02C0: "pre-glottalized",       # ˀ
    0x207F: "pre-nasalized",         # ⁿ
    0x02B7: "pre-labialized",        # ʷ
    0x02B2: "pre-palatalized",       # ʲ
}

_ALL_MODIFIER_CPS: frozenset[int] = frozenset(
    _SUFFIX_MODIFIER_TO_FEATURE.keys() | _PREFIX_MODIFIER_TO_FEATURE.keys()
)

_IPA_EQUIVALENCES: dict[str, str] = {
    "\u0261": "g",
    "\u2019": "\u02bc",
    "\u0027": "\u02bc",
}

_IPA_REVERSE: dict[str, str] = {
    value: key for key, value in _IPA_EQUIVALENCES.items()
}


def normalize_output_grapheme(grapheme: str) -> str:
    """Map canonical output forms back to preferred IPA graphemes."""
    return "".join(_IPA_REVERSE.get(char, char) for char in grapheme)


def normalize_input_grapheme(grapheme: str) -> str:
    """Normalize lookup graphemes with NFD and IPA equivalences."""
    normalized = unicodedata.normalize("NFD", grapheme)
    return "".join(_IPA_EQUIVALENCES.get(char, char) for char in normalized)


def decompose_grapheme(grapheme: str) -> tuple[str, frozenset[str]]:
    """Decompose an NFD-normalized grapheme into base + modifier features.

    Strips known combining marks (including tone diacritics), prefix
    modifier letters, and suffix modifier letters.  Returns
    ``(base, added_features)`` where *base* is the remaining string and
    *added_features* is the frozenset of feature names contributed by
    the stripped modifiers.

    Tone combining marks are expanded to onset/offset register/height
    features via the Yip/Bao binary model.

    The input *grapheme* must already be NFD-normalised and have IPA
    equivalence substitutions applied (i.e. the output of
    ``normalize_input_grapheme``).
    """
    features: set[str] = set()

    # 1. Strip prefix modifier letters.
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

    # 2. Walk the rest: pull out combining marks, suffix modifiers,
    #    and trailing Chao tone digits.
    base_chars: list[str] = []
    chao_chars: list[str] = []
    remainder = grapheme[prefix_end:]

    # Pre-scan: detect trailing superscript Chao digits.
    # They appear at the end of the grapheme after merge_tone_digits().
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

    # 3. Parse trailing Chao digits into onset/offset tone features.
    if chao_chars:
        from merkmal.segmentation import parse_chao_digits

        parsed = parse_chao_digits("".join(chao_chars))
        if parsed is not None:
            onset, mid, offset = parsed
            features |= tone_features_for_levels(onset, mid, offset)

    return "".join(base_chars), frozenset(features)


# ---------------------------------------------------------------------------
# Reverse map: feature name → modifier character (for composition)
# ---------------------------------------------------------------------------

def _build_feature_to_modifier() -> dict[str, str]:
    """Build a feature-name → modifier-character map for composition.

    Suffix modifier letters take priority over combining marks when
    both map to the same feature name (suffix letters are more common
    in IPA transcription).
    """
    result: dict[str, str] = {}
    # Combining marks first (lower priority).
    for cp, feat in _COMBINING_TO_FEATURE.items():
        result.setdefault(feat, chr(cp))
    # Suffix modifiers override.
    for cp, feat in _SUFFIX_MODIFIER_TO_FEATURE.items():
        result[feat] = chr(cp)
    return result


_FEATURE_TO_MODIFIER: dict[str, str] = _build_feature_to_modifier()


def available_modifiers() -> tuple[str, ...]:
    """Return all modifier feature names usable for composition."""
    return tuple(sorted(_FEATURE_TO_MODIFIER))


def compose_grapheme(base: str, modifiers: frozenset[str]) -> str:
    """Attach modifier characters to a base grapheme string.

    Returns an NFD-normalised IPA string with combining marks and
    modifier letters appended in a deterministic order.
    """
    suffix: list[str] = []
    for feat in sorted(modifiers):
        char = _FEATURE_TO_MODIFIER.get(feat)
        if char is not None:
            suffix.append(char)
    return base + "".join(suffix)


def build_class_table(
    dataset: FeatureDataset,
) -> dict[str, frozenset[str]]:
    """Build SOUND_CLASS -> feature set from the dataset."""
    result: dict[str, frozenset[str]] = {}
    for class_name, feat_str in dataset.class_features.items():
        if feat_str:
            features = frozenset(
                value.strip()
                for value in feat_str.split(",")
                if value.strip()
            )
            if features:
                result[class_name] = features
    return result


_NON_PULMONIC_FEATURES: frozenset[str] = frozenset({"click", "nasal-click", "implosive"})


def _enrich_click_features(features: frozenset[str]) -> frozenset[str]:
    """Add non-pulmonic airstream and velar posterior closure to clicks.

    Clicks always involve a posterior velar closure in addition to the
    anterior place of articulation.  Implosives use a glottalic
    ingressive airstream.  Both are marked as ``non-pulmonic``, and
    clicks additionally receive ``velar`` to reflect the posterior
    closure.
    """
    if not (features & _NON_PULMONIC_FEATURES):
        return features
    added: set[str] = {"non-pulmonic"}
    if "click" in features or "nasal-click" in features:
        added.add("velar")
    return features | added


class CategoricalFeatureSystem:
    """Shared base for categorical (frozenset-based) feature systems."""

    representation_kind: str = "categorical"

    @property
    def name(self) -> str:
        raise NotImplementedError

    @property
    def _grapheme_table(self) -> dict[str, frozenset[str]]:
        raise NotImplementedError

    def list_graphemes(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                normalize_output_grapheme(g)
                for g in self._grapheme_table
            )
        )

    @cached_property
    def _reverse_table(self) -> dict[frozenset[str], str]:
        result: dict[frozenset[str], str] = {}
        for grapheme, features in self._grapheme_table.items():
            if features not in result:
                result[features] = normalize_output_grapheme(grapheme)
        return result

    @cached_property
    def _class_table(self) -> dict[str, frozenset[str]]:
        return build_class_table(self.dataset)  # type: ignore[attr-defined]

    def grapheme_to_features(
        self, grapheme: str,
    ) -> frozenset[str] | None:
        normalized = normalize_input_grapheme(grapheme)

        # Exact table lookup.
        result = self._grapheme_table.get(normalized)
        if result is not None:
            return _enrich_click_features(result)

        # Tie bar: split into components, look up each, union features.
        result = self._resolve_tie_bar(normalized)
        if result is not None:
            return _enrich_click_features(result)

        # Compositional fallback: decompose and look up the base.
        base, added = decompose_grapheme(normalized)
        if base != normalized:
            # The base itself may contain a tie bar.
            base_features = self._grapheme_table.get(base)
            if base_features is None:
                base_features = self._resolve_tie_bar(base)
            if base_features is not None:
                return _enrich_click_features(base_features | added)

        # Diphthong/polyphthong fallback: if the base contains multiple
        # characters that are each individually known graphemes, union
        # their features.  This handles sequences like "aɪ", "eɪ", "aʊ".
        lookup_base = base if base != normalized else normalized
        result = self._resolve_polyphthong(lookup_base)
        if result is not None:
            return _enrich_click_features(result | added)

        return None

    def _resolve_tie_bar(
        self, grapheme: str,
    ) -> frozenset[str] | None:
        """Split a tie-bar grapheme into components, union their features."""
        for tie in ("\u0361", "\u035C"):
            if tie in grapheme:
                parts = grapheme.split(tie, maxsplit=1)
                if len(parts) == 2:
                    feats_a = self._grapheme_table.get(parts[0])
                    feats_b = self._grapheme_table.get(parts[1])
                    if feats_a is not None and feats_b is not None:
                        return feats_a | feats_b
        return None

    def _resolve_polyphthong(
        self, grapheme: str,
    ) -> frozenset[str] | None:
        """Split a multi-segment grapheme into components, union their features.

        Handles diphthongs (aɪ, eɪ, aʊ) and triphthongs (aɪə) by
        splitting the NFD-normalized string into segments via the
        grapheme table.  Uses a greedy longest-match scan so that
        multi-character base graphemes (e.g. two-letter IPA symbols)
        are correctly identified.

        Returns the unioned feature set, or None if any component is
        unknown or the grapheme is a single known segment.
        """
        if len(grapheme) < 2:
            return None

        # Greedy left-to-right segmentation: try longest prefix first.
        segments: list[frozenset[str]] = []
        i = 0
        while i < len(grapheme):
            matched = False
            # Try substrings from longest to shortest.
            for end in range(len(grapheme), i, -1):
                candidate = grapheme[i:end]
                feats = self._grapheme_table.get(candidate)
                if feats is not None:
                    segments.append(feats)
                    i = end
                    matched = True
                    break
            if not matched:
                return None  # Unknown component → give up.

        if len(segments) < 2:
            return None  # Single segment, not a polyphthong.

        # All components must be vowels (contain the "vowel" feature).
        if not all("vowel" in seg_feats for seg_feats in segments):
            return None

        result: frozenset[str] = frozenset()
        for seg_feats in segments:
            result = result | seg_feats
        return result

    def grapheme_to_representation(
        self, grapheme: str,
    ) -> CategoricalFeatures | None:
        features = self.grapheme_to_features(grapheme)
        if features is None:
            return None
        return CategoricalFeatures(values=features)

    def features_to_grapheme(
        self, features: object,
    ) -> str | None:
        if not isinstance(features, frozenset):
            return None
        return self._reverse_table.get(features)

    def is_class(self, grapheme: str) -> bool:
        return grapheme in self._class_table

    def class_features(
        self, grapheme: str,
    ) -> frozenset[str] | None:
        return self._class_table.get(grapheme)

    def class_representation(
        self, grapheme: str,
    ) -> CategoricalFeatures | None:
        features = self.class_features(grapheme)
        if features is None:
            return None
        return CategoricalFeatures(values=features)

    def add_features(
        self,
        base: frozenset[str],
        added: frozenset[str],
    ) -> frozenset[str]:
        return common.add_features(
            base, added, FEATURE_CATEGORIES, resolve_alias,
        )

    def partial_match(
        self,
        pattern: frozenset[str],
        target: frozenset[str],
    ) -> bool:
        return common.partial_match(pattern, target)

    def matches(self, pattern: object, target: object) -> bool:
        if (
            not isinstance(pattern, CategoricalFeatures)
            or not isinstance(target, CategoricalFeatures)
        ):
            msg = (
                f"{self.name} matching requires"
                " CategoricalFeatures inputs."
            )
            raise NotImplementedError(msg)
        return self.partial_match(pattern.values, target.values)

    def feature_distance(
        self, feat_a: str, feat_b: str,
    ) -> float:
        return common.feature_distance(feat_a, feat_b)

    def segment_distance(
        self,
        a: object,
        b: object,
        node_weights: dict[str, float] | str | None = None,
    ) -> float:
        if (
            not isinstance(a, CategoricalFeatures)
            or not isinstance(b, CategoricalFeatures)
        ):
            msg = (
                f"{self.name} segment_distance requires"
                " CategoricalFeatures inputs."
            )
            raise NotImplementedError(msg)
        return self.sound_distance(a.values, b.values, node_weights)

    def sound_distance(
        self,
        feats_a: frozenset[str],
        feats_b: frozenset[str],
        node_weights: dict[str, float] | str | None = None,
    ) -> float:
        return common.sound_distance(feats_a, feats_b, node_weights)
