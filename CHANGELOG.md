# Changelog

Changes are grouped by release. **Breaking** marks a change that alters the
interface or the numbers a caller receives; results computed before such a
change must be recomputed. The reasons for each change are recorded in the
commit history, in [docs/](docs/README.md) and in the design records in
[docs/development/adr/](docs/development/adr/).

## Unreleased

### Changed

- **Breaking:** the class and articulator labels (`consonantal`/`vocoid`,
  `obstruent`/`sonorant`, `continuant`/`non-continuant`, `anterior`,
  `distributed`, and `labial`, `coronal`, `dorsal`, `guttural`) were added only
  to compiled inventory rows. The complex segments the resolver synthesizes and
  every runtime model row lacked them, and since place scales are defined per
  articulator, segments at different articulators shared no place dimension:
  `d(mb, ŋg) = 0.0` in the default system, `d(mb, ᵐb) = 0.16` for one segment
  in two spellings, and in a runtime model written like the documented example
  `d(p, t) = 0.0`. The derivation now also runs in C (`src/classes.c`) for
  those feature sets; a runtime row naming neither `consonant` nor `vowel` is
  kept as written. A test checks that it reproduces the generator's on every
  compiled row. Runtime model fingerprints change, since rows now carry the
  derived labels. `distinctive` 3.0.0, `descriptive` 2.0.0.
- **Breaking:** a lateral fricative, affricate or click (`ɬ`, `ɮ`, `tɬ`, `ǁ`)
  was classed as a sonorant, because `lateral` was tested before the obstruent
  manners; `ɮ` was nearer `l` than `z`. It is now an obstruent.
- Runtime models: a label written twice in a row is one label.
- **Breaking:** in the categorical systems, two segments that both leave
  length unmarked are no longer compared on `duration`. Counted, that
  agreement gave every pair a shared dimension, so coverage and comparability
  could not report a pair that reaches nothing else (two unrelated runtime
  labels gave 0.0 with coverage 1.0 and `ok`), and it diluted every other
  difference: `sound_distance([voiced], [voiceless])` was 0.5, and
  `ignore-length` raised other distances. Every categorical distance between
  short segments rises slightly (`d(p, b)` 0.143 → 0.167 in `distinctive`).
  In an abstract segment, an unmarked length is the cell `0`, read as `short`
  against a marked value.
- **Breaking:** `distinctive` reads the derived class labels in its `vocoid`,
  `continuant`, `anterior` and `distributed` dimensions, as the geometry
  documentation said it did. `vocoid` read `vowel`/`consonant`, so glides were
  consonants and /w/ was nearer /b/ (0.39) than /u/ (0.58); `continuant`
  omitted nasals, trills and vowels, and `anterior` and `distributed`
  linguolabials and dentals. A diphthong's or cluster's own feature set also
  carries the class labels now, so that its whole-segment term shares
  dimensions with a segment's.

### Fixed

- A stress mark inside a word (`paˈta`) ended up attached, as a modifier
  letter, to the segment before it (`aˈ`), which no system recognizes. The
  tokenizers now treat `ˈ` and `ˌ` as a break and drop them, as the normalizer
  already did with a leading one.
- `mk_merge_tone_digits` (and `segment_ipa_merged`) walked back over the word
  for each tone, so a long input took quadratic time (28 KB took 8 s); it is
  now linear, with identical output.
- A grapheme whose combining marks were written in a non-canonical order
  (`ɤ̞̟̃` with U+031F after U+0303) missed its inventory row, whose key is in
  canonical order, and was synthesized from its diacritics into a different
  segment. Lookup now puts the marks in canonical order first.

## 0.10.0 (2026-11-25)

### Added

- `merkmal_typology` is installable as the separate distribution
  `merkmal-typology` (`pip install ./python/typology`), with its PHOIBLE
  inventories in the wheel; it was usable only from a checkout.
