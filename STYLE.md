# Contributing to the C core

The conventions of `include/` and `src/`, for a person or a coding agent
changing them. Each rule here is already true of the tree; where a script or
a test enforces it, that is named.

The language is C99 in strict ISO mode (`CMAKE_C_EXTENSIONS OFF`), with no
compiler extensions outside the `MK_API` visibility macro in `merkmal.h`.

## Where things live

| Path | What it is |
| --- | --- |
| `include/merkmal.h` | The entire public API. The only header that is installed. |
| `src/*.c`, `src/*.h` | One module per `.c`; its header, if any, is internal. |
| `src/generated/` | Tables generated from `models/`, `geometries/` and `diacritics/`. Never edit by hand. |
| `python/src/merkmal_module.c` | The CPython extension. Uses `merkmal.h` only. |
| `web/merkmal_wasm.c` | The WebAssembly adapter (JSON in, JSON out). Uses `merkmal.h` only. |
| `tests/c/` | C tests. Most link the public library; the internal-seam tests link `merkmal_internal`. |
| `fuzz/` | libFuzzer harnesses and their corpora. |
| `tools/` | Generators for `src/generated/`. |
| `scripts/` | Checks: generated data, public symbols, static analysis, model validation. |

Modules, from the bottom up. Each depends only on the layers below it, and
there are no include cycles:

| Layer | Modules |
| --- | --- |
| Mechanics | `array` (checked growth), `strings`, `utf8`, `unicode_norm` |
| Orthography | `normalize`, `ipa`, `tone` |
| Data | `inventory` (row access), `geometry` (geometry and the three scorers), `generated/builtin_data` |
| Resolution | `resolver`: a grapheme to its feature set, by lookup or synthesis |
| Built on resolution | `cluster`, `vector`, `bundle`, `diagnose`, `fingerprint`; `model_text` (the runtime-model parser) |
| Entry points | `system`, `registry`, `tokenize`, `string_list`, `status`, `version` |

A helper used by one module is `static` in that module. Before adding a
shared one, check that a second module needs it; then give it a module named
for what it does, never `utils.c`.

## Names

- **`mk_` and `MK_` are the public contract**, and appear only in
  `merkmal.h`. `scripts/check_public_symbols.sh` (the `public_symbols` ctest)
  fails if the library exports anything else under `mk_`.
- **`mki_` and `MKI_` are internal**: every function or object with external
  linkage that is not public, and every type, enum constant and macro in an
  internal header (`mki_resolution`, `MKI_RESOLVED_INVENTORY`).
- `static` functions and file-local types have no linkage and are not covered
  by the rule. The existing ones are spelled `mk_`; follow the file you are in.
- Include guards are `MK_<FILE>_H`.

## Types

- `bool` (from `<stdbool.h>`) for anything yes/no, including predicates.
  `int` is for numbers: counts that can be negative, `-1`-for-absent indexes,
  comparators, Chao levels.
- `size_t` for sizes, counts and indexes.
- `const` on everything not written through, including `const char *const *`
  for borrowed arrays of borrowed strings.
- No typedef hides a pointer. Opaque types are `typedef struct mk_x mk_x;`
  and are always used as `mk_x *`.
- Stateful public objects are opaque (`mk_registry`, `mk_system`,
  `mk_string_list`, `mk_bundle`). A public struct is a value type with nothing
  to hide (`mk_feature_view`, `mk_diagnosis`, `mk_bundle_comparison`).
- Every internal header includes what its own declarations use.

## Ownership

The rule is in the signature:

- **`T **out` receives an owned object.** Free it with its type's destructor:
  `mk_registry_free`, `mk_string_list_free`, `mk_bundle_free`, or
  `mk_string_free` for a `char *`. Every destructor accepts `NULL`.
- **`const T **out` and `const char *` returns are borrowed.** The header says
  from what and for how long: a system and its name live as long as their
  registry; status strings, kinds and build identity are static.
- **Inputs are borrowed** and must outlive the call only.
- Internal structs filled in place are released with `mki_*_clear`, which
  frees what they own, resets every field, and is safe to call twice.
  `mki_resolve` and `mki_parse_model_text` zero their output before any work,
  so a clear after a failure is always safe.
- `mki_string_list_adopt` takes ownership of the array it is given only on
  success; `mki_string_list_from_borrowed` copies.

## Errors

- Every fallible public function returns `mk_status`, and a failed call
  leaves nothing for the caller to free. Most also set their outputs to `NULL`
  or zero before doing any work; new ones should.
