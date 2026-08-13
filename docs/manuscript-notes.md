# Notes toward a manuscript

Findings from building and auditing `merkmal`, sorted by how much they say to
the field rather than to the codebase. Every number here is reproducible from
this repository; the command is given with each.

Read the **Status** line on each finding before using it. Some are solid enough
to lead a paper, some are corroborating detail, and two are cautionary notes
that other people's tooling needs more than a journal does.

---

## 1. A third of segment-similarity claims depend on which feature theory answers

**Status: strongest result here. Reproducible, large, and about the field's
methods rather than about this library.**

Over every claim of the form *A is closer to B than to C* that a 41-segment set
can state, and on which at least six of seven feature systems have an opinion:

| | |
| --- | ---: |
| claims | 29,179 |
| unanimous | 18,261 (62.6%) |
| **split** | **10,918 (37.4%)** |

The seven systems are Hayes-style distinctive features, a Clements–Hume-inspired
descriptive geometry, PHOIBLE's binary table, and four P-base sets including
Jakobson–Fant–Halle's *acoustic* features. Contested cases are not exotic:
`d(p,t) < d(p,k)` splits 3–3 — whether a labial is nearer a coronal or a velar
depends on who is asked.

```sh
bench/cross_theory.py
```

**Why it matters.** Claims of this shape are made constantly and in passing, in
alignment scoring, in cognate search heuristics, in arguments about which
correspondence is more natural. A third of them are partly statements about the
feature inventory rather than about the sounds. That is not a defect in any of
the theories — SPE, JFH and PHOIBLE disagree about what a segment *is*, and are
entitled to — but it means a result resting on one of them inherits that choice.

**The obvious rebuttal, and the answer.** *You picked hard cases.* No: the sweep
is exhaustive over the segment set, not curated. This matters because the first
version of the experiment used fifteen hand-picked claims and all fifteen came
back unanimous — which demonstrated only that the person picking knew what he
expected. That failure is worth reporting in the paper; it is the reason the
protocol is exhaustive.

**What would strengthen it.** Repeat over a larger segment set and report
whether the rate is stable. Break the rate down by claim type — are height
orderings more stable than place orderings? Establish whether the contested
claims cluster on particular systems (is one theory the outlier, or is the
disagreement distributed?). That last question is the most interesting and is
not answered here.

**Candidate framing.** A methodological note for a computational-linguistics or
phonology venue: *feature-based segment similarity is theory-relative, and the
field does not report which theory it used.*

---

## 2. Tone and segments are not comparable on a shared scale

**Status: solid, with a clean representational argument and two independent
lines of evidence.**

CLTS/BIPA writes tone as its own segment (`t o ³³`), which is the form CLDF
wordlists are published in. Any library that scores a tone against a consonant
must decide what that costs.

**Gold alignments never do it.** Across BDPA's 110 tone-bearing multiple
alignments, a column containing a tone token contains:

| | |
| --- | ---: |
| tone | 2,295 |
| a gap | 879 |
| an actual segment | **0** |

**And the accuracy surface is flat wherever the cost is high enough.** Sweeping
the tone-to-segment cost, with evaluation split at alignment boundaries: every
value from 0.70 upward produces *byte-identical* alignments. The data cannot
distinguish a finite cost in that region from refusing to compare at all.

```sh
bench/sweep_tone_distance.py ~/lexibank_clone/bdpa
```

**A trap worth documenting.** Scoring a tone through a feature geometry returns
a number that looks principled and is not. Every 7-feature segment scored
*exactly* 0.5000 against a tone; 8-feature segments 0.6071. The value is a
function of how many features the **other** segment has, not a statement about
tone. It is also below the threshold at which an aligner stops matching tone to
segments, so it produces alignments gold data never contains.

**The autosegmental argument, and its limit.** Invoking tiers to justify a
*number* on a shared scale misrepresents the theory: what autosegmental
phonology defines between a tone and its bearer is an association line, not a
magnitude, and the tier exists to license many-to-one association, floating
tones and stability under deletion — none of which a flat feature captures.
Invoking it to justify *incomparability* is defensible, because a plane on which
comparison is undefined is much closer to the claim the theory makes.

**Prior art agrees, mostly by omission.** Kondrak's ALINE has no tone feature.
PanPhon says in print that tone is where segmental representations lose, and its
weighted metrics score `˥` and `˩` as identical. LingPy's SCA uses a flat
prohibition plus a non-crossing constraint that makes tone–segment alignment
structurally impossible at any cost. No system I could find assigns a graded
tone-to-segment cost.

**Caveat that must appear.** BDPA's 110 tone-bearing alignments are 90 Bai and
20 Sinitic, and contain **no** tonal-versus-toneless language pair at all — every
apparently toneless row is an annotation row. So BDPA can evidence
tone-against-tone comparison and cannot evidence tone-against-nothing. The
Lexibank corpora are full of the latter.

