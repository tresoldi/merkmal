"""P-base-derived feature systems with native multi-state support."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache, cached_property
from pathlib import Path

from merkmal.geometry import (
    DEFAULT_GEOMETRY,
    _node_depth,
    valued_geometry_distance,
)
from merkmal.representations import FeatureState, ValuedFeatures, _normalize_valued_query
from merkmal.systems.categorical import normalize_input_grapheme

_PBASE_DIR = Path(__file__).resolve().parent.parent / "data" / "pbase"
_FEATURE_FILE = _PBASE_DIR / "ipa2allfeatures.csv"
_SUPPORTED_FAMILIES = ("hc", "jfh", "spe", "uftc")


# ---------------------------------------------------------------------------
# Geometry mappings: PBase feature name → Clements & Hume geometry node
# ---------------------------------------------------------------------------

_SPE_GEOMETRY: dict[str, str] = {
    "syllabic": "Manner",
    "vocalic": "Manner",
    "consonantal": "Manner",
    "sonorant": "Manner",
    "continuant": "Manner",
    "lateral": "Manner",
    "nasal": "Manner",
    "strident": "Manner",
    "delayed_primary_release": "Manner",
    "delayed_release_of_secondary_closure": "Manner",
    "voice": "Laryngeal",
    "spread": "Laryngeal",
    "heightened_subglottal_pressure": "Laryngeal",
    "glottal_(tertiary)_closure": "Laryngeal",
    "movement_of_glottal_closure": "Laryngeal",
    "covered": "Laryngeal",
    "tense": "TongueRoot",
    "high": "Dorsal",
    "low": "Dorsal",
    "back": "Dorsal",
    "anterior": "Coronal",
    "coronal": "Coronal",
    "distributed": "Coronal",
    "round": "Labial",
    "LONG": "Prosodic",
    "EXTRA": "Prosodic",
}

_HC_GEOMETRY: dict[str, str] = {
    "syllabic": "Manner",
    "vocalic": "Manner",
    "consonantal": "Manner",
    "sonorant": "Manner",
    "continuant": "Manner",
    "lateral": "Manner",
    "nasal": "Manner",
    "strident": "Manner",
    "voice": "Laryngeal",
    "spread": "Laryngeal",
    "constr": "Laryngeal",
    "tense": "TongueRoot",
    "ATR": "TongueRoot",
    "high": "Dorsal",
    "low": "Dorsal",
    "back": "Dorsal",
    "anterior": "Coronal",
    "coronal": "Coronal",
    "distributed": "Coronal",
    "round": "Labial",
    "labial": "Labial",
    "LONG": "Prosodic",
    "EXTRA": "Prosodic",
}

_JFH_GEOMETRY: dict[str, str] = {
    "vocalic ": "Manner",  # trailing space in source data
    "consonantal": "Manner",
    "interrupted": "Manner",
    "nasal": "Manner",
    "strident": "Manner",
    "voiced": "Laryngeal",
    "checked": "Laryngeal",
    "tense": "TongueRoot",
    "compact": "Dorsal",
    "diffuse": "Dorsal",
    "grave": "Place",
    "flat": "Labial",
    "sharp": "Coronal",
    "LONG": "Prosodic",
    "EXTRA": "Prosodic",
}

_UFTC_GEOMETRY: dict[str, str] = {
    "SYLLABIC": "Manner",
    "vocalic": "Manner",
    "vocoid": "Manner",
    "sonorant": "Manner",
    "continuant": "Manner",
    "lateral": "Manner",
    "nasal": "Manner",
    "strident": "Manner",
    "approximant": "Manner",
    "voice": "Laryngeal",
    "spread": "Laryngeal",
    "constricted": "Laryngeal",
    "ATR": "TongueRoot",
    "open1": "Dorsal",
    "open2": "Dorsal",
    "open3": "Dorsal",
    "open4": "Dorsal",
    "open5": "Dorsal",
    "open6": "Dorsal",
    "anterior (any)": "Coronal",
    "anterior (C)": "Coronal",
    "anterior (V)": "Coronal",
    "coronal (any)": "Coronal",
    "coronal (C)": "Coronal",
    "coronal (V)": "Coronal",
    "distributed (any)": "Coronal",
    "distributed (C)": "Coronal",
    "distributed (V)": "Coronal",
    "dorsal (any)": "Dorsal",
    "dorsal (C)": "Dorsal",
    "dorsal (V)": "Dorsal",
    "labial (any)": "Labial",
    "labial (C)": "Labial",
    "labial (V)": "Labial",
    "lingual (any)": "Coronal",
    "lingual (C)": "Coronal",
    "lingual (V)": "Coronal",
    "pharyngeal (any)": "Pharyngeal",
    "pharyngeal (C)": "Pharyngeal",
    "pharyngeal (V)": "Pharyngeal",
    "C-place": "Place",
    "V-place": "Place",
    "LONG": "Prosodic",
    "EXTRA": "Prosodic",
}

_FAMILY_GEOMETRY: dict[str, dict[str, str]] = {
    "spe": _SPE_GEOMETRY,
    "hc": _HC_GEOMETRY,
    "jfh": _JFH_GEOMETRY,
    "uftc": _UFTC_GEOMETRY,
}


def _quantize_state(state: FeatureState) -> float | None:
    """Convert a symbolic feature state to a numeric value for distance.

    Returns ``None`` for DOT (unspecified) — these dimensions are skipped.
    """
    if state == FeatureState.POSITIVE:
        return 1.0
    if state == FeatureState.NEGATIVE:
        return -1.0
    if state == FeatureState.DOT:
        return None
    # N, O, X → neutral / absent
    return 0.0


def _normalize_family(value: str) -> str:
    """Normalize a family name to the internal lowercase form."""
    normalized = value.lower()
    if normalized not in _SUPPORTED_FAMILIES:
        msg = f"Unsupported P-base family: {value!r}"
        raise KeyError(msg)
    return normalized


def _state_from_symbol(value: str) -> FeatureState:
    """Parse a raw symbolic feature value."""
    stripped = value.strip().strip('"')
    return FeatureState(stripped)


def _read_tsv(path: Path) -> list[list[str]]:
    """Read a tab-separated file as rows."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        return list(reader)


