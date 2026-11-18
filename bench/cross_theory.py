#!/usr/bin/env python3
"""Test whether a conclusion holds when the feature theory changes.

The same analysis runs under every built-in system: `distinctive` (after
Clements and Hume 1995), `descriptive`, PHOIBLE's binary features, and the four
P-base sets, among them the acoustic features of Jakobson, Fant and Halle
(1952). The question is not which system is right but whether the answer
changes between them. A result that holds under all of them is a result about
the sounds; one that holds under one system is a result about that feature
set.

    bench/cross_theory.py [--bdpa <checkout>]

Two analyses:

1. **Segment orderings.** Every claim of the form "a is closer to b than to c"
   over a fixed set of 41 segments is evaluated, rather than a hand-picked
   selection. A claim counts when at least six systems give a strict answer
   (ties and unreadable segments abstain). With the seven built-in systems,
   37.5% of the 29,224 counted claims are split (as this script prints them).
   The rate is the result; the listed examples are illustrations.
2. **Alignment accuracy**, if a BDPA checkout is given: whether the ranking of
   systems is stable, which is a different question from whether any of them
   aligns well.
"""

from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import merkmal

sys.path.insert(0, str(Path(__file__).resolve().parent))

# A segment set broad enough to cross every major class boundary and small
# enough to sweep exhaustively: 41 segments give 31,980 claims (a choice of a
# and of an unordered pair b, c from the rest).
SEGMENTS = [
    "p", "b", "t", "d", "k", "g", "m", "n", "ŋ", "s", "z", "f", "v", "ʃ", "ʒ",
    "h", "l", "r", "j", "w", "i", "e", "ɛ", "a", "ɔ", "o", "u", "y", "ø", "ə",
    "tʃ", "dʒ", "ts", "θ", "ð", "x", "ɣ", "q", "ʔ", "ɲ", "ʎ",
]

# Claims of the form "a is closer to b than to c" that are shown whatever the
# sweep finds: a split on one of these indicates an error in a feature set
# rather than a contested question.
SANITY = [
    ("p", "b", "a", "a stop is closer to its voiced counterpart than to a vowel"),
    ("i", "e", "a", "adjacent vowel heights beat distant ones"),
    ("m", "n", "s", "two nasals beat a nasal and a fricative"),
    ("s", "z", "t", "voicing is a smaller step than manner"),
]


def systems() -> list[str]:
    return merkmal.list_systems()


def votes(names: list[str], a: str, b: str, c: str, cache: dict) -> list[bool]:
    """Which systems say d(a,b) < d(a,c). Ties and refusals abstain."""
    out = []
    for system in names:
        pair = []
        for x, y in ((a, b), (a, c)):
            key = (x, y, system)
            if key not in cache:
                try:
                    cache[key] = merkmal.distance(x, y, system=system)
                except Exception:  # noqa: BLE001 - a system that cannot read these abstains
                    cache[key] = None
            pair.append(cache[key])
        if pair[0] is None or pair[1] is None or pair[0] == pair[1]:
            continue
        out.append(pair[0] < pair[1])
    return out


def orderings() -> int:
    names = systems()
    cache: dict = {}

    print(f"Sweeping every ordering claim over {len(SEGMENTS)} segments, "
          f"across {len(names)} feature theories.\n")
    for a, b, c, gloss in SANITY:
        result = votes(names, a, b, c, cache)
        agree = sum(1 for v in result if v)
        mark = "unanimous" if agree == len(result) else f"SPLIT {agree}/{len(result)}"
        print(f"  d({a},{b}) < d({a},{c})  {gloss:52} {mark}")

    total = unanimous = 0
    contested: list[tuple[int, str, str, str, int, int]] = []
    for a in SEGMENTS:
        for b, c in itertools.combinations(SEGMENTS, 2):
            if b == a or c == a:
                continue
            result = votes(names, a, b, c, cache)
            if len(result) < 6:
                continue  # too few systems answer for a split to be meaningful
            total += 1
            agree = sum(1 for v in result if v)
            if agree in (0, len(result)):
                unanimous += 1
            else:
                minority = min(agree, len(result) - agree)
                contested.append((minority, a, b, c, agree, len(result)))

    split = total - unanimous
    print(f"\n  {total} claims where at least 6 systems have an opinion")
    print(f"    unanimous: {unanimous} ({100 * unanimous / total:.1f}%)")
    print(f"    split:     {split} ({100 * split / total:.1f}%)")

    contested.sort(key=lambda row: (-row[0], row[1], row[2]))
    print("\n  Most evenly split:")
    for _minority, a, b, c, agree, n in contested[:8]:
        print(f"    d({a},{b}) < d({a},{c})   {agree}/{n} say yes")

    print("\n  A third of these depend on which feature theory answers. That is not")
    print("  a defect in any of them -- SPE, JFH and PHOIBLE disagree about what a")
    print("  segment *is* -- but a result resting on one of them is a result about")
    print("  that theory. Run your analysis twice and say which you used.")
    return split


def alignment(bdpa: Path) -> None:
    import bench_alignment as bench

    pairs = bench.gold_pairs(bdpa)
    dev, test = pairs[: len(pairs) // 2], pairs[len(pairs) // 2 :]
    print("\nAlignment accuracy under each feature theory (BDPA, gap tuned on dev):\n")
    print(f"  {'system':14} {'gap':>5} {'column acc':>11} {'readable':>10}")
    rows = []
    for name in systems():
        sub = bench.merkmal_sub(name)
        readable = sum(1 for p in test if bench.readable(p, name))
        gap = bench.tune(dev, sub)
        acc, _perfect = bench.score(test, sub, gap)
        rows.append((name, acc))
        print(f"  {name:14} {gap:5.2f} {100 * acc:10.2f}% {100 * readable / len(test):9.1f}%")
    rows.sort(key=lambda r: -r[1])
    spread = rows[0][1] - rows[-1][1]
    print(f"\n  best {rows[0][0]} at {100 * rows[0][1]:.2f}%, worst {rows[-1][0]} at "
          f"{100 * rows[-1][1]:.2f}% -- a spread of {100 * spread:.2f} points.")
    print("  Coverage moves this as much as the feature theory does; read the")
    print("  readable column beside the accuracy, not instead of it.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bdpa", type=Path, help="a BDPA checkout, for the alignment half")
    args = parser.parse_args()
    orderings()
    if args.bdpa:
        alignment(args.bdpa)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
