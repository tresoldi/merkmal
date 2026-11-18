# Installation

merkmal installs as a C library consisting of:

- the header `include/merkmal.h`;
- `libmerkmal`, static or shared according to `BUILD_SHARED_LIBS`;
- a CMake package exporting the target `merkmal::merkmal`;
- a pkg-config file, `merkmal.pc`.

The build requires CMake 3.20 or later and a C99 compiler.

## Build and install

```sh
cmake -S . -B build/release \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/usr/local
cmake --build build/release
cmake --install build/release
```

To test packaging, a user-writable prefix can be used:

```sh
cmake -S . -B build/stage \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$PWD/build/install"
cmake --build build/stage
cmake --install build/stage
```

## Static or shared

The library follows the standard CMake option `BUILD_SHARED_LIBS`:

```sh
cmake -S . -B build/shared -DBUILD_SHARED_LIBS=ON
cmake -S . -B build/static -DBUILD_SHARED_LIBS=OFF
```

The public header marks exported symbols with `MK_API`. A consumer that links
the installed CMake target needs to define nothing itself: for a shared build
the target carries the definition `MERKMAL_SHARED`, which selects the DLL
import declarations on Windows.

## Data profiles

`MERKMAL_DATA_PROFILE` selects the built-in systems the library carries:

| Profile | Systems | Data licenses |
| --- | --- | --- |
| `full` (default) | all seven | CC-BY-4.0, CC-BY-SA-3.0, CC-BY-NC-SA-4.0 |
| `cc-by` | `descriptive`, `distinctive` | CC-BY-4.0 |

```sh
cmake -S . -B build/cc-by -DMERKMAL_DATA_PROFILE=cc-by
```

A profile selects systems by the license declared in each system's provenance
manifest, not by name. Each profile is a committed, generated table:
`src/generated/builtin_data.c` for `full` and
`src/generated/cc-by/builtin_data.c` for `cc-by` (regenerated with
`python tools/generate_c_data.py --profile cc-by`). A system that the profile
omits is reported as `MK_ERR_UNKNOWN_SYSTEM`, exactly as an unknown name is.
The profile of a built library is reported by `mk_data_profile` (Python:
`merkmal.DATA_PROFILE`).

The Python package is built with a given profile from source, with the
variable set:

```sh
MERKMAL_DATA_PROFILE=cc-by pip install --no-binary merkmal merkmal   # from PyPI
MERKMAL_DATA_PROFILE=cc-by pip install .                             # from a checkout
```

merkmal is published as a single package, built with the `full` profile; the
`cc-by` profile is a build option, not a separate distribution. The compiled
library then carries only the CC BY tables, but the source distribution from
which it is built still contains the full table file, as every merkmal source
tree does.

## Unicode normalization

The library has no external dependency. NFC and NFD are compiled in from
`src/generated/unicode_data.c`, which `tools/generate_unicode_data.py` writes
from the Unicode Character Database of the Python interpreter that runs it.
Every build (static, shared, Python, WebAssembly) therefore normalizes
identically, at the Unicode version reported by `mk_unicode_version` (Python:
`merkmal.UNICODE_VERSION`). The installed CMake package and `merkmal.pc`
declare no dependency.

`libutf8proc` is used only as a test oracle:

- `MERKMAL_USE_UTF8PROC` (default `ON`) searches for it. If it is found, the
  `unicode` test compares the built-in normalizer with it over every code
  point and 400,000 generated sequences of combining marks. When utf8proc
  carries a different Unicode version from the tables, the test reports a
  skip.
- `MERKMAL_REQUIRE_UTF8PROC` (default `OFF`) makes its absence a configuration
  error, for continuous-integration jobs that must run the oracle.

Neither option changes the library that is built.

## CMake consumers

```cmake
find_package(merkmal CONFIG REQUIRED)

add_executable(example example.c)
target_link_libraries(example PRIVATE merkmal::merkmal)
```

If merkmal was installed under a custom prefix:

```sh
cmake -S consumer -B consumer/build -DCMAKE_PREFIX_PATH=/path/to/merkmal-prefix
```

## pkg-config consumers

```sh
cc example.c $(pkg-config --cflags --libs merkmal) -o example
```

For static linking:

```sh
cc example.c $(pkg-config --cflags --libs --static merkmal) -o example
```

`--static` adds the math library (`-lm`) where the platform keeps it separate,
since the library calls `fabs`. The CMake package carries the same dependency.

If merkmal was installed under a custom prefix:

```sh
export PKG_CONFIG_PATH=/path/to/merkmal-prefix/lib/pkgconfig:$PKG_CONFIG_PATH
```

On systems that install libraries under `lib64`, the corresponding directory
is `lib64/pkgconfig`.
