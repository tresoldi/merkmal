# merkmal C Core Rewrite Plan

This document records the agreed direction for moving `merkmal` from parallel
Python/Go implementations to a C99 core library with a Python wrapper.

## Goals

- Make C99 the primary implementation of `merkmal`.
- Keep the public C API high-level and stable enough for downstream C software.
- Preserve a familiar Python package named `merkmal`, implemented as a thin
  wrapper over the C library.
- Drop Go support after the C and Python implementations cover the selected
  behavior.
- Prioritize WebAssembly-friendly design: no required filesystem access for
  built-in models, no process-global mutable registry, and explicit ownership.
- Preserve parity with current behavior where useful, while allowing API and
  implementation changes when they simplify the C design.

## Confirmed Decisions

- C symbol prefix: `mk_`.
- C core: C99.
- Unicode dependency: `utf8proc`.
- Built-in models: compiled into the C library.
- Runtime models: supported later via a simple caller-supplied model format.
- C API scope: high-level operations only for now.
- Python package: keep the package name `merkmal` and familiar top-level
  functions such as `merkmal.distance("p", "b")`.
- Python binding style: CPython extension using the Limited API / `abi3` for
  better binary wheel compatibility.
- Threading: loaded registries and systems are immutable and safe for concurrent
  reads. The C library should not expose a mutable global default registry.
- First implementation slice: `descriptive` and `phoible`.
- First engine scope: categorical and valued engines. Leave the code structure
  ready for `classfeat`, but do not implement it in the first milestone.
- Repository direction: C becomes the top-level implementation; Python becomes
  a wrapper subproject.

## Non-Goals For The First Milestone

- Exposing geometry internals, inventory rows, feature matrices, or mutable model
  internals through the public C API.
- Supporting `classfeat`.
- Preserving Go support.
- Reproducing every current Python class or internal abstraction.
- Runtime JSON/TSV loading in the C library.

## Proposed Repository Layout

```text
include/
  merkmal.h

src/
  merkmal.c
  registry.c
  system.c
  unicode.c
  geometry.c
  engine_categorical.c
  engine_valued.c
  model_format.c
  generated/
    builtin_data.c
    builtin_data.h
  internal/
    alloc.h
    error.h
    string_pool.h
    feature_set.h
    utf8.h

tools/
  generate_c_data.py
  convert_model.py

tests/
  golden/
  c/
    test_descriptive.c
    test_phoible.c
    test_unicode.c
    test_geometry.c

python/
  pyproject.toml
  merkmal/
    __init__.py
    _native.*       # built extension
    py.typed
  src/
    merkmal_module.c
```

The old Python implementation has been removed from the active codebase.
Python support is now the native wrapper calling the C library.

## Public C API Shape

The public header should use opaque handles and explicit status codes.

```c
typedef struct mk_registry mk_registry;
typedef struct mk_system mk_system;
typedef struct mk_string_list mk_string_list;
typedef struct mk_feature_set mk_feature_set;

typedef enum {
    MK_OK = 0,
    MK_ERR_INVALID_ARGUMENT,
    MK_ERR_UNKNOWN_SYSTEM,
    MK_ERR_UNKNOWN_GRAPHEME,
    MK_ERR_UNSUPPORTED_MODEL,
    MK_ERR_PARSE,
    MK_ERR_OOM
} mk_status;
```

Initial functions:

```c
mk_status mk_registry_new_builtin(mk_registry **out);
void mk_registry_free(mk_registry *registry);

mk_status mk_registry_list_systems(
    const mk_registry *registry,
    mk_string_list **out
);

mk_status mk_registry_get_system(
    const mk_registry *registry,
    const char *name,
    const mk_system **out
);

mk_status mk_system_name(const mk_system *system, const char **out);
mk_status mk_system_kind(const mk_system *system, const char **out);

mk_status mk_system_is_segment(
    const mk_system *system,
    const char *utf8_grapheme,
    int *out
);

mk_status mk_system_grapheme_features(
    const mk_system *system,
    const char *utf8_grapheme,
    mk_feature_set **out
);

mk_status mk_system_segment_distance(
    const mk_system *system,
    const char *utf8_a,
    const char *utf8_b,
    double *out
);

mk_status mk_normalize_grapheme(
    const char *utf8_in,
    char **utf8_out
);

mk_status mk_segment_ipa(
    const char *utf8_in,
    mk_string_list **out
);

void mk_free_string(char *s);
void mk_string_list_free(mk_string_list *list);
void mk_feature_set_free(mk_feature_set *features);
```

