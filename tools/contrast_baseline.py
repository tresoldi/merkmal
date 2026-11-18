#!/usr/bin/env python3
"""Contrast audit of every built-in system against a recorded baseline.

Three properties, checked over each system's inventory plus composed forms
(modified bases, bare tones and cluster spellings):

1. **No undeclared collapse.** Two distinct graphemes at distance exactly zero
   are claimed to denote the same thing. In a categorical system every such
   pair must be recorded in tests/golden/contrast_baseline.tsv with a reason.

2. **No dead labels.** Every label a system can return must be able to change
   some distance; a label that reaches no scoring dimension is ignored without
   notice.

3. **No unreachable dimensions.** The converse of (2): a scoring leaf, ordinal
   scale or declared model dimension that no grapheme can activate contributes
   nothing, and the distinctions of its node reduce to fewer than it declares.

    python tools/contrast_baseline.py            # report
    python tools/contrast_baseline.py --check    # fail on any regression
    python tools/contrast_baseline.py --write    # re-record the baseline

Sampling: the categorical systems are swept exhaustively, because the
requirement that every zero be declared applies to them. The valued systems are
capped at `--max-valued-forms` forms (default 700, evenly spaced), because
their scorer walks every declared dimension per pair and an exhaustive sweep of
PHOIBLE alone exceeds eight million pairs. The cap is printed on every run;
`0` removes it.

The record has two tiers. Categorical collapses are few, and each is listed.
Valued collapses are properties of the upstream feature tables (the P-base
UFTC feature set, for example, does not distinguish /e/ from /i/), and they
number in the thousands per system, so each system is recorded as a count with
examples. Removing them would require feature values the source does not give;
the count is recorded instead, and --check fails if it rises.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import unicodedata
from pathlib import Path

import merkmal

ROOT = Path(__file__).resolve().parent.parent
GEOMETRY = ROOT / "data" / "geometries" / "clements-hume.json"
BASELINE = ROOT / "tests" / "golden" / "contrast_baseline.tsv"

CATEGORICAL = ["descriptive", "distinctive"]
VALUED = ["pbase-hc", "pbase-jfh", "pbase-spe", "pbase-uftc", "phoible"]

HEADER = ["SYSTEM", "KIND", "GRAPHEME_A", "GRAPHEME_B", "COUNT", "STATUS", "REASON"]

# The inventory is not the whole space a system accepts: modifiers compose into
# forms no row covers (`aː` against `aːː`, for instance), and a collapse among
# them is invisible to an inventory-only audit.
COMPOSED_SUFFIXES = [
    "ː", "ːː", "ˑ", "̃", "ʲ", "ʷ", "ˠ", "ˤ", "ʰ", "̥", "³³", "⁵⁵", "⁵¹",
    # Reach the diacritics that no inventory row carries, or the leaves for
    # them look unreachable when they are merely untried.
    "̈", "̽", "˞", "̘", "̙", "̯", "͈", "̚", "̬", "̺", "̻", "ʼ", "ⁿ", "ˡ",
]
COMPOSED_PREFIXES = ["ʷ", "ʲ", "ᵐ"]

# The valued systems' sweeps resolve 2,000 to 4,000 forms each (as this script
# prints them), and their scorer walks every declared dimension per pair, so an
# exhaustive sweep of PHOIBLE alone exceeds eight million pairs. Their sweep is
# capped, deterministically, and the cap is reported, so that a truncated sweep
# is not read as a complete one. The categorical systems stay exhaustive,
# because the requirement that every zero be declared applies to them.
DEFAULT_MAX_VALUED_FORMS = 700

# Under the cap, the valued counts depend on which forms were sampled, and the
# sample is drawn evenly from whatever the sweep covers. Changing the sweep's
# input (adding bare tone forms or cluster spellings, for example) therefore
# reselects the sample and moves the counts without any change to the library;
# `ai` and `au` are inventory rows in P-base, so even a change aimed at the
# categorical systems can move a valued count. A rise is evidence of a
# regression only when the swept population is unchanged; when it is enlarged
# on purpose, the baseline is re-recorded and the commit says so.

VALUED_REASON = (
    "upstream: the {system} feature table assigns these graphemes identical "
    "values on every dimension it defines, so the collapse is a property of that "
    "feature system rather than of merkmal; not an intended equivalence"
)


def read_inventory(system: str) -> list[str]:
    path = ROOT / "data" / "models" / system / "inventory.tsv"
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        next(reader)
        return sorted({row[0] for row in reader if row})


# Bare tone tokens are segments but not inventory rows, so a sweep built only
# from the inventory never reaches them. These are the whole recognition space
# of the tonal dimensions: every level, every two- and three-level contour, the
# tone letters, and Chao's neutral tone.
TONE_LEVELS = "¹²³⁴⁵"
BARE_TONE_FORMS = (
    [d for d in TONE_LEVELS]
    + [a + b for a in TONE_LEVELS for b in TONE_LEVELS]
    + [a + b + c for a in TONE_LEVELS for b in TONE_LEVELS for c in TONE_LEVELS]
    + ["˩", "˨", "˧", "˦", "˥", "˥˩", "˩˥", "˧˥", "⁰"]
)


# Every categorical system recognizes cluster spellings, and no inventory row
# carries them, so an inventory-derived sweep never reaches them. The list is
# taken from Lexibank by token frequency, so that it reflects the spellings
# found in transcribed data.
CLUSTER_FORMS = ['ai', 'au', 'ei', 'ou', 'aːi', 'əu', 'ui', 'ia', 'oi', 'ɛi', 'eu', 'ɑi', 'əi', 'ɑu', 'aɪ', 'aːu', 'ɔi', 'uɔ', 'aa', 'ua', 'ɐu', 'ai̯', 'ao', 'ɔu', 'eɪ', 'aʊ', 'ae', 'ea', 'iɛ', 'uə', 'oa', 'au̯', 'ɔɪ', 'ie', 'mb', 'ɐi']


_CHAO_DIGITS = {"⁰": 0, "¹": 1, "²": 2, "³": 3, "⁴": 4, "⁵": 5}
_CHAO_LETTERS = {"˩": 1, "˨": 2, "˧": 3, "˦": 4, "˥": 5}


def chao_contour(token: str) -> tuple[int, int, int] | None:
    """The (onset, mid, offset) pitch triple a bare tone token denotes, or None.

    Mirrors the resolver, so that two spellings of the same tone are recognized
    as such from the notation rather than from the feature sets they produce;
    the latter would be circular, since identical features are why they score
    zero.

    One level fills all three slots; two interpolate the middle; three are taken
    as written. So `⁵`, `⁵⁵`, `⁵⁵⁵` and `˥` are one tone spelled four ways, and
    `˥˩` is `⁵¹`.

    The midpoint rounds *up*, matching the resolver: `¹²` fills its middle slot
    with 2, not 1. That is a stipulation, with a visible consequence:
    `¹²` is the same tone as `¹²²` and a different one from `¹¹²`, so a rise
    reaches its target early rather than late. Rounding the other way would swap
    which of those two collapses. This function must not choose independently:
    if it disagrees with the resolver, the audit either hides a real collapse or
    reports a false one.
    """
    levels = []
    for char in token:
        if char in _CHAO_DIGITS:
            levels.append(_CHAO_DIGITS[char])
        elif char in _CHAO_LETTERS:
            levels.append(_CHAO_LETTERS[char])
        else:
            return None
    if not levels or 0 in levels or len(levels) > 3:
        return None  # neutral tone has no pitch target; over-long runs are rejected
    if len(levels) == 1:
        return (levels[0], levels[0], levels[0])
    if len(levels) == 2:
        return (levels[0], (levels[0] + levels[1] + 1) // 2, levels[1])
    return (levels[0], levels[1], levels[2])


def spelling_equivalent(a: str, b: str) -> bool:
    """Whether two graphemes are the same tone written differently."""
    contour_a = chao_contour(a)
    return contour_a is not None and contour_a == chao_contour(b)


# Spellings of one mark. Ring above is the IPA's ring below for letters with a
# descender; the apostrophe is a common stand-in for the ejective mark.
MARK_EQUIVALENTS = {"\u030a": "\u0325", "\u2019": "\u02bc", "'": "\u02bc"}


def _is_mark(char: str) -> bool:
    return unicodedata.category(char) in {"Mn", "Lm", "Sk"} or char in MARK_EQUIVALENTS


def _marks(token: str) -> tuple[frozenset[str], str, frozenset[str], int] | None:
    """(prefix marks, base letters, suffix marks, length marks), or None."""
    chars = unicodedata.normalize("NFD", token)
    start = 0
    while start < len(chars) and _is_mark(chars[start]):
        start += 1
    end = len(chars)
    base_chars: list[str] = []
    suffix: set[str] = set()
    for index in range(start, end):
        char = chars[index]
        if _is_mark(char):
            suffix.add(MARK_EQUIVALENTS.get(char, char))
        elif suffix:
            return None  # a letter after a mark: not one base with marks
        else:
            base_chars.append(char)
    if not base_chars:
        return None
    prefix = frozenset(MARK_EQUIVALENTS.get(c, c) for c in chars[:start])
    return prefix, "".join(base_chars), frozenset(suffix - {"\u02d0"}), chars.count("\u02d0")


def modifier_equivalent(a: str, b: str) -> bool:
    """Whether two graphemes are one base with the same diacritics, reordered or repeated.

    `t̪ʷʰ` and `t̪ʰʷ`, or `t̪ʰ` and `t̪ʰʰ`, write the same set of marks on the same
    base. Diacritic order carries no contrast in IPA and a repeated mark adds
    nothing. Length marks are counted rather than collected, because `ːː` is
    overlong and not a repeated `ː`; marks before the base are kept apart from
    marks after it, because `ʰt` is pre-aspirated and `tʰ` is aspirated.
    """
    marks_a, marks_b = _marks(a), _marks(b)
    return marks_a is not None and marks_a == marks_b


def composed_forms(system: str, bases: list[str]) -> list[str]:
    step = max(1, len(bases) // 40)
    out: list[str] = list(BARE_TONE_FORMS) + list(CLUSTER_FORMS)
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


def uncompared(system: str, pairs: list[tuple[str, str]]) -> int:
    """How many of these zero-distance pairs shared no comparable dimension.

    A bare count of collapses reads every zero as a claim of identity. In a
    valued system many are not: they are pairs for which the feature table has
    no dimension on which both segments have a value. Counting them separately
    keeps a rise in "the table is silent here" from looking like a rise in
    "these are the same sound".
    """
    total = 0
    for a, b in pairs:
        # The pairs were found by scoring them, so an error here is a defect to
        # report, not a pair to skip.
        result = merkmal.distance_with_coverage(a, b, system=system)
        if result.comparability == "no-shared-dimension":
            total += 1
    return total


def dead_labels(system: str, covered: list[str]) -> list[str]:
    geometry = json.loads(GEOMETRY.read_text(encoding="utf-8"))
    metadata = set(geometry.get("metadata_features", {}))
    # Cluster parses report a label per component (`n1-front`, `n2-stop`) and a
    # trajectory (`move-height-open-close`). They are open-ended (any base
    # feature can appear under any prefix), so the geometry declares them by
    # prefix rather than enumerating them. They do not score, and the
    # declaration states that, since a caller reading `move-height-open-close`
    # could otherwise assume it participates. The components themselves are
    # scored, by mk_distance_cluster_to_segment in system.c.
    prefixes = tuple(geometry.get("metadata_feature_prefixes", {}))
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
        if label in metadata or (prefixes and label.startswith(prefixes)):
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

    `unreachable_dimensions` audits the geometry. A system that scores through
    its own `scalar_dimensions` and never reads a geometry leaf, as
    `distinctive` does, needs this separate check: a declared dimension that no
    grapheme reaches is invisible to an audit of the geometry.

    A dimension is reachable if any grapheme carries any of its labels. One pole
    is enough: presence against absence still separates two segments.
    """
    path = ROOT / "data" / "models" / system / "model.json"
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
        # Rows with fewer columns than the current layout are ignored rather
        # than failing the audit; they read as "not yet declared".
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
                if key in baseline and baseline[key][1] != "UNDECLARED":
                    _, status, reason = baseline[key]
                elif modifier_equivalent(a, b):
                    status = "modifier-equivalent"
                    reason = (
                        "one base with the same diacritics, written in another "
                        "order or with a mark repeated; diacritic order carries "
                        "no contrast in IPA and a repeated mark adds nothing"
                    )
                elif spelling_equivalent(a, b):
                    # The same tone written differently. Chao's notation is
                    # redundant (a level tone may be one, two or three digits,
                    # or a tone letter), so these zeros follow the notation
                    # and do not lose a contrast.
                    status = "spelling-equivalent"
                    reason = (
                        "the same Chao contour written differently: a level tone "
                        "may be spelled with one, two or three digits or with a "
                        "tone letter, and all of them denote one tone. A "
                        "two-digit contour fills its middle slot by rounding the "
                        "midpoint up, so a rise reaches its target early: 12 is "
                        "122 and not 112"
                    )
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
            blank = uncompared(system, found)
            print(f"  of those, {blank} shared no comparable dimension "
                  f"({100 * blank / len(found):.1f}%)" if found else "")
            # The reason is derived from this run, not reviewed by hand, so it is
            # always recomputed: a stored reason carried forward could describe
            # numbers that no longer hold.
            status = "upstream-indistinguishable"
            reason = VALUED_REASON.format(system=system)
            if found:
                reason += (
                    f"; {blank} of these ({100 * blank / len(found):.1f}%) shared no "
                    "comparable dimension at all, so they are the table being silent "
                    "rather than the segments being alike"
                )
            if previous_row is not None:
                previous, previous_status, _previous_reason = previous_row
                status = previous_status
                if int(previous) < len(found):
                    problems.append(
                        f"{system}: zero-distance pairs rose from {previous} to {len(found)}"
                    )
            else:
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
        elif (ROOT / "data" / "models" / system / "model.json").exists():
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
