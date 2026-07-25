"""Tests for grapheme normalization and IPA segmentation."""

import unicodedata

import pytest

from merkmal.grapheme import (
    decompose_grapheme,
    normalize,
    normalize_input_grapheme,
    normalize_sequences,
    segment_ipa,
)


class TestNormalizeInputGrapheme:
    def test_nfd_decomposition(self) -> None:
        result = normalize_input_grapheme("ü")
        assert result == unicodedata.normalize("NFD", "ü")

    def test_ipa_g_equivalence(self) -> None:
        assert normalize_input_grapheme("ɡ") == "g"

    def test_apostrophe_to_ejective(self) -> None:
        assert normalize_input_grapheme("t'") == "tʼ"

    def test_clts_slash_keeps_post_value(self) -> None:
        assert normalize_input_grapheme("y/j") == "j"
        assert normalize_input_grapheme("sh/ʃ") == "ʃ"
        # last slash wins; pre-slash content is discarded
        assert normalize_input_grapheme("tsʰ~ʨʰ/ʨʰ") == normalize_input_grapheme("ʨʰ")

    def test_affricate_ligatures_expand(self) -> None:
        assert normalize_input_grapheme("ʤ") == "dʒ"
        assert normalize_input_grapheme("ʧ") == "tʃ"
        assert normalize_input_grapheme("ʨ") == "tɕ"

    def test_ascii_colon_is_length(self) -> None:
        assert normalize_input_grapheme("a:") == "aː"

    def test_leading_stress_stripped(self) -> None:
        assert normalize_input_grapheme("ˈɛ") == "ɛ"
        assert normalize_input_grapheme("ˌa") == "a"


class TestNormalize:
    def test_canonical_nfc_and_preferred_ipa(self) -> None:
        assert normalize("y/j") == "j"
        assert normalize("ʤ") == "dʒ"
        assert normalize("a:") == "aː"
        assert normalize("ˈɛ") == "ɛ"
        assert normalize("g") == "ɡ"  # mapped back to preferred IPA
        assert normalize(unicodedata.normalize("NFD", "ã")) == "ã"  # NFC output

    def test_idempotent_on_clean_ipa(self) -> None:
        for g in ("p", "t̠ʃ", "aː", "kʰ", "o⁵⁵"):
            assert normalize(g) == normalize(normalize(g))

    def test_bare_stress_normalizes_away(self) -> None:
        assert normalize("ˈ") == ""


class TestNormalizeSequences:
    def test_tie_bar_stripping(self) -> None:
        candidates = normalize_sequences("t͡s")
        assert "ts" in candidates

    def test_affricate_retraction(self) -> None:
        candidates = normalize_sequences("tʃ")
        assert any("̠" in c for c in candidates)

    def test_no_candidates_for_simple(self) -> None:
        assert normalize_sequences("p") == []


class TestDecomposeGrapheme:
    def test_simple_base(self) -> None:
        base, mods = decompose_grapheme("p")
        assert base == "p"
        assert mods == frozenset()

    def test_aspirated(self) -> None:
        base, mods = decompose_grapheme("pʰ")
        assert base == "p"
        assert "aspirated" in mods

    def test_devoiced_combining(self) -> None:
        base, mods = decompose_grapheme(normalize_input_grapheme("n̥"))
        assert "devoiced" in mods

    def test_prefix_modifier(self) -> None:
        base, mods = decompose_grapheme("ⁿd")
        assert base == "d"
        assert "pre-nasalized" in mods

    def test_long(self) -> None:
        base, mods = decompose_grapheme("aː")
        assert base == "a"
        assert "long" in mods

    def test_chao_tone(self) -> None:
        base, mods = decompose_grapheme("a⁵⁵")
        assert base == "a"
        assert "tone-onset-upper" in mods


class TestSegmentIPA:
    def test_simple_cv(self) -> None:
        assert segment_ipa("pa") == ["p", "a"]

    def test_aspirated_onset(self) -> None:
        assert segment_ipa("tʰoŋ") == ["tʰ", "o", "ŋ"]

    def test_affricate_with_tie_bar(self) -> None:
        assert segment_ipa("t͡sʰa") == ["t͡sʰ", "a"]

    def test_doubly_articulated_with_tie_bar(self) -> None:
        assert segment_ipa("k͡pa") == ["k͡p", "a"]

    def test_prenasalized(self) -> None:
        assert segment_ipa("ⁿda") == ["ⁿd", "a"]

    def test_long_vowel(self) -> None:
        assert segment_ipa("aːi") == ["aː", "i"]

    def test_chao_digits_separate(self) -> None:
        assert segment_ipa("kan⁵⁵") == ["k", "a", "n", "⁵⁵"]

    def test_boundary_marker(self) -> None:
        assert segment_ipa("a+b") == ["a", "+", "b"]

    def test_syllable_boundary(self) -> None:
        assert segment_ipa("a.b") == ["a", ".", "b"]

    def test_spaces_split(self) -> None:
        assert segment_ipa("p a") == ["p", "a"]

    def test_combining_diacritics(self) -> None:
        result = segment_ipa("n̥a")
        assert len(result) == 2
        assert "a" in result[1]

    def test_multiple_chao_groups(self) -> None:
        result = segment_ipa("tʰo³¹pan¹³")
        assert "³¹" in result
        assert "¹³" in result

    def test_empty_string(self) -> None:
        assert segment_ipa("") == []

    def test_single_segment(self) -> None:
        assert segment_ipa("p") == ["p"]

    def test_cluster(self) -> None:
        assert segment_ipa("str") == ["s", "t", "r"]

    @pytest.mark.parametrize(
        "ipa",
        ["pʰatʰa", "t͡sʰit͡sʰa", "ⁿdaⁿba"],
    )
    def test_roundtrip_join(self, ipa: str) -> None:
        nfd = unicodedata.normalize("NFD", ipa)
        assert "".join(segment_ipa(ipa)) == nfd

    def test_pipeline_with_merge(self) -> None:
        from merkmal.segmentation import merge_tone_digits

        segments = segment_ipa("tʰo³¹pan¹³")
        merged = merge_tone_digits(segments)
        assert "o³¹" in merged
