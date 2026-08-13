from __future__ import annotations

import os
import subprocess

from setuptools import Extension, setup

# The C core is compiled straight into the extension, so a wheel carries no
# dependency on an installed libmerkmal. Paths are relative to this file, which
# is why it lives at the repository root rather than under python/: an sdist
# built from python/ could not reach src/ or include/, and shipped without the
# C core entirely.
SOURCES = [
    "python/src/merkmal_module.c",
    "src/geometry.c",
    "src/registry.c",
    "src/resolver.c",
    "src/status.c",
    "src/string_list.c",
    "src/system.c",
    "src/unicode.c",
    "src/generated/builtin_data.c",
]

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

setup(
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
            extra_compile_args=["-std=c99", *utf8proc_cflags],
            extra_link_args=utf8proc_ldflags,
        )
    ],
)
