"""The ``merkmal`` command-line interface (python/README.md, Command line)."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import merkmal

_EXIT_OK = 0
_EXIT_USAGE = 1

# The exceptions that report a mistake in the input, printed by _print_error
# rather than as a traceback. The package raises Python's own types for these
# (KeyError for an unknown system, ValueError for an unknown grapheme), and
# NativeError, which is not a base class of any of them, for the remaining
# statuses, so all of them must be listed.
_USER_ERRORS = (ValueError, KeyError, NotImplementedError, merkmal.NativeError)


# Output modes. The human output (the default) may change between releases;
# --json, --jsonl and --tsv are the stable, documented contract for scripts
# (python/README.md, Command line).
_FORMATS = ("json", "jsonl", "tsv")


def _add_format_options(parser: argparse.ArgumentParser, default: Any) -> None:
    """Add the mutually exclusive output modes, before or after a subcommand."""
    group = parser.add_mutually_exclusive_group()
    for name in _FORMATS:
        group.add_argument(
            f"--{name}",
            dest="format",
            action="store_const",
            const=name,
            default=default,
            help=f"machine-readable {name.upper()} output (stable)",
        )


def _build_parser() -> argparse.ArgumentParser:
    """Create the parser: global options, then one subcommand."""
    parser = argparse.ArgumentParser(prog="merkmal")
    parser.add_argument(
        "-s",
        "--system",
        default=None,
        help=f"feature system name; defaults to {merkmal.DEFAULT_SYSTEM}",
    )
    _add_format_options(parser, default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    commands = {
        "systems": ("list built-in feature systems", []),
        "features": ("print features for one grapheme", ["grapheme"]),
        "distance": ("print segment distance", ["a", "b"]),
        "normalize": ("normalize one grapheme", ["grapheme"]),
        "segment": ("segment IPA text", ["text"]),
    }
    for name, (help_text, positionals) in commands.items():
        command = sub.add_parser(name, help=help_text)
        for positional in positionals:
            command.add_argument(positional)
        # SUPPRESS: a subcommand that is not given a mode must not reset one
        # given before the subcommand.
        _add_format_options(command, default=argparse.SUPPRESS)

    return parser


def _print_error(exc: Exception) -> int:
    """Print a user-facing error and return the command-line failure code."""
    # KeyError renders its argument with repr(), which would wrap a message
    # written for a person in quotes.
    message = exc.args[0] if isinstance(exc, KeyError) and exc.args else exc
    print(f"error: {message}", file=sys.stderr)
    return _EXIT_USAGE


def _tsv_field(value: object) -> str:
    """One TSV field. Backslash, tab and newline are escaped as \\, \\t and
    \\n so that a value can never add a column or a row."""
    text = repr(value) if isinstance(value, float) else str(value)
    return text.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")


def _emit(fmt: str, result: dict[str, Any], records: list[dict[str, Any]]) -> None:
    """Write `result` as one JSON object, or `records` as JSONL or TSV."""
    if fmt == "json":
        print(json.dumps(result, ensure_ascii=False))
    elif fmt == "jsonl":
        for record in records:
            print(json.dumps(record, ensure_ascii=False))
    else:
        columns = list(records[0]) if records else []
        print("\t".join(columns))
        for record in records:
            print("\t".join(_tsv_field(record[column]) for column in columns))


def _run(args: argparse.Namespace) -> tuple[list[str], dict[str, Any], list[dict[str, Any]]]:
    """Compute one command: human lines, the JSON result, the JSONL/TSV records."""
    system = args.system or merkmal.DEFAULT_SYSTEM
    if args.command == "systems":
        names = list(merkmal.list_systems())
        return names, {"systems": names}, [{"system": name} for name in names]
    if args.command == "features":
        features = sorted(merkmal.get_features(args.grapheme, system=system))
        result = {"system": system, "grapheme": args.grapheme, "features": features}
        records = [{"grapheme": args.grapheme, "feature": f} for f in features]
        return features, result, records
    if args.command == "distance":
        score, coverage, why = merkmal.distance_with_coverage(args.a, args.b, system=system)
        record = {
            "system": system,
            "a": args.a,
            "b": args.b,
            "distance": score,
            "coverage": coverage,
            "comparability": why,
        }
        return [str(merkmal.distance(args.a, args.b, system=system))], record, [record]
    if args.command == "normalize":
        normalized = merkmal.normalize(args.grapheme)
        record = {"input": args.grapheme, "normalized": normalized}
        return [normalized], record, [record]
    segments = list(merkmal.segment_ipa(args.text))
    result = {"text": args.text, "segments": segments}
    records = [{"index": i, "segment": segment} for i, segment in enumerate(segments)]
    return segments, result, records


def main(argv: list[str] | None = None) -> int:
    """Run the command line given by ``argv`` (default ``sys.argv[1:]``).

    Returns the exit status: 0 on success, 1 when the input is rejected (the
    message goes to stderr). argparse exits with status 2 on a usage error.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        # Computed in full before anything is written, so a failure leaves
        # stdout empty rather than half a document.
        lines, result, records = _run(args)
    except _USER_ERRORS as exc:
        return _print_error(exc)

    if args.format is None:
        for line in lines:
            print(line)
    else:
        _emit(args.format, result, records)
    return _EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
