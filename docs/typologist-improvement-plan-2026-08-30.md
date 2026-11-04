# Typologist-oriented improvement plan

This plan records the agreed order of work for making Merkmal a safer and more
useful substrate for historical-linguistic and typological research. It is an
implementation plan, not a claim that the proposed designs are already
validated. Arcaverborum work remains separate and deferred.

## 1. Make geometry selection honest

### Problem

Runtime models accept `@geometry`, but the current native implementation has one
compiled-in geometry and silently ignores the directive. Alternative geometry
files, such as `deep-clements-hume.json`, are source-only and cannot currently
produce runtime scores.

### Work

- In the short term, reject geometry names other than the compiled geometry with
  a clear diagnostic; do not silently ignore them.
- Define a geometry identity and registration seam in the C API.
- Decide whether custom geometries should be compiled into a build, loaded from
  validated data, or supplied through a separate registry.
- Validate every geometry independently: node paths, leaves, scales, weights,
  presets, metadata features, and reachability.
- Ensure the selected geometry participates in system and operation
  fingerprints.

### Acceptance criteria

- A request for an unavailable geometry fails deterministically.
- Two actually different geometries cannot produce results with the same
  provenance identity.
- Alternative geometries have their own validation and golden fixtures before
  they are exposed.

## 2. Add complete operation-level provenance

### Problem

The system fingerprint identifies model and compiled geometry identity, but not
all choices that affect a result: weight presets, scorer options,
segmentation, tone handling, alignment, or missingness policy.

### Work

- Keep the current system fingerprint as the stable model identity.
- Add an operation-level provenance structure that records:
  - system fingerprint;
  - geometry and scorer IDs;
  - weight preset and resolved weights;
  - segmentation/tokenization policy;
  - tone policy and normalization policy;
  - comparison and missingness policy;
  - API/library version where relevant.
- Provide canonical serialization and a digest for this operation record.
- Propagate it through Python results and make it available to downstream
  consumers such as Cognator and Regulae.

### Acceptance criteria

- Re-running an operation with any result-affecting option changed produces a
  different operation identity.
- Stored alignments, distances, and clusters can be audited without relying on
  process-local configuration.

## 3. Strengthen runtime custom-model manifests

### Problem

Runtime categorical models currently describe an inventory and feature sets but
not enough scholarly context to support reproducible historical analysis.

### Work

- Define a manifest format for runtime models with:
  - model name/version;
  - source publication, dataset, URL, and retrieval date;
  - language, dialect, doculect, or inventory scope;
  - phonemic/phonetic/orthographic interpretation;
  - transcription and normalization conventions;
  - missingness and alias policy;
  - license and redistribution terms;
  - source and transformed-data hashes.
- Keep the compact text format for convenience, but allow a manifest to travel
  with it.
- Include manifest identity in runtime fingerprints.
- Preserve strict validation for unknown, dead, and duplicate features.

### Acceptance criteria

- A custom model can be traced to an input artifact and interpretation policy.
- A model with identical rows but different declared interpretation or source is
  not treated as scientifically identical.

## 4. Separate compatibility dissimilarity from fixed-space distance

### Problem

Valued models currently use pair-dependent denominators. Their scores are useful
compatibility dissimilarities, but they are not stable metrics and should not be
silently interpreted as such.

### Work

- Give the existing pairwise-complete calculation an explicit compatibility
  name and retain it for compatibility.
- Design a fixed-space distance with explicit states for positive, negative,
  neutral, and missing values.
- Specify per-dimension missingness and neutral-state costs in model metadata.
- Version scorers independently from geometries and models.
- Add metric/property tests where the selected component distances warrant them.

### Acceptance criteria

- API names and documentation distinguish metric distance from compatibility
  dissimilarity.
- Every valued result reports comparable dimensions/weight and missingness.
- No consumer is encouraged to compare raw scores across incompatible scorers.

## 5. Propagate coverage through higher-level results

### Problem

Low-level distance APIs expose coverage, but alignments, clusters, and exported
comparisons can lose that information.

### Work

- Carry pairwise coverage and comparability status into alignment cells and
  aggregate results.
- Report coverage distributions, not only means.
- Allow callers to set explicit low-coverage policies: reject, flag, or retain.
- Preserve original tokens, selected segmentation, and unresolved/ambiguous
  alternatives where relevant.
- Add family- and transcription-stratum coverage reports for typological data.

### Acceptance criteria

- A downstream result identifies which comparisons were weakly covered.
- Thresholding and clustering can be reproduced with the same coverage policy.

## 6. Keep typology and directional sound change outside the core scorer

### Problem

Segment catalogs do not constitute a language-balanced typological sample, and
unordered daughter-pair counts do not identify diachronic direction.

### Work

- Keep typological sampling in a separate data/package layer.
- Require language IDs, genealogy, area, doculect, source, sampling weights, and
  classification version for typological observations.
- Require ancestor/descendant ordering or an explicit phylogenetic model before
  enabling directional change priors.
- Evaluate by held-out families or areas, not random word-pair splits.
- Keep quarantined directional artifacts opt-in and clearly labelled.

### Acceptance criteria

- Core Merkmal APIs make no unsupported claims about universals or sound-change
  probability.
- Any typological result reports its sample composition and effective weights.

## 7. Expose and validate alternative geometries only after the above

Alternative geometries should not be compiled or promoted merely because the
JSON exists. Once geometry selection, provenance, custom manifests, scoring
semantics, and coverage are explicit:

- update `deep-clements-hume.json` to the current feature/reachability contract;
- validate it through the same strict pipeline as the default geometry;
- provide geometry-specific fingerprints and golden distances;
- document theoretical departures and numerical weighting assumptions;
- calibrate each geometry on task-appropriate held-out data.

## Suggested implementation sequence

1. Reject or explicitly diagnose ignored `@geometry` names.
2. Design and implement operation-level provenance.
3. Add runtime model manifests and fingerprint integration.
4. Introduce named compatibility dissimilarity and a fixed-space scorer design.
5. Propagate coverage and segmentation evidence through consumers.
6. Build a separate, language-indexed typology layer.
7. Revisit alternative geometries with independent validation.

No step should change default distances or historical benchmark figures without
new evidence and a separately versioned model/scorer identity.
