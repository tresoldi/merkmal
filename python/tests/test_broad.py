"""Tests for the Broad feature system."""

import pytest

from merkmal.engines.categorical import CategoricalEngine
from merkmal.grapheme import normalize_input_grapheme
from merkmal.model import load_model


@pytest.fixture()
def system() -> CategoricalEngine:
    sys = load_model("broad")
    assert isinstance(sys, CategoricalEngine)
    return sys


def test_broad_lookup(system: CategoricalEngine) -> None:
    features = system.grapheme_to_features("a")
    assert features is not None
    assert "vowel" in features


def test_broad_class_lookup(system: CategoricalEngine) -> None:
    assert system.is_class("V") is True


class TestBroadCompositionalFallback:
    @pytest.mark.parametrize(
        "grapheme, expected_modifier",
        [
            ("kʰ", "aspirated"),
            ("tʲ", "palatalized"),
            ("bː", "long"),
            ("ã", "nasalized"),
            ("kʷ", "labialized"),
            ("tˤ", "pharyngealized"),
            ("pʼ", "ejective"),
        ],
    )
    def test_modifier_added(
        self, system: CategoricalEngine,
        grapheme: str, expected_modifier: str,
    ) -> None:
        features = system.grapheme_to_features(grapheme)
        assert features is not None
        assert expected_modifier in features

    @pytest.mark.parametrize(
        "grapheme, base_grapheme",
        [
            ("kʰ", "k"),
            ("tʲ", "t"),
            ("bː", "b"),
            ("ã", "a"),
            ("kʷ", "k"),
        ],
    )
    def test_base_features_preserved(
        self, system: CategoricalEngine,
        grapheme: str, base_grapheme: str,
    ) -> None:
        composed = system.grapheme_to_features(grapheme)
        base = system.grapheme_to_features(base_grapheme)
        assert composed is not None
        assert base is not None
        assert base.issubset(composed)

    @pytest.mark.parametrize(
        "grapheme",
        ["á", "à", "ǎ", "â"],
    )
    def test_tone_diacritics_add_tone_features(
        self, system: CategoricalEngine,
        grapheme: str,
    ) -> None:
        features = system.grapheme_to_features(grapheme)
        assert features is not None
        tone_feats = {f for f in features if f.startswith("tone-")}
        assert len(tone_feats) >= 2

    def test_composed_not_in_table(self, system: CategoricalEngine) -> None:
        norm = normalize_input_grapheme("kʰ")
        assert norm not in system._grapheme_table
