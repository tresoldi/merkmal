# merkmal C99 Refactoring Plan

Written against `~/work/modern-c99-refactoring-guide-for-coding-agents.md`,
against the tree at `60523c4`.

Scope and constraints agreed before writing:

- **API/ABI:** free rein until 1.0. Signature changes are allowed with
  CHANGELOG entries and migration notes.
- **Priorities, in order:** module structure, then footprint work, then
  hardening (fuzzing and static analysis).
- **Scope:** everything C-adjacent — `src/`, `include/`, `tests/c/`,
  `python/src/merkmal_module.c`, and `tools/generate_c_data.py`.
- **Performance:** WebAssembly size and startup matter; throughput does not
  drive the plan.

---

## 1. Repository assessment

### Size and shape

| Part | Lines | Note |
|---|---|---|
| `src/generated/builtin_data.c` | 300,698 | generated, checked in |
| `src/resolver.c` | 1,746 | largest hand-written module |
| `src/unicode.c` | 1,073 | four responsibilities in one file |
| `src/geometry.c` | 652 | geometry tables + both scorers |
| `src/registry.c` | 555 | registry + runtime-model text parser |
| `src/system.c` | 474 | public system operations |
| `src/internal.h` | 281 | shared types + shared helpers |
| `src/string_list.c`, `src/status.c` | 156 | |
| `include/merkmal.h` | 213 | the whole public surface |
| `python/src/merkmal_module.c` | 898 | CPython extension, abi3 |
| `tests/c/*` | ~1,750 | smoke, golden ×2, geometry, resolution |
| `tools/generate_c_data.py` | 855 | emits the generated data |

Hand-written C is about 4,800 lines. This is a small, well-tended codebase, not
a legacy rescue.

### Build system

CMake 3.20, `C_STANDARD 99`, `C_STANDARD_REQUIRED ON`, `C_EXTENSIONS OFF` — the
standard is explicit and strict, exactly as the guide asks. Debug, Release,
shared, and two sanitizer configurations all build from one `CMakeLists.txt`.
Install exports a CMake package config and a `.pc` file, and CI verifies both
by building consumers against the installed artifacts. Reproducibility from a
clean checkout is already covered.

`utf8proc` is an optional dependency selected by `MERKMAL_REQUIRE_UTF8PROC`,
guarded in code by `MK_HAVE_UTF8PROC` at three sites in `unicode.c`.

### C dialect and warnings

Current flags: `-Wall -Wextra -Wpedantic` (`/W4` on MSVC).

I compiled all seven first-party translation units at the guide's recommended
baseline:

```
-std=c99 -Wall -Wextra -Wpedantic -Wshadow -Wconversion \
-Wstrict-prototypes -Wmissing-prototypes
```

**Zero warnings**, every file. The stricter baseline is already met; it is
simply not enforced. That makes the ratchet free, which is unusual and worth
banking immediately.

### Public API

One header, `include/merkmal.h`, self-contained (`stddef.h` only), 26 exported
symbols, all `mk_`-prefixed, all behind `MK_API` with
`C_VISIBILITY_PRESET hidden`. `mk_registry`, `mk_system`, and `mk_string_list`
are opaque. There are no pointer typedefs. Ownership is documented in
`docs/c-api.md` and in header comments, and the naming distinguishes borrowed
from owned returns.

Gaps, all minor:

- Predicates return `int` through out-parameters — `mk_system_is_segment(…, int *out)`.
  `<stdbool.h>` appears nowhere in the project.
- Destructor naming is inconsistent: `mk_string_list_free` and
  `mk_registry_free` versus `mk_free_string`.
- Constructor naming mixes `_new_builtin` and `_new` with no `_create`.
- `mk_sound_distance` takes two independent pointer+count pairs — the exact
  case §8 of the guide describes as wanting a view type.

### Major modules and dependency direction

```
        public API (merkmal.h)
                 |
      +----------+----------+
      |          |          |
   system.c   registry.c  unicode.c
      |          |          |
      +---> resolver.c <----+
                 |
            geometry.c
                 |
        generated/builtin_data.c
```

Acyclic, pointing inward. `resolver.c` sits behind a documented seam
(`resolver.h`) that names how a grapheme was resolved — an unusually good piece
of interface design, and the model the rest of the plan should follow.

