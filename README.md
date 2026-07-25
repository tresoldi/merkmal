# merkmal

`merkmal` is a C99 phonological feature library for computational
historical linguistics. It maps IPA graphemes to phonological feature
sets or valued feature vectors and computes geometry-weighted segment
distances.

The repository is being reorganized around a small C ABI. The C library
contains compiled-in built-in models and can also accept caller-supplied
runtime models. Python support is now a native wrapper around the C
library. The old pure-Python implementation remains archived in the tree only
for data generation and parity scaffolding while the wrapper surface is
completed. Go support has been retired.

## Current Status

The C implementation currently covers the high-level operations selected
for the first native slice:

- built-in registry creation and system lookup
- listing built-in systems
- grapheme feature lookup
- segment validity checks
- categorical and valued segment distance
- geometry feature distance
- set-based sound distance with weight presets
- IPA normalization and segmentation
- Chao tone digit merging
- registering a simple caller-supplied categorical model from text

Built-in C systems currently include:

- `broad`
- `descriptive`
- `distinctive`
- `pbase-hc`
- `pbase-jfh`
- `pbase-spe`
- `pbase-uftc`
- `phoible`

`classfeat` is intentionally not part of the first native C slice, but
the generated-data and API layout leave room for it.

## Build

From the repository root:

```sh
cmake -S . -B build/c-debug -DCMAKE_BUILD_TYPE=Debug
cmake --build build/c-debug
ctest --test-dir build/c-debug --output-on-failure
```

`utf8proc` is detected with `pkg-config` when available. Development
builds can use the built-in IPA-focused fallback. To require the system
library:

```sh
cmake -S . -B build/c-debug -DMERKMAL_REQUIRE_UTF8PROC=ON
```

## C Example

```c
#include "merkmal.h"

#include <stdio.h>

int main(void) {
    mk_registry *registry = NULL;
    const mk_system *system = NULL;
    mk_feature_set *features = NULL;
    double distance = 0.0;

    if (mk_registry_new_builtin(&registry) != MK_OK) {
        return 1;
    }
    if (mk_registry_get_system(registry, "descriptive", &system) != MK_OK) {
        mk_registry_free(registry);
        return 1;
    }
    if (mk_system_grapheme_features(system, "pʰ", &features) == MK_OK) {
        for (size_t i = 0; i < mk_feature_set_size(features); i++) {
            puts(mk_feature_set_get(features, i));
        }
        mk_feature_set_free(features);
    }
    if (mk_system_segment_distance(system, "p", "b", &distance) == MK_OK) {
        printf("%f\n", distance);
    }
    mk_registry_free(registry);
    return 0;
}
```

See [docs/c-api.md](docs/c-api.md) for the public C surface and
[docs/runtime-model-format.md](docs/runtime-model-format.md) for the
line-oriented caller-supplied model format.

## Python Wrapper

The Python package builds `merkmal._native` with the CPython Limited API
and exposes the supported high-level operations from the top-level
`merkmal` module.

```sh
python -m pip install -e python
python -m pytest python/tests -q
python -m build python --wheel
```

The wheel is built as `cp312-abi3` for broad CPython compatibility.

```python
import merkmal

print(merkmal.list_systems())
print(merkmal.get_features("pʰ"))
print(merkmal.distance("p", "b"))
print(merkmal.feature_distance("voiced", "voiceless"))
print(merkmal.segment_ipa("tʰoŋ⁵⁵"))
```

The Python package is intentionally native-only; unsupported legacy helper
APIs are no longer exported from `merkmal`.

## Runtime Models

The C registry can accept a complete categorical model supplied as text:

```text
@model toy
@type categorical
@geometry clements-hume
grapheme X consonant voiceless bilabial stop
grapheme Y vowel open front unrounded
```

```c
mk_registry_add_model_text(registry, model_text);
```

The format is intentionally line-oriented, UTF-8, and grep-friendly.
Only categorical models are currently public in this format.

## Repository Structure

```text
merkmal/
├── include/                public C headers
├── src/                    C99 implementation and generated built-in data
├── tools/                  data generators for compiled-in C tables
├── tests/c/                C tests
├── tests/golden/           parity fixtures for the native implementation
├── tests/legacy_python/    archived tests for the pre-C Python implementation
├── models/                 source model data used by generators
├── geometries/             source geometry data
├── diacritics/             source diacritic/tone/modifier mappings
├── typologies/             legacy Python typology data
├── python/                 native Python wrapper
├── tools/legacy_python/    archived Python implementation for generators
└── docs/                   C API and format documentation
```

## License

MIT. See [LICENSE](LICENSE).
