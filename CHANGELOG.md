# Changelog

## Unreleased

- Added: bring-your-own-model support, start to end. Models,
  geometries, typologies, and diacritic sets resolve from a layered
  search path. `MERKMAL_MODELS`, `MERKMAL_GEOMETRIES`,
  `MERKMAL_TYPOLOGIES`, and `MERKMAL_DIACRITICS` are now
  `os.pathsep`-separated directory lists layered on top of the bundled
  data (a name in an earlier directory shadows a later one);
  `MERKMAL_DATA_ISOLATED=1` excludes the built-ins.
- Added: `merkmal.load_model_from_dir(path)`, `Registry.register_dir`,
  and `create_registry(extra_model_dirs=..., register_builtin=...)` for
  loading custom models without environment variables.
- Added: data-driven diacritics. The diacritic / modifier / tone →
  feature mapping is now a `DiacriticTable` loadable from
  `diacritics/<name>.json`; a model declares its set with the optional
  `diacritics` key in `model.json`. This makes a fully custom feature
  vocabulary work end to end. The built-in IPA/CLTS set is unchanged and
  shipped as `diacritics/ipa-clts.json`.
- Added (Go): `NewLayeredRegistry`, `LoadModelDir`, `DiacriticTable` /
  `LoadDiacritics`, and a `data/diacritics` embed.
- Fixed (Go): each model is now loaded with the geometry it declares in
  `default_geometry` (and its declared diacritic set), rather than always
  `clements-hume`. Restores Python/Go parity for custom per-model
  geometry.
- Added: JSON Schemas for model/geometry/typology/diacritics files under
  `schemas/`, a "bring your own model" guide (`docs/custom-models.md`),
  and `scripts/validate_models.py PATH` to validate an external model
  directory.

## 0.6.0

- Added: `segment_ipa(ipa) → [phones]` — IPA tokenizer that handles
  tie bars, prefix/suffix modifiers, combining marks, and Chao tone
  digits. Exported from the public API along with `decompose_grapheme`
  and `compose_grapheme`.
- Added: `MergeToneDigits` in the Go module, matching the Python
  `merge_tone_digits`. Fixed `ParseChaoDigits` handling of all-zero
  input.
- Added: sequence normalization (`normalize_sequences`) — fallback
  normalizations for postalveolar affricates (tie-bar stripping,
  retraction).
- Added: valued engine compositional fallback — valued engines
  (phoible, pbase-*) now resolve unknown graphemes via
  `decompose_grapheme` + modifier-to-feature mapping, matching the
  categorical engine's compositional chain.
- Added: CLTS normalization — slash stripping, ligature resolution,
  ASCII-colon parsing, and stress mark normalization for broader
  input compatibility.
- Added: typology module (`typology.py`) with `DirectionCost` and
  `Typology` types for asymmetric distance computation. Three
  bundled typologies: `default`, `lenition-bias`, `corecog-derived`.
- Added: geometry comparison and weight learning infrastructure
  (`paper/`).
- Added: 10,000+ cross-language golden test entries covering all
  nine systems (features, distances, partitions, geometry).
- Fixed: `parse_chao_digits` and `merge_tone_digits` restored to
  public API after accidental omission in 0.5.0.
- Cleaned up: removed one-time migration scripts, fixed import
  sorting.

## 0.5.0

- **Breaking**: data-code decoupling. Feature inventories, geometry
  tree, partition definitions, and per-system metadata moved from
  Python source files to pluggable model directories (`models/`) and
  geometry files (`geometries/`). Both Python and Go implementations
  load these data files at runtime.
- **Breaking**: Python package moved from `src/merkmal/` to
  `python/merkmal/`. Engine implementations reorganized into
  `engines/categorical.py`, `engines/valued.py`, `engines/trained.py`.
- Added: native Go module (`go/`) implementing the full `System`
  interface — model loading, geometry-weighted distance, partition
  derivation, grapheme normalization. All `fs.FS`-based for
  embedding flexibility.
- Added: cross-language golden test data (`tests/golden/`) pinning
  feature extractions, pairwise distances, and partition assignments
  across all nine systems. Both test suites validate against these.
- Added: `model.py` / `model.go` — generic model loader that reads
  `model.json` and dispatches to the appropriate engine by type.
- Added: `geometry.py` / `geometry.go` — geometry loader from JSON,
  replacing the hardcoded tree in the old `geometry.py`.
- Added: `partition.py` / `partition.go` — partition derivation from
  model config, replacing hardcoded slot definitions.
- Added: `registry.py` / `registry.go` — model discovery from the
  `models/` directory.
- Removed: `cognator_export.py` and the `export-cognator` CLI
  subcommand. Downstream Go packages now import `merkmal/go`
  directly.
- Removed: UPA transcription adapter (`upa.py`). Consumers requiring
  UPA-to-IPA mapping should handle conversion upstream.
- Removed: `exporters.py`, `data/` directory (data now in `models/`).

## 0.4.0

- Added: `--custom-level` flag to `export-cognator` for caller-specified
  partition feature subsets (repeatable as
  `--custom-level=name:feat1,feat2,...`). Mirrored in the Python API as
  the `custom_levels=` kwarg of `merkmal.export_cognator` and
  `merkmal.export_all_systems`. Custom levels appear in `partitions.tsv`
  alongside the four standard levels; their feature subsets and source
  are recorded in the manifest with `source: custom`.

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
