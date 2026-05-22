#!/usr/bin/env python3
"""Audit phonological contrast preservation across merkmal's feature systems."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from itertools import combinations

import merkmal

DEFAULT_INVENTORY = (
    "p b t d k g f v s z ʃ ʒ m n ŋ l r j w "
    "i ɪ e ɛ æ a ɑ ɒ o ɔ u ʊ ə"
).split()


def parse_args(argv: list[str] | None = None) -> list[str]:
    parser = argparse.ArgumentParser(
        description="Audit contrast preservation across merkmal feature systems.",
    )
    parser.add_argument(
        "segments",
        nargs="*",
        default=DEFAULT_INVENTORY,
        help="IPA segments to audit (default: representative 33-segment inventory)",
    )
    args = parser.parse_args(argv)
    return args.segments


def audit_system(
    system_name: str,
    inventory: list[str],
) -> dict:
    covered = []
    uncovered = []
    for seg in inventory:
        if merkmal.get_features(seg, system=system_name) is not None:
            covered.append(seg)
        else:
            uncovered.append(seg)

    collapsed: list[tuple[str, str]] = []
    distances: list[float] = []
    for seg_a, seg_b in combinations(covered, 2):
        try:
            d = merkmal.distance(seg_a, seg_b, system=system_name)
        except (KeyError, NotImplementedError):
            continue
        distances.append(d)
        if d == 0.0:
            collapsed.append((seg_a, seg_b))

    distinct_values = len(set(round(d, 10) for d in distances))

    return {
        "covered": covered,
        "uncovered": uncovered,
        "collapsed": collapsed,
        "distinct_values": distinct_values,
        "total_pairs": len(distances),
    }


def print_report(inventory: list[str], results: dict[str, dict]) -> None:
    print(f"Inventory ({len(inventory)} segments): {' '.join(inventory)}")
    print()

    collapse_counter: Counter[tuple[str, str]] = Counter()
    for system_name, data in results.items():
        for pair in data["collapsed"]:
            collapse_counter[pair] += 1

    print("=" * 60)
    print("PER-SYSTEM SUMMARY")
    print("=" * 60)
    for system_name, data in results.items():
        n_collapsed = len(data["collapsed"])
        n_covered = len(data["covered"])
        n_uncovered = len(data["uncovered"])
        n_distinct = data["distinct_values"]
        print(f"\n  {system_name}")
        print(f"    Coverage:       {n_covered}/{len(inventory)} segments")
        if n_uncovered:
            print(f"    Not recognized: {' '.join(data['uncovered'])}")
        print(f"    Collapsed:      {n_collapsed} pairs")
        print(f"    Discriminability: {n_distinct} distinct distance values")

    print()
    print("=" * 60)
    print("COLLAPSED CONTRASTS (distance = 0)")
    print("=" * 60)
    for system_name, data in results.items():
        if not data["collapsed"]:
            continue
        pairs_str = ", ".join(f"{a}~{b}" for a, b in data["collapsed"])
        print(f"\n  {system_name} ({len(data['collapsed'])} pairs):")
        print(f"    {pairs_str}")

    systems_with_no_collapses = [
        name for name, data in results.items() if not data["collapsed"]
    ]
    if systems_with_no_collapses:
        print(f"\n  No collapses: {', '.join(systems_with_no_collapses)}")

    fragile = {pair: count for pair, count in collapse_counter.items() if count > 1}
    if fragile:
        print()
        print("=" * 60)
        print("MOST FRAGILE CONTRASTS (collapsed by multiple systems)")
        print("=" * 60)
        for (seg_a, seg_b), count in sorted(fragile.items(), key=lambda x: -x[1]):
            systems_collapsing = [
                name for name, data in results.items()
                if (seg_a, seg_b) in data["collapsed"]
            ]
            print(f"  {seg_a}~{seg_b}  collapsed by {count} systems: {', '.join(systems_collapsing)}")
    else:
        print()
        print("No pair is collapsed by more than one system.")


def main(argv: list[str] | None = None) -> int:
    inventory = parse_args(argv)
    systems = merkmal.list_systems()

    results: dict[str, dict] = {}
    for system_name in systems:
        results[system_name] = audit_system(system_name, inventory)

    print_report(inventory, results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
