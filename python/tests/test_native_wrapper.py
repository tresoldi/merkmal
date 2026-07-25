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


def test_native_unicode_helpers() -> None:
    assert merkmal.normalize("g") == "ɡ"
    assert merkmal.normalize("sh/ʃ") == "ʃ"
    assert merkmal.normalize("ã") == "ã"
    assert merkmal.segment_ipa("tʰoŋ⁵⁵") == ["tʰ", "o", "ŋ", "⁵⁵"]
    assert merkmal.segment_ipa("ⁿda") == ["ⁿd", "a"]
    assert merkmal.segment_ipa("n̥a") == ["n̥", "a"]


def test_cli_uses_native_wrapper(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["systems"]) == 0
    output = capsys.readouterr().out.splitlines()
    assert "broad" in output

    assert main(["--system", "phoible", "features", "bʰ"]) == 0
    output = capsys.readouterr().out.splitlines()
    assert "spreadGlottis=+" in output
