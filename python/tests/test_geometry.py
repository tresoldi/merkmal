"""Tests for geometry APIs."""

import pytest

from merkmal.geometry import (
    FeatureNode,
    GeometryNode,
    load_geometry,
    resolve_node_weights,
)
from merkmal.grapheme import tone_features_for_levels


@pytest.fixture()
def geom():
    return load_geometry("clements-hume")


def test_root_geometry_node(geom) -> None:
    assert isinstance(geom.tree, GeometryNode)
    assert geom.tree.name == "Root"


def test_feature_lookup(geom) -> None:
    node = geom.tree.find_feature("voiced")
    assert isinstance(node, FeatureNode)
    assert node is not None
    assert node.name == "voice"


def test_feature_distance(geom) -> None:
    assert geom.feature_distance("voiced", "voiced") == 0
    left = geom.feature_distance("voiced", "voiceless")
    right = geom.feature_distance("voiceless", "voiced")
    assert left == right


def test_tonal_node_exists(geom) -> None:
    tonal = None
    for child in geom.tree.children:
        if isinstance(child, GeometryNode) and child.name == "Tonal":
            tonal = child
    assert tonal is not None
    child_names = [c.name for c in tonal.children]
    assert "TonalOnset" in child_names
    assert "TonalMid" in child_names
    assert "TonalOffset" in child_names


def test_tonal_feature_lookup(geom) -> None:
    for feat in (
        "tone-onset-upper", "tone-onset-lower",
        "tone-onset-raised", "tone-onset-lowered",
        "tone-mid-upper", "tone-mid-lower",
        "tone-mid-raised", "tone-mid-lowered",
        "tone-offset-upper", "tone-offset-lower",
        "tone-offset-raised", "tone-offset-lowered",
    ):
        node = geom.tree.find_feature(feat)
        assert node is not None, f"{feat} not found in geometry"


def _tone(onset: int, mid: int, offset: int) -> frozenset[str]:
    return tone_features_for_levels(onset, mid, offset)


def _vowel_with_tone(onset: int, mid: int, offset: int) -> frozenset[str]:
    base = frozenset({"vowel", "open", "front", "unrounded"})
    return base | _tone(onset, mid, offset)


_TONELESS_A = frozenset({"vowel", "open", "front", "unrounded"})


class TestTonalDistance:
    def test_identical_tone_zero_distance(self, geom) -> None:
        high_a = _vowel_with_tone(4, 4, 4)
        assert geom.sound_distance(high_a, high_a) == 0.0

    def test_toneless_equals_mid(self, geom) -> None:
        mid_a = _vowel_with_tone(3, 3, 3)
        assert geom.sound_distance(_TONELESS_A, mid_a) == 0.0

    def test_rising_vs_falling_less_than_level_contrast(self, geom) -> None:
        rising = _vowel_with_tone(2, 3, 4)
        falling = _vowel_with_tone(4, 3, 2)
        d_rf = geom.sound_distance(rising, falling)
        high = _vowel_with_tone(4, 4, 4)
        low = _vowel_with_tone(2, 2, 2)
        d_hl = geom.sound_distance(high, low)
        assert d_rf < d_hl
        assert d_rf > 0.0

    def test_contour_equidistant_from_shared_target(self, geom) -> None:
        rising = _vowel_with_tone(2, 3, 4)
        falling = _vowel_with_tone(4, 3, 2)
        high = _vowel_with_tone(4, 4, 4)
        d_rising_high = geom.sound_distance(rising, high)
        d_falling_high = geom.sound_distance(falling, high)
        assert d_rising_high == pytest.approx(d_falling_high)

    def test_non_tonal_distance_positive(self, geom) -> None:
        p = frozenset({"consonant", "voiceless", "bilabial", "stop"})
        b = frozenset({"consonant", "voiced", "bilabial", "stop"})
        d = geom.sound_distance(p, b)
        assert d > 0.0

    @pytest.mark.parametrize(
        "onset_a, mid_a, offset_a, onset_b, mid_b, offset_b",
        [
            (4, 4, 4, 2, 2, 2),
            (5, 5, 5, 1, 1, 1),
            (2, 3, 4, 4, 3, 2),
        ],
    )
    def test_tonal_distance_symmetric(
        self, geom,
        onset_a: int, mid_a: int, offset_a: int,
        onset_b: int, mid_b: int, offset_b: int,
    ) -> None:
        a = _vowel_with_tone(onset_a, mid_a, offset_a)
        b = _vowel_with_tone(onset_b, mid_b, offset_b)
        assert geom.sound_distance(a, b) == pytest.approx(
            geom.sound_distance(b, a),
        )


