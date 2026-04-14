"""Phonological feature geometry tree (Clements & Hume 1995)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureNode:
    """Leaf: a binary phonological feature."""

    name: str
    positive: str
    negative: str

    @property
    def is_privative(self) -> bool:
        """True if this feature has no negative pole (presence/absence only)."""
        return not self.negative


@dataclass(frozen=True)
class GeometryNode:
    """Internal node grouping features."""

    name: str
    children: tuple[GeometryNode | FeatureNode, ...]

    def all_features(self) -> frozenset[str]:
        """All leaf positive/negative values in this subtree."""
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
        """Lookup a FeatureNode by name, positive, or negative value."""
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
        """Check if a FeatureNode matches by name, positive, or negative value."""
        return node.name == value or node.positive == value or node.negative == value

    def find_parent(self, value: str) -> GeometryNode | None:
        """Find the parent GeometryNode of a feature value.

        Matches against FeatureNode name, positive, and negative fields.
        Also matches GeometryNode names (returning *their* parent).
        """
        for child in self.children:
            if isinstance(child, FeatureNode):
                if self._matches_feature(child, value):
                    return self
            elif isinstance(child, GeometryNode):
                # If a child GeometryNode itself matches the name,
                # return *this* node as its parent.
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
        """Sibling feature values under the same parent."""
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
        """Find depth of a feature value in the tree."""
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
        """Find path from root to a feature value (including the value itself)."""
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
        """Tree edge distance between two feature values."""
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
    ) -> float:
        """Normalized distance between two feature sets using tree structure.

        *node_weights* optionally scales the contribution of each named
        geometry node.  Pass a dict or a preset name string (e.g.
        ``"ignore-tone"``).  Weights propagate multiplicatively through
        the tree: ``{"Tonal": 0.5}`` halves *all* tonal features (both
        TonalOnset and TonalOffset inherit the factor).  An explicit
        child weight multiplies with its ancestors:
        ``{"Tonal": 0.5, "TonalOnset": 2.0}`` gives TonalOnset an
        effective weight of 1.0.  Nodes absent from the dict default
        to 1.0.
        """
        if feats_a == feats_b:
            return 0.0

        resolved = resolve_node_weights(node_weights)
        flat = resolved is _FLAT_SENTINEL
        ancestor_map = _build_ancestor_map(self) if resolved and not flat else {}

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

        # Collect features already handled by the leaf pass so we don't
        # double-count them in the node-group pass below.
        leaf_feats: set[str] = set()
        for leaf, _, _ in _iter_leaves(self, 1):
            if leaf.positive:
                leaf_feats.add(leaf.positive)
            if leaf.negative:
                leaf_feats.add(leaf.negative)

        # Sort the union so node_groups' insertion order (and hence the
        # ``for node_name, ... in node_groups.items()`` loop below) is
        # deterministic. Without sorted(), Python's hash randomization
        # makes this loop's order differ across processes, and
        # floating-point non-associativity in the ``total_diff +=``
        # accumulation then makes sound_distance return bitwise-different
        # results across runs.
        node_groups: dict[str, tuple[set[str], set[str]]] = {}
        for feat in sorted(feats_a | feats_b):
            if feat in leaf_feats:
                continue
            node = FEATURE_TO_GEOMETRY_NODE.get(feat)
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


def _iter_leaves(
    node: GeometryNode, depth: int,
) -> list[tuple[FeatureNode, int, str]]:
    """Iterate over all leaf FeatureNodes with their depth and parent name."""
    result: list[tuple[FeatureNode, int, str]] = []
    for child in node.children:
        if isinstance(child, FeatureNode):
            result.append((child, depth, node.name))
        else:
            result.extend(_iter_leaves(child, depth + 1))
    return result


def _node_depth(root: GeometryNode, name: str, depth: int) -> int | None:
    """Find the depth of a named GeometryNode in the tree."""
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
    """Build a map from node name to its ancestor chain (root-first)."""
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
    """Compute the effective weight for a node by multiplying ancestor weights.

    Walks from the root toward the node, multiplying each ancestor's
    weight (defaulting to 1.0 if absent from *node_weights*) with
    the node's own weight.  For example, ``{"Tonal": 0.5}`` applied
    to ``TonalOnset`` yields 0.5 because TonalOnset inherits from
    Tonal.  ``{"Tonal": 0.5, "TonalOnset": 2.0}`` yields 1.0
    (0.5 * 2.0).
    """
    weight = node_weights.get(name, 1.0)
    for ancestor in ancestor_map.get(name, ()):
        weight *= node_weights.get(ancestor, 1.0)
    return weight


# ---------------------------------------------------------------------------
# Named weight presets
# ---------------------------------------------------------------------------

_FLAT_SENTINEL: dict[str, float] = {"__flat__": 1.0}

_WEIGHT_PRESETS: dict[str, dict[str, float]] = {
    "ignore-tone": {"Tonal": 0.0},
    "ignore-prosodic": {"Prosodic": 0.0},
    "segmental": {"Tonal": 0.0, "Prosodic": 0.0},
    "tone-heavy": {"Tonal": 2.0},
    "tone-only": {
        "Laryngeal": 0.0,
        "Manner": 0.0,
        "Place": 0.0,
        "TongueRoot": 0.0,
        "Prosodic": 0.0,
    },
    "flat": _FLAT_SENTINEL,
}


def resolve_node_weights(
    weights: dict[str, float] | str | None,
) -> dict[str, float] | None:
    """Resolve a weight specification to a concrete dict.

    Accepts ``None``, an explicit dict, or a preset name string.
    Valid preset names: ``"ignore-tone"``, ``"ignore-prosodic"``,
    ``"segmental"``, ``"tone-heavy"``, ``"tone-only"``.
    """
    if weights is None or isinstance(weights, dict):
        return weights
    try:
        return _WEIGHT_PRESETS[weights]
    except KeyError:
        valid = ", ".join(sorted(_WEIGHT_PRESETS))
        msg = f"Unknown node_weights preset: {weights!r}. Valid presets: {valid}"
        raise ValueError(msg) from None


DEFAULT_GEOMETRY = GeometryNode(
    name="Root",
    children=(
        GeometryNode(
            name="Laryngeal",
            children=(
                FeatureNode(name="voice", positive="voiced", negative="voiceless"),
                FeatureNode(name="spread_glottis", positive="aspirated", negative=""),
                FeatureNode(name="constricted_glottis", positive="glottalized", negative=""),
                FeatureNode(name="breathy_voice", positive="breathy", negative=""),
                FeatureNode(name="creaky_voice", positive="creaky", negative=""),
            ),
        ),
        GeometryNode(
            name="Manner",
            children=(
                FeatureNode(name="sonorant", positive="sonorant", negative="obstruent"),
                FeatureNode(name="continuant", positive="continuant", negative=""),
                FeatureNode(name="nasal", positive="nasal", negative=""),
                FeatureNode(name="lateral", positive="lateral", negative=""),
                FeatureNode(name="strident", positive="sibilant", negative=""),
                FeatureNode(name="delayed_release", positive="affricate", negative=""),
                FeatureNode(name="tap_feature", positive="tap", negative=""),
                FeatureNode(name="airstream", positive="non-pulmonic", negative=""),
                FeatureNode(name="syllabic", positive="syllabic", negative="non-syllabic"),
            ),
        ),
        GeometryNode(
            name="Place",
            children=(
                GeometryNode(
                    name="Labial",
                    children=(
                        FeatureNode(name="round", positive="rounded", negative="unrounded"),
                    ),
                ),
                GeometryNode(
                    name="Coronal",
                    children=(
                        FeatureNode(name="anterior", positive="anterior", negative=""),
                        FeatureNode(name="distributed", positive="distributed", negative=""),
                    ),
                ),
                GeometryNode(
                    name="Dorsal",
                    children=(
                        FeatureNode(name="high", positive="close", negative="open"),
                        FeatureNode(name="low", positive="near-open", negative="near-close"),
                        FeatureNode(name="back", positive="back", negative="front"),
                    ),
                ),
                GeometryNode(
                    name="Pharyngeal",
                    children=(
                        FeatureNode(name="pharyngeal_place", positive="pharyngeal", negative=""),
                        FeatureNode(name="epiglottal_place", positive="epiglottal", negative=""),
                    ),
                ),
                GeometryNode(
                    name="Glottal",
                    children=(FeatureNode(name="glottal_place", positive="glottal", negative=""),),
                ),
            ),
        ),
        GeometryNode(
            name="TongueRoot",
            children=(
                FeatureNode(
                    name="atr",
                    positive="advanced-tongue-root",
                    negative="retracted-tongue-root",
                ),
            ),
        ),
        GeometryNode(
            name="Prosodic",
            children=(
                FeatureNode(name="long_feature", positive="long", negative=""),
                FeatureNode(name="nasalized_feature", positive="nasalized", negative=""),
                FeatureNode(name="labialized_feature", positive="labialized", negative=""),
                FeatureNode(name="palatalized_feature", positive="palatalized", negative=""),
                FeatureNode(name="pharyngealized_feature", positive="pharyngealized", negative=""),
                FeatureNode(name="ejective_feature", positive="ejective", negative=""),
                FeatureNode(name="stress_feature", positive="primary-stress", negative=""),
            ),
        ),
        GeometryNode(
            name="Tonal",
            children=(
                GeometryNode(
                    name="TonalOnset",
                    children=(
                        FeatureNode(
                            name="tone_onset_register",
                            positive="tone-onset-upper",
                            negative="tone-onset-lower",
                        ),
                        FeatureNode(
                            name="tone_onset_height",
                            positive="tone-onset-raised",
                            negative="tone-onset-lowered",
                        ),
                    ),
                ),
                GeometryNode(
                    name="TonalMid",
                    children=(
                        FeatureNode(
                            name="tone_mid_register",
                            positive="tone-mid-upper",
                            negative="tone-mid-lower",
                        ),
                        FeatureNode(
                            name="tone_mid_height",
                            positive="tone-mid-raised",
                            negative="tone-mid-lowered",
                        ),
                    ),
                ),
                GeometryNode(
                    name="TonalOffset",
                    children=(
                        FeatureNode(
                            name="tone_offset_register",
                            positive="tone-offset-upper",
                            negative="tone-offset-lower",
                        ),
                        FeatureNode(
                            name="tone_offset_height",
                            positive="tone-offset-raised",
                            negative="tone-offset-lowered",
                        ),
                    ),
                ),
            ),
        ),
    ),
)

def valued_geometry_distance(
    a_values: dict[str, float | None],
    b_values: dict[str, float | None],
    geometry_map: dict[str, str],
    dimension_weights: dict[str, float],
    node_weights: dict[str, float] | str | None = None,
) -> float:
    """Geometry-weighted distance between two quantized valued-feature dicts.

    *a_values* / *b_values* map feature names to numeric values (``1.0``,
    ``-1.0``, ``0.0``) or ``None`` (skip).  *geometry_map* maps each feature
    name to a C&H geometry node.  *dimension_weights* maps each feature name
    to its base weight (typically ``1.0 / depth``).

    This helper is shared by ``PBaseFeatureSystem`` and
    ``PhoibleFeatureSystem``.
    """
    if a_values == b_values:
        return 0.0

    resolved = resolve_node_weights(node_weights)
    flat = resolved is _FLAT_SENTINEL
    ancestor_map = _build_ancestor_map(DEFAULT_GEOMETRY) if resolved and not flat else {}

    total_weight = 0.0
    total_diff = 0.0

    # Sort the key union so ``total_diff`` and ``total_weight``
    # accumulate in a deterministic order. See the comment in
    # ``sound_distance`` above — the same floating-point
    # non-associativity concern applies to this valued-distance path
    # (used by PBaseFeatureSystem / PhoibleFeatureSystem).
    all_keys = sorted(a_values.keys() | b_values.keys())
    for key in all_keys:
        val_a = a_values.get(key)
        val_b = b_values.get(key)

        # Skip dimensions where either side is unspecified (None)
        if val_a is None or val_b is None:
            continue

        # Skip dimensions both absent / neutral
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


FEATURE_TO_GEOMETRY_NODE: dict[str, str] = {
    "voiced": "Laryngeal",
    "voiceless": "Laryngeal",
    "aspirated": "Laryngeal",
    "glottalized": "Laryngeal",
    "breathy": "Laryngeal",
    "creaky": "Laryngeal",
    "stop": "Manner",
    "fricative": "Manner",
    "affricate": "Manner",
    "nasal": "Manner",
    "approximant": "Manner",
    "trill": "Manner",
    "tap": "Manner",
    "lateral": "Manner",
    "click": "Manner",
    "implosive": "Manner",
    "non-pulmonic": "Manner",
    "sibilant": "Manner",
    "syllabic": "Manner",
    "non-syllabic": "Manner",
    "bilabial": "Labial",
    "labio-dental": "Labial",
    "labio-velar": "Labial",
    "labio-palatal": "Labial",
    "labial": "Labial",
    "rounded": "Labial",
    "unrounded": "Labial",
    "dental": "Coronal",
    "alveolar": "Coronal",
    "post-alveolar": "Coronal",
    "alveolo-palatal": "Coronal",
    "retroflex": "Coronal",
    "linguolabial": "Coronal",
    "palatal": "Dorsal",
    "palatal-velar": "Dorsal",
    "velar": "Dorsal",
    "uvular": "Dorsal",
    "close": "Dorsal",
    "near-close": "Dorsal",
    "close-mid": "Dorsal",
    "mid": "Dorsal",
    "open-mid": "Dorsal",
    "near-open": "Dorsal",
    "open": "Dorsal",
    "front": "Dorsal",
    "near-front": "Dorsal",
    "central": "Dorsal",
    "near-back": "Dorsal",
    "back": "Dorsal",
    "pharyngeal": "Pharyngeal",
    "epiglottal": "Pharyngeal",
    "glottal": "Glottal",
    "advanced-tongue-root": "TongueRoot",
    "retracted-tongue-root": "TongueRoot",
    "long": "Prosodic",
    "nasalized": "Prosodic",
    "labialized": "Prosodic",
    "palatalized": "Prosodic",
    "pharyngealized": "Prosodic",
    "ejective": "Prosodic",
    "primary-stress": "Prosodic",
    "tone-onset-upper": "TonalOnset",
    "tone-onset-lower": "TonalOnset",
    "tone-onset-raised": "TonalOnset",
    "tone-onset-lowered": "TonalOnset",
    "tone-mid-upper": "TonalMid",
    "tone-mid-lower": "TonalMid",
    "tone-mid-raised": "TonalMid",
    "tone-mid-lowered": "TonalMid",
    "tone-offset-upper": "TonalOffset",
    "tone-offset-lower": "TonalOffset",
    "tone-offset-raised": "TonalOffset",
    "tone-offset-lowered": "TonalOffset",
}
