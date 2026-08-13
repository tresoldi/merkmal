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
import hashlib
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


GEOMETRY_NODES: set[str] = set()
GEOMETRY_FEATURES: set[str] = set()
GEOMETRY_NAMES: set[str] = set()


def check_identifier(value: str, where: str) -> None:
    """Surrounding whitespace makes an identifier silently fail to match.

    models/pbase-jfh/model.json mapped "vocalic " with a trailing space for
    long enough to ship: the header said "vocalic", the two never matched, and
    the entire dimension was absent from every distance while every check
    passed.
    """
    if value != value.strip():
        error(f"{where}: {value!r} has leading/trailing whitespace")
    if not value:
        error(f"{where}: empty identifier")


def walk_geometry(node: dict, nodes: set[str], features: set[str], leaves: set[str]) -> None:
    name = node.get("name", "")
    if "children" in node:
        nodes.add(name)
        for child in node["children"]:
            walk_geometry(child, nodes, features, leaves)
    else:
        leaves.add(name)
        features.add(name)
        for key in ("positive", "negative"):
            if node.get(key):
                features.add(node[key])


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

    nodes: set[str] = set()
    features: set[str] = set()
    leaves: set[str] = set()
    walk_geometry(tree, nodes, features, leaves)
    GEOMETRY_NODES.update(nodes)
    GEOMETRY_FEATURES.update(features)
    GEOMETRY_NAMES.add(data.get("name", ""))
    GEOMETRY_NAMES.update(data.get("compatibility_names", []))
    ok(f"Tree has {len(leaves)} leaf features under {len(nodes)} nodes")

    # A feature owned by two leaves would score twice for one difference.
    owners: dict[str, list[str]] = {}

    def collect_owners(node: dict) -> None:
        if "children" in node:
            for child in node["children"]:
                collect_owners(child)
            return
        for key in ("positive", "negative"):
            if node.get(key):
                owners.setdefault(node[key], []).append(node["name"])

    collect_owners(tree)
    for feature, leaf_names in sorted(owners.items()):
        if len(leaf_names) > 1:
            error(f"feature {feature!r} is claimed by several leaves: {leaf_names}")
        check_identifier(feature, "geometry leaf feature")

    for scale in data.get("ordinal_scales", []):
        check_identifier(str(scale.get("name", "")), "ordinal_scale name")
        if scale.get("node") not in nodes:
            error(f"ordinal_scale {scale['name']!r} names unknown node {scale.get('node')!r}")
        levels = list(scale.get("levels", []))
        if len(levels) < 2:
            error(f"ordinal_scale {scale['name']!r} needs at least two levels")
        if len(set(levels)) != len(levels):
            error(f"ordinal_scale {scale['name']!r} repeats a level")
        for level in levels:
            check_identifier(str(level), f"ordinal_scale {scale['name']!r} level")
        default = scale.get("default_level")
        if default is not None and not (0 <= int(default) < len(levels)):
            error(f"ordinal_scale {scale['name']!r} default_level {default} is out of range")
        GEOMETRY_FEATURES.update(str(level) for level in levels)
    # A label may not be both an ordered level and a leaf pole: it would score
    # once as a step on the scale and again as a mismatch.
    scale_levels = {
        str(level)
        for scale in data.get("ordinal_scales", [])
        for level in scale.get("levels", [])
    }
    overlap = sorted(scale_levels & set(owners))
    if overlap:
        error(f"labels are both an ordered level and a leaf pole: {overlap}")
    ok(f"{len(data.get('ordinal_scales', []))} ordered scales, all naming real nodes")

    GEOMETRY_FEATURES.update(data.get("metadata_features", {}))

    ftn = data.get("feature_to_node", {})
    for feature, node_name in sorted(ftn.items()):
        check_identifier(feature, "feature_to_node key")
        if node_name not in nodes:
            error(f"feature_to_node[{feature!r}] points at unknown node {node_name!r}")
    GEOMETRY_FEATURES.update(ftn)
    ok(f"feature_to_node has {len(ftn)} entries, all resolving to real nodes")

    presets = data.get("weight_presets", {})
    for preset_name, value in sorted(presets.items()):
        if value == "__flat__":
            continue
        for node_name, weight in value.items():
            if node_name not in nodes:
                error(f"weight preset {preset_name!r} names unknown node {node_name!r}")
            if not isinstance(weight, (int, float)) or weight < 0:
                error(f"weight preset {preset_name!r}[{node_name!r}] is not a finite non-negative number")
    ok(f"{len(presets)} weight presets, all naming real nodes")

    # The theory-fidelity metadata the review asked for, so the name cannot
    # quietly drift back to claiming it implements a published model.
    if "departures" not in data or not data["departures"]:
        error("Missing 'departures': a project-specific tree must list how it differs from its inspiration")
    if data.get("theory_fidelity") != "inspired-by":
        error("Expected theory_fidelity='inspired-by'; this tree is not a published model")


