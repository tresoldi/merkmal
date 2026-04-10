"""Tests for the Broad feature system."""

import pytest

from merkmal import BroadFeatureSystem, load_builtin_dataset


@pytest.fixture()
def system() -> BroadFeatureSystem:
    return BroadFeatureSystem(dataset=load_builtin_dataset())


def test_broad_lookup(system: BroadFeatureSystem) -> None:
    """The Broad system resolves common graphemes."""
    features = system.grapheme_to_features("a")
    assert features is not None
    assert "vowel" in features


def test_broad_class_lookup(system: BroadFeatureSystem) -> None:
    """The Broad system resolves sound classes."""
    assert system.is_class("V") is True


class TestBroadCompositionalFallback:
    """Verify Broad produces sensible results for composed graphemes."""

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
        self, system: BroadFeatureSystem,
        grapheme: str, expected_modifier: str,
    ) -> None:
        """Composed grapheme includes the modifier feature."""
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
        self, system: BroadFeatureSystem,
        grapheme: str, base_grapheme: str,
    ) -> None:
        """Composed grapheme retains all base features."""
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
        self, system: BroadFeatureSystem,
        grapheme: str,
    ) -> None:
        """Tone diacritics produce tone-onset/tone-offset features."""
        features = system.grapheme_to_features(grapheme)
        assert features is not None
        tone_feats = {f for f in features if f.startswith("tone-")}
        assert len(tone_feats) >= 2

    def test_composed_not_in_table(self, system: BroadFeatureSystem) -> None:
        """Composed graphemes are resolved via fallback, not table lookup."""
        from merkmal.systems.categorical import normalize_input_grapheme
        norm = normalize_input_grapheme("kʰ")
        assert norm not in system._grapheme_table
