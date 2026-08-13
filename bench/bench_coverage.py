#!/usr/bin/env python3
"""Measure what fraction of real CLDF wordlist data merkmal can actually read.

Every other guard in this repository checks the library against itself: the
golden fixtures, the contrast baseline, the generated-data check. They all pass
on a library that is internally perfect and unusable on the field's data. This
one checks it against the outside.

The metric that matters is not "does `is_segment` work" but "if a token appears
in a CLDF `Segments` column, does merkmal have defined behaviour for it". A form
is only usable if *every* token in it parses, so token coverage alone flatters
the result: failures cluster by language family, and a 95% token rate can still
mean an entire branch of the tree is unreadable.

Two modes:

    bench/bench_coverage.py                     # check the committed fixture
    bench/bench_coverage.py --check             # ...and fail below the floors
    bench/bench_coverage.py --regenerate DIR    # rebuild from a Lexibank checkout

`DIR` is a directory of CLDF dataset clones, each with `cldf/forms.csv`. The
fixture is regenerated deliberately and its diff reviewed, exactly like
`bench/baseline.txt`: a change here is always an argued change.

Why a committed fixture rather than reading the corpus every run: 152 dataset
clones are ~14M tokens and not something CI can fetch, and the aggregate segment
table is small, factual, and carries no wordlist content. See
bench/corpus/provenance.json for what it is and where it came from.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "bench" / "corpus"
SEGMENTS_TSV = CORPUS / "lexibank-segments.tsv"
FLOORS_JSON = CORPUS / "coverage-floors.json"

# CLDF writes these as tokens in the Segments column; they are not sounds and no
# phonological library should be asked to score them.
BOUNDARY_MARKERS = {"+", "_", "#"}


# ---------------------------------------------------------------- fixture i/o


def load_fixture() -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    """Return (global segment->tokens, dataset->segment->tokens)."""
    if not SEGMENTS_TSV.exists():
        sys.exit(f"missing fixture {SEGMENTS_TSV}; run --regenerate first")
    total: dict[str, int] = {}
    per_ds: dict[str, dict[str, int]] = collections.defaultdict(dict)
    with SEGMENTS_TSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            seg, tokens, dataset = row["SEGMENT"], int(row["TOKENS"]), row["DATASET"]
            per_ds[dataset][seg] = tokens
            total[seg] = total.get(seg, 0) + tokens
    return total, dict(per_ds)


def scan_corpus(corpus_dir: Path) -> tuple[dict[str, dict[str, int]], dict[str, tuple[int, int]]]:
    """Walk CLDF clones and count segment tokens per dataset.

    Also returns per-dataset (forms, forms_with_all_tokens_known) so the
    regenerated baseline can record the form-level rate, which cannot be
    recovered from the aggregate table: whether a form parses depends on which
    segments co-occur in it, not on their marginal frequencies.
    """
    csv.field_size_limit(10**7)
    per_ds: dict[str, dict[str, int]] = {}
    forms: dict[str, tuple[int, int]] = {}
    paths = sorted(corpus_dir.glob("*/cldf/forms.csv"))
    if not paths:
        sys.exit(f"no */cldf/forms.csv under {corpus_dir}")
    for path in paths:
        dataset = path.parent.parent.name
        counts: dict[str, int] = collections.Counter()
        n_forms = 0
        form_tokens: list[list[str]] = []
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if "Segments" not in (reader.fieldnames or []):
                continue
            for row in reader:
                raw = (row.get("Segments") or "").strip()
                if not raw:
                    continue
                tokens = [t for t in raw.split() if t not in BOUNDARY_MARKERS]
                if not tokens:
                    continue
                n_forms += 1
                counts.update(tokens)
                form_tokens.append(tokens)
        if not n_forms:
            continue
        per_ds[dataset] = dict(counts)
        forms[dataset] = (n_forms, form_tokens)  # type: ignore[assignment]
    return per_ds, forms  # type: ignore[return-value]


# ------------------------------------------------------------------ measuring


def accepted(segments, system: str) -> set[str]:
    """The subset of `segments` the library recognizes under `system`."""
    import merkmal

    out = set()
    for seg in segments:
        try:
            if merkmal.is_segment(seg, system=system):
                out.add(seg)
        except Exception:  # a raised error is a rejection for coverage purposes
            pass
    return out


def measure(total: dict[str, int], systems: list[str]) -> dict[str, dict[str, float]]:
    tok_total = sum(total.values())
    report = {}
    for system in systems:
        ok = accepted(total, system)
        report[system] = {
            "types_pct": 100.0 * len(ok) / len(total),
            "tokens_pct": 100.0 * sum(total[s] for s in ok) / tok_total,
            "types_ok": len(ok),
            "types_total": len(total),
        }
    return report


def blocked_datasets(per_ds: dict[str, dict[str, int]], system: str) -> list[tuple[str, float]]:
    """Datasets by token coverage, worst first.

    Token coverage per dataset is exactly recoverable from the aggregate table;
    the form-level rate is not, and is recorded in the baseline instead.
    """
    every = set()
    for counts in per_ds.values():
        every.update(counts)
    ok = accepted(every, system)
    rows = []
    for dataset, counts in per_ds.items():
        tot = sum(counts.values())
        good = sum(n for s, n in counts.items() if s in ok)
        rows.append((dataset, 100.0 * good / tot if tot else 100.0))
    rows.sort(key=lambda r: r[1])
    return rows


# ----------------------------------------------------------------- reporting


def report(check: bool) -> int:
    import merkmal

    total, per_ds = load_fixture()
    systems = list(merkmal.list_systems())
    result = measure(total, systems)

    print(f"Lexibank segment coverage  ({len(total)} types, {sum(total.values())} tokens, "
          f"{len(per_ds)} datasets)")
    print(f"  {'system':14} {'types':>16} {'tokens':>9}")
    for system in systems:
        r = result[system]
        print(f"  {system:14} {r['types_ok']:6}/{r['types_total']:<6} "
              f"{r['types_pct']:5.1f}% {r['tokens_pct']:8.2f}%")

    primary = "distinctive" if "distinctive" in systems else systems[0]
    rows = blocked_datasets(per_ds, primary)
    worst = [r for r in rows if r[1] < 90.0]
    print(f"\n  datasets below 90% token coverage under {primary}: {len(worst)} of {len(rows)}")
    for dataset, pct in rows[:10]:
        print(f"    {dataset:28} {pct:6.1f}%")
    if len(worst) > 10:
        print(f"    ... and {len(worst) - 10} more")

    if not check:
        return 0

    if not FLOORS_JSON.exists():
        sys.exit(f"missing {FLOORS_JSON}; run --regenerate to record floors")
    floors = json.loads(FLOORS_JSON.read_text(encoding="utf-8"))
    failed = False
    print("\n  against recorded floors:")
    for system, floor in sorted(floors["systems"].items()):
        if system not in result:
            print(f"    {system:14} MISSING from the build")
            failed = True
            continue
        got = result[system]
        for key in ("types_pct", "tokens_pct"):
            # Floors are stored at the precision they are printed at, so compare
            # at that precision: a measured 95.5687 is not a regression against a
            # recorded 95.57, it is the same number written down.
            if round(got[key], 2) + 1e-9 < floor[key]:
                print(f"    {system:14} {key} {got[key]:.2f}% < floor {floor[key]:.2f}%")
                failed = True
    if failed:
        print("\nFAILED: coverage regressed. Coverage is the metric that decides whether")
        print("this library is usable on the field's data; a drop here is not cosmetic.")
        return 1
    print("    all systems at or above their recorded floor")
    print("\nOK")
    return 0


def regenerate(corpus_dir: Path) -> int:
    import merkmal

    per_ds, forms = scan_corpus(corpus_dir)
    CORPUS.mkdir(parents=True, exist_ok=True)

    with SEGMENTS_TSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter="\t", lineterminator="\n")
        writer.writerow(["DATASET", "SEGMENT", "TOKENS"])
        for dataset in sorted(per_ds):
            for seg, n in sorted(per_ds[dataset].items(), key=lambda kv: (-kv[1], kv[0])):
                writer.writerow([dataset, seg, n])

    total: dict[str, int] = collections.Counter()
    for counts in per_ds.values():
        total.update(counts)
    systems = list(merkmal.list_systems())
    result = measure(dict(total), systems)
    FLOORS_JSON.write_text(
        json.dumps(
            {
                "note": (
                    "Floors recorded from a deliberate regeneration. bench_coverage.py "
                    "--check fails below them. Raise them when coverage improves so the "
                    "gain cannot be silently lost; lowering one is an argued change."
                ),
                "systems": {
                    s: {"types_pct": round(result[s]["types_pct"], 2),
                        "tokens_pct": round(result[s]["tokens_pct"], 2)}
                    for s in systems
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # The form-level rate needs co-occurrence and so cannot live in the
    # aggregate fixture; record it here while the corpus is in hand.
    primary = "distinctive" if "distinctive" in systems else systems[0]
    every: set[str] = set()
    for counts in per_ds.values():
        every.update(counts)
    ok = accepted(every, primary)
    lines = [
        "# Per-dataset form parse rates, recorded from a deliberate regeneration.",
        "#",
        "# A form counts as parsed only if every one of its segments is recognized,",
        "# which is the condition an actual pipeline faces. This cannot be recomputed",
        "# from bench/corpus/lexibank-segments.tsv: whether a form parses depends on",
        f"# which segments co-occur in it. System: {primary}.",
        "#",
        "# Regenerate with: bench/bench_coverage.py --regenerate <lexibank-dir>",
        "",
        f"{'DATASET':30} {'FORMS':>8} {'%FORMS':>8} {'%TOKENS':>8}",
    ]
    rows = []
    for dataset, (n_forms, form_tokens) in forms.items():
        full = sum(1 for toks in form_tokens if all(t in ok for t in toks))
        tot = sum(len(t) for t in form_tokens)
        good = sum(1 for toks in form_tokens for t in toks if t in ok)
        pct_tokens = 100.0 * good / tot if tot else 100.0
        rows.append((dataset, n_forms, 100.0 * full / n_forms, pct_tokens))
    rows.sort(key=lambda r: r[2])
    for dataset, n_forms, pf, pt in rows:
        lines.append(f"{dataset:30} {n_forms:8} {pf:7.1f}% {pt:7.1f}%")
    blocked = sum(1 for r in rows if r[2] < 3.0)
    lines[len(lines) - len(rows) - 1 : len(lines) - len(rows) - 1] = [
        f"# {len(rows)} datasets; {blocked} below 3% of forms parsed.",
        "",
    ]
    baseline = ROOT / "bench" / "coverage_baseline.txt"
    baseline.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {SEGMENTS_TSV.relative_to(ROOT)} "
          f"({sum(len(v) for v in per_ds.values())} rows, {len(per_ds)} datasets)")
    print(f"Wrote {FLOORS_JSON.relative_to(ROOT)}")
    print("Wrote bench/coverage_baseline.txt")
    print("\nReview the diff before committing: these numbers are the library's")
    print("contract with the field's data.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true",
                        help="fail if any system is below its recorded floor")
    parser.add_argument("--regenerate", metavar="DIR", type=Path,
                        help="rebuild the fixture from a directory of CLDF dataset clones")
    args = parser.parse_args()
    if args.regenerate:
        return regenerate(args.regenerate)
    return report(args.check)


if __name__ == "__main__":
    raise SystemExit(main())