# SPDX identifiers this repository knows how to describe in NOTICE. Anything
# else needs a redistribution decision before it can be bundled.
KNOWN_SPDX = {"MIT", "CC-BY-4.0", "CC-BY-SA-3.0", "CC-BY-SA-4.0", "CC-BY-NC-SA-4.0", "CC0-1.0"}


def check_provenance(model_dir: Path, mj: dict) -> None:
    """A version number is not provenance.

    "1.0.0" says nothing about which upstream release the table came from or
    what transformed it, so the build is not reproducible and the attribution
    is not checkable. UNVERIFIED entries are allowed and reported: recording
    that something is unknown is the point, guessing it is not.
    """
    path = model_dir / "provenance.json"
    if not path.exists():
        error("Missing provenance.json (see scripts/generate_notice.py)")
        return

    manifest = json.loads(path.read_text(encoding="utf-8"))
    required = (
        "artifact_id", "artifact_version", "upstream_name", "upstream_release",
        "upstream_url", "upstream_commit_or_doi", "retrieved", "transformation",
        "citation", "license_spdx", "redistribution_notes", "input_sha256",
    )
    for field in required:
        if field not in manifest:
            error(f"provenance.json missing field: {field}")

    spdx = manifest.get("license_spdx", "")
    if spdx not in KNOWN_SPDX:
        error(f"provenance.json license_spdx={spdx!r} is not a recognized SPDX expression")
    if mj.get("license") and mj["license"] != spdx:
        error(f"model.json license={mj['license']!r} disagrees with provenance license_spdx={spdx!r}")

    digests = manifest.get("input_sha256", {})
    for name, expected in digests.items():
        source = model_dir / name
        if not source.exists():
            error(f"provenance.json records a hash for missing file {name}")
            continue
        actual = hashlib.sha256(source.read_bytes()).hexdigest()
        if actual != expected:
            error(f"{name} has changed since provenance.json was written (rerun the manifest step)")
    for source in sorted(model_dir.iterdir()):
        if source.is_file() and source.name != "provenance.json" and source.name not in digests:
            error(f"{source.name} is not covered by provenance.json input_sha256")

    unverified = sorted(
        field for field in required
        if isinstance(manifest.get(field), str) and manifest[field].startswith("UNVERIFIED")
    )
    if unverified:
        warn(f"provenance not yet established for: {', '.join(unverified)}")
    else:
        ok(f"provenance complete, license {spdx}")


