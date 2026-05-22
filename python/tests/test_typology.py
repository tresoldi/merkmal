"""Tests for typological direction costs (asymmetric distance)."""

import pytest

from merkmal.typology import DirectionCost, Typology, load_typology


def test_load_default_typology() -> None:
    typ = load_typology("default")
    assert typ.name == "default"
    assert typ.direction_costs == {}


def test_load_lenition_bias() -> None:
    typ = load_typology("lenition-bias")
    assert typ.name == "lenition-bias"
    assert "voice" in typ.direction_costs
    assert "continuant" in typ.direction_costs
    dc = typ.direction_costs["continuant"]
    assert dc.neg_to_pos == 0.75
    assert dc.pos_to_neg == 1.25


def test_unknown_typology_raises() -> None:
    with pytest.raises(FileNotFoundError, match="Typology not found"):
        load_typology("nonexistent-typology")


def test_direction_cost_defaults() -> None:
    dc = DirectionCost()
    assert dc.pos_to_neg == 1.0
    assert dc.neg_to_pos == 1.0


def test_typology_cost_for_symmetric() -> None:
    typ = Typology(name="sym", direction_costs={})
    assert typ.cost_for("voice", 2.0) == 2.0
    assert typ.cost_for("voice", -2.0) == 2.0
    assert typ.cost_for("voice", 0.0) == 0.0


def test_typology_cost_for_asymmetric() -> None:
    typ = Typology(
        name="test",
        direction_costs={"voice": DirectionCost(pos_to_neg=0.5, neg_to_pos=1.5)},
    )
    assert typ.cost_for("voice", 2.0) == 1.0
    assert typ.cost_for("voice", -2.0) == 3.0
    assert typ.cost_for("unknown_feat", 2.0) == 2.0


class TestSymmetricDefault:
    def test_default_typology_gives_same_as_no_typology(self) -> None:
        import merkmal

        d_sym = merkmal.distance("p", "b")
        d_default = merkmal.distance("p", "b", typology="default")
        assert d_sym == pytest.approx(d_default)

    def test_symmetric_without_typology(self) -> None:
        import merkmal

        d_pb = merkmal.distance("p", "b")
        d_bp = merkmal.distance("b", "p")
        assert d_pb == d_bp


class TestAsymmetricDistance:
    def test_p_b_asymmetric(self) -> None:
        """p and b differ on the voice leaf; direction costs should make them asymmetric."""
        import merkmal

        d_pb = merkmal.distance("p", "b", typology="lenition-bias")
        d_bp = merkmal.distance("b", "p", typology="lenition-bias")
        assert d_pb != d_bp

    def test_devoicing_cheaper_than_voicing(self) -> None:
        """b->p (devoicing, pos_to_neg=0.85) should be cheaper than p->b (voicing, neg_to_pos=1.15)."""
        import merkmal

        d_pb = merkmal.distance("p", "b", typology="lenition-bias")
        d_bp = merkmal.distance("b", "p", typology="lenition-bias")
        assert d_bp < d_pb

    def test_identical_segments_zero(self) -> None:
        import merkmal

        assert merkmal.distance("p", "p", typology="lenition-bias") == 0.0
        assert merkmal.distance("f", "f", typology="lenition-bias") == 0.0

    def test_no_typology_stays_symmetric(self) -> None:
        """Without typology, p/b distance should remain symmetric."""
        import merkmal

        d_pb = merkmal.distance("p", "b")
        d_bp = merkmal.distance("b", "p")
        assert d_pb == d_bp
