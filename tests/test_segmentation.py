"""Tests for tone digit preprocessing."""

import pytest

from merkmal.segmentation import merge_tone_digits, parse_chao_digits


class TestParseChaoDigits:
    """parse_chao_digits converts superscript digits to (onset, mid, offset)."""

    def test_level_tone(self) -> None:
        assert parse_chao_digits("⁵") == (5, 5, 5)
        assert parse_chao_digits("¹") == (1, 1, 1)
        assert parse_chao_digits("³") == (3, 3, 3)

    def test_contour_tone(self) -> None:
        assert parse_chao_digits("³⁵") == (3, 4, 5)
        assert parse_chao_digits("²¹") == (2, 2, 1)
        assert parse_chao_digits("⁵³") == (5, 4, 3)

    def test_contour_round_toward_neutral(self) -> None:
        """Half-levels round toward neutral (3)."""
        # 2+3=5, avg=2.5, round toward 3 → 3
        assert parse_chao_digits("²³") == (2, 3, 3)
        # 3+4=7, avg=3.5, round toward 3 → 3
        assert parse_chao_digits("³⁴") == (3, 3, 4)
        # 1+2=3, avg=1.5, round toward 3 → 2
        assert parse_chao_digits("¹²") == (1, 2, 2)
        # 4+5=9, avg=4.5, round toward 3 → 4
        assert parse_chao_digits("⁴⁵") == (4, 4, 5)

    def test_three_digit(self) -> None:
        """Three-digit tones: mid = second digit (explicit)."""
        assert parse_chao_digits("²¹³") == (2, 1, 3)
        assert parse_chao_digits("⁴⁴⁵") == (4, 4, 5)

    def test_zero_is_none(self) -> None:
        assert parse_chao_digits("⁰") is None

    def test_empty_is_none(self) -> None:
        assert parse_chao_digits("") is None

    def test_double_level(self) -> None:
        assert parse_chao_digits("⁵⁵") == (5, 5, 5)
        assert parse_chao_digits("³³") == (3, 3, 3)


class TestMergeToneDigits:
    """merge_tone_digits attaches tone to syllabic nucleus."""

    def test_tone_directly_after_vowel(self) -> None:
        assert merge_tone_digits(["t", "a", "³⁵"]) == ["t", "a³⁵"]

    def test_tone_after_coda(self) -> None:
        assert merge_tone_digits(["k", "a", "n", "⁵⁵"]) == ["k", "a⁵⁵", "n"]

    def test_morpheme_boundary(self) -> None:
        result = merge_tone_digits(["tʰ", "o", "³¹", "+", "p", "e", "j", "¹³"])
        assert result == ["tʰ", "o³¹", "+", "p", "e¹³", "j"]

    def test_zero_dropped(self) -> None:
        assert merge_tone_digits(["a", "⁰"]) == ["a"]

    def test_syllabic_nasal(self) -> None:
        assert merge_tone_digits(["n̩", "²¹"]) == ["n̩²¹"]

    def test_no_tone_passthrough(self) -> None:
        segs = ["p", "a", "t"]
        assert merge_tone_digits(segs) == ["p", "a", "t"]

    def test_multiple_syllables(self) -> None:
        result = merge_tone_digits(
            ["l", "w", "o", "³⁵", "+", "k", "w", "o", "r", "⁵⁵"],
        )
        assert result == ["l", "w", "o³⁵", "+", "k", "w", "o⁵⁵", "r"]

    def test_empty_input(self) -> None:
        assert merge_tone_digits([]) == []


class TestToneDigitFeaturization:
    """Merged tone digits produce correct tone features via merkmal."""

    def test_level_tone_features(self) -> None:
        import merkmal

        feats = merkmal.get_features("a⁵⁵")
        assert feats is not None
        assert "tone-onset-upper" in feats
        assert "tone-onset-raised" in feats
        assert "tone-offset-upper" in feats
        assert "tone-offset-raised" in feats

    def test_contour_tone_features(self) -> None:
        import merkmal

        feats = merkmal.get_features("a³⁵")
        assert feats is not None
        # onset=3 (mid) → no onset features
        assert "tone-onset-upper" not in feats
        assert "tone-onset-lower" not in feats
        # mid=4 (interpolated: (3+5)/2=4) → upper+lowered
        assert "tone-mid-upper" in feats
        assert "tone-mid-lowered" in feats
        # offset=5 → upper+raised
        assert "tone-offset-upper" in feats
        assert "tone-offset-raised" in feats

    def test_plain_vowel_no_tone(self) -> None:
        import merkmal

        feats = merkmal.get_features("a")
        assert feats is not None
        assert not any("tone" in f for f in feats)

    def test_toned_distance_nonzero(self) -> None:
        import merkmal

        d = merkmal.distance("a⁵⁵", "a²¹")
        assert d > 0.0

    def test_tone_zeroed_by_segmental(self) -> None:
        import merkmal

        d = merkmal.distance("a⁵⁵", "a²¹", node_weights="segmental")
        assert d == pytest.approx(0.0)