The two problems are file granularity, not direction:

1. **`unicode.c` is four modules.** UTF-8 primitives (`mk_utf8_char_len`,
   `mk_utf8_codepoint`, `mk_is_combining_mark`), NFD/NFC normalization
   (`mk_decompose`, `mk_compose_known_pair`, 128 lines), tokenization
   (`mk_segment_ipa`, 243 lines), and Chao tone handling (`mk_chao_level`,
   `mk_merge_tone_digits`, `mk_split_tone`) share one file for no reason beyond
   history.
2. **`internal.h` is the `common.h` the guide warns about in §24.** It carries
   16 data-table struct definitions, 28 `extern` declarations of generated
   tables, string helpers, UTF-8 helpers, geometry predicates, and the scoring
   seam. Every module includes all of it, so every module compiles against
   every other module's contract.

`resolver.c` at 1,746 lines with functions of 198, 170, and 152 lines is large
but internally coherent — it is a synthesis pipeline, and each synthesizer is a
separate `static`. It splits along existing seams.

### Memory ownership

Direct `malloc`/`free`, no custom allocator, no arena — appropriate for the
lifetimes here. `goto cleanup` is used where it belongs (40 sites in
`resolver.c`, 5 in `system.c`, 4 in `registry.c`) and nowhere else.
`mk_resolution` documents its aliasing invariant precisely: `features` aliases
`owned_features` exactly when the latter is non-NULL. `mk_string_list_adopt`
exists specifically so callers that already own an array hand it over rather
than copy-and-free. Ownership is in good shape.

### Error handling

One model: `mk_status` with seven values, returned by every fallible function,
out-parameters for results. No `errno`, no `abort()`, no `assert()` anywhere in
the library, no global error state, no magic values. The recent removal of
`NAN`-as-error-signal from the scorers closed the last second channel.
`MK_ERR_UNKNOWN_GRAPHEME` versus `MK_ERR_PARSE` carries a real distinction
(not recognized versus recognized-and-rejected) and the header explains it.

This milestone is done. It does not need a milestone.

### Global state

**None in the library.** No mutable file-scope variables in `src/`. This was a
deliberate design goal in `C_REWRITE_PLAN.md` for WebAssembly and threading,
and it holds. The only statics are in the Python extension
(`default_registry`, `mk_py_error`), documented as build-once-never-mutate with
`m_size = -1` declared accordingly.

### Buffers and strings

Everything is NUL-terminated `const char *`. For a library whose inputs are IPA
graphemes this is defensible, and the guide's §8 does not demand view types
where they hurt readability. Internally `mk_feature_view` already pairs
pointer and count for the scoring seam.

The risk is elsewhere: **fixed-size stack buffers with `snprintf`**, at
`registry.c:289` (`char buffer[512]`), `registry.c:382` (`[256]`),
`resolver.c:366` (`[96]`), `resolver.c:384` (`[128]`), `resolver.c:464`
(`[32]`), `resolver.c:994` (`[8]`), and a family of `char one[5]` codepoint
buffers across `unicode.c` and `resolver.c`. `snprintf` truncates silently, and
`resolver.c:384` builds feature labels of the form `move-%s-%s-%s` from feature
names — a truncated label is not a crash, it is a wrong feature name that
scores against nothing. No return value of `snprintf` is checked.

### Test coverage

Strong. Five C test binaries, 708 lines of Python tests, golden fixtures
produced by the Python wrapper and replayed by the C tests (the producer and
consumer were split deliberately in `687a087`). CI additionally checks that
generated data matches its sources, that models and provenance validate, that
the contrast baseline holds, that `NOTICE` matches the manifests, and that
golden fixtures match the build.

One coverage hole: **`MK_HAVE_UTF8PROC=0` is never exercised by `ctest`.** All
three C jobs pass `MERKMAL_REQUIRE_UTF8PROC=ON`. The fallback path — three
`#if` branches covering normalization and segmentation NFD — is built only by
the WASM job, and tested there by a 90-line smoke program that checks six
calls. That is the configuration WebAssembly ships, and it is the least tested
one.

### Tooling baseline

