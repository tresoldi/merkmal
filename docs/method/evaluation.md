# Evaluation

This document reports how the library's output compares with external
references. The figures are taken from the committed baselines in `bench/`
(`alignment_baseline.txt`, `coverage_baseline.txt` and
`corpus/coverage-floors.json`, `cross_theory_baseline.txt`,
`fit_pair_costs_baseline.txt`),
which are regenerated only together with a change intended to move them; each
section names the script that reproduces its result. Internal consistency
checks (golden fixtures, the contrast baseline, the generated-data check) are
described in [../development/release-policy.md](../development/release-policy.md)
and are not repeated here.

## 1. Segment substitution cost in pairwise alignment

**Question.** As a substitution cost inside a standard aligner, does a merkmal
distance reproduce expert alignments as well as the sound-class scoring of
LingPy (SCA; List 2012)?

**Data and procedure.** 2,250 gold pairwise alignments drawn from the 750
multiple alignments of the BDPA benchmark (three pairs per alignment, seed 1),
as distributed in [lexibank/bdpa](https://github.com/lexibank/bdpa) (commit
`e1e3aea`), with LingPy 2.6.14 for the SCA classes. Each scorer is used as the
substitution cost of the same Needleman–Wunsch implementation; the gap cost is
tuned per scorer on half of the alignments and evaluated on the other half.
The split, and the bootstrap of the differences, are by alignment rather than
by pair, because the pairs drawn from one alignment share its words and
doculects and are not independent. The comparison concerns the substitution
cost alone: LingPy as a system also uses prosodic strings, swap detection and
secondary alignment, which are not part of this comparison. Two references
bound the result from below: an identity scorer (0 for equal segments, 1
otherwise), and a consonant/vowel scorer (0 for equal segments, 0.5 for two
vowels or two consonants, 1 otherwise) that knows nothing but that split.

**Results** (`bench/alignment_baseline.txt`; column accuracy and proportion of
perfectly reproduced alignments on the evaluation half):

| Population | Scorer | Gap | Column accuracy | Perfect |
| --- | --- | ---: | ---: | ---: |
| All pairs (2,250) | identity | 0.70 | 85.27% | 76.89% |
| | consonant/vowel | 0.80 | 92.66% | 88.36% |
| | LingPy SCA | 0.30 | 96.24% | 94.13% |
| | merkmal `distinctive` | 0.30 | 95.95% | 92.98% |
| | merkmal `descriptive` | 0.40 | 95.58% | 92.18% |
| | merkmal `phoible` | 0.60 | 92.09% | 87.91% |
| | merkmal `pbase-spe` | 0.60 | 92.03% | 88.00% |
| Pairs fully readable by `distinctive` (2,163; 96.1%) | LingPy SCA | 0.40 | 96.16% | 94.17% |
| | merkmal `distinctive` | 0.40 | 96.00% | 94.08% |
| | merkmal `descriptive` | 0.50 | 95.61% | 93.26% |

Bootstrap 95% intervals for the difference in column accuracy from SCA, over
all pairs: `distinctive` −0.22% [−0.78, +0.35], `descriptive` −0.56%
[−1.26, +0.16], `phoible` −3.68% [−4.94, −2.47], `pbase-spe` −3.71%
[−4.98, −2.49]; on the readable pairs, `distinctive` −0.03% [−0.73, +0.59].

**Interpretation.** The categorical systems are slightly below SCA as point
estimates, and the difference is not resolved at this sample size: an interval
that includes zero shows that no difference is detectable, not that the
scorers are equivalent. Most of what any of them achieves is already reached
by the consonant/vowel split, which leaves about 3.6 points between it and
SCA. The valued systems are clearly worse as alignment costs, worse than the
consonant/vowel scorer, and are meant for comparing feature theories rather
than for alignment. In the 3.9% of pairs that contain a segment `distinctive`
does not recognize (a coverage limitation, section 2), that segment costs 1.0
against any other segment, which lowers the figure over all pairs; neither
figure should be reported without the other.

The tuned gap costs are specific to each scorer, because the distributions of
distances differ between systems. Several of the library's choices were made
while looking at this benchmark (the default system, the cross-tier cost, the
vowel/consonant dimension of `distinctive`), so it is not an independent test
of them.

**Reproduction.** `bench/bench_alignment.py --bdpa <BDPA checkout> [--record]`.
The benchmark requires a local BDPA checkout and is therefore not run in CI.

### Choice of the default system

`distinctive` and `descriptive` recognize exactly the same graphemes over the
corpus of section 2 (7,396 segment types, no disagreement), so the choice
between them rests on scoring alone. `distinctive` is the default; on the
measurement above both are within the interval of SCA, `distinctive` nearer to
it.

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
and 99.72% of tokens; for `phoible` 77.79% and 95.77%, and for the P-base
systems 63.41-67.09% and 95.02-95.32%. The valued floors fell after 0.10.0,
when a valued system began refusing a mark whose effect it cannot learn from
its own table instead of reading the segment as its base (`kˀ`, `ä`, `i̠` in
P-base). The categorical floors were 95.44% until 0.10.0, which refuses a mark
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

**Result** (`bench/cross_theory_baseline.txt`). Of 28,769 orderings, 66.5%
are unanimous and 33.5% differ between systems. A conclusion drawn from one feature system is therefore in part a
conclusion about that system, and the system used should be reported.

**Reproduction.** `bench/cross_theory.py [--bdpa <BDPA checkout>]`.

## 4. Fitted pair costs

**Question.** Would substitution costs estimated from aligned data improve on
the geometry's costs?

**Procedure.** Leave-one-family-out cross-validation over the BDPA alignments,
with segment-pair costs estimated by pointwise mutual information and shrunk
towards the geometry's costs.

**Result** (`bench/fit_pair_costs_baseline.txt`). No detectable difference:
mean +0.26 points of column accuracy, 95% interval [−0.70, +1.22], improvement
in three of five folds. BDPA covers five
families and is 65% Indo-European, which suffices to detect a large effect but
not to resolve a small one. No fitted costs are distributed with the library.

**Reproduction.** `bench/fit_pair_costs.py --bdpa <BDPA checkout>`.

## References

List, Johann-Mattis. 2012. SCA: Phonetic alignment based on sound classes. In
Marija Slavkovik and Dan Lassiter (eds.), *New directions in logic, language,
and computation*, 32–51. Berlin, Heidelberg: Springer.
