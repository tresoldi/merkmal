"""Tests for the Descriptive feature system."""

import pytest

from merkmal.engines.categorical import CategoricalEngine
from merkmal.model import load_model


@pytest.fixture()
def descriptive() -> CategoricalEngine:
    sys = load_model("descriptive")
    assert isinstance(sys, CategoricalEngine)
    return sys


def test_descriptive_lookup(descriptive: CategoricalEngine) -> None:
    features = descriptive.grapheme_to_features("a")
    assert features is not None
    assert "vowel" in features


def test_descriptive_class_lookup(descriptive: CategoricalEngine) -> None:
    features = descriptive.class_features("V")
    assert features is not None
    assert "vowel" in features


@pytest.mark.parametrize(
    "grapheme, expected_feature",
    [
        ("â", "tone-onset-upper"),
        ("á", "tone-onset-upper"),
        ("ā", "vowel"),
        ("à", "tone-onset-lower"),
        ("pʰ", "aspirated"),
        ("tː", "long"),
        ("ã", "nasalized"),
        ("ˀt", "pre-glottalized"),
        ("n̥", "devoiced"),
        ("kʷ", "labialized"),
    ],
)
def test_composition(
    descriptive: CategoricalEngine, grapheme: str, expected_feature: str,
) -> None:
    features = descriptive.grapheme_to_features(grapheme)
    assert features is not None, f"grapheme {grapheme!r} not resolved"
    assert expected_feature in features


@pytest.mark.parametrize(
    "grapheme, expected_feature",
    [
        ("ù", "tone-onset-lower"),
        ("ɔ̃", "nasalized"),
        ("ɛ̰", "creaky"),
    ],
)
def test_novel_composition(
    descriptive: CategoricalEngine, grapheme: str, expected_feature: str,
) -> None:
    features = descriptive.grapheme_to_features(grapheme)
    assert features is not None, f"grapheme {grapheme!r} not resolved"
    assert expected_feature in features


def test_composition_preserves_base_features(descriptive: CategoricalEngine) -> None:
    base = descriptive.grapheme_to_features("a")
    composed = descriptive.grapheme_to_features("á")
    assert base is not None
    assert composed is not None
    assert base < composed
    assert composed - base == {
        "tone-onset-upper", "tone-onset-lowered",
        "tone-mid-upper", "tone-mid-lowered",
        "tone-offset-upper", "tone-offset-lowered",
    }


def test_click_gets_non_pulmonic_and_velar(descriptive: CategoricalEngine) -> None:
    features = descriptive.grapheme_to_features("ǃ")
    assert features is not None
    assert "click" in features
    assert "non-pulmonic" in features
    assert "velar" in features


def test_implosive_gets_non_pulmonic(descriptive: CategoricalEngine) -> None:
    features = descriptive.grapheme_to_features("ɓ")
    assert features is not None
    assert "non-pulmonic" in features
    assert "velar" not in features


def test_pulmonic_stop_no_non_pulmonic(descriptive: CategoricalEngine) -> None:
    features = descriptive.grapheme_to_features("t")
    assert features is not None
    assert "non-pulmonic" not in features


def test_tie_bar_doubly_articulated(descriptive: CategoricalEngine) -> None:
    features = descriptive.grapheme_to_features("k͡p")
    assert features is not None
    assert "velar" in features
    assert "bilabial" in features
    assert "voiceless" in features
    assert "stop" in features


def test_tie_bar_affricate(descriptive: CategoricalEngine) -> None:
    features = descriptive.grapheme_to_features("t͡s")
    assert features is not None
    assert "stop" in features or "affricate" in features
    assert "consonant" in features


def test_tie_bar_with_modifier(descriptive: CategoricalEngine) -> None:
    features = descriptive.grapheme_to_features("k͡pʰ")
    assert features is not None
    assert "velar" in features
    assert "bilabial" in features
    assert "aspirated" in features
