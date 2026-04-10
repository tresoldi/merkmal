"""Tests for geometry APIs."""

import pytest

from merkmal.geometry import (
    DEFAULT_GEOMETRY,
    FeatureNode,
    GeometryNode,
    resolve_node_weights,
)
from merkmal.systems.categorical import tone_features_for_levels


def test_root_geometry_node() -> None:
    """The default geometry tree has the expected root."""
    assert isinstance(DEFAULT_GEOMETRY, GeometryNode)
    assert DEFAULT_GEOMETRY.name == "Root"


def test_feature_lookup() -> None:
    """Known features resolve to leaf nodes."""
    node = DEFAULT_GEOMETRY.find_feature("voiced")
    assert isinstance(node, FeatureNode)
    assert node is not None
    assert node.name == "voice"


def test_feature_distance() -> None:
    """Feature distance is symmetric and zero on identity."""
    assert DEFAULT_GEOMETRY.feature_distance("voiced", "voiced") == 0
    left = DEFAULT_GEOMETRY.feature_distance("voiced", "voiceless")
    right = DEFAULT_GEOMETRY.feature_distance("voiceless", "voiced")
    assert left == right


# -- Tonal geometry tests --


def test_tonal_node_exists() -> None:
    """The Tonal node exists with TonalOnset, TonalMid, and TonalOffset children."""
    tonal = None
    for child in DEFAULT_GEOMETRY.children:
        if isinstance(child, GeometryNode) and child.name == "Tonal":
            tonal = child
    assert tonal is not None
    child_names = [c.name for c in tonal.children]
    assert "TonalOnset" in child_names
    assert "TonalMid" in child_names
    assert "TonalOffset" in child_names


def test_tonal_feature_lookup() -> None:
    """Tone features resolve in the geometry tree."""
    for feat in (
        "tone-onset-upper", "tone-onset-lower",
        "tone-onset-raised", "tone-onset-lowered",
        "tone-mid-upper", "tone-mid-lower",
        "tone-mid-raised", "tone-mid-lowered",
        "tone-offset-upper", "tone-offset-lower",
        "tone-offset-raised", "tone-offset-lowered",
    ):
        node = DEFAULT_GEOMETRY.find_feature(feat)
        assert node is not None, f"{feat} not found in geometry"


def _tone(onset: int, mid: int, offset: int) -> frozenset[str]:
    """Helper: build tone feature set from Chao levels."""
    return tone_features_for_levels(onset, mid, offset)


def _vowel_with_tone(onset: int, mid: int, offset: int) -> frozenset[str]:
    """Helper: 'a' vowel features + tone."""
    base = frozenset({"vowel", "open", "front", "unrounded"})
    return base | _tone(onset, mid, offset)


_TONELESS_A = frozenset({"vowel", "open", "front", "unrounded"})


class TestTonalDistance:
    """Tonal distance via the geometry tree's sound_distance."""

    def test_identical_tone_zero_distance(self) -> None:
        high_a = _vowel_with_tone(4, 4, 4)
        assert DEFAULT_GEOMETRY.sound_distance(high_a, high_a) == 0.0

    def test_toneless_equals_mid(self) -> None:
        mid_a = _vowel_with_tone(3, 3, 3)  # mid = empty tone features
        assert DEFAULT_GEOMETRY.sound_distance(_TONELESS_A, mid_a) == 0.0

    def test_rising_vs_falling_less_than_level_contrast(self) -> None:
        """Rising vs falling share the same mid, so differ less than high vs low."""
        rising = _vowel_with_tone(2, 3, 4)
        falling = _vowel_with_tone(4, 3, 2)
        d_rf = DEFAULT_GEOMETRY.sound_distance(rising, falling)
        high = _vowel_with_tone(4, 4, 4)
        low = _vowel_with_tone(2, 2, 2)
        d_hl = DEFAULT_GEOMETRY.sound_distance(high, low)
        # Rising/falling share mid=3, so their distance is less than
        # high vs low which differs on all three tonal points.
        assert d_rf < d_hl
        assert d_rf > 0.0

    def test_contour_equidistant_from_shared_target(self) -> None:
        """Rising shares high offset with level-high; falling shares high onset.

        With symmetric onset/mid/offset weighting both are equidistant.
        """
        rising = _vowel_with_tone(2, 3, 4)
        falling = _vowel_with_tone(4, 3, 2)
        high = _vowel_with_tone(4, 4, 4)
        d_rising_high = DEFAULT_GEOMETRY.sound_distance(rising, high)
        d_falling_high = DEFAULT_GEOMETRY.sound_distance(falling, high)
        assert d_rising_high == pytest.approx(d_falling_high)

    def test_non_tonal_distance_positive(self) -> None:
        """Non-tonal segments still have positive distance on voicing."""
        p = frozenset({"consonant", "voiceless", "bilabial", "stop"})
        b = frozenset({"consonant", "voiced", "bilabial", "stop"})
        d = DEFAULT_GEOMETRY.sound_distance(p, b)
        assert d > 0.0

    @pytest.mark.parametrize(
        "onset_a, mid_a, offset_a, onset_b, mid_b, offset_b",
        [
            (4, 4, 4, 2, 2, 2),  # high vs low
            (5, 5, 5, 1, 1, 1),  # extra-high vs extra-low
            (2, 3, 4, 4, 3, 2),  # rising vs falling
        ],
    )
    def test_tonal_distance_symmetric(
        self,
        onset_a: int, mid_a: int, offset_a: int,
        onset_b: int, mid_b: int, offset_b: int,
    ) -> None:
        a = _vowel_with_tone(onset_a, mid_a, offset_a)
        b = _vowel_with_tone(onset_b, mid_b, offset_b)
        assert DEFAULT_GEOMETRY.sound_distance(a, b) == pytest.approx(
            DEFAULT_GEOMETRY.sound_distance(b, a),
        )


