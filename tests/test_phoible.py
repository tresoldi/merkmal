"""Tests for the PHOIBLE feature system."""

import pytest

from merkmal import distance, get_system
from merkmal.representations import ValuedFeatures
from merkmal.systems.phoible import PhoibleFeatureSystem


class TestPhoibleSystem:
    """Core PhoibleFeatureSystem functionality."""

    @pytest.fixture()
    def system(self) -> PhoibleFeatureSystem:
        return PhoibleFeatureSystem()

    def test_loads(self, system: PhoibleFeatureSystem) -> None:
        """System loads without error and has segments."""
        graphemes = system.list_graphemes()
        assert len(graphemes) > 0

    def test_coverage_minimum(self, system: PhoibleFeatureSystem) -> None:
        """Coverage should be at least 3000 segments."""
        assert len(system.list_graphemes()) >= 3000

    def test_common_segments_resolve(self, system: PhoibleFeatureSystem) -> None:
        """Common IPA segments produce ValuedFeatures."""
        for grapheme in ("p", "b", "t", "d", "k", "a", "i", "u"):
            repr_ = system.grapheme_to_representation(grapheme)
            assert repr_ is not None, f"{grapheme!r} not found"
            assert isinstance(repr_, ValuedFeatures)

    def test_representation_kind(self, system: PhoibleFeatureSystem) -> None:
        assert system.representation_kind == "valued"

    def test_name(self, system: PhoibleFeatureSystem) -> None:
        assert system.name == "phoible"

    def test_unknown_grapheme(self, system: PhoibleFeatureSystem) -> None:
        assert system.grapheme_to_representation("ZZZZZ") is None


class TestPhoibleDistance:
    """Geometry-aware valued distance for PHOIBLE."""

    @pytest.fixture()
    def system(self) -> PhoibleFeatureSystem:
        return PhoibleFeatureSystem()

    def test_identical_zero(self, system: PhoibleFeatureSystem) -> None:
        repr_p = system.grapheme_to_representation("p")
        assert repr_p is not None
        assert system.segment_distance(repr_p, repr_p) == 0.0

    def test_voicing_pair(self, system: PhoibleFeatureSystem) -> None:
        repr_p = system.grapheme_to_representation("p")
        repr_b = system.grapheme_to_representation("b")
        assert repr_p is not None and repr_b is not None
        d = system.segment_distance(repr_p, repr_b)
        assert 0.0 < d < 0.2

    def test_place_larger_than_voicing(self, system: PhoibleFeatureSystem) -> None:
        repr_p = system.grapheme_to_representation("p")
        repr_t = system.grapheme_to_representation("t")
        repr_b = system.grapheme_to_representation("b")
        assert repr_p is not None and repr_t is not None and repr_b is not None
        d_voicing = system.segment_distance(repr_p, repr_b)
        d_place = system.segment_distance(repr_p, repr_t)
        assert d_place > d_voicing

    def test_symmetry(self, system: PhoibleFeatureSystem) -> None:
        repr_a = system.grapheme_to_representation("a")
        repr_i = system.grapheme_to_representation("i")
        assert repr_a is not None and repr_i is not None
        assert system.segment_distance(repr_a, repr_i) == pytest.approx(
            system.segment_distance(repr_i, repr_a),
        )

    def test_node_weights_string_preset(self, system: PhoibleFeatureSystem) -> None:
        repr_p = system.grapheme_to_representation("p")
        repr_b = system.grapheme_to_representation("b")
        assert repr_p is not None and repr_b is not None
        d = system.segment_distance(repr_p, repr_b, node_weights="segmental")
        assert isinstance(d, float) and d > 0.0


class TestPhoibleRegistry:
    """PHOIBLE is registered and accessible via high-level API."""

    def test_registered(self) -> None:
        sys = get_system("phoible")
        assert sys.name == "phoible"

    def test_distance_via_api(self) -> None:
        d = distance("p", "b", system="phoible")
        assert isinstance(d, float) and d > 0.0

    def test_distance_with_node_weights(self) -> None:
        d = distance("p", "b", system="phoible", node_weights="ignore-tone")
        assert isinstance(d, float) and d > 0.0
