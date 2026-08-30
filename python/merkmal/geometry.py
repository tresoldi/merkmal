"""Validated, experimental scoring for JSON geometries.

The native library deliberately compiles one geometry. This module provides a
separate Python path for comparing already-resolved feature sets under an
alternative geometry, without implying that native ``distance`` selected it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable  # noqa: TC003
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class GeometryError(ValueError):
    """A geometry is malformed or cannot score the requested features."""


@dataclass(frozen=True)
class _Leaf:
    feature: str
    parent: str
    weight: float
    negative: str


class Geometry:
    """A validated JSON geometry and its explicit feature-set scorer."""

    def __init__(self, data: dict[str, Any], *, source: str = "<mapping>") -> None:
        self.data = data
        self.source = source
        self.name = str(data.get("name", ""))
        self.version = str(data.get("version", ""))
        if data.get("schema_version") != 1 or not self.name or not self.version:
            raise GeometryError(f"{source}: schema_version, name, and version are required")
        self._nodes: set[str] = set()
        self._leaves: list[_Leaf] = []
        self._walk(data.get("tree"), parent=None, depth=0)
        if not self._leaves:
            raise GeometryError(f"{source}: geometry has no leaves")
        self._feature_to_node = dict(data.get("feature_to_node", {}))
        self._scales = tuple(data.get("ordinal_scales", ()))
        self._validate_scales()
        self._presets = dict(data.get("weight_presets", {}))
        self._validate_presets()
        self.payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.digest = hashlib.sha256(self.payload.encode("utf-8")).hexdigest()

    @classmethod
    def from_path(cls, path: str | Path) -> Geometry:
        location = Path(path)
        return cls(json.loads(location.read_text(encoding="utf-8")), source=str(location))

    def _walk(self, node: Any, *, parent: str | None, depth: int) -> None:
        if not isinstance(node, dict) or not isinstance(node.get("name"), str):
            raise GeometryError(f"{self.source}: every tree node needs a name")
        name = node["name"]
        if name in self._nodes:
            raise GeometryError(f"{self.source}: duplicate geometry node {name!r}")
        self._nodes.add(name)
        children = node.get("children")
        if children is not None:
            if not isinstance(children, list):
                raise GeometryError(f"{self.source}: children for {name!r} must be a list")
            for child in children:
                self._walk(child, parent=name, depth=depth + 1)
            return
        positive = node.get("positive")
        if not isinstance(positive, str) or not positive:
            raise GeometryError(f"{self.source}: leaf {name!r} needs positive")
        self._leaves.append(
            _Leaf(
                positive,
                parent or "",
                float(node.get("weight", 1.0 / max(depth, 1))),
                str(node.get("negative", "")),
            )
        )

    def _validate_scales(self) -> None:
        seen: set[str] = set()
        for scale in self._scales:
            name = scale.get("name")
            levels = scale.get("levels")
            if (
                not isinstance(name, str)
                or name in seen
                or not isinstance(levels, list)
                or len(levels) < 2
            ):
                raise GeometryError(f"{self.source}: malformed ordinal scale")
            if len(set(levels)) != len(levels) or scale.get("node") not in self._nodes:
                raise GeometryError(f"{self.source}: invalid ordinal scale {name!r}")
            seen.add(name)

    def _validate_presets(self) -> None:
        for name, value in self._presets.items():
            if value == "__flat__":
                continue
            if not isinstance(value, dict):
                raise GeometryError(f"{self.source}: preset {name!r} must be a mapping")
            for node, weight in value.items():
                if node not in self._nodes or not isinstance(weight, (int, float)) or weight < 0:
                    raise GeometryError(f"{self.source}: invalid weight in preset {name!r}")

    def _weight(self, node: str, preset: str | None) -> float:
        if preset is None:
            return 1.0
        if preset not in self._presets:
            raise GeometryError(f"{self.source}: unknown weight preset {preset!r}")
        value = self._presets[preset]
        if value == "__flat__":
            return 1.0
        return float(value.get(node, 1.0))

    def distance(
        self, features_a: Iterable[str], features_b: Iterable[str], *, preset: str | None = None
    ) -> float:
        """Return a geometry score for two resolved feature sets.

        This mirrors the experimental categorical scorer: leaf mismatches and
        node-group mismatches are weighted, while ordered scales retain their
        ordinal distance. It is intentionally separate from native scoring.
        """
        a, b = set(features_a), set(features_b)
        total = difference = 0.0
        scored: set[str] = set()
        for leaf in self._leaves:
            weight = leaf.weight * self._weight(leaf.parent, preset)
            av = leaf.feature in a
            bv = leaf.feature in b
            if leaf.negative:
                if leaf.negative in a:
                    av = False
                if leaf.negative in b:
                    bv = False
            total += weight
            opposite = (
                (leaf.feature in a and leaf.negative in b)
                or (leaf.feature in b and leaf.negative in a)
            )
            difference += weight * (1.0 if av != bv and opposite else 0.5 if av != bv else 0.0)
            scored.add(leaf.feature)
            if leaf.negative:
                scored.add(leaf.negative)
        for feature, node in self._feature_to_node.items():
            if feature in scored or feature in a or feature in b:
                weight = self._weight(node, preset)
                total += weight
                difference += weight * (0.5 if (feature in a) != (feature in b) else 0.0)
        for scale in self._scales:
            levels = scale["levels"]
            ia = next((i for i, x in enumerate(levels) if x in a), None)
            ib = next((i for i, x in enumerate(levels) if x in b), None)
            if ia is not None and ib is not None:
                weight = float(scale.get("weight", 1.0)) * self._weight(scale["node"], preset)
                total += weight
                difference += weight * abs(ia - ib) / (len(levels) - 1)
        return difference / total if total else 0.0
