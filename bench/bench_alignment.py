#!/usr/bin/env python3
"""Score merkmal's segment distance as an alignment substitution cost.

merkmal supplies a substitution cost, not a gap model or an aligner, so the
question is narrow: as a substitution cost, how does it compare with an
established one?

The comparison is with the SCA sound classes of LingPy. Both scorers run
through the same Needleman-Wunsch implementation here, with the gap cost tuned
per scorer on a held-out half, so that only the substitution matrix differs.
The result concerns the matrix, not LingPy as a whole, which also uses
prosodic strings, swap detection and secondary alignment.

The reference data is BDPA, the Benchmark Database of Phonetic Alignments:
gold multiple alignments from which pairwise alignments are projected. The
script takes a BDPA checkout:

    bench/bench_alignment.py --bdpa <bdpa-checkout>

Results are written to bench/alignment_baseline.txt with --record. Accuracy is
reported over all pairs and over the pairs `distinctive` can read in full, and
the two are to be read together. The gap cost is tuned on half of the
alignments and measured on the other half, and the differences from SCA are
bootstrapped by alignment, because the pairs drawn from one alignment are not
independent. An identity scorer and a consonant/vowel scorer are the lower
references.

BDPA appends annotation rows (`LOCAL`, `SWAPS` and others) with the same shape
as language rows; their cells are markup (`*`, `.`), not transcription. They
are excluded here, and any reader of these files must exclude them likewise.
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
BOOTSTRAP = 2000


# Gold data


# BDPA appends annotation rows to an alignment block. They are named,
# tab-separated and as wide as a language row, so a reader that goes by shape
# takes them for doculects. Their cells are BDPA's own markup (`*` local
# identity, `.` unmarked), not transcription.
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
        # A row made only of markup is not a transcription, whatever its
        # name; this also catches annotation rows not listed above.
        if all(c in MSA_MARKUP_CELLS for c in cells):
            continue
        rows.append(cells)
    return rows


def gold_pairs_grouped(bdpa: Path, rng: random.Random | None = None) -> dict[str, list]:
    """Gold pairwise alignments keyed by the alignment they came from.

    Grouped because up to PAIRS_PER_MSA pairs share a wordlist and a set of
    doculects, so an evaluation split that is to avoid leakage must cut
    between alignments, not between pairs.
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
    """All gold pairs in one shuffled list; the order is part of the baseline."""
    rng = random.Random(SEED)
    groups = gold_pairs_grouped(bdpa, rng)
    out = [pair for name in groups for pair in groups[name]]
    rng.shuffle(out)  # the same rng, so the order matches the recorded baseline
    return out


# Aligning


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


# Scorers


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


IPA_VOWELS = set("aeiouyæøœɐɑɒɔəɘɛɜɞɤɨɪɯɵɶʉʊʌʏ")


def cv_sub():
    """A three-valued reference: 0 for equal segments, 0.5 for two vowels or
    two consonants, 1 otherwise. It says how much of the benchmark a scorer
    that knows only the vowel/consonant split already reaches."""
    import unicodedata

    def vowel(token):
        base = unicodedata.normalize("NFD", token)[:1]
        return base in IPA_VOWELS

    return lambda a, b: 0.0 if a == b else (0.5 if vowel(a) == vowel(b) else 1.0)


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


# Report


def bootstrap_delta(groups, sub_a, gap_a, sub_b, gap_b):
    """95% CI on the column-accuracy difference A - B.

    Resampled by alignment, not by pair: the pairs drawn from one multiple
    alignment share its words and doculects, so they are not independent, and
    a bootstrap over pairs understates the uncertainty.
    """
    deltas = {
        name: [x - y for x, y in zip(per_pair_accuracy(pairs, sub_a, gap_a),
                                     per_pair_accuracy(pairs, sub_b, gap_b), strict=True)]
        for name, pairs in groups.items()
    }
    names = sorted(deltas)
    rng = random.Random(7)
    means = []
    for _ in range(BOOTSTRAP):
        sample = [d for _ in names for d in deltas[names[rng.randrange(len(names))]]]
        means.append(statistics.fmean(sample))
    means.sort()
    every = [d for name in names for d in deltas[name]]
    return (statistics.fmean(every),
            means[int(0.025 * BOOTSTRAP)],
            means[int(0.975 * BOOTSTRAP)])


def run(bdpa: Path, record: bool) -> int:
    groups = gold_pairs_grouped(bdpa)
    primary = "distinctive"
    # The split is between alignments, so that no alignment contributes pairs
    # to both the half that tunes the gap cost and the half that measures.
    names = sorted(groups)
    random.Random(SEED).shuffle(names)
    dev_names = set(names[: len(names) // 2])

    scorers = {
        "identity": identity_sub(),
        "consonant/vowel": cv_sub(),
        "lingpy-SCA": sca_sub(),
        "merkmal:distinctive": merkmal_sub("distinctive"),
        "merkmal:descriptive": merkmal_sub("descriptive"),
        "merkmal:phoible": merkmal_sub("phoible"),
        "merkmal:pbase-spe": merkmal_sub("pbase-spe"),
    }

    out = []
    def emit(line=""):
        print(line)
        out.append(line)

    total = sum(len(pairs) for pairs in groups.values())
    emit(f"BDPA phonetic alignment benchmark  ({total} gold pairwise alignments from")
    emit(f"{len(groups)} alignments, seed {SEED}, {PAIRS_PER_MSA} pairs per alignment; gap tuned")
    emit("on half of the alignments and measured on the other half)")

    readable_groups = {
        name: [p for p in pairs if readable(p, primary)] for name, pairs in groups.items()
    }
    readable_count = sum(len(pairs) for pairs in readable_groups.values())
    subsets = [
        ("ALL PAIRS", groups),
        (f"READABLE UNDER {primary.upper()} "
         f"({readable_count} of {total}, {100 * readable_count / total:.1f}%)", readable_groups),
    ]

    for label, subset in subsets:
        dev = [p for name in names if name in dev_names for p in subset[name]]
        test_groups = {
            name: subset[name] for name in names if name not in dev_names and subset[name]
        }
        test = [p for name in names if name in test_groups for p in test_groups[name]]
        if len(test) < 50:
            emit(f"\n{label}: too few pairs to report")
            continue
        emit()
        emit(label)
        emit(f"  {'scorer':22} {'gap':>5} {'column acc':>11} {'perfect':>9}")
        tuned = {}
        for name, sub in scorers.items():
            gap = tune(dev, sub)
            acc, perfect = score(test, sub, gap)
            tuned[name] = (sub, gap)
            emit(f"  {name:22} {gap:5.2f} {100 * acc:10.2f}% {100 * perfect:8.2f}%")
        emit("  bootstrap 95% CI on column-accuracy difference from SCA (by alignment):")
        for name in scorers:
            if not name.startswith("merkmal:"):
                continue
            d, lo, hi = bootstrap_delta(test_groups, *tuned[name], *tuned["lingpy-SCA"])
            verdict = "not significant" if lo < 0 < hi else "significant"
            emit(f"    {name:22} {100 * d:+6.2f}%  [{100 * lo:+.2f}, {100 * hi:+.2f}]  {verdict}")

    if record:
        header = [
            "# BDPA alignment benchmark, recorded from a deliberate run.",
            "#",
            "# merkmal supplies a substitution cost, not an aligner. This measures that",
            "# cost against LingPy's SCA classes through an identical Needleman-Wunsch.",
            "# The split and the bootstrap are by alignment, since the pairs drawn from",
            "# one alignment are not independent. Read the two blocks together.",
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