| Check | Status |
|---|---|
| GCC build | CI, Debug and Release |
| Clang build | absent |
| Extended warnings | clean but unenforced |
| `-Werror` | absent |
| AddressSanitizer | CI |
| UndefinedBehaviorSanitizer | CI |
| Static analysis | absent |
| Fuzzing | absent |
| Benchmarks | absent |
| Size/footprint tracking | absent |
| macOS / Windows / MSVC | absent, though the header carries an `_WIN32` branch |

### Footprint: the dominant finding

`builtin_data.c` compiled at `-O2`:

```
.rodata          2,450,200 bytes
.rodata.str1.1      35,029 bytes   <- all the actual string content
relocations        281,322
```

**The string data is 35 KB. The object is 2.5 MB.** The gap is pointer arrays:
9,728 inventory entries hold roughly 260,000 `const char *` slots, eight bytes
each, every one of them a relocation. The feature vocabulary across all entry
tables is 376 distinct labels.

In a static native binary this is merely wasteful. In WebAssembly every one of
those 281,322 relocations is data-segment initialization work at instantiate
time, and the pointer table is carried in the `.wasm` payload. This is the
single largest lever available for WASM size and startup, it is entirely
mechanical, and it lives in a generated file behind one Python script.

### Architectural risks

1. Footprint is 70× the information content (above).
2. The `MK_HAVE_UTF8PROC=0` profile is the shipped WASM profile and the least
   tested configuration.
3. Silent `snprintf` truncation produces wrong feature labels rather than
   errors.
4. `internal.h` couples every module to every other module's private contract,
   which will make the data-representation change in Milestone 3 touch more
   files than it should.

---

## 2. Proposed target architecture

Unchanged: the dependency direction, the error model, the absence of global
state, the opaque handles, the CMake layout, the library/CLI separation (there
is no C CLI; the CLI is Python over the library, which is what §26 asks for).

Changed:

```
include/
  merkmal.h                 public surface, unchanged in shape

src/
  status.c
  string_list.c
  strings.c / strings.h     mk_strdup_internal, mk_streq, mk_append_text
  utf8.c / utf8.h           codepoint primitives, char length, prefix tests
  normalize.c / normalize.h NFD/NFC, decomposition, source conventions
  tone.c / tone.h           Chao levels, merge, split
  tokenize.c / tokenize.h   mk_segment_ipa and the cluster grammar
  resolver.c / resolver.h   the seam (unchanged interface)
  synth_diacritics.c        \
  synth_cluster.c            > resolver's synthesizers, one file each
  synth_complex.c           /
  geometry.c / geometry.h   geometry tables and predicates
  score.c / score.h         the two scorers
  registry.c / registry.h   registry lifecycle
  model_text.c / model_text.h   the runtime-model parser
  system.c                  public system operations
  generated/
    builtin_data.c / .h     offset-based tables, zero relocations
    builtin_data_types.h    the table struct definitions

fuzz/
  fuzz_model_text.c
  fuzz_segment.c
  fuzz_resolve.c
  fuzz_normalize.c

bench/
  bench_footprint.sh        .wasm bytes, data segment, relocation count
  bench_lookup.c            microbenchmark, for evidence not for gating
```

`internal.h` disappears. Each module publishes a narrow private header; the
generated data publishes its own types. A module includes what it uses.

The data representation becomes: one pooled string blob, one interned feature
vocabulary, and tables of `uint32_t` offsets and `uint16_t` feature IDs. Names
are recovered at the lookup boundary as borrowed pointers into the blob, so
nothing above the storage layer changes representation and no allocation is
added.

---

## 3. Milestone plan

Milestones 0 through 2 of the guide's generic sequence (baseline,
characterization, compiler hygiene) are substantially already satisfied here,
as are its Milestones 5, 7, 8, and 9 (ownership, error model, global state,
core/IO separation). They are not repeated as work. What follows is what this
repository actually needs.

---

### Milestone A — Bank the baseline, and measure footprint

**Objective.** Enforce the discipline the code already has, and start
measuring the thing the project is about to optimize.

**Current evidence.** All seven translation units compile clean at
`-Wshadow -Wconversion -Wstrict-prototypes -Wmissing-prototypes`, but CI asks
for none of them. There is no record of `.wasm` size, data-segment size, or
relocation count, so Milestone C would have nothing to compare against. The
`MK_HAVE_UTF8PROC=0` profile runs no `ctest`.

