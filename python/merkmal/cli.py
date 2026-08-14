"""Small native-backed command line interface."""

from __future__ import annotations

import argparse
import sys

import merkmal

_EXIT_OK = 0
_EXIT_USAGE = 1

# What the wrapper raises when the user got something wrong.
#
# They are Python's own types, on purpose: merkmal.Registry documents KeyError
# for an unknown system and ValueError for an unknown grapheme, and callers
# expect to catch those rather than something library-specific. NativeError is
# not a base class of any of them -- it is created with no base -- so catching
# it alone caught none of the mistakes a person actually makes, and every one
# of them exited through a traceback instead of _print_error. It stays in the
# tuple for the statuses that do map to it.
_USER_ERRORS = (ValueError, KeyError, NotImplementedError, merkmal.NativeError)


def _build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser for the supported wrapper operations."""
    parser = argparse.ArgumentParser(prog="merkmal")
    parser.add_argument(
        "-s",
        "--system",
        default=None,
        help="feature system name; defaults to the C library default",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("systems", help="list built-in feature systems")

    features_cmd = sub.add_parser("features", help="print features for one grapheme")
    features_cmd.add_argument("grapheme")

    distance_cmd = sub.add_parser("distance", help="print segment distance")
    distance_cmd.add_argument("a")
    distance_cmd.add_argument("b")

    normalize_cmd = sub.add_parser("normalize", help="normalize one grapheme")
    normalize_cmd.add_argument("grapheme")

    segment_cmd = sub.add_parser("segment", help="segment IPA text")
    segment_cmd.add_argument("text")

    return parser


def _print_error(exc: Exception) -> int:
    """Print a user-facing error and return the command-line failure code."""
    # KeyError renders its argument with repr(), which would wrap a message
    # written for a person in quotes.
    message = exc.args[0] if isinstance(exc, KeyError) and exc.args else exc
    print(f"error: {message}", file=sys.stderr)
    return _EXIT_USAGE


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface and return its process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "systems":
            for system in merkmal.list_systems():
                print(system)
            return _EXIT_OK
        if args.command == "features":
            for feature in sorted(merkmal.get_features(args.grapheme, system=args.system)):
                print(feature)
            return _EXIT_OK
        if args.command == "distance":
            print(merkmal.distance(args.a, args.b, system=args.system))
            return _EXIT_OK
        if args.command == "normalize":
            print(merkmal.normalize(args.grapheme))
            return _EXIT_OK
        if args.command == "segment":
            for segment in merkmal.segment_ipa(args.text):
                print(segment)
            return _EXIT_OK
    except _USER_ERRORS as exc:
        return _print_error(exc)

    parser.error(f"unknown command: {args.command}")
    return _EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
