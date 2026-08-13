# Release Policy

This policy applies to the C library, source tarballs, and Python wheels.

## Dependency Policy

Release and distribution builds require `libutf8proc` discovered through
pkg-config:

```sh
cmake -S . -B build/release \
  -DCMAKE_BUILD_TYPE=Release \
  -DMERKMAL_REQUIRE_UTF8PROC=ON
```

The built-in IPA-focused Unicode fallback remains available for local
development, bootstrap builds, and early WebAssembly experiments:

```sh
cmake -S . -B build/dev -DMERKMAL_USE_UTF8PROC=OFF
```

`MERKMAL_USE_UTF8PROC=OFF` selects the fallback outright.
`MERKMAL_REQUIRE_UTF8PROC=OFF` only tolerates it when `libutf8proc` is absent,
so it does not reproduce the fallback on a developer machine that has the
library installed.

The project does not vendor `utf8proc` in the native C distribution. For
WebAssembly, vendoring or `FetchContent` can be reconsidered if the Emscripten
toolchain path makes system pkg-config integration too brittle.

## Supported C Toolchains

The C core is C99 and is expected to build with:

- GCC 11 or newer on Linux
- Clang 14 or newer on Linux and macOS
- Apple Clang from supported macOS/Xcode releases

MSVC is not a release target yet. The source avoids C extensions, but Windows
packaging and DLL import/export testing still need a dedicated pass.

## Release Artifacts

Planned release artifacts:

- source tarball containing generated C data
- native C install tree via CMake install rules
- Python `cp312-abi3` wheels

Source releases should include generated `src/generated/builtin_data.c` so
users do not need Python tooling to build the C library.

## Validation Gates

Before tagging a release:

- C tests pass with `MERKMAL_REQUIRE_UTF8PROC=ON`
- C tests pass for shared-library builds
- install-tree CMake consumer smoke test passes
- install-tree pkg-config consumer smoke test passes
- sanitizer CI passes for the C library
- Python wrapper tests pass
- Python wheel builds and contains only the native wrapper package files
- `python scripts/validate_models.py` passes (schema, exact identifier
  matching, feature coverage, geometry node resolution, provenance)
- `python scripts/contrast_baseline.py --check` passes: no undeclared
  zero-distance pair, no label unable to affect a distance
- `python scripts/generate_notice.py --check` passes, so `NOTICE` matches the
  provenance manifests
- `python scripts/regenerate_golden.py --check` passes

## Data Releases

A data release is separate from a code release, because it changes observable
numbers even when no code changed.

- Any change to `models/`, `geometries/`, or `diacritics/` that moves a
  distance or a feature set is a **major** model version, not a patch. Say so
  in `CHANGELOG.md` with what moved and why.
- Regenerate golden fixtures with `scripts/regenerate_golden.py` and read the
  diff. Do not accept a regenerated fixture without reviewing it: those values
  are the library's contract.
- Re-stamp `models/*/provenance.json` (the input hashes are checked) and
  regenerate `NOTICE`.
- If PHOIBLE data is touched, re-verify it against the release its manifest
  pins:

  ```sh
  scripts/rebuild_phoible_inventory.py <cldf/parameters.csv> --check
  ```

  It is not in CI because it needs the upstream file, and fetching one over the
  network is not something a build should depend on. It is how the 5,272
  miscopied cells were found, so run it rather than trusting that the table
  still says what upstream says.
- Never describe a distribution bundling the CLTS-derived categorical
  inventories, PHOIBLE, or P-base data as MIT-only. The current expression is
  `MIT AND CC-BY-4.0 AND CC-BY-SA-3.0 AND CC-BY-NC-SA-4.0`.
- Fields marked `UNVERIFIED` in a provenance manifest must be established
  before the next data release, not guessed from filenames.