**Concrete changes.**

1. Add `-Wshadow -Wconversion -Wstrict-prototypes -Wmissing-prototypes` to the
   non-MSVC branch of `target_compile_options`.
2. Add `MERKMAL_WERROR` (default `OFF`), enabled in CI only. Downstream
   consumers never get `-Werror`, per §16.
3. Add a `c-fallback` CI job: `-DMERKMAL_REQUIRE_UTF8PROC=OFF` with the
   dependency deliberately absent, running the full `ctest` suite. Skip any
   test that legitimately requires utf8proc by name, and list those in the job.
4. Add `bench/bench_footprint.sh`: builds the Emscripten target, records
   `.wasm` byte size, data-segment size, and (for the native object) `size -A`
   plus `readelf -r | wc -l`. Write results to `bench/baseline.txt`, committed.
5. Add a CI step that runs it and prints the numbers. Do not gate on them yet.

**Affected files.** `CMakeLists.txt`, `.github/workflows/ci.yml`,
`bench/bench_footprint.sh`, `bench/baseline.txt`, `docs/` build notes.

**Tests.** No new behavioral tests. The fallback job is itself the new
coverage; expect it to surface real failures on first run, since that path has
only ever been smoke-tested.

**Tooling.** GCC, Emscripten, `size`, `readelf`.

**Risks.** Low, with one honest caveat: the fallback job may fail immediately.
That is the milestone working, not the milestone breaking. Fix what it finds
here rather than deferring — a fallback bug found now is a bug that does not
get blamed on Milestone B's file moves.

**Compatibility.** None. No source, header, or behavior change.

**Acceptance criteria.**

- CI builds clean at the extended warning set with `-Werror`.
- `ctest` passes with `MK_HAVE_UTF8PROC=0`, or each exclusion is named and
  justified in the workflow.
- `bench/baseline.txt` records `.wasm` size, data-segment size, native
  `.rodata` size, and relocation count for a Release build.

**Depends on.** Nothing.

---

### Milestone B — Split `internal.h` and `unicode.c`

**Objective.** Make each `.c` file a module with a narrow private header, so
the data-representation change in Milestone C touches storage and nothing else.

**Current evidence.** `internal.h` is 281 lines carrying 16 struct definitions,
28 generated-table `extern`s, and four unrelated families of helper prototypes;
all seven modules include it. `unicode.c` is 1,073 lines spanning UTF-8
primitives, normalization, tokenization, and Chao tone. `geometry.c` holds both
the geometry tables and both scorers. `registry.c` holds both registry
lifecycle and a 192-line text parser.

**Concrete changes.**

1. Move the table struct definitions and the generated `extern`s from
   `internal.h` into `src/generated/builtin_data_types.h`, included by
   `builtin_data.h`.
2. Split `unicode.c` into `utf8.c`, `normalize.c`, `tokenize.c`, `tone.c`, each
   with a header declaring only what other modules call. `mk_utf8_codepoint`,
   `mk_is_combining_mark`, and `mk_is_map_mark` stay `static` in `utf8.c` if
   only `utf8.c` uses them — check before promoting.
3. Move `mk_strdup_internal`, `mk_streq`, and `mk_append_text` into
   `strings.{c,h}`. `string_list.c` keeps only the collection.
4. Move `mk_score_categorical` and `mk_score_valued` into `score.{c,h}`;
   `geometry.{c,h}` keeps tables, predicates, and `mk_feature_distance`.
5. Move the runtime-model parser out of `registry.c` into `model_text.{c,h}`.
   `mk_registry_add_model_text_ex` stays in `registry.c` as the public entry
   and calls into it.
6. Split the resolver's synthesizers into `synth_diacritics.c`,
   `synth_cluster.c`, and `synth_complex.c` behind one internal header.
   `resolver.c` keeps `mk_resolve`, the inventory paths, and
   `mk_resolution_clear`. Break the 198-line `mk_decompose_diacritics` and the
   170-line `mk_synthesize_cluster` into named steps as part of the move.
7. Delete `internal.h`.
8. Update `MERKMAL_SOURCES` and the `test_resolution` target, which compiles
   the source list directly.

