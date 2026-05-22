#!/usr/bin/env python3
"""Learn optimal geometry node weights from CoreCog gold cognate data.

For each geometry × weight-scheme combination, computes word-level
distances for cognate and non-cognate pairs, then evaluates separation
(AUC). Additionally optimizes per-node weights via gradient-free search
(Nelder-Mead on node weights) to maximize AUC, and compares the
learned weights against the 1/depth default.

Usage:
    python scripts/learn_weights.py
    python scripts/learn_weights.py --split dev_core --geometries clements-hume deep-clements-hume
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

import merkmal
from merkmal.geometry import (
    GeometryNode,
    _iter_leaves,
    _node_depth,
    load_geometry,
)

FORMS_CSV = Path.home() / "repos/arcaverborum/output/aggregate/forms.csv"
DATASETS_CSV = Path.home() / "repos/arcaverborum/datasets.csv"
SPLITS_DIR = Path(__file__).resolve().parent.parent.parent / "cognator/benchmark/splits"

GAP_COST = 0.6
MAX_PAIRS_PER_DATASET = 3000
MAX_WORD_LEN = 15


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Learn geometry weights from CoreCog gold cognate data.",
    )
    parser.add_argument(
        "--forms", type=Path, default=FORMS_CSV,
        help="Path to arcaverborum forms.csv",
    )
    parser.add_argument(
        "--datasets", type=Path, default=DATASETS_CSV,
        help="Path to arcaverborum datasets.csv",
    )
    parser.add_argument(
        "--split", default="dev_core",
        help="Benchmark split (dev_core, dev_full, holdout). Default: dev_core.",
    )
    parser.add_argument(
        "--eval-split", default=None,
        help="Evaluation split (default: same as --split).",
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
        "--max-pairs", type=int, default=MAX_PAIRS_PER_DATASET,
        help=f"Max cognate pairs per dataset (default: {MAX_PAIRS_PER_DATASET})",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output JSON with learned weights (default: print report only)",
    )
    return parser.parse_args(argv)


def load_expert_datasets(datasets_csv: Path) -> set[str]:
    result = set()
    with datasets_csv.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("ExpertCognates") == "TRUE":
                result.add(row["NAME"])
    return result


def load_split(split_name: str) -> set[str]:
    path = SPLITS_DIR / f"{split_name}.txt"
    if not path.exists():
        print(f"ERROR: split file not found: {path}", file=sys.stderr)
        sys.exit(1)
    return set(path.read_text().strip().splitlines())


def load_word_pairs(
    forms_csv: Path,
    allowed_datasets: set[str],
    max_pairs: int,
) -> tuple[list[tuple[list[str], list[str]]], list[tuple[list[str], list[str]]]]:
    """Load cognate and non-cognate word pairs.

    Returns (cognate_pairs, non_cognate_pairs).
    """
    groups: dict[str, dict[str, dict[str, list[tuple[str, list[str]]]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list)),
    )
    with forms_csv.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ds = row.get("cognate_source", "")
            if ds not in allowed_datasets:
                continue
            cognacy = row.get("Cognacy", "").strip()
            if not cognacy:
                continue
            segments_str = row.get("Segments", "").strip()
            if not segments_str:
                continue
            segments = [s for s in segments_str.split() if s != "+"]
            if not segments or len(segments) > MAX_WORD_LEN:
                continue
            concept = row.get("concept_id", "")
            variety = row.get("av_id", "")
            cog_id = cognacy.split(";")[0].strip()
            if cog_id:
                groups[ds][concept][cog_id].append((variety, segments))

    cognate_pairs: list[tuple[list[str], list[str]]] = []
    non_cognate_pairs: list[tuple[list[str], list[str]]] = []

    for ds_name in sorted(groups):
        ds_cog = 0
        ds_noncog = 0
        for concept, cog_groups in groups[ds_name].items():
            cog_ids = list(cog_groups.keys())
            for cog_id in cog_ids:
                entries = cog_groups[cog_id]
                seen: dict[str, list[str]] = {}
                for variety, segments in entries:
                    if variety not in seen:
                        seen[variety] = segments
                variety_list = list(seen.values())
                for sa, sb in combinations(variety_list, 2):
                    cognate_pairs.append((sa, sb))
                    ds_cog += 1
                    if ds_cog >= max_pairs:
                        break
                if ds_cog >= max_pairs:
                    break
            if ds_cog >= max_pairs:
                break

            for cog_a, cog_b in combinations(cog_ids, 2):
                entries_a = cog_groups[cog_a]
                entries_b = cog_groups[cog_b]
                if entries_a and entries_b:
                    _, seg_a = entries_a[0]
                    _, seg_b = entries_b[0]
                    non_cognate_pairs.append((seg_a, seg_b))
                    ds_noncog += 1
                    if ds_noncog >= max_pairs:
                        break
            if ds_noncog >= max_pairs:
                continue

        if ds_noncog < ds_cog:
            concept_forms: list[list[str]] = []
            for concept, cog_groups in groups[ds_name].items():
                for entries in cog_groups.values():
                    if entries:
                        concept_forms.append(entries[0][1])
                        break
            import random
            rng = random.Random(42)
            rng.shuffle(concept_forms)
            for i in range(0, len(concept_forms) - 1, 2):
                non_cognate_pairs.append((concept_forms[i], concept_forms[i + 1]))
                ds_noncog += 1
                if ds_noncog >= ds_cog:
                    break

        print(
            f"  {ds_name}: {ds_cog} cognate, {ds_noncog} non-cognate pairs",
            file=sys.stderr,
        )

    return cognate_pairs, non_cognate_pairs


def segment_distance_with_geometry(
    seg_a: str,
    seg_b: str,
    system_obj: Any,
    geom: Any,
    node_weights: dict[str, float] | str | None = None,
) -> float:
    """Compute segment distance using a specific geometry."""
    from merkmal.engines.categorical import CategoricalEngine

    if isinstance(system_obj, CategoricalEngine):
        feats_a = system_obj.grapheme_to_features(seg_a)
        feats_b = system_obj.grapheme_to_features(seg_b)
        if feats_a is None or feats_b is None:
            return 1.0
        return geom.tree.sound_distance(
            feats_a, feats_b, node_weights,
            feature_to_node=geom.feature_to_node,
        )
    try:
        return merkmal.distance(seg_a, seg_b, system=system_obj.name, node_weights=node_weights)
    except (KeyError, NotImplementedError):
        return 1.0


def word_distance_nw(
    seq_a: list[str],
    seq_b: list[str],
    system_obj: Any,
    geom: Any,
    node_weights: dict[str, float] | str | None = None,
) -> float:
    """NW alignment cost normalized by alignment length."""
    n, m = len(seq_a), len(seq_b)
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + GAP_COST
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + GAP_COST

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            sub = segment_distance_with_geometry(
                seq_a[i - 1], seq_b[j - 1],
                system_obj, geom, node_weights,
            )
            dp[i][j] = min(
                dp[i - 1][j - 1] + sub,
                dp[i - 1][j] + GAP_COST,
                dp[i][j - 1] + GAP_COST,
            )

    align_len = max(n, m)
    return dp[n][m] / align_len if align_len > 0 else 0.0


def compute_auc(
    cognate_dists: list[float],
    noncognate_dists: list[float],
) -> float:
    """Mann-Whitney U-based AUC via sort, O(n log n)."""
    if not cognate_dists or not noncognate_dists:
        return 0.5
    n_cog = len(cognate_dists)
    n_noncog = len(noncognate_dists)
    labeled = [(d, 0) for d in cognate_dists] + [(d, 1) for d in noncognate_dists]
    labeled.sort()
    rank_sum_cog = 0.0
    i = 0
    while i < len(labeled):
        j = i
        while j < len(labeled) and labeled[j][0] == labeled[i][0]:
            j += 1
        avg_rank = (i + j + 1) / 2.0
        for k in range(i, j):
            if labeled[k][1] == 0:
                rank_sum_cog += avg_rank
        i = j
    u = rank_sum_cog - n_cog * (n_cog + 1) / 2.0
    return 1.0 - u / (n_cog * n_noncog)


def get_internal_nodes(tree: GeometryNode) -> list[str]:
    """Get names of all internal geometry nodes (for weight optimization)."""
    nodes = [tree.name]
    for child in tree.children:
        if isinstance(child, GeometryNode):
            nodes.extend(get_internal_nodes(child))
    return nodes


def evaluate_scheme(
    cognate_pairs: list[tuple[list[str], list[str]]],
    noncog_pairs: list[tuple[list[str], list[str]]],
    system_obj: Any,
    geom: Any,
    node_weights: dict[str, float] | str | None,
    label: str,
) -> tuple[float, float, float]:
    """Evaluate a weight scheme. Returns (AUC, mean_cognate_dist, mean_noncognate_dist)."""
    cog_dists = [
        word_distance_nw(a, b, system_obj, geom, node_weights)
        for a, b in cognate_pairs
    ]
    noncog_dists = [
        word_distance_nw(a, b, system_obj, geom, node_weights)
        for a, b in noncog_pairs
    ]
    auc = compute_auc(cog_dists, noncog_dists)
    mean_cog = sum(cog_dists) / len(cog_dists) if cog_dists else 0.0
    mean_noncog = sum(noncog_dists) / len(noncog_dists) if noncog_dists else 0.0
    return auc, mean_cog, mean_noncog


def optimize_weights(
    cognate_pairs: list[tuple[list[str], list[str]]],
    noncog_pairs: list[tuple[list[str], list[str]]],
    system_obj: Any,
    geom: Any,
) -> tuple[dict[str, float], float]:
    """Optimize node weights to maximize AUC using Nelder-Mead."""
    from scipy.optimize import minimize

    node_names = get_internal_nodes(geom.tree)

    sample_cog = cognate_pairs[:200]
    sample_noncog = noncog_pairs[:200]

    def objective(x: Any) -> float:
        weights = {name: max(0.01, float(val)) for name, val in zip(node_names, x)}
        auc, _, _ = evaluate_scheme(
            sample_cog, sample_noncog, system_obj, geom, weights, "opt",
        )
        return -auc

    x0 = [1.0] * len(node_names)
    result = minimize(
        objective, x0, method="Nelder-Mead",
        options={"maxiter": 300, "xatol": 0.02, "fatol": 0.0005},
    )

    learned = {
        name: round(max(0.01, float(val)), 3)
        for name, val in zip(node_names, result.x)
    }

    auc, _, _ = evaluate_scheme(
        cognate_pairs, noncog_pairs, system_obj, geom, learned, "learned",
    )

    return learned, auc


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.forms.exists():
        print(f"ERROR: forms.csv not found: {args.forms}", file=sys.stderr)
        return 1

    expert_datasets = load_expert_datasets(args.datasets)
    split_datasets = load_split(args.split)
    allowed = expert_datasets & split_datasets

    print(f"Loading word pairs from {len(allowed)} datasets ({args.split})...", file=sys.stderr)
    cognate_pairs, noncog_pairs = load_word_pairs(args.forms, allowed, args.max_pairs)
    print(
        f"\nTotal: {len(cognate_pairs)} cognate, {len(noncog_pairs)} non-cognate pairs",
        file=sys.stderr,
    )

    if not cognate_pairs or not noncog_pairs:
        print("ERROR: no pairs found", file=sys.stderr)
        return 1

    system_obj = merkmal.get_system(args.system)
    results: dict[str, dict[str, Any]] = {}

    for geom_name in args.geometries:
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"Geometry: {geom_name}", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)

        geom = load_geometry(geom_name)
        geom_results: dict[str, Any] = {}

        schemes: list[tuple[str, dict[str, float] | str | None]] = [
            ("1/depth (default)", None),
            ("flat", "flat"),
        ]

        for scheme_name, node_weights in schemes:
            print(f"\n  Evaluating: {scheme_name}...", file=sys.stderr)
            auc, mean_cog, mean_noncog = evaluate_scheme(
                cognate_pairs, noncog_pairs,
                system_obj, geom, node_weights, scheme_name,
            )
            sep = mean_noncog - mean_cog
            geom_results[scheme_name] = {
                "auc": round(auc, 4),
                "mean_cognate_dist": round(mean_cog, 4),
                "mean_noncognate_dist": round(mean_noncog, 4),
                "separation": round(sep, 4),
            }
            print(
                f"    AUC={auc:.4f}  cog={mean_cog:.4f}  "
                f"noncog={mean_noncog:.4f}  sep={sep:.4f}",
                file=sys.stderr,
            )

        try:
            print(f"\n  Optimizing node weights (Nelder-Mead)...", file=sys.stderr)
            learned_weights, learned_auc = optimize_weights(
                cognate_pairs, noncog_pairs, system_obj, geom,
            )
            auc_full, mean_cog, mean_noncog = evaluate_scheme(
                cognate_pairs, noncog_pairs,
                system_obj, geom, learned_weights, "learned",
            )
            sep = mean_noncog - mean_cog
            geom_results["learned"] = {
                "auc": round(auc_full, 4),
                "mean_cognate_dist": round(mean_cog, 4),
                "mean_noncognate_dist": round(mean_noncog, 4),
                "separation": round(sep, 4),
                "weights": learned_weights,
            }
            print(
                f"    AUC={auc_full:.4f}  cog={mean_cog:.4f}  "
                f"noncog={mean_noncog:.4f}  sep={sep:.4f}",
                file=sys.stderr,
            )
            print(f"    Learned weights:", file=sys.stderr)
            for node, w in sorted(learned_weights.items()):
                default_depth = _node_depth(geom.tree, node, 1) or 1
                print(
                    f"      {node:20s}  w={w:.3f}  (1/depth={1/default_depth:.3f})",
                    file=sys.stderr,
                )
        except ImportError:
            print("  scipy not available, skipping optimization", file=sys.stderr)
            learned_weights = {}

        results[geom_name] = geom_results

    print(f"\n{'='*60}", file=sys.stderr)
    print("SUMMARY", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"\n{'geometry':30s} {'scheme':20s} {'AUC':>8s} {'separation':>12s}", file=sys.stderr)
    print("-" * 72, file=sys.stderr)
    for geom_name, geom_results in results.items():
        for scheme_name, data in geom_results.items():
            print(
                f"  {geom_name:28s} {scheme_name:20s} {data['auc']:8.4f} {data['separation']:12.4f}",
                file=sys.stderr,
            )

    if args.output:
        output_data = {
            "split": args.split,
            "system": args.system,
            "n_cognate_pairs": len(cognate_pairs),
            "n_noncognate_pairs": len(noncog_pairs),
            "results": results,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(output_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\nResults written to {args.output}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