Guidelines:

- Inputs are UTF-8 `const char *`.
- Returned strings and collection objects are owned by the caller unless the
  function explicitly documents borrowed lifetime.
- Unknown graphemes return `MK_ERR_UNKNOWN_GRAPHEME`, not a sentinel distance.
- Python can translate status codes into exceptions, `None`, or compatibility
  behavior.

## Runtime Model Format

Built-ins should be generated into C tables. Runtime model support can use a
simple line-oriented format that is easy to diff, grep, inspect, and generate.

Example categorical model:

```text
@model descriptive
@type categorical
@geometry clements-hume

feature consonant major
feature vowel major

grapheme p consonant voiceless bilabial stop
grapheme b consonant voiced bilabial stop

class PLOSIVE consonant stop
```

Example valued model:

```text
@model phoible
@type valued
@geometry clements-hume

features syllabic consonantal sonorant continuant voice

grapheme p - + - - -
grapheme b - + - - +
```

This format should initially be an internal/generated interchange format. After
the C slice is proven, decide whether to document it as a stable user-facing
format.

## Roadmap

### Milestone 0: Planning And Test Baseline

- [x] Create a branch for the C core rewrite plan.
- [x] Record architectural decisions in this document.
- [x] Verify current Python tests pass.
- [x] Verify pre-retirement Go tests pass.
- [x] Add an issue/task list or project board if desired.

### Milestone 1: C Project Skeleton

- [x] Move toward C-centered repository layout.
- [x] Add `include/merkmal.h`.
- [x] Add `src/` and internal headers.
- [x] Add build system.
- [x] Vendor or configure `utf8proc`.
- [x] Add a minimal C test runner.
- [x] Add CI entries for C build/tests.

Build system candidates:

- CMake: strong ecosystem support, good fit for Python `scikit-build-core`,
  common for native libraries.
- Meson: clean C developer experience, good dependency handling.

Recommendation: use CMake because it aligns well with `abi3` wheel builds.

### Milestone 2: Core Runtime Infrastructure

- [x] Implement allocation helpers.
- [x] Implement status/error conventions.
- [x] Implement owned string and string-list containers.
- [x] Implement feature-set container.
- [x] Implement UTF-8 iteration helpers where `utf8proc` does not directly
  cover the local need.
- [x] Implement grapheme normalization with full `utf8proc` parity.
- [x] Implement IPA segmentation and tone-digit merging.
- [x] Add initial Unicode/grapheme C smoke tests.

### Milestone 3: Generated Built-In Data

- [x] Write `tools/generate_c_data.py`.
- [x] Generate data for `descriptive`.
- [x] Generate data for `phoible`.
- [x] Generate shared geometry data for `clements-hume`.
- [x] Generate shared diacritic data.
- [x] Keep generated output deterministic and readable enough for review.
- [x] Decide whether generated files are checked in or created during build.

Recommendation: check generated C files in initially. It simplifies packaging
and makes diffs visible while the generator matures.

### Milestone 4: Geometry

- [x] Port flattened feature-node representation needed for sound distance.
- [x] Port public feature-distance calculation.
- [x] Port geometry-weighted sound-distance calculation for categorical systems.
- [x] Port weight preset support needed by the first slice.
- [x] Add C golden tests against first-slice system distance fixtures.
- [x] Add C golden tests against `tests/golden/geometry_*.tsv`.
  - [x] `geometry_distances.tsv`
  - [x] `geometry_sound_distances.tsv`
  - [x] `geometry_weighted_distances.tsv`

### Milestone 5: Categorical Engine Slice

- [x] Implement categorical system construction from generated data.
- [x] Implement `descriptive` lookup.
- [x] Implement true C-side diacritic decomposition for categorical features covered by current fixtures.
- [x] Implement tie-bar and sequence normalization behavior needed for parity.
- [x] Implement geometry-compatible categorical segment distance.
- [x] Add C golden tests for `descriptive_features.tsv`.
- [x] Add C golden tests for `descriptive_distances.tsv`.

### Milestone 6: Valued Engine Slice

