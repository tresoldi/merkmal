# Can `merkmal` become the reference library?

**Reviewer perspective:** computational historical linguistics and phonological
typology. **Date:** 2026-08-13. **Against:** `282cef2` (`refactor/c99-modernization`).

**Method.** Every number below was measured, not estimated. Two corpora:

- **Lexibank**, 152 CLDF datasets with a populated `Segments` column
  (2,721,234 forms; 14,796,205 segment tokens; 7,398 distinct segment types),
  from the local clones in `~/lexibank_clone`.
- **BDPA**, the Benchmark Database of Phonetic Alignments — 750 gold-standard
  multiple alignments, from which I sampled 2,250 gold pairwise alignments.

This review does not re-audit
[`independent-linguistic-review.md`](independent-linguistic-review.md). Those
findings were largely acted on and I confirmed the important ones: the vowel
space is now ordinally correct, Chao tone levels are monotone, `d(w, u) <
d(w, p)` holds in `broad`, `classes.tsv`'s `resonant` class is fixed and `XXX`
is gone, the `mb`/`nd` blocklist is gone. That work landed.

The question here is different and is the one the project has actually asked:
**what stands between this library and being the thing people in the field
reach for by default?** The answer turns out to be measurable, and it is not
what either previous review was looking at.

---

## Executive summary

**The phonology is good enough. The coverage is not, and the coverage problem
is concentrated in exactly the languages where the field's open problems are.**

Two headline measurements.

**1. On alignment data `merkmal` can fully read, it is statistically
indistinguishable from LingPy's SCA** — the field's incumbent, a 28-symbol
sound-class alphabet from 2012. Same Needleman–Wunsch harness, gap cost tuned
per scorer on a dev half, evaluated on a held-out half:

| scorer | column accuracy | perfect alignments |
| --- | ---: | ---: |
| LingPy SCA | 96.87% | 93.65% |
| `merkmal:distinctive` | **96.35%** | **93.37%** |
| `merkmal:broad` | 95.67% | 92.27% |
| identity baseline | 87.35% | 78.87% |

Bootstrap 95% CI on the difference from SCA: `distinctive` −0.25%
[−0.87, +0.39], **not significant**. (`broad` −0.93% [−1.69, −0.14] *is*
significant — see §4.) A feature geometry reaching parity with SCA is a real
result and the project should claim it.

**2. Over the whole benchmark, `merkmal` loses, and loses only because it
cannot read 36% of the pairs.**

| scorer | column accuracy | perfect |
| --- | ---: | ---: |
| LingPy SCA | 91.66% | 88.18% |
| `merkmal:distinctive` | 89.60% | 85.07% |

−1.98% [−2.78, −1.13], significant. Every point of that gap is coverage. On the
802 pairs containing at least one token `merkmal` rejects, it degrades toward
the identity baseline (78.82%) while SCA holds at 83.53%, because SCA's
converter maps *everything* — including the tokens `merkmal` refuses.

**3. Across Lexibank, 28 of 152 datasets have effectively zero forms that
`merkmal` can parse end to end**, and they are, without exception, the tonal
ones: Sinitic, Hmong-Mien, Bai, Tai-Kadai, Lolo-Burmese, Karen, Tujia,
Benue-Congo.

| | |
| --- | ---: |
| median dataset: forms fully parsed | 95.9% |
| datasets below 90% | 52 of 152 |
| datasets below 50% | 31 of 152 |
| datasets below 3% | 26 of 152 |

The single cause is that **CLTS/BIPA writes tone as its own segment**
(`t o ³³`), and `merkmal` only accepts tone bound to a vowel (`a³³`). 474,905
tokens — 3.3% of all Lexibank tokens, and the majority of tokens in every tonal
dataset — are standalone tone tokens that `is_segment` rejects.

A library that cannot process Sinitic or Hmong-Mien wordlists in the format the
field publishes them in cannot be the reference library for computational
historical linguistics. This is the finding.

---

## 1. Where `merkmal` sits in the field

It helps to be precise about the neighbours, because "reference library" means
different things against each of them.

