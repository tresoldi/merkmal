"""Tests for UPA (Uralic Phonetic Alphabet) transcription adapter."""

from __future__ import annotations

import pytest

from merkmal.upa import adapt, adapt_segment, segment_upa


# ---------------------------------------------------------------------------
# Segmenter tests
# ---------------------------------------------------------------------------


class TestSegmentUpa:
    """Tests for the UPA string segmenter."""

    def test_simple_word(self) -> None:
        assert segment_upa("kala") == ["k", "a", "l", "a"]

    def test_combining_diacritics_stay_attached(self) -> None:
        # i + combining breve below = single segment
        result = segment_upa("ni\u032Er")
        assert len(result) == 3
        assert result[1] == "i\u032E"

    def test_acute_accent_attached(self) -> None:
        # ń = n + combining acute (NFD)
        result = segment_upa("ń")
        assert len(result) == 1

    def test_modifier_prime_attached(self) -> None:
        # lʹ = l + modifier prime
        result = segment_upa("l\u02B9")
        assert len(result) == 1
        assert result[0] == "l\u02B9"

    def test_multiple_diacritics(self) -> None:
        # macron + breve below on same vowel
        result = segment_upa("ī\u032E")
        assert len(result) == 1

    def test_whitespace_splits(self) -> None:
        assert segment_upa("ka la") == ["k", "a", "l", "a"]

    def test_punctuation_ignored(self) -> None:
        assert segment_upa("ka-la") == ["k", "a", "l", "a"]

    def test_empty_string(self) -> None:
        assert segment_upa("") == []

    def test_uralex_nganasan_nose(self) -> None:
        # ŋüŋkə
        result = segment_upa("ŋüŋkə")
        assert len(result) == 5

    def test_uralex_komi_nose(self) -> None:
        # ni̮r
        result = segment_upa("ni\u032Er")
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Base consonant mappings
# ---------------------------------------------------------------------------


class TestConsonantMapping:
    """Test UPA consonant → IPA mapping."""

    @pytest.mark.parametrize(
        ("upa", "ipa"),
        [
            ("b", "b"),
            ("d", "d"),
            ("f", "f"),
            ("g", "g"),
            ("k", "k"),
            ("l", "l"),
            ("m", "m"),
            ("n", "n"),
            ("p", "p"),
            ("r", "r"),
            ("s", "s"),
            ("t", "t"),
            ("v", "v"),
            ("z", "z"),
            ("h", "h"),
            ("w", "w"),
            ("j", "j"),
        ],
    )
    def test_basic_consonants(self, upa: str, ipa: str) -> None:
        assert adapt_segment(upa) == ipa

    def test_velar_nasal(self) -> None:
        assert adapt_segment("ŋ") == "ŋ"


# ---------------------------------------------------------------------------
# Greek letter fricatives
# ---------------------------------------------------------------------------


class TestGreekLetters:
    """Test UPA Greek letter → IPA mapping."""

    @pytest.mark.parametrize(
        ("upa", "ipa"),
        [
            ("\u03B2", "\u03B2"),   # β → β
            ("\u03B3", "\u0263"),   # γ → ɣ
            ("\u03B4", "\u00F0"),   # δ → ð
            ("\u03D1", "\u03B8"),   # ϑ → θ
            ("\u03C7", "x"),        # χ → x
            ("\u03C6", "\u0278"),   # φ → ɸ
        ],
    )
    def test_greek_fricatives(self, upa: str, ipa: str) -> None:
        assert adapt_segment(upa) == ipa


# ---------------------------------------------------------------------------
# Palatalized consonants (acute accent)
# ---------------------------------------------------------------------------


class TestPalatalization:
    """Test UPA palatalization conventions."""

    @pytest.mark.parametrize(
        ("upa", "ipa"),
        [
            ("ń", "\u0272"),       # ń → ɲ
            ("ś", "\u0255"),       # ś → ɕ
            ("ź", "\u0291"),       # ź → ʑ
            ("ĺ", "\u028E"),       # ĺ → ʎ
            ("ŕ", "r\u02B2"),      # ŕ → rʲ
            ("ć", "t\u0255"),      # ć → tɕ
        ],
    )
    def test_acute_palatalization(self, upa: str, ipa: str) -> None:
        assert adapt_segment(upa) == ipa

    def test_modifier_prime_palatalization(self) -> None:
        # lʹ → lʲ
        assert adapt_segment("l\u02B9") == "l\u02B2"

    def test_modifier_prime_on_d(self) -> None:
        # dʹ → dʲ
        assert adapt_segment("d\u02B9") == "d\u02B2"

    def test_modifier_prime_on_n(self) -> None:
        # nʹ → nʲ
        assert adapt_segment("n\u02B9") == "n\u02B2"


