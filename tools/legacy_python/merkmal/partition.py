"""Partition-class derivation.

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

The slot choice per system is driven by the ``partitions`` field in
model.json.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

LEVELS: tuple[str, ...] = ("prosody", "coarse", "medium", "fine")


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
    feature_categories: dict[str, str],
) -> tuple[str, ...]:
    by_category: dict[str, list[str]] = {s: [] for s in slots}
    for feat in features:
        cat = feature_categories.get(feat)
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
    partition_slots: dict[str, dict[str, tuple[str, ...]]],
    is_categorical: bool,
    feature_categories: dict[str, str],
) -> _Signature:
    type_name = _ROLE_TO_TYPE_NAME[role]
    if role == "X":
        return _Signature(type_name, (), (), False)
    role_key: str | None = (
        "C" if role in ("C", "R", "G") else "V" if role == "V" else None
    )
    if role_key is None:
        return _Signature(type_name, (), (), not is_categorical)
    level_spec = partition_slots.get(level, {})
    slots = level_spec.get(role_key, ())
    if is_categorical:
        values = _project_categorical(features, slots, feature_categories)
        return _Signature(type_name, slots, values, False)
    values = _project_valued(features, slots)
    return _Signature(type_name, slots, values, True)


def _signature_for_custom(
    features: frozenset[str],
    role: str,
    slots_for_role: dict[str, tuple[str, ...]],
    is_categorical: bool,
    feature_categories: dict[str, str],
) -> _Signature:
    type_name = _ROLE_TO_TYPE_NAME[role]
    if role == "X":
        return _Signature(type_name, (), (), False)
    role_key: str | None = (
        "C" if role in ("C", "R", "G") else "V" if role == "V" else None
    )
    if role_key is None:
        return _Signature(type_name, (), (), not is_categorical)
    slots = slots_for_role.get(role_key, ())
    if is_categorical:
        values = _project_categorical(features, slots, feature_categories)
        return _Signature(type_name, slots, values, False)
    values = _project_valued(features, slots)
    return _Signature(type_name, slots, values, True)


def _prosody_signature(role: str) -> tuple[str, str]:
    return role, role


def _assign_codes(class_fulls: list[str], tentatives: dict[str, str]) -> dict[str, str]:
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


def manifest_features(
    partition_slots: dict[str, dict[str, tuple[str, ...]]],
    is_categorical: bool,
    level: str,
) -> tuple[str, ...]:
    if level == "prosody":
        return ("role",)
    if is_categorical:
        all_feats: list[str] = ["type"]
        spec = partition_slots.get(level, {})
        for role_key in ("C", "V"):
            for slot in spec.get(role_key, ()):
                if slot not in all_feats:
                    all_feats.append(slot)
        return tuple(all_feats)
    spec = partition_slots.get(level, {})
    seen: list[str] = ["type"]
    for role_key in ("C", "V"):
        for slot in spec.get(role_key, ()):
            if slot not in seen:
                seen.append(slot)
    return tuple(seen)


def _valued_feature_names(
    feats_of: dict[str, frozenset[str] | None],
) -> frozenset[str]:
    names: set[str] = set()
    for feats in feats_of.values():
        if not feats:
            continue
        for f in feats:
            name, sep, _ = f.partition("=")
            if sep:
                names.add(name)
    return frozenset(names)


def valid_features_for_system(
    is_categorical: bool,
    feature_categories: dict[str, str],
    feats_of: dict[str, frozenset[str] | None],
) -> frozenset[str]:
    if is_categorical:
        return frozenset(feature_categories.values()) | {"type"}
    return _valued_feature_names(feats_of) | {"type"}


def _infer_custom_slots(
    features: tuple[str, ...],
    is_categorical: bool,
    feature_categories: dict[str, str],
    graphemes: list[str],
    role_of: dict[str, str],
    feats_of: dict[str, frozenset[str] | None],
) -> dict[str, tuple[str, ...]]:
    feat_no_type = tuple(f for f in features if f != "type")
    role_members: dict[str, list[frozenset[str]]] = {"C": [], "V": []}
    for g in graphemes:
        r = role_of.get(g, "X")
        feats = feats_of.get(g) or frozenset()
        if r in ("C", "R", "G"):
            role_members["C"].append(feats)
        elif r == "V":
            role_members["V"].append(feats)
    slots_for_role: dict[str, tuple[str, ...]] = {}
    for role_key, member_feats in role_members.items():
        kept: list[str] = []
        for f in feat_no_type:
            if is_categorical:
                has_value = any(
                    any(feature_categories.get(feat) == f for feat in gf)
                    for gf in member_feats
                )
            else:
                needle = f + "="
                has_value = any(
                    any(feat.startswith(needle) for feat in gf)
                    for gf in member_feats
                )
            if has_value:
                kept.append(f)
        slots_for_role[role_key] = tuple(kept)
    return slots_for_role


def validate_custom_levels(
    is_categorical: bool,
    feature_categories: dict[str, str],
    custom_levels: Mapping[str, Sequence[str]] | None,
    feats_of: dict[str, frozenset[str] | None],
) -> dict[str, tuple[str, ...]]:
    if not custom_levels:
        return {}
    standard = set(LEVELS)
    valid_feats = valid_features_for_system(is_categorical, feature_categories, feats_of)
    canonical: dict[str, tuple[str, ...]] = {}
    for name, feats in custom_levels.items():
        if not name or not isinstance(name, str):
            msg = f"Custom level name must be a non-empty string; got {name!r}"
            raise ValueError(msg)
        if name in standard:
            msg = (
                f"Custom level name {name!r} collides with standard level; "
                f"standard levels are {sorted(standard)}"
            )
            raise ValueError(msg)
        if name in canonical:
            msg = f"Duplicate custom level name: {name!r}"
            raise ValueError(msg)
        feat_list = list(feats) if feats else []
        if not feat_list:
            msg = f"Custom level {name!r} has empty feature list"
            raise ValueError(msg)
        if len(set(feat_list)) != len(feat_list):
            msg = f"Custom level {name!r} has duplicate features: {feat_list}"
            raise ValueError(msg)
        unknown = [f for f in feat_list if f not in valid_feats]
        if unknown:
            preview = ", ".join(sorted(valid_feats))
            msg = (
                f"Custom level {name!r}: unknown feature(s) {unknown!r}. "
                f"Valid features: {preview}"
            )
            raise ValueError(msg)
        canonical[name] = tuple(sorted(feat_list))
    return canonical


def custom_level_slots(
    is_categorical: bool,
    feature_categories: dict[str, str],
    custom_levels: dict[str, tuple[str, ...]],
    graphemes: list[str],
    role_of: dict[str, str],
    feats_of: dict[str, frozenset[str] | None],
) -> dict[str, dict[str, tuple[str, ...]]]:
    return {
        name: _infer_custom_slots(
            feats, is_categorical, feature_categories,
            graphemes, role_of, feats_of,
        )
        for name, feats in custom_levels.items()
    }


@dataclass(frozen=True)
class PartitionRow:
    grapheme: str
    level: str
    class_code: str
    class_full: str


def compute_partitions(
    partition_slots: dict[str, dict[str, tuple[str, ...]]],
    is_categorical: bool,
    feature_categories: dict[str, str],
    graphemes: list[str],
    role_of: dict[str, str],
    feats_of: dict[str, frozenset[str] | None],
    custom_levels: dict[str, tuple[str, ...]] | None = None,
) -> tuple[list[PartitionRow], dict[str, int]]:
    """Build partition rows for every (grapheme, level) pair.

    *partition_slots* comes from model.json ``partitions`` field.
    *is_categorical* determines projection method.
    *feature_categories* is needed for categorical projection.
    """
    custom_levels = custom_levels or {}
    custom_names = tuple(sorted(custom_levels))
    all_levels: tuple[str, ...] = LEVELS + custom_names
    slots_by_custom = custom_level_slots(
        is_categorical, feature_categories, custom_levels,
        graphemes, role_of, feats_of,
    )

    full_per_pair: dict[tuple[str, str], str] = {}
    tentative_per_level: dict[str, dict[str, str]] = {
        level: {} for level in all_levels
    }

    for g in graphemes:
        role = role_of[g]
        feats = feats_of.get(g) or frozenset()

        code, full = _prosody_signature(role)
        full_per_pair[(g, "prosody")] = full
        tentative_per_level["prosody"][full] = code

        for level in LEVELS:
            if level == "prosody":
                continue
            sig = _signature_for(
                feats, role, level,
                partition_slots, is_categorical, feature_categories,
            )
            full = sig.class_full
            full_per_pair[(g, level)] = full
            tentative_per_level[level][full] = sig.tentative_code()

        for name in custom_names:
            sig = _signature_for_custom(
                feats, role, slots_by_custom[name],
                is_categorical, feature_categories,
            )
            full = sig.class_full
            full_per_pair[(g, name)] = full
            tentative_per_level[name][full] = sig.tentative_code()

    full_to_code_per_level: dict[str, dict[str, str]] = {}
    class_counts: dict[str, int] = {}
    for level in all_levels:
        fulls = [full_per_pair[(g, level)] for g in graphemes]
        full_to_code_per_level[level] = _assign_codes(
            fulls, tentative_per_level[level],
        )
        class_counts[level] = len(set(fulls))

    rows: list[PartitionRow] = []
    for g in graphemes:
        for level in all_levels:
            full = full_per_pair[(g, level)]
            code = full_to_code_per_level[level][full]
            rows.append(PartitionRow(g, level, code, full))
    rows.sort(key=lambda r: (r.grapheme, r.level))
    return rows, class_counts


@dataclass(frozen=True)
class PartitionTable:
    """Precomputed partition assignment for all graphemes and levels."""

    rows: list[PartitionRow]
    class_counts: dict[str, int]
    _lookup: dict[tuple[str, str], str]

    def partition(self, level: str, grapheme: str) -> str:
        """Return the class code for a grapheme at a given level."""
        return self._lookup.get((grapheme, level), "")

    def class_count(self, level: str) -> int:
        """Return the number of distinct class codes at a given level."""
        return self.class_counts.get(level, 0)

    @staticmethod
    def levels() -> tuple[str, ...]:
        """Return the standard partition levels."""
        return LEVELS


def build_partition_table(
    partition_slots: dict[str, dict[str, tuple[str, ...]]],
    is_categorical: bool,
    feature_categories: dict[str, str],
    graphemes: list[str],
    role_of: dict[str, str],
    feats_of: dict[str, frozenset[str] | None],
    custom_levels: dict[str, tuple[str, ...]] | None = None,
) -> PartitionTable:
    """Build a PartitionTable for all graphemes and levels."""
    rows, class_counts = compute_partitions(
        partition_slots, is_categorical, feature_categories,
        graphemes, role_of, feats_of, custom_levels,
    )
    lookup: dict[tuple[str, str], str] = {}
    for row in rows:
        lookup[(row.grapheme, row.level)] = row.class_code
    return PartitionTable(rows=rows, class_counts=class_counts, _lookup=lookup)


def unclassified_graphemes(rows: list[PartitionRow]) -> list[str]:
    seen: list[str] = []
    for row in rows:
        if row.level == "prosody" and row.class_code == "X":
            seen.append(row.grapheme)
    return seen


def level_features_by_system(
    partition_slots: dict[str, dict[str, tuple[str, ...]]],
    is_categorical: bool,
) -> dict[str, tuple[str, ...]]:
    return {
        level: manifest_features(partition_slots, is_categorical, level)
        for level in LEVELS
    }


__all__ = [
    "LEVELS",
    "PartitionRow",
    "PartitionTable",
    "build_partition_table",
    "compute_partitions",
    "custom_level_slots",
    "level_features_by_system",
    "manifest_features",
    "unclassified_graphemes",
    "valid_features_for_system",
    "validate_custom_levels",
]
