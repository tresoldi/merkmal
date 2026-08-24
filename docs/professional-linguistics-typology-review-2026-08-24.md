# Professional historical-linguistics and typology review

**Review date:** 2026-08-24  
**Scope:** `merkmal`, with integration implications for sibling packages
`cognator` and `regulae`.

## Overall assessment

Merkmal has an unusually strong scholarly posture for a phonological software
library. In particular, it distinguishes experimental segment dissimilarity
from historical probability, exposes comparison coverage, documents
non-metric behaviour, retains a language-indexed typology layer outside the
core, and quarantines an invalid historical-direction artefact rather than
repairing its numbers into a misleading claim.

The central outstanding work is not another ad-hoc reweighting of the feature
geometry. It is reproducibility of analytical choices, explicit treatment of
ambiguous transcription, and a data-bearing historical layer if historical
claims are ever desired.

## Priorities

### P0 — establish provenance and redistribution evidence

The P-base models still state that their upstream release, extraction,
retrieval date, and source revision are unverified. The typology data also
claims relicensing permission whose grantor, date, and documentary evidence
are unverified. These are acceptable warnings in an exploratory repository,
but should be resolved before a data release or publication that presents the
models as reproducible scholarly resources.

Recommended action:

- preserve the exact acquired upstream artefacts or immutable references;
- document the extraction program and its input checksums;
- record the licensing communication or distribute under the demonstrably
  applicable upstream terms; and
- promote unresolved provenance from a warning to a release gate for
  data-bearing releases.

Relevant files: `models/pbase-*/provenance.json`,
`typology/data/provenance.json`, and `docs/release-policy.md`.

### P0 — expose a public semantic fingerprint

Neither a library version nor a system name fully identifies an analysis. A
result can change when the inventory, geometry, diacritic resolver, tone
grammar, scorer, or weighting preset changes without a C ABI change. Cognator
already demonstrates the risk: its calibration constants are on Merkmal's
distance scale and a feature-inventory change altered clustering behaviour.

Add a public C/Python API returning a generated, stable fingerprint for the
complete semantic configuration, for example:

```text
model-id + model-data hash + geometry-id/version + scorer-id/version
+ resolver-policy-version + tone-policy-version + weight-preset
```

Downstream exports should record it, and tools should reject comparison of
results with incompatible fingerprints by default. Regulae currently records
the feature-system name and Merkmal package version, which is a useful start
but not enough to reconstruct a conditioning vocabulary or a distance scale.

### Deferred — segmentation policy

The separate orthographic and system-aware tokenizers are a sound design. But
longest-match remains an analysis rather than neutral preprocessing for
untied affricates, prenasalized/coarticulated stops, vowel sequences, and
corpus-specific boundary conventions.

This work is deferred. When resumed, add selectable policies for these
phenomena, diagnostics that expose plausible alternative tokenizations, and a
policy identifier that downstream packages must store. For historical corpora,
explicit user-supplied segmentation should remain the preferred, lossless input
form.

### Deferred — structured tone representation

The current Chao support correctly distinguishes tonal from toneless material,
uses ordered pitch levels, accepts IPA tone letters, and rejects malformed
long contours atomically. Flat segment features nevertheless cannot preserve
association, floating tones, register systems, tone sandhi, or the distinction
between a pitch transcription and a language-specific tone-category label.

This work is deferred. When resumed, add an optional structured `Tone`
representation retaining original spelling, register/contour, association
domain, and declared interpretation. Models should declare `tone_support =
none | categorical | contour`. Historical sound-law tooling should treat a tone
category with no asserted phonetic value as a category, not as a Chao pitch
level.

### P1 — make coverage travel with typological comparison results

`mk_system_segment_distance_ex` correctly returns coverage and a
comparability status. The typology companion's `inventory_distance`, however,
filters unreadable segments and returns only a float. This can conceal whether
an apparent inventory difference is phonological or an artefact of model and
transcription coverage.

Replace bare scalar returns with an `InventoryComparison` record containing:

- the score and system fingerprint;
- readable and unreadable segments on both sides;
- distribution of pairwise comparison coverage and comparability statuses;
- any cross-tier comparisons; and
- the selected segmentation policy.

The same principle applies to `feature_economy`: report how much of an
inventory contributed before presenting it as a property of that inventory.

### Deferred — typological sampling designs

The typology companion correctly labels PHOIBLE aggregates as aggregates over
PHOIBLE, not the world's languages. This work is deferred. When resumed, it
should offer reproducible sampling constructors, without selecting one
silently:

- one inventory per Glottocode;
- family-balanced samples at a stated Glottolog classification level;
- macroarea × family-stratified samples; and
- spatially thinned samples using stated coordinates and radius.

Every aggregate should retain the selected inventory IDs, weighting function,
classification release, coordinate source, and sample composition.

### Completed — retire the duplicate `broad` system

`broad` was retired in this branch. It was a duplicate of `descriptive` and
created a false analytic choice without preserving a distinct analysis.

## Historical-linguistic boundary

Merkmal should remain non-directional in its core. A defensible historical
layer requires observations with direction evidence rather than merely paired
daughter forms. At minimum, a future dataset should record family/branch,
ancestor or temporal ordering, source and confidence, cognate-set identity,
segmental and prosodic environment, morphology where relevant, and chronology
or time depth. Evaluation must split by family (and ideally area) rather than
random word pair.

Until such data exist, recurrent correspondence models may be useful for
alignment and candidate generation but must not be called estimates of sound
change direction or naturalness. The quarantine of
`typologies/corecog-derived.json` is methodologically correct.

## Integration recommendations

### Cognator

Cognator's vendored Merkmal pin and recalibration protocol are exemplary.
Extend the pin record and all benchmark/detection outputs with Merkmal's
semantic fingerprint and segmentation policy. Promotion should require
coverage reports stratified by family and transcription convention, rather
than an aggregate accuracy alone.

### Regulae

Regulae's induced natural-class and conditioning vocabulary depend directly on
the features the selected Merkmal system exposes. Its JSON provenance should
therefore record the exact model/geometry/resolver fingerprint, not only the
system name and package version. Comparisons across fingerprints should be
flagged as non-comparable unless deliberately re-run.

For tonal and ambiguous-segmentation corpora, preserve the source notation and
the selected interpretation/policy in model provenance so that a discovered
rule remains linguistically auditable.

## Verification at review time

The following passed on 2026-08-24:

- CMake build and all 11 CTest tests;
- 50 typology and Python tests;
- model validation, contrast-baseline, NOTICE, and golden-fixture checks.

The model validator emitted only the known unresolved provenance warnings for
P-base and PHOIBLE retrieval metadata.
