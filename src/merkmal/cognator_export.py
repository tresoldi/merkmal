"""Export a merkmal system to a byte-stable cognator bundle.

Produces a small self-describing directory of TSV files plus a
``manifest.json`` that downstream consumers (principally the
``cognator`` Go package) can read without a Python runtime
dependency on merkmal.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import unicodedata
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from merkmal.analysis import distance as _analysis_distance
from merkmal.partitions import LEVELS as PARTITION_LEVELS
from merkmal.partitions import (
    compute_partitions,
    level_features_by_system,
    unclassified_graphemes,
)
from merkmal.registry import get_registry, get_system

if TYPE_CHECKING:
    from collections.abc import Iterable

    from merkmal.protocol import FeatureSystem

SCHEMA_VERSION = 1

_TONE_LETTERS: frozenset[str] = frozenset("˥˦˧˨˩")
_CHAO_SUPERSCRIPTS: frozenset[str] = frozenset("⁰¹²³⁴⁵")
_STANDALONE_SUPRASEG: frozenset[str] = frozenset({"ˈ", "ˌ", "ː", "ˑ"})

_ROLE_R_FEATURES: frozenset[str] = frozenset(
    {"nasal", "lateral", "trill", "tap", "flap", "sonorant"},
)
_ROLE_C_FEATURES: frozenset[str] = frozenset(
    {"stop", "plosive", "fricative", "affricate", "implosive", "click"},
)
_ROLE_G_FEATURES: frozenset[str] = frozenset(
    {"approximant", "semi-vowel"},
)

_ROLE_R_STATES: frozenset[str] = frozenset(
    {"nasal=+", "lateral=+", "trill=+", "tap=+", "sonorant=+"},
)
_ROLE_G_STATES: frozenset[str] = frozenset({"approximant=+"})


class CognatorExportError(ValueError):
    """Raised when the exporter detects an internal inconsistency."""


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _format_float(x: float) -> str:
    return f"{x:.6f}"


def _resolve_export_date() -> str:
    epoch_str = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch_str is not None and epoch_str.strip():
        ts = int(epoch_str.strip())
        dt = datetime.fromtimestamp(ts, tz=UTC)
    else:
        dt = datetime.now(tz=UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_tone_token(grapheme: str) -> bool:
    if not grapheme:
        return False
    for ch in grapheme:
        if ch in _TONE_LETTERS:
            continue
        if ch in _CHAO_SUPERSCRIPTS:
            continue
        if ch.isdigit():
            continue
        return False
    return True


def _role_from_plain_features(feats: frozenset[str]) -> str | None:
    if "vowel" in feats:
        return "V"
    if "consonant" in feats:
        if _ROLE_R_FEATURES & feats:
            return "R"
        if _ROLE_G_FEATURES & feats:
            return "G"
        if _ROLE_C_FEATURES & feats:
            return "C"
        return None
    return None


def _role_from_valued_features(feats: frozenset[str]) -> str | None:
    if "syllabic=+" in feats:
        return "V"
    if "consonantal=+" in feats or "consonant=+" in feats:
        if _ROLE_R_STATES & feats:
            return "R"
        if _ROLE_G_STATES & feats:
            return "G"
        return "C"
    if "sonorant=+" in feats and "approximant=+" in feats:
        return "G"
    return None


def _derive_role(grapheme: str, system_obj: FeatureSystem) -> str:
    try:
        desc_feats = get_system("descriptive").grapheme_to_features(grapheme)
    except KeyError:
        desc_feats = None
    if desc_feats:
        role = _role_from_plain_features(desc_feats)
        if role is not None:
            return role

    feats = system_obj.grapheme_to_features(grapheme)
    if feats:
        role = _role_from_plain_features(feats)
        if role is not None:
            return role
        role = _role_from_valued_features(feats)
        if role is not None:
            return role

    if _is_tone_token(grapheme):
        return "T"
    if grapheme in _STANDALONE_SUPRASEG:
        return "S"

    return "X"


def _maybe_class_rows(
    system_obj: FeatureSystem,
    graphemes: Iterable[str],
) -> list[tuple[str, str]] | None:
    if system_obj.name != "classfeat":
        return None
    from merkmal.systems.classfeat import classify_to_class

    rows: list[tuple[str, str]] = []
    for g in graphemes:
        cls = classify_to_class(g)
        if cls is not None:
            rows.append((g, cls))
    return rows


def _compute_raw_distances(
    system: str,
    graphemes: list[str],
) -> tuple[list[list[float]], float]:
    n = len(graphemes)
    matrix = [[0.0] * n for _ in range(n)]
    d_max = 0.0
    for i in range(n):
        a = graphemes[i]
        for j in range(i + 1, n):
            b = graphemes[j]
            d = _analysis_distance(a, b, system=system)
            if math.isnan(d) or math.isinf(d):
                msg = f"Non-finite distance for ({a!r}, {b!r}) in system {system!r}: {d}"
                raise CognatorExportError(msg)
            if d < 0.0:
                msg = f"Negative distance for ({a!r}, {b!r}) in system {system!r}: {d}"
                raise CognatorExportError(msg)
            matrix[i][j] = d
            matrix[j][i] = d
            if d > d_max:
                d_max = d
    return matrix, d_max


def _write_bytes(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def _tsv_bytes(header: list[str], rows: Iterable[list[str]]) -> bytes:
    parts = ["\t".join(header)]
    parts.extend("\t".join(row) for row in rows)
    return ("\n".join(parts) + "\n").encode("utf-8")


def _file_meta(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"present": False, "sha256": "", "rows": 0, "bytes": 0}
    data = path.read_bytes()
    rows = max(0, data.count(b"\n") - 1)
    return {
        "present": True,
        "sha256": hashlib.sha256(data).hexdigest(),
        "rows": rows,
        "bytes": len(data),
    }


def export_cognator(
    system: str,
    out_dir: str | Path,
    *,
    force: bool = False,
) -> Path:
    """Export a merkmal feature system to a cognator bundle.

    Produces ``distances.tsv``, ``prosody.tsv``, ``fallback.tsv``, and
    (when the system has a class reduction) ``classes.tsv`` under
    *out_dir*, together with a ``manifest.json`` listing merkmal version,
    export date, row counts, and SHA-256 hashes.

    Byte-stable under ``SOURCE_DATE_EPOCH``.
    """
    registry = get_registry()
    if system not in registry.list_systems():
        msg = f"Unknown feature system: {system!r}. Available: {registry.list_systems()}"
        raise KeyError(msg)
    system_obj = registry.get_system(system)

    out_path = Path(out_dir)
    if out_path.exists() and out_path.is_dir() and any(out_path.iterdir()) and not force:
        msg = f"Output directory {out_path!s} is not empty; pass force=True to overwrite"
        raise FileExistsError(msg)
    out_path.mkdir(parents=True, exist_ok=True)

    raw_graphemes = list(system_obj.list_graphemes())
    nfc_graphemes = sorted({_nfc(g) for g in raw_graphemes})
    n = len(nfc_graphemes)

    raw_matrix, d_max_raw = _compute_raw_distances(system, nfc_graphemes)
    d_max_for_norm = d_max_raw if d_max_raw > 0.0 else 1.0

    dist_rows: list[list[str]] = []
    for i in range(n):
        a = nfc_graphemes[i]
        for j in range(n):
            b = nfc_graphemes[j]
            if i == j:
                d_norm = 0.0
            else:
                d_norm = raw_matrix[i][j] / d_max_for_norm
                if d_norm < 0.0:
                    d_norm = 0.0
                elif d_norm > 1.0:
                    d_norm = 1.0
            dist_rows.append([a, b, _format_float(d_norm)])
    _write_bytes(
        out_path / "distances.tsv",
        _tsv_bytes(["grapheme_a", "grapheme_b", "distance"], dist_rows),
    )

    class_rows = _maybe_class_rows(system_obj, nfc_graphemes)
    classes_path = out_path / "classes.tsv"
    if class_rows is not None:
        sorted_class_rows = sorted(class_rows)
        _write_bytes(
            classes_path,
            _tsv_bytes(["grapheme", "class"], [[g, c] for g, c in sorted_class_rows]),
        )
    elif classes_path.exists():
        classes_path.unlink()

    prosody_rows: list[tuple[str, str]] = []
    role_of: dict[str, str] = {}
    unknown: list[str] = []
    for g in nfc_graphemes:
        role = _derive_role(g, system_obj)
        role_of[g] = role
        if role == "X":
            unknown.append(g)
        prosody_rows.append((g, role))
    prosody_rows.sort()
    _write_bytes(
        out_path / "prosody.tsv",
        _tsv_bytes(
            ["grapheme", "role"],
            [[g, r] for g, r in prosody_rows],
        ),
    )
    if unknown:
        preview = ", ".join(repr(g) for g in unknown[:10])
        suffix = "..." if len(unknown) > 10 else ""
        warnings.warn(
            f"{len(unknown)} grapheme(s) in system {system!r} "
            f"mapped to prosody role 'X': [{preview}{suffix}]",
            stacklevel=2,
        )

    feats_of: dict[str, frozenset[str] | None] = {
        g: system_obj.grapheme_to_features(g) for g in nfc_graphemes
    }
    partition_rows, class_counts = compute_partitions(
        system, nfc_graphemes, role_of, feats_of,
    )
    _write_bytes(
        out_path / "partitions.tsv",
        _tsv_bytes(
            ["grapheme", "level", "class_code", "class_full"],
            [[r.grapheme, r.level, r.class_code, r.class_full] for r in partition_rows],
        ),
    )
    partition_unclassified = unclassified_graphemes(partition_rows)
    if partition_unclassified:
        preview = ", ".join(repr(g) for g in partition_unclassified[:10])
        suffix = "..." if len(partition_unclassified) > 10 else ""
        warnings.warn(
            f"{len(partition_unclassified)} grapheme(s) in system {system!r} "
            f"mapped to partition class 'X' (unclassified): [{preview}{suffix}]",
            stacklevel=2,
        )

    _write_bytes(
        out_path / "fallback.tsv",
        _tsv_bytes(["input", "target", "note"], []),
    )

    file_names = [
        "distances.tsv", "classes.tsv", "prosody.tsv",
        "partitions.tsv", "fallback.tsv",
    ]
    files_meta = {name: _file_meta(out_path / name) for name in file_names}

    level_features = level_features_by_system(system)
    partitions_manifest = {
        "levels": list(PARTITION_LEVELS),
        "definitions": {
            level: {
                "features": list(level_features[level]),
                "class_count": class_counts[level],
            }
            for level in PARTITION_LEVELS
        },
    }

    from merkmal import __version__

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "merkmal_version": __version__,
        "system": system,
        "export_date": _resolve_export_date(),
        "distance_normalization": {
            "method": "linear_scale",
            "d_max_raw": d_max_raw,
            "description": "d' = clip(d_raw / d_max_raw, 0, 1)",
        },
        "grapheme_count": n,
        "partitions": partitions_manifest,
        "files": files_meta,
    }
    manifest_path = out_path / "manifest.json"
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    manifest_path.write_bytes(manifest_text.encode("utf-8"))
    return manifest_path


def export_all_systems(
    out_dir: str | Path,
    *,
    force: bool = False,
) -> list[Path]:
    """Export every registered system to ``<out_dir>/<system>/``."""
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    manifests: list[Path] = []
    for system in get_registry().list_systems():
        manifests.append(export_cognator(system, root / system, force=force))
    return manifests
