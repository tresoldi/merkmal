"""Tests for the analysis helper APIs."""

import pytest

from merkmal import (
    FeatureMatrix,
    FeatureState,
    derive_class_features,
    distance,
    features_to_graphemes,
    get_system,
    inventory_weights,
    minimal_matrix,
    tabulate_matrix,
    valued_distance,
    valued_matches,
)


def test_features_to_graphemes_partial() -> None:
    """Partial queries should return matching graphemes."""
    matches = features_to_graphemes(frozenset({"vowel"}))
    assert "a" in matches
    assert "p" not in matches


def test_features_to_graphemes_negative_query() -> None:
    """Negative feature queries should honor partial-match semantics."""
    matches = features_to_graphemes(frozenset({"consonant", "-voiced"}))
    assert "p" in matches
    assert "b" not in matches


def test_features_to_graphemes_exact() -> None:
    """Exact queries should only return exact feature matches."""
    system = get_system("descriptive")
    features = system.grapheme_to_features("a")
    assert features is not None
    matches = features_to_graphemes(features, exact=True)
    assert "a" in matches


def test_derive_class_features() -> None:
    """Derived class features should be the strict feature intersection."""
    features = derive_class_features(["t", "d"])
    assert "consonant" in features
    assert "alveolar" in features
    assert "stop" in features
    assert "voiced" not in features


def test_minimal_matrix_categorical() -> None:
    """Categorical systems should yield a boolean feature matrix."""
    matrix = minimal_matrix(["t", "d"], system="descriptive")
    assert isinstance(matrix, FeatureMatrix)
    assert matrix.mode == "categorical"
    assert matrix.columns == ("voiced",)
    assert matrix.rows["t"] == (False,)
    assert matrix.rows["d"] == (True,)


def test_minimal_matrix_distinctive() -> None:
    """The distinctive system should produce a scalar matrix."""
    matrix = minimal_matrix(["t", "d"], system="distinctive")
    assert isinstance(matrix, FeatureMatrix)
    assert matrix.mode == "scalar"
    assert matrix.columns
    assert all(isinstance(value, float) for value in matrix.rows["t"])


def test_tabulate_matrix_plain() -> None:
    """Plain-text matrix rendering should include a header and rows."""
    matrix = minimal_matrix(["t", "d"], system="descriptive")
    rendered = tabulate_matrix(matrix)
    assert "grapheme" in rendered
    assert "t" in rendered
    assert "d" in rendered


def test_tabulate_matrix_markdown() -> None:
    """Markdown rendering should include a markdown separator row."""
    matrix = minimal_matrix(["t", "d"], system="descriptive")
    rendered = tabulate_matrix(matrix, format="markdown")
    assert " | " in rendered
    assert "---" in rendered


def test_tabulate_matrix_invalid_format() -> None:
    """Unsupported formats should fail explicitly."""
    matrix = minimal_matrix(["t", "d"], system="descriptive")
    with pytest.raises(NotImplementedError):
        tabulate_matrix(matrix, format="csv")


def test_distance_helper() -> None:
    """The helper should resolve graphemes and compute system distance."""
    assert distance("a", "a") == 0.0
    assert distance("a", "e") >= 0.0


def test_distance_precomputed() -> None:
    """Precomputed distance data should override system lookup."""
    matrix = {"a": {"e": 1.5}}
    assert distance("a", "e", precomputed=matrix) == 1.5
    assert distance("e", "a", precomputed=matrix) == 1.5


def test_distance_precomputed_missing_pair() -> None:
    """Missing precomputed entries should fail explicitly."""
    with pytest.raises(KeyError):
        distance("a", "u", precomputed={"a": {"e": 1.5}})


def test_features_to_graphemes_pbase_partial() -> None:
    """Valued systems should support dict-based partial queries."""
    matches = features_to_graphemes({"syllabic": "+"}, system="pbase-hc")
    assert "a" in matches
    assert "p" not in matches


def test_features_to_graphemes_pbase_exact() -> None:
    """Valued systems should support exact native-state matching."""
    system = get_system("pbase-hc")
    representation = system.grapheme_to_representation("a")
    assert representation is not None
    matches = features_to_graphemes(representation.values, system="pbase-hc", exact=True)
    assert "a" in matches


def test_derive_class_features_pbase() -> None:
    """Valued systems should derive shared multi-state features."""
    features = derive_class_features(["t", "d"], system="pbase-hc")
    assert isinstance(features, dict)
    assert features["consonantal"] == FeatureState.POSITIVE
    assert "voice" not in features


def test_minimal_matrix_pbase() -> None:
    """P-base systems should yield valued feature matrices."""
    matrix = minimal_matrix(["t", "d"], system="pbase-hc")
    assert isinstance(matrix, FeatureMatrix)
    assert matrix.mode == "valued"
    assert matrix.columns == ("voice",)
    assert matrix.rows["t"] == (FeatureState.NEGATIVE,)
    assert matrix.rows["d"] == (FeatureState.POSITIVE,)


def test_tabulate_matrix_pbase() -> None:
    """Valued matrix rendering should preserve symbolic feature states."""
    matrix = minimal_matrix(["t", "d"], system="pbase-hc")
    rendered = tabulate_matrix(matrix)
    assert "+" in rendered
    assert "-" in rendered


def test_distance_helper_pbase() -> None:
    """The distance helper should use native multi-state distances."""
    assert distance("a", "a", system="pbase-hc") == 0.0
    assert distance("t", "d", system="pbase-hc") > 0.0


