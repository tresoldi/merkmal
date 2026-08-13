# Working on merkmal's C core

What a contributor needs to know that the code does not say for itself. For the
public API contract see [docs/c-api.md](docs/c-api.md); for the model text
format see [docs/runtime-model-format.md](docs/runtime-model-format.md).

## Commands

```sh
# Build and test. This is the configuration to use by default.
cmake -S . -B build/dev -DCMAKE_BUILD_TYPE=Debug -DMERKMAL_WERROR=ON
cmake --build build/dev
ctest --test-dir build/dev --output-on-failure

# The fallback Unicode profile -- the one WebAssembly ships. Selects it even
# where libutf8proc is installed, which MERKMAL_REQUIRE_UTF8PROC=OFF does not.
cmake -S . -B build/fallback -DMERKMAL_USE_UTF8PROC=OFF -DMERKMAL_WERROR=ON

# Sanitizers. One at a time; the option takes address or undefined.
cmake -S . -B build/asan -DCMAKE_BUILD_TYPE=Debug -DMERKMAL_ENABLE_SANITIZER=address

# Static analysis. Accepted findings are listed in the script.
scripts/run_static_analysis.sh

# Fuzzing. Clang only; see fuzz/README.md.
CC=clang cmake -S . -B build/fuzz -DMERKMAL_BUILD_FUZZERS=ON -DMERKMAL_BUILD_TESTS=OFF
cmake --build build/fuzz
./build/fuzz/fuzz_segment fuzz/corpus/segment -max_total_time=300

# Benchmarks. Update bench/baseline.txt only with a change meant to move it.
bench/bench_footprint.sh
bench/bench_lookup.sh

# Python wrapper.
python -m pip install -e ".[dev]" --no-build-isolation
python -m pytest python/tests tools/tests -q
```

Regenerating the compiled data after changing anything under `models/`,
`geometries/`, or `diacritics/`:

```sh
python tools/generate_c_data.py
python scripts/check_generated_data.py     # proves the emitter is deterministic
```

Changing a distance or a feature set is a **data contract change**. The golden
fixtures will fail; that is the point. Regenerate them deliberately and review
the diff as data:

```sh
python scripts/regenerate_golden.py --check   # report drift, change nothing
python scripts/regenerate_golden.py           # rewrite the fixtures
```

## Where things live

```
include/merkmal.h    the entire public surface: 30 symbols, all mk_-prefixed
src/
  status.c           mk_status -> string
  vector.c           fixed-width numeric feature vectors
  strings.c          strdup, streq, has_prefix, append_text, free_items
  string_list.c      the library's only collection type
  utf8.c             UTF-8 encoding mechanics, Unicode-level classification
  ipa.c              IPA orthographic classification: vowel letters, boundaries
  normalize.c        decomposition, composition, the two normalization entries
  tone.c             Chao tone: reading it, merging it onto a nucleus, splitting
  tokenize.c         orthographic tokenization
  inventory.c        reading inventory rows, whichever storage a system uses
  resolver.c         the resolution seam and every synthesizer behind it
  geometry.c         geometry tables, feature predicates, and both scorers
  model_text.c       the runtime-model parser -- the only untrusted-input parser
  registry.c         registry lifecycle
  system.c           the public system operations, and cluster scoring policy
  generated/         emitted by tools/generate_c_data.py; never edit by hand
```

Dependencies point inward and the graph is acyclic: `system.c` and `registry.c`
sit above `resolver.c`, which sits above `geometry.c` and `inventory.c`, which
sit above the generated data. A module includes the headers it uses; there is
deliberately no shared `internal.h`, because there was one and every module
ended up compiling against every other module's private contract.

Two files are larger than the rest and stay that way on purpose. `resolver.c`
is a synthesis pipeline whose stages share 26 file-scope helpers; splitting it
would export those instead of hiding them. `geometry.c` holds the scorers with
the tables they read for the same reason. Both are recorded in
[REFACTORING_PLAN.md](REFACTORING_PLAN.md).

## Ownership

The naming carries it, and it is consistent:

| suffix | meaning |
|---|---|
| `_new`, `_new_builtin` | allocates; caller owns the result |
| `_free` | releases what the matching constructor produced; tolerates NULL |
| `_adopt` | takes ownership of what the caller passes, including on failure paths |
| `_from_borrowed` | copies; the caller keeps its own |
| `_clear` | releases what a struct owns and re-zeroes it; safe to repeat |

