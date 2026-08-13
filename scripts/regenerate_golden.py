#!/usr/bin/env python3
"""Regenerate the checked-in golden fixtures from the installed native build.

The fixtures are parity data: the C tests replay them and fail on any change.
That is the point, so this script is deliberately not wired into the build. Run
it only when a model-data or scoring change is *intended*, and review the diff
as data, not as noise:

    python -m pip install -e . --no-build-isolation
    python scripts/regenerate_golden.py --check      # report drift, change nothing
    python scripts/regenerate_golden.py              # rewrite the fixtures

The grapheme and pair lists are taken from the existing files, so this rewrites
values without silently changing what is covered. A row whose grapheme or pair
no longer resolves is reported and dropped; that is a contract change and
should be justified in the changelog.

Scope: only the `{model}_features.tsv` and `{model}_distances.tsv` fixtures the
active C tests replay. The `_full` fixtures and the `classfeat` fixtures are
archived pre-C Python parity data, and rewriting them from the C build would
destroy the record they exist to keep. See tests/golden/README.md for the drift
that record currently shows.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import merkmal

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden"

# classfeat is not part of the native C slice; its fixtures are historical.
SYSTEMS = [
    "broad",
    "descriptive",
    "distinctive",
    "pbase-hc",
    "pbase-jfh",
    "pbase-spe",
    "pbase-uftc",
    "phoible",
]


def read_rows(path: Path) -> tuple[str, list[list[str]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return lines[0], [line.split("\t") for line in lines[1:] if line]


def write_rows(path: Path, header: str, rows: list[list[str]]) -> None:
    body = "\n".join(["\t".join(row) for row in rows])
    path.write_text(header + "\n" + body + "\n", encoding="utf-8")


def format_distance(value: float, previous: str) -> str:
    # These files are not uniformly formatted: most rows carry a fixed 10-decimal
    # string, a few carry repr(). Matching whichever the row already used keeps
    # the diff to rows whose *value* actually moved.
    try:
        if previous == f"{float(previous):.10f}":
            return f"{value:.10f}"
    except ValueError:
        pass
    return repr(value)


def regenerate_features(system: str, path: Path, dropped: list[str]) -> list[list[str]]:
    header, rows = read_rows(path)
    out: list[list[str]] = []
    for row in rows:
        grapheme = row[0]
        try:
            features = merkmal.get_features(grapheme, system=system)
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            dropped.append(f"{path.name}: {grapheme!r} no longer resolves ({exc})")
            continue
        out.append([grapheme, "|".join(sorted(features))])
    return out


def regenerate_distances(system: str, path: Path, dropped: list[str]) -> list[list[str]]:
    header, rows = read_rows(path)
    out: list[list[str]] = []
    for row in rows:
        a, b = row[0], row[1]
        try:
            value = merkmal.distance(a, b, system=system)
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            dropped.append(f"{path.name}: {a!r}/{b!r} no longer resolves ({exc})")
            continue
        out.append([a, b, format_distance(value, row[2])])
    return out


GEOMETRY_FIXTURES = [
    "geometry_distances.tsv",
    "geometry_sound_distances.tsv",
    "geometry_weighted_distances.tsv",
]


def find_geometry_binary(build_dir: Path | None) -> Path | None:
    """The geometry fixtures are keyed by feature sets defined inside
    tests/c/test_geometry.c, so that binary regenerates them itself.

    Picking the most recently built one matters: an older build directory
    regenerates the fixtures with stale library code and reports no drift,
    which reads as "nothing changed" when in fact nothing was checked.
    """
    if build_dir is not None:
        binary = (build_dir / "test_geometry").resolve()
        return binary if binary.exists() else None
    candidates = sorted(
        (ROOT / "build").glob("*/test_geometry"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def regenerate_geometry(build_dir: Path | None, check: bool, changed: list[str]) -> None:
    binary = find_geometry_binary(build_dir)
    before = {name: (GOLDEN / name).read_text(encoding="utf-8") for name in GEOMETRY_FIXTURES}
    if binary is None:
        print(
            "NOTE: no built test_geometry found; geometry fixtures were not checked. "
            "Configure and build the C tests first, or pass --build-dir.",
            file=sys.stderr,
        )
        return
    subprocess.run([str(binary), "--regenerate"], check=True, cwd=ROOT)  # noqa: S603
    for name in GEOMETRY_FIXTURES:
        path = GOLDEN / name
        after = path.read_text(encoding="utf-8")
        if after != before[name]:
            changed.append(f"{name}: regenerated from {binary.relative_to(ROOT)}")
            if check:
                path.write_text(before[name], encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report which fixtures would change and exit non-zero, writing nothing",
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=None,
        help="build directory holding test_geometry (default: the newest under build/)",
    )
    args = parser.parse_args()

    dropped: list[str] = []
    changed: list[str] = []

    regenerate_geometry(args.build_dir, args.check, changed)

    for system in SYSTEMS:
        for suffix, regenerate in (
            ("_features.tsv", regenerate_features),
            ("_distances.tsv", regenerate_distances),
        ):
            path = GOLDEN / f"{system}{suffix}"
            if not path.exists():
                continue
            header, before = read_rows(path)
            after = regenerate(system, path, dropped)
            if after != before:
                changed.append(f"{path.name}: {sum(1 for x, y in zip(before, after, strict=False) if x != y)} value(s) differ, {len(before)} -> {len(after)} rows")
                if not args.check:
                    write_rows(path, header, after)

    for message in dropped:
        print(f"DROPPED: {message}", file=sys.stderr)
    for message in changed:
        print(("WOULD UPDATE: " if args.check else "UPDATED: ") + message)

    if not changed and not dropped:
        print("Golden fixtures already match the current build.")
        return 0
    if args.check:
        print("\nFixtures are stale. Review the change, then rerun without --check.")
        return 1
    print("\nReview the diff before committing: these values are the library's contract.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
