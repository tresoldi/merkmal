# WebAssembly

The C core is designed to work in WebAssembly with compiled-in built-in models
and no required filesystem access.

## Current Surface Decision

The first WebAssembly target is the raw C ABI exported by `include/merkmal.h`.
A small JavaScript convenience wrapper can be added later after the C ABI has
settled. Keeping the first target at the C layer avoids prematurely designing a
JS API before downstream consumers are known.

## Emscripten CMake Build

With Emscripten activated:

```sh
emcmake cmake -S . -B build/wasm \
  -DCMAKE_BUILD_TYPE=Release \
  -DMERKMAL_BUILD_TESTS=OFF \
  -DMERKMAL_REQUIRE_UTF8PROC=OFF
cmake --build build/wasm
```

The fallback Unicode path is used for this first spike. Native distribution
builds require system `utf8proc`, but the WebAssembly path keeps
`MERKMAL_REQUIRE_UTF8PROC=OFF` until the Emscripten packaging story is worth
formalizing. A later WebAssembly release can either vendor/build `utf8proc`
inside the Emscripten toolchain or document the fallback as the supported
browser profile.

## Node Smoke Test

The repository includes a smoke test that compiles a standalone WebAssembly
program and runs it with Node:

```sh
tests/wasm/run_node_smoke.sh
```

The smoke test exercises:

- built-in registry construction
- built-in system lookup
- feature lookup
- segment distance
- grapheme normalization
- IPA segmentation with tone digit merging

The Emscripten link command uses `-sFILESYSTEM=0`, so the test fails if the
exercised built-in-model path needs filesystem access.
