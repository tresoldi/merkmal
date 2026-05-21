"""Valued feature engine (phoible, pbase-*).

Loads explicit feature matrices from inventory.tsv. Computes distances
via geometry-weighted valued-feature comparison.
"""

from __future__ import annotations

import contextlib
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

from merkmal.geometry import _node_depth, valued_geometry_distance
from merkmal.grapheme import normalize_input_grapheme
from merkmal.representations import FeatureState, ValuedFeatures, _normalize_valued_query

if TYPE_CHECKING:
    from merkmal.geometry import Geometry
    from merkmal.model import ModelConfig


def _quantize_state(state: FeatureState) -> float | None:
    if state == FeatureState.POSITIVE:
        return 1.0
    if state == FeatureState.NEGATIVE:
        return -1.0
    if state == FeatureState.DOT:
        return None
    return 0.0


@dataclass
class ValuedEngine:
    """Unified valued-feature engine for PHOIBLE and P-base systems."""

    config: ModelConfig
    geometry: Geometry

    representation_kind: str = "valued"

    @property
    def name(self) -> str:
        return self.config.name

    @cached_property
    def _state_symbols(self) -> dict[str, FeatureState]:
        raw = self.config.raw.get("state_symbols", {"+": 1.0, "-": -1.0, "0": None})
        result: dict[str, FeatureState] = {}
        for symbol in raw:
            with contextlib.suppress(ValueError):
                result[symbol] = FeatureState(symbol)
        if not result:
            result = {
                "+": FeatureState.POSITIVE,
                "-": FeatureState.NEGATIVE,
            }
        return result

    @cached_property
    def _feature_names(self) -> tuple[str, ...]:
        return tuple(self.config.inventory_header[1:])

    @cached_property
    def _table(self) -> dict[str, dict[str, FeatureState]]:
        table: dict[str, dict[str, FeatureState]] = {}
        feat_names = self._feature_names
        for row in self.config.inventory_rows:
            grapheme = normalize_input_grapheme(row[0])
            values: dict[str, FeatureState] = {}
            for i, feat in enumerate(feat_names):
                raw_val = row[i + 1].strip().strip('"') if i + 1 < len(row) else "."
                try:
                    values[feat] = FeatureState(raw_val)
                except ValueError:
                    values[feat] = FeatureState.DOT
            existing = table.get(grapheme)
            if existing is None:
                table[grapheme] = values
            elif existing != values:
                table[grapheme] = {
                    key: existing[key] if existing[key] == values[key] else FeatureState.DOT
                    for key in existing
                }
        return table

    @cached_property
    def _geometry_map(self) -> dict[str, str]:
        return self.config.raw.get("geometry_map", {})

    @cached_property
    def _dimension_weights(self) -> dict[str, float]:
        weights: dict[str, float] = {}
        for feat_name, node_name in self._geometry_map.items():
            depth = _node_depth(self.geometry.tree, node_name, 1) or 2
            weights[feat_name] = 1.0 / depth
        return weights

    # ── FeatureSystem protocol ──────────────────────────────────────────

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
            msg = f"{self.name} requires dict or ValuedFeatures queries."
            raise NotImplementedError(msg)
        if not isinstance(target, ValuedFeatures):
            msg = f"{self.name} matching requires ValuedFeatures targets."
            raise NotImplementedError(msg)
        return all(
            target.values.get(key) == value
            for key, value in query.items()
        )

    def partial_match(self, pattern: frozenset[str], target: frozenset[str]) -> bool:
        msg = f"Set-based partial_match is not meaningful for {self.name}."
        raise NotImplementedError(msg)

    def add_features(self, base: frozenset[str], added: frozenset[str]) -> frozenset[str]:
        msg = f"Set-based add_features is not meaningful for {self.name}."
        raise NotImplementedError(msg)

    def feature_distance(self, feat_a: str, feat_b: str) -> float:
        return 0.0 if feat_a == feat_b else 1.0

    def segment_distance(
        self, a: object, b: object,
        node_weights: dict[str, float] | str | None = None,
    ) -> float:
        if not isinstance(a, ValuedFeatures) or not isinstance(b, ValuedFeatures):
            msg = f"{self.name} segment_distance requires ValuedFeatures inputs."
            raise NotImplementedError(msg)
        a_quantized = {k: _quantize_state(v) for k, v in a.values.items()}
        b_quantized = {k: _quantize_state(v) for k, v in b.values.items()}
        return valued_geometry_distance(
            self.geometry.tree,
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
        msg = f"Set-based sound_distance is not meaningful for {self.name}."
        raise NotImplementedError(msg)
