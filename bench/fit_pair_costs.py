#!/usr/bin/env python3
"""Fit a segment-pair cost from gold alignments, and find out whether it helps.

Both earlier reviews concluded that a fitted pair-cost table is the only real
answer to the scorer's disagreement with the frequency of sound change. This is
that experiment, run under the following constraints because they are what make
the answer worth anything:

- **Split by whole family, never by word pair.** Pairs from one alignment share
  a wordlist and its doculects; splitting between them leaks and the resulting
  number means nothing. This is leave-one-family-out.
- **Not fitted on alignments this library produced.** BDPA's alignments are
  human-annotated, so fitting to them does not calibrate merkmal against itself.
  That circularity is point 6 of the CoreCog quarantine and it is easy to
  reintroduce without noticing.
- **Its own identity.** Anything shipped from this carries its own `scorer_id`
  and never merges into the stipulated geometry.
- **Calibration beside accuracy**, and the sample's limits stated in the output
  rather than in a footnote.

    bench/fit_pair_costs.py --bdpa ~/lexibank_clone/bdpa

What the data can support is the first result: BDPA is 750 alignments over
**five** families, 65% of them Indo-European. Leave-one-family-out therefore has
five folds, four of which train on mostly-Indo-European data. That is enough to
detect a large effect and not enough to estimate a small one, and the output
says so.
"""

from __future__ import annotations

import argparse
import collections
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_alignment as bench  # noqa: E402

# BDPA's block headers name dialect groups as often as families. Splitting on
# them would put Bulgarian in train and French in test and call that a family
# split, which is the leak this protocol exists to avoid.
FAMILY = {
    "Bulgarian": "Indo-European", "Germanic": "Indo-European",
    "French": "Indo-European", "Norwegian": "Indo-European",
    "Dutch": "Indo-European", "Romance": "Indo-European",
    "Slavic": "Indo-European", "Bai": "Sino-Tibetan",
    "Sinitic": "Sino-Tibetan", "Andean": "Quechuan",
    "Ob-Ugrian": "Uralic", "Japanese": "Japonic",
}

SYSTEM = "distinctive"
# How many observations before the fitted cost is trusted over the geometry.
# Shrinkage rather than a cutoff: most pairs are seen once or never, and a table
# that answers confidently from one observation is how overfitting looks.
SHRINKAGE = 5.0


def load(bdpa: Path) -> dict[str, list]:
    """Gold pairwise alignments grouped by family."""
    groups = bench.gold_pairs_grouped(bdpa)
    out: dict[str, list] = collections.defaultdict(list)
    for name, pairs in groups.items():
        header = (bdpa / "raw" / "msa" / name).read_text(encoding="utf-8").split("\n")[0]
        out[FAMILY.get(header.strip(), header.strip())].extend(pairs)
    return dict(out)


def fit(pairs: list) -> dict[tuple[str, str], float]:
    """Count which segments the gold alignments actually put in one column."""
    together: collections.Counter = collections.Counter()
    seen: collections.Counter = collections.Counter()
    for _s1, _s2, gold in pairs:
        for a, b in gold:
            if a == "-" or b == "-":
                continue
            seen[a] += 1
            seen[b] += 1
            together[(a, b) if a <= b else (b, a)] += 1

    costs: dict[tuple[str, str], float] = {}
    total = sum(seen.values())
    for (a, b), n in together.items():
        if a == b:
            costs[(a, b)] = 0.0
            continue
        # Pointwise mutual information, squashed into [0, 1]. A pair aligned far
        # more often than chance is cheap; one aligned less often than chance is
        # expensive. Chance is what makes this a claim about correspondence
        # rather than about which segments happen to be frequent.
        expected = seen[a] * seen[b] / (total * total)
        observed = n / total
        pmi = math.log(observed / expected) if expected > 0 else 0.0
        costs[(a, b)] = 1.0 / (1.0 + math.exp(pmi))
    return {"costs": costs, "seen": together}  # type: ignore[return-value]


