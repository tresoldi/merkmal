"""Partition-class derivation for the cognator export bundle.

A partition assigns every grapheme of a system to exactly one class
label at a configurable granularity.  The partition is induced by
projecting each grapheme's feature set onto a per-level subset of
features and grouping graphemes whose projected signature is identical.

Four levels are emitted for every system:

- ``prosody`` mirrors the existing prosody.tsv role (C/V/R/G/T/S/X).
- ``coarse`` projects onto the big articulatory divisions (manner for
  consonants, height for vowels).
- ``medium`` adds place (consonants) and centrality (vowels); ~SCA-size.
- ``fine`` adds voicing (consonants) and roundness (vowels).

The slot choice per system is driven by which features are
linguistically load-bearing in that system and is recorded in the
manifest so consumers can audit the derivation.
"""

from __future__ import annotations

from dataclasses import dataclass

from merkmal.systems.categorical import FEATURE_CATEGORIES

LEVELS: tuple[str, ...] = ("prosody", "coarse", "medium", "fine")


_CATEGORICAL_SYSTEMS: frozenset[str] = frozenset(
    {"descriptive", "broad", "distinctive"},
)


# For categorical systems: slot is a category name from FEATURE_CATEGORIES.
# Projection collects, for each slot, the sorted '+'-joined feature
# values whose category equals that slot.
_CATEGORICAL_SLOTS: dict[str, dict[str, tuple[str, ...]]] = {
    "coarse": {"C": ("manner",), "V": ("height",)},
    "medium": {"C": ("manner", "place"), "V": ("height", "centrality")},
    "fine": {
        "C": ("manner", "place", "phonation"),
        "V": ("height", "centrality", "roundedness"),
    },
}


_CATEGORICAL_MANIFEST_FEATURES: dict[str, tuple[str, ...]] = {
    "coarse": ("type", "manner", "height"),
    "medium": ("type", "manner", "place", "height", "centrality"),
    "fine": (
        "type", "manner", "place", "phonation",
        "height", "centrality", "roundedness",
    ),
}


# For valued systems: slot is an exact feature name; projection is the
# state string (e.g., '+', '-', '0') of that feature.  Slot sets are
# nested (coarse ⊂ medium ⊂ fine) so that the resulting partitions
# refine monotonically.
_VALUED_SLOTS: dict[str, dict[str, dict[str, tuple[str, ...]]]] = {
    "phoible": {
        "coarse": {"C": ("sonorant", "continuant"), "V": ("high", "low")},
        "medium": {
            "C": ("sonorant", "continuant", "labial", "coronal", "dorsal"),
            "V": ("high", "low", "back"),
        },
        "fine": {
            "C": (
                "sonorant", "continuant", "labial", "coronal", "dorsal",
                "periodicGlottalSource",
            ),
            "V": ("high", "low", "back", "round"),
        },
    },
    "classfeat": {
        "coarse": {"C": ("sonorant", "continuant"), "V": ("high", "back")},
        "medium": {
            "C": ("sonorant", "continuant", "labial", "coronal", "dorsal"),
            "V": ("high", "back"),
        },
        "fine": {
            "C": (
                "sonorant", "continuant", "labial", "coronal", "dorsal", "voice",
            ),
            "V": ("high", "back", "round"),
        },
    },
    "pbase-hc": {
        "coarse": {"C": ("sonorant", "continuant"), "V": ("high", "low")},
        "medium": {
            "C": ("sonorant", "continuant", "labial", "coronal"),
            "V": ("high", "low", "back"),
        },
        "fine": {
            "C": ("sonorant", "continuant", "labial", "coronal", "voice"),
            "V": ("high", "low", "back", "round"),
        },
    },
    "pbase-spe": {
        "coarse": {"C": ("sonorant", "continuant"), "V": ("high", "low")},
        "medium": {
            "C": ("sonorant", "continuant", "coronal", "anterior"),
            "V": ("high", "low", "back"),
        },
        "fine": {
            "C": ("sonorant", "continuant", "coronal", "anterior", "voice"),
            "V": ("high", "low", "back", "round"),
        },
    },
    "pbase-jfh": {
        "coarse": {"C": ("consonantal", "nasal"), "V": ("compact",)},
        "medium": {
            "C": ("consonantal", "nasal", "grave", "strident"),
            "V": ("compact", "diffuse", "grave"),
        },
        "fine": {
            "C": ("consonantal", "nasal", "grave", "strident", "voiced"),
            "V": ("compact", "diffuse", "grave", "flat"),
        },
    },
    "pbase-uftc": {
        "coarse": {
            "C": ("sonorant", "continuant"),
            "V": ("SYLLABIC", "open1"),
        },
        "medium": {
            "C": (
                "sonorant", "continuant",
                "coronal (any)", "dorsal (any)", "labial (any)",
            ),
            "V": ("SYLLABIC", "open1", "open3", "open5"),
        },
        "fine": {
            "C": (
                "sonorant", "continuant",
                "coronal (any)", "dorsal (any)", "labial (any)", "voice",
            ),
            "V": ("SYLLABIC", "open1", "open3", "open5"),
        },
    },
}