**Affected files.** All of `src/`, `CMakeLists.txt`, and any test including
`internal.h`.

**Tests.** No new behavior, so no new behavioral tests. The existing suite is
the regression net, and it is adequate for a pure move: golden distances,
golden features, geometry, resolution paths, and 1,034 lines of smoke. Run the
full matrix including the new fallback job after each split, not once at the
end.

**Tooling.** GCC and Clang if available; both sanitizer configurations;
`check-generated-data`.

**Risks.** Medium, all mechanical: a `static` accidentally promoted to external
linkage, or a helper duplicated rather than moved. Mitigate by comparing
`nm -g` output on the built library before and after — the exported set must be
byte-identical, still 26 symbols. Do each split as its own commit.

**Compatibility.** No public header change. ABI unchanged; verify with `nm -g`.

**Acceptance criteria.**

- `internal.h` no longer exists.
- No source file exceeds ~700 lines; no function exceeds ~120 lines.
- Each module's header declares only what other modules call.
- `nm -g` on the shared library lists the same 26 symbols as before.
- Full CI matrix green.

**Depends on.** Milestone A (for the warning ratchet and the fallback job to
catch mistakes during the moves).

---

### Milestone C — Compact the generated data

**Objective.** Cut WebAssembly payload and instantiate-time work by removing
the pointer tables from the compiled data.

**Current evidence.** `builtin_data.o` at `-O2`: 2,450,200 bytes of `.rodata`
against 35,029 bytes of string content, and 281,322 relocations. 9,728
inventory entries reference roughly 260,000 `const char *` slots drawn from a
vocabulary of 376 distinct feature labels.

**Concrete changes.**

1. Teach `tools/generate_c_data.py` to emit:
   - `mk_string_pool` — one `static const char[]` blob holding every distinct
     grapheme and feature label, NUL-separated.
   - `mk_feature_names[]` — `uint32_t` offsets into the pool, indexed by
     feature ID. 376 entries today; `uint16_t` IDs leave ample headroom.
   - Entry tables as `{uint32_t grapheme_offset; uint32_t feature_start;
     uint16_t feature_count;}`, with feature IDs in one flat `uint16_t` array
     per system.
2. Apply the same treatment to the geometry tables, diacritic maps, tone marks,
   and decompositions.
3. Add accessors in `builtin_data.h`: `mk_pool_string(uint32_t)`,
   `mk_feature_name(uint16_t)`, `mk_entry_features(entry, const char **scratch)`.
4. **Keep everything above the storage layer working in `const char *`.** The
   resolver synthesizes feature labels at runtime (`move-%s-%s-%s`,
   `tone-%s-%d`) that are not in the compiled vocabulary, so a fully interned
   pipeline would need a runtime intern table — which would make registries
   mutable on read and forfeit the concurrent-read guarantee
   `C_REWRITE_PLAN.md` commits to. Expanding IDs to borrowed pool pointers at
   lookup time keeps `mk_feature_view`, both scorers, and the whole resolver
   unchanged, adds no allocation, and still removes every relocation. Expansion
   needs a caller-provided scratch array; entries carry at most a few dozen
   features, so a fixed stack array with a documented bound is enough — assert
   the bound at generation time, in Python, where it is checkable.
5. Regenerate; `scripts/check_generated_data.py` proves the emitter is
   deterministic.

**Affected files.** `tools/generate_c_data.py`, `src/generated/*`,
`src/resolver.c` and `src/registry.c` at their lookup sites, `src/geometry.c`.

**Tests.**

- Golden fixtures are the regression net and must not change by one bit. If
  `regenerate_golden.py --check` passes, the representation change was
  behavior-neutral.
- Add a C test asserting `mk_feature_name` round-trips every ID to the same
  string the previous representation held — generate the expected list from
  Python into a fixture, so the test does not check the emitter against itself.
- Add a generator unit test in Python for pool construction and ID assignment.
  `tools/generate_c_data.py` is 855 lines with no test of its own beyond the
  round-trip check.

**Tooling.** `bench/bench_footprint.sh` before and after; both sanitizers
(the scratch-array bound is exactly what ASan catches); Emscripten.

