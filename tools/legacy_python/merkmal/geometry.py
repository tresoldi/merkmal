"""Phonological feature geometry tree.

Loads geometry definitions from JSON files. Provides tree-structured
distance computation for both categorical and valued feature systems.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from merkmal.typology import Typology


@dataclass(frozen=True)
class FeatureNode:
    """Leaf: a binary phonological feature."""

    name: str
    positive: str
    negative: str

    @property
    def is_privative(self) -> bool:
        return not self.negative


@dataclass(frozen=True)
class GeometryNode:
    """Internal node grouping features."""

    name: str
    children: tuple[GeometryNode | FeatureNode, ...]

    def all_features(self) -> frozenset[str]:
        result: set[str] = set()
        for child in self.children:
            if isinstance(child, FeatureNode):
                if child.positive:
                    result.add(child.positive)
                if child.negative:
                    result.add(child.negative)
            else:
                result |= child.all_features()
        return frozenset(result)

    def find_feature(self, value: str) -> FeatureNode | None:
        for child in self.children:
            if isinstance(child, FeatureNode):
                if child.name == value or child.positive == value or child.negative == value:
                    return child
            else:
                result = child.find_feature(value)
                if result is not None:
                    return result
        return None

    def _matches_feature(self, node: FeatureNode, value: str) -> bool:
        return node.name == value or node.positive == value or node.negative == value

    def find_parent(self, value: str) -> GeometryNode | None:
        for child in self.children:
            if isinstance(child, FeatureNode):
                if self._matches_feature(child, value):
                    return self
            elif isinstance(child, GeometryNode):
                if child.name.lower() == value.lower():
                    return self
                for grandchild in child.children:
                    if isinstance(grandchild, FeatureNode) and self._matches_feature(
                        grandchild, value
                    ):
                        return child
                result = child.find_parent(value)
                if result is not None:
                    return result
        return None

    def siblings_of(self, value: str) -> frozenset[str]:
        parent = self.find_parent(value)
        if parent is None:
            return frozenset()
        result: set[str] = set()
        for child in parent.children:
            if isinstance(child, FeatureNode):
                if child.positive and child.positive != value:
                    result.add(child.positive)
                if child.negative and child.negative != value:
                    result.add(child.negative)
        return frozenset(result)

    def _depth_of(self, value: str, depth: int = 0) -> int | None:
        for child in self.children:
            if isinstance(child, FeatureNode):
                if self._matches_feature(child, value):
                    return depth + 1
            else:
                result = child._depth_of(value, depth + 1)
                if result is not None:
                    return result
        return None

    def _path_to(self, value: str) -> list[str] | None:
        for child in self.children:
            if isinstance(child, FeatureNode):
                if self._matches_feature(child, value):
                    return [self.name, child.name, value]
            elif isinstance(child, GeometryNode):
                sub = child._path_to(value)
                if sub is not None:
                    return [self.name, *sub]
        return None

    def feature_distance(self, a: str, b: str) -> int:
        if a == b:
            return 0
        path_a = self._path_to(a)
        path_b = self._path_to(b)
        if path_a is None or path_b is None:
            return 999
        common = 0
        for left, right in zip(path_a, path_b, strict=False):
            if left == right:
                common += 1
            else:
                break
        return (len(path_a) - common) + (len(path_b) - common)

    def sound_distance(
        self,
        feats_a: frozenset[str],
        feats_b: frozenset[str],
        node_weights: dict[str, float] | str | None = None,
        feature_to_node: dict[str, str] | None = None,
    ) -> float:
        if feats_a == feats_b:
            return 0.0

        resolved = resolve_node_weights(self, node_weights)
        flat = resolved is _FLAT_SENTINEL
        ancestor_map = _build_ancestor_map(self) if resolved and not flat else {}
        ftn = feature_to_node or {}

        total_weight = 0.0
        total_diff = 0.0

        for leaf, depth, parent_name in _iter_leaves(self, 1):
            if flat:
                weight = 1.0
            else:
                nw = (
                    _resolve_node_weight(parent_name, resolved, ancestor_map)
                    if resolved
                    else 1.0
                )
                weight = nw / depth
            total_weight += weight

            a_has_pos = leaf.positive in feats_a if leaf.positive else False
            a_has_neg = leaf.negative in feats_a if leaf.negative else False
            b_has_pos = leaf.positive in feats_b if leaf.positive else False
            b_has_neg = leaf.negative in feats_b if leaf.negative else False

            if not (a_has_pos or a_has_neg or b_has_pos or b_has_neg):
                total_weight -= weight
                continue

            a_val = 1.0 if a_has_pos else (-1.0 if a_has_neg else 0.0)
            b_val = 1.0 if b_has_pos else (-1.0 if b_has_neg else 0.0)
            divisor = 1.0 if leaf.is_privative else 2.0
            total_diff += weight * abs(a_val - b_val) / divisor

        leaf_feats: set[str] = set()
        for leaf, _, _ in _iter_leaves(self, 1):
            if leaf.positive:
                leaf_feats.add(leaf.positive)
            if leaf.negative:
                leaf_feats.add(leaf.negative)

        node_groups: dict[str, tuple[set[str], set[str]]] = {}
        for feat in sorted(feats_a | feats_b):
            if feat in leaf_feats:
                continue
            node = ftn.get(feat)
            if node is None:
                continue
            if node not in node_groups:
                node_groups[node] = (set(), set())
            if feat in feats_a:
                node_groups[node][0].add(feat)
            if feat in feats_b:
                node_groups[node][1].add(feat)

        for node_name, (a_set, b_set) in node_groups.items():
            if flat:
                weight = 1.0
            else:
                depth = _node_depth(self, node_name, 1) or 2
                nw = (
                    _resolve_node_weight(node_name, resolved, ancestor_map)
                    if resolved
                    else 1.0
                )
                weight = nw / depth
            total_weight += weight

            if a_set == b_set:
                continue
            total_diff += weight

        return total_diff / total_weight if total_weight > 0 else 0.0

    def directed_sound_distance(
        self,
        feats_a: frozenset[str],
        feats_b: frozenset[str],
        typology: Typology,
        node_weights: dict[str, float] | str | None = None,
        feature_to_node: dict[str, str] | None = None,
    ) -> float:
        if feats_a == feats_b:
            return 0.0

        resolved = resolve_node_weights(self, node_weights)
        flat = resolved is _FLAT_SENTINEL
        ancestor_map = _build_ancestor_map(self) if resolved and not flat else {}
        ftn = feature_to_node or {}

        total_weight = 0.0
        total_diff = 0.0

        for leaf, depth, parent_name in _iter_leaves(self, 1):
            if flat:
                weight = 1.0
            else:
                nw = (
                    _resolve_node_weight(parent_name, resolved, ancestor_map)
                    if resolved
                    else 1.0
                )
                weight = nw / depth
            total_weight += weight

            a_has_pos = leaf.positive in feats_a if leaf.positive else False
            a_has_neg = leaf.negative in feats_a if leaf.negative else False
            b_has_pos = leaf.positive in feats_b if leaf.positive else False
            b_has_neg = leaf.negative in feats_b if leaf.negative else False

            if not (a_has_pos or a_has_neg or b_has_pos or b_has_neg):
                total_weight -= weight
                continue

            a_val = 1.0 if a_has_pos else (-1.0 if a_has_neg else 0.0)
            b_val = 1.0 if b_has_pos else (-1.0 if b_has_neg else 0.0)
            diff = a_val - b_val
            divisor = 1.0 if leaf.is_privative else 2.0
            total_diff += weight * typology.cost_for(leaf.name, diff) / divisor

        leaf_feats: set[str] = set()
        for leaf, _, _ in _iter_leaves(self, 1):
            if leaf.positive:
                leaf_feats.add(leaf.positive)
            if leaf.negative:
                leaf_feats.add(leaf.negative)

        node_groups: dict[str, tuple[set[str], set[str]]] = {}
        for feat in sorted(feats_a | feats_b):
            if feat in leaf_feats:
                continue
            node = ftn.get(feat)
            if node is None:
                continue
            if node not in node_groups:
                node_groups[node] = (set(), set())
            if feat in feats_a:
                node_groups[node][0].add(feat)
            if feat in feats_b:
                node_groups[node][1].add(feat)

        for node_name, (a_set, b_set) in node_groups.items():
            if flat:
                weight = 1.0
            else:
                depth = _node_depth(self, node_name, 1) or 2
                nw = (
                    _resolve_node_weight(node_name, resolved, ancestor_map)
                    if resolved
                    else 1.0
                )
                weight = nw / depth
            total_weight += weight

            if a_set == b_set:
                continue
            total_diff += weight

        return total_diff / total_weight if total_weight > 0 else 0.0


# ── Geometry object (tree + metadata) ───────────────────────────────────

class Geometry:
    """A loaded geometry: tree + feature-to-node mapping + presets."""

    def __init__(
        self,
        tree: GeometryNode,
        feature_to_node: dict[str, str],
        weight_presets: dict[str, Any],
        name: str = "",
    ) -> None:
        self.tree = tree
        self.feature_to_node = feature_to_node
        self.weight_presets = weight_presets
        self.name = name

    def sound_distance(
        self,
        feats_a: frozenset[str],
        feats_b: frozenset[str],
        node_weights: dict[str, float] | str | None = None,
    ) -> float:
        return self.tree.sound_distance(
            feats_a, feats_b, node_weights,
            feature_to_node=self.feature_to_node,
        )

    def feature_distance(self, a: str, b: str) -> int:
        return self.tree.feature_distance(a, b)

    def valued_distance(
        self,
        a_values: dict[str, float | None],
        b_values: dict[str, float | None],
        geometry_map: dict[str, str],
        dimension_weights: dict[str, float],
        node_weights: dict[str, float] | str | None = None,
    ) -> float:
        return valued_geometry_distance(
            self.tree, a_values, b_values,
            geometry_map, dimension_weights, node_weights,
        )

    def directed_sound_distance(
        self,
        feats_a: frozenset[str],
        feats_b: frozenset[str],
        typology: Typology,
        node_weights: dict[str, float] | str | None = None,
    ) -> float:
        return self.tree.directed_sound_distance(
            feats_a, feats_b, typology, node_weights,
            feature_to_node=self.feature_to_node,
        )

    def directed_valued_distance(
        self,
        a_values: dict[str, float | None],
        b_values: dict[str, float | None],
        geometry_map: dict[str, str],
        dimension_weights: dict[str, float],
        typology: Typology,
        node_weights: dict[str, float] | str | None = None,
    ) -> float:
        return directed_valued_geometry_distance(
            self.tree, a_values, b_values,
            geometry_map, dimension_weights, typology, node_weights,
        )

    def node_depth(self, node_name: str) -> int:
        return _node_depth(self.tree, node_name, 1) or 2


# ── Loading from JSON ───────────────────────────────────────────────────

def _node_from_json(data: dict[str, Any]) -> GeometryNode | FeatureNode:
    if "positive" in data:
        return FeatureNode(
            name=data["name"],
            positive=data["positive"],
            negative=data.get("negative", ""),
        )
    children = tuple(_node_from_json(c) for c in data.get("children", []))
    return GeometryNode(name=data["name"], children=children)


@cache
def load_geometry(name: str) -> Geometry:
    from merkmal import paths

    path = paths.resolve_file("geometries", f"{name}.json")
    if path is None:
        roots = paths.data_roots("geometries")
        msg = f"Geometry not found: {name} (looked in {roots})"
        raise FileNotFoundError(msg)

    data = json.loads(path.read_text(encoding="utf-8"))
    tree = _node_from_json(data["tree"])
    assert isinstance(tree, GeometryNode)

    ftn = data.get("feature_to_node", {})

    presets_raw = data.get("weight_presets", {})
    presets: dict[str, Any] = {}
    for k, v in presets_raw.items():
        if v == "__flat__":
            presets[k] = _FLAT_SENTINEL
        else:
            presets[k] = v

    geom = Geometry(
        tree=tree,
        feature_to_node=ftn,
        weight_presets=presets,
        name=name,
    )
    return geom


# ── Internal helpers (same algorithms as before) ────────────────────────

def _iter_leaves(
    node: GeometryNode, depth: int,
) -> list[tuple[FeatureNode, int, str]]:
    result: list[tuple[FeatureNode, int, str]] = []
    for child in node.children:
        if isinstance(child, FeatureNode):
            result.append((child, depth, node.name))
        else:
            result.extend(_iter_leaves(child, depth + 1))
    return result


def _node_depth(root: GeometryNode, name: str, depth: int) -> int | None:
    if root.name == name:
        return depth
    for child in root.children:
        if isinstance(child, GeometryNode):
            result = _node_depth(child, name, depth + 1)
            if result is not None:
                return result
    return None


def _build_ancestor_map(
    node: GeometryNode, ancestors: tuple[str, ...] = (),
) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {node.name: ancestors}
    for child in node.children:
        if isinstance(child, GeometryNode):
            result.update(
                _build_ancestor_map(child, (*ancestors, node.name)),
            )
    return result


def _resolve_node_weight(
    name: str,
    node_weights: dict[str, float],
    ancestor_map: dict[str, tuple[str, ...]],
) -> float:
    weight = node_weights.get(name, 1.0)
    for ancestor in ancestor_map.get(name, ()):
        weight *= node_weights.get(ancestor, 1.0)
    return weight


_FLAT_SENTINEL: dict[str, float] = {"__flat__": 1.0}


def resolve_node_weights(
    geom: GeometryNode | Geometry,
    weights: dict[str, float] | str | None,
) -> dict[str, float] | None:
    if weights is None or isinstance(weights, dict):
        return weights
    if isinstance(geom, Geometry):
        presets = geom.weight_presets
    else:
        presets = getattr(geom, "_weight_presets", {})
    if weights in presets:
        return cast("dict[str, float]", presets[weights])
    # Fallback to built-in presets
    builtin: dict[str, dict[str, float]] = {
        "ignore-tone": {"Tonal": 0.0},
        "ignore-prosodic": {"Prosodic": 0.0},
        "segmental": {"Tonal": 0.0, "Prosodic": 0.0},
        "tone-heavy": {"Tonal": 2.0},
        "tone-only": {
            "Laryngeal": 0.0, "Manner": 0.0, "Place": 0.0,
            "TongueRoot": 0.0, "Prosodic": 0.0,
        },
        "flat": _FLAT_SENTINEL,
    }
    if weights in builtin:
        return builtin[weights]
    valid = ", ".join(sorted({*presets, *builtin}))
    msg = f"Unknown node_weights preset: {weights!r}. Valid presets: {valid}"
    raise ValueError(msg)


def valued_geometry_distance(
    tree: GeometryNode,
    a_values: dict[str, float | None],
    b_values: dict[str, float | None],
    geometry_map: dict[str, str],
    dimension_weights: dict[str, float],
    node_weights: dict[str, float] | str | None = None,
) -> float:
    if a_values == b_values:
        return 0.0

    resolved = resolve_node_weights(tree, node_weights)
    flat = resolved is _FLAT_SENTINEL
    ancestor_map = _build_ancestor_map(tree) if resolved and not flat else {}

    total_weight = 0.0
    total_diff = 0.0

    all_keys = sorted(a_values.keys() | b_values.keys())
    for key in all_keys:
        val_a = a_values.get(key)
        val_b = b_values.get(key)

        if val_a is None or val_b is None:
            continue
        if val_a == 0.0 and val_b == 0.0:
            continue

        node_name = geometry_map.get(key)
        if node_name is None:
            continue

        if flat:
            weight = 1.0
        else:
            base_w = dimension_weights.get(key, 0.5)
            nw = (
                _resolve_node_weight(node_name, resolved, ancestor_map)
                if resolved
                else 1.0
            )
            weight = base_w * nw
        total_weight += weight
        total_diff += weight * abs(val_a - val_b) / 2.0

    return total_diff / total_weight if total_weight > 0 else 0.0


def directed_valued_geometry_distance(
    tree: GeometryNode,
    a_values: dict[str, float | None],
    b_values: dict[str, float | None],
    geometry_map: dict[str, str],
    dimension_weights: dict[str, float],
    typology: Typology,
    node_weights: dict[str, float] | str | None = None,
) -> float:
    if a_values == b_values:
        return 0.0

    resolved = resolve_node_weights(tree, node_weights)
    flat = resolved is _FLAT_SENTINEL
    ancestor_map = _build_ancestor_map(tree) if resolved and not flat else {}

    total_weight = 0.0
    total_diff = 0.0

    all_keys = sorted(a_values.keys() | b_values.keys())
    for key in all_keys:
        val_a = a_values.get(key)
        val_b = b_values.get(key)

        if val_a is None or val_b is None:
            continue
        if val_a == 0.0 and val_b == 0.0:
            continue

        node_name = geometry_map.get(key)
        if node_name is None:
            continue

        if flat:
            weight = 1.0
        else:
            base_w = dimension_weights.get(key, 0.5)
            nw = (
                _resolve_node_weight(node_name, resolved, ancestor_map)
                if resolved
                else 1.0
            )
            weight = base_w * nw
        total_weight += weight
        diff = val_a - val_b
        total_diff += weight * typology.cost_for(key, diff) / 2.0

    return total_diff / total_weight if total_weight > 0 else 0.0
