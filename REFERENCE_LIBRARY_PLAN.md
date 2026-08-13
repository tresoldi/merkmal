# Plan: from working library to reference library

Follows [`docs/reference-library-review.md`](docs/reference-library-review.md),
which measured the gap. This document records the decisions taken against that
review and stages the work.

The review's finding, restated because everything here follows from it: **on
alignment data `merkmal` can fully read, `distinctive` is statistically
indistinguishable from LingPy's SCA (96.35% vs 96.87% column accuracy, CI on the
difference [−0.87, +0.39]). Over the whole benchmark it loses significantly, and
every point of that gap is coverage.** The phonology is already competitive. The
work is to make it readable, citable, and usable on the data the field
publishes.

## Decisions

| # | Decision | Consequence |
| --- | --- | --- |
| D1 | Tone binds to the nucleus by default **and** bare tone tokens are a recognized segment kind | Unblocks 26 datasets without foreclosing tone-to-tone correspondence work |
| D2 | No aligner; `merkmal` stays segment-only | The docs must say plainly that it supplies the substitution cost and not the gap model |
| D3 | The categorical inventories are CLTS-derived | Licensing and citation must be corrected before any release |
| D4 | `broad` is deprecated; `distinctive` becomes the default | Removes a public name implying a choice that does not exist, and makes the default the system that performs |
| D5 | Numeric feature vectors ship in phase 1 | Opens the ML/neural-phonology audience currently conceded to PanPhon |
| D6 | A language-indexed typology layer is added | `merkmal` can then mean the word "typology" |
| D7 | A fitted scorer ships under its own `scorer_id` | Never mixed with the stipulated geometry |

---

## Phase 0 — Provenance and licensing (blocking) — **largely done, one decision open**

Status as of 2026-08-13. What was established and corrected is recorded inline
below; two items remain and both are the maintainer's call, not work.

- **Source established: CLTS v1.4.1**, tag `d0dbd4bd`. Verified by diffing the
  inventory against every tagged CLTS release: v1.4.1 matches 768 of 769
  graphemes and 766 of 769 byte-identical NAME strings, against 689/680 for
  v2.0.0 and later. Three rows diverge and are recorded in the manifests.
- **`classfeat` is *not* CLTS-derived** — this plan originally said four models,
  which was wrong. Its inventory is `GRAPHEME`/`CLASS`, a 110-symbol sound-class
  alphabet with hand-assigned classes, not CLTS names. Its MIT declaration
  stands. Three models were re-stamped, not four.
- **PHOIBLE established as CLDF `cldf-datasets/phoible` v2.0.1**
  (`f36deac7f80b`), from the maintainer's direct knowledge of having produced
  it. Content diff could not have settled this on its own — v2.0, v2.0.1 and 3.0
  match at 98.9%, 99.5% and 99.7% of graphemes — which is why it was left open
  until answered rather than inferred. The license was then checked against the
  pinned release rather than assumed: v2.0.1 declares no `dc:license` of its own
  (CC-BY-4.0 appears only from the 3.0 revision), so PHOIBLE 2.0's own
  CC-BY-SA-3.0 governs. The existing declaration was correct.
- **Found while verifying, not yet fixed:** PHOIBLE extraction is not
  self-consistent. Against v2.0.1, 3,729 cells where upstream says `0` (not
  applicable) were written `-` rather than `.`, 761 where upstream specifies a
  value were written `.`, and 697 where upstream gives a contour were resolved to
  a single `+`/`-`. 95.43% of cells are accounted for by the intended
  transformation. This is data work, not provenance work, and belongs in phase 1.
- **Deferred by decision:** merkmal 0.1.0, 0.1.1 and 0.2.0 are live on PyPI
  declaring `License: MIT`. The 0.2.0 wheel ships `merkmal/data/sounds.tsv`
  (778 rows, 100% CLTS graphemes, 99.1% byte-identical CLTS names) and CLTS's
  `transcriptions/upa.tsv`, so those releases misdeclare their license. They are
  being left as they are for now; the intent is to disclose the correction on the
  project webpage once that exists, rather than yank.