| | what it is | has a distance? | ecosystem role |
| --- | --- | --- | --- |
| **CLTS** / `pyclts` | transcription-system interoperability: maps graphemes from IPA, X-SAMPA, ASJP, Dolgopolsky and others onto normalized **BIPA** graphemes with generative descriptive names | no | the standard; every Lexibank `Segments` column is BIPA |
| **PanPhon** | IPA → 24 articulatory features, weighted feature edit distance, fixed-width numeric vectors | yes, one | the default in NLP/ML phonology |
| **PHOIBLE** | 3,000+ language inventories with feature values | no | the typology data source |
| **LingPy** | sound classes (SCA, Dolgopolsky, ASJP), alignment, cognate detection | yes, via classes | the workhorse for CHL pipelines |
| **`merkmal`** | grapheme → versioned feature sets in 8 systems; configurable geometry-weighted dissimilarity; C99 ABI | yes, eight | not yet in the ecosystem |

`merkmal`'s functional twin is **PanPhon**, not CLTS. Its *data shape* is
CLTS's. Its ambitions are broader than either.

### What `merkmal` genuinely has that nothing else does

These are real and I want them stated before the criticism:

1. **Eight feature systems behind one interface**, including three that no other
   library exposes computationally (P-base SPE, JFH, UFTC). Nobody else lets you
   ask "does this result survive changing the feature theory?" That is a
   first-class scientific question and `merkmal` is the only tool that makes it
   a one-line change.
2. **An explicit, documented, swappable weighting geometry.** PanPhon's weights
   are a fixed list in a CSV. `merkmal` has a declared tree, a stated
   `1/depth` stipulation, a `theory_fidelity` field, and a `departures` list.
3. **A C99 core with a small ABI.** Portable to WebAssembly, R, Julia, Rust,
   Java. Every competitor is Python-only. For a *reference* library this matters
   more than it looks — it is the difference between a Python package and an
   infrastructure component.
4. **Intellectual honesty as an engineering practice.** The zero-distance
   baseline, the non-metric counterexample under test, the quarantined CoreCog
   prior, the `UNVERIFIED` provenance fields. I have reviewed a lot of resources
   in this space and this is the top decile. It is also, bluntly, the thing most
   likely to earn the field's trust.

### What CLTS has that `merkmal` does not, and needs

- **Multi-system grapheme input.** X-SAMPA, ASJP, Dolgopolsky in; BIPA out.
  Historical data arrives in all of these.
- **Tone, diphthongs, and clusters as first-class sounds**, not as synthesis
  edge cases.
- **Grapheme *diagnosis*.** `pyclts` tells you *why* a grapheme is invalid and
  what the nearest valid form is. `merkmal` returns
  `MK_ERR_UNKNOWN_GRAPHEME`. For transcription QC — a major use case — the
  diagnosis *is* the product.
- **Sound classes** as an API. `classes.tsv` exists in the repo, is not shipped,
  has no API, and its 20 classes are not a Dolgopolsky-style alphabet.

---

## 2. The coverage measurement

152 Lexibank datasets, 14,193,616 segment tokens (excluding the `+`, `_`, `#`
boundary markers), 7,396 distinct segment types.

| system | types accepted | tokens accepted |
| --- | ---: | ---: |
| `descriptive` | 89.5% | 96.12% |
| `phoible` | 79.2% | 95.81% |
| `pbase-*` (all four) | 73.7% | 95.63% |
| `broad`, `distinctive` | 73.4% | 95.57% |

The token figure looks reassuring and is misleading. **A form is only usable if
*every* token in it parses**, and the failures are not randomly distributed —
they cluster by language family. Hence: median 95.9% of forms fully parsed, but
26 datasets below 3%.

### What fails, by frequency (`broad`, 1,968 failing types)

| category | types | tokens | example |
| --- | ---: | ---: | --- |
| **standalone tone token** | 82 | **474,905** | `³³`, `⁵⁵`, `²¹`, `˥˩` |
| CLTS unknown/error markers | 3 | 33,288 | `<?>`, `<<->>` |
| diphthong as one token | ≈283 | 59,565 | `ai`, `au`, `ei`, `aːi` |
| slash convention `source/BIPA` | 561 | 39,219 | `⁶/⁵¹`, `ay/ai` |
| other | ≈1,039 | 22,471 | `gb`, `ai̯`, `ŋm`, `kk` |