# ---------------------------------------------------------------------------
# Postalveolar consonants (caron)
# ---------------------------------------------------------------------------


class TestPostalveolar:
    """Test UPA caron → IPA postalveolar mapping."""

    @pytest.mark.parametrize(
        ("upa", "ipa"),
        [
            ("š", "\u0283"),       # š → ʃ
            ("ž", "\u0292"),       # ž → ʒ
            ("č", "t\u0283"),      # č → tʃ
            ("ǯ", "d\u0292"),      # ǯ → dʒ
        ],
    )
    def test_caron_postalveolar(self, upa: str, ipa: str) -> None:
        assert adapt_segment(upa) == ipa


# ---------------------------------------------------------------------------
# Vowel mappings
# ---------------------------------------------------------------------------


class TestVowelMapping:
    """Test UPA vowel → IPA mapping."""

    @pytest.mark.parametrize(
        ("upa", "ipa"),
        [
            ("a", "a"),
            ("e", "e"),
            ("i", "i"),
            ("o", "o"),
            ("u", "u"),
            ("ə", "ə"),
        ],
    )
    def test_basic_vowels(self, upa: str, ipa: str) -> None:
        assert adapt_segment(upa) == ipa

    @pytest.mark.parametrize(
        ("upa", "ipa"),
        [
            ("ä", "\u00E6"),       # ä → æ
            ("ö", "\u00F8"),       # ö → ø
            ("ü", "y"),            # ü → y
        ],
    )
    def test_umlaut_vowels(self, upa: str, ipa: str) -> None:
        assert adapt_segment(upa) == ipa

    @pytest.mark.parametrize(
        ("upa", "ipa"),
        [
            ("ā", "a\u02D0"),     # ā → aː
            ("ē", "e\u02D0"),     # ē → eː
            ("ī", "i\u02D0"),     # ī → iː
            ("ō", "o\u02D0"),     # ō → oː
            ("ū", "u\u02D0"),     # ū → uː
            ("ǖ", "y\u02D0"),     # ǖ → yː
            ("ǟ", "\u00E6\u02D0"),  # ǟ → æː
            ("ȫ", "\u00F8\u02D0"),  # ȫ → øː
        ],
    )
    def test_long_vowels(self, upa: str, ipa: str) -> None:
        assert adapt_segment(upa) == ipa


# ---------------------------------------------------------------------------
# Back unrounded vowels (breve below)
# ---------------------------------------------------------------------------


class TestBackUnrounded:
    """Test UPA breve-below → back unrounded vowel remapping."""

    @pytest.mark.parametrize(
        ("upa", "ipa"),
        [
            ("i\u032E", "\u026F"),       # i̮ → ɯ
            ("e\u032E", "\u0264"),       # e̮ → ɤ
            ("a\u032E", "\u0251"),       # a̮ → ɑ
        ],
    )
    def test_breve_below_remapping(self, upa: str, ipa: str) -> None:
        assert adapt_segment(upa) == ipa

    def test_long_back_unrounded(self) -> None:
        # ī̮ (long + breve below) → ɯː
        assert adapt_segment("ī\u032E") == "\u026F\u02D0"


# ---------------------------------------------------------------------------
# Inverted breve above (backing diacritic)
# ---------------------------------------------------------------------------


class TestInvertedBreveAbove:
    """Test UPA inverted breve above as backing diacritic."""

    def test_schwa_backed(self) -> None:
        # ə̑ → ɤ
        assert adapt_segment("ə\u0311") == "\u0264"


# ---------------------------------------------------------------------------
# Small capitals (devoiced)
# ---------------------------------------------------------------------------


class TestSmallCapitals:
    """Test UPA small capital → devoiced IPA mapping."""

    @pytest.mark.parametrize(
        ("upa", "ipa"),
        [
            ("\u0299", "b\u0325"),   # ʙ → b̥
            ("\u1D05", "d\u0325"),   # ᴅ → d̥
            ("\u1D22", "z\u0325"),   # ᴢ → z̥
        ],
    )
    def test_small_cap_devoiced(self, upa: str, ipa: str) -> None:
        assert adapt_segment(upa) == ipa


