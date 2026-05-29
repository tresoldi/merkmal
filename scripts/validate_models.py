#!/usr/bin/env python3
"""Validate model directories and geometry files.

Checks: all model.json files are valid, all referenced data files
exist and have expected structure, geometry tree is well-formed.

Usage:
    validate_models.py                 # validate the bundled models
    validate_models.py PATH [PATH ...] # validate your own model dir(s)

The second form is for users bringing their own model: point it at a
directory containing a model.json. See docs/custom-models.md.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
GEOM_DIR = ROOT / "geometries"

errors: list[str] = []
warnings: list[str] = []


def error(msg: str) -> None:
    errors.append(msg)
    print(f"  ERROR: {msg}")


def warn(msg: str) -> None:
    warnings.append(msg)
    print(f"  WARN:  {msg}")


def ok(msg: str) -> None:
    print(f"  OK:    {msg}")


def read_tsv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        rows = list(reader)
    return header, rows


def validate_geometry() -> None:
    print("\n[Geometry: clements-hume.json]")
    path = GEOM_DIR / "clements-hume.json"
    if not path.exists():
        error(f"Missing {path}")
        return

    data = json.loads(path.read_text(encoding="utf-8"))

    for field in ("schema_version", "name", "version", "description",
                  "weight_presets", "feature_to_node", "tree"):
        if field not in data:
            error(f"Missing field: {field}")

    if data.get("schema_version") != 1:
        error(f"Expected schema_version=1, got {data.get('schema_version')}")

    tree = data.get("tree", {})
    if tree.get("name") != "Root":
        error(f"Tree root should be 'Root', got {tree.get('name')}")

    # Count leaves
    def count_leaves(node: dict) -> int:
        if "positive" in node:
            return 1
        return sum(count_leaves(c) for c in node.get("children", []))

    n_leaves = count_leaves(tree)
    ok(f"Tree has {n_leaves} leaf features")

    ftn = data.get("feature_to_node", {})
    ok(f"feature_to_node has {len(ftn)} entries")

    presets = data.get("weight_presets", {})
    ok(f"{len(presets)} weight presets")


def validate_model(name: str) -> None:
    validate_model_dir(MODELS_DIR / name, expected_name=name)


def validate_model_dir(model_dir: Path, expected_name: str | None = None) -> None:
    label = expected_name or model_dir.name
    print(f"\n[Model: {label}]")
    if not model_dir.is_dir():
        error(f"Missing directory: {model_dir}")
        return

    # model.json
    mj_path = model_dir / "model.json"
    if not mj_path.exists():
        error("Missing model.json")
        return

    mj = json.loads(mj_path.read_text(encoding="utf-8"))

    for field in ("schema_version", "name", "version", "type",
                  "description", "default_geometry"):
        if field not in mj:
            error(f"Missing field: {field}")

    model_type = mj.get("type", "")
    ok(f"type={model_type}")

    if expected_name is not None and mj.get("name") != expected_name:
        error(
            f"name mismatch: model.json says '{mj.get('name')}', "
            f"dir is '{expected_name}'"
        )

    # diacritics (optional; '' / absent means built-in IPA/CLTS set)
    diac = mj.get("diacritics")
    if diac:
        ok(f"diacritics={diac} (resolved from the diacritics search path at load time)")

    # inventory.tsv
    inv_path = model_dir / "inventory.tsv"
    if not inv_path.exists():
        error(f"Missing inventory.tsv")
        return

    header, rows = read_tsv(inv_path)
    ok(f"inventory.tsv: {len(rows)} rows, {len(header)} columns")

    if model_type == "categorical":
        if header != ["GRAPHEME", "NAME"]:
            error(f"Expected [GRAPHEME, NAME] header, got {header}")

        # features.tsv
        feat_path = model_dir / "features.tsv"
        if feat_path.exists():
            fh, fr = read_tsv(feat_path)
            if fh != ["VALUE", "FEATURE"]:
                error(f"features.tsv: expected [VALUE, FEATURE] header")
            ok(f"features.tsv: {len(fr)} entries")
        else:
            warn("No features.tsv (optional for categorical)")

        # classes.tsv
        cls_path = model_dir / "classes.tsv"
        if cls_path.exists():
            ch, cr = read_tsv(cls_path)
            ok(f"classes.tsv: {len(cr)} classes")
        else:
            warn("No classes.tsv (optional)")

        # feature_extraction
        fe = mj.get("feature_extraction")
        if fe not in ("filtered", "unfiltered"):
            error(f"feature_extraction should be 'filtered' or 'unfiltered', got {fe!r}")
        else:
            ok(f"feature_extraction={fe}")

        # scalar_dimensions (distinctive only)
        if "scalar_dimensions" in mj:
            dims = mj["scalar_dimensions"]
            ok(f"scalar_dimensions: {len(dims)} dimensions")
            for d in dims:
                for f in ("name", "positive", "negative", "geometry_node"):
                    if f not in d:
                        error(f"scalar_dimension missing field: {f}")

    elif model_type == "valued":
        if len(header) < 2:
            error("inventory.tsv needs at least GRAPHEME + 1 feature column")
        if header[0] != "GRAPHEME":
            error(f"First column should be GRAPHEME, got {header[0]}")
        n_feats = len(header) - 1
        ok(f"{n_feats} feature columns")

        # geometry_map
        gm = mj.get("geometry_map", {})
        if not gm:
            error("Missing geometry_map")
        else:
            ok(f"geometry_map: {len(gm)} entries")

        # state_symbols
        ss = mj.get("state_symbols")
        if ss:
            ok(f"state_symbols: {list(ss.keys())}")

    elif model_type == "trained":
        if header[0] != "GRAPHEME":
            error(f"First column should be GRAPHEME, got {header[0]}")

        # weights.json
        w_path = model_dir / "weights.json"
        if w_path.exists():
            ok("weights.json present")
        else:
            warn("No weights.json")

        # sound_classes
        sc = mj.get("sound_classes", {})
        ok(f"sound_classes: {len(sc)} classes")

        # class_prototypes
        cp = mj.get("class_prototypes", {})
        ok(f"class_prototypes: {len(cp)} prototypes")

        # feature_names
        fn = mj.get("feature_names", [])
        ok(f"feature_names: {len(fn)} dimensions")

    else:
        error(f"Unknown model type: {model_type}")

    # partitions (all types)
    parts = mj.get("partitions", {})
    if parts:
        ok(f"partitions: {list(parts.keys())}")
    else:
        warn("No partitions defined")


def validate_cross_model_parity() -> None:
    """Check that categorical models share identical inventories."""
    print("\n[Cross-model parity checks]")

    inventories = {}
    for name in ("descriptive", "broad", "distinctive"):
        path = MODELS_DIR / name / "inventory.tsv"
        if path.exists():
            _, rows = read_tsv(path)
            inventories[name] = set(r[0] for r in rows)

    if len(inventories) == 3:
        if inventories["descriptive"] == inventories["broad"] == inventories["distinctive"]:
            ok(f"All 3 categorical models share {len(inventories['descriptive'])} graphemes")
        else:
            error("Categorical model inventories differ!")
            for a, b in [("descriptive", "broad"), ("descriptive", "distinctive")]:
                diff = inventories[a].symmetric_difference(inventories[b])
                if diff:
                    error(f"  {a} vs {b}: {len(diff)} differences")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="model directories to validate (default: bundled models)",
    )
    args = parser.parse_args()

    print("Model Validation")
    print("=" * 60)

    if args.paths:
        for path in args.paths:
            validate_model_dir(path)
    else:
        validate_geometry()
        models = sorted(d.name for d in MODELS_DIR.iterdir() if d.is_dir())
        for name in models:
            validate_model(name)
        validate_cross_model_parity()

    print("\n" + "=" * 60)
    if errors:
        print(f"FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
        sys.exit(1)
    else:
        print(f"PASSED: {len(warnings)} warning(s)")


if __name__ == "__main__":
    main()
