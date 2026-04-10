"""PHOIBLE-derived feature system with geometry-aware valued distance."""

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

_PHOIBLE_DIR = Path(__file__).resolve().parent.parent / "data" / "phoible"
_SEGMENT_FILE = _PHOIBLE_DIR / "segments.tsv"

# PHOIBLE uses +/-/0 encoding; map to FeatureState.
_SYMBOL_MAP: dict[str, FeatureState] = {
    "+": FeatureState.POSITIVE,
    "-": FeatureState.NEGATIVE,
    "0": FeatureState.DOT,
}

# ---------------------------------------------------------------------------
# PHOIBLE feature → C&H geometry node mapping (37 features)
# ---------------------------------------------------------------------------

_PHOIBLE_GEOMETRY: dict[str, str] = {
    "tone": "Tonal",
    "stress": "Prosodic",
    "syllabic": "Manner",
    "short": "Prosodic",
    "long": "Prosodic",
    "consonantal": "Manner",
    "sonorant": "Manner",
    "continuant": "Manner",
    "delayedRelease": "Manner",
    "approximant": "Manner",
    "tap": "Manner",
    "trill": "Manner",
    "nasal": "Manner",
    "lateral": "Manner",
    "labial": "Labial",
    "round": "Labial",
    "labiodental": "Labial",
    "coronal": "Coronal",
    "anterior": "Coronal",
    "distributed": "Coronal",
    "strident": "Coronal",
    "dorsal": "Dorsal",
    "high": "Dorsal",
    "low": "Dorsal",
    "front": "Dorsal",
    "back": "Dorsal",
    "tense": "TongueRoot",
    "retractedTongueRoot": "TongueRoot",
    "advancedTongueRoot": "TongueRoot",
    "periodicGlottalSource": "Laryngeal",
    "epilaryngealSource": "Laryngeal",
    "spreadGlottis": "Laryngeal",
    "constrictedGlottis": "Laryngeal",
    "fortis": "Laryngeal",
    "lenis": "Laryngeal",
    "raisedLarynxEjective": "Laryngeal",
    "loweredLarynxImplosive": "Laryngeal",
    "click": "Manner",
}


def _state_from_symbol(value: str) -> FeatureState:
    """Parse a PHOIBLE feature value."""
    return _SYMBOL_MAP.get(value.strip(), FeatureState.DOT)


def _quantize_state(state: FeatureState) -> float | None:
    """Convert a symbolic feature state to a numeric value for distance."""
    if state == FeatureState.POSITIVE:
        return 1.0
    if state == FeatureState.NEGATIVE:
        return -1.0
    if state == FeatureState.DOT:
        return None
    return 0.0


@cache
def _phoible_table() -> tuple[tuple[str, ...], dict[str, dict[str, FeatureState]]]:
    """Load bundled PHOIBLE segments TSV. Returns (feature_names, table)."""
    with _SEGMENT_FILE.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader)
        feature_names = tuple(header[1:])
        table: dict[str, dict[str, FeatureState]] = {}
        for row in reader:
            phoneme = normalize_input_grapheme(row[0])
            values = {
                feature_names[i]: _state_from_symbol(row[i + 1])
                for i in range(len(feature_names))
            }
            table[phoneme] = values
    return feature_names, table


@dataclass(frozen=True)
class PhoibleFeatureSystem:
    """PHOIBLE-derived valued feature system with geometry-aware distance."""

    @property
    def name(self) -> str:
        return "phoible"

    @property
    def representation_kind(self) -> str:
        return "valued"

    @cached_property
    def _feature_names(self) -> tuple[str, ...]:
        return _phoible_table()[0]

    @cached_property
    def _table(self) -> dict[str, dict[str, FeatureState]]:
        return _phoible_table()[1]

    @cached_property
    def _dimension_weights(self) -> dict[str, float]:
        weights: dict[str, float] = {}
        for feat_name, node_name in _PHOIBLE_GEOMETRY.items():
            depth = _node_depth(DEFAULT_GEOMETRY, node_name, 1) or 2
            weights[feat_name] = 1.0 / depth
        return weights

    def list_graphemes(self) -> tuple[str, ...]:
        return tuple(sorted(self._table))

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
            msg = "PHOIBLE system requires dict or ValuedFeatures queries."
            raise NotImplementedError(msg)
        if not isinstance(target, ValuedFeatures):
            msg = "PHOIBLE matching requires ValuedFeatures targets."
            raise NotImplementedError(msg)
        return all(
            target.values.get(key) == value
            for key, value in query.items()
        )

    def partial_match(self, pattern: frozenset[str], target: frozenset[str]) -> bool:
        msg = "Set-based partial_match is not meaningful for PHOIBLE system."
        raise NotImplementedError(msg)

    def add_features(self, base: frozenset[str], added: frozenset[str]) -> frozenset[str]:
        msg = "Set-based add_features is not meaningful for PHOIBLE system."
        raise NotImplementedError(msg)

    def feature_distance(self, feat_a: str, feat_b: str) -> float:
        return 0.0 if feat_a == feat_b else 1.0

    def segment_distance(
        self, a: object, b: object,
        node_weights: dict[str, float] | str | None = None,
    ) -> float:
        if not isinstance(a, ValuedFeatures) or not isinstance(b, ValuedFeatures):
            msg = "PHOIBLE segment_distance requires ValuedFeatures inputs."
            raise NotImplementedError(msg)
        a_quantized = {k: _quantize_state(v) for k, v in a.values.items()}
        b_quantized = {k: _quantize_state(v) for k, v in b.values.items()}
        return valued_geometry_distance(
            a_quantized,
            b_quantized,
            _PHOIBLE_GEOMETRY,
            self._dimension_weights,
            node_weights,
        )

    def sound_distance(
        self, feats_a: frozenset[str], feats_b: frozenset[str],
        node_weights: dict[str, float] | str | None = None,
    ) -> float:
        msg = "Set-based sound_distance is not meaningful for PHOIBLE system."
        raise NotImplementedError(msg)