**Risks.** Highest-risk milestone in the plan. The scratch-array bound is a
buffer contract, and getting it wrong is a stack overflow in the hot path.
Mitigations: assert the bound in Python at generation time; assert it again in
C in debug builds; run the whole suite under ASan before merging. A secondary
risk is that `uint16_t` feature IDs constrain future runtime models — runtime
models are parsed into their own owned tables and do not share the compiled
vocabulary, so they are unaffected; state this in the header.

**Compatibility.** No public API change. Runtime model behavior unchanged.
Binary artifacts change substantially — note it in the CHANGELOG for packagers.

**Acceptance criteria.**

- Native `.rodata` for `builtin_data.o` under 700 KB, from 2.45 MB.
- Relocation count in `builtin_data.o` under 1,000, from 281,322.
- `.wasm` size and instantiate time recorded against the Milestone A baseline
  with the deltas stated in the CHANGELOG.
- Every golden fixture byte-identical.
- Sanitizer jobs green.

**Depends on.** Milestone A (baseline numbers), Milestone B (so the change
lands in storage rather than smearing across a shared `internal.h`).

---

### Milestone D — Sorted lookup, gated on measurement

**Objective.** Replace the linear grapheme scan, but only if the numbers say it
is worth the generator complexity.

**Current evidence.** `mk_find_entry` (`resolver.c:9`) walks the whole entry
array calling `mk_streq` — up to 9,728 comparisons per lookup, and the
longest-match tokenizer issues several lookups per token. No benchmark exists,
so the cost is unmeasured.

**Concrete changes.**

1. Add `bench/bench_lookup.c`: tokenize and score a representative wordlist,
   report time per segment. Record a baseline.
2. If and only if lookup is a measurable share of that time: emit entry tables
   sorted by grapheme in the generator, replace `mk_find_entry` with a binary
   search over pool offsets, and assert sortedness at generation time.
3. If it is not: record the measurement in `bench/baseline.txt`, write one
   paragraph saying so, and close the milestone unimplemented.

**Affected files.** `bench/bench_lookup.c`, and conditionally
`tools/generate_c_data.py` and `src/resolver.c`.

**Tests.** Golden fixtures unchanged. Add a test that a grapheme sorting
adjacent to a multi-byte neighbor still resolves — byte-wise ordering over
UTF-8 is what the search assumes, and the generator must sort the same way C
compares.

**Tooling.** The benchmark; sanitizers.

**Risks.** Low, and the milestone is explicitly allowed to end in no code. The
one real trap is a sort-order mismatch between Python and C: sort on raw bytes
in both, and assert it in the generated file.

**Compatibility.** None.

**Acceptance criteria.** A recorded measurement, and either a binary search
with proven-identical results or a written decision not to build one.

**Depends on.** Milestone C.

---

### Milestone E — Fuzzing and the truncation audit

**Objective.** Attack the untrusted-input boundaries automatically, and close
the silent-truncation class by hand.

**Current evidence.** Four entry points consume arbitrary text with no fuzzing:
`mk_registry_add_model_text` (a hand-written line parser), `mk_segment_ipa`,
`mk_resolve`, and `mk_normalize_grapheme`. All four are already free of global
state and filesystem access, so they satisfy the guide's precondition for
fuzzing without any preparatory work. Seven fixed-size stack buffers are filled
with `snprintf` and no return value is checked; `resolver.c:384` composes
`move-%s-%s-%s` feature labels from feature names into `char label[128]`, where
truncation yields a plausible-looking wrong label rather than an error.

**Concrete changes.**

1. Add `fuzz/` with libFuzzer harnesses for the four entry points, each calling
   the library directly.
2. Add a `MERKMAL_BUILD_FUZZERS` CMake option, off by default, Clang-only.
3. Seed corpora from the golden fixtures and the model files under `models/`.
4. Add a short CI job running each harness for a bounded time under ASan+UBSan.
5. Audit every `snprintf` site: check the return value, and return
   `MK_ERR_INVALID_ARGUMENT` (or grow the buffer) on truncation. `char one[5]`
   codepoint buffers are correct by construction given
   `mk_utf8_char_len` ≤ 4 — document that rather than changing it.
6. Add a static analysis job: `gcc -fanalyzer` and `clang --analyze`, baseline
   recorded, high-confidence findings fixed, suppressions narrow and commented.

