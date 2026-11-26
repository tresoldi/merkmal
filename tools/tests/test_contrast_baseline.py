"""Unit tests for the contrast baseline's classification of zero distances."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contrast_baseline import uncompared  # noqa: E402


def test_uncompared_counts_pairs_without_a_shared_dimension() -> None:
    # PHOIBLE gives these two segments no value on a common dimension, so they
    # score 0.0 with nothing compared.
    pairs = [("ae̯", "ɹ̪̹̩"), ("N", "m")]
    assert uncompared("phoible", pairs) == 1


def test_complex_spellings_are_declared_equivalent() -> None:
    from contrast_baseline import complex_spelling_equivalent

    assert complex_spelling_equivalent("mb", "ᵐb")
    assert complex_spelling_equivalent("ʈʂ", "tʂ")
    assert not complex_spelling_equivalent("mb", "nd")