- **Still `UNVERIFIED`: the four `pbase-*` models** (release, commit, retrieval
  date) and PHOIBLE's retrieval date. P-base is distributed from a website
  rather than a versioned repository, so the diff method that settled CLTS does
  not apply; this needs maintainer records.
- **Open:** the NC question below.

### Original scope

**This blocks everything else, including any release.** Not because it is
urgent-feeling, but because a reference library that cannot be cited or
redistributed correctly is not a reference library, and because the current
state is a misdeclaration in a shipped artifact.

`models/{broad,descriptive,distinctive}/provenance.json` each declared
`license_spdx: MIT`. Per D3 they are CLTS-derived, so that was wrong. `NOTICE`
and the distribution's declared `MIT AND CC-BY-SA-3.0 AND CC-BY-NC-SA-4.0` were
wrong by omission. All are now corrected to `CC-BY-4.0` and
`MIT AND CC-BY-4.0 AND CC-BY-SA-3.0 AND CC-BY-NC-SA-4.0`. `dist/` is gitignored
and holds only stale local builds; the published PyPI releases are the real
exposure (see status above).

1. Establish the derivation empirically rather than from memory: diff the
   inventories against a pinned CLTS release and record the overlap, the
   transformation applied, and the CLTS version and commit. This also settles
   `diacritics/ipa-clts.json`.
2. Re-stamp the four manifests with the correct SPDX identifier, upstream
   release, commit, retrieval date, and the CLTS citation (List et al.).
3. Regenerate `NOTICE`; update the distribution license expression; yank or
   supersede the affected artifacts in `dist/`.
4. Replace the remaining `UNVERIFIED` upstream fields for PHOIBLE and P-base
   while the provenance work is open. The validator already surfaces them.

**Also decide, and it is a real adoption question:** the four `pbase-*` models
are `CC-BY-NC-SA-4.0`, which forbids commercial redistribution. Many
institutional and industrial users cannot take a dependency that bundles NC
data at all. Options are a core distribution without the NC models and an
opt-in data package, or accepting the restriction and stating it prominently.
This needs an answer before packaging is finalized.

**Acceptance.** `scripts/validate_models.py` reports zero `UNVERIFIED` fields;
`scripts/generate_notice.py --check` passes; every bundled artifact's license
is traceable to a pinned upstream release.

---

## Phase 1 — The BIPA input contract

The goal is a stated, tested guarantee: **if a token appears in a CLDF
`Segments` column, `merkmal` has defined behaviour for it.** Today that holds
for 73.4% of Lexibank segment types.

### 1a-0. What a tone segment is worth — decided 2026-08-13

Three distinct pairs were being conflated. Only the third was ever open:

| pair | status |
| --- | --- |
| `a` ~ `a¹³` — toneless vs tone-bearing vowel | exists, 0.1014 |
| `a¹³` ~ `a³³` — two tones on one vowel | exists, 0.0489 |
| `¹³` ~ `p` — a *bare* tone token vs a segment | does not exist; this is the decision |

> **These three decisions were sent for adversarial review before implementation
> and did not survive it. See "Review outcome" at the end of this section. They
> are kept here as the record of what was proposed and why, because the reasons
> the evidence failed are more useful than the proposal was.**

**D8 — a bare tone segment is separated from segmental units by a Root-level
tier leaf carried by every segment.** Autosegmentally motivated: tone occupies
its own tier, and a tier mismatch is a real phonological statement rather than a
fudge. It sits beside `vocoid` (weight 0.8), which is the existing precedent for
a Root-level major-class leaf.

The evidence, in the order it should be weighed:

