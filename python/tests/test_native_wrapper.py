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
    assert merkmal.is_segment("ə³³", system="descriptive")
    assert merkmal.is_segment("a³³", system="descriptive")
    assert merkmal.is_segment("o³³", system="descriptive")
    assert merkmal.is_segment("i³³", system="descriptive")
    assert not merkmal.is_segment("p³¹", system="descriptive")
    assert not merkmal.is_segment("p³³", system="descriptive")

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

    features_33 = merkmal.get_features("a³³", system="descriptive")
    assert "vowel" in features_33
    assert not any(feature.startswith("tone-") for feature in features_33)


def test_native_descriptive_broadened_source_tokens() -> None:
    positive = [
        "ai",
        "au",
        "ei",
        "aːi",
        "iau",
        "ai³³",
        "aːi³³",
        "ɐu³³",
        "əi³¹",
        "ɛï",
        "ɛï³³",
        "ɛï³¹",
        "ɛï³⁵",
        "ɛï⁴⁵",
        "ɛï⁴⁵³",
        "ᵐb",
        "ⁿd",
        "ⁿdʳ",
        "ɡb",
        "gb",
        "kp",
        "kpʷ",
        "kx",
        "gɣ",
        "kɣ",
        "tʂ",
        "tʂʰ",
        "ŋ̀",
        "m̀",
        "ä",
        "ă",
        "ç",
        "ḭ",
        "ṳ",
        "ṵ",
        "ṵː",
        "ṽ",
        "ñ",
        "ń",
        "ỹ",
        "kw",
        "gw",
        "ŋg",
        "kk",
        "ll",
        "tt",
        "nn",
        "pp",
    ]
    for token in positive:
        assert merkmal.is_segment(token, system="descriptive"), token

    negative = [
        "<?>",
        "<<->>",
        "<<[>>",
        "<<]>>",
        "<<~>>",
        "<</>>",
        "<<.>>",
        "→",
        "+",
        "∼",
        "_",
        "S",
        "T",
        "¹/¹",
        "³/¹",
        "³¹",
        "³⁵",
        "⁵⁵",
        "mb",
        "nd",
        "ě",
        "ǎ",
        "ý",
        "p³³",
    ]
    for token in negative:
        assert not merkmal.is_segment(token, system="descriptive"), token

    features_ai = merkmal.get_features("ai", system="descriptive")
    assert {
        "vowel",
        "diphthong",
        "n1-open",
        "n2-close",
        "move-height-open-close",
    } <= features_ai
    assert "open" not in features_ai
    assert "close" not in features_ai

    features_long = merkmal.get_features("aːi³³", system="descriptive")
    assert {"diphthong", "n1-long"} <= features_long
    assert not any(feature.startswith("tone-") for feature in features_long)

    features_tone = merkmal.get_features("əi³¹", system="descriptive")
    assert {"diphthong", "n1-mid", "tone-offset-lower", "tone-offset-lowered"} <= features_tone

    features_precomposed = merkmal.get_features("ɛï³³", system="descriptive")
    assert {
        "vowel",
        "diphthong",
        "n1-open-mid",
        "n2-close",
        "n2-centralized",
    } <= features_precomposed

    features_affricate = merkmal.get_features("kɣ", system="descriptive")
    assert {"consonant", "affricate", "velar"} <= features_affricate
    assert "voiceless" not in features_affricate

    features_labialized = merkmal.get_features("kw", system="descriptive")
    assert {"consonant", "complex", "consonant-cluster"} <= features_labialized
    assert {"n1-velar", "n2-labio-velar"} <= features_labialized

    features_geminate = merkmal.get_features("kk", system="descriptive")
    assert {"consonant", "complex", "consonant-cluster", "geminate"} <= features_geminate

    assert {"consonant", "nasalized"} <= merkmal.get_features("ñ", system="descriptive")
    assert {"vowel", "nasalized"} <= merkmal.get_features("ỹ", system="descriptive")
    assert {"vowel", "creaky"} <= merkmal.get_features("ḭ", system="descriptive")
    assert {"vowel", "breathy"} <= merkmal.get_features("ṳ", system="descriptive")
    assert {"vowel", "creaky"} <= merkmal.get_features("ṵ", system="descriptive")
    assert {"vowel", "creaky", "long"} <= merkmal.get_features("ṵː", system="descriptive")

    features_v_tilde = merkmal.get_features("ṽ", system="descriptive")
    assert {"consonant", "nasalized"} <= features_v_tilde
    assert "vowel" not in features_v_tilde
    assert "voiced" not in features_affricate
    assert "sibilant" not in features_affricate

    features_syllabic = merkmal.get_features("ŋ̀", system="descriptive")
    assert {"syllabic", "tone-onset-lower", "tone-offset-lower"} <= features_syllabic

    for token in negative:
        with pytest.raises(ValueError):
            merkmal.get_features(token, system="descriptive")


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
    assert merkmal.distance("ai", "ai", system="descriptive") == 0.0
    assert merkmal.distance("ai", "a", system="descriptive") < merkmal.distance(
        "ai", "i", system="descriptive"
    )
    assert 0.0 < merkmal.distance("ai", "au", system="descriptive") < 1.0
    assert math.isfinite(merkmal.distance("ai³³", "aːi³³", system="descriptive"))


def test_native_unicode_helpers() -> None:
    assert merkmal.normalize("g") == "ɡ"
    assert merkmal.normalize("sh/ʃ") == "ʃ"
    assert merkmal.normalize("ã") == "ã"
    assert merkmal.normalize("ï") == "ï"
    assert merkmal.normalize("ḭ") == "ḭ"
    assert merkmal.normalize("ṳ") == "ṳ"
    assert merkmal.normalize("ṵ") == "ṵ"
    assert merkmal.normalize("ṽ") == "ṽ"
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