- `merkmal_typology`: an inventory comparison whose mean match coverage is
  below `MIN_MATCH_COVERAGE` (0.5) is flagged (`InventoryComparison.low_coverage`)
  and emits a `LowCoverageWarning`.
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

- The compiled-in normalization tables move from Unicode 15.1 to 16.0
  (`mk_unicode_version`, `merkmal.UNICODE_VERSION`). Only characters assigned
  in 16.0 normalize differently; no IPA character is among them, and no
  distance or fingerprint changes. 16.0 is the version of the utf8proc that CI
  installs, whose mismatch had made CI skip the normalization oracle. A build
  configured with `MERKMAL_REQUIRE_UTF8PROC=ON` now fails, rather than skips,
  when utf8proc carries another Unicode version, so the oracle cannot silently
  stop running.
- **Breaking:** a mark written twice on one letter is refused with
  `MK_ERR_PARSE` (`merkmal.ParseError`) in every system: `tʰʰ`, `tʰʷʰ`, `ã̃`,
  `ⁿⁿt`, `á́`. It added nothing, since features are a set, so such a label
  resolved as the one with the mark once, at distance zero from it. The same
  mark on two letters (`t̥ʃ̥`, `kʷkʷ`) and a doubled length mark (`aːː`,
  overlong) are unaffected. In the Lexibank corpus of `bench/corpus/` the
  categorical systems now recognize 7,053 of the 7,396 segment types (7,059
  before); the six refused are `ts̠̠`, `ɑ̠̠`, `ao̠̠̠`, `õ̃i`, `ẽː̃` and `⁵/ẽː̃`.
- **Breaking:** in the categorical systems a feature vector also encodes a
  synthesized cluster's parts: after the segment columns come `components`
  (the number of parts) and one block of segment columns per part, up to three.
  Two diphthongs had near-empty, equal vectors (`ai` and `au`) although their
  distance is not zero; equal vectors now imply distance zero for clusters
  too. Widths: `distinctive` 64 → 257, `descriptive` 68 → 273. The segment
  columns, which lead the vector, are unchanged, and so is
  `fixed_space_distance` between two segments.
- **Breaking:** the tokenizers (`mk_segment_ipa` and those built on it) rewrote
  ASCII digits 0–5 as Chao superscripts (`ji5` gave `j`, `i`, `⁵`), contrary to
  the documentation and to the recognizer, which refuses ASCII digits. They now
  leave them as written. The conversion is available explicitly as
  `mk_ascii_chao_digits` (`merkmal.ascii_chao_digits`), for text known to write
  Chao levels in ASCII.
- **Breaking:** a cluster whose part carries a diacritic or a tone (`ntʰ`,
  `stʰ`, `pʷpʷ`, `ái`, `a¹i`) was reduced to its marks and scored 0.0 against
  every cluster of its shape, with full coverage (`d(ntʰ, mpʰ) = 0.0`). It is
  now resolved as a cluster whose parts keep their features: a diacritic stays
  with its part, a prefix modifier (`ⁿ` in `ⁿph`) with the base after it, and a
  tone is one tone of the whole syllable, wherever and however often it is
  written (`a¹i`, `ai¹` and `a¹i¹` are one segment; two different tones are
  refused). The same Lexibank segment types are recognized; distances change
  for these forms.
- `mk_system_segment_ipa` keeps a complex segment with a diacritic as one token
  (`tʃʰa` gives `tʃʰ`, `a`, not `t`, `ʃʰ`, `a`), as the recognizer reads it, and
  is total in the valued systems, where a tone after a vowel raised
  `MK_ERR_UNSUPPORTED_MODEL`.
- The JSON Schemas in `data/schemas/` are removed: nothing read them, and
  `tools/validate_models.py` is the statement of a valid model or geometry file.
