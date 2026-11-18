"""Unit tests for the contrast baseline's classification of zero distances."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contrast_baseline import uncompared  # noqa: E402


def test_uncompared_counts_pairs_without_a_shared_dimension() -> None:
    # In PHOIBLE a tone row defines none of the segmental dimensions, so a
    # tone and a consonant score 0.0 with nothing compared.
    pairs = [("N", "˥˧"), ("N", "m")]
    assert uncompared("phoible", pairs) == 1
