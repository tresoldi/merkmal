#!/usr/bin/env python3
"""Rewrite models/phoible/inventory.tsv cells from the pinned upstream table.

The extraction that produced this inventory was not self-consistent. Measured
against `cldf-datasets/phoible` v2.0.1, the release `provenance.json` pins:

- 3,729 cells where upstream says `0` -- the feature does not apply -- were
  written `-`, which asserts it applies and is absent;
- 761 cells where upstream gives `+` or `-` were written `.`, dropping a value
  the source states;
- 686 cells where upstream gives a per-phase contour such as `+,-` were resolved
  to a single sign, while 3,788 other contours were written `.`.

None of that is visible in a distance: it moves scores without ever failing a
check. This script applies one rule to every cell instead:

    +           -> +
    -           -> -
    0           -> .    the feature does not apply to this segment
    N           -> .    upstream has no feature vector at all (2 segments)
    a,b[,c]     -> .    a contour; a single-valued cell cannot hold one
    (empty)     -> .

Contours collapse rather than resolve because picking one phase of `+,-` invents
a claim the source does not make. `.` says "this table cannot represent it",
which is true, and `mk_system_segment_distance_ex` now reports the coverage cost
of saying so.

Only rows whose grapheme matches upstream are touched. The row *sets* also
differ -- 17 graphemes here that v2.0.1 lacks, 58 there that this inventory
lacks -- and reconciling those is a separate question about which release's
segment list to carry, not a cell-level defect.

    scripts/rebuild_phoible_inventory.py <path-to-cldf/parameters.csv>
    scripts/rebuild_phoible_inventory.py <path> --check
"""

from __future__ import annotations

import argparse
import csv
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INVENTORY = ROOT / "models" / "phoible" / "inventory.tsv"


def fold(grapheme: str) -> str:
    """Match upstream spellings: NFD, and the script g written as ASCII g."""
    return unicodedata.normalize("NFD", grapheme).replace("ɡ", "g")


def cell(value: str) -> str:
    value = (value or "").strip()
    if value in {"+", "-"}:
        return value
    # Everything else says, in one way or another, that there is no single
    # value here: not applicable, no vector, a contour, or nothing at all.
    return "."


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
            out_rows.append(row)
            continue
        new = [row[0]]
        row_changed = False
        for index, name in enumerate(features, start=1):
            if name not in source:
                new.append(row[index])
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