Four separate observations follow.

**(a) Tone is the whole story.** 474,905 tokens in one category. BIPA's
convention — tone as a segment in its own right — is not an eccentricity; it is
the only convention that works for languages where tone is a morpheme, floats,
or associates to more than one syllable. `merkmal`'s model, where tone is a
diacritic property of a vowel, is a *representational* choice that is
incompatible with how the field's data is encoded. The already-good ordinal
Chao scale is the right *metric*; it is attached to the wrong *object*.

I tested the value of fixing this. A crude shim outside the library — parse
standalone tone tokens, score them on the ordinal Chao scale, treat tone-vs-
segment as maximally distant — moves full-benchmark column accuracy from 89.60%
to 90.06%. That is a modest gain *on BDPA*, which under-represents tonal data
relative to Lexibank; the Lexibank measurement above is the one that shows the
real size of the prize (26 datasets from unusable to usable).

**(b) The slash convention is half-handled, which is worse than not at all.**
`normalize()` correctly resolves `a/b → b`, but `is_segment()` does not document
that it applies the same rule, and `⁶/⁵¹` fails anyway because the *result* is a
tone token. A caller cannot tell which failures are convention failures and
which are real.

**(c) `broad` and `descriptive` are not operationally identical, and the README
says they are.** On real data they disagree on **1,188 segment types (78,762
tokens)** — every diphthong and cluster, which `descriptive` synthesizes and
`broad` rejects. The README's claim is true of the *distance* path (I found 0
disagreements across 19,900 shared pairs) and false of the *recognition* path.
That is a one-sentence correction, but it is currently a documented falsehood
about the difference between two of the eight public system names.

**(d) `<?>` is CLTS's "I could not convert this" marker.** 33,288 tokens.
Rejecting it is correct; silently failing is not. It should have its own status
code, because a caller wants to distinguish "your data has a known gap here"
from "this library does not support this sound".

---

## 3. The alignment benchmark, in full

BDPA, 750 gold MSAs → 2,250 gold pairwise alignments, shuffled, split 50/50 into
dev (gap-cost tuning) and test. Identical global Needleman–Wunsch for every
scorer; only the substitution cost differs. LingPy's SCA similarity scores are
mapped linearly to `[0,1]` distances.

**Full benchmark (2,250 pairs):**

| scorer | gap* | column acc | perfect |
| --- | ---: | ---: | ---: |
| LingPy SCA | 0.40 | **91.66%** | **88.18%** |
| `merkmal:distinctive` | 0.50 | 89.60% | 85.07% |
| `merkmal:distinctive` + tone shim | 0.50 | 90.06% | 85.69% |
| `merkmal:broad` | 0.60 | 88.96% | 84.36% |
| `merkmal:phoible` | 0.50 | 88.10% | 82.93% |
| `merkmal:pbase-hc` | 0.70 | 88.06% | 83.29% |
| identity | 0.80 | 82.89% | 73.51% |

**Fully parseable subset (1,448 pairs, 64.4%):**

| scorer | gap* | column acc | perfect |
| --- | ---: | ---: | ---: |
| LingPy SCA | 0.40 | 96.87% | 93.65% |
| `merkmal:distinctive` | 0.30 | 96.35% | 93.37% |
| `merkmal:broad` | 0.40 | 95.67% | 92.27% |
| identity | 0.80 | 87.35% | 78.87% |

**Unparseable subset (802 pairs):** SCA 83.53%, `broad` 79.42%, `distinctive`
78.82%, identity 74.76%.

**Caveats, stated plainly.** This isolates the substitution matrix and nothing
else. LingPy's production SCA aligner also uses prosodic strings, swap
detection, and secondary alignment, so this is *not* a claim that `merkmal`
matches LingPy-the-system — it is the stronger and more useful claim that
`merkmal`'s *segment distance* is as good a substitution cost as the field's
standard sound classes. I sampled 3 pairs per MSA; gold pairwise alignments were
derived by projecting MSA rows and dropping doubly-gapped columns.

