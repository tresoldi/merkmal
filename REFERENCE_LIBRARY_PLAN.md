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

### 1a. Tone (D1)

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

**Acceptance.** A checked-in regression metric — Lexibank coverage over a pinned
dataset sample — with a floor that CI enforces. The review recommends this
specifically: it is the number that decides whether the library is usable on the
field's data, and it should not be recoverable by accident or lost by accident.
Target: ≥99% of segment types and 100% of the 26 currently-blocked datasets
parsing end to end.

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