class TestNodeWeights:
    """Tests for the node_weights parameter on sound_distance."""

    _P = frozenset({"consonant", "voiceless", "bilabial", "stop"})
    _B = frozenset({"consonant", "voiced", "bilabial", "stop"})

    def test_none_gives_same_as_default(self) -> None:
        """node_weights=None should equal no weighting."""
        d1 = DEFAULT_GEOMETRY.sound_distance(self._P, self._B)
        d2 = DEFAULT_GEOMETRY.sound_distance(self._P, self._B, node_weights=None)
        assert d1 == pytest.approx(d2)

    def test_zero_weight_eliminates_node(self) -> None:
        """Zeroing Laryngeal should make p vs b identical (voicing is the only diff)."""
        d = DEFAULT_GEOMETRY.sound_distance(
            self._P, self._B, node_weights={"Laryngeal": 0.0},
        )
        assert d == pytest.approx(0.0)

    def test_tonal_zero_eliminates_tone_distance(self) -> None:
        """Zeroing tonal sub-nodes should make toned vs toneless vowels identical."""
        high_a = _vowel_with_tone(4, 4, 4)
        d = DEFAULT_GEOMETRY.sound_distance(
            _TONELESS_A, high_a,
            node_weights={"TonalOnset": 0.0, "TonalMid": 0.0, "TonalOffset": 0.0},
        )
        assert d == pytest.approx(0.0)

    def test_ancestor_weight_propagates(self) -> None:
        """Zeroing Tonal should eliminate tone distance via ancestor propagation."""
        high_a = _vowel_with_tone(4, 4, 4)
        d = DEFAULT_GEOMETRY.sound_distance(
            _TONELESS_A, high_a,
            node_weights={"Tonal": 0.0},
        )
        assert d == pytest.approx(0.0)

    def test_ancestor_weight_multiplicative(self) -> None:
        """Ancestor and child weights multiply."""
        high_a = _vowel_with_tone(4, 4, 4)
        # Tonal=0.5 propagates to TonalOnset and TonalOffset
        d_half = DEFAULT_GEOMETRY.sound_distance(
            _TONELESS_A, high_a,
            node_weights={"Tonal": 0.5},
        )
        d_default = DEFAULT_GEOMETRY.sound_distance(_TONELESS_A, high_a)
        assert d_half < d_default

        # Tonal=0.5, TonalOnset=2.0 → effective TonalOnset=1.0, TonalOffset=0.5
        d_mixed = DEFAULT_GEOMETRY.sound_distance(
            _TONELESS_A, high_a,
            node_weights={"Tonal": 0.5, "TonalOnset": 2.0},
        )
        assert d_mixed != pytest.approx(d_half)
        assert d_mixed != pytest.approx(d_default)

    def test_higher_weight_increases_distance(self) -> None:
        """Increasing Laryngeal weight should increase p vs b distance."""
        d_default = DEFAULT_GEOMETRY.sound_distance(self._P, self._B)
        d_boosted = DEFAULT_GEOMETRY.sound_distance(
            self._P, self._B, node_weights={"Laryngeal": 5.0},
        )
        assert d_boosted > d_default


class TestResolveNodeWeights:
    """Tests for resolve_node_weights and string preset support."""

    def test_none_returns_none(self) -> None:
        assert resolve_node_weights(None) is None

    def test_dict_passthrough(self) -> None:
        weights = {"Laryngeal": 0.5}
        assert resolve_node_weights(weights) is weights

    def test_known_preset_returns_dict(self) -> None:
        result = resolve_node_weights("ignore-tone")
        assert isinstance(result, dict)
        assert result["Tonal"] == 0.0

    def test_unknown_preset_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown node_weights preset"):
            resolve_node_weights("nonexistent")

    def test_segmental_preset(self) -> None:
        result = resolve_node_weights("segmental")
        assert result is not None
        assert result["Tonal"] == 0.0
        assert result["Prosodic"] == 0.0


