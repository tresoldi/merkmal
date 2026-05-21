"""Tests for PBase geometry-aware valued distance."""

import pytest

from merkmal import distance
from merkmal.engines.valued import ValuedEngine
from merkmal.model import load_model


class TestPBaseSegmentDistance:
    @pytest.fixture()
    def hc(self) -> ValuedEngine:
        sys = load_model("pbase-hc")
        assert isinstance(sys, ValuedEngine)
        return sys

    def test_identical_zero(self, hc: ValuedEngine) -> None:
        repr_p = hc.grapheme_to_representation("p")
        assert repr_p is not None
        assert hc.segment_distance(repr_p, repr_p) == 0.0

    def test_voicing_pair_small(self, hc: ValuedEngine) -> None:
        repr_p = hc.grapheme_to_representation("p")
        repr_b = hc.grapheme_to_representation("b")
        assert repr_p is not None and repr_b is not None
        d = hc.segment_distance(repr_p, repr_b)
        assert 0.0 < d < 0.15

    def test_place_pair_larger(self, hc: ValuedEngine) -> None:
        repr_p = hc.grapheme_to_representation("p")
        repr_t = hc.grapheme_to_representation("t")
        repr_b = hc.grapheme_to_representation("b")
        assert repr_p is not None and repr_t is not None and repr_b is not None
        d_voicing = hc.segment_distance(repr_p, repr_b)
        d_place = hc.segment_distance(repr_p, repr_t)
        assert d_place > d_voicing

    def test_symmetry(self, hc: ValuedEngine) -> None:
        repr_p = hc.grapheme_to_representation("p")
        repr_b = hc.grapheme_to_representation("b")
        assert repr_p is not None and repr_b is not None
        assert hc.segment_distance(repr_p, repr_b) == pytest.approx(
            hc.segment_distance(repr_b, repr_p),
        )

    def test_zero_laryngeal_eliminates_voicing(self, hc: ValuedEngine) -> None:
        repr_p = hc.grapheme_to_representation("p")
        repr_b = hc.grapheme_to_representation("b")
        assert repr_p is not None and repr_b is not None
        d = hc.segment_distance(repr_p, repr_b, node_weights={"Laryngeal": 0.0})
        assert d == pytest.approx(0.0)

    def test_string_preset(self, hc: ValuedEngine) -> None:
        repr_p = hc.grapheme_to_representation("p")
        repr_b = hc.grapheme_to_representation("b")
        assert repr_p is not None and repr_b is not None
        d = hc.segment_distance(repr_p, repr_b, node_weights="ignore-tone")
        assert isinstance(d, float) and d > 0.0

    @pytest.mark.parametrize("family", ["hc", "spe", "jfh", "uftc"])
    def test_all_families(self, family: str) -> None:
        sys = load_model(f"pbase-{family}")
        assert isinstance(sys, ValuedEngine)
        repr_p = sys.grapheme_to_representation("p")
        repr_b = sys.grapheme_to_representation("b")
        assert repr_p is not None and repr_b is not None
        d = sys.segment_distance(repr_p, repr_b)
        assert 0.0 < d < 1.0


class TestAnalysisRouting:
    def test_routing_with_node_weights(self) -> None:
        d = distance("p", "b", system="pbase-hc", node_weights="ignore-tone")
        assert isinstance(d, float) and d > 0.0

    def test_routing_without_node_weights(self) -> None:
        d = distance("p", "b", system="pbase-hc")
        assert isinstance(d, float) and d > 0.0

    def test_routing_identical(self) -> None:
        d = distance("p", "p", system="pbase-hc", node_weights="segmental")
        assert d == 0.0