**Affected files.** `fuzz/*`, `CMakeLists.txt`, `.github/workflows/ci.yml`,
`src/registry.c`, `src/resolver.c`, `src/model_text.c`.

**Tests.** Every crash found becomes a fixture under `tests/c/fuzz_regress/`
replayed by a normal `ctest` test. Add a direct test for truncation: a model
text with a pathologically long feature name must fail with a status, not
succeed with a truncated label.

**Tooling.** Clang, libFuzzer, ASan, UBSan, `gcc -fanalyzer`, `clang --analyze`.

**Risks.** Fuzzing a 1,700-line resolver will find things. Budget for fixes.
Time-box the CI job so it stays a smoke check; run longer campaigns manually.

**Compatibility.** Truncation fixes change failure behavior on inputs that
previously succeeded incorrectly. That is a fix, and belongs in the CHANGELOG
as one.

**Acceptance criteria.**

- Four harnesses build and run clean for the CI budget.
- Every `snprintf` either checks its result or carries a comment proving it
  cannot truncate.
- Static analysis runs reproducibly with a recorded baseline and no unexplained
  suppressions.
- Fuzz-found crashes exist as `ctest` regressions.

**Depends on.** Milestone B (harnesses target module seams, not a monolith).

---

### Milestone F — The one breaking API cleanup, then 1.0

**Objective.** Spend the pre-1.0 freedom once, deliberately, in a single
milestone.

**Current evidence.** `<stdbool.h>` is unused; `mk_system_is_segment` reports a
yes/no through `int *out`. Destructors are named `mk_string_list_free`,
`mk_registry_free`, and `mk_free_string`. `mk_sound_distance` takes two
independent pointer+count pairs.

**Concrete changes.**

1. `#include <stdbool.h>` in `merkmal.h`; `mk_system_is_segment(…, bool *out)`.
   Internal predicates (`mk_streq`, `mk_has_prefix`, `mk_geometry_knows_feature`)
   become `bool` too.
2. Rename `mk_free_string` to `mk_string_free` for consistency with the other
   destructors.
3. Introduce `mk_feature_view` — already the internal type — as a public value
   struct, and give `mk_sound_distance` an overloadless two-view signature.
   Keep the existing four-argument form as a documented wrapper for one release
   if any consumer needs it; drop it at 1.0 otherwise.
4. Audit the header against §30: every function documents ownership,
   nullability, and error behavior. Most already do.
5. Migration notes in the CHANGELOG; bump to 1.0.0.

**Affected files.** `include/merkmal.h`, all of `src/`,
`python/src/merkmal_module.c`, `docs/c-api.md`, `tests/c/*`,
`tests/c/install_consumer/main.c`, `tests/wasm/smoke.c`.

**Tests.** Existing suite plus a compile-only test that `merkmal.h` builds
standalone under `-std=c99 -Wall -Wextra -Wpedantic` from an empty translation
unit and from C++ (the header carries `extern "C"`).

**Tooling.** `nm -g` diff to confirm the exported set is exactly what was
intended.

**Risks.** Low technically, higher socially — this is the change downstream
feels. Isolate it in its own milestone and its own release, exactly as §29 asks.

**Compatibility.** Breaking, intentionally, once. `bool` in an out-parameter is
an ABI change on any platform where `_Bool` and `int` differ in size, which is
most; it must ride a SOVERSION bump.

**Acceptance criteria.**

- `merkmal.h` compiles standalone in C99 and C++.
- Every public function's contract is documented.
- CHANGELOG carries migration notes for each break.
- Python wrapper and WASM smoke updated; full matrix green.

**Depends on.** Milestones B, C, E — break the API once, after the internals
have stopped moving.

---

### Milestone G — Python extension and generator

**Objective.** Hold the C code outside `src/` to the same standard.

**Current evidence.** `merkmal_module.c` is 898 lines with its own conventions:
a `PY_UTF8_SLOTS 4` macro and a `py_utf8_args` structure that exists to
consolidate cleanup ladders — good, but the fixed slot count is exactly the
kind of implicit bound §6 of the guide warns about. It is not built under
sanitizers in CI. `tools/generate_c_data.py` is 855 lines whose only test is a
round-trip byte comparison against its own output, which cannot catch a
consistently wrong emission.