- **Breaking:** tone merging (`mk_merge_tone_digits`, `mk_segment_ipa_merged`)
  keeps a tone with no vowel or syllabic consonant before it in its word as a
  token of its own (`ŋ²¹` gives `ŋ`, `²¹`; `⁵⁵` gives `⁵⁵`) instead of dropping
  it. The token resolves as a tone in the categorical systems. The neutral
  tone `⁰`, which was always dropped, is likewise kept as a token of its own.
- Geometry 3.0.1: the geometry file's references to its documentation point to
  `docs/method/geometry.md`. No distance changes, but the geometry hash in every
  semantic fingerprint does.
- **Breaking:** a PHOIBLE tone row (valued `tone=+`) against a segment is
  cross-tier, as in the categorical systems: the declared cross-tier cost 1.0
  with `MK_CMP_CROSS_TIER`, where it scored 0.0 with no shared dimension. Such
  a row is also refused as an abstract segment. The comparison policy in the
  semantic fingerprint is `segment-distance-v2`.
- `AbstractSegment.compare` and the WebAssembly adapter report comparability
  as `cross-tier` and `no-shared-dimension`, the labels of
  `distance_with_coverage`, instead of `cross_tier` and `no_shared_dimension`.
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

- Smaller edges: a runtime model with a second `@model` line, a second word
  after the name, or a row for `+` (never looked up) is refused instead of
  accepted; `mk_string_list_new` reports a NULL item as an invalid argument,
  not out of memory; `mk_system_feature_vector` with no buffer reports the
  width; the browser demonstration reported a valid prefix of 64 bytes or more
  as empty. Command line: `segment` uses the `--system` given (it ignored it),
  `normalize` refuses the option, and output to a closed pipe no longer prints
  a traceback.
- Documentation that did not match the code: the PHOIBLE tone example in
  `c-api.md` (a tone against a segment is cross-tier, not 0.0), the reason given
  for zero distances in the valued systems (equal on every dimension *both*
  define, not identical source rows), PHOIBLE's dimension count (38, not 37;
  model 2.0.1, whose fingerprint changes and whose distances do not), the
  claim that every grapheme yields an abstract segment, the methods of
  `Registry`, and the undocumented reading of `x/y` as `y` and of a leading
  stress mark.
- Cost on long or large input: canonical reordering was quadratic in a run of
  combining marks, `mk_system_diagnose` resolved every prefix of its input (17 s
  for 4 KB), and a runtime model's fingerprint was quadratic in its rows. Long
  mark runs are sorted in linear time, diagnosis tries prefixes up to 256
  bytes, and the fingerprint sorts the rows once; results are unchanged.
- Out of memory during resolution could give a wrong answer instead of
  `MK_ERR_OOM`: `aːː` resolved as `aː`, and a cluster could be reported as an
  unknown grapheme.
- `merkmal.pc` assumed the library directory is two levels below the prefix,
  so with a multiarch `CMAKE_INSTALL_LIBDIR` (`lib/x86_64-linux-gnu`) it pointed
  at `<prefix>/lib/include`. The path is computed when configuring.
- An unknown weight preset was accepted, and ignored, when the answer needed no
  scoring (a grapheme against itself, a tone against a segment); it is refused
  on every path. `mk_system_segment_distance_ex` left `*coverage` unwritten
  when a grapheme was refused; it is 0.0, as documented.
- Python: a malformed grapheme (`a¹²³⁴`, `aːːː`) raised `NativeError`, not the
  documented `ValueError`. It raises the new `merkmal.ParseError`, a subclass of
  both. A feature name too long to prefix in a cluster raised `MemoryError`;
  it raises `ParseError`.
- The PHOIBLE inventories of `merkmal_typology` were labelled CC-BY-4.0 on a
  relicensing permission that was never recorded. They are labelled with
  PHOIBLE's own terms, CC-BY-SA-3.0, like the PHOIBLE model in the core library.
- A static consumer was not told to link the math library, which the library
  needs for `fabs`: `merkmal.pc` now lists `-lm` in `Libs.private`, and the
  CMake package carries it as a link-only dependency.
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
