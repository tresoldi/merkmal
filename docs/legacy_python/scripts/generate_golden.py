#!/usr/bin/env python3
"""Generate golden parity data for cross-language testing.

Run from the merkmal repo root (or anywhere with the package installed):

    python tests/generate_golden.py

Outputs TSV files into tests/golden/.  The C tests validate against these
files.
"""

from __future__ import annotations

import csv
import sys
from itertools import combinations
from pathlib import Path

# Ensure the archived Python implementation is importable when running from repo root.
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_PY = _REPO / "tools" / "legacy_python"
if str(_PY) not in sys.path:
    sys.path.insert(0, str(_PY))

from merkmal.geometry import load_geometry
from merkmal.model import list_available_models, load_model

GOLDEN_DIR = _HERE / "golden"

# Graphemes used across all systems.  Chosen for broad IPA coverage:
# stops, fricatives, nasals, liquids, glides, vowels, clicks, tones.
CORE_GRAPHEMES: list[str] = [
    "p", "b", "t", "d", "k", "g",
    "q", "ʔ",
    "f", "v", "s", "z", "ʃ", "ʒ", "x", "h",
    "m", "n", "ŋ", "ɲ",
    "l", "r", "ɾ", "ɹ", "ɬ",
    "j", "w",
    "a", "e", "i", "o", "u",
    "ɛ", "ɔ", "ə", "ɨ", "ɑ",
    "æ", "ø", "y", "ɯ",
    "ɓ", "ɗ",
    "ǃ", "ǀ",
    "t͡s", "d͡ʒ", "t͡ʃ",
]

# Additional graphemes for categorical systems (modifiers, tones).
CATEGORICAL_EXTRA: list[str] = [
    "pʰ", "tː", "ã", "kʷ", "tʲ",
    "á", "à", "â",
]

# Distance pairs: chosen to cover same-class, cross-class, vowel-consonant.
DISTANCE_PAIRS: list[tuple[str, str]] = [
    ("p", "b"), ("p", "t"), ("p", "k"), ("p", "a"),
    ("t", "d"), ("t", "s"), ("t", "n"),
    ("k", "g"), ("k", "q"), ("k", "x"),
    ("s", "z"), ("s", "ʃ"), ("s", "f"),
    ("m", "n"), ("m", "ŋ"), ("n", "l"),
    ("a", "e"), ("a", "i"), ("a", "o"), ("a", "u"),
    ("i", "u"), ("i", "e"), ("e", "o"),
    ("ɛ", "e"), ("ɔ", "o"), ("ə", "a"),
    ("p", "f"), ("b", "v"), ("d", "z"),
    ("j", "i"), ("w", "u"),
    ("l", "r"), ("l", "ɾ"),
    ("p", "p"), ("a", "a"),
]

# Feature pairs for geometry tree distance.
GEOMETRY_FEATURE_PAIRS: list[tuple[str, str]] = [
    ("voiced", "voiceless"),
    ("voiced", "voiced"),
    ("bilabial", "alveolar"),
    ("bilabial", "velar"),
    ("alveolar", "velar"),
    ("stop", "fricative"),
    ("stop", "nasal"),
    ("nasal", "lateral"),
    ("vowel", "consonant"),
    ("aspirated", "voiceless"),
    ("tone-onset-upper", "tone-onset-lower"),
    ("tone-onset-upper", "tone-offset-upper"),
]


def _write_tsv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def _available_graphemes(system: object, candidates: list[str]) -> list[str]:
    return [g for g in candidates if system.grapheme_to_features(g) is not None]


def generate_features(name: str, system: object) -> None:
    candidates = list(CORE_GRAPHEMES)
    if system.representation_kind == "categorical":
        candidates.extend(CATEGORICAL_EXTRA)

    graphemes = _available_graphemes(system, candidates)
    rows: list[list[str]] = []
    for g in graphemes:
        feats = system.grapheme_to_features(g)
        if feats is None:
            continue
        rows.append([g, "|".join(sorted(feats))])

    _write_tsv(
        GOLDEN_DIR / f"{name}_features.tsv",
        ["GRAPHEME", "FEATURES"],
        rows,
    )
    print(f"  {name}_features.tsv: {len(rows)} graphemes")


def generate_distances(name: str, system: object) -> None:
    rows: list[list[str]] = []
    for a, b in DISTANCE_PAIRS:
        fa = system.grapheme_to_features(a)
        fb = system.grapheme_to_features(b)
        if fa is None or fb is None:
            continue

        rep_a = system.grapheme_to_representation(a)
        rep_b = system.grapheme_to_representation(b)
        if rep_a is None or rep_b is None:
            continue

        # Use segment_distance (geometry-weighted) for all systems.
        d = system.segment_distance(rep_a, rep_b)
        rows.append([a, b, f"{d:.10f}"])

    _write_tsv(
        GOLDEN_DIR / f"{name}_distances.tsv",
        ["GRAPHEME_A", "GRAPHEME_B", "DISTANCE"],
        rows,
    )
    print(f"  {name}_distances.tsv: {len(rows)} pairs")


