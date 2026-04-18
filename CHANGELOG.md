# Changelog

## 0.3.0

- Added: `partitions.tsv` in cognator export — feature-subset-derived
  grapheme partition at four granularity levels (prosody, coarse,
  medium, fine). Derived from each system's own features; transparent
  per-level feature subset recorded in manifest.

## 0.2.0

- Added: `export-cognator` subcommand for static export of feature
  distances, classes, prosody, and fallback data to a byte-stable
  bundle consumed by cognator. Exposed as `merkmal.export_cognator`
  (single system) and `merkmal.export_all_systems` (every registered
  system). Bundles are reproducible under `SOURCE_DATE_EPOCH` and
  include SHA-256 hashes in `manifest.json`.
- Added: `merkmal` console script entry point (also runnable via
  `python -m merkmal`).

## 0.1.1

- Fix cross-process non-determinism in `sound_distance` and
  `valued_geometry_distance`. Set unions are now sorted before
  iteration so floating-point accumulation order is stable
  regardless of Python's hash randomization seed.

## 0.1.0

Initial public release.

- Nine built-in feature systems: descriptive, broad, distinctive,
  pbase-hc, pbase-jfh, pbase-spe, pbase-uftc, phoible, classfeat.
- Feature geometry tree for structured distance (Clements & Hume 1995).
- Tonal geometry (Yip 1980, Bao 1999): register, contour, onset/mid/offset.
- ClassFeat: trained hybrid system (sound classes + continuous features).
- Compositional segment decomposition via Unicode NFD.
- UPA transcription adapter.
- Analysis layer: queries, matrices, natural class derivation, distance, export.
- Zero runtime dependencies, Python 3.12+.