class TestStringPresetIntegration:
    """End-to-end tests for string presets through sound_distance."""

    def test_ignore_tone_preset_geometry(self) -> None:
        """'ignore-tone' via geometry should zero out tonal distance."""
        high_a = _vowel_with_tone(4, 4, 4)
        d = DEFAULT_GEOMETRY.sound_distance(
            _TONELESS_A, high_a, node_weights="ignore-tone",
        )
        assert d == pytest.approx(0.0)

    def test_ignore_tone_same_as_dict(self) -> None:
        """String preset should give same result as equivalent dict."""
        high_a = _vowel_with_tone(4, 4, 4)
        d_str = DEFAULT_GEOMETRY.sound_distance(
            _TONELESS_A, high_a, node_weights="ignore-tone",
        )
        d_dict = DEFAULT_GEOMETRY.sound_distance(
            _TONELESS_A, high_a, node_weights={"Tonal": 0.0},
        )
        assert d_str == pytest.approx(d_dict)

    def test_tone_heavy_increases_tonal_weight(self) -> None:
        """'tone-heavy' should increase distance for tonal differences."""
        high_a = _vowel_with_tone(4, 4, 4)
        d_default = DEFAULT_GEOMETRY.sound_distance(_TONELESS_A, high_a)
        d_heavy = DEFAULT_GEOMETRY.sound_distance(
            _TONELESS_A, high_a, node_weights="tone-heavy",
        )
        assert d_heavy > d_default


class TestPrivativeRescaling:
    """Privative features contribute the same max distance as equipollent."""

    def test_privative_max_equals_equipollent_max(self) -> None:
        """Aspirated (privative) and voiced (equipollent) give same max contribution.

        Build minimal feature sets that differ on exactly one feature each,
        then compare the per-feature contribution.
        """
        # Equipollent: voiced vs voiceless (only voicing differs)
        voiced = frozenset({"voiced"})
        voiceless = frozenset({"voiceless"})
        d_equi = DEFAULT_GEOMETRY.sound_distance(voiced, voiceless)

        # Privative: aspirated vs absent (only aspiration differs)
        aspirated = frozenset({"aspirated"})
        unaspirated = frozenset[str]()
        d_priv = DEFAULT_GEOMETRY.sound_distance(aspirated, unaspirated)

        # Both should contribute equally — the raw distance values may differ
        # because of different total_weight denominators, but the per-feature
        # contribution (before normalisation) should be 1.0 for both.
        # With single-feature sets the normalised result should be equal.
        assert d_priv == pytest.approx(d_equi)

    def test_aspirated_vs_unaspirated_distance(self) -> None:
        """t vs tʰ (differ only in aspiration) should give non-trivial distance."""
        t = frozenset({"consonant", "voiceless", "alveolar", "stop"})
        th = frozenset({"consonant", "voiceless", "alveolar", "stop", "aspirated"})
        d = DEFAULT_GEOMETRY.sound_distance(t, th)
        assert d > 0.0

    def test_privative_both_absent_skipped(self) -> None:
        """Two segments both lacking a privative feature contribute 0 for it.

        When both segments share the same privative feature, the diff for
        that dimension is 0.  The normalised distance decreases because
        total_weight grows (shared feature enters denominator), but the
        numerator stays the same — i.e., no diff is contributed.
        """
        p = frozenset({"consonant", "voiceless", "bilabial", "stop"})
        t = frozenset({"consonant", "voiceless", "alveolar", "stop"})
        d = DEFAULT_GEOMETRY.sound_distance(p, t)
        # Adding aspiration to both: diff for aspiration is 0, but
        # total_weight increases → normalised distance should decrease.
        p_asp = p | frozenset({"aspirated"})
        t_asp = t | frozenset({"aspirated"})
        d_asp = DEFAULT_GEOMETRY.sound_distance(p_asp, t_asp)
        assert d_asp <= d

    def test_node_group_absent_vs_present(self) -> None:
        """Node group presence vs absence now contributes full weight.

        Segments differing only in a node-group feature (e.g., bilabial
        vs alveolar) should produce positive distance.
        """
        # bilabial only
        a = frozenset({"bilabial"})
        # alveolar only
        b = frozenset({"alveolar"})
        d = DEFAULT_GEOMETRY.sound_distance(a, b)
        assert d > 0.0
        # With rescaling, both the Labial and Coronal node groups
        # contribute full weight (1.0 each), not 0.5.