def test_valued_matches_dot_policies() -> None:
    """DOT handling in valued matching should be configurable."""
    query = {"syllabic": FeatureState.DOT, "voice": FeatureState.POSITIVE}
    target = {"syllabic": FeatureState.NEGATIVE, "voice": FeatureState.POSITIVE}
    assert valued_matches(query, target, dot_policy="strict") is False
    assert valued_matches(query, target, dot_policy="query-wildcard") is True
    assert valued_matches(query, target, dot_policy="either-wildcard") is True


def test_valued_distance_dot_policies() -> None:
    """DOT handling in valued distance should be configurable."""
    left = {"syllabic": FeatureState.DOT, "voice": FeatureState.POSITIVE}
    right = {"syllabic": FeatureState.NEGATIVE, "voice": FeatureState.POSITIVE}
    assert valued_distance(left, right, dot_policy="ignore") == 0.0
    assert valued_distance(left, right, dot_policy="partial") == 0.25
    assert valued_distance(left, right, dot_policy="strict") == 0.5


def test_features_to_graphemes_valued_dot_policy() -> None:
    """Valued grapheme queries should support wildcard DOT policies."""
    strict = features_to_graphemes(
        {"syllabic": ".", "vocalic": "+"},
        system="pbase-hc",
        valued_dot_policy="strict",
    )
    wildcard = features_to_graphemes(
        {"syllabic": ".", "vocalic": "+"},
        system="pbase-hc",
        valued_dot_policy="query-wildcard",
    )
    assert len(wildcard) >= len(strict)
    assert "a" in wildcard


# -- Compositional query expansion --


class TestCompose:
    """Tests for features_to_graphemes with compose parameter."""

    _ASPIRATED_P = frozenset({
        "consonant", "voiceless", "bilabial", "stop", "aspirated",
    })

    def test_compose_false_is_default(self) -> None:
        """Default compose=False only returns table graphemes."""
        result = features_to_graphemes(self._ASPIRATED_P, compose=False)
        assert result == features_to_graphemes(self._ASPIRATED_P)

    def test_compose_true_finds_composed(self) -> None:
        """compose=True finds aspirated p via composition."""
        result = features_to_graphemes(
            self._ASPIRATED_P, compose=True, exact=True,
        )
        assert len(result) >= 1
        assert any("ʰ" in g for g in result)

    def test_compose_list_single_modifier(self) -> None:
        """compose=[modifier] expands with that specific modifier."""
        result = features_to_graphemes(
            self._ASPIRATED_P, compose=["aspirated"], exact=True,
        )
        assert len(result) >= 1
        assert any("ʰ" in g for g in result)

    def test_compose_list_multi_modifier(self) -> None:
        """compose=[m1, m2] tries all subsets including the pair."""
        query = frozenset({
            "vowel", "open", "front", "unrounded",
            "nasalized", "long",
        })
        result = features_to_graphemes(
            query, compose=["nasalized", "long"], exact=True,
        )
        assert len(result) >= 1

    def test_compose_no_duplicates(self) -> None:
        """Composed results should not duplicate table entries."""
        query = frozenset({"vowel", "open", "front", "unrounded"})
        result = features_to_graphemes(query, compose=True, exact=True)
        assert len(result) == len(set(result))


# -- Inventory weights --


class TestInventoryWeights:
    """Tests for inventory_weights()."""

    _HAWAIIAN = ("p", "k", "ʔ", "m", "n", "ŋ", "h", "l", "w")
    _GEORGIAN = ("p", "pʰ", "b", "t", "tʰ", "d", "k", "kʰ", "g")

    def test_hawaiian_manner_high(self) -> None:
        """Hawaiian has diverse manner classes -> Manner weight should be highest."""
        w = inventory_weights(list(self._HAWAIIAN))
        assert "Manner" in w
        assert w["Manner"] == max(w.values())

    def test_hawaiian_laryngeal_lower_than_manner(self) -> None:
        """Hawaiian is mostly voiceless -> Laryngeal weight < Manner weight."""
        w = inventory_weights(list(self._HAWAIIAN))
        assert w.get("Laryngeal", 0.0) < w["Manner"]

    def test_georgian_laryngeal_high(self) -> None:
        """Georgian has 3-way laryngeal contrast -> Laryngeal weight high."""
        w = inventory_weights(list(self._GEORGIAN))
        assert "Laryngeal" in w
        assert w["Laryngeal"] > w.get("Manner", 0.0) or w["Laryngeal"] >= 0.45

    def test_georgian_laryngeal_exceeds_hawaiian(self) -> None:
        """Georgian Laryngeal weight > Hawaiian Laryngeal weight."""
        hw = inventory_weights(list(self._HAWAIIAN))
        gw = inventory_weights(list(self._GEORGIAN))
        assert gw["Laryngeal"] > hw["Laryngeal"]

    def test_weights_work_with_distance(self) -> None:
        """Returned dict integrates with distance(node_weights=...)."""
        w = inventory_weights(list(self._HAWAIIAN))
        d = distance("p", "b", node_weights=w)
        assert isinstance(d, float)
        assert d > 0.0

    def test_single_segment_empty(self) -> None:
        """Single-segment inventory returns empty weights."""
        w = inventory_weights(["p"])
        assert w == {}

    def test_empty_inventory(self) -> None:
        """Empty inventory returns empty weights."""
        w = inventory_weights([])
        assert w == {}

    def test_place_distinction_nonzero(self) -> None:
        """Node-mapped place features yield non-zero weights for d(p,k)."""
        w = inventory_weights(list(self._HAWAIIAN))
        d = distance("p", "k", node_weights=w)
        assert d > 0.0

    def test_all_weights_between_zero_and_one(self) -> None:
        """All weights should be in (0, 1]."""
        for inv in (self._HAWAIIAN, self._GEORGIAN):
            w = inventory_weights(list(inv))
            for v in w.values():
                assert 0.0 < v <= 1.0