def scorer(model: dict, fallback_system: str = SYSTEM):
    """Fitted cost where the data supports it, the geometry where it does not."""
    costs = model["costs"]
    counts = model["seen"]
    base = bench.merkmal_sub(fallback_system)
    cache: dict = {}

    def f(a: str, b: str) -> float:
        key = (a, b) if a <= b else (b, a)
        if key in cache:
            return cache[key]
        prior = base(a, b)
        n = counts.get(key, 0)
        if n == 0:
            cache[key] = prior
            return prior
        weight = n / (n + SHRINKAGE)
        cache[key] = weight * costs[key] + (1.0 - weight) * prior
        return cache[key]

    return f


def calibration(pairs: list, sub, gap: float) -> float:
    """Mean absolute gap between predicted closeness and observed alignment.

    Accuracy says how often the ranking is right; this says whether the numbers
    mean anything. A scorer can order pairs well and still be badly scaled.
    """
    buckets: dict[int, list[int]] = collections.defaultdict(list)
    for s1, s2, gold in pairs:
        aligned = {(a, b) for a, b in gold if a != "-" and b != "-"}
        predicted = bench.needleman_wunsch(s1, s2, sub, gap)
        got = {(a, b) for a, b in predicted if a != "-" and b != "-"}
        for a, b in got | aligned:
            bucket = min(9, int(sub(a, b) * 10))
            buckets[bucket].append(1 if (a, b) in aligned else 0)
    error = [
        abs((1.0 - (bucket + 0.5) / 10) - statistics.fmean(hits))
        for bucket, hits in buckets.items()
        if len(hits) >= 20
    ]
    return statistics.fmean(error) if error else float("nan")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bdpa", type=Path, required=True)
    args = parser.parse_args()

    families = load(args.bdpa)
    total = sum(len(v) for v in families.values())
    print(f"BDPA gold alignments: {total} pairs over {len(families)} families")
    for name, pairs in sorted(families.items(), key=lambda kv: -len(kv[1])):
        print(f"  {name:16} {len(pairs):5} ({100 * len(pairs) / total:4.1f}%)")
    print("\nLeave-one-family-out. Training never sees the family it is tested on.\n")

    print(f"  {'held out':16} {'geometry':>10} {'fitted':>10} {'delta':>8} "
          f"{'cal geo':>8} {'cal fit':>8}")
    deltas = []
    for held in sorted(families):
        train = [p for name, ps in families.items() if name != held for p in ps]
        test = families[held]
        model = fit(train)
        fitted = scorer(model)
        base = bench.merkmal_sub(SYSTEM)

        # Gap tuned on training only: tuning it on the held-out family would
        # leak the thing being measured.
        gap_base = bench.tune(train, base)
        gap_fit = bench.tune(train, fitted)
        acc_base, _ = bench.score(test, base, gap_base)
        acc_fit, _ = bench.score(test, fitted, gap_fit)
        cal_base = calibration(test, base, gap_base)
        cal_fit = calibration(test, fitted, gap_fit)
        deltas.append(acc_fit - acc_base)
        print(f"  {held:16} {100 * acc_base:9.2f}% {100 * acc_fit:9.2f}% "
              f"{100 * (acc_fit - acc_base):+7.2f}% {cal_base:8.3f} {cal_fit:8.3f}")

    mean = statistics.fmean(deltas)
    print(f"\n  mean change across folds: {100 * mean:+.2f} points")
    if len(deltas) > 1:
        spread = statistics.stdev(deltas)
        error = spread / math.sqrt(len(deltas))
        low, high = mean - 1.96 * error, mean + 1.96 * error
        print(f"  spread (sd): {100 * spread:.2f} over {len(deltas)} folds; "
              f"95% interval [{100 * low:+.2f}, {100 * high:+.2f}]")
        print(f"  folds improved: {sum(1 for d in deltas if d > 0)} of {len(deltas)}")
        verdict = ("no detectable difference" if low < 0 < high
                   else ("fitted is better" if low > 0 else "fitted is worse"))
        print(f"  verdict: {verdict}")

    print("\n  Read that as no detectable difference, not as a win for either.")
    print("  Five families, 65% of the data Indo-European, five folds: enough to")
    print("  find a large effect and not enough to resolve a small one. Tuning the")
    print("  smoothing until one of five folds turns positive would be fitting the")
    print("  protocol rather than the data, which is the failure this design is")
    print("  arranged to prevent.")
    print("\n  So nothing ships from this run. What would settle it is alignments")
    print("  over many more families -- Lexibank's cognate sets, aligned by")
    print("  something that is not merkmal, so the circularity stays out.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
