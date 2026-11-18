#!/usr/bin/env python3
"""The inputs of the committed WebAssembly build, and whether it is current.

web/merkmal.js and web/merkmal.wasm are committed artifacts (ADR 0003), built
by web/build-wasm.sh, which records in web/BUILD_INFO a SHA-256 over every file
the build reads. This script computes that hash. With --check it fails if the
recorded hash differs from the sources, that is, if a change under src/,
include/ or the adapter was committed without rebuilding the page's engine.

The hash is over the inputs, not the output, so the check does not depend on
the Emscripten version: two compilers may emit different bytes from the same
sources, and either build is current.

    python tools/wasm_inputs.py            # print the hash
    python tools/wasm_inputs.py --check    # compare with web/BUILD_INFO
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_INFO = ROOT / "web" / "BUILD_INFO"


def inputs() -> list[Path]:
    """Every file the WebAssembly build reads, in a fixed order.

    The build compiles the library from src/ with the full data profile, so the
    cc-by tables are not an input.
    """
    files = [
        ROOT / "CMakeLists.txt",
        ROOT / "include" / "merkmal.h",
        ROOT / "web" / "build-wasm.sh",
        ROOT / "web" / "merkmal_wasm.c",
    ]
    files += [
        path
        for path in (ROOT / "src").rglob("*")
        if path.is_file()
        and path.suffix in {".c", ".h"}
        and "cc-by" not in path.relative_to(ROOT / "src").parts
    ]
    return sorted(files, key=lambda path: path.relative_to(ROOT).as_posix())


def inputs_sha256() -> str:
    """SHA-256 over each input's repository path and bytes."""
    digest = hashlib.sha256()
    for path in inputs():
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8") + b"\0")
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def recorded_sha256() -> str | None:
    """The inputs_sha256 line of web/BUILD_INFO, or None if it has none."""
    for line in BUILD_INFO.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition(" ")
        if key == "inputs_sha256":
            return value.strip()
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="fail if web/BUILD_INFO is out of date"
    )
    args = parser.parse_args()

    current = inputs_sha256()
    if not args.check:
        print(current)
        return 0

    recorded = recorded_sha256()
    if recorded == current:
        print("web/merkmal.wasm is current with its sources.")
        return 0
    print(
        "web/merkmal.wasm is stale: its sources changed since it was built "
        f"(recorded {recorded or 'nothing'}, sources {current}). "
        "Run web/build-wasm.sh and commit web/merkmal.js, web/merkmal.wasm "
        "and web/BUILD_INFO.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