1. **Gold alignments never put tone in a column with a segment.** Across BDPA's
   110 tone-bearing MSAs, a column containing a tone token contains: tone 2,295
   times, a gap 879 times, and an actual segment ~0 times (the 137 `*` and 41
   `.` are BDPA's own markers). 105 of those 110 MSAs have at least one toneless
   row, so tonal-versus-toneless is the common case, not an edge case. This is a
   categorical fact and it is the real justification.
2. **The geometry's own answer is too low.** A tone-only feature set already
   scores 0.50 against a vowel and 0.61 against a stop through `sound_distance`.
   An aligner prefers gapping both sides when the distance exceeds 2×gap, and
   the tuned gaps are 0.30–0.50, so the threshold is 0.60–1.00. At 0.50 the
   aligner matches tone to vowels, which gold data never does.
3. **That 0.50/0.61 spread is an artifact, not phonology.** It tracks the *other*
   segment's feature count — every 7-feature segment scores exactly 0.5000 — and
   is not even monotone in it (`t`, 10 features, scores 0.5925, below `p` at 8
   features and 0.6071). It looks principled and is not.
4. **Fitting bounds the weight; it does not pick it.** Sweeping the tone-segment
   distance over 330 BDPA pairs containing tone: 0.30 → 81.98%, 0.50 → 82.79%,
   **0.80 → 85.23%**, 1.00 → 85.47%, 2.00 → 84.53% (test column accuracy, gap
   re-tuned per value). Bootstrap: 0.80 vs 0.50 is +2.01% [−0.07, +4.50], *not*
   significant though every value ≥0.7 beat every value ≤0.5 on dev; 0.80 vs
   1.00 is −0.02% [−1.36, +1.44], indistinguishable. So the target is "high,
   inside roughly [0.7, 1.2]" and the choice within that band remains a
   stipulation — an evidence-bounded one, to be documented as such alongside the
   geometry's other stipulated weights, not described as fitted.

**D9 — the tier leaf applies to every segment, and the resulting re-scaling is
accepted.** Like `vocoid`, it enters the denominator of every distance and will
compress within-class contrasts across all eight systems. This was chosen over
confining it to tone comparisons, for uniformity. The failure when `vocoid` was
added was that the compression went *undocumented* and silently invalidated
calibrated thresholds; that must not repeat. Required alongside the change:
measure the compression, publish the before/after distribution, regenerate the
golden fixtures with the drift reported, and state plainly in `CHANGELOG.md`
that stored distances, alignments, clusters and thresholds must be recomputed.

**D10 — a toneless segment is closest to mid.** Today `d(a, a¹³)`, `d(a, a³³)`,
`d(a, a⁵⁵)` and `d(a, a¹¹)` are all exactly 0.1014: a toneless vowel is
equidistant from every tone. Instead an absent tone level compares as level 3 on
the ordinal scale, so a toneless form matches an unmarked/mid register most
cheaply, which is what tonogenesis work needs. `tone-present` stays privative, so
a toneless form is still not identical to a mid-level one.

The argument against, recorded because it is real: in CLDF corpora an unmarked
vowel usually means tone was not transcribed rather than that it is level 3, so
this reads missing data as a phonological value. Mitigation: the `ignore-tone`
weight preset already exists for callers working with untranscribed-tone data,
and the docs for this behaviour should point at it.

### Review outcome — D8, D9 and D10 rejected, 2026-08-13

An independent adversarial review reproduced the evidence and then re-ran it
with two defects removed. What follows is verified, not taken on report.

**The claim that carried D8 was false.** "105 of 110 tone-bearing alignments
have at least one toneless row" counted BDPA's `LOCAL` and `SWAPS` annotation
rows as languages. Filtering them: **0 of 110**. BDPA contains no tonal-versus-
toneless language pair at all, so it cannot measure the situation D8 exists to
price. The co-occurrence counts themselves reproduce exactly (tone 2,295, gap
879, segment 0) but are partly definitional — BDPA's annotators tokenised tone
separately — and come from 110 alignments that are 90 Bai and 20 Sinitic.

**The harness had that same defect, and it cost a headline.** `read_msa` read
annotation rows as doculects: 8.1% of all pairs were sequences of `*` and `.`.
Corrected, `distinctive` is **−0.65% [−1.18, −0.14] against SCA on readable
pairs — significant**, where the contaminated run showed −0.25% [−0.87, +0.39],
not significant. The parity claim is withdrawn. Fixed in `bench_alignment.py`;
`bench/alignment_baseline.txt` re-recorded.

**The sweep leaked and, once fixed, saturates.** It split pairs rather than
alignments, so up to three pairs from one wordlist straddled dev and test —
the leak D7 declares non-negotiable. Split at alignment boundaries, every value
from T = 0.70 to T = 2.00 gives *byte-identical* results, and T = 0.70 versus
the geometry's own 0.50 is +0.71% [−0.20, +1.54], **not significant**. The
benchmark identifies a rule — never match tone to a segment — not a weight, and
cannot distinguish any cost in the saturated region from declaring the two
incomparable.

**D9's premise was wrong about scope.** A geometry leaf reaches `broad` and
`descriptive` only. `distinctive` scores through its own `scalar_dimensions` and
never reads geometry leaves; the five valued systems reject tone-bearing
graphemes outright. "All eight systems" was wrong in both directions. The review
further measured the leaf as *costing* −0.33% [−0.64, −0.03] column accuracy,
and as reordering rather than rescaling — 1.67% of pairwise closer-than
comparisons flip, which no published rescale factor can repair.

**D10 was a third, unrecorded compression.** Implemented as an ordinal
`default_level`, the three tone scales fire on every pair, adding 1.2 to every
denominator: mean distance −17.5%, `d(p,b)` −24.8%. It also weakens what it
claims to fix, moving `d(a, a³³)` from 0.1079 to 0.0857. And the corpora already
have the notation it wants to model — Chao neutral tone `⁰`, which is 8.3% of
tone tokens in `beidasinitic` (its single largest blocking token) and which
merkmal rejects outright. `ignore-tone` does not mitigate it either: zeroing
`Tonal` leaves a bare tone as a featureless segment still costing 0.554 against
`p`, because deleting a token is a sequence operation the library does not own.

**What replaces them.** Tier becomes a property of the segment record rather
than a scoring dimension — alongside the existing unscored `metadata_features` —
and cross-tier comparison is answered through the comparability channel item 1c
already commits to building for `total_weight == 0`. The cost policy becomes
versioned data in the geometry file rather than a tree edit, which is what makes
it swappable for the later evidence-derived and preference-derived weighting
schemes. No existing distance moves, no fixtures regenerate, no thresholds are
invalidated.

**And the coverage case never needed any of this.** Recognition alone — bare
tone tokens, `⁰`, the boundary markers, the slash convention, and the item 1b
diphthong parity — takes the 26 blocked datasets from 0.1% to ~93% of forms
parsed under `descriptive`. Not one point of that requires a tone-to-segment
number.

### 1a. Tone (D1) — recognition landed 2026-08-13, comparison still open

**Done.** Bare Chao runs and IPA tone letters resolve as segments; `⁰` is
recognized as neutral tone with its own privative feature rather than folded
into a pitch level; malformed runs report a parse error rather than an unknown
grapheme; valued systems refuse. Coverage went from 26 datasets below 3% of
forms parsed to 1, and token coverage from 95.6% to 99.2% (`descriptive`
99.7%). The remaining dataset has no tone in it.

The contrast audit now sweeps bare tone forms, because they are the whole
recognition space for the tonal dimensions and an inventory-derived sweep never
saw them. That gap surfaced immediately: adding the `tone_neutral` leaf made the
audit fail with one unreachable dimension per categorical system, which is the
guard doing its job.

**Still open — what a tone costs against a segment.** Tone tokens carry
`tonal-autosegment` as a declared unscored `metadata_feature`, so today they
compare through the geometry like anything else and land around 0.50 against a
vowel and 0.61 against a stop. Those are placeholder numbers, and §"Review
outcome" above says why they are the wrong ones. The replacement is the
comparability channel item 1c already owes, plus a versioned `tier_policy` block
so the cost is swappable data rather than a tree edit. Until that lands, callers
comparing a tone with a segment are getting a number nobody defends.

### 1a-1. Tone, original scope (D1)

- `mk_merge_tone_digits` takes a *token list*, not a string. The current
  string form mangles the field's actual input: `'t o ³³'` →
  `['t', ' ', 'o³³', ' ']`, and splits `tʰ` into `t` + `ʰ`. Keep the string
  form for compatibility; add the token-list form and make it the documented
  path.
- Bare Chao digit runs and IPA tone letters become a recognized segment kind,
  scored on the existing ordinal Chao scale among themselves, with a **declared**
  distance to non-tone segments. Declared, not fabricated — the number goes in
  the geometry docs with its rationale, the way the stipulated weights already do.
- Binding stays reversible; `split_tone` is already its inverse. Add a property
  test that binding then splitting round-trips for every tone-bearing form.
- Fix `segment_ipa_merged('to⁶/⁵¹')` → `['t', 'o⁶⁵¹', '/']`. It merges across
  the slash into a tone that does not exist and leaves a stray delimiter.

### 1b-0. Cluster parity — done 2026-08-13, and it unblocks D4

Diphthongs, clusters and complex segments were gated on a `strcmp` of the
system's *name* against `"descriptive"`. Nothing in the synthesis was ever
descriptive-specific, and opening the gate to any categorical system caused
**zero golden-fixture drift** — confirmation it was gating recognition, not
behaviour.

`distinctive` goes from 78.5% to **94.5%** of Lexibank segment types, and the
median dataset now parses **100%** of its forms. Three datasets remain below 90%.

**This was a precondition for D4, not an optional extra.** Making `distinctive`
the default while it rejected 1,188 types that `descriptive` accepted would have
shipped a default that was the least able to read the field's data. That is now
resolved and D4 can land.

**Parity with SCA returns, on a sound basis.** Readable subset 92.9% of BDPA
(from 64.4%); `distinctive` 96.16% against SCA's 96.72%, difference −0.39%
[−0.95, +0.15], **not significant**. The retracted claim rested on 64.4% of the
benchmark with annotation rows contaminating it; this rests on nearly all of it,
clean. Nothing about scoring changed — every point came from reading more data.

**An old finding closed.** Cluster parses return 61 labels no dimension reads —
`n1-`/`n2-`/`n3-` component copies, `move-` trajectories, and the unit labels.
The first independent review raised this and it was never resolved. They are now
declared unscored in the geometry, by prefix for the open-ended families, and
the audit sweeps cluster spellings drawn from Lexibank by token frequency.

**A fragility worth remembering.** The valued systems' collapse counts are a
property of *which* 700 forms the cap sampled. Growing the sweep reselects the
sample and moves the counts with nothing in the library having changed — `ai`
and `au` are P-base inventory rows, which is how a categorical-only change moved
`pbase-jfh` from 5,722 to 6,067. A rise there is evidence of regression only
when the swept population is unchanged.

### 1b. The rest of the contract

- **Diphthongs and clusters in every system**, not `descriptive` only. This is
  what D4 turns into work: 1,188 segment types currently recognized by
  `descriptive` and rejected by `broad`/`distinctive`.
- **The slash convention** (`source/BIPA`) becomes part of the documented
  `is_segment` contract, not an undocumented side effect of `normalize()`.
- **`<?>` and `<<->>`** get their own status code. A caller must be able to
  distinguish "your data has a known gap here" (33,288 tokens in Lexibank) from
  "this library does not support this sound".
- **Boundary markers** `+`, `_`, `#` get documented behaviour.

### 1c. Residual defects from the review

- `d(kp, ŋm) = 0.7255`. `/kp/` is a unit, `/ŋm/` is synthesized as a cluster.
  Same object type, different code path, and a natural class across Niger-Congo.
- `features("ntʃ")` returns *n + t + ʃ*, contradicting `system_segment_ipa`,
  which correctly gives `[n, tʃ, a]`. Route the cluster parser through the
  tokenizer.
- `d(aa, aː) = 0.2651` against `d(a, aː) = 0.0564`. Doubled spelling for length
  is standard in Uralic, Austronesian and much African data.
- Valued systems return `0.0` when `total_weight == 0`. Return coverage
  alongside the score so "identical" and "incomparable" stop being the same
  number. This is the last live instance of a pattern both prior reviews flagged.

### 1d. Numeric feature vectors (D5)

Fixed-width per system, documented width and column order, explicit
missing-value convention for the valued systems' `.` cells. One call for a
segment, one for a token list.

**Acceptance — the harness is built, the target is not yet met.**
`bench/bench_coverage.py --check` runs in CI against a committed aggregate
segment table and fails below recorded per-system floors; `bench/bench_alignment.py`
reproduces the SCA comparison. Both baselines are committed, so the review's
numbers are now reproducible from the repository rather than from a scratch
directory.

Floors as recorded today (`bench/corpus/coverage-floors.json`): `descriptive`
89.45% of types, the rest 73.4–79.2%. `bench/coverage_baseline.txt` records 26
of 152 datasets below 3% of forms parsed.

Target for this phase: ≥99% of segment types, and all 26 currently-blocked
datasets parsing end to end. Raise the floors as the work lands, so a gain
cannot be silently lost.

---

## Phase 2 — Defaults, deprecation, and diagnosis

### 2a. `broad` (D4)

Deprecate `broad`; `distinctive` becomes the default. `broad` is the name a new
user picks first, it is operationally identical to `descriptive` in the distance
path, it differs from it in the recognition path while the README claims
otherwise, and it is the one system significantly worse than SCA on data it can
read (−0.93%, CI [−1.69, −0.14]). Correct the README's "operationally
identical" claim in the same change: it is true of distances (0 disagreements
across 19,900 sampled pairs) and false of recognition.