**The one system that should worry you.** `broad` is significantly worse than
SCA on data it can read, while `distinctive` is not. `broad` is the name a new
user will pick first — it sounds like the safe default, and it is the one listed
first in the README. `distinctive` is the system that actually performs. That is
a defaults problem, not a modelling problem.

---

## 4. What people would want to do with this, and what stops them

Six workflows, in rough order of how many people want them.

### 4.1 Alignment and cognate detection — *blocked by tone, then by scope*

The largest single use. `merkmal` supplies the substitution cost and, per §3,
supplies a good one. But it stops at the segment: there is **no sequence-level
API at all**. No word distance, no alignment, no gap model. Every user will
write the same 40-line Needleman–Wunsch, choose a gap cost with no guidance
(the tuned optimum ranges 0.30–0.70 *across systems*, so the choice is not
obvious and is not documented), and get slightly different numbers.

For a *reference* library that is a real problem: reproducibility across papers
requires that the gap model be part of the specification, not part of each
user's scratch code.

### 4.2 Transcription QC and orthography profile development — *blocked by diagnosis*

Checking a new dataset's transcriptions is exactly what a fast C library with a
778-grapheme validated inventory should be best in the world at. What is missing
is the diagnosis: on rejection, a caller needs the longest valid prefix, the
offending codepoint, and the nearest valid grapheme. `MK_ERR_UNKNOWN_GRAPHEME`
does not support the workflow.

### 4.3 Feature vectors for ML — *blocked outright*

`get_features` returns a `frozenset` of label strings. There is **no numeric
vector export**. PanPhon's most-used function by a wide margin is
`word_to_vector_list`; it is the reason PanPhon is in every neural phonology
paper. Anyone wanting to embed phonemes, train a seq2seq reconstruction model,
or compute a phonological feature matrix must write the label→vector mapping
themselves, and will get it wrong for the valued systems (which return
`anterior=.` style strings mixing three-way values with missingness).

A fixed-width, documented, per-system numeric vector with an explicit
missing-value convention would be a small addition and probably the single
highest-adoption feature in this document.

### 4.4 Phonological typology — *out of scope, and that is a decision to revisit*

The README is careful and correct: these are segment-*type* catalogs with no
language indexing, no contrastive/allophonic status, no genealogy, no areal or
sampling weight. Given that, **`merkmal` cannot today do typology at all.**
Nothing in the API takes a language.

That is a defensible scope choice, but it sits awkwardly with the goal of being
the reference library for typology. The questions typologists actually ask —
inventory size and shape, feature economy, distance *between inventories*,
markedness hierarchies, areal signal, universals testing — all need a
language-indexed layer. PHOIBLE ships one, `merkmal` already bundles PHOIBLE's
segment table, and the join is the language-to-segment mapping the repo has
deliberately left out.

### 4.5 Sound change modelling — *absent, and correctly so for now*

Both prior reviews landed on this: the scorer anti-correlates with change
frequency, and the honest response is to say phonetic similarity and diachronic
probability are different quantities. The project made the right call in
declining to hand-tune. But "the reference library for computational historical
linguistics" that has *nothing* to say about sound change is a strange object.
The gap is real; the question is whether it is filled by fitted data
(§5) or by staying out of it.

### 4.6 Cross-theory robustness studies — *available now, and unadvertised*

The one thing `merkmal` can do today that nobody else can: rerun an analysis
under SPE, JFH, UFTC, PHOIBLE and Hayes-style features and report whether the
conclusion is stable. That is a publishable methodological contribution and it
is currently buried in a list of eight system names. It is the strongest
existing argument for the library's existence and deserves a worked example.

---

## 5. Residual linguistic defects

Smaller than the above, all confirmed on the current build.

**(a) `d(kp, ŋm) = 0.7255`.** `/kp/` resolves to a unit labio-velar stop;
`/ŋm/`, its nasal counterpart, is synthesized as a two-segment cluster. They
score further apart than most consonant–vowel pairs. In Yoruba, Ewe, Igbo and
much of the Niger-Congo family these are a natural class. Same object type,
different code path.

