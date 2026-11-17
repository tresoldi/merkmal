#!/usr/bin/env python3
"""Rewrite data/models/phoible/inventory.tsv cells from the pinned upstream table.

The upstream table is `cldf/parameters.csv` of `cldf-datasets/phoible` v2.0.1,
the release that `provenance.json` pins. Each cell of a row whose grapheme
matches upstream (after NFD and with script g folded to ASCII g) is rewritten
by one rule:

    +           -> +
    -           -> -
    0           -> 0    the feature does not apply to this segment
    N           -> ?    upstream has no feature vector at all (2 segments)
    a,b[,c]     -> ?    a contour; a single-valued cell cannot hold one
    (empty)     -> ?    the source does not say

`0` and `?` are different claims and are kept apart: `0` says the feature does
not apply, `?` that its value is not known here. Neither is compared in a point
distance; they differ for abstract segments
(`docs/method/abstract-segments.md`), where `?` can be completed and `0`
cannot.

A contour becomes `?` rather than one of its phases, because choosing a phase
of `+,-` makes a claim the source does not make. `mk_system_segment_distance_ex`
reports the resulting loss of coverage.

The row sets of this inventory and of v2.0.1 differ; which release's segment
list to carry is a separate question, and rows without an upstream match keep
their values. In those rows, and in columns upstream does not have, a `.` cell
does not say whether the feature applies, so it becomes `?`.

With --check, nothing is written and the exit status is 1 if any cell would
change.

    tools/rebuild_phoible_inventory.py <path-to-cldf/parameters.csv>
    tools/rebuild_phoible_inventory.py <path> --check
"""

from __future__ import annotations

import argparse
import csv
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INVENTORY = ROOT / "data" / "models" / "phoible" / "inventory.tsv"


def fold(grapheme: str) -> str:
    """Match upstream spellings: NFD, and the script g written as ASCII g."""
    return unicodedata.normalize("NFD", grapheme).replace("ɡ", "g")


def cell(value: str) -> str:
    value = (value or "").strip()
    if value in {"+", "-", "0"}:
        return value
    # No single value here: no vector, a contour, or nothing at all.
    return "?"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("upstream", type=Path, help="cldf/parameters.csv from phoible v2.0.1")
    parser.add_argument("--check", action="store_true",
                        help="report what would change and fail if anything would")
    args = parser.parse_args()

    upstream: dict[str, dict[str, str]] = {}
    with args.upstream.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            upstream[fold(row["Name"])] = row

    with INVENTORY.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader)
        rows = [row for row in reader if row]

    features = header[1:]
    changed_cells = 0
    changed_rows = 0
    unmatched = 0
    out_rows = []
    for row in rows:
        source = upstream.get(fold(row[0]))
        if source is None:
            unmatched += 1
            kept = [row[0]] + ["?" if value == "." else value for value in row[1:]]
            changed_cells += sum(a != b for a, b in zip(row, kept, strict=True))
            changed_rows += kept != row
            out_rows.append(kept)
            continue
        new = [row[0]]
        row_changed = False
        for index, name in enumerate(features, start=1):
            if name not in source:
                kept = "?" if row[index] == "." else row[index]
                if kept != row[index]:
                    changed_cells += 1
                    row_changed = True
                new.append(kept)
                continue
            value = cell(source[name])
            if value != row[index]:
                changed_cells += 1
                row_changed = True
            new.append(value)
        changed_rows += row_changed
        out_rows.append(new)

    print(f"rows: {len(rows)} ({unmatched} not in upstream, left as they are)")
    print(f"cells corrected: {changed_cells} across {changed_rows} rows")

    if args.check:
        if changed_cells:
            print("\nFAILED: the inventory does not match the pinned upstream table.")
            return 1
        print("\nOK")
        return 0

    with INVENTORY.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(out_rows)
    print(f"\nWrote {INVENTORY.relative_to(ROOT)}. Re-stamp provenance and regenerate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
