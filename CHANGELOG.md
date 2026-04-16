# Changelog

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
