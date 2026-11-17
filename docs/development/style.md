# Conventions of the C sources

The conventions of `include/` and `src/`, for a person or a coding agent
changing them. They apply [the house standard](house-standard.md) to this
project; [AGENTS.md](../../AGENTS.md) is the short checklist, and
[docs/development/adr/](adr/) records where merkmal departs from the standard and why.
Each rule here is already true of the tree; where a script or a test enforces
it, that is named.

The language is C99 in strict ISO mode (`CMAKE_C_EXTENSIONS OFF`), with no
compiler extensions outside the `MK_API` visibility macro in `merkmal.h`.

## Where things live

| Path | What it is |
| --- | --- |
| `include/merkmal.h` | The entire public API. The only header that is installed. |
| `src/*.c`, `src/*.h` | One module per `.c`; its header, if any, is internal. |
| `src/generated/` | Tables generated from `data/models/`, `data/geometries/` and `data/diacritics/`. Never edit by hand. |
| `python/src/merkmal_module.c` | The CPython extension. Uses `merkmal.h` only. |
| `web/merkmal_wasm.c` | The WebAssembly adapter (JSON in, JSON out). Uses `merkmal.h` only. |
| `tests/c/` | C tests. Most link the public library; the internal-seam tests link `merkmal_internal`. |
| `tests/fuzz/` | libFuzzer harnesses and their corpora. |
| `tools/` | Generators for `src/generated/`, and the checks: generated data, public symbols, formatting, static analysis, model validation. |

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
  `merkmal.h`. `tools/check_public_symbols.sh` (the `public_symbols` ctest)
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
  `mki_resolve` and `mki_parse_model_text` zero their output once their
  arguments are valid, so a clear after any later failure is safe; on
  MK_ERR_INVALID_ARGUMENT the output is untouched.
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

## Comments

Comments must preserve information that is not obvious from the code.
Prioritize intent, invariants, ownership, lifetime, units, safety
assumptions, and reasons for non-obvious implementation choices. Do not
narrate the code. If a comment merely restates what well-named code already
says, delete the comment or improve the code instead.

When code looks unnecessarily strange, either simplify it or explain why it
must remain strange.

### What to comment

Always comment, where the code cannot say it:

- **Ownership and lifetime.** Who frees it, and until when a borrowed pointer
  stays valid: "Borrowed from the registry; valid until mk_registry_free."
- **Invariants**, especially the ones the type system cannot express: "`features`
  aliases `owned_features` exactly when `owned_features` is non-NULL."
- **Nullability**, when NULL is accepted or returned and that is not the
  obvious default.
- **Units and ranges**: a byte offset rather than a code-point index, a share
  in `[0, 1]`, a Chao level from 0 to 5.
- **Safety assumptions** behind pointer arithmetic, fixed buffers and size
  calculations: "Safe because `one` has room for a four-byte code point and
  its terminator, and mki_utf8_step never returns more than four."
- **Why simpler-looking code is wrong**: "Not strlen: the length is
  authoritative and the input may contain NUL." "A struct copy is not enough:
  `features` may alias the source's inline array."
- **Non-obvious algorithm choices** and intentional complexity: why a binary
  search over an inventory sorted at build time, why a fixed array of three
  slots is enough for a cluster's components.
- **Data layouts and table formats**: what a cell code or a packed offset
  means. A short ASCII layout is welcome.
- **Workarounds, platform quirks and compatibility paths**, with what would
  let them go.

Usually do not comment: assignments, loops whose purpose is plain, ordinary
error checks, trivial getters, declarations whose names already say it.

### Where comments go

- **Headers say the contract.** In `merkmal.h` and in internal headers:
  ownership, lifetime, nullability, units, length semantics, every status a
  function can return and what each means, and whether the call is total.
- **`.c` files say the implementation**: invariants, algorithm choices,
  workarounds, safety assumptions, and why the code is shaped the way it is.
  Do not repeat the header's contract there.
- A substantial `static` function gets a short comment before it when its
  inputs, ownership on success, or state on failure are not obvious from the
  signature:

  ```c
  /* The longest run of tokens at `index` that the system reads as one
   * segment. On MK_OK *segment is owned by the caller and *span says how
   * many tokens it consumed; on failure both are untouched. */
  ```

### Public declarations

In `merkmal.h`, lead with the contract, then give at most a few lines of
rationale. When the reasoning needs more room, put it in `docs/guide/c-api.md` and
point there ("See docs/guide/c-api.md, Distance with coverage."). Name tags such as
`@param` and `@return` are not used: they repeat the signature. Say only what
the signature cannot.

