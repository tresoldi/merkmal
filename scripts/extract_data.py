#!/usr/bin/env python3
"""Extract merkmal data into model directories and geometry files.

Phase 1 of the data-code decoupling plan. Reads live Python data
structures and writes them as self-contained JSON/TSV files.
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


# ── Geometry extraction ─────────────────────────────────────────────────

def extract_geometry() -> None:
    from merkmal.geometry import (
        DEFAULT_GEOMETRY,
        FEATURE_TO_GEOMETRY_NODE,
        FeatureNode,
        GeometryNode,
        _WEIGHT_PRESETS,
    )

    def node_to_dict(node: GeometryNode | FeatureNode) -> dict:
        if isinstance(node, FeatureNode):
            return {
                "name": node.name,
                "positive": node.positive,
                "negative": node.negative,
            }
        return {
            "name": node.name,
            "children": [node_to_dict(c) for c in node.children],
        }

    presets = {}
    for name, value in _WEIGHT_PRESETS.items():
        if name == "flat":
            presets[name] = "__flat__"
        else:
            presets[name] = value

    geometry = {
        "schema_version": 1,
        "name": "clements-hume",
        "version": "1.0.0",
        "description": "Clements & Hume (1995) feature geometry",
        "reference": "Clements, G.N. & Hume, E.V. (1995). The internal organization of speech sounds.",
        "weight_presets": presets,
        "feature_to_node": dict(sorted(FEATURE_TO_GEOMETRY_NODE.items())),
        "tree": node_to_dict(DEFAULT_GEOMETRY),
    }

    out = GEOM_DIR / "clements-hume.json"
    out.write_text(json.dumps(geometry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  wrote {out} ({len(FEATURE_TO_GEOMETRY_NODE)} feature mappings)")


# ── Helpers ─────────────────────────────────────────────────────────────

def write_tsv(path: Path, header: list[str], rows: list[list[str]]) -> int:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)
    return len(rows)


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ── Categorical models (descriptive, broad, distinctive) ────────────────

def extract_categorical_data() -> None:
    """Extract shared inventory, features, and classes for categorical models."""
    from merkmal.dataset import load_builtin_dataset

    ds = load_builtin_dataset()

    # inventory.tsv (same for all three)
    inv_rows = [[g, name] for g, name in sorted(ds.sounds.items())]

    # features.tsv
    feat_rows = [[v, f] for v, f in sorted(ds.features)]

    # classes.tsv
    class_rows = []
    for cls_name in sorted(ds.classes):
        desc, feats_str, graphemes = ds.classes[cls_name]
        class_rows.append([cls_name, desc, feats_str, "|".join(graphemes)])

    for model_name in ("descriptive", "broad", "distinctive"):
        model_dir = MODELS_DIR / model_name
        n = write_tsv(model_dir / "inventory.tsv", ["GRAPHEME", "NAME"], inv_rows)
        print(f"  {model_name}/inventory.tsv: {n} graphemes")
        n = write_tsv(model_dir / "features.tsv", ["VALUE", "FEATURE"], feat_rows)
        print(f"  {model_name}/features.tsv: {n} entries")
        n = write_tsv(model_dir / "classes.tsv",
                       ["SOUND_CLASS", "DESCRIPTION", "FEATURES", "GRAPHEMES"],
                       class_rows)
        print(f"  {model_name}/classes.tsv: {n} classes")


def extract_descriptive_model() -> None:
    from merkmal.partitions import _CATEGORICAL_SLOTS

    model = {
        "schema_version": 1,
        "name": "descriptive",
        "version": "1.0.0",
        "type": "categorical",
        "description": "Articulatory feature system based on IPA descriptions",
        "author": "Tiago Tresoldi",
        "license": "MIT",
        "default_geometry": "clements-hume",
        "feature_extraction": "filtered",
        "partitions": {
            level: {role: list(slots) for role, slots in roles.items()}
            for level, roles in _CATEGORICAL_SLOTS.items()
        },
    }
    out = MODELS_DIR / "descriptive" / "model.json"
    write_json(out, model)
    print(f"  wrote {out}")


def extract_broad_model() -> None:
    from merkmal.partitions import _CATEGORICAL_SLOTS

    model = {
        "schema_version": 1,
        "name": "broad",
        "version": "1.0.0",
        "type": "categorical",
        "description": "Simplified categorical system keeping all name tokens",
        "author": "Tiago Tresoldi",
        "license": "MIT",
        "default_geometry": "clements-hume",
        "feature_extraction": "unfiltered",
        "partitions": {
            level: {role: list(slots) for role, slots in roles.items()}
            for level, roles in _CATEGORICAL_SLOTS.items()
        },
    }
    out = MODELS_DIR / "broad" / "model.json"
    write_json(out, model)
    print(f"  wrote {out}")


def extract_distinctive_model() -> None:
    from merkmal.partitions import _CATEGORICAL_SLOTS
    from merkmal.systems.distinctive import _SCALAR_DIMENSIONS

    dims = []
    for d in _SCALAR_DIMENSIONS:
        dims.append({
            "name": d.name,
            "positive": sorted(d.positive),
            "negative": sorted(d.negative),
            "geometry_node": d.geometry_node,
        })

    model = {
        "schema_version": 1,
        "name": "distinctive",
        "version": "1.0.0",
        "type": "categorical",
        "description": "Clements & Hume distinctive features with scalar dimensions",
        "author": "Tiago Tresoldi",
        "license": "MIT",
        "default_geometry": "clements-hume",
        "feature_extraction": "filtered",
        "scalar_dimensions": dims,
        "partitions": {
            level: {role: list(slots) for role, slots in roles.items()}
            for level, roles in _CATEGORICAL_SLOTS.items()
        },
    }
    out = MODELS_DIR / "distinctive" / "model.json"
    write_json(out, model)
    print(f"  wrote {out} ({len(dims)} scalar dimensions)")


# ── PHOIBLE ─────────────────────────────────────────────────────────────

def extract_phoible() -> None:
    from merkmal.systems.phoible import _PHOIBLE_GEOMETRY, _phoible_table

    feature_names, table = _phoible_table()

    # inventory.tsv with feature columns
    header = ["GRAPHEME"] + list(feature_names)
    rows = []
    for grapheme in sorted(table):
        row = [grapheme]
        for feat in feature_names:
            row.append(table[grapheme][feat].value)
        rows.append(row)

    model_dir = MODELS_DIR / "phoible"
    n = write_tsv(model_dir / "inventory.tsv", header, rows)
    print(f"  phoible/inventory.tsv: {n} graphemes, {len(feature_names)} features")

    # Partition slots from partitions.py
    from merkmal.partitions import _VALUED_SLOTS
    phoible_partitions = _VALUED_SLOTS.get("phoible", {})

    model = {
        "schema_version": 1,
        "name": "phoible",
        "version": "1.0.0",
        "type": "valued",
        "description": "PHOIBLE binary features (37 dimensions)",
        "license": "CC-BY",
        "default_geometry": "clements-hume",
        "state_symbols": {"+": 1.0, "-": -1.0, "0": None},
        "geometry_map": dict(sorted(_PHOIBLE_GEOMETRY.items())),
        "partitions": {
            level: {role: list(slots) for role, slots in roles.items()}
            for level, roles in phoible_partitions.items()
        },
    }
    write_json(model_dir / "model.json", model)
    print(f"  wrote phoible/model.json")


# ── P-base families ─────────────────────────────────────────────────────

def extract_pbase() -> None:
    from merkmal.partitions import _VALUED_SLOTS
    from merkmal.systems.pbase import (
        _FAMILY_GEOMETRY,
        _SUPPORTED_FAMILIES,
        _pbase_table,
    )

    for family in _SUPPORTED_FAMILIES:
        table = _pbase_table(family)
        geom_map = _FAMILY_GEOMETRY[family]

        # Collect all feature names for this family
        all_features: list[str] = []
        if table:
            first = next(iter(table.values()))
            all_features = list(first.keys())

        # inventory.tsv
        header = ["GRAPHEME"] + all_features
        rows = []
        for grapheme in sorted(table):
            row = [grapheme]
            for feat in all_features:
                row.append(table[grapheme][feat].value)
            rows.append(row)

        model_name = f"pbase-{family}"
        model_dir = MODELS_DIR / model_name
        n = write_tsv(model_dir / "inventory.tsv", header, rows)
        print(f"  {model_name}/inventory.tsv: {n} graphemes, {len(all_features)} features")

        # Partition slots
        pbase_partitions = _VALUED_SLOTS.get(model_name, {})

        # State symbols for pbase (all 6 states)
        state_syms = {
            "+": 1.0,
            "-": -1.0,
            ".": None,
            "n": 0.0,
            "o": 0.0,
            "x": 0.0,
        }

        model = {
            "schema_version": 1,
            "name": model_name,
            "version": "1.0.0",
            "type": "valued",
            "description": f"P-base feature system, {family.upper()} family",
            "license": "CC-BY-NC-SA-4.0",
            "default_geometry": "clements-hume",
            "state_symbols": state_syms,
            "geometry_map": dict(sorted(geom_map.items())),
            "partitions": {
                level: {role: list(slots) for role, slots in roles.items()}
                for level, roles in pbase_partitions.items()
            },
        }
        write_json(model_dir / "model.json", model)
        print(f"  wrote {model_name}/model.json")


# ── ClassFeat ───────────────────────────────────────────────────────���───

def extract_classfeat() -> None:
    import shutil

    from merkmal.partitions import _VALUED_SLOTS
    from merkmal.systems.classfeat import (
        CLASS_NAMES,
        FEATURE_NAMES,
        GEOMETRY_MAP,
        _CLASS_PROTOTYPES,
        _SCA_CLASSES,
        _load_weights,
    )

    model_dir = MODELS_DIR / "classfeat"

    # inventory.tsv: grapheme → class
    rows = []
    for cls in CLASS_NAMES:
        for grapheme in sorted(_SCA_CLASSES[cls]):
            rows.append([grapheme, cls])
    rows.sort(key=lambda r: r[0])
    n = write_tsv(model_dir / "inventory.tsv", ["GRAPHEME", "CLASS"], rows)
    print(f"  classfeat/inventory.tsv: {n} grapheme-class pairs")

    # Copy weights.json
    weights_src = SRC / "merkmal" / "data" / "classfeat" / "weights.json"
    weights_dst = model_dir / "weights.json"
    if weights_src.exists():
        shutil.copy2(weights_src, weights_dst)
        print(f"  classfeat/weights.json: copied")
    else:
        # Generate default weights
        weights = _load_weights()
        write_json(weights_dst, weights)
        print(f"  classfeat/weights.json: generated defaults")

    # Partition slots
    classfeat_partitions = _VALUED_SLOTS.get("classfeat", {})

    # Class prototypes
    prototypes = {}
    for cls_name, proto in sorted(_CLASS_PROTOTYPES.items()):
        prototypes[cls_name] = proto

    # Sound classes
    sound_classes = {}
    for cls_name in CLASS_NAMES:
        sound_classes[cls_name] = sorted(_SCA_CLASSES[cls_name])

    model = {
        "schema_version": 1,
        "name": "classfeat",
        "version": "1.0.0",
        "type": "trained",
        "description": "Trained hybrid: 24 sound classes + continuous features",
        "author": "Tiago Tresoldi",
        "license": "MIT",
        "default_geometry": "clements-hume",
        "alpha": 0.5,
        "feature_names": list(FEATURE_NAMES),
        "geometry_map": dict(sorted(GEOMETRY_MAP.items())),
        "sound_classes": sound_classes,
        "class_prototypes": prototypes,
        "partitions": {
            level: {role: list(slots) for role, slots in roles.items()}
            for level, roles in classfeat_partitions.items()
        },
    }
    write_json(model_dir / "model.json", model)
    print(f"  wrote classfeat/model.json")


# ── Main ────────────────────────────────────────────────────────────────

def main() -> None:
    print("Phase 1: Data Extraction")
    print("=" * 60)

    print("\n[1/7] Geometry...")
    extract_geometry()

    print("\n[2/7] Categorical data (shared inventory/features/classes)...")
    extract_categorical_data()

    print("\n[3/7] Descriptive model...")
    extract_descriptive_model()

    print("\n[4/7] Broad model...")
    extract_broad_model()

    print("\n[5/7] Distinctive model...")
    extract_distinctive_model()

    print("\n[6/7] PHOIBLE model...")
    extract_phoible()

    print("\n[7/7] P-base models...")
    extract_pbase()

    print("\n[8/8] ClassFeat model...")
    extract_classfeat()

    print("\n" + "=" * 60)
    print("Done. Verify with: python scripts/validate_models.py")


if __name__ == "__main__":
    main()
