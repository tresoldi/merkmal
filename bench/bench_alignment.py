#!/usr/bin/env python3
"""Score merkmal's segment distance as an alignment substitution cost.

merkmal supplies a substitution cost and deliberately not a gap model or an
aligner. The question this answers is
therefore narrow and is the only one the library is responsible for: *as a
substitution cost*, is it as good as what the field already uses?

The comparison is against LingPy's SCA sound classes, the incumbent. Both run
through the identical Needleman-Wunsch here, with the gap cost tuned per scorer
on a held-out half, so the only thing that differs is the substitution matrix.
This is not a claim about LingPy-the-system, which also uses prosodic strings,
swap detection and secondary alignment; it is a claim about the matrix.

Reference data is BDPA, the Benchmark Database of Phonetic Alignments: gold
multiple alignments from which pairwise alignments are projected. Point it at a
BDPA checkout:

    bench/bench_alignment.py --bdpa ~/lexibank_clone/bdpa

Results are compared against bench/alignment_baseline.txt and written back with
--record. Coverage is reported alongside accuracy and that pairing is the point:
on pairs merkmal can fully read it comes close to SCA, and over the whole
benchmark it falls well behind, because it cannot read 30% of them. Reporting
the second number without the first would be as misleading as the reverse.

A warning paid for in retracted results: BDPA appends annotation rows (`LOCAL`,
`SWAPS`) that are shaped exactly like language rows. The first version of this
file read them as doculects, which put 8% of pairs -- sequences of `*` and `.`
-- into a phonological benchmark, and inflated every reported figure by roughly
four points. Anything that reads these files by shape must exclude them.
"""

from __future__ import annotations

import argparse
import itertools
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "bench" / "alignment_baseline.txt"

SEED = 1
PAIRS_PER_MSA = 3
GAP_GRID = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
BOOTSTRAP = 400


# --------------------------------------------------------------- gold data


# BDPA appends annotation rows to an alignment block. They are named, tab-
# separated and the same width as a language row, so anything that reads by
# shape picks them up as doculects. Their cells are BDPA's own markup (`*`
# local-identity, `.` unmarked), not transcription.
MSA_ANNOTATION_ROWS = {"LOCAL", "SWAPS", "CROSSED", "MERGE"}
MSA_MARKUP_CELLS = {"*", ".", "-", ""}


