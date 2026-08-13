# Changelog

## Unreleased

### Internal structure, and two tokenization defects

Restructuring of the C library and its Python wrapper. No distance, feature
set, or tokenization result changes except where noted as a fix.

- Fixed: IPA tone letters were dropped by tone merging. The tokenizer grouped
  `˥˦˧˨˩` into a tone run, but the merge step decoded superscripts only, judged
  the run all-zero, and discarded it — `segment_ipa_merged("a˥")` returned a
  toneless `"a"`. The library had three Chao decoders accepting three different
  alphabets; it now has one.
- Fixed: graphemes in a caller-supplied runtime model were stored as written
  while queries were normalized, so a `grapheme` row spelled with a precomposed
  `ã` could not be matched under either spelling. Runtime and built-in models
  now share one normalization, and the source conventions apply too, so a row
  written `ʧ` is reachable as `tʃ`.
- Fixed: an unknown `node_weights` preset on a cluster segment such as `ai`
  returned `MK_OK` with a composed value near 0.8 instead of
  `MK_ERR_INVALID_ARGUMENT`. The scorers no longer signal failure with `NAN`.
- **Breaking (Python):** `feature_distance` no longer accepts `system`. It
  measures a distance in the compiled geometry, which every system shares; the
  argument was validated and then ignored, so a caller naming `phoible` was
  silently given clements-hume numbers.
- **Breaking (Python):** `merkmal._native._registry_*` are gone. Each operation
  is now one function taking an optional `registry`, and `Registry` methods
  call it. `merkmal.Registry` itself is unchanged apart from `system` now
  defaulting to `None` (the same default system) rather than to the literal
  `"descriptive"`.
- Added: `merkmal.Registry.system_segment_ipa`.
- Changed: adding a model to the shared default registry now raises
  `ValueError` rather than mutating what every other caller in the process
  sees. Construct a `merkmal.Registry`.
- Changed: bare `mb`, `nd`, `mp`, `nt` and `ŋg` are recognized as prenasalized
  consonant clusters; `docs/c-api.md` still described the older two-item
  blocklist.
- Internal: segment resolution moved into `src/resolver.{c,h}` behind
  `mk_resolve`, which reports which path resolved a grapheme; `src/system.c`
  went from 2298 to 473 lines. The two component parsers and the two cluster
  synthesizers became one of each, taking a grammar. Hand-written C dropped
  from 5466 to 5084 lines and the Python binding from 929 to 811.

### Second review pass: ordered scales, derived class features, tone

An independent linguistic review ([docs/independent-linguistic-review.md](docs/independent-linguistic-review.md))
found that the first pass had corrected the symptoms it measured while leaving
the underlying defect: ordered properties were encoded as unordered flags, and
several basic features were unreachable. See
[docs/review-response.md](docs/review-response.md) for the correction notice.

- **Corrected claim.** "Every consonant-consonant pair scores below every
  consonant-vowel pair" was false; it generalised from eight hand-picked pairs.
  Measured across the inventory, `broad` had a max C-C of 0.829 against a min
  C-V of 0.660. The claim is withdrawn.
- **Corrected claim.** "Every zero is on the record" covered only the bare
  inventory of the three categorical systems. It missed composed forms
  (`d(aː, aːː)` was 0) and all five valued systems (`phoible` scored zero on
  ~5% of pairs). The audit now covers all eight systems and composed forms.
- **Corrected claim.** "33 dead labels to 0" checked one direction only.
  Thirteen scoring leaves were unreachable because no inventory name ever says
  `sonorant`, `continuant`, `anterior` or `distributed`. Both directions are now
  checked.
- **Breaking (numeric): all categorical distances changed again.** Ordered
  properties are now scored as ordered scales, cost proportional to the
  difference in level.
- Fixed: the vowel space was not ordinally correct. `d(i,e)` was 0.214 while
  `d(i,a)` was 0.167, and `/i/`, `/e/` and `/a/` were all exactly 0.500 from
  `/ɔ/`. Height and backness are now seven- and five-point ordered scales.
- Fixed: the Chao tone code was not monotone in the digit. Levels 2 and 4
  differed on both the register and the height bit, so they scored as far apart
  as 1 and 5. Each position now carries an ordered level.
