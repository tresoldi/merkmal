#!/usr/bin/env python3
"""Regenerate the checked-in golden fixtures from the installed native build.

The fixtures are parity data: the C tests replay them and fail on any change.
For that reason this script is not part of the build. It is run only when a
change to model data or scoring is intended, and its diff is reviewed as a
change of data:

    python -m pip install -e . --no-build-isolation
    python tools/regenerate_golden.py --check      # report drift, change nothing
    python tools/regenerate_golden.py              # rewrite the fixtures

All values are produced here, through the installed native build; the C tests
only read them, so no test can rewrite the values it is checked against, and no
CMake build is needed.

The grapheme and pair lists are taken from the existing files, so values are
rewritten without changing what is covered. A row whose grapheme or pair no
longer resolves is reported and dropped; that is a change of contract and
needs a CHANGELOG.md entry.

Scope: the fixtures the C tests replay, namely `{model}_features.tsv`,
`{model}_distances.tsv`, and the geometry fixtures keyed by
`geometry_cases.tsv`. The `_full` and `classfeat` fixtures are archived output
of the earlier Python implementation and are left as they are, since
rewriting them from the C build would remove the record they keep. See
tests/golden/README.md.

With --check, nothing is written and the exit status is 1 if any fixture would
change or any row would be dropped.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import merkmal

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden"

# classfeat is not a system of the C library; its fixtures are archived.
SYSTEMS = [
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
    # string, a few carry repr(). Keeping whichever form the row already uses
    # limits the diff to rows whose value changed.
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


GEOMETRY_CASES = GOLDEN / "geometry_cases.tsv"


def read_geometry_cases() -> dict[str, list[str]]:
    """The named feature sets the geometry fixtures are keyed by.

    They live in a versioned file rather than in the test source, so that this
    script, and not tests/c/test_geometry.c, produces the fixtures the test
    replays: the program that checks the values does not also write them.
    """
    header, rows = read_rows(GEOMETRY_CASES)
    return {row[0]: row[1].split("|") for row in rows}


def regenerate_geometry_feature_distances(path: Path, dropped: list[str]) -> list[list[str]]:
    header, rows = read_rows(path)
    out: list[list[str]] = []
    for row in rows:
        a, b = row[0], row[1]
        try:
            value = merkmal.feature_distance(a, b)
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            dropped.append(f"{path.name}: {a!r}/{b!r} failed ({exc})")
            continue
        out.append([a, b, str(value)])
    return out


def regenerate_geometry_sound_distances(
    path: Path,
    cases: dict[str, list[str]],
    weighted: bool,
    dropped: list[str],
) -> list[list[str]]:
    header, rows = read_rows(path)
    out: list[list[str]] = []
    for row in rows:
        preset = row[0] if weighted else "None"
        a, b = (row[1], row[2]) if weighted else (row[0], row[1])
        if a not in cases or b not in cases:
            dropped.append(f"{path.name}: {a!r}/{b!r} is not in geometry_cases.tsv")
            continue
        node_weights = None if preset == "None" else preset
        try:
            value = merkmal.sound_distance(cases[a], cases[b], node_weights=node_weights)
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            dropped.append(f"{path.name}: {preset}/{a!r}/{b!r} failed ({exc})")
            continue
        formatted = f"{value:.10f}"
        out.append([preset, a, b, formatted] if weighted else [a, b, formatted])
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report which fixtures would change and exit non-zero, writing nothing",
    )
    args = parser.parse_args()

    dropped: list[str] = []
    changed: list[str] = []

    cases = read_geometry_cases()
    geometry: list[tuple[Path, object]] = [
        (GOLDEN / "geometry_distances.tsv",
         lambda path: regenerate_geometry_feature_distances(path, dropped)),
        (GOLDEN / "geometry_sound_distances.tsv",
         lambda path: regenerate_geometry_sound_distances(path, cases, False, dropped)),
        (GOLDEN / "geometry_weighted_distances.tsv",
         lambda path: regenerate_geometry_sound_distances(path, cases, True, dropped)),
    ]
    for path, regenerate in geometry:
        header, before = read_rows(path)
        after = regenerate(path)  # type: ignore[operator]
        if after != before:
            changed.append(f"{path.name}: {len(before)} -> {len(after)} rows")
            if not args.check:
                write_rows(path, header, after)

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
