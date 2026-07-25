#!/usr/bin/env python3
"""Compare distance behaviour across geometry variants and weight schemes.

For a representative segment inventory, computes pairwise distances under
multiple geometry × weight-scheme combinations. Reports Spearman rank
correlations, rank reversals, and discriminability (distinct distance values).

Usage:
    python scripts/compare_geometries.py
    python scripts/compare_geometries.py --geometries clements-hume deep-clements-hume
"""

from __future__ import annotations

import argparse
import sys
from itertools import combinations

import merkmal
from merkmal.engines.categorical import CategoricalEngine
from merkmal.geometry import load_geometry

CONSONANTS = "p b t d k g f v s z ʃ ʒ m n ŋ l r j w".split()
VOWELS = "i ɪ e ɛ æ a ɑ ɒ o ɔ u ʊ ə".split()
INVENTORY = CONSONANTS + VOWELS


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare geometry variants and weight schemes.",
    )
    parser.add_argument(
        "--system", default="descriptive",
        help="Feature system (default: descriptive)",
    )
    parser.add_argument(
        "--geometries", nargs="+", default=["clements-hume", "deep-clements-hume"],
        help="Geometries to compare",
    )
    parser.add_argument(
        "--schemes", nargs="+", default=["default", "flat"],
        help="Weight schemes (default, flat)",
    )
    parser.add_argument(
        "segments", nargs="*", default=INVENTORY,
        help="IPA segments (default: 33-segment representative inventory)",
    )
    return parser.parse_args(argv)


def compute_distances(
    pairs: list[tuple[str, str]],
    system_obj: CategoricalEngine,
    geom: merkmal.Geometry,
    node_weights: dict[str, float] | str | None,
) -> list[float]:
    distances = []
    for a, b in pairs:
        feats_a = system_obj.grapheme_to_features(a)
        feats_b = system_obj.grapheme_to_features(b)
        if feats_a is None or feats_b is None:
            distances.append(float("nan"))
            continue
        d = geom.tree.sound_distance(
            feats_a, feats_b, node_weights,
            feature_to_node=geom.feature_to_node,
        )
        distances.append(d)
    return distances


def spearman_rank_correlation(x: list[float], y: list[float]) -> float:
    """Spearman rank correlation between two lists."""
    valid = [(a, b) for a, b in zip(x, y) if a == a and b == b]
    if len(valid) < 3:
        return float("nan")
    xs, ys = zip(*valid)
    n = len(xs)

    def rank(values: tuple[float, ...]) -> list[float]:
        indexed = sorted(range(n), key=lambda i: values[i])
        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j < n and values[indexed[j]] == values[indexed[i]]:
                j += 1
            avg_rank = (i + j + 1) / 2.0
            for k in range(i, j):
                ranks[indexed[k]] = avg_rank
            i = j
        return ranks

    rx = rank(xs)
    ry = rank(ys)
    mean_rx = sum(rx) / n
    mean_ry = sum(ry) / n
    num = sum((a - mean_rx) * (b - mean_ry) for a, b in zip(rx, ry))
    den_x = sum((a - mean_rx) ** 2 for a in rx) ** 0.5
    den_y = sum((b - mean_ry) ** 2 for b in ry) ** 0.5
    return num / (den_x * den_y) if den_x * den_y > 0 else 0.0


def count_rank_reversals(x: list[float], y: list[float]) -> int:
    """Count pairs where rank order differs between x and y."""
    valid = [(a, b) for a, b in zip(x, y) if a == a and b == b]
    reversals = 0
    for i in range(len(valid)):
        for j in range(i + 1, len(valid)):
            if (valid[i][0] - valid[j][0]) * (valid[i][1] - valid[j][1]) < 0:
                reversals += 1
    return reversals


def count_distinct(dists: list[float]) -> int:
    return len({round(d, 10) for d in dists if d == d})


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    system_obj = merkmal.get_system(args.system)
    if not isinstance(system_obj, CategoricalEngine):
        print(f"ERROR: system {args.system} is not categorical", file=sys.stderr)
        return 1

    covered = [s for s in args.segments if system_obj.grapheme_to_features(s) is not None]
    pairs = list(combinations(covered, 2))
    print(f"Inventory: {len(covered)} segments, {len(pairs)} pairs")
    print()

    all_configs: list[tuple[str, str, list[float]]] = []

    for geom_name in args.geometries:
        geom = load_geometry(geom_name)
        for scheme in args.schemes:
            nw: dict[str, float] | str | None = None if scheme == "default" else scheme
            dists = compute_distances(pairs, system_obj, geom, nw)
            label = f"{geom_name}/{scheme}"
            n_distinct = count_distinct(dists)
            valid_dists = [d for d in dists if d == d]
            mean_d = sum(valid_dists) / len(valid_dists) if valid_dists else 0
            print(f"  {label:45s}  distinct={n_distinct:4d}  mean={mean_d:.4f}")
            all_configs.append((geom_name, scheme, dists))

    print()
    print("=" * 70)
    print("SPEARMAN RANK CORRELATIONS")
    print("=" * 70)
    labels = [f"{g}/{s}" for g, s, _ in all_configs]
    header = f"{'':35s}" + "".join(f"{l:>18s}" for l in labels)
    print(header)
    for i, (g1, s1, d1) in enumerate(all_configs):
        row = f"  {labels[i]:33s}"
        for j, (g2, s2, d2) in enumerate(all_configs):
            if j <= i:
                rho = spearman_rank_correlation(d1, d2) if i != j else 1.0
                row += f"{rho:18.4f}"
            else:
                row += f"{'':>18s}"
        print(row)

    print()
    print("=" * 70)
    print("RANK REVERSALS")
    print("=" * 70)
    header = f"{'':35s}" + "".join(f"{l:>18s}" for l in labels)
    print(header)
    for i, (g1, s1, d1) in enumerate(all_configs):
        row = f"  {labels[i]:33s}"
        for j, (g2, s2, d2) in enumerate(all_configs):
            if j < i:
                rev = count_rank_reversals(d1, d2)
                row += f"{rev:18d}"
            elif j == i:
                row += f"{0:18d}"
            else:
                row += f"{'':>18s}"
        print(row)

    print()
    print("=" * 70)
    print("DIAGNOSTIC PAIRS")
    print("=" * 70)
    diagnostic = [
        ("p", "b"), ("p", "t"), ("p", "f"), ("p", "k"),
        ("s", "ʃ"), ("m", "n"), ("i", "u"), ("a", "ə"),
        ("p", "a"), ("t", "n"),
    ]
    header = f"{'pair':>8s}" + "".join(f"  {l:>18s}" for l in labels)
    print(header)
    print("-" * (8 + 20 * len(labels)))
    for a, b in diagnostic:
        row = f"  {a}~{b:4s}"
        for g, s, dists in all_configs:
            idx = None
            for pi, (pa, pb) in enumerate(pairs):
                if (pa, pb) == (a, b) or (pb, pa) == (a, b):
                    idx = pi
                    break
            if idx is not None:
                row += f"{dists[idx]:20.4f}"
            else:
                row += f"{'N/A':>20s}"
        print(row)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