def check_categorical_coverage(mj: dict, rows: list[list[str]]) -> None:
    """Every label the inventory can produce must reach a scoring dimension.

    A categorical model describes each segment with a sound name, and the
    generator turns the words of that name into features. A word that no
    geometry leaf, feature_to_node entry, or scalar dimension mentions is
    parsed, stored, returned to callers, and then ignored by the scorer. That
    is how "devoiced", "apical", "unreleased", and the whole length series used
    to make no difference to any distance.
    """
    if not GEOMETRY_FEATURES:
        return

    # Same word-splitting the generator uses, kept in step via a direct import.
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        from generate_c_data import FEATURE_ALIASES  # noqa: PLC0415
    finally:
        sys.path.pop(0)

    scored = set(GEOMETRY_FEATURES)
    for dim in mj.get("scalar_dimensions", []):
        scored.update(dim.get("positive", []))
        scored.update(dim.get("negative", []))

    labels: set[str] = set()
    for row in rows:
        if len(row) < 2:
            continue
        for word in row[1].split():
            value = word.lower().strip().replace("_", "-")
            labels.add(FEATURE_ALIASES.get(value, value))

    # Derived features are added by the generator, so a label that only feeds a
    # derivation is scored through the feature it produces.
    from generate_c_data import derive_class_features  # noqa: PLC0415

    for label in list(labels):
        scored |= set(derive_class_features(frozenset({label}))) & GEOMETRY_FEATURES

    unscored = sorted(labels - scored)
    if unscored:
        error(
            f"{len(unscored)} inventory label(s) reach no scoring dimension and so "
            f"cannot affect any distance: {unscored}"
        )
    else:
        ok(f"all {len(labels)} inventory labels reach a scoring dimension")


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

    for field in ("name", "version", "type", "default_geometry"):
        if isinstance(mj.get(field), str):
            check_identifier(mj[field], f"model.json {field}")

    declared_geometry = mj.get("default_geometry", "")
    if GEOMETRY_NAMES and declared_geometry not in GEOMETRY_NAMES:
        error(
            f"default_geometry={declared_geometry!r} matches no geometry name or "
            f"compatibility name ({sorted(GEOMETRY_NAMES)})"
        )

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
        error("Missing inventory.tsv")
        return

    header, rows = read_tsv(inv_path)
    ok(f"inventory.tsv: {len(rows)} rows, {len(header)} columns")

    if model_type == "categorical":
        if header != ["GRAPHEME", "NAME"]:
            error(f"Expected [GRAPHEME, NAME] header, got {header}")

        check_categorical_coverage(mj, rows)

        # features.tsv
        feat_path = model_dir / "features.tsv"
        if feat_path.exists():
            fh, fr = read_tsv(feat_path)
            if fh != ["VALUE", "FEATURE"]:
                error("features.tsv: expected [VALUE, FEATURE] header")
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
            seen_dims: set[str] = set()
            for d in dims:
                for f in ("name", "positive", "negative", "geometry_node"):
                    if f not in d:
                        error(f"scalar_dimension missing field: {f}")
                name = d.get("name", "")
                check_identifier(name, "scalar_dimension name")
                if name in seen_dims:
                    error(f"scalar_dimension {name!r} is declared more than once")
                seen_dims.add(name)
                node = d.get("geometry_node", "")
                if GEOMETRY_NODES and node not in GEOMETRY_NODES:
                    error(f"scalar_dimension {name!r} maps to unknown geometry node {node!r}")
                overlap = set(d.get("positive", [])) & set(d.get("negative", []))
                if overlap:
                    error(f"scalar_dimension {name!r} lists {sorted(overlap)} as both positive and negative")
                for label in list(d.get("positive", [])) + list(d.get("negative", [])):
                    check_identifier(label, f"scalar_dimension {name!r} label")

    elif model_type == "valued":
        if len(header) < 2:
            error("inventory.tsv needs at least GRAPHEME + 1 feature column")
        if header[0] != "GRAPHEME":
            error(f"First column should be GRAPHEME, got {header[0]}")
        n_feats = len(header) - 1
        ok(f"{n_feats} feature columns")

        # geometry_map must agree with the inventory header exactly. A key that
        # matches no column contributes nothing; a column that no key mentions
        # is silently excluded from every distance.
        gm = mj.get("geometry_map", {})
        if not gm:
            error("Missing geometry_map")
        else:
            columns = header[1:]
            for column in columns:
                check_identifier(column, "inventory column")
            duplicates = {c for c in columns if columns.count(c) > 1}
            if duplicates:
                error(f"inventory.tsv has duplicate columns: {sorted(duplicates)}")

            for key, node in sorted(gm.items()):
                check_identifier(key, "geometry_map key")
                if GEOMETRY_NODES and node not in GEOMETRY_NODES:
                    error(f"geometry_map[{key!r}] points at unknown geometry node {node!r}")

            unmatched = sorted(set(gm) - set(columns))
            unmapped = sorted(set(columns) - set(gm))
            if unmatched:
                error(f"geometry_map keys with no inventory column: {unmatched}")
            if unmapped:
                error(f"inventory columns absent from geometry_map (they cannot affect any distance): {unmapped}")
            if not unmatched and not unmapped:
                ok(f"geometry_map: {len(gm)} entries, exactly matching the inventory header")

        # state_symbols
        ss = mj.get("state_symbols")
        if ss:
            declared = set(ss)
            used: set[str] = set()
            for row in rows:
                for cell in row[1:]:
                    used.add(cell.strip().strip('"'))
            undeclared = sorted(v for v in used - declared if v)
            if undeclared:
                error(f"inventory uses undeclared state symbols: {undeclared}")
            else:
                ok(f"state_symbols: {sorted(declared)}, covering every value used")
        else:
            error("Missing state_symbols: the meaning of each cell must be declared")

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

    check_provenance(model_dir, mj)

    # partitions (all types)
    parts = mj.get("partitions", {})
    if parts:
        ok(f"partitions: {list(parts.keys())}")
    else:
        warn("No partitions defined")