### 2b. Rejection diagnostics

On rejection, return the longest valid prefix, the offending codepoint, and the
nearest valid grapheme. Transcription QC is a workflow a fast C library with a
validated inventory should be best in the world at, and there the diagnosis *is*
the product. `MK_ERR_UNKNOWN_GRAPHEME` does not support it.

### 2c. Say what the library is not (D2)

State in the README that `merkmal` supplies the substitution cost and not the
gap model, and point at LingPy for the sequence layer. Include the measured gap
costs (0.30–0.70 depending on system) so users are not guessing.

### 2d. Advertise the unique capability

A worked example of a cross-theory robustness check — the same analysis under
SPE, JFH, UFTC, PHOIBLE and Hayes-style features, reporting whether the
conclusion is stable. Nothing else in the field can do this and it is currently
one line in a list of eight system names.

---

## Phase 3 — The typology layer (D6)

Nothing in the current API takes a language, so the library cannot do typology
at all today. The join is PHOIBLE's language-to-segment mapping, which the repo
has deliberately left out.

Scope to settle when the phase opens: inventory size and shape, feature economy,
inventory-to-inventory distance, markedness and implicational hierarchies, areal
and genealogical signal. Sampling weight and genealogy are the hard part and are
exactly what the README's existing disclaimer is careful about — that care must
survive the addition, not be dropped because there is now a language column.