# ---------------------------------------------------------------------------
# Full word tests (from UraLex data)
# ---------------------------------------------------------------------------


class TestUraLexWords:
    """Test full UPA words from the UraLex dataset."""

    def test_nganasan_nose(self) -> None:
        # ŋüŋkə → [ŋ, y, ŋ, k, ə]
        result = adapt("ŋüŋkə")
        assert result == ["ŋ", "y", "ŋ", "k", "ə"]

    def test_meadow_mari_water(self) -> None:
        # βüt → [β, y, t]
        result = adapt("\u03B2üt")
        assert result == ["\u03B2", "y", "t"]

    def test_selkup_fire(self) -> None:
        # tǖ → [t, yː]
        result = adapt("tǖ")
        assert result == ["t", "y\u02D0"]

    def test_komi_nose(self) -> None:
        # ni̮r → [n, ɯ, r]
        result = adapt("ni\u032Er")
        assert result == ["n", "\u026F", "r"]

    def test_udmurt_go(self) -> None:
        # mi̮ni̮ni̮ → [m, ɯ, n, ɯ, n, ɯ]
        result = adapt("mi\u032Eni\u032Eni\u032E")
        assert result == ["m", "\u026F", "n", "\u026F", "n", "\u026F"]

    def test_sosva_mansi_tongue(self) -> None:
        # ńēləm → [ɲ, eː, l, ə, m]
        result = adapt("ńēləm")
        assert result == ["\u0272", "e\u02D0", "l", "ə", "m"]

    def test_nganasan_water(self) -> None:
        # bi̮ˀ → [b, ɯ, ʔ]
        result = adapt("bi\u032Eˀ")
        assert result == ["b", "\u026F", "ʔ"]

    def test_ingrian_nose(self) -> None:
        # nenä → [n, e, n, æ]
        result = adapt("nenä")
        assert result == ["n", "e", "n", "\u00E6"]

    def test_vakh_khanty_fire(self) -> None:
        # tö̆ɣət → [t, ø̆, ɣ, ə, t]
        result = adapt("tö\u0306\u0263ət")
        assert len(result) == 5
        assert result[0] == "t"
        assert result[4] == "t"


# ---------------------------------------------------------------------------
# Integration with merkmal feature system
# ---------------------------------------------------------------------------


