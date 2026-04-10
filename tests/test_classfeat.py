"""Tests for the ClassFeat feature system."""

from __future__ import annotations

import pytest

from merkmal.representations import FeatureState, ValuedFeatures
from merkmal.systems.classfeat import (
    CLASS_NAMES,
    FEATURE_NAMES,
    GEOMETRY_MAP,
    ClassFeatFeatureSystem,
    _classify_segment,
    classify_to_class,
)


@pytest.fixture
def sys() -> ClassFeatFeatureSystem:
    return ClassFeatFeatureSystem()


class TestClassifySegment:
    def test_voiceless_bilabial_stop(self) -> None:
        vec = _classify_segment("p")
        assert vec is not None
        assert vec["labial"] == 1.0
        assert vec["voice"] == -1.0
        assert vec["continuant"] == -1.0

    def test_voiced_bilabial_stop(self) -> None:
        vec = _classify_segment("b")
        assert vec is not None
        assert vec["labial"] == 1.0
        assert vec["voice"] == 1.0

    def test_voiceless_alveolar_fricative(self) -> None:
        vec = _classify_segment("s")
        assert vec is not None
        assert vec["sibilant"] == 1.0
        assert vec["continuant"] == 1.0
        assert vec["coronal"] == 1.0

    def test_close_front_vowel(self) -> None:
        vec = _classify_segment("i")
        assert vec is not None
        assert vec["syllabic"] == 1.0
        assert vec["high"] == 1.0
        assert vec["back"] == -1.0
        assert vec["round"] == -1.0

    def test_open_back_rounded_vowel(self) -> None:
        vec = _classify_segment("ɒ")
        assert vec is not None
        assert vec["high"] == -1.0
        assert vec["back"] == 1.0
        assert vec["round"] == 1.0

    def test_aspirated_stop(self) -> None:
        vec = _classify_segment("pʰ")
        assert vec is not None
        assert vec["aspirated"] == 1.0
        assert vec["labial"] == 1.0

    def test_affricate(self) -> None:
        vec = _classify_segment("t͡s")
        assert vec is not None
        assert vec["sibilant"] == 1.0
        assert vec["continuant"] == -1.0  # affricate class C

    def test_implosive(self) -> None:
        vec = _classify_segment("ɓ")
        assert vec is not None
        assert vec["glottalized"] == 1.0
        assert vec["labial"] == 1.0

    def test_unknown_returns_none(self) -> None:
        assert _classify_segment("🎵") is None

    def test_tone_digits(self) -> None:
        vec = _classify_segment("a⁵⁵")
        assert vec is not None
        assert vec["tone_onset"] == 1.0
        assert vec["tone_mid"] == 1.0
        assert vec["tone_offset"] == 1.0

    def test_falling_tone(self) -> None:
        vec = _classify_segment("a⁵¹")
        assert vec is not None
        assert vec["tone_onset"] == 1.0
        assert vec["tone_mid"] == 0.0  # (1.0 + -1.0) / 2
        assert vec["tone_offset"] == -1.0

    def test_level_tone_single_digit(self) -> None:
        vec = _classify_segment("a³")
        assert vec is not None
        assert vec["tone_onset"] == 0.0
        assert vec["tone_mid"] == 0.0
        assert vec["tone_offset"] == 0.0

    def test_three_digit_tone(self) -> None:
        vec = _classify_segment("a²¹³")
        assert vec is not None
        assert vec["tone_onset"] == -0.5  # Chao 2
        assert vec["tone_mid"] == -1.0    # Chao 1 (explicit)
        assert vec["tone_offset"] == 0.0  # Chao 3

    def test_all_features_present(self) -> None:
        vec = _classify_segment("p")
        assert vec is not None
        assert set(vec.keys()) == set(FEATURE_NAMES)


