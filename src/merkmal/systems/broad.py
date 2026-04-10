"""Broad feature system."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

from merkmal.systems.categorical import (
    CategoricalFeatureSystem,
    normalize_input_grapheme,
    parse_sound_name,
)

if TYPE_CHECKING:
    from merkmal.dataset import FeatureDataset


@dataclass(frozen=True)
class BroadFeatureSystem(CategoricalFeatureSystem):
    """Built-in Broad feature system."""

    dataset: FeatureDataset

    @property
    def name(self) -> str:
        return "broad"

    @cached_property
    def _grapheme_table(self) -> dict[str, frozenset[str]]:
        table: dict[str, frozenset[str]] = {}
        for grapheme, name in self.dataset.sounds.items():
            features = parse_sound_name(
                name, filter_categories=False,
            )
            if features:
                table[normalize_input_grapheme(grapheme)] = features
        return table
