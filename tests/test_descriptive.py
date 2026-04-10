"""Tests for the Descriptive feature system."""

import pytest

from merkmal import DescriptiveFeatureSystem, load_builtin_dataset


@pytest.fixture()
def descriptive() -> DescriptiveFeatureSystem:
    return DescriptiveFeatureSystem(dataset=load_builtin_dataset())


def test_descriptive_lookup(descriptive: DescriptiveFeatureSystem) -> None:
    """The Descriptive system resolves common graphemes."""
    features = descriptive.grapheme_to_features("a")
    assert features is not None
    assert "vowel" in features


def test_descriptive_class_lookup(descriptive: DescriptiveFeatureSystem) -> None:
    """The Descriptive system resolves sound classes."""
    features = descriptive.class_features("V")
    assert features is not None
    assert "vowel" in features


# -- Compositional decomposition tests --


@pytest.mark.parametrize(
    "grapheme, expected_feature",
    [
        ("\u00e2", "tone-onset-upper"),    # â falling: onset=high(4)
        ("\u00e1", "tone-onset-upper"),    # á high(4)
        ("\u0101", "vowel"),               # ā mid(3) — no tone features added
        ("\u00e0", "tone-onset-lower"),    # à low(2)
        ("p\u02b0", "aspirated"),          # pʰ (suffix modifier)
        ("t\u02d0", "long"),               # tː
        ("a\u0303", "nasalized"),          # ã (combining tilde)
        ("\u02c0t", "pre-glottalized"),    # ˀt (prefix modifier)
        ("n\u0325", "devoiced"),           # n̥ (combining ring below)
        ("k\u02b7", "labialized"),         # kʷ
    ],
)
def test_composition(
    descriptive: DescriptiveFeatureSystem, grapheme: str, expected_feature: str,
) -> None:
    """Compositional decomposition adds the expected modifier feature."""
    features = descriptive.grapheme_to_features(grapheme)
    assert features is not None, f"grapheme {grapheme!r} not resolved"
    assert expected_feature in features


@pytest.mark.parametrize(
    "grapheme, expected_feature",
    [
        ("\u00f9", "tone-onset-lower"),  # ù low tone (not in base table)
        ("\u0254\u0303", "nasalized"),   # ɔ̃
        ("\u025b\u0330", "creaky"),      # ɛ̰
    ],
)
def test_novel_composition(
    descriptive: DescriptiveFeatureSystem, grapheme: str, expected_feature: str,
) -> None:
    """Composition works for graphemes never enumerated in sounds.tsv."""
    features = descriptive.grapheme_to_features(grapheme)
    assert features is not None, f"grapheme {grapheme!r} not resolved"
    assert expected_feature in features


def test_composition_preserves_base_features(descriptive: DescriptiveFeatureSystem) -> None:
    """Composed features include all base features plus the modifier."""
    base = descriptive.grapheme_to_features("a")
    composed = descriptive.grapheme_to_features("\u00e1")  # á (high tone)
    assert base is not None
    assert composed is not None
    assert base < composed  # base is a strict subset
    # High tone (level 4) = onset/mid/offset all upper+lowered
    assert composed - base == {
        "tone-onset-upper", "tone-onset-lowered",
        "tone-mid-upper", "tone-mid-lowered",
        "tone-offset-upper", "tone-offset-lowered",
    }


# -- Click enrichment tests --


def test_click_gets_non_pulmonic_and_velar(descriptive: DescriptiveFeatureSystem) -> None:
    """Clicks receive non-pulmonic airstream and velar posterior closure."""
    features = descriptive.grapheme_to_features("\u01c3")  # ǃ postalveolar click
    assert features is not None
    assert "click" in features
    assert "non-pulmonic" in features
    assert "velar" in features


def test_implosive_gets_non_pulmonic(descriptive: DescriptiveFeatureSystem) -> None:
    """Implosives receive non-pulmonic but not velar."""
    features = descriptive.grapheme_to_features("\u0253")  # ɓ
    assert features is not None
    assert "non-pulmonic" in features
    assert "velar" not in features


def test_pulmonic_stop_no_non_pulmonic(descriptive: DescriptiveFeatureSystem) -> None:
    """Pulmonic stops do not get non-pulmonic."""
    features = descriptive.grapheme_to_features("t")
    assert features is not None
    assert "non-pulmonic" not in features


# -- Tie bar tests --


def test_tie_bar_doubly_articulated(descriptive: DescriptiveFeatureSystem) -> None:
    """Tie-bar graphemes resolve to union of component features."""
    features = descriptive.grapheme_to_features("k\u0361p")  # k͡p
    assert features is not None
    assert "velar" in features
    assert "bilabial" in features
    assert "voiceless" in features
    assert "stop" in features


def test_tie_bar_affricate(descriptive: DescriptiveFeatureSystem) -> None:
    """Tie-bar affricates resolve even without a table entry."""
    features = descriptive.grapheme_to_features("t\u0361s")  # t͡s
    assert features is not None
    assert "stop" in features or "affricate" in features
    assert "consonant" in features


def test_tie_bar_with_modifier(descriptive: DescriptiveFeatureSystem) -> None:
    """Tie-bar graphemes with diacritics decompose correctly."""
    features = descriptive.grapheme_to_features("k\u0361p\u02b0")  # k͡pʰ
    assert features is not None
    assert "velar" in features
    assert "bilabial" in features
    assert "aspirated" in features