### History and figures

- **Present tense, the reason only.** A comment says why the code is the way
  it is now, not what it used to be. "Off-tree features return
  MK_ERR_NO_TREE_PATH: a sentinel distance would look like a real one", not
  "This used to write 999 and return MK_OK". What changed, and when, belongs
  in the commit message and `CHANGELOG.md`.
- **A measured figure stays only if it justifies a decision**, and it names
  what it was measured on, so it can be re-checked: "33,275 tokens
  (<dataset> <release>, counted by <script>)". Otherwise the figure goes in
  `CHANGELOG.md` or `docs/`, and the comment keeps the conclusion.

### Form

- `/* ... */` only; no `//`. A comment of more than one line is one block,
  with each continuation line starting ` * `.
- `/**` opens a comment on a public declaration in `merkmal.h`, so editors
  and documentation tools pick it up. Use `/*` everywhere else.
- Prefer one short block to several one-line comments about the same thing.
- Sections in a long file get a plain `/* Tokenization */`, not a banner. A
  file that needs many sections probably needs splitting into modules.
- Name magic numbers (`#define`, `enum`), and comment what a bit or a code
  means when a name cannot carry it.
- A `TODO` says when or why it becomes actionable, with an issue number when
  there is one, as in `TODO(#<issue>): drop the 1.0 aliases once no caller
  uses them`. A bare "TODO: improve" is not a TODO.

## Formatting

Formatting is mechanical: `.clang-format` at the root decides it, and it is
not a review topic. `tools/check_format.sh` fails on any first-party C file
that differs from it, and `tools/check_format.sh --fix` reformats in place.
Generated tables are excluded by `.clang-format-ignore`.

Never restyle code you are not otherwise changing. A reformat goes in a commit
of its own, never mixed with a functional change. Where hand layout carries
meaning (a table with one case per line, a literal split on purpose), wrap it
in `/* clang-format off */` and `/* clang-format on */`, with the reason in a
comment just above.

## Generated data

`src/generated/builtin_data.c`, `src/generated/cc-by/builtin_data.c` and
`src/generated/unicode_data.c` are written by `tools/generate_c_data.py`
(both data profiles) and `tools/generate_unicode_data.py`.
`src/generated/builtin_data.h` is hand-written, and the generator reads its
struct fields and limits from it, so a layout change is made there first.

```sh
python tools/generate_c_data.py                     # full profile
python tools/generate_c_data.py --profile cc-by     # cc-by profile
python tools/check_generated_data.py              # CI: committed == generated
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
| Formatting | `tools/check_format.sh` (`--fix` to apply) |
| Static analysis | `tools/run_static_analysis.sh` (GCC `-fanalyzer` and `clang --analyze`; any output beyond the headers is a new finding) |
| Fuzzing | `CC=clang cmake -S . -B build-fuzz -DMERKMAL_BUILD_FUZZERS=ON -DMERKMAL_BUILD_TESTS=OFF`, then `build-fuzz/fuzz_<target> tests/fuzz/corpus/<target>` |
| Python | `pip install . pytest && python -m pytest python/tests -q` |

The warning set is in `CMakeLists.txt` as `MERKMAL_C_WARNINGS`. The library
and every test compile clean under it with GCC and Clang. `-Werror` is opt-in
(`MERKMAL_WERROR`) so that downstream builds are not held to it.

`tests/c/test_alloc_failure.c` fails every allocation in turn inside the main
entry points (Linux only). A new code path that allocates should be reachable
from it; under ASan it catches a leak or a double free on a failure path that
no ordinary input reaches.

## Adding to the public API

1. Declare it in `merkmal.h` with `MK_API`, under a `/**` comment that leads
   with the contract: ownership, lifetime, nullability and every status it
   can return (see Comments).
2. Keep the existing signature shape: inputs first, then `out` parameters,
   returning `mk_status`.
3. Test it through the public header, in `tests/c/test_smoke.c` or a test of
   its own.
4. Describe it in `docs/guide/c-api.md` and add a `CHANGELOG.md` entry. Mark any
   behavior change **Breaking**.
5. Bind it in `python/src/merkmal_module.c` if Python callers need it.

A new source file goes in `MERKMAL_SOURCES` in `CMakeLists.txt`. `setup.py`
picks up `src/*.c` by itself.
