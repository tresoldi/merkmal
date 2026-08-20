from __future__ import annotations

import glob
import os
import subprocess

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
SOURCES = ["python/src/merkmal_module.c"] + sorted(
    os.path.relpath(path, HERE)
    for pattern in ("src/*.c", "src/generated/*.c")
    for path in glob.glob(os.path.join(HERE, pattern))
)

# Distribution builds must not silently fall back to the built-in Unicode
# path. Set this in any environment that produces artifacts for other people
# (cibuildwheel does, via CIBW_ENVIRONMENT) so a missing libutf8proc fails the
# build instead of shipping degraded normalization to every installer.
REQUIRE_UTF8PROC = os.environ.get("MERKMAL_REQUIRE_UTF8PROC", "").lower() in {
    "1",
    "on",
    "true",
    "yes",
}


def utf8proc_build_options() -> tuple[list[tuple[str, str]], list[str], list[str]]:
    try:
        subprocess.run(
            ["pkg-config", "--exists", "libutf8proc"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        if REQUIRE_UTF8PROC:
            raise SystemExit(
                "merkmal: libutf8proc not found via pkg-config, and "
                "MERKMAL_REQUIRE_UTF8PROC is set. Install libutf8proc "
                "development headers, or unset the variable to build with the "
                "IPA-focused fallback (development builds only)."
            ) from None
        return [("MK_HAVE_UTF8PROC", "0")], [], []

    cflags = subprocess.check_output(
        ["pkg-config", "--cflags", "libutf8proc"],
        text=True,
    ).split()
    libs = subprocess.check_output(
        ["pkg-config", "--libs", "libutf8proc"],
        text=True,
    ).split()
    return [("MK_HAVE_UTF8PROC", "1")], cflags, libs


utf8proc_macros, utf8proc_cflags, utf8proc_ldflags = utf8proc_build_options()

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
                *utf8proc_macros,
            ],
            py_limited_api=True,
            extra_compile_args=[
                "-std=c99",
                *WARNINGS,
                *SANITIZE_FLAGS,
                *utf8proc_cflags,
            ],
            extra_link_args=[*SANITIZE_FLAGS, *utf8proc_ldflags],
        )
    ],
)