A `const char *` returned through an out-parameter is **borrowed** unless the
function name or its comment says otherwise. Borrowed strings from a system or
registry are valid as long as that registry is. Owned strings are freed with
`mk_string_free`, owned lists with `mk_string_list_free`.

`mk_resolution` is the one place the rule needs stating: `features` aliases
`owned_features` exactly when `owned_features` is non-NULL, and on the
inventory paths it instead aliases the struct's own `inline_features` array.
`resolver.h` spells this out; read it before touching resolution.

## Errors

One model. Every fallible function returns `mk_status` and writes its result
through an out-parameter. There is no `errno`, no global error state, no
`abort()`, and no `assert()` anywhere in the library — untrusted input is
reported, never asserted.

The distinction that matters:

- `MK_ERR_UNKNOWN_GRAPHEME` — nothing recognized the input. This is also how
  the synthesizers hand off to one another.
- `MK_ERR_PARSE` — something recognized the shape and rejected the content: an
  over-long Chao run, a feature label too long to represent.

That split is what lets `mk_system_is_segment` stay total while
`mk_system_grapheme_features` reports why.

Use `goto cleanup` for multi-resource error paths. It is used throughout and is
the expected idiom here.

## Buffers

Fixed-size stack buffers must either check `snprintf`'s return value or carry a
comment proving they cannot truncate. Both exist in the tree; both are
intentional. A truncated *diagnostic* is acceptable and says so. A truncated
*feature label* is not: it is a different feature, one the geometry does not
know, which silently contributes nothing to any distance.

Never advance through UTF-8 with the length a lead byte claims. `mk_utf8_step`
returns the smaller of the claimed length and the bytes actually present. The
unbounded form is gone because nineteen call sites used it and every one of
them could read past the terminator.

## The compiled data

`src/generated/builtin_data.c` is emitted, never edited. It holds the eight
built-in inventories as offsets into an interned string pool and 16-bit feature
ids, not as pointers — 260,000 pointer slots cost 2.08 MB and one relocation
each to name 35 KB of text, which dominated the WebAssembly payload.

Consequences worth knowing before changing the emitter:

- Rows are sorted by the grapheme's **UTF-8 bytes**, the order `strcmp`
  imposes, because `mk_inventory_find` binary-searches them. Sorting by Python
  `str` would order by code point and the search would miss rows that exist.
  `test_resolution` checks the emitted order.
- A row may carry at most `MK_MAX_ENTRY_FEATURES` features. The resolver
  reserves that many pointer slots inside every `mk_resolution`, so raising it
  costs stack on every lookup. The generator refuses to emit a wider row.
- The pool is emitted in 2 KB chunks. C99 only requires string literals of
  4,095 characters and adjacent literals concatenate into one.
- Duplicate graphemes within a system are rejected: a binary search may return
  either row where the old linear scan always returned the first.

## Footprint and performance

`bench/baseline.txt` is committed. Change it only alongside work meant to move
it, so a diff there is always an argued change. Two rules, both learned here:

- Measure before optimizing. The inventory index was built because the scan
  measured 25.9 µs on phoible, not because a linear scan looks slow.
- Say what did not move. Sorting the inventory halved tokenization and left
  pair scoring almost unchanged; the remaining time is the scorer's own walk
  over leaves, node groups and ordered scales.

## Adding a test

- A behavioral change belongs in the golden fixtures, produced by
  `regenerate_golden.py` through the Python wrapper and replayed by the C
  tests. The producer and the consumer are deliberately separate, so no test
  can rewrite the values it is checked against.
- A malformed or hostile input belongs in `tests/c/test_malformed.c`. Copy it
  into a heap buffer sized exactly to its bytes: the same bytes in a string
  literal read into adjacent rodata and pass silently.
- A resolution path belongs in `tests/c/test_resolution.c`, which asserts
  *which* path resolved a grapheme, not merely that one did.
- A fuzz-found crash belongs in `tests/c/test_malformed.c` too, so `ctest`
  replays it forever rather than only whoever runs the fuzzer.

## Platform assumptions

Linux and macOS with GCC or Clang are the tested targets; CI runs Linux. The
header carries an `_WIN32`/MSVC export branch that nothing currently tests.

`utf8proc` is optional. With it, normalization adds a final NFC or NFD pass;
without it, the compiled decomposition table does the work alone. Both profiles
run the full test suite in CI. The fallback is what WebAssembly ships.
