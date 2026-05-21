"""Tests for the distinctive feature system."""

import pytest

from merkmal.engines.categorical import CategoricalEngine
from merkmal.model import load_model


@pytest.fixture()
def system() -> CategoricalEngine:
    sys = load_model("distinctive")
    assert isinstance(sys, CategoricalEngine)
    return sys


def test_distinctive_lookup(system: CategoricalEngine) -> None:
    features = system.grapheme_to_features("a")
    assert features is not None
    assert "vowel" in features


def test_distinctive_scalars(system: CategoricalEngine) -> None:
    scalars = system.grapheme_to_scalars("a")
    assert scalars is not None
    assert isinstance(scalars, dict)


class TestDistinctiveSoundDistancePresets:
    _P = frozenset({"consonant", "voiceless", "bilabial", "stop"})
    _B = frozenset({"consonant", "voiced", "bilabial", "stop"})

    def test_string_preset_accepted(self, system: CategoricalEngine) -> None:
        d = system.sound_distance(self._P, self._B, node_weights="ignore-tone")
        assert isinstance(d, float)

    def test_string_preset_matches_dict(self, system: CategoricalEngine) -> None:
        d_str = system.sound_distance(
            self._P, self._B, node_weights="ignore-tone",
        )
        d_dict = system.sound_distance(
            self._P, self._B, node_weights={"Tonal": 0.0},
        )
        assert d_str == pytest.approx(d_dict)

    def test_zero_laryngeal_eliminates_voicing(self, system: CategoricalEngine) -> None:
        d = system.sound_distance(
            self._P, self._B, node_weights={"Laryngeal": 0.0},
        )
        assert d == pytest.approx(0.0)


class TestPrivativeRescalingDistinctive:
    def test_privative_rescaling_distinctive(self, system: CategoricalEngine) -> None:
        base = frozenset({"consonant", "bilabial", "stop"})
        voiced = base | frozenset({"voiced"})
        voiceless = base | frozenset({"voiceless"})
        d_voicing = system.sound_distance(voiced, voiceless)

        plain = base | frozenset({"voiceless"})
        aspirated = plain | frozenset({"aspirated"})
        d_aspiration = system.sound_distance(plain, aspirated)

        assert d_voicing > 0.0
        assert d_aspiration > 0.0
        assert d_aspiration > 0.0
