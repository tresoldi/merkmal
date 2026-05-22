"""Typological direction costs for asymmetric distance computation.

Direction costs encode diachronic typological priors (e.g. lenition
is more frequent than fortition). They live in separate files from
the synchronic geometry because they encode different knowledge.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent


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
    env = os.environ.get("MERKMAL_TYPOLOGIES")
    if env:
        p = Path(env)
        if p.is_dir():
            return p
    candidate = _ROOT / "typologies"
    if candidate.is_dir():
        return candidate
    msg = (
        f"Cannot find typologies/ directory. Set MERKMAL_TYPOLOGIES or ensure "
        f"{candidate} exists."
    )
    raise FileNotFoundError(msg)


@cache
def load_typology(name: str) -> Typology:
    typ_dir = find_typologies_dir()
    path = typ_dir / f"{name}.json"
    if not path.exists():
        msg = f"Typology not found: {name} (looked in {typ_dir})"
        raise FileNotFoundError(msg)

    data = json.loads(path.read_text(encoding="utf-8"))
    costs: dict[str, DirectionCost] = {}
    for feature_name, vals in data.get("direction_costs", {}).items():
        costs[feature_name] = DirectionCost(
            pos_to_neg=vals.get("pos_to_neg", 1.0),
            neg_to_pos=vals.get("neg_to_pos", 1.0),
        )
    return Typology(name=data["name"], direction_costs=costs)
