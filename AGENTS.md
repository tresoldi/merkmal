# Working on merkmal

Instructions for coding agents (and people) changing this repository. The
conventions themselves are in [STYLE.md](STYLE.md); the house standard they
follow is [docs/house-standard.md](docs/house-standard.md); decisions that
depart from it, or that are easy to undo by accident, are in
[docs/adr/](docs/adr/).

## Build and test

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug -DMERKMAL_WERROR=ON
cmake --build build
ctest --test-dir build --output-on-failure
```

```sh
python -m pip install -e ".[dev]"
python -m pytest python/tests -q
```

## Checks to run before committing

CI runs all of these (`.github/workflows/ci.yml`). Run the ones your change
touches; STYLE.md, Building and checking, has the full table.

- C: the build above with GCC and with Clang, and with
  `-DMERKMAL_ENABLE_SANITIZER=address` and `=undefined`.
- `tools/check_format.sh`
- `tools/run_static_analysis.sh` (any finding beyond the documented one is new)
- `python tools/check_generated_data.py` after touching `data/models/`,
  `data/geometries/`, `data/diacritics/`, `tools/` or `src/generated/builtin_data.h`
- `python tools/regenerate_golden.py --check`, `tools/validate_models.py`,
  `tools/contrast_baseline.py --check`, `tools/generate_notice.py --check`
- Python: `python -m ruff check python/merkmal python/tests python/typology tools bench setup.py`
  and `python -m mypy python/merkmal`

## Boundaries

- `include/merkmal.h` is the whole public API. The Python extension
  (`python/src/merkmal_module.c`) and the WebAssembly adapter
  (`web/merkmal_wasm.c`) include it and nothing else from `src/`.
  [ADR 0001](docs/adr/0001-c-api-is-the-canonical-interface.md).
- `mk_` names are public, `mki_` names internal; the `public_symbols` test
  fails on a leak.
- Canonical data lives in `data/models/`, `data/geometries/` and `data/diacritics/`. Changing
  it changes distances, golden fixtures and semantic fingerprints; follow
  docs/release-policy.md, Data Releases.

## Generated files: never edit by hand

- `src/generated/*.c`: run `python tools/generate_c_data.py` (and with
  `--profile cc-by`) or `python tools/generate_unicode_data.py`.
- `tests/golden/*.tsv`: `python tools/regenerate_golden.py`.
- `NOTICE`: `python tools/generate_notice.py`.
- `web/merkmal.js`, `web/merkmal.wasm`, `web/BUILD_INFO`: `web/build-wasm.sh`
  (needs Emscripten). [ADR 0003](docs/adr/0003-generated-artifacts-are-committed.md).

## Do not

- skip, disable or weaken a test to make a change pass;
- restyle code you are not otherwise changing, or mix a reformat with a
  functional change;
- add a dependency without meeting the house standard's test (Dependencies
  must justify themselves) and recording it;
- change a license or a license expression ([ADR 0004](docs/adr/0004-mit-for-code-upstream-terms-for-data.md));
- change a public signature or `mk_status` value without a **Breaking**
  CHANGELOG entry; statuses are appended, never renumbered.

## Every change

- One concern per commit.
- A user-visible change gets a CHANGELOG.md entry under Unreleased.
- A fixed bug leaves a test that fails without the fix.