def check_scalar_weight_agreement() -> None:
    """The two scoring paths must not disagree about what a dimension costs.

    A categorical model may score through its own `scalar_dimensions` instead of
    the geometry leaves. Where a dimension shares a name with a leaf, the two
    have to cost the same, or `docs/geometry.md` describes neither of them.

    They used to disagree on all 35 shared names, for two reasons: a dimension
    was weighted at its geometry *node's* depth while the leaf of the same name
    sits one level below that node, and an explicit `weight` on a leaf was
    dropped on the scalar path -- `vocoid` is declared 0.8 and was scoring 1.0
    in `distinctive`, the system meant to become the default. Both are fixed in
    `tools/generate_c_data.py`; this is what stops them coming back.
    """
    # Ask the generator itself what weight it will emit, rather than restating
    # its rule here. A guard that reimplements the thing it guards passes when
    # both copies are wrong together, which is how the original divergence
    # survived: docs/geometry.md stated one rule and the generator applied
    # another, and nothing compared them.
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import generate_c_data
    finally:
        sys.path.pop(0)

    geometry_obj = json.loads(
        (ROOT / "geometries" / "clements-hume.json").read_text(encoding="utf-8")
    )
    # Depth convention has to come from the generator too. `geometry_leaves`
    # counts from the root's children, not from the root, and reimplementing
    # that here by eye is precisely how a guard ends up certifying a mismatch.
    leaves = {
        name: (1.0 / depth if explicit is None else float(explicit))
        for name, _pos, _neg, depth, _parent, explicit in generate_c_data.geometry_leaves(
            geometry_obj["tree"]
        )
    }
    shared = 0
    bad = 0
    for path in sorted((ROOT / "models").glob("*/model.json")):
        system = path.parent.name
        if json.loads(path.read_text(encoding="utf-8")).get("type") != "categorical":
            continue
        _kind, _entries, _gmap, _weights, dimensions = generate_c_data.load_categorical(
            system, geometry_obj
        )
        for dim in dimensions:
            name = str(dim["name"])
            if name not in leaves:
                continue
            shared += 1
            if abs(float(dim["weight"]) - leaves[name]) > 1e-12:
                error(
                    f"{system}: scalar dimension {name!r} will be emitted at weight "
                    f"{float(dim['weight']):.6f}, but the geometry leaf of the same name "
                    f"costs {leaves[name]:.6f}"
                )
                bad += 1
    if bad == 0:
        ok(f"{shared} scalar dimension(s) agree with the geometry leaves they mirror")


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
        check_scalar_weight_agreement()

    print("\n" + "=" * 60)
    if errors:
        print(f"FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
        sys.exit(1)
    else:
        print(f"PASSED: {len(warnings)} warning(s)")


if __name__ == "__main__":
    main()