---

## 3. Coverage is a hidden failure mode, and token rates conceal it

**Status: solid, and immediately useful to anyone building tooling on CLDF.**

Measured over 152 Lexibank datasets (14,193,616 segment tokens, 7,396 types),
this library began at **95.57% token coverage** — a figure that reads as fine.

It was not fine. A form is usable only if *every* token in it parses, and
failures cluster by language family:

| | before | after |
| --- | ---: | ---: |
| tokens read | 95.57% | 99.71% |
| segment types read | 73.4% | 94.7% |
| median dataset, forms fully parsed | 95.9% | 100% |
| datasets below 3% of forms parsed | **26** | 1 |

The 26 unusable datasets were Sinitic, Hmong-Mien, Bai, Tai-Kadai,
Lolo-Burmese, Karen and Tujia — the tonal families, blocked because tone is
written as its own segment. A 4.4% token gap was concealing the unusability of
the tonal half of the world's languages.

```sh
bench/bench_coverage.py --check
```

**The methodological point.** Report **form-level parse rates per dataset**, not
corpus-wide token coverage. The two differ by an amount that depends entirely on
whether failures are independent — and in phonological data they never are.

---

## 4. A feature geometry reaches sound-class parity, and coverage decides the rest

**Status: solid, but only after a correction that is itself worth reporting.**

On BDPA gold pairwise alignments, identical Needleman–Wunsch for every scorer,
gap tuned per scorer on a held-out half, over the 93.2% of pairs the library can
fully read:

| scorer | column accuracy | perfect |
| --- | ---: | ---: |
| LingPy SCA | 96.69% | 94.66% |
| feature geometry (`distinctive`) | 96.18% | 93.99% |
| identity baseline | 86.84% | 78.84% |

Difference from SCA: **−0.37%, 95% CI [−0.93, +0.10] — not significant.**

**The correction.** An earlier version of this claim was published in
`docs/reference-library-review.md` and **retracted**. It rested on 64.4% of the
benchmark and was measured with BDPA's annotation rows counted as languages. The
corrected figure rests on 93.2% of it with the contamination removed. The
retraction is in the repository's history rather than quietly overwritten, and a
manuscript should say which measurement it is reporting and why.

**The substantive point.** Every point of improvement between the first
measurement and this one came from *reading more data*, not from changing how
anything scores. Coverage was worth several times more than modelling.

---

## 5. Fitted pair costs do not beat a stipulated geometry on available data

**Status: a clean negative result, and the protocol is the contribution.**

Leave-one-family-out over BDPA's human-annotated alignments; segment-pair costs
from pointwise mutual information shrunk toward the geometry by observation
count; gap tuned on training folds only:

| held out | geometry | fitted | delta |
| --- | ---: | ---: | ---: |
| Indo-European | 96.17% | 96.03% | −0.14 |
| Japonic | 86.89% | 87.38% | +0.49 |
| Quechuan | 100.00% | 100.00% | 0.00 |
| Sino-Tibetan | 90.83% | 89.36% | −1.47 |
| Uralic | 93.12% | 92.81% | −0.31 |

Mean −0.28 points, 95% interval **[−0.92, +0.35]**, 1 of 5 folds improved. **No
detectable difference**, not a win for either side.

```sh
bench/fit_pair_costs.py --bdpa ~/lexibank_clone/bdpa
```

**Why the protocol is the point.** Splitting by word pair instead of by family
leaks — pairs from one alignment share a wordlist and its doculects. Fitting to
alignments the library itself produced would calibrate it against its own
biases. Both mistakes make a fitted table look good, and both are easy to make
without noticing; this project has a quarantined artefact that made the second
one.

**The binding limit is the corpus**, not the method: BDPA is five families and
65% Indo-European. Enough to find a large effect, not to resolve a small one.
Tuning the smoothing until a fold turns positive would be fitting the protocol
rather than the data.

**Calibration moves independently of accuracy** and is worth reporting
separately: on Japonic the fitted costs were substantially better *scaled*
(0.079 → 0.038) while barely better *ranked*. A scorer can order pairs well and
still mean nothing by its numbers.

**What would settle it.** Alignments over many more families — Lexibank cognate
sets aligned by something that is not the scorer being calibrated.

---

## 6. Feature economy reproduces Clements on PHOIBLE

**Status: replication, useful as corroboration rather than as a headline.**

Inventory size over the number of features any of its segments takes a value on,
computed over PHOIBLE's 3,020 doculects: Hawaiian at 13 segments is the least
economical (0.36), Hindi at 94 the most (2.54). Larger inventories reuse
features rather than adding them, which is Clements' observation.

