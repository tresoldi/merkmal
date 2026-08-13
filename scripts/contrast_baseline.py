#!/usr/bin/env python3
"""Exhaustive contrast audit across every built-in system.

Three properties, checked over the whole bundled inventory plus composed forms,
not a sample:

1. **No undeclared collapse.** Two distinct graphemes scoring exactly zero is a
   claim that they denote the same thing. Every such pair must be on the record
   with a reason.

2. **No dead labels.** Every label a system can return must be able to change
   some distance. A label reaching no scoring dimension is silently ignored.

3. **No unreachable dimensions.** The mirror of (2), and the one that was
   missing: a scoring leaf no grapheme can activate is decorative, and its whole
   node then collapses into one boolean. That is how every manner distinction
   came to cost the same.

    python scripts/contrast_baseline.py            # report
    python scripts/contrast_baseline.py --check    # fail on any regression
    python scripts/contrast_baseline.py --write    # re-record the baseline

Sampling: the categorical systems are swept exhaustively, since that is where
the every-zero-declared contract lives. The valued systems are capped at
`--max-valued-forms` (default 700, evenly spaced) because their scorer walks
every declared dimension per pair and PHOIBLE alone would be over eight million
comparisons. The cap is printed on every run; pass `0` for the full sweep.

The record is two-tier by necessity. Categorical collapses are few, so each is
listed. Valued collapses are properties of the *upstream* feature table -- the
P-base UFTC feature set does not distinguish /e/ from /i/ at all -- so they run
to tens of thousands and are recorded as a count with examples. Inventing
feature values to remove them would be fabricating data; the honest treatment is
to publish the number and let it be checked for regression.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
from pathlib import Path

import merkmal

ROOT = Path(__file__).resolve().parent.parent
GEOMETRY = ROOT / "geometries" / "clements-hume.json"
BASELINE = ROOT / "tests" / "golden" / "contrast_baseline.tsv"

CATEGORICAL = ["broad", "descriptive", "distinctive"]
VALUED = ["pbase-hc", "pbase-jfh", "pbase-spe", "pbase-uftc", "phoible"]

HEADER = ["SYSTEM", "KIND", "GRAPHEME_A", "GRAPHEME_B", "COUNT", "STATUS", "REASON"]

# The bare inventory is not the whole space a system accepts: modifiers compose
# into forms no row covers, and `aː` versus `aːː` scored zero for exactly that
# reason while an inventory-only audit reported a clean sheet.
COMPOSED_SUFFIXES = [
    "ː", "ːː", "ˑ", "̃", "ʲ", "ʷ", "ˠ", "ˤ", "ʰ", "̥", "³³", "⁵⁵", "⁵¹",
    # Reach the diacritics that no inventory row carries, or the leaves for
    # them look unreachable when they are merely untried.
    "̈", "̽", "˞", "̘", "̙", "̯", "͈", "̚", "̬", "̺", "̻", "ʼ", "ⁿ", "ˡ",
]
COMPOSED_PREFIXES = ["ʷ", "ʲ", "ᵐ"]

# The valued systems have 1,000-3,500 forms each and their scorer walks every
# declared dimension per pair, so an exhaustive sweep of PHOIBLE alone is over
# eight million comparisons. Their sweep is capped, deterministically, and the
# cap is reported: a silent truncation would read as "covered everything". The
# categorical systems stay exhaustive, because that is where the
# every-zero-declared contract lives.
DEFAULT_MAX_VALUED_FORMS = 700

VALUED_REASON = (
    "upstream: the {system} feature table assigns these graphemes identical "
    "values on every dimension it defines, so the collapse is a property of that "
    "feature system rather than of merkmal; not an intended equivalence"
)


def read_inventory(system: str) -> list[str]:
    path = ROOT / "models" / system / "inventory.tsv"
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        next(reader)
        return sorted({row[0] for row in reader if row})


def composed_forms(system: str, bases: list[str]) -> list[str]:
    step = max(1, len(bases) // 40)
    out: list[str] = []
    for base in bases[::step][:40]:
        candidates = [base + suffix for suffix in COMPOSED_SUFFIXES]
        candidates += [prefix + base for prefix in COMPOSED_PREFIXES]
        for form in candidates:
            try:
                merkmal.get_features(form, system=system)
            except Exception:  # noqa: BLE001 - unsupported combinations are expected
                continue
            out.append(form)
    return out


def resolved(system: str, graphemes: list[str]) -> list[str]:
    out = []
    for grapheme in graphemes:
        try:
            merkmal.get_features(grapheme, system=system)
        except Exception:  # noqa: BLE001 - out of scope for this system
            continue
        out.append(grapheme)
    return out


def collapses(system: str, covered: list[str]) -> list[tuple[str, str]]:
    return [
        (a, b)
        for a, b in itertools.combinations(covered, 2)
        if merkmal.distance(a, b, system=system) == 0.0
    ]


def dead_labels(system: str, covered: list[str]) -> list[str]:
    geometry = json.loads(GEOMETRY.read_text(encoding="utf-8"))
    metadata = set(geometry.get("metadata_features", {}))
    # An ordered level is skipped when the other segment has no value on the
    # scale, so probing it against an unrelated label always scores zero. The
    # meaningful comparison is against a different level of the same scale.
    scale_of: dict[str, list[str]] = {}
    for scale in geometry.get("ordinal_scales", []):
        for level in scale["levels"]:
            scale_of[str(level)] = [str(x) for x in scale["levels"]]

    labels: set[str] = set()
    for grapheme in covered:
        labels |= set(merkmal.get_features(grapheme, system=system))

    dead = []
    for label in sorted(labels):
        if "=" in label:
            continue  # a valued state pair, not a categorical label
        if label in metadata:
            continue  # declared as deliberately unscored
        probe = merkmal.Registry()
        try:
            probe.add_model_text(
                "\n".join(
                    [
                        "@model _probe",
                        "@type categorical",
                        "@validation permissive",
                        f"grapheme A {label}",
                        "grapheme B " + next(
                            (other for other in scale_of.get(label, []) if other != label),
                            "__mk_probe_label_the_geometry_cannot_know__",
                        ),
                    ]
                )
            )
        except Exception:  # noqa: BLE001 - a label the parser rejects cannot score
            dead.append(label)
            continue
        if probe.distance("A", "B", system="_probe") == 0.0:
            dead.append(label)
    return dead


def unreachable_dimensions(system: str, covered: list[str]) -> list[str]:
    geometry = json.loads(GEOMETRY.read_text(encoding="utf-8"))
    metadata = set(geometry.get("metadata_features", {}))
    present: set[str] = set()
    for grapheme in covered:
        present |= set(merkmal.get_features(grapheme, system=system))

    out: list[str] = []

    def walk(node: dict) -> None:
        if "children" in node:
            for child in node["children"]:
                walk(child)
            return
        for pole in ("positive", "negative"):
            value = node.get(pole)
            if value and value not in present and value not in metadata:
                out.append(f"leaf {node['name']}.{pole} = {value}")

    walk(geometry["tree"])
    for scale in geometry.get("ordinal_scales", []):
        reachable = sum(1 for level in scale["levels"] if level in present)
        if scale.get("default_level") is not None:
            reachable += 1
        if reachable < 2:
            out.append(f"scale {scale['name']} ({reachable} reachable level(s))")
    return out


def unreachable_model_dimensions(system: str, covered: list[str]) -> list[str]:
    """Scoring dimensions the *model* declares that no grapheme can activate.

    `unreachable_dimensions` above audits the geometry. That is the wrong
    artifact for a system that scores through its own `scalar_dimensions` and
    never reads a geometry leaf -- which is what `distinctive` does. Auditing
    only the geometry is how nine tone dimensions survived the ordinal tone
    rewrite: they were left behind by the old two-bit Chao encoding, no grapheme
    has been able to reach them since, and every check in this repository passed.

    A dimension is reachable if any grapheme carries any of its labels. One pole
    is enough: presence against absence still separates two segments.
    """
    path = ROOT / "models" / system / "model.json"
    if not path.exists():
        return []
    declared = json.loads(path.read_text(encoding="utf-8")).get("scalar_dimensions", [])
    if not declared:
        return []

    present: set[str] = set()
    for grapheme in covered:
        present |= set(merkmal.get_features(grapheme, system=system))

    out = []
    for dim in declared:
        labels = [str(x) for x in dim.get("positive", [])] + [
            str(x) for x in dim.get("negative", [])
        ]
        if not any(label in present for label in labels):
            out.append(f"{dim['name']} (no grapheme carries any of {labels})")
    return out


def read_baseline() -> dict[tuple[str, str, str, str], tuple[str, str, str]]:
    if not BASELINE.exists():
        return {}
    with BASELINE.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        next(reader)
        # Rows from an older layout are ignored rather than crashing the audit;
        # they simply read as "not yet declared".
        return {
            (row[0], row[1], row[2], row[3]): (row[4], row[5], row[6])
            for row in reader
            if len(row) >= 7 and not row[0].startswith("#")
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit non-zero on any regression")
    parser.add_argument("--write", action="store_true", help="re-record the baseline file")
    parser.add_argument(
        "--max-valued-forms",
        type=int,
        default=DEFAULT_MAX_VALUED_FORMS,
        help=f"cap forms per valued system, evenly sampled (default {DEFAULT_MAX_VALUED_FORMS}; 0 = no cap)",
    )
    args = parser.parse_args()

    baseline = read_baseline()
    recorded: list[list[str]] = []
    problems: list[str] = []

    for system in CATEGORICAL + VALUED:
        bases = read_inventory(system)
        # dict.fromkeys rather than set(): a composed form can coincide with an
        # inventory row, and a duplicate would compare against itself and be
        # recorded as a collapse.
        forms = list(dict.fromkeys(bases + composed_forms(system, bases)))
        covered = resolved(system, forms)
        note = ""
        if system in VALUED and args.max_valued_forms and len(covered) > args.max_valued_forms:
            total = len(covered)
            step = total / args.max_valued_forms
            covered = [covered[int(i * step)] for i in range(args.max_valued_forms)]
            note = f", SAMPLED {len(covered)} of {total}"
        pairs = len(covered) * (len(covered) - 1) // 2
        found = collapses(system, covered)
        print(
            f"\n[{system}] {len(covered)} forms ({len(bases)} inventory{note}), "
            f"{pairs} pairs, {len(found)} zero-distance"
        )

        if system in CATEGORICAL:
            for a, b in found:
                key = (system, "pair", a, b)
                if key in baseline:
                    _, status, reason = baseline[key]
                else:
                    status, reason = "UNDECLARED", "not in the baseline"
                    problems.append(f"undeclared collapse in {system}: {a!r} ~ {b!r}")
                recorded.append([system, "pair", a, b, "1", status, reason])
        else:
            # Summary rows carry their examples in the GRAPHEME_A column, so
            # they are matched on (system, kind) rather than on the full key.
            previous_row = next(
                (value for key, value in baseline.items()
                 if key[0] == system and key[1] == "summary"),
                None,
            )
            examples = "; ".join(f"{a}~{b}" for a, b in found[:6])
            if previous_row is not None:
                previous, status, reason = previous_row
                if int(previous) < len(found):
                    problems.append(
                        f"{system}: zero-distance pairs rose from {previous} to {len(found)}"
                    )
            else:
                status = "upstream-indistinguishable"
                reason = VALUED_REASON.format(system=system)
                problems.append(f"{system}: {len(found)} collapses not yet recorded")
            recorded.append([system, "summary", examples, "", str(len(found)), status, reason])
            if found:
                print(f"  examples: {examples}")

        dead = dead_labels(system, covered)
        if dead:
            problems.append(f"{system}: {len(dead)} label(s) cannot affect any distance: {dead}")
            print(f"  DEAD LABELS: {dead}")
        else:
            print("  every returned label can affect a distance")

        if system in CATEGORICAL:
            unreachable = unreachable_dimensions(system, covered)
            if unreachable:
                problems.append(f"{system}: {len(unreachable)} unreachable scoring dimension(s)")
                print(f"  UNREACHABLE ({len(unreachable)}):")
                for name in unreachable:
                    print(f"    {name}")
            else:
                print("  every scoring dimension is reachable")

        orphans = unreachable_model_dimensions(system, covered)
        if orphans:
            problems.append(
                f"{system}: {len(orphans)} declared model dimension(s) no grapheme can reach"
            )
            print(f"  ORPHANED MODEL DIMENSIONS ({len(orphans)}):")
            for name in orphans:
                print(f"    {name}")
        elif (ROOT / "models" / system / "model.json").exists():
            print("  every declared model dimension is reachable")

    if args.write:
        with BASELINE.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            writer.writerow(HEADER)
            writer.writerows(recorded)
        print(f"\nWrote {len(recorded)} row(s) to {BASELINE.relative_to(ROOT)}")
        print("Replace any UNDECLARED status with a reviewed status and reason.")
        return 0

    if problems:
        print(f"\n{len(problems)} problem(s):")
        for message in problems:
            print(f"  {message}")
        if args.check:
            print("\nFAILED: the contrast baseline regressed.")
            return 1
        return 0

    print("\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
