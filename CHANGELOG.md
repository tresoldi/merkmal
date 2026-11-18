# Changelog

Changes are grouped by release. **Breaking** marks a change that alters the
interface or the numbers a caller receives; results computed before such a
change must be recomputed. The reasons for each change are recorded in the
commit history, in [docs/](docs/README.md) and in the design records in
[docs/development/adr/](docs/development/adr/).

## Unreleased

### Added

- Abstract segments: feature bundles without a grapheme, with cells that may be
  unspecified or restricted to a set of values (`mk_bundle_*`,
  `merkmal.AbstractSegment`). See
  [docs/method/abstract-segments.md](docs/method/abstract-segments.md).
- `mk_system_inventory` (the graphemes of a system's own table) and
  `mk_unicode_normalize` (NFC or NFD without IPA rewrites), in C.
- Build identity: `MK_VERSION_*` macros, `mk_version_string`, `mk_data_profile`
  and `mk_unicode_version`; `merkmal._native.LIBRARY_VERSION` and
  `merkmal.DEFAULT_SYSTEM` in Python.
- Command line: `--json`, `--jsonl` and `--tsv` output, documented as the stable
  interface for scripts; `distance` also reports coverage and comparability.
- Runtime model format: an optional `@format_version` directive; a model
  declaring a newer version than the library reads is refused.

### Changed

- **Breaking:** `distinctive` model 2.0.0. Each scalar dimension names the
  geometry leaf it mirrors and takes that leaf's weight and node, so
  `distinctive` and `descriptive` weight the same property alike; the four
  dimensions without a leaf declare their weight. Eighteen dimensions change
  weight (the articulators 0.25 → 0.4, secondary articulations and `apical`
  0.25 → 0.33, `nasalized`, `ejective`, `fricative`, `click` and `implosive`
  0.33 → 0.5), and `nasalized` and `ejective` move to the `Manner` and
  `Laryngeal` nodes, which changes their weight presets. Most `distinctive`
  distances change slightly (`p`–`b` 0.1493 → 0.1429; rank correlation 0.994
  over 79,800 pairs), and the semantic fingerprint changes.
- **Breaking:** numeric feature vectors include every dimension the scorer reads
  (ordered scales and node-group columns), so their width and columns change
  (`distinctive` 54 → 64, `descriptive` 62 → 68). Equal vectors now imply a
  distance of zero.
- **Breaking:** `mk_sound_distance` refuses a feature label the geometry does not
  know, with the new status `MK_ERR_UNKNOWN_FEATURE` (Python: `ValueError`),
  instead of ignoring it.
- PHOIBLE model 2.0.0 distinguishes "does not apply" (`0`) from "unknown" (`?`),
  which were both written `.`. Distances are unchanged; feature labels change,
  and unknown values are `NaN` in feature vectors.
- Python: a string argument containing U+0000 raises `ValueError` instead of
  being truncated at that character. The browser demonstration refuses such
  input in the same way.
- Repository layout: source data in `data/`, all generators and checks in
  `tools/`, fuzzing harnesses in `tests/fuzz/`, the typology package in
  `python/typology/`, and documentation in `docs/guide/`, `docs/method/` and
  `docs/development/`. Internal working documents were removed.

### Fixed

- An affricate, labial-velar or prenasalized stop written without a tie bar
  (`tʃ`, `kp`, `mb`) was derived with fixed features in any categorical system,
  including a runtime model that lists neither letter; it is now derived only
  when the system lists both. The built-in systems are unaffected.
- The WebAssembly adapter wrote an unknown feature value (NaN) as `nan`, which is
  not JSON; it now writes `null`, and the demonstration shows it as `?`.
- Tone merging dropped the tone of a syllabic consonant marked with U+030D
  above (`ŋ̍²¹` gave `ŋ̍`); the mark is now treated like U+0329 below.
- The contrast baseline counted no zero-distance pair as having "no comparable
  dimension": an unpacking error was swallowed. It now reports 7,131 of the
  13,779 sampled PHOIBLE pairs, mostly a tone row against a segment.
- `mk_system_segment_distance_ex` did not set the coverage of a comparison
  involving a synthesized cluster, so the caller's initial value was returned and
  the comparability derived from it could be wrong. Cluster coverage is now
  computed from the coverage of its parts; distances are unchanged.
- A runtime model row with more than 64 features overflowed a stack buffer in
  `mk_system_semantic_fingerprint`.
- `mk_system_segment_ipa` freed memory twice, and cluster synthesis leaked
  memory, when an allocation failed.

## 0.9.0 (2026-11-04)

The first release of the C library and the Python package built on it. Work
developed under the provisional version 1.0.0, which was never released, is
included here.

### Added

- A C99 library with a single public header, `merkmal.h`; CMake build, install
  rules, a CMake package and a pkg-config file.
- A Python package wrapping the library through the CPython limited API, built
  as `abi3` wheels, with a `merkmal` command line.
- A WebAssembly build and a browser demonstration.
- Seven compiled-in feature systems: `distinctive`, `descriptive`, `phoible`,
  `pbase-hc`, `pbase-jfh`, `pbase-spe` and `pbase-uftc`.
- A `cc-by` data profile without the share-alike and non-commercial tables
  (`MERKMAL_DATA_PROFILE`, `merkmal.DATA_PROFILE`).
- Runtime models in a line-oriented text format, validated strictly by default
  (`mk_registry_add_model_text`, `_ex` with a diagnostic, `_n` for byte buffers).
- System-aware tokenization by longest match (`mk_system_segment_ipa`).
- Comparison with coverage and comparability (`mk_system_segment_distance_ex`,
  `merkmal.distance_with_coverage`).
- Numeric feature vectors (`mk_system_feature_vector`, `merkmal.feature_vector`).
- Diagnosis of a refused grapheme: the valid prefix and the offending character
  (`mk_system_diagnose`).
- Semantic fingerprints of a system's data and policies
  (`mk_system_semantic_fingerprint`).
- Separation of a merged tone (`mk_split_tone`); tone written as a segment of its
  own; the IPA tone letters U+02E5–U+02E9.
- Status codes `MK_ERR_SOURCE_MARKER` (CLDF and CLTS markup), `MK_ERR_DUPLICATE_SYSTEM`
  and `MK_ERR_NO_TREE_PATH`.
- `merkmal_typology`, a companion package of language-indexed PHOIBLE
  inventories, separate from the core library.
- Provenance manifests for every model and a `NOTICE` generated from them.
- Benchmarks against external references (alignment, corpus coverage,
  cross-theory robustness, fitted pair costs) and an exhaustive record of
  zero-distance pairs; see [docs/method/evaluation.md](docs/method/evaluation.md).
- Fuzzing harnesses, static analysis, sanitizer builds and a strict warning set
  in continuous integration.

### Changed

- **Breaking:** the default system is `distinctive` (previously `descriptive`).
- **Breaking:** categorical distances changed: ordered properties (vowel height
  and backness, length, Chao tone level, place) are compared as positions on
  scales, and major-class features are derived; `pbase-jfh` distances changed
  with a corrected feature mapping.
- **Breaking:** PHOIBLE's values were rebuilt from the pinned upstream release
  (v2.0.1), correcting 5,272 cells; PHOIBLE distances changed.
- **Breaking:** the valued systems refuse tone-bearing graphemes
  (`MK_ERR_UNSUPPORTED_MODEL`) instead of ignoring the tone.
- **Breaking:** a tone and a segment are not compared on a shared scale; the
  comparison returns a declared cross-tier cost and reports it through the new
  `mk_comparability` output of `mk_system_segment_distance_ex`.
- **Breaking:** `mk_feature_distance` returns `MK_ERR_NO_TREE_PATH` for a feature
  outside the geometry tree instead of the value 999.
- **Breaking (C):** `mk_feature_set` was removed; `mk_system_grapheme_features`
  returns an `mk_string_list`. `mk_free_string` was renamed `mk_string_free`.
  `mk_system_is_segment` reports through `bool *` rather than `int *`.
  `mk_sound_distance` takes two `mk_feature_view` values instead of four
  arguments.
- **Breaking (Python):** `feature_distance` takes no `system` argument, and the
  private `merkmal._native._registry_*` functions were removed.
- **Breaking:** the distribution declares
  `MIT AND CC-BY-4.0 AND CC-BY-SA-3.0 AND CC-BY-NC-SA-4.0`, reflecting the terms of
  the bundled data.
- A place diacritic changes the place of the segment it modifies, and
  contradictory diacritics are refused (`MK_ERR_PARSE`).
- Diphthongs, consonant clusters and complex segments are derived in every
  categorical system, and a cluster's parts are resolved once and reused.
- A registry refuses a second system with an existing name
  (`MK_ERR_DUPLICATE_SYSTEM`).
- Unicode normalization is compiled in, so every build returns the same strings;
  utf8proc is used only as a test oracle.
- Inventory lookup is a binary search, and the compiled data is interned
  (WebAssembly payload 55% smaller).
- Only the public API is exported from the library (`mk_` public, `mki_`
  internal).

### Fixed

- A heap buffer over-read on truncated UTF-8 input.
- A cluster component read after the end of its stack frame.
- Tie-barred spellings of derived complex segments (`t͡ʂ`, `d͡ʐ`) were refused.
- `ʏ` could not begin a diphthong, and `ɚ`, `ɝ` were not recognized.
- An affricate inside a cluster was split into its two letters.
- A source convention could replace a segment that the system itself lists.
- IPA tone letters were dropped by tone merging.
- Strict validation of a runtime model took time quadratic in its size.

### Removed

- **Breaking:** the `broad` system, a duplicate of `descriptive`.
- **Breaking:** the pure-Python implementation and its helper functions, and the
  Go module.

## 0.6.0

- Added `segment_ipa`, an IPA tokenizer handling tie bars, modifiers, combining
  marks and Chao tone digits, together with `decompose_grapheme` and
  `compose_grapheme`.
- Added `MergeToneDigits` to the Go module; fixed `ParseChaoDigits` for all-zero
  input.
- Added fallback normalization of postalveolar affricates (tie-bar removal,
  retraction).
- Added compositional resolution of unknown graphemes in the valued systems.
- Added CLTS normalization: slash removal, ligatures, ASCII colon and stress
  marks.
- Added a typology module with asymmetric direction costs and three bundled
  typologies.
- Added over 10,000 cross-language golden test entries for all nine systems.
- Fixed: `parse_chao_digits` and `merge_tone_digits` were missing from the public
  API in 0.5.0.

## 0.5.0

- **Breaking:** feature inventories, the geometry, partitions and system metadata
  moved from Python source into model directories and geometry files loaded at
  run time.
- **Breaking:** the Python package moved from `src/merkmal/` to
  `python/merkmal/`.
- Added a Go module implementing the same interface, cross-language golden tests,
  and generic loaders for models, geometries and partitions.
- Removed the cognator export, the UPA transcription adapter and the exporters.

## 0.4.0

- Added caller-specified partition levels to the cognator export
  (`--custom-level`, `custom_levels=`).

## 0.3.0

- Added grapheme partitions at four levels of granularity to the cognator export.

## 0.2.0

- Added the `export-cognator` command, a reproducible export of distances,
  classes and prosody, and the `merkmal` command-line entry point.

## 0.1.1

- Fixed non-deterministic results of `sound_distance` and
  `valued_geometry_distance` across processes.

## 0.1.0

Initial release: nine feature systems, a feature geometry after Clements and Hume
(1995) and a tonal geometry after Yip (1980) and Bao (1999), the ClassFeat
system, compositional decomposition of segments, a UPA adapter, and an analysis
layer.