@cache
def _pbase_table(family: str) -> dict[str, dict[str, FeatureState]]:
    """Load one bundled P-base feature family with conservative duplicate merging."""
    normalized_family = _normalize_family(family)
    rows = _read_tsv(_FEATURE_FILE)
    header = rows[0]
    body = rows[1:]

    family_columns: list[tuple[int, str]] = []
    for index, raw_name in enumerate(header[1:], start=1):
        name = raw_name.strip().strip('"')
        prefix, suffix = name.split(".", 1)
        if prefix.lower() == normalized_family:
            family_columns.append((index, suffix.strip()))

    result: dict[str, dict[str, FeatureState]] = {}
    for row in body:
        grapheme = normalize_input_grapheme(row[0])
        values = {
            column_name: _state_from_symbol(row[index])
            for index, column_name in family_columns
        }
        existing = result.get(grapheme)
        if existing is None:
            result[grapheme] = values
            continue
        if existing != values:
            result[grapheme] = {
                key: existing[key] if existing[key] == values[key] else FeatureState.DOT
                for key in existing
            }

    return result



@dataclass(frozen=True)
class PBaseFeatureSystem:
    """A bundled P-base-derived feature family."""

    family: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "family", _normalize_family(self.family))

    @property
    def name(self) -> str:
        return f"pbase-{self.family}"

    @property
    def representation_kind(self) -> str:
        return "valued"

    def list_graphemes(self) -> tuple[str, ...]:
        return tuple(sorted(self._table))

    @cached_property
    def _table(self) -> dict[str, dict[str, FeatureState]]:
        return _pbase_table(self.family)

    @cached_property
    def _geometry_map(self) -> dict[str, str]:
        return _FAMILY_GEOMETRY[self.family]

    @cached_property
    def _dimension_weights(self) -> dict[str, float]:
        weights: dict[str, float] = {}
        for feat_name, node_name in self._geometry_map.items():
            depth = _node_depth(DEFAULT_GEOMETRY, node_name, 1) or 2
            weights[feat_name] = 1.0 / depth
        return weights

    def grapheme_to_representation(self, grapheme: str) -> ValuedFeatures | None:
        normalized = normalize_input_grapheme(grapheme)
        values = self._table.get(normalized)
        if values is None:
            return None
        return ValuedFeatures(values=dict(values))

    def class_representation(self, grapheme: str) -> ValuedFeatures | None:
        return None

    def grapheme_to_features(self, grapheme: str) -> frozenset[str] | None:
        representation = self.grapheme_to_representation(grapheme)
        if representation is None:
            return None
        labels = {f"{name}={state.value}" for name, state in representation.values.items()}
        return frozenset(labels)

    def features_to_grapheme(self, features: object) -> str | None:
        if isinstance(features, ValuedFeatures):
            query = features.values
        elif isinstance(features, Mapping):
            query = _normalize_valued_query(features)
        else:
            return None

        for grapheme, values in self._table.items():
            if values == query:
                return grapheme
        return None

    def is_class(self, grapheme: str) -> bool:
        return False

    def class_features(self, grapheme: str) -> frozenset[str] | None:
        return None

    def matches(self, pattern: object, target: object) -> bool:
        if isinstance(pattern, ValuedFeatures):
            query = pattern.values
        elif isinstance(pattern, Mapping):
            query = _normalize_valued_query(pattern)
        else:
            msg = "P-base systems require dict or ValuedFeatures queries."
            raise NotImplementedError(msg)

        if not isinstance(target, ValuedFeatures):
            msg = "P-base matching requires ValuedFeatures targets."
            raise NotImplementedError(msg)

        return all(
            target.values.get(key) == value
            for key, value in query.items()
        )

    def partial_match(self, pattern: frozenset[str], target: frozenset[str]) -> bool:
        msg = "Set-based partial_match is not meaningful for P-base systems."
        raise NotImplementedError(msg)

    def add_features(self, base: frozenset[str], added: frozenset[str]) -> frozenset[str]:
        msg = "Set-based add_features is not meaningful for P-base systems."
        raise NotImplementedError(msg)

    def feature_distance(self, feat_a: str, feat_b: str) -> float:
        return 0.0 if feat_a == feat_b else 1.0

    def segment_distance(
        self, a: object, b: object,
        node_weights: dict[str, float] | str | None = None,
    ) -> float:
        if not isinstance(a, ValuedFeatures) or not isinstance(b, ValuedFeatures):
            msg = "P-base segment_distance requires ValuedFeatures inputs."
            raise NotImplementedError(msg)

        a_quantized = {k: _quantize_state(v) for k, v in a.values.items()}
        b_quantized = {k: _quantize_state(v) for k, v in b.values.items()}

        return valued_geometry_distance(
            a_quantized,
            b_quantized,
            self._geometry_map,
            self._dimension_weights,
            node_weights,
        )

    def sound_distance(
        self, feats_a: frozenset[str], feats_b: frozenset[str],
        node_weights: dict[str, float] | str | None = None,
    ) -> float:
        msg = "Set-based sound_distance is not meaningful for P-base systems."
        raise NotImplementedError(msg)
