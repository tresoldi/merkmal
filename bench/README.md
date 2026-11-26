# Benchmarks

The scripts in this directory measure the library in two respects: its cost
(compiled size and run time) and its behaviour against external references
(expert alignments, published wordlists, other feature systems). Each benchmark
that records a result does so in a committed baseline file, which is updated
only together with a change intended to move it. The results of the external
comparisons, with their interpretation, are reported in
[docs/method/evaluation.md](../docs/method/evaluation.md); this file describes
how each benchmark is run.

The Python scripts use the installed `merkmal` package. Those that read the
Benchmark Database of Phonetic Alignments (BDPA) need a local checkout of
[lexibank/bdpa](https://github.com/lexibank/bdpa) and are not run in CI.

| Script | Question | Recorded in | In CI |
| --- | --- | --- | --- |
| `bench_footprint.sh` | Compiled size and relocation count | `baseline.txt` | yes |
| `bench_lookup.sh` | Time for lookup, tokenization and distance | `baseline.txt` | no |
| `bench_coverage.py` | Coverage of published CLDF transcriptions | `coverage_baseline.txt`, `corpus/coverage-floors.json` | `--check` |
| `bench_alignment.py` | Quality as a substitution cost in alignment | `alignment_baseline.txt` | no |
| `cross_theory.py` | Dependence of segment orderings on the feature system | `cross_theory_baseline.txt` | no |
| `fit_pair_costs.py` | Effect of substitution costs fitted to alignments | `fit_pair_costs_baseline.txt` | no |
| `sweep_tone_distance.py` | Cost of aligning a tone with a segment | docs/guide/c-api.md | no |

## Cost

### `bench_footprint.sh`

Compiles every library source file with `-std=c99 -O2 -DNDEBUG` and reports the
text and read-only data size and the relocation count of each object, with the
generated data tables listed separately. The relocation count is reported
because the generated tables consist largely of pointers into a string pool,
each of which is a relocation in the WebAssembly payload and at load time.

```sh
bench/bench_footprint.sh [build_dir]
```

### `bench_lookup.c`, `bench_lookup.sh`

Measures the CPU time of inventory lookup, tokenization and segment distance,
and reports the lookup separately from the operations that use it. The program
calls the internal function `mki_inventory_find`, so `bench_lookup.sh` builds it
directly against the library sources rather than as a CMake target.

```sh
bench/bench_lookup.sh [build_dir]
```

Both results are recorded in [`baseline.txt`](baseline.txt).

## External references

### `bench_coverage.py`: coverage of published transcriptions

**Question.** For a token in the `Segments` column of a published CLDF
wordlist, does the library have defined behaviour?

**Data.** [`corpus/lexibank-segments.tsv`](corpus/lexibank-segments.tsv), a
table of segment types and token counts aggregated over 152 Lexibank datasets,
with its provenance in [`corpus/provenance.json`](corpus/provenance.json). The
table contains segment types and counts only, without forms, glosses or
language identifiers; it therefore does not redistribute the wordlists, and
their licenses do not apply to it. The manifest states that this reasoning
does not hold for any extension to form-level data.

**Procedure.** For each built-in system, the share of segment types and of
tokens that the system recognizes. Token coverage overstates usability, because
a form can be used only if every one of its tokens is recognized and
unrecognized segments cluster by dataset and family. The share of fully
recognized forms per dataset is therefore recorded as well; it depends on which
segments occur together in a form and cannot be computed from the aggregate
table, so it is rebuilt only from the dataset clones.

**Recorded in.** [`corpus/coverage-floors.json`](corpus/coverage-floors.json)
(minimum type and token coverage per system) and
[`coverage_baseline.txt`](coverage_baseline.txt) (form-level coverage per
dataset, for `distinctive`).

```sh
bench/bench_coverage.py                         # report
bench/bench_coverage.py --check                 # fail below the recorded floors (run in CI)
bench/bench_coverage.py --regenerate <dir>      # rebuild from a directory of CLDF dataset clones
```

### `bench_alignment.py`: substitution cost in pairwise alignment

**Question.** As the substitution cost of a standard aligner, does a merkmal
distance reproduce expert alignments as well as the SCA sound classes of LingPy
(List 2012)?

**Data.** Pairwise alignments projected from the gold multiple alignments of
BDPA.

**Procedure.** Each scorer is used as the substitution cost of the same
Needleman–Wunsch implementation, with the gap cost tuned per scorer on one half
of the pairs and evaluated on the other; an identity scorer is the lower
reference. Only the substitution cost is compared: LingPy as a system also uses
prosodic strings, swap detection and secondary alignment. Results are reported
over all pairs and over the pairs whose every segment the system recognizes,
and the two figures are to be read together: the difference between them is a
coverage effect, not a property of the distances. The script requires LingPy.

**Recorded in.** [`alignment_baseline.txt`](alignment_baseline.txt); see
[evaluation.md, section 1](../docs/method/evaluation.md#1-segment-substitution-cost-in-pairwise-alignment).

```sh
bench/bench_alignment.py --bdpa <bdpa-checkout> [--record]
```

### `cross_theory.py`: dependence on the feature system

**Question.** How often does a statement of the form "A is closer to B than to
C" hold in every feature system?

**Procedure.** Every such ordering over a fixed set of 41 segments is evaluated
in each built-in system, and the orderings on which at least six systems give a
judgement are classified as unanimous or split. The orderings are enumerated
exhaustively rather than selected, so that the rate does not depend on a choice
of examples. With `--bdpa`, the script also compares the systems' alignment
accuracy on BDPA.

**Recorded in.** Not written to a file; the result is reported in
[evaluation.md, section 3](../docs/method/evaluation.md#3-dependence-of-orderings-on-the-feature-theory).

```sh
bench/cross_theory.py [--bdpa <bdpa-checkout>]
```

### `fit_pair_costs.py`: fitted pair costs

**Question.** Do substitution costs estimated from expert alignments improve on
the costs of the geometry?

**Procedure.** Leave-one-family-out cross-validation over the BDPA alignments.
Segment-pair costs are estimated by pointwise mutual information and shrunk
towards the geometry's costs. The split is by whole family, because pairs from
one alignment share a wordlist and its doculects, and the costs are fitted to
human alignments rather than to alignments produced with this library. BDPA
covers five families, which limits the size of effect the procedure can
resolve. No fitted costs are distributed with the library.

**Recorded in.** Not written to a file; the result is reported in
[evaluation.md, section 4](../docs/method/evaluation.md#4-fitted-pair-costs).

```sh
bench/fit_pair_costs.py --bdpa <bdpa-checkout>
```

### `sweep_tone_distance.py`: tone against segment

**Question.** Which cost for aligning a tone with a segment best reproduces the
BDPA alignments that contain tone?

**Procedure.** A substitution function that uses the library for segment pairs,
an ordinal comparison of Chao levels for tone pairs, and a swept constant for a
tone against a segment. The alignments containing tone are split between a
development and a test half, and the script reports the value above which
every cost gives the same alignments. It is the evidence for the cross-tier
cost described in
[docs/guide/c-api.md, Distance with coverage](../docs/guide/c-api.md#distance-with-coverage).

```sh
bench/sweep_tone_distance.py <bdpa-checkout>
```

## References

List, Johann-Mattis. 2012. SCA: Phonetic alignment based on sound classes. In
Marija Slavkovik and Dan Lassiter (eds.), *New directions in logic, language,
and computation*, 32–51. Berlin, Heidelberg: Springer.
