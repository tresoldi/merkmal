"""Model and geometry discovery and loading.

Locates model directories under ``models/`` and geometry files under
``geometries/``, reads their JSON/TSV data, and dispatches to the
appropriate engine to create a FeatureSystem.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent


def _find_dir(name: str, env_var: str) -> Path:
    env = os.environ.get(env_var)
    if env:
        p = Path(env)
        if p.is_dir():
            return p
    candidate = _ROOT / name
    if candidate.is_dir():
        return candidate
    msg = (
        f"Cannot find {name}/ directory. Set {env_var} or ensure "
        f"{candidate} exists."
    )
    raise FileNotFoundError(msg)


def find_models_dir() -> Path:
    return _find_dir("models", "MERKMAL_MODELS")


def find_geometries_dir() -> Path:
    return _find_dir("geometries", "MERKMAL_GEOMETRIES")


def list_available_models() -> list[str]:
    models_dir = find_models_dir()
    return sorted(
        d.name for d in models_dir.iterdir()
        if d.is_dir() and (d / "model.json").exists()
    )


# ── TSV loading ─────────────────────────────────────────────────────────

def read_tsv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        rows = list(reader)
    return header, rows


# ── Model config ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ModelConfig:
    """Parsed model.json plus loaded data files."""

    name: str
    version: str
    model_type: str
    description: str
    default_geometry: str
    raw: dict[str, Any]
    model_dir: Path

    # Categorical fields
    feature_extraction: str = ""
    scalar_dimensions: tuple[dict[str, Any], ...] = ()

    # Data loaded from files
    inventory_header: tuple[str, ...] = ()
    inventory_rows: tuple[tuple[str, ...], ...] = ()

    # Categorical-specific
    feature_categories: dict[str, str] = field(default_factory=dict)
    classes_data: dict[str, tuple[str, str, tuple[str, ...]]] = field(default_factory=dict)

    # Partition config
    partitions: dict[str, dict[str, tuple[str, ...]]] = field(default_factory=dict)


def load_model_config(model_dir: Path) -> ModelConfig:
    mj_path = model_dir / "model.json"
    raw = json.loads(mj_path.read_text(encoding="utf-8"))

    model_type = raw["type"]

    # Load inventory.tsv
    inv_path = model_dir / "inventory.tsv"
    inv_header, inv_rows = read_tsv(inv_path)

    # Load features.tsv (categorical only)
    feature_categories: dict[str, str] = {}
    feat_path = model_dir / "features.tsv"
    if feat_path.exists():
        _, feat_rows = read_tsv(feat_path)
        for row in feat_rows:
            if len(row) >= 2:
                feature_categories[row[0]] = row[1]

    # Load classes.tsv (categorical only)
    classes_data: dict[str, tuple[str, str, tuple[str, ...]]] = {}
    cls_path = model_dir / "classes.tsv"
    if cls_path.exists():
        _, cls_rows = read_tsv(cls_path)
        for row in cls_rows:
            if len(row) >= 4:
                graphemes = tuple(row[3].split("|")) if row[3] else ()
                classes_data[row[0]] = (row[1], row[2], graphemes)

    # Parse partitions
    partitions: dict[str, dict[str, tuple[str, ...]]] = {}
    for level, roles in raw.get("partitions", {}).items():
        partitions[level] = {
            role: tuple(slots) for role, slots in roles.items()
        }

    # Scalar dimensions
    scalar_dims = tuple(raw.get("scalar_dimensions", []))

    return ModelConfig(
        name=raw["name"],
        version=raw.get("version", "0.0.0"),
        model_type=model_type,
        description=raw.get("description", ""),
        default_geometry=raw.get("default_geometry", "clements-hume"),
        raw=raw,
        model_dir=model_dir,
        feature_extraction=raw.get("feature_extraction", ""),
        scalar_dimensions=scalar_dims,
        inventory_header=tuple(inv_header),
        inventory_rows=tuple(tuple(r) for r in inv_rows),
        feature_categories=feature_categories,
        classes_data=classes_data,
        partitions=partitions,
    )


# ── Model instantiation ────────────────────────────────────────────────

def load_model(name: str, geometry: Any = None) -> Any:
    """Load a named model and return a FeatureSystem instance.

    If *geometry* is None, loads the model's default geometry.
    """
    from merkmal.engines.categorical import CategoricalEngine
    from merkmal.engines.trained import TrainedEngine
    from merkmal.engines.valued import ValuedEngine
    from merkmal.geometry import load_geometry

    models_dir = find_models_dir()
    model_dir = models_dir / name
    if not model_dir.is_dir():
        msg = f"Model not found: {name}"
        raise FileNotFoundError(msg)

    config = load_model_config(model_dir)

    if geometry is None:
        geometry = load_geometry(config.default_geometry)

    if config.model_type == "categorical":
        return CategoricalEngine(config=config, geometry=geometry)
    if config.model_type == "valued":
        return ValuedEngine(config=config, geometry=geometry)
    if config.model_type == "trained":
        return TrainedEngine(config=config, geometry=geometry)

    msg = f"Unknown model type: {config.model_type}"
    raise ValueError(msg)
