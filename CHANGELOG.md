# Changelog

## Unreleased

- Breaking: repository direction changed from parallel Python/Go
  implementations to a C99 core library with a native Python wrapper.
  Go support has been retired.
- Breaking: the installable Python package is now native-only. The old
  pure-Python implementation and its tests have been removed from the active
  codebase.
- Added: C99 library skeleton, public `merkmal.h`, CMake build, compiled-in
  built-in data, C golden tests, and CPython Limited API wrapper.
- Added: C install rules, exported CMake package metadata, pkg-config metadata,
  public symbol annotations, and `mk_status_string`.
- Added: release policy documentation, sanitizer CI, and an Emscripten/Node
  smoke test for the raw C ABI with filesystem support disabled.
- Added: public C APIs for built-in registries, runtime categorical model
  registration, feature lookup, segment distance, geometry feature
  distance, sound distance with weight presets, IPA normalization,
  segmentation, and Chao tone digit merging.
- Added: `mk_split_tone` and Python `split_tone`, which separate a merged
  segment such as `a¹³` into its base grapheme and its Chao tone token.
  Consumers that model tone as its own dimension previously had to
  reimplement Chao digit parsing to undo `mk_merge_tone_digits`.
- Documented: Chao digits are pitch levels, not tone-category numbers.
  Superscript `⁰`-`⁵` merge; ASCII digits such as Jyutping `ji6` or Yoruba
  `ori3` label tone categories, carry no pitch, and stay unrecognised
  rather than synthesising tone features the notation never asserted.
- Added: Python wrapper access to `node_weights`, tone-digit merging,
  merged IPA segmentation, and a minimal native `Registry` for runtime model
  text.
- Added: descriptive source-token synthesis for vowel clusters, explicit
  complex consonants, broader affricate spellings, and tone-bearing nuclei.
- Added: Arca-driven residual descriptive support for precomposed-vowel
  clusters such as `ɛï³³` and mixed velar affricate source tokens such as
  `kɣ`.
- Added: compositional descriptive support for precomposed vowel/modifier
  source tokens such as `ḭ`, `ṳ`, `ṵ`, and `ṵː`, plus `ṽ` as a nasalized
  consonant.
- Changed: bare `mb` and `nd`, standalone tone clusters, slash-delimited
  tone/control forms, and source markup/control tokens remain invalid source
  segments.
- Added: public documentation for C distribution, the C API, and the
  line-oriented runtime categorical model format.
- Changed: pre-C Python tutorials, notebooks, and research scripts are archived under
  `docs/legacy_python/` until they are rewritten for the native API.
- Changed: generated C data now comes directly from the top-level source data
  files instead of importing archived Python loaders.

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
