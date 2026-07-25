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

## utf8proc

`utf8proc` is discovered with pkg-config.

- `MERKMAL_REQUIRE_UTF8PROC=ON` fails configuration if `libutf8proc` is missing.
- `MERKMAL_REQUIRE_UTF8PROC=OFF` allows the IPA-focused fallback used for
  development builds.

Distribution builds should use `MERKMAL_REQUIRE_UTF8PROC=ON`.
See [release-policy.md](release-policy.md) for the current release dependency
policy.

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