**(b) Affricates still break apart inside clusters.** `features("ntʃ")` returns
`n1-` nasal, `n2-` alveolar stop, `n3-` post-alveolar fricative — that is
*n + t + ʃ*, not *n + tʃ*, and it contradicts `system_segment_ipa("ntʃa")`,
which correctly yields `[n, tʃ, a]`. The cluster parser does not use the
tokenizer.

**(c) Doubled spelling is still further from the length mark than the plain
segment is.** `d(aa, aː) = 0.2651` against `d(a, aː) = 0.0564`;
`d(pp, pː) = 0.2943`. Doubled graphemes for length are standard in Uralic,
Austronesian and much African data and appear throughout Lexibank
(`kk`, `tt`, `pp`, `ll`, `mm`, `nn`, `ff` are all in the failure list above).

**(d) The valued systems still return `0.0` where they mean "no shared
dimension".** `mk_valued_distance` accumulating `total_weight = 0` and returning
a confident zero is the last live instance of the pattern both prior reviews
flagged. Returning coverage alongside the score remains listed as open, and it
is the correct fix. Until then, users of `phoible` in particular cannot
distinguish "identical" from "incomparable".

**(e) Provenance: the CLTS relationship.** `models/broad/inventory.tsv` is a
`GRAPHEME`/`NAME` table whose names (`unrounded open front vowel`) follow the
CLTS generative name grammar exactly, and `diacritics/ipa-clts.json` is named
for it. `review-response.md` states the relationship "is asserted nowhere and
should not be". For a library asking to be cited as reference infrastructure,
this is the most serious item in this document. If the categorical inventories
are CLTS-derived, that is a CC-BY obligation and a citation; if they are
independent, that is a remarkable convergence that needs saying. It cannot stay
unresolved.

---

## 6. What "reference library" would require

Ordered by how much each unblocks, not by effort.

1. **Tone as a first-class segment.** Accept standalone Chao digit runs and IPA
   tone letters as segments; give them a tone-only feature representation and a
   defined distance to non-tone segments. Unblocks 26 datasets and the entire
   tonal half of the field's open problems.
2. **BIPA as the declared input contract.** Diphthongs, clusters, `<?>`, the
   slash convention, and boundary markers get documented, tested behaviour in
   every system rather than in `descriptive` only. Add a coverage-regression
   test against a Lexibank sample so this cannot rot.
3. **Numeric feature vectors.** Fixed-width, per system, explicit missing-value
   convention. Highest adoption per line of code in this document.
4. **A sequence layer, or an explicit refusal.** If `merkmal` supplies the
   substitution cost but not the gap model, it is a component, not a reference.
   Either ship alignment with a specified gap model, or publish a canonical
   reference aligner as a separate documented artifact.
5. **Rejection diagnostics.** Longest valid prefix, offending codepoint, nearest
   valid grapheme. Turns rejection into a product.
6. **Resolve provenance**, especially CLTS. Nothing else on this list matters if
   the data cannot be cited.
7. **Decide on typology.** Either add the language-indexed layer and mean the
   word, or drop typology from the library's stated goal and let PHOIBLE own it.
8. **A worked cross-theory robustness example.** The unique capability, unadvertised.

Items 1–3 and 5 are additive and break nothing. Item 4 is a scope decision. Items
6–7 are decisions before they are work.

---

## What was measured, and how to reproduce

Every number here is reproducible from the repository. The throwaway scripts
that produced them have been replaced by two committed benchmarks; see
[`bench/README.md`](../bench/README.md).

| measurement | reproduce with |
| --- | --- |
| Lexibank coverage, per-dataset parse rates | `bench/bench_coverage.py` (CI-checked against recorded floors) |
| BDPA alignment benchmark and bootstrap CIs | `bench/bench_alignment.py --bdpa <checkout>` |
| SCA baseline | `lingpy` 2.6.13, `rcParams['sca']`, `token2class` |
| significance | 400-sample bootstrap over per-pair column accuracy differences, seed 7 |

The coverage figure is now a CI floor rather than a one-off measurement, because
it is the number that decides whether this library is usable on the field's
data, and a silent regression in it would be worse than the original defect.
