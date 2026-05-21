"""Command-line interface for the merkmal package."""

from __future__ import annotations

import argparse
import sys

from merkmal.model import list_available_models
from merkmal.registry import get_registry

_EXIT_OK = 0
_EXIT_USAGE = 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="merkmal")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List available feature systems.")

    info_cmd = sub.add_parser("info", help="Show info about a feature system.")
    info_cmd.add_argument("system")

    return parser


def _run_list() -> int:
    models = list_available_models()
    for name in models:
        print(name)
    return _EXIT_OK


def _run_info(args: argparse.Namespace) -> int:
    registry = get_registry()
    try:
        system = registry.get_system(args.system)
    except KeyError:
        print(
            f"error: unknown system {args.system!r}. "
            f"Available: {registry.list_systems()}",
            file=sys.stderr,
        )
        return _EXIT_USAGE

    print(f"name: {system.name}")
    print(f"kind: {system.representation_kind}")
    graphemes = system.list_graphemes()
    print(f"graphemes: {len(graphemes)}")
    return _EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "list":
        return _run_list()
    if args.command == "info":
        return _run_info(args)
    parser.error(f"unknown command: {args.command}")
    return _EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