def generate_distances_classfeat(name: str, system: object) -> None:
    """ClassFeat uses grapheme_cost for its primary distance metric."""
    rows: list[list[str]] = []
    for a, b in DISTANCE_PAIRS:
        cost = system.grapheme_cost(a, b)
        # grapheme_cost returns 1.0 for unknown graphemes; skip those.
        va = system.grapheme_vector(a)
        vb = system.grapheme_vector(b)
        if va is None or vb is None:
            continue
        rows.append([a, b, f"{cost:.10f}"])

    _write_tsv(
        GOLDEN_DIR / f"{name}_distances.tsv",
        ["GRAPHEME_A", "GRAPHEME_B", "DISTANCE"],
        rows,
    )
    print(f"  {name}_distances.tsv: {len(rows)} pairs")


def generate_geometry_distances() -> None:
    geom = load_geometry("clements-hume")
    rows: list[list[str]] = []
    for a, b in GEOMETRY_FEATURE_PAIRS:
        d = geom.feature_distance(a, b)
        rows.append([a, b, str(d)])

    _write_tsv(
        GOLDEN_DIR / "geometry_distances.tsv",
        ["FEATURE_A", "FEATURE_B", "DISTANCE"],
        rows,
    )
    print(f"  geometry_distances.tsv: {len(rows)} pairs")


def generate_sound_distances() -> None:
    """Geometry-level sound_distance for categorical feature sets."""
    geom = load_geometry("clements-hume")
    test_sets: list[tuple[str, frozenset[str]]] = [
        ("p-feats", frozenset({"consonant", "voiceless", "bilabial", "stop"})),
        ("b-feats", frozenset({"consonant", "voiced", "bilabial", "stop"})),
        ("t-feats", frozenset({"consonant", "voiceless", "alveolar", "stop"})),
        ("k-feats", frozenset({"consonant", "voiceless", "velar", "stop"})),
        ("s-feats", frozenset({"consonant", "voiceless", "alveolar", "fricative"})),
        ("a-feats", frozenset({"vowel", "open", "front", "unrounded"})),
        ("i-feats", frozenset({"vowel", "close", "front", "unrounded"})),
        ("u-feats", frozenset({"vowel", "close", "back", "rounded"})),
    ]
    rows: list[list[str]] = []
    for (name_a, feats_a), (name_b, feats_b) in combinations(test_sets, 2):
        d = geom.sound_distance(feats_a, feats_b)
        rows.append([name_a, name_b, f"{d:.10f}"])

    _write_tsv(
        GOLDEN_DIR / "geometry_sound_distances.tsv",
        ["SET_A", "SET_B", "DISTANCE"],
        rows,
    )
    print(f"  geometry_sound_distances.tsv: {len(rows)} pairs")


def generate_node_weights_distances() -> None:
    """Sound distances under various node_weights presets."""
    geom = load_geometry("clements-hume")
    p = frozenset({"consonant", "voiceless", "bilabial", "stop"})
    b = frozenset({"consonant", "voiced", "bilabial", "stop"})
    a_feats = frozenset({"vowel", "open", "front", "unrounded"})

    presets = [None, "ignore-tone", "segmental", "flat"]
    feat_pairs = [
        ("p", "b", p, b),
        ("p", "a", p, a_feats),
    ]
    rows: list[list[str]] = []
    for preset in presets:
        for name_a, name_b, fa, fb in feat_pairs:
            d = geom.sound_distance(fa, fb, node_weights=preset)
            rows.append([str(preset), name_a, name_b, f"{d:.10f}"])

    _write_tsv(
        GOLDEN_DIR / "geometry_weighted_distances.tsv",
        ["PRESET", "SET_A", "SET_B", "DISTANCE"],
        rows,
    )
    print(f"  geometry_weighted_distances.tsv: {len(rows)} entries")


def main() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating geometry golden data...")
    generate_geometry_distances()
    generate_sound_distances()
    generate_node_weights_distances()

    print("\nGenerating per-model golden data...")
    for name in sorted(list_available_models()):
        print(f"\n  [{name}]")
        system = load_model(name)

        generate_features(name, system)

        if name == "classfeat":
            generate_distances_classfeat(name, system)
        else:
            generate_distances(name, system)

    print("\nDone.")


if __name__ == "__main__":
    main()
