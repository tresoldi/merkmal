# WebAssembly

The C core builds for WebAssembly with the built-in models compiled in, and
needs no filesystem access.

## Interface

Two interfaces are available.

- **The C ABI.** The library built with Emscripten is linked into a
  WebAssembly program, which calls the functions of `include/merkmal.h`
  directly, as the Node smoke test does. This is the canonical interface
  ([ADR 0001](../development/adr/0001-c-api-is-the-canonical-interface.md)).
- **The JSON adapter used by the browser demonstration.**
  [`web/merkmal_wasm.c`](../../web/merkmal_wasm.c) wraps the C API in a small
  set of functions (`merkmal_list_systems`, `merkmal_grapheme_features`,
  `merkmal_segment_distance`, `merkmal_tokenize`, `merkmal_distance_matrix`,
  `merkmal_normalize`, `merkmal_diagnose`, `merkmal_register_model`,
  `merkmal_version`) that take strings and return a JSON string. Every
  returned string except that of `merkmal_version` is owned by the caller and
  must be released with `merkmal_free`. The adapter includes `merkmal.h` and
  nothing else from `src/`. It is the interface of the demonstration page
  (`web/index.html`, `web/app.js`), not a stable JavaScript API.

`web/build-wasm.sh` builds the adapter into `web/merkmal.js` and
`web/merkmal.wasm`, and records in `web/BUILD_INFO` the source commit, the
Emscripten version and a SHA-256 over every file the build reads
(`tools/wasm_inputs.py`). These files are committed
([ADR 0003](../development/adr/0003-generated-artifacts-are-committed.md)) and
must be rebuilt after any change under `src/` or `include/`:
`python tools/wasm_inputs.py --check`, run in CI, fails when the recorded hash
no longer matches the sources. The hash covers the inputs rather than the
output, so the check does not depend on the Emscripten version.

## Emscripten CMake build

With Emscripten activated:

```sh
emcmake cmake -S . -B build/wasm \
  -DCMAKE_BUILD_TYPE=Release \
  -DMERKMAL_BUILD_TESTS=OFF \
  -DMERKMAL_USE_UTF8PROC=OFF
cmake --build build/wasm
```

Normalization is compiled in, so the WebAssembly build normalizes exactly as
the native library and the Python package do; `MERKMAL_USE_UTF8PROC=OFF` only
stops CMake from searching for the test oracle. The `c-fallback` job in
continuous integration runs the full C test suite without utf8proc, which is
the same configuration.

## Node smoke test

A smoke test compiles a standalone WebAssembly program and runs it with Node:

```sh
tests/wasm/run_node_smoke.sh
```

It requires `emcc` and `node`, and exercises:

- construction of the built-in registry;
- lookup of a built-in system;
- feature lookup;
- segment distance;
- grapheme normalization;
- IPA segmentation with tone merging.

The program is linked with `-sFILESYSTEM=0`, so the test fails if any of these
operations requires filesystem access.