Open question deferred to this phase: core library or companion package. A
companion keeps sampling-weight and genealogy concerns out of the C core and
lets the typology data carry its own licensing.

---

## Phase 4 — The fitted scorer (D7)

Both prior reviews concluded a fitted pair-cost table is the only real answer to
the change-frequency problem. The 170 local Lexibank clones with cognate
annotations are the training signal.

Non-negotiable design constraints, all learned from `corecog-derived.json`:

- Ships under its own `scorer_id` and `scorer_version`, never mixed with the
  stipulated geometry and never the default without a separate decision.
- **Evaluation splits by whole family**, not by word pair. Splitting by pair
  leaks, and the resulting number would be meaningless.
- Per-cognate-set and per-family weighting, so densely sampled families do not
  dominate.
- Calibration reported alongside accuracy.
- Not fitted on alignments produced with the dissimilarity being calibrated.
  That circularity is point 6 of the CoreCog quarantine and it is easy to
  reintroduce without noticing.

---

## Out of scope, stated so it stays decided

- **An aligner** (D2). Component, not framework.
- **Sound change modelling.** The scorer anti-correlates with change frequency;
  the honest position — that phonetic similarity and diachronic probability are
  different quantities — stands. Phase 4 is the only route in, and it does not
  claim to model change.
- **Hand-tuning the geometry so that historically frequent changes score close.**
  Already declined, for good reasons, in `docs/review-response.md`.

---

## Sequencing

Phase 0 blocks release. Phases 1 and 2 are additive and can proceed in parallel
with it. Phase 1 is where the adoption is: it converts a library that fails on
the tonal half of the world's languages into one that does not. Phases 3 and 4
are research programmes and should not be started until the coverage regression
metric from phase 1 is green and holding.
