"""Validate Python results against golden parity data."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from merkmal.geometry import load_geometry
from merkmal.model import list_available_models, load_model

GOLDEN_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "golden"
TOLERANCE = 1e-8


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


# ── Geometry golden tests ──────────────────────────────────────────────


class TestGeometryGolden:
    @pytest.fixture()
    def geom(self):
        return load_geometry("clements-hume")

    def test_feature_distances(self, geom) -> None:
        rows = _read_tsv(GOLDEN_DIR / "geometry_distances.tsv")
        for row in rows:
            expected = int(row["DISTANCE"])
            actual = geom.feature_distance(row["FEATURE_A"], row["FEATURE_B"])
            assert actual == expected, (
                f"{row['FEATURE_A']}↔{row['FEATURE_B']}: "
                f"expected {expected}, got {actual}"
            )

    def test_sound_distances(self, geom) -> None:
        sets = {
            "p-feats": frozenset({"consonant", "voiceless", "bilabial", "stop"}),
            "b-feats": frozenset({"consonant", "voiced", "bilabial", "stop"}),
            "t-feats": frozenset({"consonant", "voiceless", "alveolar", "stop"}),
            "k-feats": frozenset({"consonant", "voiceless", "velar", "stop"}),
            "s-feats": frozenset({"consonant", "voiceless", "alveolar", "fricative"}),
            "a-feats": frozenset({"vowel", "open", "front", "unrounded"}),
            "i-feats": frozenset({"vowel", "close", "front", "unrounded"}),
            "u-feats": frozenset({"vowel", "close", "back", "rounded"}),
        }
        rows = _read_tsv(GOLDEN_DIR / "geometry_sound_distances.tsv")
        for row in rows:
            expected = float(row["DISTANCE"])
            actual = geom.sound_distance(sets[row["SET_A"]], sets[row["SET_B"]])
            assert actual == pytest.approx(expected, abs=TOLERANCE), (
                f"{row['SET_A']}↔{row['SET_B']}: "
                f"expected {expected}, got {actual}"
            )

    def test_weighted_distances(self, geom) -> None:
        sets = {
            "p": frozenset({"consonant", "voiceless", "bilabial", "stop"}),
            "b": frozenset({"consonant", "voiced", "bilabial", "stop"}),
            "a": frozenset({"vowel", "open", "front", "unrounded"}),
        }
        rows = _read_tsv(GOLDEN_DIR / "geometry_weighted_distances.tsv")
        for row in rows:
            preset = None if row["PRESET"] == "None" else row["PRESET"]
            expected = float(row["DISTANCE"])
            actual = geom.sound_distance(
                sets[row["SET_A"]], sets[row["SET_B"]],
                node_weights=preset,
            )
            assert actual == pytest.approx(expected, abs=TOLERANCE), (
                f"preset={preset} {row['SET_A']}↔{row['SET_B']}: "
                f"expected {expected}, got {actual}"
            )


# ── Per-model golden tests ─────────────────────────────────────────────


def _model_names() -> list[str]:
    return sorted(list_available_models())


class TestModelFeaturesGolden:
    @pytest.mark.parametrize("model_name", _model_names())
    def test_features(self, model_name: str) -> None:
        path = GOLDEN_DIR / f"{model_name}_features.tsv"
        if not path.exists():
            pytest.skip(f"No golden features for {model_name}")
        system = load_model(model_name)
        rows = _read_tsv(path)
        for row in rows:
            grapheme = row["GRAPHEME"]
            expected = frozenset(row["FEATURES"].split("|"))
            actual = system.grapheme_to_features(grapheme)
            assert actual is not None, f"{model_name}: {grapheme!r} not found"
            assert actual == expected, (
                f"{model_name} {grapheme!r}: "
                f"expected {sorted(expected)}, got {sorted(actual)}"
            )


class TestModelDistancesGolden:
    @pytest.mark.parametrize("model_name", _model_names())
    def test_distances(self, model_name: str) -> None:
        path = GOLDEN_DIR / f"{model_name}_distances.tsv"
        if not path.exists():
            pytest.skip(f"No golden distances for {model_name}")
        system = load_model(model_name)
        rows = _read_tsv(path)
        for row in rows:
            a, b = row["GRAPHEME_A"], row["GRAPHEME_B"]
            expected = float(row["DISTANCE"])

            if model_name == "classfeat":
                actual = system.grapheme_cost(a, b)
            else:
                rep_a = system.grapheme_to_representation(a)
                rep_b = system.grapheme_to_representation(b)
                assert rep_a is not None, f"{model_name}: {a!r} not found"
                assert rep_b is not None, f"{model_name}: {b!r} not found"
                actual = system.segment_distance(rep_a, rep_b)

            assert actual == pytest.approx(expected, abs=TOLERANCE), (
                f"{model_name} {a!r}↔{b!r}: "
                f"expected {expected}, got {actual}"
            )


# ── Full parity tests ─────────────────────────────────────────────────


class TestFullFeatureParity:
    @pytest.mark.parametrize("model_name", _model_names())
    def test_features_full(self, model_name: str) -> None:
        path = GOLDEN_DIR / f"{model_name}_features_full.tsv"
        if not path.exists():
            pytest.skip(f"No full golden features for {model_name}")
        system = load_model(model_name)
        rows = _read_tsv(path)
        for row in rows:
            grapheme = row["GRAPHEME"]
            expected = frozenset(row["FEATURES"].split("|"))
            actual = system.grapheme_to_features(grapheme)
            assert actual is not None, f"{model_name}: {grapheme!r} not found"
            assert actual == expected, (
                f"{model_name} {grapheme!r}: "
                f"expected {sorted(expected)}, got {sorted(actual)}"
            )


class TestFullDistanceParity:
    @pytest.mark.parametrize("model_name", _model_names())
    def test_distances_full(self, model_name: str) -> None:
        path = GOLDEN_DIR / f"{model_name}_distances_full.tsv"
        if not path.exists():
            pytest.skip(f"No full golden distances for {model_name}")
        system = load_model(model_name)
        rows = _read_tsv(path)
        for row in rows:
            a, b = row["GRAPHEME_A"], row["GRAPHEME_B"]
            expected = float(row["DISTANCE"])

            if model_name == "classfeat":
                actual = system.grapheme_cost(a, b)
            else:
                rep_a = system.grapheme_to_representation(a)
                rep_b = system.grapheme_to_representation(b)
                assert rep_a is not None, f"{model_name}: {a!r} not found"
                assert rep_b is not None, f"{model_name}: {b!r} not found"
                actual = system.segment_distance(rep_a, rep_b)

            assert actual == pytest.approx(expected, abs=TOLERANCE), (
                f"{model_name} {a!r}↔{b!r}: "
                f"expected {expected}, got {actual}"
            )