class TestFeatureIntegration:
    """Test that UPA segments produce valid features through merkmal."""

    def test_get_features_with_transcription(self) -> None:
        from merkmal import get_features
        feats = get_features("š", transcription="upa")
        assert feats is not None
        assert "fricative" in feats

    def test_get_features_upa_vowel(self) -> None:
        from merkmal import get_features
        feats = get_features("ü", transcription="upa")
        assert feats is not None
        assert "rounded" in feats
        assert "front" in feats

    def test_get_features_back_unrounded(self) -> None:
        from merkmal import get_features
        feats = get_features("i\u032E", transcription="upa")
        assert feats is not None
        assert "back" in feats or "unrounded" in feats

    def test_get_features_palatalized(self) -> None:
        from merkmal import get_features
        feats = get_features("ń", transcription="upa")
        assert feats is not None

    def test_unknown_transcription_raises(self) -> None:
        from merkmal import get_features
        with pytest.raises(ValueError, match="Unknown transcription"):
            get_features("a", transcription="unknown")

    def test_segment_distance_with_transcription(self) -> None:
        from merkmal import segment_distance
        # UPA š vs s should have nonzero distance
        d = segment_distance("š", "s", system="distinctive", transcription="upa")
        assert d > 0

    def test_get_representation_with_transcription(self) -> None:
        from merkmal import get_representation
        rep = get_representation("δ", transcription="upa")
        assert rep is not None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and robustness tests."""

    def test_plain_ipa_passthrough(self) -> None:
        # IPA symbols that happen to exist in both systems
        assert adapt_segment("p") == "p"
        assert adapt_segment("a") == "a"

    def test_glottal_stop_marker(self) -> None:
        assert adapt_segment("ˀ") == "ʔ"

    def test_empty_segment(self) -> None:
        assert adapt("") == []

    def test_hyphenated_verb_stem(self) -> None:
        # UraLex has trailing hyphens on verb stems
        result = adapt("mən-")
        assert result == ["m", "ə", "n"]

    def test_precomposed_vs_decomposed_match(self) -> None:
        # ń as precomposed (U+0144) vs n + combining acute
        import unicodedata
        precomposed = "\u0144"
        decomposed = unicodedata.normalize("NFD", precomposed)
        assert adapt_segment(precomposed) == adapt_segment(decomposed)

    def test_cyrillic_schwa_normalized(self) -> None:
        # Cyrillic schwa (U+04D9) should map to IPA schwa.
        assert adapt_segment("\u04D9") == "\u0259"

    def test_nobreak_space_splits(self) -> None:
        # NO-BREAK SPACE should work as delimiter.
        assert adapt("ka\u00A0la") == ["k", "a", "l", "a"]

    def test_underscore_boundary(self) -> None:
        # Underscore is a morpheme boundary, should be stripped.
        assert adapt("ka_la") == ["k", "a", "l", "a"]


# ---------------------------------------------------------------------------
# Combining marks (compositional decomposition)
# ---------------------------------------------------------------------------


class TestCombiningMarks:
    """Test UPA combining marks handled compositionally."""

    def test_combining_caron_on_s(self) -> None:
        # s + combining caron = š → ʃ
        assert adapt_segment("s\u030C") == "\u0283"

    def test_combining_caron_on_z(self) -> None:
        assert adapt_segment("z\u030C") == "\u0292"

    def test_combining_caron_on_c(self) -> None:
        assert adapt_segment("c\u030C") == "t\u0283"

    def test_combining_diaeresis_on_o(self) -> None:
        # o + combining diaeresis = ö → ø
        assert adapt_segment("o\u0308") == "\u00F8"

    def test_combining_diaeresis_on_u(self) -> None:
        assert adapt_segment("u\u0308") == "y"

    def test_combining_diaeresis_on_a(self) -> None:
        assert adapt_segment("a\u0308") == "\u00E6"

    def test_combining_dot_below_on_t(self) -> None:
        # t + dot below → ʈ (retroflex)
        assert adapt_segment("t\u0323") == "\u0288"

    def test_combining_dot_below_on_d(self) -> None:
        assert adapt_segment("d\u0323") == "\u0256"

    def test_combining_dot_below_on_n(self) -> None:
        assert adapt_segment("n\u0323") == "\u0273"

    def test_combining_dot_below_on_s(self) -> None:
        assert adapt_segment("s\u0323") == "\u0282"

    def test_combining_circumflex_below(self) -> None:
        # Circumflex below → laminal (IPA square below).
        result = adapt_segment("t\u032D")
        assert "\u033B" in result

    def test_combining_inverted_breve_below(self) -> None:
        # Non-syllabic marker.
        result = adapt_segment("u\u032F")
        assert "\u032F" in result

    def test_combining_grave(self) -> None:
        # à is in the TSV table, maps to itself.
        result = adapt_segment("a\u0300")
        assert result == "à"

    def test_combining_grave_on_vowel_not_in_table(self) -> None:
        # Grave on a vowel not explicitly in the table passes through.
        result = adapt_segment("o\u0300")
        assert "\u0300" in result

    def test_modifier_low_ring_devoicing(self) -> None:
        # Modifier letter low ring → IPA ring below (voiceless).
        result = adapt_segment("l\u02F3")
        assert "\u0325" in result

    def test_caron_n(self) -> None:
        # ň → ɳ (retroflex nasal in UPA)
        assert adapt_segment("ň") == "\u0273"


# ---------------------------------------------------------------------------
# Additional base characters (UraLex-attested)
# ---------------------------------------------------------------------------


class TestAdditionalCharacters:
    """Test additional characters found in UraLex data."""

    def test_q(self) -> None:
        assert adapt_segment("q") == "q"

    def test_ezh(self) -> None:
        assert adapt_segment("ʒ") == "ʒ"

    def test_a_ring(self) -> None:
        # å → ɔ
        assert adapt_segment("å") == "\u0254"

    def test_e_dot_above(self) -> None:
        # ė → e
        assert adapt_segment("ė") == "e"

    def test_m_acute(self) -> None:
        # ḿ → mʲ
        assert adapt_segment("ḿ") == "m\u02B2"

    def test_t_acute(self) -> None:
        # ť → tʲ
        assert adapt_segment("ť") == "t\u02B2"

    def test_d_caron(self) -> None:
        # ď → dʲ
        assert adapt_segment("ď") == "d\u02B2"
