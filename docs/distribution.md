# C Library Distribution

`merkmal` installs as a normal C library with:

- `include/merkmal.h`
- `libmerkmal` as a static or shared library, depending on `BUILD_SHARED_LIBS`
- a CMake package exporting `merkmal::merkmal`
- a pkg-config file named `merkmal.pc`

## Build And Install

```sh
cmake -S . -B build/release \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/usr/local \
  -DMERKMAL_REQUIRE_UTF8PROC=ON
cmake --build build/release
cmake --install build/release
```

Use a user-writable prefix while testing packaging:

```sh
cmake -S . -B build/stage \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$PWD/build/install" \
  -DMERKMAL_REQUIRE_UTF8PROC=ON
cmake --build build/stage
cmake --install build/stage
```

## Static Or Shared

CMake follows the standard `BUILD_SHARED_LIBS` option:

```sh
cmake -S . -B build/shared -DBUILD_SHARED_LIBS=ON
cmake -S . -B build/static -DBUILD_SHARED_LIBS=OFF
```

The public header uses `MK_API` for exported symbols. Consumers normally do not
need to define anything manually when they use the installed CMake target.

## Unicode normalization

The library has no external dependency. NFC and NFD are compiled in from
`src/generated/unicode_data.c`, which `tools/generate_unicode_data.py` writes
from the Unicode Character Database of the generating Python. Every build —
static, shared, Python, WebAssembly — normalizes identically, at the version in
`mki_unicode_version` (exposed to Python as `merkmal.UNICODE_VERSION`).

Earlier versions used `libutf8proc` when it was installed and an IPA-focused
approximation when it was not, and the two returned different strings for the
same input. That distinction is gone, and the installed CMake package and
`merkmal.pc` no longer name utf8proc.

`libutf8proc` survives only as a test oracle:

- `MERKMAL_USE_UTF8PROC` (default `ON`) looks for it, and if found the
  `unicode` test compares the built-in normalizer with it over every code
  point and 400,000 generated mark sequences. When utf8proc carries a
  different Unicode version than the tables, the test reports a skip.
- `MERKMAL_REQUIRE_UTF8PROC` (default `OFF`) makes its absence a configuration
  error, for CI jobs that must run the oracle.

Neither option changes the library that is built.

## CMake Consumers

```cmake
find_package(merkmal CONFIG REQUIRED)

add_executable(example example.c)
target_link_libraries(example PRIVATE merkmal::merkmal)
```

If merkmal was installed to a custom prefix:

```sh
cmake -S consumer -B consumer/build -DCMAKE_PREFIX_PATH=/path/to/merkmal-prefix
```

## pkg-config Consumers

```sh
cc example.c $(pkg-config --cflags --libs merkmal) -o example
```

For static linking:

```sh
cc example.c $(pkg-config --cflags --libs --static merkmal) -o example
```

If merkmal was installed to a custom prefix:

```sh
export PKG_CONFIG_PATH=/path/to/merkmal-prefix/lib/pkgconfig:$PKG_CONFIG_PATH
```

On systems that install libraries under `lib64`, use the matching
`lib64/pkgconfig` directory.
