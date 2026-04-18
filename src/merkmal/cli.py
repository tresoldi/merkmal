"""Command-line interface for the merkmal package."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from merkmal.cognator_export import (
    CognatorExportError,
    export_all_systems,
    export_cognator,
)
from merkmal.registry import get_registry

_EXIT_OK = 0
_EXIT_USAGE = 1
_EXIT_IO = 2
_EXIT_INTERNAL = 3


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="merkmal")
    sub = parser.add_subparsers(dest="command", required=True)

    ec = sub.add_parser(
        "export-cognator",
        help="Export a feature system to a byte-stable cognator bundle.",
    )
    ec.add_argument("--system", default=None)
    ec.add_argument("--out", default=None)
    ec.add_argument("--all-systems", action="store_true", dest="all_systems")
    ec.add_argument("--force", action="store_true")
    return parser


def _run_export_cognator(args: argparse.Namespace) -> int:
    registry = get_registry()
    if args.all_systems and args.system:
        print("error: --all-systems cannot be combined with --system", file=sys.stderr)
        return _EXIT_USAGE
    if not args.all_systems and not args.system:
        print("error: either --system or --all-systems is required", file=sys.stderr)
        return _EXIT_USAGE

    if args.all_systems:
        out = Path(args.out) if args.out else Path("./cognator_export")
        try:
            export_all_systems(out, force=args.force)
        except FileExistsError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return _EXIT_IO
        except CognatorExportError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return _EXIT_INTERNAL
        except OSError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return _EXIT_IO
        return _EXIT_OK

    if args.system not in registry.list_systems():
        print(
            f"error: unknown system {args.system!r}. "
            f"Available: {registry.list_systems()}",
            file=sys.stderr,
        )
        return _EXIT_USAGE

    out = Path(args.out) if args.out else Path("./cognator_export") / args.system
    try:
        export_cognator(args.system, out, force=args.force)
    except FileExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return _EXIT_IO
    except CognatorExportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return _EXIT_INTERNAL
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return _EXIT_IO
    return _EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "export-cognator":
        return _run_export_cognator(args)
    parser.error(f"unknown command: {args.command}")
    return _EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