- Fixed: two-digit contours never filled the mid slot, so `a¹` and `a¹¹` — the
  same level tone spelled two ways — differed.
- Added: IPA tone letters U+02E5–U+02E9, the primary IPA tone notation, were
  rejected outright and are now read as pitch levels.
- Fixed: 19 precomposed tone-marked vowels (including the whole Pinyin
  third-tone set `ǎ ě ǐ ǒ ǔ`) were rejected while their canonically equivalent
  NFD spellings were accepted — and `normalize()` returns the precomposed form,
  so the documented preprocessing step turned working input into failing input.
  Decomposition is now table-driven and identical with or without utf8proc.
- Fixed: length was a set of unordered flags. A half-long vowel scored further
  from a long one than a plain vowel did, `aː` and `aːː` were identical, and
  breve-plus-length-mark asserted both `ultra-short` and `long`. Duration is now
  a five-point ordered scale, a repeated length mark means overlong, and
  contradictory values are rejected.
- Fixed: every manner distinction cost the same, because `sonorant`,
  `continuant`, `anterior` and `distributed` were never activated by any
  grapheme. They are now derived from the manner and place labels.
- Fixed: `/w/` scored as far from `/u/` as `/ʔ/` does from `/a/`. `vocoid` is
  derived and covers the cardinal glides, which are [-consonantal].
- Fixed: clicks carried the rear closure as a second place, so `/ǃ/` was exactly
  equidistant from `/k/` and `/t/`. The rear closure is now its own feature.
- Fixed: `segmental` and `ignore-prosodic` silently discarded nasalisation and
  ejectivity along with length. Both moved out of `Prosodic`; `ignore-length`
  and `ignore-secondary` presets added.
- Fixed: `mb` and `nd` were rejected by a two-item blocklist while `mp`, `nt`,
  `ŋg` and `ndz` were accepted. The blocklist is gone.
- Fixed: `pre-nasalized` was asserted for any nasal-initial cluster, so the
  geminates `mm`/`nn` and the labial-velar nasal `ŋm` carried it.
- Fixed: three inventory errors — a Private-Use-Area codepoint U+F268, a
  spurious `oz̻`, and `ǃǃ` — and seven rows carrying an undescribed combining
  circumflex, which consumed the tone mark and produced a plain mid vowel while
  the same sequence elsewhere synthesised a full falling tone.
- Fixed: `classes.tsv` defined class `R` "resonant" as `consonant,-stop`, which
  captured every fricative and affricate; and shipped a leftover `XXX`
  "development" class.
- Fixed: `typologies/lenition-bias.json` made devoicing the cheap direction,
  contradicting its own stated lenition scale.
- Fixed: two more inventory naming errors that made distinct segments
  identical — `ʈʂː` was named *voiced* though `ʈʂ` is voiceless, and `ⁿgǃ` (a
  prenasalized plain click) was named a *nasal-click*, which made it the same
  as prenasalized `ŋǃ`.
- Fixed: cross-articulator place had become invisible while the ordered place
  scales were being introduced — each scale is undefined for the other
  articulator, so `d(b, g)` was 0. The privative articulator features (labial,
  coronal, dorsal, guttural) now carry that difference.
- Result: **no pair of distinct forms scores zero in any categorical system**,
  over 611,065 pairs including modifier-composed forms; every label can affect
  a distance and every scoring dimension is reachable.
- Documented: phonetic distance does not track diachronic probability. Frequent
  changes score *further* apart than rare ones on average. This is inherent, not
  a tuning target.

### First review pass

#### Response to the external linguistics and phonology review

See [docs/review-response.md](docs/review-response.md) for the finding-by-finding
account. Highlights:

- **Breaking (numeric): categorical and `pbase-jfh` distances changed.** Every
  distance produced by `broad`, `descriptive`, and `distinctive` moved, and
  every feature set for a tone-bearing grapheme changed. Recompute stored
  distances, alignments, clusters, and thresholds; do not mix cached scores
  across this change.
