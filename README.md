# merkmal

`merkmal` is a C99 phonological feature library for computational
historical linguistics. It maps IPA graphemes to phonological feature
sets or valued feature vectors and computes geometry-weighted segment
distances.

The repository is being reorganized around a small C ABI. The C library
contains compiled-in built-in models and can also accept caller-supplied
runtime models. Python support is now a native wrapper around the C
library. The old pure-Python implementation and Go support have been removed
from the active codebase. Historical Python tutorials, notebooks, and research
scripts are archived under `docs/legacy_python/`.

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
- descriptive source-token validation for vowel clusters, selected
  author-defined consonant clusters, precomposed Latin source letters,
  broader affricate spellings, and tone-bearing nuclei
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

## Build And Install

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

For installation as a downstream C dependency:

```sh
cmake -S . -B build/release \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/usr/local \
  -DMERKMAL_REQUIRE_UTF8PROC=ON
cmake --build build/release
cmake --install build/release
```

Installed consumers can use either CMake:

```cmake
find_package(merkmal CONFIG REQUIRED)
target_link_libraries(example PRIVATE merkmal::merkmal)
```

or pkg-config:

```sh
cc example.c $(pkg-config --cflags --libs merkmal) -o example
```

See [docs/distribution.md](docs/distribution.md) for static/shared builds,
custom prefixes, and `utf8proc` dependency notes. See
[docs/release-policy.md](docs/release-policy.md) for release dependency and
validation policy. See [docs/webassembly.md](docs/webassembly.md) for the
initial Emscripten and Node smoke-test path.

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
[docs/distribution.md](docs/distribution.md) for installation and downstream
integration. See
[docs/runtime-model-format.md](docs/runtime-model-format.md) for the
line-oriented caller-supplied model format.

## Python Wrapper

The Python package builds `merkmal._native` with the CPython Limited API
and exposes the supported high-level operations from the top-level
`merkmal` module.

```sh
python -m pip install -e ".[dev]"
python -m pytest python/tests -q
python -m build --sdist --wheel
```

The wheel is built as `cp312-abi3` for broad CPython compatibility.

```python
import merkmal

print(merkmal.list_systems())
print(merkmal.get_features("pʰ"))
print(merkmal.distance("p", "b"))
print(merkmal.feature_distance("voiced", "voiceless"))
print(merkmal.segment_ipa("tʰoŋ⁵⁵"))
print(merkmal.is_segment("aːi³³", system="descriptive"))
```

The Python package is intentionally native-only; unsupported legacy helper
APIs are no longer exported from `merkmal`.

Runtime model registration is exposed through an owned native registry:

```python
registry = merkmal.Registry()
registry.add_model_text("""
@model toy
@type categorical
@geometry clements-hume
grapheme X consonant voiceless bilabial stop
grapheme Y vowel open front unrounded
""")
print(registry.distance("X", "Y", system="toy"))
```

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
├── cmake/                  CMake and pkg-config package templates
├── tools/                  data generators for compiled-in C tables
├── scripts/                active source-data validation and audit scripts
├── tests/c/                C tests
├── tests/golden/           parity fixtures for the native implementation
├── models/                 source model data used by generators
├── geometries/             source geometry data
├── diacritics/             source diacritic/tone/modifier mappings
├── typologies/             source typology data reserved for later C support
├── python/                 native Python wrapper
├── docs/legacy_python/     archived pre-C tutorials, notebooks, and scripts
└── docs/                   C API and format documentation
```

## License

MIT. See [LICENSE](LICENSE).