_ROLE_TO_TYPE_NAME: dict[str, str] = {
    "C": "consonant",
    "R": "consonant",
    "G": "consonant",
    "V": "vowel",
    "T": "tone",
    "S": "suprasegmental",
    "X": "unclassified",
}


_TYPE_CODE: dict[str, str] = {
    "consonant": "C",
    "vowel": "V",
    "tone": "T",
    "suprasegmental": "S",
    "unclassified": "X",
}


@dataclass(frozen=True)
class _Signature:
    """The projected class signature for one (grapheme, level) pair."""

    type_name: str
    slot_names: tuple[str, ...]
    slot_values: tuple[str, ...]
    valued: bool

    @property
    def class_full(self) -> str:
        if self.type_name == "unclassified":
            return "unclassified"
        parts: list[str] = [self.type_name]
        if self.valued:
            for name, value in zip(self.slot_names, self.slot_values, strict=True):
                parts.append(f"{name}={value}" if value else f"{name}=?")
        else:
            parts.extend(v if v else "?" for v in self.slot_values)
        return "|".join(parts)

    def tentative_code(self) -> str:
        if self.type_name == "unclassified":
            return "X"
        prefix = _TYPE_CODE[self.type_name]
        if not self.slot_values:
            return prefix
        shorts = [
            _valued_short(v) if self.valued else _categorical_short(v)
            for v in self.slot_values
        ]
        return f"{prefix}.{''.join(shorts)}"


def _valued_short(value: str) -> str:
    if not value:
        return "x"
    mapping = {"+": "p", "-": "n", "0": "z"}
    ch = value[0]
    return mapping.get(ch, ch.lower())


def _categorical_short(value: str) -> str:
    if not value:
        return "x"
    return value[0].lower()


def _project_categorical(
    features: frozenset[str],
    slots: tuple[str, ...],
) -> tuple[str, ...]:
    by_category: dict[str, list[str]] = {s: [] for s in slots}
    for feat in features:
        cat = FEATURE_CATEGORIES.get(feat)
        if cat in by_category:
            by_category[cat].append(feat)
    return tuple(
        "+".join(sorted(by_category[s])) for s in slots
    )


def _project_valued(
    features: frozenset[str],
    slots: tuple[str, ...],
) -> tuple[str, ...]:
    feat_map: dict[str, str] = {}
    for feat in features:
        name, sep, state = feat.partition("=")
        if sep:
            feat_map[name] = state
    return tuple(feat_map.get(s, "") for s in slots)


def _signature_for(
    features: frozenset[str],
    role: str,
    level: str,
    system: str,
) -> _Signature:
    type_name = _ROLE_TO_TYPE_NAME[role]
    if role == "X":
        return _Signature(type_name, (), (), False)
    role_key: str | None = (
        "C" if role in ("C", "R", "G") else "V" if role == "V" else None
    )
    if role_key is None:
        # T or S: type only, no further slots.
        return _Signature(type_name, (), (), False)
    if system in _CATEGORICAL_SYSTEMS:
        slots = _CATEGORICAL_SLOTS[level].get(role_key, ())
        values = _project_categorical(features, slots)
        return _Signature(type_name, slots, values, False)
    spec = _VALUED_SLOTS.get(system, {})
    slots = spec.get(level, {}).get(role_key, ())
    values = _project_valued(features, slots)
    return _Signature(type_name, slots, values, True)


