from __future__ import annotations

import subprocess

from setuptools import Extension, setup

SOURCES = [
    "src/merkmal_module.c",
    "../src/feature_set.c",
    "../src/geometry.c",
    "../src/registry.c",
    "../src/status.c",
    "../src/string_list.c",
    "../src/system.c",
    "../src/unicode.c",
    "../src/generated/builtin_data.c",
]

def utf8proc_build_options() -> tuple[list[tuple[str, str]], list[str], list[str]]:
    try:
        subprocess.run(
            ["pkg-config", "--exists", "libutf8proc"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
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
            include_dirs=["../include", "../src"],
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