- [x] Implement valued system construction from generated data.
- [x] Implement `phoible` lookup.
- [x] Implement valued diacritic effects.
- [x] Implement geometry-compatible valued segment distance.
- [x] Add C golden tests for `phoible_features.tsv`.
- [x] Add C golden tests for `phoible_distances.tsv`.

### Milestone 7: Python Wrapper Slice

- [x] Replace Python top-level slice with a thin native wrapper.
- [x] Keep package name `merkmal`.
- [x] Preserve familiar top-level calls for the slice:
  - `list_systems`
  - `get_features`
  - `is_segment`
  - `distance`
  - `normalize`
  - `segment_ipa`
- [x] Use CPython Limited API / `abi3`.
- [x] Build local wheel.
- [x] Run Python tests for the supported slice.

### Milestone 8: Expand Built-In Systems

- [x] Add `broad`.
- [x] Add `distinctive`.
- [x] Add `pbase-hc`.
- [x] Add `pbase-jfh`.
- [x] Add `pbase-spe`.
- [x] Add `pbase-uftc`.
- [x] Expand C golden tests.
- [x] Expand Python wrapper coverage.

### Milestone 9: Runtime Model Input

- [x] Implement parser for the line-oriented model format.
- [x] Add structured validation errors.
- [x] Add C API for registering a caller-supplied model into a registry.
- [x] Add CLI utility or test fixture that loads a runtime model.
- [x] Decide whether to document the format as public.

### Milestone 10: Retire Old Implementations

- [x] Remove or archive old Python implementation modules.
- [x] Remove Go module and Go data copies.
- [x] Update README and documentation.
- [x] Update changelog with intentional compatibility breaks.
- [x] Keep golden fixtures as cross-checks for the C implementation.

## Phase 2 Decisions

- Keep generated C data checked in for source releases and Python wheel builds.
- Require system `utf8proc` for release/distribution builds; keep the fallback
  path for development, bootstrap, and the first WebAssembly spike.
- Do not vendor `utf8proc` for native C distribution in Phase 2.
- Support both static and shared library builds through the standard CMake
  `BUILD_SHARED_LIBS` option.
- Keep the Python package native-only, with a minimal `Registry` wrapper rather
  than the old Python object model.
- Target the raw C ABI for the first WebAssembly surface; defer a JS wrapper
  until downstream requirements are clearer.

## Immediate Next Tasks

1. Continue release validation on additional compilers/platforms.
2. Rewrite native-first tutorials to replace `docs/legacy_python/`.

## Phase 2 Roadmap: C Distribution First

### Milestone 11: C Install And Consumer Integration

- [x] Add install rules for `merkmal.h` and `libmerkmal`.
- [x] Export a CMake package with `merkmal::merkmal`.
- [x] Generate and install `merkmal.pc` for pkg-config consumers.
- [x] Add public symbol export annotations for shared-library builds.
- [x] Add a small public status-to-string helper.
- [x] Add install-tree smoke tests for CMake consumers.
- [x] Add install-tree smoke tests for pkg-config consumers.
- [x] Verify both static and shared library builds.

### Milestone 12: Release Build Policy

- [x] Decide whether release builds require system `utf8proc`.
- [x] Decide whether to vendor `utf8proc` for WebAssembly and platforms without
  good system packages.
- [x] Document supported compiler/platform matrix.
- [x] Add sanitizer CI jobs for the C library.
- [x] Add release artifact notes for source tarballs and Python wheels.

### Milestone 13: Source Data Pipeline Cleanup

- [x] Make top-level `models/`, `geometries/`, `diacritics/`, and `typologies/`
  the canonical source data.
- [x] Rewrite `tools/generate_c_data.py` so it reads source data directly.
- [x] Remove the archived Python runtime after the direct parser is complete.
- [x] Regenerate C data and verify deterministic output.

### Milestone 14: Native Wrapper Ergonomics

- [x] Expose `node_weights` in Python `distance`.
- [x] Expose `merge_tone_digits` and `segment_ipa_merged`.
- [x] Add a minimal Python registry wrapper for runtime model text.
- [x] Keep unsupported legacy object-model APIs out of the top-level package.

### Milestone 15: WebAssembly Spike

- [x] Add an Emscripten build preset or documented build command.
- [x] Verify built-in models work without filesystem access.
- [x] Decide whether to ship raw C ABI only or a tiny JS wrapper.
- [x] Add a browser or Node smoke test for normalization, features, and distance.