- New statuses are **appended** to `mk_status`, never inserted: callers
  persist the numbers. Give each a label in `src/status.c`.
- A predicate is total. `mk_system_is_segment` answers `false` for input it
  rejects, and the reason comes from the function that resolves it.
- Where the detail matters, an `_ex` variant returns an owned diagnostic, as
  `mk_registry_add_model_text_ex` does. Diagnostics are text for people;
  callers branch on the status.
- No `assert`, `abort` or `exit` in the library. A failed allocation is
  `MK_ERR_OOM`, never a crash.
- A function holding more than one resource cleans up through a single
  `goto cleanup` (or `fail`/`finish`) label. Initialize every owned pointer to
  `NULL` first, so the label can free all of them on every path.
- A magic value is not an error channel. `mk_feature_distance` used to write
  999 and return `MK_OK`; it now returns `MK_ERR_NO_TREE_PATH`.

## Strings, buffers and allocation

- Public text is UTF-8 and NUL-terminated, except where an `_n` variant takes
  a length (`mk_registry_add_model_text_n`). An `_n` variant refuses an
  embedded NUL rather than truncating at it, and so does every Python binding.
- Step through UTF-8 with `mki_utf8_step`, which never steps past the
  terminator, even on a truncated sequence.
- Grow arrays with `mki_grow_array`, which checks `count + extra` and the
  byte size for overflow, and leaves the array untouched if it fails. Do not
  write another `cap * 2` and `realloc`.
- No variable-length arrays (`-Wvla`). Fixed buffers are sized from a stated
  bound (`MKI_MAX_ENTRY_FEATURES`, four bytes per code point).

## Generated data

`src/generated/builtin_data.c`, `src/generated/cc-by/builtin_data.c` and
`src/generated/unicode_data.c` are written by `tools/generate_c_data.py`
(both data profiles) and `tools/generate_unicode_data.py`.
`src/generated/builtin_data.h` is hand-written, and the generator reads its
struct fields and limits from it, so a layout change is made there first.

```sh
python tools/generate_c_data.py                     # full profile
python tools/generate_c_data.py --profile cc-by     # cc-by profile
python scripts/check_generated_data.py              # CI: committed == generated
```

## Building and checking

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug -DMERKMAL_WERROR=ON
cmake --build build && ctest --test-dir build --output-on-failure
```

CI runs each of these, so run the ones your change touches:

| Check | How |
| --- | --- |
| Clang | `CC=clang cmake -S . -B build-clang -DMERKMAL_WERROR=ON` |
| AddressSanitizer / UBSan | `-DMERKMAL_ENABLE_SANITIZER=address` or `=undefined` |
| cc-by data profile | `-DMERKMAL_DATA_PROFILE=cc-by` |
| Shared library | `-DBUILD_SHARED_LIBS=ON` |
| Static analysis | `scripts/run_static_analysis.sh` (GCC `-fanalyzer` and `clang --analyze`; any output beyond the headers is a new finding) |
| Fuzzing | `CC=clang cmake -S . -B build-fuzz -DMERKMAL_BUILD_FUZZERS=ON -DMERKMAL_BUILD_TESTS=OFF`, then `build-fuzz/fuzz_<target> fuzz/corpus/<target>` |
| Python | `pip install . pytest && python -m pytest python/tests -q` |

The warning set is in `CMakeLists.txt` as `MERKMAL_C_WARNINGS`. The library
and every test compile clean under it with GCC and Clang. `-Werror` is opt-in
(`MERKMAL_WERROR`) so that downstream builds are not held to it.

`tests/c/test_alloc_failure.c` fails every allocation in turn inside the main
entry points (Linux only). A new code path that allocates should be reachable
from it; under ASan it catches a leak or a double free on a failure path that
no ordinary input reaches.

## Adding to the public API

1. Declare it in `merkmal.h` with `MK_API`, and document ownership, lifetime,
   nullability and every status it can return.
2. Keep the existing signature shape: inputs first, then `out` parameters,
   returning `mk_status`.
3. Test it through the public header, in `tests/c/test_smoke.c` or a test of
   its own.
4. Describe it in `docs/c-api.md` and add a `CHANGELOG.md` entry. Mark any
   behavior change **Breaking**.
5. Bind it in `python/src/merkmal_module.c` if Python callers need it.

A new source file goes in `MERKMAL_SOURCES` in `CMakeLists.txt`. `setup.py`
picks up `src/*.c` by itself.