**Concrete changes.**

1. Add a CI job building the extension with ASan+UBSan and running
   `python/tests` under it (`LD_PRELOAD` the ASan runtime).
2. Assert `PY_UTF8_SLOTS` sufficiency at compile time
   (`_Static_assert` is C11; a negative-array-size idiom keeps it C99), or make
   the slot count a per-call parameter.
3. Add unit tests for `generate_c_data.py`: pool construction, ID assignment,
   sort order, and the feature-count bound Milestone C introduces.
4. Bring the extension under the same warning flags as the library.

**Affected files.** `python/src/merkmal_module.c`, `setup.py`,
`.github/workflows/ci.yml`, `tools/generate_c_data.py`, new
`tools/tests/test_generate_c_data.py`.

**Tests.** As above, plus the existing 708-line wrapper suite.

**Tooling.** ASan/UBSan under CPython, `ruff`, `mypy`, `pytest`.

**Risks.** CPython under ASan reports leaks from the interpreter itself; use a
suppression file and document it rather than disabling LeakSanitizer wholesale.

**Compatibility.** None to the Python API.

**Acceptance criteria.** Extension is sanitizer-clean under its own suite; the
generator has direct tests; both build at the library's warning level.

**Depends on.** Milestone C (the generator tests describe the new emission).

---

### Milestone H — Contributor contract

**Objective.** Write down what the previous milestones established, so it
survives.

**Concrete changes.** A `STYLE.md` covering: the module map and what belongs
where; the ownership vocabulary (`_new`/`_free`/`_adopt`/`_clear`, borrowed
versus owned returns); the `mk_status` conventions and the
`UNKNOWN_GRAPHEME`/`PARSE` distinction; build, test, sanitizer, fuzz, and
benchmark commands; the generated-data pipeline and the footprint budget with
its current numbers; the `MK_HAVE_UTF8PROC` profiles and which one WASM ships.

**Affected files.** `STYLE.md`, `docs/c-api.md`, `README.md`, `CLAUDE.md`
(there is none today; one belongs here).

**Acceptance criteria.** A new contributor can answer the guide's §37 questions
from the repository alone.

**Depends on.** Everything above.

---

## 4. Deferred work

Attractive, and deliberately not scheduled:

- **Portability matrix.** Clang, macOS, Windows/MSVC. The header already
  carries an `_WIN32` export branch that nothing tests. Worth doing, but you
  ranked it below the three priorities above, and it competes with nothing on
  this list — add it whenever a downstream consumer asks. Adding Clang alone to
  the existing Linux job is nearly free and could ride along with Milestone A
  if convenient.
- **Arena allocation.** The resolver allocates a handful of small strings per
  synthesized segment with clear lifetimes. An arena would be abstraction ahead
  of need (§25, §34).
- **Bitset feature representation.** With 376 labels, a 512-bit set per entry
  would make scoring word-wise. It is a bigger change than Milestone C, it
  breaks the "features are a list of names" model that the resolver depends on
  for synthesized labels, and it should wait for a benchmark that demands it.
- **Runtime JSON/TSV model loading in C.** Explicitly a non-goal in
  `C_REWRITE_PLAN.md`; the text format covers it.
- **A JavaScript wrapper API.** `docs/webassembly.md` correctly defers this
  until the C ABI settles — which is Milestone F.
- **Thread-safety documentation and testing.** Registries are immutable after
  construction and the design intends concurrent reads, but nothing tests it.
  A TSan job is cheap; it is just not urgent while there are no threaded
  consumers.
- **Splitting `builtin_data.c` per system for incremental linking.** Only
  matters if WASM builds want to drop unused systems, which is a different
  feature (selectable model sets) with its own API question.

---

## 5. First recommended milestone

**Milestone A.**

It is the smallest, it is nearly free — the warning ratchet is a two-line CMake
change against code that already passes — and it produces the two things
everything else needs: a footprint baseline that makes Milestone C's claims
checkable, and a `MK_HAVE_UTF8PROC=0` test run that turns the shipped WASM
configuration from smoke-tested into tested.

Expect the fallback job to fail on first run. Finding that now, before any file
moves, is precisely the point.
