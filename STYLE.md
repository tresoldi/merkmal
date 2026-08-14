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

# That the library exports the public API and nothing else. Also runs as part
# of ctest; this form is for checking an archive built somewhere else.
scripts/check_public_symbols.sh build/dev/libmerkmal.a

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
include/merkmal.h    the entire public surface: 32 symbols, all mk_-prefixed
src/                 everything else, prefixed mki_ (see "Two prefixes")
  diagnose.c         why a grapheme was refused
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
  cluster.c          scoring a segment written as more than one part
  geometry.c         geometry tables, feature predicates, and the three
                     scorers behind mki_scorer_for
  model_text.c       the runtime-model parser -- the only untrusted-input parser
  registry.c         registry lifecycle
  system.c           the public system operations
  generated/         builtin_data.c is emitted, never edited by hand;
                     builtin_data.h describes its shape and is maintained here
```

Dependencies point inward and the graph is acyclic: `system.c` and `registry.c`
sit above `cluster.c`, which sits above `resolver.c`, which sits above
`geometry.c` and `inventory.c`, which sit above the generated data. A module
includes the headers it uses; there is deliberately no shared `internal.h`,
because there was one and every module ended up compiling against every other
module's private contract.

Two files are larger than the rest and stay that way on purpose. `resolver.c`
is a synthesis pipeline whose stages share 49 file-scope helpers; splitting it
would export those instead of hiding them. `geometry.c` holds the scorers with
the tables they read for the same reason. Both are recorded in
[REFACTORING_PLAN.md](REFACTORING_PLAN.md), whose figures for them are older
than the files.

Cluster scoring was the one part of `system.c` that met neither test — its six
helpers were used by cluster scoring and nothing else, so moving them to
`cluster.c` hid them rather than exporting them.

## Two prefixes

**`mk_` is the public contract. `mki_` is anything else with external linkage.**

The rule is about linkage, not spelling for its own sake. The 108 `static`
helpers keep their `mk_` names: they have no external linkage, cannot collide
with anything, and are already scoped by the file they sit in. Renaming them
would be churn that teaches a reader nothing the `static` did not.

C has one symbol namespace, so a consumer linking `libmerkmal.a` sees every
external name in it, not just the declared ones. The archive holds 107: the 32
in `include/merkmal.h` and 75 internal ones — the resolution and scoring seams,
the cluster policy, the string helpers, the compiled tables. They all used to
be spelled `mk_`, which meant this file's claim that `mk_` marked the public
surface was true only by intention. `mki_resolve` and `mki_streq` now say what
they are.

A shared build hides the internals by visibility either way; the static build,
which is the default and what the pkg-config consumer links, does not.

`ctest -R public_symbols` enforces it by reading the archive with `nm` and
comparing against the header, so a new cross-module helper named `mk_something`
fails the suite rather than quietly widening the API.

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

The rule the types must keep: **a pointer a struct owns is not `const`.** Two
structs hold both kinds side by side and both spell the difference out —
`mk_resolution` pairs the borrowed `features` with the owned `owned_features`,
and `mk_system` pairs the borrowed `owned.name` with the allocation
`owned_name`. `mk_builtin_entry` did not, and its two destructors cast `const`
away twenty-eight times to free what they owned. Nothing was wrong at any of
the twenty-eight, but a type that needs a cast to be freed is a type the
compiler cannot check. `-Wcast-qual` is on so that it stays checkable; when it
fires, the fix is the type, not the cast.

Casts that *add* `const` are fine and appear at a few call boundaries, because
C will not convert `char **` to `const char *const *` on its own.

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
- `MK_ERR_NO_TREE_PATH` — the question was well-formed and the geometry tree
  has no answer to it. `mk_feature_distance` is defined over tree features
  only; it used to write `999` into the out-parameter and return `MK_OK`, which
  is the second error channel this section exists to rule out.
- `MK_ERR_DUPLICATE_SYSTEM` — the model parsed and validated; the registry
  already holds that name. Its own status rather than `MK_ERR_INVALID_ARGUMENT`
  because that value already means "you passed a null pointer" on the same
  call, and a name collision is something a caller can act on.

That split is what lets `mk_system_is_segment` stay total while
`mk_system_grapheme_features` reports why.

Use `goto cleanup` for multi-resource error paths. It is used throughout and is
the expected idiom here.

## The scoring seam

Three scorers, one interface, one place that chooses:

| scorer | reads | systems |
|---|---|---|
| `leaf` | the compiled geometry's leaves, node groups and ordered scales | `broad`, `descriptive`, every runtime model, and `mk_sound_distance`'s system-free path |
| `scalar` | the system's declared `scalar_dimensions`, plus ordered scales | `distinctive` |
| `valued` | the system's geometry map and `name=state` cells | `phoible`, the four `pbase-*` |

`mki_scorer_for` in `geometry.c` is the only code that decides. It used to be
two tests on two different fields in two files — a `kind` test in `system.c`
chose categorical against valued, and a test on `scalar_dimension_count` buried
inside the categorical body chose scalar against leaf. The second was invisible
from `geometry.h` and it picked the scorer for the default system.

Every scorer reports `coverage`, because the caller cannot know which one it
reached and must not have to. Coverage is relative to the *system's* declared
dimensions, not to the segments, so a segment compared with itself is below 1.0
whenever it has a gap. `mk_system_segment_distance_ex` used to assert 1.0 on the
scorers' behalf; it no longer speaks for a body it does not look inside.

Identity is the caller's question, not a scorer's — a scorer sees
`mk_feature_view` and never a grapheme. The same-grapheme shortcut in `system.c`
is an optimization for the score, so it applies only when no coverage was asked
for.

## Clusters carry their parts

A cluster — a diphthong, an untied affricate, a geminate — is synthesized by
resolving each part and composing the results, so every part has been resolved
by the time the cluster exists. `mk_cluster_component` carries that forward.

It used to keep only the spelling, and `cluster.c`'s ancestor in `system.c`
re-resolved it: comparing `ai³³` with `au` ran the whole seam four more times on
strings that had just been resolved. Storing a part costs one small array copy
when it came from an inventory, because the array the lookup filled is the
resolution's own stack scratch; a synthesized part's array moves across for
free. `bench/baseline.txt` records what that trade measured at.

The five numbers cluster scoring composes with are data, in the geometry file's
`cluster_policy`, for the same reason `tier_policy` is. The rules that apply
them — which part is the nucleus, when the length penalty is waived — stay in
`cluster.c`, because they read both segments.

## Buffers

Fixed-size stack buffers must either check `snprintf`'s return value or carry a
comment proving they cannot truncate. Both exist in the tree; both are
intentional. A truncated *diagnostic* is acceptable and says so. A truncated
*feature label* is not: it is a different feature, one the geometry does not
know, which silently contributes nothing to any distance.

Never advance through UTF-8 with the length a lead byte claims. `mki_utf8_step`
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
  imposes, because `mki_inventory_find` binary-searches them. Sorting by Python
  `str` would order by code point and the search would miss rows that exist.
  `test_resolution` checks the emitted order.
- A row may carry at most `MK_MAX_ENTRY_FEATURES` features. The resolver
  reserves that many pointer slots inside every `mk_resolution`, so raising it
  costs stack on every lookup. The generator refuses to emit a wider row, and
  reads the limit out of the header rather than keeping its own copy.
- The pool is emitted in 2 KB chunks. C99 only requires string literals of
  4,095 characters and adjacent literals concatenate into one.
- Duplicate graphemes within a system are rejected: a binary search may return
  either row where the old linear scan always returned the first.

`builtin_data.h` is the shape and the generator only fills it in. Every emitted
struct goes through `c_struct`, which reads the header's fields and refuses an
initializer that has drifted from them, so the two cannot disagree:

- The header is authoritative for **field order**. Initializers used to be
  positional, which made order load-bearing across two languages —
  `entry_graphemes` and `entry_feature_at` are both `const unsigned int *` and
  adjacent, so transposing either side compiled clean under `-Werror` and
  returned the wrong row for every lookup.
- The header is authoritative for **which fields exist**. Designating them
  fixes the order problem but opens another, because
  `-Wmissing-field-initializers` does not fire for designated initializers: a
  new field would be zero-filled in silence. `c_struct` fails the generator
  instead.
- The header is authoritative for **`MK_MAX_ENTRY_FEATURES`**. It was a second
  `= 64` in the generator held in step by a comment, and raising only that one
  emits a row wider than the array the resolver reserves.

`check_generated_data.py` proves the emitter is deterministic. It cannot prove
it is right — it compares the emitter against its own output — so what keeps the
two languages honest is reading the header rather than restating it.

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
- A scoring change belongs in `tests/c/test_scoring.c`, which asserts *which*
  scorer a system selects for the same reason, and covers
  `mk_system_segment_distance_ex`.
- A fuzz-found crash belongs in `tests/c/test_malformed.c` too, so `ctest`
  replays it forever rather than only whoever runs the fuzzer.

## Platform assumptions

Linux and macOS with GCC or Clang are the tested targets; CI runs Linux. The
header carries an `_WIN32`/MSVC export branch that nothing currently tests.

`utf8proc` is optional. With it, normalization adds a final NFC or NFD pass;
without it, the compiled decomposition table does the work alone. Both profiles
run the full test suite in CI. The fallback is what WebAssembly ships.
