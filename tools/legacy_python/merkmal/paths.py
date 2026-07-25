"""Layered data-path resolution for models, geometries, and typologies.

merkmal ships a bundled copy of its data under ``merkmal/data``. Users
who want to add or override data — their own models, geometries,
typologies, or diacritic sets — point the corresponding environment
variable at one or more directories:

* ``MERKMAL_MODELS``      — model directories (each with ``model.json``)
* ``MERKMAL_GEOMETRIES``  — geometry JSON files
* ``MERKMAL_TYPOLOGIES``  — typology JSON files
* ``MERKMAL_DIACRITICS``  — diacritic JSON files

Each variable is an ``os.pathsep``-separated list of directories. By
default the listed directories are *layered on top of* the bundled
data: an entry found in an earlier directory wins, but anything not
provided by the user still falls back to the built-ins. Set
``MERKMAL_DATA_ISOLATED=1`` to drop the built-ins entirely and use only
the directories supplied by the environment / API.

This module is the single source of truth for that resolution; the
model, geometry, and typology loaders all build on it.
"""

from __future__ import annotations

import os
from pathlib import Path

_PKG_DATA = Path(__file__).resolve().parent / "data"
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# subdir name -> env var providing extra search directories
_ENV_VARS: dict[str, str] = {
    "models": "MERKMAL_MODELS",
    "geometries": "MERKMAL_GEOMETRIES",
    "typologies": "MERKMAL_TYPOLOGIES",
    "diacritics": "MERKMAL_DIACRITICS",
}

_ISOLATED_ENV = "MERKMAL_DATA_ISOLATED"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def isolated() -> bool:
    """Whether built-in bundled data should be excluded (env-controlled)."""
    return os.environ.get(_ISOLATED_ENV, "").strip().lower() in _TRUTHY


def _env_dirs(subdir: str) -> list[Path]:
    env_var = _ENV_VARS.get(subdir)
    if not env_var:
        return []
    raw = os.environ.get(env_var)
    if not raw:
        return []
    return [Path(p) for p in raw.split(os.pathsep) if p.strip()]


def _builtin_dirs(subdir: str) -> list[Path]:
    out: list[Path] = []
    pkg = _PKG_DATA / subdir
    if pkg.is_dir():
        out.append(pkg)
    repo = _REPO_ROOT / subdir
    if repo.is_dir() and repo.resolve() != pkg.resolve():
        out.append(repo)
    return out


def data_roots(
    subdir: str,
    *,
    extra_dirs: list[Path] | list[str] | None = None,
    include_builtin: bool = True,
) -> list[Path]:
    """Return the ordered, de-duplicated search path for *subdir*.

    Order of precedence (earlier wins):

    1. ``extra_dirs`` passed programmatically
    2. directories from the matching ``MERKMAL_*`` environment variable
    3. bundled built-in data (unless excluded)

    Built-ins are excluded when *include_builtin* is ``False`` or when
    ``MERKMAL_DATA_ISOLATED`` is set.
    """
    roots: list[Path] = []
    for d in extra_dirs or []:
        roots.append(Path(d))
    roots.extend(_env_dirs(subdir))
    if include_builtin and not isolated():
        roots.extend(_builtin_dirs(subdir))

    seen: set[Path] = set()
    out: list[Path] = []
    for r in roots:
        if not r.is_dir():
            continue
        key = r.resolve()
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def primary_dir(subdir: str) -> Path:
    """Return the highest-precedence existing directory for *subdir*.

    Kept for callers that need a single directory (e.g. error messages
    and backward-compatible ``find_*_dir`` helpers).
    """
    roots = data_roots(subdir)
    if roots:
        return roots[0]
    msg = (
        f"Cannot find {subdir}/ directory. Set {_ENV_VARS.get(subdir, 'the env var')} "
        f"or ensure the bundled package data exists."
    )
    raise FileNotFoundError(msg)


def resolve_file(
    subdir: str,
    filename: str,
    *,
    extra_dirs: list[Path] | list[str] | None = None,
    include_builtin: bool = True,
) -> Path | None:
    """Find *filename* across the search path for *subdir*; None if absent."""
    for root in data_roots(subdir, extra_dirs=extra_dirs, include_builtin=include_builtin):
        candidate = root / filename
        if candidate.exists():
            return candidate
    return None
