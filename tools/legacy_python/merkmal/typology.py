"""Typological direction costs for asymmetric distance computation.

Direction costs encode diachronic typological priors (e.g. lenition
is more frequent than fortition). They live in separate files from
the synchronic geometry because they encode different knowledge.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

from merkmal import paths

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class DirectionCost:
    pos_to_neg: float = 1.0
    neg_to_pos: float = 1.0


@dataclass(frozen=True)
class Typology:
    name: str
    direction_costs: dict[str, DirectionCost]

    def cost_for(self, feature_name: str, diff: float) -> float:
        dc = self.direction_costs.get(feature_name)
        if dc is None:
            return abs(diff)
        if diff > 0:
            return diff * dc.pos_to_neg
        if diff < 0:
            return -diff * dc.neg_to_pos
        return 0.0


def find_typologies_dir() -> Path:
    """Highest-precedence typologies directory (see :mod:`merkmal.paths`)."""
    return paths.primary_dir("typologies")


@cache
def load_typology(name: str) -> Typology:
    path = paths.resolve_file("typologies", f"{name}.json")
    if path is None:
        roots = paths.data_roots("typologies")
        msg = f"Typology not found: {name} (looked in {roots})"
        raise FileNotFoundError(msg)

    data = json.loads(path.read_text(encoding="utf-8"))
    costs: dict[str, DirectionCost] = {}
    for feature_name, vals in data.get("direction_costs", {}).items():
        costs[feature_name] = DirectionCost(
            pos_to_neg=vals.get("pos_to_neg", 1.0),
            neg_to_pos=vals.get("neg_to_pos", 1.0),
        )
    return Typology(name=data["name"], direction_costs=costs)
