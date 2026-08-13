#!/usr/bin/env python3
"""QUARANTINED. Do not use this to derive a sound-change direction prior.

Archived pre-C script, kept as a record of what produced
typologies/corecog-derived.json. Its output is not historically interpretable:

  * Direction is not identified. It tallies changes between two *daughter*
    varieties, and an unordered pair of attested states does not tell you which
    one is earlier.
  * The stated orientation is wrong. The caveat it writes says direction is
    relative to the alphabetically first variety; `seen_varieties` keeps input
    encounter order and is never sorted, so re-ordering the input flips labels.
  * The cost transform is inverted. `direction_ratios` below documents that the
    more frequent direction should be discounted below 1.0, then computes
    `pos_to_neg = 2.0 * ratio`, which grows with frequency.
  * Every language pair inside a cognate set is emitted, so large sets weigh
    quadratically and well-sampled families dominate.
  * Environment is pooled away, and the alignments come from the same
    dissimilarity the result was meant to calibrate.

See typologies/README.md. Fixing the arithmetic alone would not make the output
valid, and would silently reverse anything already consuming it.

Original description follows.

Derive empirical direction costs from cognator's CoreCog gold data.

Reads arcaverborum's forms.csv, extracts cognate pairs from expert-coded
datasets, aligns them with Needleman-Wunsch using merkmal distances, and
tallies directed feature changes per leaf feature.  Outputs a typology
JSON suitable for merkmal.load_typology().

Usage:
    python scripts/derive_direction_costs.py
    python scripts/derive_direction_costs.py --split dev_core --system phoible
    python scripts/derive_direction_costs.py --output typologies/corecog-derived.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import merkmal
from merkmal.geometry import FeatureNode, _iter_leaves, load_geometry

FORMS_CSV = Path.home() / "repos/arcaverborum/output/aggregate/forms.csv"
DATASETS_CSV = Path.home() / "repos/arcaverborum/datasets.csv"
SPLITS_DIR = Path(__file__).resolve().parent.parent.parent / "cognator/benchmark/splits"

GAP_COST = 0.6
EXTEND_COST = 0.3
MIN_OBSERVATIONS = 20


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Derive direction costs from CoreCog gold cognate data.",
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
        "--split", default=None,
        help="Benchmark split to use (dev_core, dev_full, holdout). Default: all expert datasets.",
    )
    parser.add_argument(
        "--system", default="descriptive",
        help="Feature system for alignment and feature extraction (default: descriptive)",
    )
    parser.add_argument(
        "--geometry", default="clements-hume",
        help="Geometry for leaf feature enumeration (default: clements-hume)",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output JSON path (default: print to stdout)",
    )
    parser.add_argument(
        "--min-obs", type=int, default=MIN_OBSERVATIONS,
        help=f"Minimum observations per feature to include (default: {MIN_OBSERVATIONS})",
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


def load_cognate_groups(
    forms_csv: Path,
    allowed_datasets: set[str],
) -> dict[str, dict[str, list[tuple[str, list[str]]]]]:
    """Load cognate groups: {dataset: {cognate_id: [(variety, segments)]}}."""
    groups: dict[str, dict[str, list[tuple[str, list[str]]]]] = defaultdict(
        lambda: defaultdict(list),
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
            if not segments:
                continue
            variety = row.get("av_id", "")
            for cog_id in cognacy.split(";"):
                cog_id = cog_id.strip()
                if cog_id:
                    groups[ds][cog_id].append((variety, segments))
    return dict(groups)


def nw_align(
    seq_a: list[str],
    seq_b: list[str],
    system: str,
) -> list[tuple[str | None, str | None]]:
    """Simple Needleman-Wunsch alignment using merkmal distances."""
    n, m = len(seq_a), len(seq_b)
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + GAP_COST
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + GAP_COST

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            try:
                sub_cost = merkmal.distance(seq_a[i - 1], seq_b[j - 1], system=system)
            except (KeyError, NotImplementedError):
                sub_cost = 1.0
            match = dp[i - 1][j - 1] + sub_cost
            gap_a = dp[i - 1][j] + (EXTEND_COST if i > 1 and dp[i - 1][j] == dp[i - 2][j] + GAP_COST else GAP_COST)
            gap_b = dp[i][j - 1] + (EXTEND_COST if j > 1 and dp[i][j - 1] == dp[i][j - 2] + GAP_COST else GAP_COST)
            dp[i][j] = min(match, gap_a, gap_b)

    alignment: list[tuple[str | None, str | None]] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            try:
                sub_cost = merkmal.distance(seq_a[i - 1], seq_b[j - 1], system=system)
            except (KeyError, NotImplementedError):
                sub_cost = 1.0
            if dp[i][j] == dp[i - 1][j - 1] + sub_cost:
                alignment.append((seq_a[i - 1], seq_b[j - 1]))
                i -= 1
                j -= 1
                continue
        if i > 0 and dp[i][j] >= dp[i - 1][j]:
            alignment.append((seq_a[i - 1], None))
            i -= 1
        else:
            alignment.append((None, seq_b[j - 1]))
            j -= 1

    alignment.reverse()
    return alignment


def extract_leaf_features(
    grapheme: str,
    system_obj: merkmal.protocol.FeatureSystem,
) -> frozenset[str] | None:
    feats = system_obj.grapheme_to_features(grapheme)
    return feats


def tally_feature_changes(
    alignments: list[list[tuple[str | None, str | None]]],
    system: str,
    geometry_name: str,
) -> dict[str, Counter[str]]:
    """Count feature transitions per leaf feature.

    Returns {feature_name: Counter({"pos_to_neg": N, "neg_to_pos": M, "same": K})}.
    """
    system_obj = merkmal.get_system(system)
    geom = load_geometry(geometry_name)

    leaves = _iter_leaves(geom.tree, 1)
    leaf_features: list[FeatureNode] = [leaf for leaf, _, _ in leaves]

    tallies: dict[str, Counter[str]] = {lf.name: Counter() for lf in leaf_features}

    for alignment in alignments:
        for seg_a, seg_b in alignment:
            if seg_a is None or seg_b is None:
                continue
            feats_a = extract_leaf_features(seg_a, system_obj)
            feats_b = extract_leaf_features(seg_b, system_obj)
            if feats_a is None or feats_b is None:
                continue

            for lf in leaf_features:
                a_pos = lf.positive in feats_a if lf.positive else False
                a_neg = lf.negative in feats_a if lf.negative else False
                b_pos = lf.positive in feats_b if lf.positive else False
                b_neg = lf.negative in feats_b if lf.negative else False

                a_val = 1 if a_pos else (-1 if a_neg else 0)
                b_val = 1 if b_pos else (-1 if b_neg else 0)

                if a_val == 0 and b_val == 0:
                    continue

                if a_val == b_val:
                    tallies[lf.name]["same"] += 1
                elif a_val > b_val:
                    tallies[lf.name]["pos_to_neg"] += 1
                else:
                    tallies[lf.name]["neg_to_pos"] += 1

    return tallies


def compute_direction_costs(
    tallies: dict[str, Counter[str]],
    min_obs: int,
) -> dict[str, dict[str, float]]:
    """Convert tallies to direction cost ratios.

    For each feature with enough observations, the cost of the more
    frequent direction gets a discount (< 1.0) and the less frequent
    direction gets a penalty (> 1.0), centered around 1.0.
    """
    costs: dict[str, dict[str, float]] = {}
    for feat_name, counts in sorted(tallies.items()):
        p2n = counts["pos_to_neg"]
        n2p = counts["neg_to_pos"]
        total_changes = p2n + n2p
        if total_changes < min_obs:
            continue

        ratio = p2n / total_changes
        pos_to_neg = 2.0 * ratio
        neg_to_pos = 2.0 * (1.0 - ratio)

        pos_to_neg = max(0.5, min(1.5, pos_to_neg))
        neg_to_pos = max(0.5, min(1.5, neg_to_pos))

        if abs(pos_to_neg - 1.0) < 0.02 and abs(neg_to_pos - 1.0) < 0.02:
            continue

        costs[feat_name] = {
            "pos_to_neg": round(pos_to_neg, 3),
            "neg_to_pos": round(neg_to_pos, 3),
        }

    return costs


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.forms.exists():
        print(f"ERROR: forms.csv not found: {args.forms}", file=sys.stderr)
        return 1
    if not args.datasets.exists():
        print(f"ERROR: datasets.csv not found: {args.datasets}", file=sys.stderr)
        return 1

    expert_datasets = load_expert_datasets(args.datasets)
    if args.split:
        split_datasets = load_split(args.split)
        allowed = expert_datasets & split_datasets
    else:
        allowed = expert_datasets

    print(f"Loading cognate groups from {len(allowed)} datasets...", file=sys.stderr)
    cognate_groups = load_cognate_groups(args.forms, allowed)

    total_pairs = 0
    alignments: list[list[tuple[str | None, str | None]]] = []

    for ds_name, cog_groups in sorted(cognate_groups.items()):
        ds_pairs = 0
        for cog_id, entries in cog_groups.items():
            varieties = {v for v, _ in entries}
            if len(varieties) < 2:
                continue
            seen_varieties: dict[str, list[str]] = {}
            for variety, segments in entries:
                if variety not in seen_varieties:
                    seen_varieties[variety] = segments

            variety_list = list(seen_varieties.items())
            for (v_a, seg_a), (v_b, seg_b) in combinations(variety_list, 2):
                alignment = nw_align(seg_a, seg_b, args.system)
                alignments.append(alignment)
                ds_pairs += 1

            if ds_pairs >= 5000:
                break

        total_pairs += ds_pairs
        print(f"  {ds_name}: {ds_pairs} pairs aligned", file=sys.stderr)

    print(f"\nTotal aligned pairs: {total_pairs} (×2 for both directions)", file=sys.stderr)
    print(f"Tallying feature changes...", file=sys.stderr)

    tallies = tally_feature_changes(alignments, args.system, args.geometry)

    print(f"\nFeature change tallies:", file=sys.stderr)
    for feat_name, counts in sorted(tallies.items()):
        total = counts["pos_to_neg"] + counts["neg_to_pos"]
        if total >= args.min_obs:
            same = counts["same"]
            p2n = counts["pos_to_neg"]
            n2p = counts["neg_to_pos"]
            pct = p2n / total * 100 if total > 0 else 50
            print(
                f"  {feat_name:25s}  same={same:6d}  "
                f"+→−={p2n:5d}  −→+={n2p:5d}  "
                f"ratio={pct:.1f}% pos→neg",
                file=sys.stderr,
            )

    costs = compute_direction_costs(tallies, args.min_obs)

    result = {
        "name": "corecog-derived",
        "source": f"Derived from {total_pairs} cognate pairs across {len(cognate_groups)} CoreCog datasets",
        "caveat": (
            "Direction labels (pos_to_neg, neg_to_pos) are relative to "
            "alphabetically-first variety in each pair. Asymmetry magnitudes "
            "are meaningful across many families, but sign requires phylogenetic "
            "direction (e.g., known proto-language)."
        ),
        "system": args.system,
        "geometry": args.geometry,
        "direction_costs": costs,
    }

    output_json = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_json + "\n", encoding="utf-8")
        print(f"\nWrote {args.output}", file=sys.stderr)
    else:
        print(output_json)

    n_asym = len(costs)
    print(f"\n{n_asym} features show asymmetric direction costs", file=sys.stderr)
    for feat, c in sorted(costs.items()):
        print(
            f"  {feat:25s}  pos→neg={c['pos_to_neg']:.3f}  neg→pos={c['neg_to_pos']:.3f}",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