def _prosody_signature(role: str) -> tuple[str, str]:
    """Return (class_code, class_full) for the prosody level."""
    return role, role


def _assign_codes(class_fulls: list[str], tentatives: dict[str, str]) -> dict[str, str]:
    """Resolve collisions in tentative codes; return class_full → class_code."""
    unique = sorted(set(class_fulls))
    groups: dict[str, list[str]] = {}
    for full in unique:
        groups.setdefault(tentatives[full], []).append(full)
    result: dict[str, str] = {}
    for code, fulls in groups.items():
        if len(fulls) == 1:
            result[fulls[0]] = code
        else:
            for idx, full in enumerate(fulls, start=1):
                result[full] = f"{code}_{idx}"
    return result


def manifest_features(system: str, level: str) -> tuple[str, ...]:
    """Return the feature-subset description for *system* at *level*."""
    if level == "prosody":
        return ("role",)
    if system in _CATEGORICAL_SYSTEMS:
        return _CATEGORICAL_MANIFEST_FEATURES[level]
    spec = _VALUED_SLOTS.get(system, {}).get(level, {})
    seen: list[str] = ["type"]
    for role_key in ("C", "V"):
        for slot in spec.get(role_key, ()):
            if slot not in seen:
                seen.append(slot)
    return tuple(seen)


@dataclass(frozen=True)
class PartitionRow:
    grapheme: str
    level: str
    class_code: str
    class_full: str


def compute_partitions(
    system: str,
    graphemes: list[str],
    role_of: dict[str, str],
    feats_of: dict[str, frozenset[str] | None],
) -> tuple[list[PartitionRow], dict[str, int]]:
    """Build partition rows for every (grapheme, level) pair.

    Returns (rows, class_counts) where *rows* is sorted by (grapheme,
    level) and *class_counts* maps level → number of distinct classes.
    """
    # Gather class_full per (grapheme, level); resolve codes per level.
    full_per_pair: dict[tuple[str, str], str] = {}
    tentative_per_level: dict[str, dict[str, str]] = {
        level: {} for level in LEVELS
    }

    for g in graphemes:
        role = role_of[g]
        feats = feats_of.get(g) or frozenset()

        # Prosody level.
        code, full = _prosody_signature(role)
        full_per_pair[(g, "prosody")] = full
        tentative_per_level["prosody"][full] = code

        # Other levels.
        for level in LEVELS:
            if level == "prosody":
                continue
            sig = _signature_for(feats, role, level, system)
            full = sig.class_full
            full_per_pair[(g, level)] = full
            tentative_per_level[level][full] = sig.tentative_code()

    full_to_code_per_level: dict[str, dict[str, str]] = {}
    class_counts: dict[str, int] = {}
    for level in LEVELS:
        fulls = [full_per_pair[(g, level)] for g in graphemes]
        full_to_code_per_level[level] = _assign_codes(
            fulls, tentative_per_level[level],
        )
        class_counts[level] = len(set(fulls))

    rows: list[PartitionRow] = []
    for g in graphemes:
        for level in LEVELS:
            full = full_per_pair[(g, level)]
            code = full_to_code_per_level[level][full]
            rows.append(PartitionRow(g, level, code, full))
    rows.sort(key=lambda r: (r.grapheme, r.level))
    return rows, class_counts


def unclassified_graphemes(rows: list[PartitionRow]) -> list[str]:
    """Return graphemes whose prosody role is 'X' (unclassified)."""
    seen: list[str] = []
    for row in rows:
        if row.level == "prosody" and row.class_code == "X":
            seen.append(row.grapheme)
    return seen


def level_features_by_system(system: str) -> dict[str, tuple[str, ...]]:
    """Return per-level feature lists for *system* (manifest)."""
    return {level: manifest_features(system, level) for level in LEVELS}


def _system_has_spec(system: str) -> bool:
    return system in _CATEGORICAL_SYSTEMS or system in _VALUED_SLOTS


def supported_systems() -> frozenset[str]:
    return frozenset(_CATEGORICAL_SYSTEMS | frozenset(_VALUED_SLOTS))


__all__ = [
    "LEVELS",
    "PartitionRow",
    "compute_partitions",
    "level_features_by_system",
    "manifest_features",
    "supported_systems",
    "unclassified_graphemes",
]
