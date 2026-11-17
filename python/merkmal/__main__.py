"""Entry point for ``python -m merkmal``, the same as the ``merkmal`` command."""

from __future__ import annotations

from merkmal.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