- Fixed: 33 feature labels reached no scoring dimension and so could not affect
  any distance, among them `consonant`, `vowel`, `devoiced`, `apical`,
  `laminal`, `unreleased`, `velarized`, and the whole length series. As a
  result `p`~`p̥`, `t`~`t̺`, `k`~`k̚`, and `y`~`yːː` all scored exactly zero.
  Over all 302,253 inventory pairs, zero-distance pairs fell from 802/802/599
  to 7/7/7, and those 7 are now declared with reasons in
  `tests/golden/contrast_baseline.tsv`.
- Fixed: `distinctive` could not separate palatal/velar/uvular consonants,
  bilabial from labiodental, the guttural places, close-mid from mid from
  open-mid, lateral fricatives from lateral approximants, or clicks from
  implosives. Dimensions were added for each.
- Fixed: Chao level 3 produced no features, so a mid-tone segment was identical
  to a toneless one (`a` = `a³³` = `ā`). Tone now emits `tone-present` plus an
  explicit `tone-<position>-mid-level`.
- Fixed: a Chao run of four or more digits was split into two contradictory
  tone readings, so `a¹²³⁴` was accepted and carried both `tone-onset-lowered`
  and `tone-onset-raised`. Over-long runs are now rejected whole.
- Fixed: `models/pbase-jfh/model.json` mapped `"vocalic "` with a trailing
  space, so that dimension was absent from every `pbase-jfh` distance. The dead
  `spread` key was removed from `models/pbase-spe/model.json`.
- Fixed: `models/phoible/model.json` declared the state symbol `0`, which never
  occurs in its inventory, while the 30,181 cells written as `.` were
  undeclared. Its license is corrected from generic `CC-BY` to `CC-BY-SA-3.0`.
- Breaking: the valued systems (`pbase-*`, `phoible`) now return
  `MK_ERR_UNSUPPORTED_MODEL` for tone-bearing graphemes. None has a dimension a
  tone modifier can move, so they previously scored `a¹¹` and `a⁵⁵` as equal.
- Breaking: runtime model registration validates strictly by default. A model
  whose features the geometry does not know is rejected with a diagnostic
  instead of registering and then scoring every comparison as zero. Use
  `@validation permissive` to opt out.
- Breaking: the distribution declares
  `MIT AND CC-BY-SA-3.0 AND CC-BY-NC-SA-4.0`, not MIT alone. The compiled-in
  tables include PHOIBLE (share-alike) and P-base (non-commercial share-alike)
  data. See the generated `NOTICE`.
- Added: `mk_system_segment_ipa` / `merkmal.system_segment_ipa`, longest-match
  tokenization that agrees with a system's own recognizer, so `tʃa` becomes
  `[tʃ, a]` and `kpa` becomes `[kp, a]`. `mk_segment_ipa` is unchanged and now
  documented as orthographic tokenization.
- Added: `mk_registry_add_model_text_ex`, which reports which line and token a
  rejected model failed on.
- Added: per-artifact `models/*/provenance.json`, a generated `NOTICE`, and
  `scripts/generate_notice.py`. Upstream release, commit, and retrieval date
  are recorded as `UNVERIFIED` rather than guessed.
- Added: `scripts/contrast_baseline.py` (exhaustive collapse and dead-label
  audit) and `scripts/regenerate_golden.py` (reviewable fixture regeneration).
- Changed: the geometry is identified as `merkmal-clements-hume-inspired-v1`
  with an explicit `departures` list; `clements-hume` remains a compatibility
  name. See [docs/geometry.md](docs/geometry.md).
- Changed: `typologies/corecog-derived.json` is quarantined. It is not a
  sound-change direction prior: unordered daughter-daughter pairs do not
  identify direction, its stated pair orientation was wrong, and its cost
  transform was inverted. See `typologies/README.md`.
- Documented: the output is an experimental dissimilarity, not a metric, not a
  sound-change probability, and not a typological statistic. `broad` and
  `descriptive` are operationally identical at this revision.

### Earlier unreleased work

- Breaking: repository direction changed from parallel Python/Go
  implementations to a C99 core library with a native Python wrapper.
  Go support has been retired.
- Breaking: the installable Python package is now native-only. The old
  pure-Python implementation and its tests have been removed from the active
  codebase.
- Changed: Python packaging now lives at the repository root so source
  distributions include the C core and can build independently of a checkout.
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
