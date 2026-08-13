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