def read_msa(path: Path) -> list[list[str]]:
    """Language rows of a BDPA alignment block, annotation rows excluded."""
    rows = []
    for line in path.read_text(encoding="utf-8").split("\n")[2:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        name = parts[0].strip(". ").upper()
        cells = [c.strip() for c in parts[1:]]
        if name in MSA_ANNOTATION_ROWS:
            continue
        # Belt and braces: a row made only of markup is not a transcription,
        # whatever it is called.
        if all(c in MSA_MARKUP_CELLS for c in cells):
            continue
        rows.append(cells)
    return rows


def gold_pairs_grouped(bdpa: Path, rng: random.Random | None = None) -> dict[str, list]:
    """Gold pairwise alignments keyed by the alignment they came from.

    Needed because up to PAIRS_PER_MSA pairs share a wordlist and a set of
    doculects, so any evaluation split has to cut between alignments and not
    between pairs.
    """
    files = sorted((bdpa / "raw" / "msa").glob("*.msa"))
    if not files:
        sys.exit(f"no .msa files under {bdpa / 'raw' / 'msa'}")
    rng = rng if rng is not None else random.Random(SEED)
    groups: dict[str, list] = {}
    for path in files:
        rows = read_msa(path)
        if len(rows) < 2:
            continue
        combos = list(itertools.combinations(range(len(rows)), 2))
        rng.shuffle(combos)
        for i, j in combos[:PAIRS_PER_MSA]:
            # A column gapped in both rows says nothing about this pair.
            cols = zip(rows[i], rows[j], strict=False)
            gold = [(a, b) for a, b in cols if not (a == "-" and b == "-")]
            s1 = [a for a, _ in gold if a != "-"]
            s2 = [b for _, b in gold if b != "-"]
            if s1 and s2:
                groups.setdefault(path.name, []).append((s1, s2, gold))
    return groups


def gold_pairs(bdpa: Path) -> list[tuple[list[str], list[str], list[tuple[str, str]]]]:
    """Flat, shuffled view of the above. Ordering is part of the baseline."""
    rng = random.Random(SEED)
    groups = gold_pairs_grouped(bdpa, rng)
    out = [pair for name in groups for pair in groups[name]]
    rng.shuffle(out)  # same rng instance and state as before grouping existed
    return out


# ---------------------------------------------------------------- aligning


def needleman_wunsch(s1, s2, sub, gap):
    n, m = len(s1), len(s2)
    dist = [[0.0] * (m + 1) for _ in range(n + 1)]
    back = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dist[i][0] = dist[i - 1][0] + gap
        back[i][0] = 1
    for j in range(1, m + 1):
        dist[0][j] = dist[0][j - 1] + gap
        back[0][j] = 2
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cand = (dist[i - 1][j - 1] + sub(s1[i - 1], s2[j - 1]),
                    dist[i - 1][j] + gap,
                    dist[i][j - 1] + gap)
            k = min(range(3), key=lambda t: cand[t])
            dist[i][j], back[i][j] = cand[k], k
    i, j, out = n, m, []
    while i > 0 or j > 0:
        k = back[i][j]
        if k == 0:
            out.append((s1[i - 1], s2[j - 1]))
            i -= 1
            j -= 1
        elif k == 1:
            out.append((s1[i - 1], "-"))
            i -= 1
        else:
            out.append(("-", s2[j - 1]))
            j -= 1
    return out[::-1]


def columns(alignment):
    """Index-based column signature, so alignments are comparable as sets."""
    i = j = 0
    out = []
    for a, b in alignment:
        out.append((i if a != "-" else None, j if b != "-" else None))
        if a != "-":
            i += 1
        if b != "-":
            j += 1
    return set(out)


def score(pairs, sub, gap):
    hit = tot = perfect = 0
    for s1, s2, gold in pairs:
        g = columns(gold)
        p = columns(needleman_wunsch(s1, s2, sub, gap))
        hit += len(g & p)
        tot += len(g)
        perfect += g == p
    return hit / tot, perfect / len(pairs)


def per_pair_accuracy(pairs, sub, gap):
    out = []
    for s1, s2, gold in pairs:
        g = columns(gold)
        p = columns(needleman_wunsch(s1, s2, sub, gap))
        out.append(len(g & p) / len(g))
    return out


def tune(pairs, sub):
    return max(GAP_GRID, key=lambda g: score(pairs, sub, g)[0])


# ----------------------------------------------------------------- scorers


def merkmal_sub(system):
    import merkmal
    cache = {}

    def f(a, b):
        key = (a, b)
        if key not in cache:
            if a == b:
                cache[key] = 0.0
            else:
                try:
                    cache[key] = merkmal.distance(a, b, system=system)
                except Exception:
                    cache[key] = 1.0  # unreadable is maximally distant
        return cache[key]
    return f


def sca_sub():
    from lingpy.sequence.sound_classes import token2class
    from lingpy.settings import rcParams
    model = rcParams["sca"]
    cache = {}

    def f(a, b):
        key = (a, b)
        if key not in cache:
            try:
                ca, cb = token2class(a, "sca"), token2class(b, "sca")
                cache[key] = (10.0 - model.scorer[ca, cb]) / 20.0
            except Exception:
                cache[key] = 0.0 if a == b else 1.0
        return cache[key]
    return f


def identity_sub():
    return lambda a, b: 0.0 if a == b else 1.0


def readable(pair, system):
    import merkmal
    for seq in (pair[0], pair[1]):
        for token in seq:
            try:
                if not merkmal.is_segment(token, system=system):
                    return False
            except Exception:
                return False
    return True


# ------------------------------------------------------------------ report


def bootstrap_delta(pairs, sub_a, gap_a, sub_b, gap_b):
    """95% CI on the column-accuracy difference A - B, paired by pair."""
    deltas = [x - y for x, y in zip(per_pair_accuracy(pairs, sub_a, gap_a),
                                    per_pair_accuracy(pairs, sub_b, gap_b), strict=True)]
    rng = random.Random(7)
    means = []
    for _ in range(BOOTSTRAP):
        sample = [deltas[rng.randrange(len(deltas))] for _ in range(len(deltas))]
        means.append(statistics.fmean(sample))
    means.sort()
    return (statistics.fmean(deltas),
            means[int(0.025 * BOOTSTRAP)],
            means[int(0.975 * BOOTSTRAP)])


def run(bdpa: Path, record: bool) -> int:
    pairs = gold_pairs(bdpa)
    primary = "distinctive"

    scorers = {
        "identity": identity_sub(),
        "lingpy-SCA": sca_sub(),
        "merkmal:distinctive": merkmal_sub("distinctive"),
    }

    out = []
    def emit(line=""):
        print(line)
        out.append(line)

    emit(f"BDPA phonetic alignment benchmark  ({len(pairs)} gold pairwise alignments,")
    emit(f"seed {SEED}, {PAIRS_PER_MSA} pairs per MSA, gap tuned on a held-out half)")

    subsets = [("ALL PAIRS", pairs)]
    cov = [p for p in pairs if readable(p, primary)]
    subsets.append((f"READABLE UNDER {primary.upper()} "
                    f"({len(cov)} of {len(pairs)}, {100 * len(cov) / len(pairs):.1f}%)", cov))

    for label, subset in subsets:
        if len(subset) < 50:
            emit(f"\n{label}: too few pairs to report")
            continue
        dev, test = subset[: len(subset) // 2], subset[len(subset) // 2:]
        emit()
        emit(label)
        emit(f"  {'scorer':22} {'gap':>5} {'column acc':>11} {'perfect':>9}")
        tuned = {}
        for name, sub in scorers.items():
            gap = tune(dev, sub)
            acc, perfect = score(test, sub, gap)
            tuned[name] = (sub, gap)
            emit(f"  {name:22} {gap:5.2f} {100 * acc:10.2f}% {100 * perfect:8.2f}%")
        emit("  bootstrap 95% CI on column-accuracy difference from SCA:")
        for name in ("merkmal:distinctive",):
            d, lo, hi = bootstrap_delta(test, *tuned[name], *tuned["lingpy-SCA"])
            verdict = "not significant" if lo < 0 < hi else "significant"
            emit(f"    {name:22} {100 * d:+6.2f}%  [{100 * lo:+.2f}, {100 * hi:+.2f}]  {verdict}")

    if record:
        header = [
            "# BDPA alignment benchmark, recorded from a deliberate run.",
            "#",
            "# merkmal supplies a substitution cost, not an aligner. This measures that",
            "# cost against LingPy's SCA classes through an identical Needleman-Wunsch.",
            "# Read the two blocks together: parity on readable pairs and a loss overall",
            "# is a coverage result, not a modelling one.",
            "#",
            "# Regenerate with: bench/bench_alignment.py --bdpa <bdpa-checkout> --record",
            "",
        ]
        BASELINE.write_text("\n".join(header + out) + "\n", encoding="utf-8")
        print(f"\nWrote {BASELINE.relative_to(ROOT)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bdpa", type=Path, required=True,
                        help="path to a BDPA checkout containing raw/msa/*.msa")
    parser.add_argument("--record", action="store_true",
                        help="write bench/alignment_baseline.txt")
    args = parser.parse_args()
    return run(args.bdpa, args.record)


if __name__ == "__main__":
    raise SystemExit(main())
