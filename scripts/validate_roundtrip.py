#!/usr/bin/env python3
"""Roundtrip validation: compare extracted model data against live Python objects.

Ensures the extracted TSV/JSON files exactly match the in-memory data
structures from the current Python code.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

MODELS_DIR = ROOT / "models"
GEOM_DIR = ROOT / "geometries"

errors = 0


def check(condition: bool, msg: str) -> None:
    global errors
    if condition:
        print(f"  OK:    {msg}")
    else:
        print(f"  FAIL:  {msg}")
        errors += 1


def read_tsv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        rows = list(reader)
    return header, rows


def validate_geometry_roundtrip() -> None:
    print("\n[Geometry roundtrip]")
    from merkmal.geometry import (
        DEFAULT_GEOMETRY,
        FEATURE_TO_GEOMETRY_NODE,
        FeatureNode,
        GeometryNode,
    )

    data = json.loads((GEOM_DIR / "clements-hume.json").read_text("utf-8"))

    # feature_to_node
    extracted_ftn = data["feature_to_node"]
    check(
        extracted_ftn == dict(sorted(FEATURE_TO_GEOMETRY_NODE.items())),
        f"feature_to_node matches ({len(extracted_ftn)} entries)",
    )

    # tree structure: count leaves recursively
    def count_py_leaves(node: GeometryNode | FeatureNode) -> int:
        if isinstance(node, FeatureNode):
            return 1
        return sum(count_py_leaves(c) for c in node.children)

    def count_json_leaves(node: dict) -> int:
        if "positive" in node:
            return 1
        return sum(count_json_leaves(c) for c in node.get("children", []))

    py_leaves = count_py_leaves(DEFAULT_GEOMETRY)
    json_leaves = count_json_leaves(data["tree"])
    check(py_leaves == json_leaves, f"leaf count: Python={py_leaves}, JSON={json_leaves}")

    # Verify leaf data matches
    def get_py_leaves(node: GeometryNode | FeatureNode) -> list[tuple[str, str, str]]:
        if isinstance(node, FeatureNode):
            return [(node.name, node.positive, node.negative)]
        result = []
        for c in node.children:
            result.extend(get_py_leaves(c))
        return result

    def get_json_leaves(node: dict) -> list[tuple[str, str, str]]:
        if "positive" in node:
            return [(node["name"], node["positive"], node["negative"])]
        result = []
        for c in node.get("children", []):
            result.extend(get_json_leaves(c))
        return result

    py_l = sorted(get_py_leaves(DEFAULT_GEOMETRY))
    json_l = sorted(get_json_leaves(data["tree"]))
    check(py_l == json_l, "all leaf (name, positive, negative) tuples match")


def validate_categorical_roundtrip(model_name: str) -> None:
    print(f"\n[{model_name} roundtrip]")
    from merkmal.dataset import load_builtin_dataset

    ds = load_builtin_dataset()

    # inventory
    _, rows = read_tsv(MODELS_DIR / model_name / "inventory.tsv")
    extracted_sounds = {r[0]: r[1] for r in rows}
    check(
        extracted_sounds == dict(sorted(ds.sounds.items())),
        f"inventory matches ({len(extracted_sounds)} graphemes)",
    )

    # features
    _, rows = read_tsv(MODELS_DIR / model_name / "features.tsv")
    extracted_feats = [(r[0], r[1]) for r in rows]
    py_feats = sorted(ds.features)
    check(
        extracted_feats == py_feats,
        f"features match ({len(extracted_feats)} entries)",
    )


def validate_phoible_roundtrip() -> None:
    print("\n[phoible roundtrip]")
    from merkmal.systems.phoible import _PHOIBLE_GEOMETRY, _phoible_table

    feature_names, table = _phoible_table()

    header, rows = read_tsv(MODELS_DIR / "phoible" / "inventory.tsv")
    check(header[0] == "GRAPHEME", "first column is GRAPHEME")
    check(tuple(header[1:]) == feature_names, f"feature columns match ({len(feature_names)})")

    extracted = {}
    for row in rows:
        grapheme = row[0]
        extracted[grapheme] = {header[i+1]: row[i+1] for i in range(len(feature_names))}

    check(set(extracted.keys()) == set(table.keys()), "grapheme sets match")

    mismatches = 0
    for g in table:
        if g not in extracted:
            continue
        for feat in feature_names:
            py_val = table[g][feat].value
            ex_val = extracted[g][feat]
            if py_val != ex_val:
                mismatches += 1
    check(mismatches == 0, f"all feature values match (checked {len(table)} * {len(feature_names)})")


def validate_pbase_roundtrip(family: str) -> None:
    model_name = f"pbase-{family}"
    print(f"\n[{model_name} roundtrip]")
    from merkmal.systems.pbase import _FAMILY_GEOMETRY, _pbase_table

    table = _pbase_table(family)
    geom_map = _FAMILY_GEOMETRY[family]

    header, rows = read_tsv(MODELS_DIR / model_name / "inventory.tsv")
    feature_names = header[1:]

    extracted = {}
    for row in rows:
        grapheme = row[0]
        extracted[grapheme] = {feature_names[i]: row[i+1] for i in range(len(feature_names))}

    check(set(extracted.keys()) == set(table.keys()),
          f"grapheme sets match ({len(table)})")

    mismatches = 0
    for g in table:
        if g not in extracted:
            continue
        for feat in table[g]:
            py_val = table[g][feat].value
            ex_val = extracted[g].get(feat, "")
            if py_val != ex_val:
                mismatches += 1
    check(mismatches == 0, f"all feature values match")

    # geometry_map
    mj = json.loads((MODELS_DIR / model_name / "model.json").read_text("utf-8"))
    check(mj["geometry_map"] == dict(sorted(geom_map.items())),
          f"geometry_map matches ({len(geom_map)} entries)")


def validate_classfeat_roundtrip() -> None:
    print("\n[classfeat roundtrip]")
    from merkmal.systems.classfeat import (
        CLASS_NAMES,
        _CLASS_PROTOTYPES,
        _SCA_CLASSES,
    )

    # inventory (grapheme → class)
    _, rows = read_tsv(MODELS_DIR / "classfeat" / "inventory.tsv")
    extracted_map = {r[0]: r[1] for r in rows}

    py_map = {}
    for cls in CLASS_NAMES:
        for g in _SCA_CLASSES[cls]:
            py_map[g] = cls

    check(extracted_map == py_map, f"grapheme→class map matches ({len(py_map)} entries)")

    # model.json class info
    mj = json.loads((MODELS_DIR / "classfeat" / "model.json").read_text("utf-8"))

    for cls in CLASS_NAMES:
        py_members = sorted(_SCA_CLASSES[cls])
        ex_members = mj["sound_classes"].get(cls, [])
        if py_members != ex_members:
            print(f"  FAIL:  class {cls}: Python={py_members}, JSON={ex_members}")

    check(
        set(mj["class_prototypes"].keys()) == set(_CLASS_PROTOTYPES.keys()),
        f"class_prototypes keys match ({len(_CLASS_PROTOTYPES)})",
    )

    # Verify prototype values
    proto_mismatches = 0
    for cls in _CLASS_PROTOTYPES:
        py_proto = _CLASS_PROTOTYPES[cls]
        ex_proto = mj["class_prototypes"].get(cls, {})
        for feat, val in py_proto.items():
            if ex_proto.get(feat) != val:
                proto_mismatches += 1
    check(proto_mismatches == 0, "all class prototype values match")


def main() -> None:
    print("Roundtrip Validation")
    print("=" * 60)

    validate_geometry_roundtrip()
    validate_categorical_roundtrip("descriptive")
    validate_phoible_roundtrip()
    for fam in ("hc", "jfh", "spe", "uftc"):
        validate_pbase_roundtrip(fam)
    validate_classfeat_roundtrip()

    print("\n" + "=" * 60)
    if errors:
        print(f"FAILED: {errors} error(s)")
        sys.exit(1)
    else:
        print("ALL ROUNDTRIP CHECKS PASSED")


if __name__ == "__main__":
    main()
