"""Tests for the native C-backed top-level wrapper slice."""

from __future__ import annotations

import math

import pytest

import merkmal
from merkmal.cli import main


pytestmark = pytest.mark.skipif(
    getattr(merkmal, "_native", None) is None,
    reason="native extension is not built",
)


def test_native_lists_expanded_systems() -> None:
    systems = merkmal.list_systems()
    assert systems == sorted(
        [
            "broad",
            "descriptive",
            "distinctive",
            "pbase-hc",
            "pbase-jfh",
            "pbase-spe",
            "pbase-uftc",
            "phoible",
        ]
    )


def test_native_wrapper_surface_is_small() -> None:
    assert "load_model" not in merkmal.__all__
    assert not hasattr(merkmal, "CategoricalEngine")
    assert "Registry" in merkmal.__all__


def test_native_features_and_validity() -> None:
    assert merkmal.get_features("p") == frozenset(
        {"bilabial", "consonant", "stop", "voiceless"}
    )
    assert "syllabic=+" in merkmal.get_features("a", system="phoible")
    assert "aspirated" in merkmal.get_features("pʰ")
    assert "affricate" in merkmal.get_features("t͡ʃ")
    assert "spreadGlottis=+" in merkmal.get_features("bʰ", system="phoible")
    assert merkmal.is_segment("t͡ʃ")
    assert not merkmal.is_segment("not-ipa")
    assert not merkmal.is_segment("<?>", system="descriptive")
    with pytest.raises(ValueError):
        merkmal.get_features("<?>", system="descriptive")


def test_native_descriptive_tone_bearing_vowels_are_segments() -> None:
    assert merkmal.merge_tone_digits(["k", "a", "³¹"]) == ["k", "a³¹"]
    assert merkmal.is_segment("a³¹", system="descriptive")
    assert merkmal.is_segment("a⁵¹", system="descriptive")
    assert not merkmal.is_segment("p³¹", system="descriptive")

    features_31 = merkmal.get_features("a³¹", system="descriptive")
    assert {"vowel", "tone-offset-lower", "tone-offset-lowered"} <= features_31

    features_51 = merkmal.get_features("a⁵¹", system="descriptive")
    assert {
        "vowel",
        "tone-onset-upper",
        "tone-onset-raised",
        "tone-offset-lower",
        "tone-offset-lowered",
    } <= features_51


def test_native_distance_matches_golden_probe() -> None:
    assert math.isclose(merkmal.distance("p", "b"), 0.375, abs_tol=1e-10)
    assert math.isclose(
        merkmal.distance("p", "b", system="phoible"),
        0.0365853659,
        abs_tol=1e-10,
    )
    assert merkmal.feature_distance("voiced", "voiceless") == 2
    assert merkmal.feature_distance("tone-onset-upper", "tone-offset-upper") == 6
    assert merkmal.feature_distance("bilabial", "velar") == 999
    assert math.isclose(
        merkmal.distance("p", "b", system="distinctive", node_weights="flat"),
        0.2,
        abs_tol=1e-10,
    )


def test_native_unicode_helpers() -> None:
    assert merkmal.normalize("g") == "ɡ"
    assert merkmal.normalize("sh/ʃ") == "ʃ"
    assert merkmal.normalize("ã") == "ã"
    assert merkmal.segment_ipa("tʰoŋ⁵⁵") == ["tʰ", "o", "ŋ", "⁵⁵"]
    assert merkmal.segment_ipa_merged("tʰoŋ⁵⁵") == ["tʰ", "o⁵⁵", "ŋ"]
    assert merkmal.merge_tone_digits(["tʰ", "o", "ŋ", "⁵⁵"]) == ["tʰ", "o⁵⁵", "ŋ"]
    assert merkmal.segment_ipa("ⁿda") == ["ⁿd", "a"]
    assert merkmal.segment_ipa("n̥a") == ["n̥", "a"]


def test_native_registry_runtime_model() -> None:
    registry = merkmal.Registry()
    registry.add_model_text(
        "\n".join(
            [
                "@model toy",
                "@type categorical",
                "@geometry clements-hume",
                "grapheme X consonant voiceless bilabial stop",
                "grapheme Y consonant voiced bilabial stop",
            ]
        )
    )

    assert "toy" in registry.list_systems()
    assert registry.get_features("X", system="toy") == frozenset(
        {"consonant", "voiceless", "bilabial", "stop"}
    )
    assert registry.is_segment("Y", system="toy")
    assert math.isclose(registry.distance("X", "Y", system="toy"), 0.375, abs_tol=1e-10)


def test_cli_uses_native_wrapper(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["systems"]) == 0
    output = capsys.readouterr().out.splitlines()
    assert "broad" in output

    assert main(["--system", "phoible", "features", "bʰ"]) == 0
    output = capsys.readouterr().out.splitlines()
    assert "spreadGlottis=+" in output
