# Evaluation

This document reports how the library's output compares with external
references. The figures are taken from the committed baselines in `bench/`,
which are regenerated only together with a change intended to move them; each
section names the script that reproduces its result. Internal consistency
checks (golden fixtures, the contrast baseline, the generated-data check) are
described in [../development/release-policy.md](../development/release-policy.md)
and are not repeated here.

## 1. Segment substitution cost in pairwise alignment

**Question.** As a substitution cost inside a standard aligner, does a merkmal
distance reproduce expert alignments as well as the sound-class scoring of
LingPy (SCA; List 2012)?

**Data and procedure.** 2,250 gold pairwise alignments drawn from the BDPA
benchmark (three pairs per multiple alignment, seed 1), as distributed in
[lexibank/bdpa](https://github.com/lexibank/bdpa) (commit `e1e3aea`), with
LingPy 2.6.14 for the SCA classes. Each scorer is used as
the substitution cost of the same Needleman–Wunsch implementation; the gap cost
is tuned per scorer on one half of the pairs and evaluated on the other. The
comparison concerns the substitution cost alone: LingPy as a system also uses
prosodic strings, swap detection and secondary alignment, which are not part of
this comparison. An identity scorer (0 for equal segments, 1 otherwise) is the
lower reference.

**Results** (`bench/alignment_baseline.txt`; column accuracy and proportion of
perfectly reproduced alignments on the evaluation half):

| Population | Scorer | Gap | Column accuracy | Perfect |
| --- | --- | ---: | ---: | ---: |
| All pairs (2,250) | identity | 0.80 | 85.85% | 77.51% |
| | LingPy SCA | 0.30 | 96.35% | 94.49% |
| | merkmal `distinctive` | 0.40 | 95.68% | 93.24% |
| Pairs fully readable by `distinctive` (2,163; 96.1%) | identity | 0.80 | 86.49% | 78.56% |
| | LingPy SCA | 0.30 | 96.48% | 94.55% |
| | merkmal `distinctive` | 0.40 | 95.90% | 93.90% |

Bootstrap 95% intervals for the difference in column accuracy from SCA:
−0.49% [−1.06, +0.17] over all pairs, −0.39% [−0.95, +0.10] over the readable
pairs.

**Interpretation.** The difference from SCA is not significant, either over
the whole benchmark or on the pairs whose every segment the system recognizes.
In the 3.9% of pairs that contain a segment the system does not recognize (a
coverage limitation, section 2), that segment costs 1.0 against any other
segment, which lowers the figure over all pairs; neither figure should be
reported without the other. An interval that includes zero shows that no
difference is detectable at this sample size, not that the two are
equivalent.

The tuned gap costs are specific to each scorer, because the distributions of
distances differ between systems.

**Reproduction.** `bench/bench_alignment.py --bdpa <BDPA checkout> [--record]`.
The benchmark requires a local BDPA checkout and is therefore not run in CI.

### Choice of the default system

`distinctive` and `descriptive` recognize exactly the same graphemes over the
corpus of section 2 (7,396 segment types, no disagreement), so the choice
between them rests on scoring alone. When the default was set (release 0.9.0),
the same alignment benchmark placed `distinctive` within the confidence
interval of SCA (−0.39%, interval including zero) and the geometry-scored
systems below it (−0.79%, significant). The current measurement for
`distinctive` is the one in the table above.

## 2. Coverage of published transcriptions

**Question.** For a segment that occurs in the `Segments` column of a published
CLDF wordlist, does the library have defined behaviour?

**Data.** `bench/corpus/lexibank-segments.tsv`, an aggregate table of segment
types and token counts from 152 Lexibank datasets (7,396 segment types). It
contains no forms, glosses or language identifiers; its provenance is recorded
in `bench/corpus/provenance.json`.

**Results.** Recognition floors per system are recorded in
`bench/corpus/coverage-floors.json`, and the check fails if coverage falls below
them. For `distinctive` and `descriptive` the floors are 95.36% of segment types
and 99.72% of tokens. They were 95.44% until 0.10.0, which refuses a mark
written twice on one letter; the six segment types that does affect (`ts̠̠`,
`ɑ̠̠`, `ao̠̠̠`, `õ̃i`, `ẽː̃`, `⁵/ẽː̃`) were read as the type with the mark once.

Token coverage overstates usability: a form can be used only if every one of its
segments is recognized, and unrecognized segments cluster by dataset and family.
`bench/coverage_baseline.txt` therefore records, for each dataset, the
proportion of forms whose segments are all recognized. Of the 152 datasets, 143
reach at least 99%; eight lie between 74.4% and 98.7%; and one
(`williamsonbenuecongo`) has no fully readable form, although 62.4% of its
tokens are recognized.

**Reproduction.** `bench/bench_coverage.py` reports, `--check` compares with the
floors (run in CI), and `--regenerate <directory of Lexibank clones>` rebuilds
the per-dataset table.

## 3. Dependence of orderings on the feature theory

**Question.** How often does a statement of the form "A is closer to B than to
C" hold regardless of which feature system is used?

**Procedure.** Every such ordering over a set of 41 segments on which at least
six systems give a judgement, evaluated in each of the seven built-in systems:
`distinctive`, `descriptive`, PHOIBLE's binary table, and the four P-base
feature sets, among them the acoustic features of Jakobson, Fant and Halle.

**Result.** Of 29,224 orderings, 62.5% are unanimous and 37.5% differ between
systems. A conclusion drawn from one feature system is therefore in part a
conclusion about that system, and the system used should be reported.

**Reproduction.** `bench/cross_theory.py [--bdpa <BDPA checkout>]`.

## 4. Fitted pair costs

**Question.** Would substitution costs estimated from aligned data improve on
the geometry's costs?

**Procedure.** Leave-one-family-out cross-validation over the BDPA alignments,
with segment-pair costs estimated by pointwise mutual information and shrunk
towards the geometry's costs.

**Result.** No detectable difference: mean +0.28 points of column accuracy, 95%
interval [−0.71, +1.27], improvement in three of five folds. BDPA covers five
families and is 65% Indo-European, which suffices to detect a large effect but
not to resolve a small one. No fitted costs are distributed with the library.

**Reproduction.** `bench/fit_pair_costs.py --bdpa <BDPA checkout>`.

## References

List, Johann-Mattis. 2012. SCA: Phonetic alignment based on sound classes. In
Marija Slavkovik and Dan Lassiter (eds.), *New directions in logic, language,
and computation*, 32–51. Berlin, Heidelberg: Springer.