Note the definition: **per feature, not per (feature, value) pair.** Counting
pairs roughly halves the figure and is not the quantity Clements defines — I
made that error first. The absolute value depends on the feature system, so it
compares inventories within one system and not across systems.

---

## 7. Two cautionary notes other people's pipelines need

**Status: not a paper, but the community should know. Worth a note, a blog post,
or an appendix.**

**BDPA's annotation rows look like languages.** Each alignment block may end with
`LOCAL` or `SWAPS` rows that are tab-separated and exactly as wide as a language
row, but contain BDPA's own markup (`*`, `.`) rather than transcription. Anything
reading these files by shape ingests them as doculects. Here that was 568 `LOCAL`
and 66 `SWAPS` rows, contaminating 8.1% of sampled pairs and inflating every
accuracy figure by roughly four points — enough to turn a significant result
non-significant and back. **Filter by row name before use.**

**PHOIBLE's `0` does not mean minus.** In the CLDF `parameters.csv`, `0` means
the feature does not apply to that segment, `-` means it applies and is absent,
and a comma-separated value such as `+,-` is a per-phase contour. Conflating `0`
with `-` manufactures agreement between segments on features neither one has,
and shrinks distances systematically. In this repository that error affected
3,729 cells; correcting it raised the mean pairwise distance over a 24,090-pair
sample from 0.2208 to 0.2420. `N` appears on all 37 columns of two segments and
means there is no feature vector at all.

---

## 8. PHOIBLE's sample composition, quantified

**Status: background for anything typological, and a caveat other papers should
be carrying.**

| | |
| --- | ---: |
| inventories | 3,020 |
| languages | 2,186 |
| languages with more than one doculect | 531 (up to 11) |
| Atlantic-Congo | 17.0% of inventories |
| Pama-Nyungan | 10.7% |
| Africa | 29.3% |
| Papunesia | 7.4% |

Two families are 28% of the sample and 834 inventories are additional doculects
of a language already present. That /m/ occurs in 96% of PHOIBLE's inventories
is a real fact and is **not** the claim that /m/ occurs in 96% of the world's
languages. The difference is not a technicality at this composition.

Nothing here proposes a weighting scheme. Choosing one means choosing a
genealogy and a level and defending both, which is a research decision rather
than a default.

---

## 9. A recurring defect shape, worth a methods paragraph

**Status: observation, not a result. But it recurred often enough to be worth
saying.**

Several of the worst defects found were not wrong code in one place. They were
**two layers each behaving sensibly whose composition was wrong**:

- A normalization table rewrote a grapheme into another spelling; the inventory
  had the original as its own row. Each was right; applying the rewrite before
  the lookup merged two distinct segments.
- A geometry declared a feature's weight; a second scoring path derived weights
  by depth and never read the declaration. Both were coherent; they disagreed by
  25% on the major-class dimension, and the documentation described neither.
- A feature-set scorer and a segment scorer agreed under one default system and
  silently diverged under another.

The guards that caught these were the ones that compared **two representations
of the same fact** — a declared weight against an emitted weight, a label
against the dimension that should score it, a collapse against the notation that
should explain it. Guards that checked one artifact against itself passed
throughout.

---

## Reproducing everything

```sh
bench/bench_coverage.py --check                     # §3
bench/bench_alignment.py --bdpa <checkout>          # §4, §7
bench/cross_theory.py                               # §1
bench/sweep_tone_distance.py <bdpa>                 # §2
bench/fit_pair_costs.py --bdpa <checkout>           # §5
python -c "import merkmal_typology as t; print(t.sample_composition().describe())"   # §6, §8
scripts/rebuild_phoible_inventory.py <parameters.csv> --check                        # §7
```

Corpora: Lexibank CLDF datasets, and BDPA
(`lexibank/bdpa`). PHOIBLE is pinned to `cldf-datasets/phoible` v2.0.1
(`f36deac7f80b`); the segment inventories derive from CLTS v1.4.1 (`d0dbd4bd`).

## Gaps to close before submission

1. **§1 needs the by-system breakdown.** Is disagreement distributed, or is one
   feature set the outlier? Currently unanswered and it is the first question a
   reviewer will ask.
2. **§2 needs a tonal-versus-toneless corpus.** BDPA has none. The claim about
   what tone should cost against *nothing* rests on the co-occurrence argument
   alone.
3. **§5 needs more families.** Five, at 65% Indo-European, cannot resolve the
   effect either way.
4. **§1 and §4 use the same seven systems**, four of which are P-base variants
   sharing an inventory. Independence is weaker than the system count suggests
   and should be stated.
5. Confirm the PanPhon, ALINE and SCA claims in §2 against current releases
   before citing; they were verified against the versions installed here.
