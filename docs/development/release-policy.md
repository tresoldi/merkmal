# Release policy

This policy applies to the C library, source distributions and Python
wheels.

## Dependency policy

The C library and the Python extension have no external dependency. Unicode
normalization is compiled in ([installation guide](../guide/installation.md#unicode-normalization);
[ADR 0002](adr/0002-unicode-normalization-is-compiled-in.md)), so a release
artifact normalizes identically wherever it is built.

Release CI runs the normalization oracle, which needs `libutf8proc`:

```sh
cmake -S . -B build/release \
  -DCMAKE_BUILD_TYPE=Release \
  -DMERKMAL_REQUIRE_UTF8PROC=ON
```

A move to a new Unicode version is a data change: `src/generated/unicode_data.c`
is regenerated with an interpreter carrying that version, the oracle is run
against a utf8proc of the same version, and the change is recorded in the
changelog. The Unicode version (`merkmal.UNICODE_VERSION`) is part of what
identifies a result, and is not included in the semantic fingerprint.

## Supported C toolchains

The C core is C99 and is expected to build with:

- GCC 11 or newer on Linux;
- Clang 14 or newer on Linux and macOS;
- Apple Clang from supported macOS and Xcode releases.

MSVC is not a release target. The source uses no C extensions, but Windows
packaging and DLL import and export are not tested.

## Release artifacts

- A source distribution, which includes the generated tables in
  `src/generated/`, so that building the C library needs no Python
  ([ADR 0003](adr/0003-generated-artifacts-are-committed.md)).
- The native C install tree, through the CMake install rules.
- Python wheels for the stable ABI from CPython 3.12 (`cp312-abi3`), built
  for Linux on x86-64 and AArch64 (`.github/workflows/wheels.yml`); other
  platforms install from the source distribution.

## Version numbers

A release bumps the version in five places: `project(VERSION ...)` in
`CMakeLists.txt`, `MK_VERSION_*` in `include/merkmal.h`, `pyproject.toml`,
`python/merkmal/__init__.py` and `CITATION.cff`. The C smoke test fails if the
header and CMake disagree, and the Python tests fail if `__version__` and the
linked library disagree.

## Validation gates

Before a release is tagged, the following pass:

- the C tests with `MERKMAL_REQUIRE_UTF8PROC=ON`;
- the C tests of a shared-library build;
- the CMake and pkg-config consumer tests against an installed tree;
- the C library under the sanitizers;
- the Python tests;
- the wheel build, and the wheel contains only the package files;
- `python tools/validate_models.py` (required fields, exact identifier
  matching, feature coverage, geometry node resolution, provenance);
- `python tools/contrast_baseline.py --check`: no undeclared zero-distance
  pair, and no label unable to affect a distance;
- `python tools/generate_notice.py --check`, so that `NOTICE` matches the
  provenance manifests;
- `python tools/regenerate_golden.py --check`.

## Data releases

A data release is separate from a code release, because it changes observable
numbers even when no code changed.

- Any change to `data/models/`, `data/geometries/` or `data/diacritics/` that
  moves a distance or a feature set is a **major** model version, not a patch.
  `CHANGELOG.md` states what moved and why.
- Golden fixtures are regenerated with `tools/regenerate_golden.py`, and the
  diff is reviewed before it is accepted: those values are the library's
  contract.
- `data/models/*/provenance.json` is re-stamped (the input hashes are
  checked; `tools/generate_notice.py --restamp`) and `NOTICE` regenerated.
- A change to the PHOIBLE data is re-verified against the release its
  manifest pins:

  ```sh
  tools/rebuild_phoible_inventory.py <cldf/parameters.csv> --check
  ```

  The P-base tables are rebuilt from P-base's data archive the same way, and
  re-verified with:

  ```sh
  tools/rebuild_pbase_inventories.py <pbase/ipa2allfeatures.csv> --check
  ```

  These checks are not in CI, because they need the upstream files and a
  build should not depend on the network. They are the only checks that the
  tables still agree with upstream cell by cell.
- **A distribution that bundles the data tables is not MIT-only.** Its license
  expression is `MIT AND CC-BY-4.0 AND CC-BY-SA-3.0 AND CC-BY-NC-SA-4.0`, and
  it agrees in `pyproject.toml`, `setup.py`, `NOTICE` and the README
  ([ADR 0004](adr/0004-mit-for-code-upstream-terms-for-data.md)).
- PHOIBLE and the four P-base models are redistributed under their upstream
  terms, `CC-BY-SA-3.0` and `CC-BY-NC-SA-4.0`. No permission to relicense them
  has been granted; they are not relicensed without a recorded grant from
  the rights holders.
- A field marked `UNVERIFIED` in a provenance manifest is established from
  the source before the next data release, not inferred from file names.
