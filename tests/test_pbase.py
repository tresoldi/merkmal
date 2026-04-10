"""Tests for PBase geometry-aware valued distance."""

import pytest

from merkmal import distance
from merkmal.systems.pbase import PBaseFeatureSystem


class TestPBaseSegmentDistance:
    """PBase segment_distance with geometry weighting."""

    @pytest.fixture()
    def hc(self) -> PBaseFeatureSystem:
        return PBaseFeatureSystem("hc")

    @pytest.fixture()
    def spe(self) -> PBaseFeatureSystem:
        return PBaseFeatureSystem("spe")

    @pytest.fixture()
    def jfh(self) -> PBaseFeatureSystem:
        return PBaseFeatureSystem("jfh")

    @pytest.fixture()
    def uftc(self) -> PBaseFeatureSystem:
        return PBaseFeatureSystem("uftc")

    # -- identical segments → 0.0 --

    def test_identical_zero(self, hc: PBaseFeatureSystem) -> None:
        repr_p = hc.grapheme_to_representation("p")
        assert repr_p is not None
        assert hc.segment_distance(repr_p, repr_p) == 0.0

    # -- voicing pair → small distance --

    def test_voicing_pair_small(self, hc: PBaseFeatureSystem) -> None:
        repr_p = hc.grapheme_to_representation("p")
        repr_b = hc.grapheme_to_representation("b")
        assert repr_p is not None and repr_b is not None
        d = hc.segment_distance(repr_p, repr_b)
        assert 0.0 < d < 0.15

    # -- place pair → larger distance --

    def test_place_pair_larger(self, hc: PBaseFeatureSystem) -> None:
        repr_p = hc.grapheme_to_representation("p")
        repr_t = hc.grapheme_to_representation("t")
        repr_b = hc.grapheme_to_representation("b")
        assert repr_p is not None and repr_t is not None and repr_b is not None
        d_voicing = hc.segment_distance(repr_p, repr_b)
        d_place = hc.segment_distance(repr_p, repr_t)
        assert d_place > d_voicing

    # -- symmetry --

    def test_symmetry(self, hc: PBaseFeatureSystem) -> None:
        repr_p = hc.grapheme_to_representation("p")
        repr_b = hc.grapheme_to_representation("b")
        assert repr_p is not None and repr_b is not None
        assert hc.segment_distance(repr_p, repr_b) == pytest.approx(
            hc.segment_distance(repr_b, repr_p),
        )

    # -- node_weights zeroing --

    def test_zero_laryngeal_eliminates_voicing(self, hc: PBaseFeatureSystem) -> None:
        repr_p = hc.grapheme_to_representation("p")
        repr_b = hc.grapheme_to_representation("b")
        assert repr_p is not None and repr_b is not None
        d = hc.segment_distance(repr_p, repr_b, node_weights={"Laryngeal": 0.0})
        assert d == pytest.approx(0.0)

    # -- string preset --

    def test_string_preset(self, hc: PBaseFeatureSystem) -> None:
        repr_p = hc.grapheme_to_representation("p")
        repr_b = hc.grapheme_to_representation("b")
        assert repr_p is not None and repr_b is not None
        d = hc.segment_distance(repr_p, repr_b, node_weights="ignore-tone")
        assert isinstance(d, float) and d > 0.0

    # -- all 4 families produce valid distances --

    @pytest.mark.parametrize("family", ["hc", "spe", "jfh", "uftc"])
    def test_all_families(self, family: str) -> None:
        sys = PBaseFeatureSystem(family)
        repr_p = sys.grapheme_to_representation("p")
        repr_b = sys.grapheme_to_representation("b")
        assert repr_p is not None and repr_b is not None
        d = sys.segment_distance(repr_p, repr_b)
        assert 0.0 < d < 1.0


class TestAnalysisRouting:
    """analysis.distance() routes through segment_distance for valued + node_weights."""

    def test_routing_with_node_weights(self) -> None:
        d = distance("p", "b", system="pbase-hc", node_weights="ignore-tone")
        assert isinstance(d, float) and d > 0.0

    def test_routing_without_node_weights(self) -> None:
        """Without node_weights, valued systems still use valued_distance."""
        d = distance("p", "b", system="pbase-hc")
        assert isinstance(d, float) and d > 0.0

    def test_routing_identical(self) -> None:
        d = distance("p", "p", system="pbase-hc", node_weights="segmental")
        assert d == 0.0