class TestNodeWeights:
    _P = frozenset({"consonant", "voiceless", "bilabial", "stop"})
    _B = frozenset({"consonant", "voiced", "bilabial", "stop"})

    def test_none_gives_same_as_default(self, geom) -> None:
        d1 = geom.sound_distance(self._P, self._B)
        d2 = geom.sound_distance(self._P, self._B, node_weights=None)
        assert d1 == pytest.approx(d2)

    def test_zero_weight_eliminates_node(self, geom) -> None:
        d = geom.sound_distance(
            self._P, self._B, node_weights={"Laryngeal": 0.0},
        )
        assert d == pytest.approx(0.0)

    def test_tonal_zero_eliminates_tone_distance(self, geom) -> None:
        high_a = _vowel_with_tone(4, 4, 4)
        d = geom.sound_distance(
            _TONELESS_A, high_a,
            node_weights={"TonalOnset": 0.0, "TonalMid": 0.0, "TonalOffset": 0.0},
        )
        assert d == pytest.approx(0.0)

    def test_ancestor_weight_propagates(self, geom) -> None:
        high_a = _vowel_with_tone(4, 4, 4)
        d = geom.sound_distance(
            _TONELESS_A, high_a,
            node_weights={"Tonal": 0.0},
        )
        assert d == pytest.approx(0.0)

    def test_ancestor_weight_multiplicative(self, geom) -> None:
        high_a = _vowel_with_tone(4, 4, 4)
        d_half = geom.sound_distance(
            _TONELESS_A, high_a,
            node_weights={"Tonal": 0.5},
        )
        d_default = geom.sound_distance(_TONELESS_A, high_a)
        assert d_half < d_default
        d_mixed = geom.sound_distance(
            _TONELESS_A, high_a,
            node_weights={"Tonal": 0.5, "TonalOnset": 2.0},
        )
        assert d_mixed != pytest.approx(d_half)
        assert d_mixed != pytest.approx(d_default)

    def test_higher_weight_increases_distance(self, geom) -> None:
        d_default = geom.sound_distance(self._P, self._B)
        d_boosted = geom.sound_distance(
            self._P, self._B, node_weights={"Laryngeal": 5.0},
        )
        assert d_boosted > d_default


class TestResolveNodeWeights:
    def test_none_returns_none(self, geom) -> None:
        assert resolve_node_weights(geom, None) is None

    def test_dict_passthrough(self, geom) -> None:
        weights = {"Laryngeal": 0.5}
        assert resolve_node_weights(geom, weights) is weights

    def test_known_preset_returns_dict(self, geom) -> None:
        result = resolve_node_weights(geom, "ignore-tone")
        assert isinstance(result, dict)
        assert result["Tonal"] == 0.0

    def test_unknown_preset_raises(self, geom) -> None:
        with pytest.raises(ValueError, match="Unknown node_weights preset"):
            resolve_node_weights(geom, "nonexistent")

    def test_segmental_preset(self, geom) -> None:
        result = resolve_node_weights(geom, "segmental")
        assert result is not None
        assert result["Tonal"] == 0.0
        assert result["Prosodic"] == 0.0


class TestStringPresetIntegration:
    def test_ignore_tone_preset_geometry(self, geom) -> None:
        high_a = _vowel_with_tone(4, 4, 4)
        d = geom.sound_distance(
            _TONELESS_A, high_a, node_weights="ignore-tone",
        )
        assert d == pytest.approx(0.0)

    def test_ignore_tone_same_as_dict(self, geom) -> None:
        high_a = _vowel_with_tone(4, 4, 4)
        d_str = geom.sound_distance(
            _TONELESS_A, high_a, node_weights="ignore-tone",
        )
        d_dict = geom.sound_distance(
            _TONELESS_A, high_a, node_weights={"Tonal": 0.0},
        )
        assert d_str == pytest.approx(d_dict)

    def test_tone_heavy_increases_tonal_weight(self, geom) -> None:
        high_a = _vowel_with_tone(4, 4, 4)
        d_default = geom.sound_distance(_TONELESS_A, high_a)
        d_heavy = geom.sound_distance(
            _TONELESS_A, high_a, node_weights="tone-heavy",
        )
        assert d_heavy > d_default


class TestPrivativeRescaling:
    def test_privative_max_equals_equipollent_max(self, geom) -> None:
        voiced = frozenset({"voiced"})
        voiceless = frozenset({"voiceless"})
        d_equi = geom.sound_distance(voiced, voiceless)

        aspirated = frozenset({"aspirated"})
        unaspirated = frozenset[str]()
        d_priv = geom.sound_distance(aspirated, unaspirated)

        assert d_priv == pytest.approx(d_equi)

    def test_aspirated_vs_unaspirated_distance(self, geom) -> None:
        t = frozenset({"consonant", "voiceless", "alveolar", "stop"})
        th = frozenset({"consonant", "voiceless", "alveolar", "stop", "aspirated"})
        d = geom.sound_distance(t, th)
        assert d > 0.0

    def test_privative_both_absent_skipped(self, geom) -> None:
        p = frozenset({"consonant", "voiceless", "bilabial", "stop"})
        t = frozenset({"consonant", "voiceless", "alveolar", "stop"})
        d = geom.sound_distance(p, t)
        p_asp = p | frozenset({"aspirated"})
        t_asp = t | frozenset({"aspirated"})
        d_asp = geom.sound_distance(p_asp, t_asp)
        assert d_asp <= d

    def test_node_group_absent_vs_present(self, geom) -> None:
        a = frozenset({"bilabial"})
        b = frozenset({"alveolar"})
        d = geom.sound_distance(a, b)
        assert d > 0.0
