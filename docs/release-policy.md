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
cmake -S . -B build/dev -DMERKMAL_REQUIRE_UTF8PROC=OFF
```

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
