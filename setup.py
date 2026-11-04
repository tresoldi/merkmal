from __future__ import annotations

import glob
import os

from setuptools import Extension, setup

# The C core is compiled straight into the extension, so a wheel carries no
# dependency on an installed libmerkmal. Paths are relative to this file, which
# is why it lives at the repository root rather than under python/: an sdist
# built from python/ could not reach src/ or include/, and shipped without the
# C core entirely.
#
# The core sources are globbed rather than listed. They were listed here, in
# CMakeLists.txt, and in tests/wasm/run_node_smoke.sh, so splitting a module
# meant remembering three places; the one that gets forgotten fails at link
# time in whichever build nobody ran locally. Sorted for reproducible builds.
HERE = os.path.dirname(os.path.abspath(__file__))

# MERKMAL_DATA_PROFILE=cc-by builds the extension with only the CC-BY-4.0
# tables (descriptive, distinctive), leaving out PHOIBLE (CC-BY-SA-3.0) and
# P-base (CC-BY-NC-SA-4.0). For a distributable package use
# scripts/prepare_distribution.py, which also removes the excluded data from
# the source tree and sets the package name and license expression.
DATA_PROFILE = os.environ.get("MERKMAL_DATA_PROFILE", "full")
PROFILE_DATA = {
    "full": "src/generated/builtin_data.c",
    "cc-by": "src/generated/cc-by/builtin_data.c",
}
if DATA_PROFILE not in PROFILE_DATA:
    raise SystemExit(f"merkmal: MERKMAL_DATA_PROFILE must be one of {sorted(PROFILE_DATA)}")

SOURCES = ["python/src/merkmal_module.c"] + sorted(
    os.path.relpath(path, HERE)
    for pattern in ("src/*.c", "src/generated/*.c")
    for path in glob.glob(os.path.join(HERE, pattern))
    if os.path.relpath(path, HERE) != PROFILE_DATA["full"]
) + [PROFILE_DATA[DATA_PROFILE]]

# Unicode normalization is compiled in from src/generated/unicode_data.c, so
# the extension has no system dependency and every build normalizes alike.
# MERKMAL_REQUIRE_UTF8PROC, which made a missing libutf8proc fatal, is accepted
# and ignored so that existing build scripts keep working.

# The same warning set the CMake build enforces, minus two that the CPython API
# forces on any extension:
#
#   -Wcast-function-type   PyMethodDef stores every method as PyCFunction, so
#                          METH_VARARGS|METH_KEYWORDS entries must be cast from
#                          a three-argument function. That cast is the
#                          documented idiom, not a mistake.
#   -Wmissing-prototypes   PyInit__native is declared by PyMODINIT_FUNC, which
#                          GCC does not count as a prototype.
#
# Not applied via -Werror: a wheel build should not fail on a warning from a
# compiler or CPython version this project has not seen.
WARNINGS = [
    "-Wall",
    "-Wextra",
    "-Wpedantic",
    "-Wshadow",
    "-Wconversion",
    "-Wstrict-prototypes",
]

# Set MERKMAL_SANITIZE=address,undefined to build the extension for a sanitizer
# run. The CI job that does this preloads the ASan runtime, because CPython
# itself is not built with it.
SANITIZE = os.environ.get("MERKMAL_SANITIZE", "")
SANITIZE_FLAGS = (
    [f"-fsanitize={SANITIZE}", "-fno-omit-frame-pointer", "-g"] if SANITIZE else []
)

setup(
    license="MIT AND CC-BY-4.0 AND CC-BY-SA-3.0 AND CC-BY-NC-SA-4.0",
    options={"bdist_wheel": {"py_limited_api": "cp312"}},
    ext_modules=[
        Extension(
            "merkmal._native",
            sources=SOURCES,
            include_dirs=["include", "src"],
            define_macros=[
                ("Py_LIMITED_API", "0x030C0000"),
            ],
            py_limited_api=True,
            extra_compile_args=[
                "-std=c99",
                *WARNINGS,
                *SANITIZE_FLAGS,
            ],
            extra_link_args=[*SANITIZE_FLAGS],
        )
    ],
)
