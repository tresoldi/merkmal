"""Tests for the typology companion package."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

merkmal_typology = pytest.importorskip("merkmal_typology")
mt = merkmal_typology


def test_data_loads_and_is_language_indexed() -> None:
    inventories = mt.inventories()
    languages = mt.languages()
    assert len(inventories) == 3020
    assert len(languages) == 2186
    # More inventories than languages is the sampling problem in one line, and
    # the reason `Inventory.inventory` is a doculect id and not a glottocode.
    assert len(inventories) > len(languages)
    english = next(i for i in inventories if i.glottocode == "stan1293")
    assert len(english.segments) == 40
    assert languages["stan1293"].family == "Indo-European"


def test_cross_language_numbers_carry_their_sample() -> None:
    """A bare frequency invites being read as a fact about languages."""
    frequency = mt.segment_frequency()
    # /m/ is the commonest segment in PHOIBLE, which is the standard result.
    assert frequency.most_common(1)[0][0] == "m"
    assert frequency.share("m") > 0.9

    sample = frequency.sample
    assert sample.inventories == 3020
    assert sample.languages == 2186
    assert sample.duplicated_languages == 834
    assert sample.families["Atlantic-Congo"] / sample.inventories > 0.15

    # The composition travels with the number, in the text and in the object.
    rendered = str(frequency)
    assert "Unweighted" in rendered
    assert "Atlantic-Congo" in rendered


def test_inventory_distance_is_symmetric_and_about_content() -> None:
    by_code = {i.glottocode: i for i in mt.inventories()}
    english, french, german = (by_code[c] for c in ("stan1293", "stan1290", "stan1295"))

    assert mt.inventory_distance(english, french) == pytest.approx(
        mt.inventory_distance(french, english)
    )
    assert 0.0 <= mt.inventory_distance(english, french) <= 1.0
    assert mt.inventory_distance(english, english) == pytest.approx(0.0, abs=1e-9)

    # German before French: the ordering an explicit size penalty got wrong,
    # because it made near-equal inventory *sizes* look like similarity.
    assert mt.inventory_distance(english, german) < mt.inventory_distance(english, french)


def test_feature_economy_rises_with_inventory_size() -> None:
    """Clements' observation: bigger inventories reuse features, not add them."""
    by_code = {i.glottocode: i for i in mt.inventories()}
    small = min(mt.inventories()[:400], key=lambda i: len(i.segments))
    english = by_code["stan1293"]
    assert mt.feature_economy(small) < mt.feature_economy(english)
    # Counted per feature, not per (feature, value) pair -- the latter roughly
    # halves it and is not the quantity Clements defines.
    assert mt.feature_economy(english) > 1.0
