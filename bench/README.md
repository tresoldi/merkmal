# Benchmarks

Four benchmarks, in two groups. Each has a committed baseline, and a baseline is
updated only alongside a change meant to move it, so a diff here is always an
argued change.

## Does it cost what it used to?

| | |
| --- | --- |
| `bench_footprint.sh` | compiled size and relocation count |
| `bench_lookup.c` / `.sh` | inventory lookup, tokenization, distance |

Recorded in [`baseline.txt`](baseline.txt).

## Is it any good, and can it read the data?

These two exist because every other guard in this repository — golden fixtures,
contrast baseline, generated-data check — measures the library against itself.
All of them pass on a library that is internally consistent and useless in
practice. These measure it against the outside.

### `bench_coverage.py` — coverage of real CLDF data

```sh
bench/bench_coverage.py                          # report
bench/bench_coverage.py --check                  # fail below the recorded floors
bench/bench_coverage.py --regenerate ~/lexibank  # rebuild from CLDF clones
```

The metric is not "does `is_segment` work" but "if a token appears in a CLDF
`Segments` column, does merkmal have defined behaviour for it". Token coverage
alone flatters the result: a form is only usable if *every* token in it parses,
and failures cluster by language family, so a 95% token rate can coexist with an
entire branch of the tree being unreadable. Both numbers are reported, and
[`coverage_baseline.txt`](coverage_baseline.txt) records the per-dataset
form-level rate, which cannot be recomputed from the aggregate fixture because
it depends on which segments co-occur in a form.

Runs in CI against [`corpus/lexibank-segments.tsv`](corpus/), an aggregate
segment-frequency table with its own provenance manifest. It carries segment
types and counts only — no forms, glosses, or language identifiers — so it does
not redistribute the wordlists and does not inherit their licenses. If it is
ever extended to carry form-level data that reasoning stops holding; see
`corpus/provenance.json`.

### `cross_theory.py` — does the conclusion survive the feature theory?

```sh
bench/cross_theory.py [--bdpa ~/lexibank_clone/bdpa]
```

The one question this library can answer and its neighbours cannot: PanPhon has
one feature set, CLTS has none, LingPy has sound classes. Here the same claim is
put to Hayes-style distinctive features, a descriptive geometry, PHOIBLE's
binary table, and three P-base sets including Jakobson-Fant-Halle's *acoustic*
features.

Swept exhaustively rather than hand-picked, because a hand-picked set shows
whatever the picker expected — the first version of this used fifteen claims I
chose, and all fifteen were unanimous, which taught nobody anything. Over every
"A is closer to B than to C" that 41 segments can state and at least six systems
have an opinion on: **62.6% unanimous, 37.4% split**.

A third of the orderings depend on which feature theory answers. That is not a
defect in any of them — SPE, JFH and PHOIBLE disagree about what a segment *is*
— but it means a result resting on one of them is partly a result about that
theory. Run it twice and say which you used.

### `fit_pair_costs.py` — would a fitted table do better?

```sh
bench/fit_pair_costs.py --bdpa ~/lexibank_clone/bdpa
```

Leave-one-family-out over BDPA's human alignments, with segment-pair costs from
pointwise mutual information shrunk toward the geometry. The answer on this data
is **no detectable difference**: mean −0.28 points, 95% interval [−0.92, +0.35],
1 of 5 folds improved.

Nothing ships from it. BDPA is five families and 65% Indo-European — enough to
find a large effect, not to resolve a small one — and tuning the smoothing until
a fold turns positive would be fitting the protocol rather than the data. That
is how the quarantined CoreCog prior went wrong, and the constraints here exist
to prevent a repeat.

### `bench_alignment.py` — the substitution cost, against the incumbent

```sh
bench/bench_alignment.py --bdpa ~/lexibank_clone/bdpa [--record]
```

merkmal supplies a substitution cost and deliberately not a gap model or an
aligner. So the only question it is responsible for is whether that cost is as
good as what the field already uses, and the comparison is against LingPy's SCA
sound classes through an identical Needleman-Wunsch, gap tuned per scorer on a
held-out half. This is not a claim about LingPy-the-system, which also brings
prosodic strings, swap detection and secondary alignment.

Needs a [BDPA](https://github.com/lexibank/bdpa) checkout, so it is not wired
into CI. Results in [`alignment_baseline.txt`](alignment_baseline.txt).

Read its two blocks together. On pairs merkmal can fully read it reaches SCA
parity; over the whole benchmark it loses, because it cannot read a third of
them. That gap is a coverage result, not a modelling one, and reporting either
number alone would misrepresent it.
