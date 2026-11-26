#!/usr/bin/env python3
"""Rebuild the four P-base inventories from the upstream data files.

The upstream table is `pbase/ipa2allfeatures.csv` from P-base's data archive
(`https://phon.chass.ncsu.edu/pbase/pbasefiles.zip`, "PBase data as of October
2, 2022"), which `provenance.json` pins by hash. It has one row per IPA
transcription and one column per feature, prefixed by its feature system:
`JFH.` (Jakobson, Fant and Halle), `SPE.`, `HC.` (Halle and Clements) and
`UFTc.` (Unified Feature Theory). Each system's columns become
`data/models/pbase-<system>/inventory.tsv`, in upstream order, and each cell
is rewritten by one rule:

    +   -> +
    -   -> -
    x   -> +    UFT: the node is present (V-place, vocalic)
    o   -> -    UFT: the node is absent
    n   -> 0    the feature does not apply to this segment
    .   -> ?    the source does not give a value

`x` and `o` are a contrast, not a midpoint: a vowel has the vocalic node and a
plain consonant has not. Read as 0, as the hand extraction this replaces read
them, they were never compared. `n` is P-base's "not applicable" (`lateral` on
a non-coronal, `distributed` on a vowel), the claim PHOIBLE writes `0`, and is
not compared either; it used to be scored as a value halfway between `+` and
`-`.

A transcription listed more than once is kept once, at its first row; a later
row that disagrees on a cell makes that cell `?`.

With --check, nothing is written and the exit status is 1 if any file would
change.

    tools/rebuild_pbase_inventories.py <path-to-pbase/ipa2allfeatures.csv>
    tools/rebuild_pbase_inventories.py <path> --check
"""

from __future__ import annotations

import argparse
import csv
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYSTEMS = {"JFH": "pbase-jfh", "SPE": "pbase-spe", "HC": "pbase-hc", "UFTc": "pbase-uftc"}
CODES = {"+": "+", "-": "-", "x": "+", "o": "-", "n": "0", ".": "?"}


def fold(grapheme: str) -> str:
    """The key two spellings of one transcription share: NFD, script g as g."""
    return unicodedata.normalize("NFD", grapheme).replace("ɡ", "g")


def read_upstream(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))
    return [name.strip() for name in rows[0]], [row for row in rows[1:] if row]


def build(header: list[str], rows: list[list[str]], prefix: str) -> str:
    columns = [i for i, name in enumerate(header) if name.startswith(prefix + ".")]
    names = [header[i][len(prefix) + 1:] for i in columns]
    table: dict[str, tuple[str, list[str]]] = {}
    for row in rows:
        values = []
        for i in columns:
            value = row[i].strip()
            if value not in CODES:
                raise SystemExit(f"{row[0]!r}: unknown code {value!r} in {header[i]}")
            values.append(CODES[value])
        key = fold(row[0])
        if key not in table:
            table[key] = (row[0], values)
        else:
            spelling, kept = table[key]
            table[key] = (spelling, [a if a == b else "?" for a, b in zip(kept, values, strict=True)])
    lines = ["\t".join(["GRAPHEME", *names])]
    lines += ["\t".join([spelling, *values]) for spelling, values in table.values()]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("table", type=Path, help="pbase/ipa2allfeatures.csv")
    parser.add_argument("--check", action="store_true", help="fail if a file would change")
    args = parser.parse_args()

    header, rows = read_upstream(args.table)
    changed = []
    for prefix, system in SYSTEMS.items():
        path = ROOT / "data" / "models" / system / "inventory.tsv"
        text = build(header, rows, prefix)
        if path.read_text(encoding="utf-8") != text:
            changed.append(system)
            if not args.check:
                path.write_text(text, encoding="utf-8")
    if args.check:
        if changed:
            print(f"would change: {', '.join(changed)}", file=sys.stderr)
            return 1
        print("the P-base inventories match the upstream table")
        return 0
    print(f"rewrote {len(changed)} inventories" + (f": {', '.join(changed)}" if changed else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