class TestClassFeatSystem:
    def test_name(self, sys: ClassFeatFeatureSystem) -> None:
        assert sys.name == "classfeat"

    def test_representation_kind(self, sys: ClassFeatFeatureSystem) -> None:
        assert sys.representation_kind == "valued"

    def test_grapheme_to_representation(self, sys: ClassFeatFeatureSystem) -> None:
        rep = sys.grapheme_to_representation("p")
        assert isinstance(rep, ValuedFeatures)
        assert rep.values["labial"] == FeatureState.POSITIVE
        assert rep.values["voice"] == FeatureState.NEGATIVE

    def test_grapheme_to_representation_none(self, sys: ClassFeatFeatureSystem) -> None:
        assert sys.grapheme_to_representation("🎵") is None

    def test_grapheme_to_features(self, sys: ClassFeatFeatureSystem) -> None:
        feats = sys.grapheme_to_features("p")
        assert isinstance(feats, frozenset)
        assert "labial=+" in feats
        assert "voice=-" in feats

    def test_list_graphemes(self, sys: ClassFeatFeatureSystem) -> None:
        graphemes = sys.list_graphemes()
        assert len(graphemes) > 50
        assert "p" in graphemes
        assert "a" in graphemes

    def test_segment_distance_identical(self, sys: ClassFeatFeatureSystem) -> None:
        rep = sys.grapheme_to_representation("p")
        assert rep is not None
        assert sys.segment_distance(rep, rep) == 0.0

    def test_segment_distance_voicing(self, sys: ClassFeatFeatureSystem) -> None:
        rp = sys.grapheme_to_representation("p")
        rb = sys.grapheme_to_representation("b")
        assert rp is not None and rb is not None
        d = sys.segment_distance(rp, rb)
        assert 0.0 < d < 1.0

    def test_segment_distance_p_vs_a(self, sys: ClassFeatFeatureSystem) -> None:
        rp = sys.grapheme_to_representation("p")
        ra = sys.grapheme_to_representation("a")
        assert rp is not None and ra is not None
        d_pa = sys.segment_distance(rp, ra)
        # p vs a should be larger than p vs b
        rb = sys.grapheme_to_representation("b")
        assert rb is not None
        d_pb = sys.segment_distance(rp, rb)
        assert d_pa > d_pb

    def test_grapheme_vector(self, sys: ClassFeatFeatureSystem) -> None:
        vec = sys.grapheme_vector("p")
        assert vec is not None
        assert isinstance(vec, dict)
        assert vec["labial"] == 1.0

    def test_features_to_grapheme_returns_none(self, sys: ClassFeatFeatureSystem) -> None:
        assert sys.features_to_grapheme(frozenset()) is None


class TestClassifyToClass:
    def test_basic_consonants(self) -> None:
        assert classify_to_class("p") == "P"
        assert classify_to_class("t") == "T"
        assert classify_to_class("k") == "K"
        assert classify_to_class("q") == "Q"

    def test_split_h(self) -> None:
        assert classify_to_class("h") == "Hf"
        assert classify_to_class("ʔ") == "Hq"

    def test_split_k_q(self) -> None:
        assert classify_to_class("k") == "K"
        assert classify_to_class("q") == "Q"
        assert classify_to_class("ɢ") == "Q"

    def test_split_n_ng(self) -> None:
        assert classify_to_class("n") == "N"
        assert classify_to_class("ŋ") == "Ng"

    def test_split_i_ic(self) -> None:
        assert classify_to_class("i") == "I"
        assert classify_to_class("ɨ") == "Ic"
        assert classify_to_class("ɯ") == "Ic"

    def test_split_a_ab(self) -> None:
        assert classify_to_class("a") == "A"
        assert classify_to_class("ɑ") == "Ab"

    def test_merge_u_y_to_v(self) -> None:
        assert classify_to_class("u") == "V"
        assert classify_to_class("y") == "V"
        assert classify_to_class("ʉ") == "V"

    def test_merge_b_w_to_f(self) -> None:
        assert classify_to_class("f") == "F"
        assert classify_to_class("v") == "F"
        assert classify_to_class("w") == "F"

    def test_affricates_in_c(self) -> None:
        assert classify_to_class("t͡s") == "C"
        assert classify_to_class("d͡ʒ") == "C"
        assert classify_to_class("c") == "C"

    def test_unknown_returns_none(self) -> None:
        assert classify_to_class("🎵") is None

    def test_24_classes(self) -> None:
        assert len(CLASS_NAMES) == 24

    def test_stress_stripped(self) -> None:
        assert classify_to_class("ˈp") == "P"
        assert classify_to_class("ˌt") == "T"

    def test_prenasalised(self) -> None:
        assert classify_to_class("ⁿd") == "T"
        assert classify_to_class("ᵐb") == "P"

    def test_legacy_ipa(self) -> None:
        assert classify_to_class("ʧ") == "C"  # legacy affricate

    def test_slash_notation(self) -> None:
        # Takes the right side
        assert classify_to_class("ќ/kʼ") is not None


class TestGraphemeCost:
    def test_identical_zero(self, sys: ClassFeatFeatureSystem) -> None:
        cost = sys.grapheme_cost("p", "p")
        assert cost == 0.0

    def test_same_class_low(self, sys: ClassFeatFeatureSystem) -> None:
        cost_pb = sys.grapheme_cost("p", "b")
        cost_pa = sys.grapheme_cost("p", "a")
        assert cost_pb < cost_pa

    def test_unknown_returns_one(self, sys: ClassFeatFeatureSystem) -> None:
        assert sys.grapheme_cost("p", "🎵") == 1.0

    def test_symmetric(self, sys: ClassFeatFeatureSystem) -> None:
        assert sys.grapheme_cost("p", "t") == sys.grapheme_cost("t", "p")


class TestGeometryMap:
    def test_all_features_mapped(self) -> None:
        assert set(GEOMETRY_MAP.keys()) == set(FEATURE_NAMES)

    def test_known_nodes(self) -> None:
        assert GEOMETRY_MAP["labial"] == "Labial"
        assert GEOMETRY_MAP["voice"] == "Laryngeal"
        assert GEOMETRY_MAP["syllabic"] == "Manner"
        assert GEOMETRY_MAP["tone_onset"] == "TonalOnset"
