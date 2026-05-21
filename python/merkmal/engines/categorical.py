"""Categorical feature engine (descriptive, broad, distinctive).

Parses IPA sound names into feature sets, computes distances via
geometry tree. Supports optional scalar dimension overlay
(distinctive features).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

from merkmal.grapheme import (
    decompose_grapheme,
    normalize_input_grapheme,
    normalize_output_grapheme,
    normalize_sequences,
)
from merkmal.representations import CategoricalFeatures

if TYPE_CHECKING:
    from merkmal.geometry import Geometry
    from merkmal.model import ModelConfig


FEATURE_ALIASES: dict[str, str] = {
    "plosive": "stop",
}


def resolve_alias(feature: str) -> str:
    return FEATURE_ALIASES.get(feature, feature)


def parse_sound_name(
    name: str,
    *,
    feature_categories: dict[str, str],
    filter_categories: bool = True,
) -> frozenset[str]:
    features: set[str] = set()
    for word in name.split():
        value = word.lower().strip().replace("_", "-")
        if value and (not filter_categories or value in feature_categories):
            features.add(value)
    return frozenset(features)


_NON_PULMONIC_FEATURES: frozenset[str] = frozenset({"click", "nasal-click", "implosive"})


def _enrich_click_features(features: frozenset[str]) -> frozenset[str]:
    if not (features & _NON_PULMONIC_FEATURES):
        return features
    added: set[str] = {"non-pulmonic"}
    if "click" in features or "nasal-click" in features:
        added.add("velar")
    return features | added


# ── Engine class ────────────────────────────────────────────────────────

@dataclass
class CategoricalEngine:
    """Unified categorical engine for descriptive, broad, and distinctive models."""

    config: ModelConfig
    geometry: Geometry

    representation_kind: str = "categorical"

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def feature_categories(self) -> dict[str, str]:
        return self.config.feature_categories

    @property
    def filter_categories(self) -> bool:
        return self.config.feature_extraction == "filtered"

    @cached_property
    def _grapheme_table(self) -> dict[str, frozenset[str]]:
        table: dict[str, frozenset[str]] = {}
        for row in self.config.inventory_rows:
            grapheme, sound_name = row[0], row[1]
            features = parse_sound_name(
                sound_name,
                feature_categories=self.feature_categories,
                filter_categories=self.filter_categories,
            )
            if features:
                table[normalize_input_grapheme(grapheme)] = features
        return table

    @cached_property
    def _reverse_table(self) -> dict[frozenset[str], str]:
        result: dict[frozenset[str], str] = {}
        for grapheme, features in self._grapheme_table.items():
            if features not in result:
                result[features] = normalize_output_grapheme(grapheme)
        return result

    @cached_property
    def _class_table(self) -> dict[str, frozenset[str]]:
        result: dict[str, frozenset[str]] = {}
        for class_name, (_, feat_str, _) in self.config.classes_data.items():
            if feat_str:
                features = frozenset(
                    v.strip() for v in feat_str.split(",") if v.strip()
                )
                if features:
                    result[class_name] = features
        return result

    # ── Scalar dimensions (distinctive) ─────────────────────────────────

    @cached_property
    def _scalar_dims(self) -> tuple[dict, ...]:
        return self.config.scalar_dimensions

    @cached_property
    def _dimension_weights(self) -> dict[str, float]:
        if not self._scalar_dims:
            return {}
        weights: dict[str, float] = {}
        for dim in self._scalar_dims:
            depth = self.geometry.node_depth(dim["geometry_node"])
            weights[dim["name"]] = 1.0 / depth
        return weights

    def _features_to_scalar(self, features: frozenset[str]) -> dict[str, float]:
        result: dict[str, float] = {}
        for dim in self._scalar_dims:
            positive = frozenset(dim["positive"])
            negative = frozenset(dim["negative"])
            if features & positive:
                result[dim["name"]] = 1.0
            elif negative and features & negative:
                result[dim["name"]] = -1.0
        return result

    # ── FeatureSystem protocol ──────────────────────────────────────────

    def list_graphemes(self) -> tuple[str, ...]:
        return tuple(
            sorted(normalize_output_grapheme(g) for g in self._grapheme_table)
        )

    def grapheme_to_features(self, grapheme: str) -> frozenset[str] | None:
        normalized = normalize_input_grapheme(grapheme)
        result = self._grapheme_table.get(normalized)
        if result is not None:
            return _enrich_click_features(result)
        for candidate in normalize_sequences(normalized):
            result = self._grapheme_table.get(candidate)
            if result is not None:
                return _enrich_click_features(result)
        result = self._resolve_tie_bar(normalized)
        if result is not None:
            return _enrich_click_features(result)
        base, added = decompose_grapheme(normalized)
        if base != normalized:
            base_features = self._grapheme_table.get(base)
            if base_features is None:
                base_features = self._resolve_tie_bar(base)
            if base_features is not None:
                return _enrich_click_features(base_features | added)
        lookup_base = base if base != normalized else normalized
        result = self._resolve_polyphthong(lookup_base)
        if result is not None:
            return _enrich_click_features(result | added)
        return None

    def _resolve_tie_bar(self, grapheme: str) -> frozenset[str] | None:
        for tie in ("͡", "͜"):
            if tie in grapheme:
                parts = grapheme.split(tie, maxsplit=1)
                if len(parts) == 2:
                    feats_a = self._grapheme_table.get(parts[0])
                    feats_b = self._grapheme_table.get(parts[1])
                    if feats_a is not None and feats_b is not None:
                        return feats_a | feats_b
        return None

    def _resolve_polyphthong(self, grapheme: str) -> frozenset[str] | None:
        if len(grapheme) < 2:
            return None
        segments: list[frozenset[str]] = []
        i = 0
        while i < len(grapheme):
            matched = False
            for end in range(len(grapheme), i, -1):
                candidate = grapheme[i:end]
                feats = self._grapheme_table.get(candidate)
                if feats is not None:
                    segments.append(feats)
                    i = end
                    matched = True
                    break
            if not matched:
                return None
        if len(segments) < 2:
            return None
        if not all("vowel" in seg_feats for seg_feats in segments):
            return None
        result: frozenset[str] = frozenset()
        for seg_feats in segments:
            result = result | seg_feats
        return result

    def grapheme_to_representation(self, grapheme: str) -> CategoricalFeatures | None:
        features = self.grapheme_to_features(grapheme)
        if features is None:
            return None
        return CategoricalFeatures(values=features)

    def features_to_grapheme(self, features: object) -> str | None:
        if not isinstance(features, frozenset):
            return None
        return self._reverse_table.get(features)

    def is_class(self, grapheme: str) -> bool:
        return grapheme in self._class_table

    def class_features(self, grapheme: str) -> frozenset[str] | None:
        return self._class_table.get(grapheme)

    def class_representation(self, grapheme: str) -> CategoricalFeatures | None:
        features = self.class_features(grapheme)
        if features is None:
            return None
        return CategoricalFeatures(values=features)

    def add_features(
        self, base: frozenset[str], added: frozenset[str],
    ) -> frozenset[str]:
        from merkmal.common import add_features
        return add_features(base, added, self.feature_categories, resolve_alias)

    def partial_match(
        self, pattern: frozenset[str], target: frozenset[str],
    ) -> bool:
        from merkmal.common import partial_match
        return partial_match(pattern, target)

    def matches(self, pattern: object, target: object) -> bool:
        if (
            not isinstance(pattern, CategoricalFeatures)
            or not isinstance(target, CategoricalFeatures)
        ):
            msg = f"{self.name} matching requires CategoricalFeatures inputs."
            raise NotImplementedError(msg)
        return self.partial_match(pattern.values, target.values)

    def feature_distance(self, feat_a: str, feat_b: str) -> float:
        return float(self.geometry.feature_distance(feat_a, feat_b))

    def sound_distance(
        self,
        feats_a: frozenset[str],
        feats_b: frozenset[str],
        node_weights: dict[str, float] | str | None = None,
    ) -> float:
        if self._scalar_dims:
            return self._scalar_sound_distance(feats_a, feats_b, node_weights)
        return self.geometry.sound_distance(feats_a, feats_b, node_weights)

    def _scalar_sound_distance(
        self,
        feats_a: frozenset[str],
        feats_b: frozenset[str],
        node_weights: dict[str, float] | str | None = None,
    ) -> float:
        if feats_a == feats_b:
            return 0.0

        from merkmal.geometry import (
            _FLAT_SENTINEL,
            _build_ancestor_map,
            _resolve_node_weight,
            resolve_node_weights,
        )

        resolved = resolve_node_weights(self.geometry, node_weights)
        flat = resolved is _FLAT_SENTINEL
        ancestor_map = (
            _build_ancestor_map(self.geometry.tree) if resolved and not flat else {}
        )

        scalars_a = self._features_to_scalar(feats_a)
        scalars_b = self._features_to_scalar(feats_b)
        total_weight = 0.0
        total_diff = 0.0

        for dim in self._scalar_dims:
            if flat:
                weight = 1.0
            else:
                nw = (
                    _resolve_node_weight(
                        dim["geometry_node"], resolved, ancestor_map,
                    )
                    if resolved
                    else 1.0
                )
                weight = self._dimension_weights[dim["name"]] * nw
            value_a = scalars_a.get(dim["name"], 0.0)
            value_b = scalars_b.get(dim["name"], 0.0)

            if value_a == 0.0 and value_b == 0.0:
                continue

            total_weight += weight
            divisor = 1.0 if not dim["negative"] else 2.0
            total_diff += weight * abs(value_a - value_b) / divisor

        if total_weight > 0:
            return total_diff / total_weight
        return 0.0

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
            msg = f"{self.name} segment_distance requires CategoricalFeatures inputs."
            raise NotImplementedError(msg)
        return self.sound_distance(a.values, b.values, node_weights)

    # Extra methods for distinctive compat
    def grapheme_to_scalars(self, grapheme: str) -> dict[str, float] | None:
        if not self._scalar_dims:
            return None
        features = self.grapheme_to_features(grapheme)
        if features is None:
            return None
        return self._features_to_scalar(features)

    def features_to_scalars(self, features: frozenset[str]) -> dict[str, float]:
        return self._features_to_scalar(features)

    @property
    def dimensions(self) -> tuple[dict, ...]:
        return self._scalar_dims
