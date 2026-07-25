#!/usr/bin/env python3
"""Generate built-in C data tables from the current merkmal data files."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


CATEGORICAL_SYSTEMS = [
    "broad",
    "descriptive",
    "distinctive",
]

VALUED_SYSTEMS = [
    "pbase-hc",
    "pbase-jfh",
    "pbase-spe",
    "pbase-uftc",
    "phoible",
]

FEATURE_ALIASES = {
    "plosive": "stop",
}

NON_PULMONIC_FEATURES = frozenset({"click", "nasal-click", "implosive"})

IPA_INPUT_MAP = {
    "ɡ": "g",
    "'": "ʼ",
    "’": "ʼ",
}

LIGATURE_EXPANSIONS = {
    "ʣ": "dz",
    "ʤ": "dʒ",
    "ʥ": "dʑ",
    "ʦ": "ts",
    "ʧ": "tʃ",
    "ʨ": "tɕ",
}

ASCII_TO_IPA = {
    ":": "ː",
}

STRESS_MARKS = frozenset({"ˈ", "ˌ"})


def c_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def c_ident(value: str) -> str:
    ident = re.sub(r"[^0-9A-Za-z_]", "_", value)
    ident = re.sub(r"_+", "_", ident).strip("_")
    if not ident or ident[0].isdigit():
        ident = f"_{ident}"
    return ident.lower()


def read_tsv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader)
        rows = list(reader)
    return header, rows


def resolve_slash(grapheme: str) -> str:
    if "/" in grapheme:
        post = grapheme.rsplit("/", 1)[1]
        if post:
            return post
    return grapheme


def normalize_input_grapheme(grapheme: str) -> str:
    grapheme = resolve_slash(grapheme)
    while grapheme[:1] in STRESS_MARKS:
        grapheme = grapheme[1:]
    normalized = unicodedata.normalize("NFD", grapheme)
    out: list[str] = []
    for char in normalized:
        if char in LIGATURE_EXPANSIONS:
            out.append(LIGATURE_EXPANSIONS[char])
        elif char in ASCII_TO_IPA:
            out.append(ASCII_TO_IPA[char])
        else:
            out.append(IPA_INPUT_MAP.get(char, char))
    return "".join(out)


def parse_sound_name(
    name: str,
    feature_categories: dict[str, str],
    filter_categories: bool,
) -> frozenset[str]:
    features: set[str] = set()
    for word in name.split():
        value = word.lower().strip().replace("_", "-")
        value = FEATURE_ALIASES.get(value, value)
        if value and (not filter_categories or value in feature_categories):
            features.add(value)
    return frozenset(features)


def enrich_click_features(features: frozenset[str]) -> frozenset[str]:
    if not (features & NON_PULMONIC_FEATURES):
        return features
    added = {"non-pulmonic"}
    if "click" in features or "nasal-click" in features:
        added.add("velar")
    return features | added


def geometry_node_depth(tree: dict[str, object], name: str, depth: int = 1) -> int | None:
    if tree.get("name") == name:
        return depth
    for child in tree.get("children", []):
        if "children" in child:
            found = geometry_node_depth(child, name, depth + 1)
            if found is not None:
                return found
    return None


def geometry_leaves(tree: dict[str, object], depth: int = 1) -> list[tuple[str, str, str, int, str]]:
    result: list[tuple[str, str, str, int, str]] = []
    parent = str(tree["name"])
    for child in tree.get("children", []):
        if "children" in child:
            result.extend(geometry_leaves(child, depth + 1))
        else:
            result.append(
                (
                    str(child["name"]),
                    str(child.get("positive", "")),
                    str(child.get("negative", "")),
                    depth,
                    parent,
                )
            )
    return result


def geometry_feature_paths(
    tree: dict[str, object],
    ancestors: tuple[str, ...] = (),
    seen: set[str] | None = None,
) -> list[tuple[str, list[str]]]:
    if seen is None:
        seen = set()
    current = (*ancestors, str(tree["name"]))
    result: list[tuple[str, list[str]]] = []
    for child in tree.get("children", []):
        if "children" in child:
            result.extend(geometry_feature_paths(child, current, seen))
        else:
            leaf_name = str(child["name"])
            for value in (leaf_name, str(child.get("positive", "")), str(child.get("negative", ""))):
                if value and value not in seen:
                    seen.add(value)
                    result.append((value, [*current, leaf_name, value]))
    return result


def geometry_node_depths(tree: dict[str, object], depth: int = 1) -> list[tuple[str, int]]:
    result = [(str(tree["name"]), depth)]
    for child in tree.get("children", []):
        if "children" in child:
            result.extend(geometry_node_depths(child, depth + 1))
    return result


def geometry_node_parents(tree: dict[str, object], parent: str = "") -> list[tuple[str, str]]:
    result = [(str(tree["name"]), parent)]
    for child in tree.get("children", []):
        if "children" in child:
            result.extend(geometry_node_parents(child, str(tree["name"])))
    return result


def load_geometry() -> dict[str, object]:
    return json.loads((ROOT / "geometries" / "clements-hume.json").read_text(encoding="utf-8"))


def load_diacritics() -> dict[str, object]:
    return json.loads((ROOT / "diacritics" / "ipa-clts.json").read_text(encoding="utf-8"))


def load_categorical(name: str, geometry: dict[str, object]) -> tuple[str, list[tuple[str, list[str]]], list[tuple[str, str]], list[float], list[dict[str, object]]]:
    model_dir = ROOT / "models" / name
    raw = json.loads((model_dir / "model.json").read_text(encoding="utf-8"))
    _, inventory_rows = read_tsv(model_dir / "inventory.tsv")
    feature_categories: dict[str, str] = {}
    features_path = model_dir / "features.tsv"
    if features_path.exists():
        _, feature_rows = read_tsv(features_path)
        feature_categories = {
            row[0]: row[1]
            for row in feature_rows
            if len(row) >= 2
        }
    entries: dict[str, list[str]] = {}
    filter_categories = raw.get("feature_extraction", "") == "filtered"
    for row in inventory_rows:
        if len(row) < 2:
            continue
        grapheme, sound_name = row[0], row[1]
        features = parse_sound_name(
            sound_name,
            feature_categories=feature_categories,
            filter_categories=filter_categories,
        )
        if features:
            entries[normalize_input_grapheme(grapheme)] = sorted(enrich_click_features(features))
    scalar_dimensions = []
    tree = geometry["tree"]
    for dim in raw.get("scalar_dimensions", []):
        depth = geometry_node_depth(tree, dim["geometry_node"]) or 2
        scalar_dimensions.append(
            {
                "name": dim["name"],
                "geometry_node": dim["geometry_node"],
                "positive": list(dim.get("positive", [])),
                "negative": list(dim.get("negative", [])),
                "weight": 1.0 / depth,
            }
        )
    return "MK_SYSTEM_CATEGORICAL", sorted(entries.items()), [], [], scalar_dimensions


def load_valued(name: str, geometry: dict[str, object]) -> tuple[str, list[tuple[str, list[str]]], list[tuple[str, str]], list[float], list[dict[str, object]]]:
    model_dir = ROOT / "models" / name
    raw = json.loads((model_dir / "model.json").read_text(encoding="utf-8"))
    header, inventory_rows = read_tsv(model_dir / "inventory.tsv")

    table: dict[str, dict[str, str]] = {}
    feature_names = header[1:]
    for row in inventory_rows:
        if not row:
            continue
        grapheme = normalize_input_grapheme(row[0])
        values: dict[str, str] = {}
        for index, feature in enumerate(feature_names):
            raw_value = row[index + 1].strip().strip('"') if index + 1 < len(row) else "."
            values[feature] = raw_value if raw_value in {"+", "-", "n", ".", "o", "x"} else "."
        existing = table.get(grapheme)
        if existing is None:
            table[grapheme] = values
        elif existing != values:
            table[grapheme] = {
                key: existing[key] if existing[key] == values[key] else "."
                for key in existing
            }

    entries = {
        grapheme: sorted(f"{feature}={state}" for feature, state in values.items())
        for grapheme, values in table.items()
    }
    geometry_map = sorted(raw.get("geometry_map", {}).items())
    weights: list[float] = []
    tree = geometry["tree"]
    for _, node_name in geometry_map:
        depth = geometry_node_depth(tree, node_name) or 2
        weights.append(1.0 / depth)
    return "MK_SYSTEM_VALUED", sorted(entries.items()), geometry_map, weights, []


def emit_feature_node_map(symbol: str, entries: list[tuple[str, str]]) -> str:
    lines: list[str] = []
    if not entries:
        return ""
    lines.append(f"static const mk_feature_node_map {symbol}[] = {{")
    for feature, node in entries:
        lines.append(f"    {{{c_string(feature)}, {c_string(node)}}},")
    lines.append("};")
    lines.append("")
    lines.append(
        f"#define {symbol.upper()}_COUNT (sizeof({symbol}) / sizeof({symbol}[0]))"
    )
    lines.append("")
    return "\n".join(lines)


def emit_weights(symbol: str, weights: list[float]) -> str:
    lines: list[str] = []
    if not weights:
        return ""
    lines.append(f"static const double {symbol}[] = {{")
    for weight in weights:
        lines.append(f"    {weight:.17g},")
    lines.append("};")
    lines.append("")
    return "\n".join(lines)


def emit_scalar_dimensions(symbol: str, dimensions: list[dict[str, object]]) -> str:
    lines: list[str] = []
    dim_symbols: list[tuple[str, str]] = []

    if not dimensions:
        return ""

    for index, dim in enumerate(dimensions):
        pos_values = list(dim["positive"])
        neg_values = list(dim["negative"])
        pos_symbol = f"{symbol}_{index}_positive" if pos_values else "NULL"
        neg_symbol = f"{symbol}_{index}_negative" if neg_values else "NULL"
        dim_symbols.append((pos_symbol, neg_symbol))
        if pos_values:
            lines.append(f"static const char *const {pos_symbol}[] = {{")
            for feature in pos_values:
                lines.append(f"    {c_string(str(feature))},")
            lines.append("};")
            lines.append("")
        if neg_values:
            lines.append(f"static const char *const {neg_symbol}[] = {{")
            for feature in neg_values:
                lines.append(f"    {c_string(str(feature))},")
            lines.append("};")
            lines.append("")

    lines.append(f"static const mk_scalar_dimension {symbol}[] = {{")
    for index, dim in enumerate(dimensions):
        pos_symbol, neg_symbol = dim_symbols[index]
        lines.append(
            f"    {{{c_string(str(dim['name']))}, {c_string(str(dim['geometry_node']))}, "
            f"{pos_symbol}, {len(dim['positive'])}, "
            f"{neg_symbol}, {len(dim['negative'])}, {float(dim['weight']):.17g}}},"
        )
    lines.append("};")
    lines.append("")
    lines.append(f"#define {symbol.upper()}_COUNT (sizeof({symbol}) / sizeof({symbol}[0]))")
    lines.append("")
    return "\n".join(lines)


def emit_system(name: str, kind: str, entries: list[tuple[str, list[str]]], geometry_map: list[tuple[str, str]], weights: list[float], scalar_dimensions: list[dict[str, object]]) -> str:
    prefix = c_ident(name)
    lines: list[str] = []
    entry_names: list[str] = []

    for index, (_, features) in enumerate(entries):
        symbol = f"{prefix}_{index}_features"
        entry_names.append(symbol)
        lines.append(f"static const char *const {symbol}[] = {{")
        for feature in features:
            lines.append(f"    {c_string(feature)},")
        lines.append("};")
        lines.append("")

    table_symbol = f"{prefix}_entries"
    lines.append(f"static const mk_builtin_entry {table_symbol}[] = {{")
    for index, (grapheme, features) in enumerate(entries):
        lines.append(
            f"    {{{c_string(grapheme)}, {entry_names[index]}, {len(features)}}},"
        )
    lines.append("};")
    lines.append("")
    lines.append(
        f"#define {prefix.upper()}_ENTRY_COUNT "
        f"(sizeof({table_symbol}) / sizeof({table_symbol}[0]))"
    )
    lines.append("")
    lines.append(emit_feature_node_map(f"{prefix}_geometry_map", geometry_map))
    lines.append(emit_weights(f"{prefix}_dimension_weights", weights))
    lines.append(emit_scalar_dimensions(f"{prefix}_scalar_dimensions", scalar_dimensions))
    return "\n".join(lines)


def emit_geometry(geometry: dict[str, object]) -> str:
    tree = geometry["tree"]
    ftn = sorted(geometry.get("feature_to_node", {}).items())
    leaves = geometry_leaves(tree)
    node_depths = sorted(geometry_node_depths(tree))
    node_parents = sorted(geometry_node_parents(tree))
    feature_paths = geometry_feature_paths(tree)
    presets = geometry.get("weight_presets", {})
    lines: list[str] = []

    lines.append("const mk_geometry_leaf mk_clements_hume_leaves[] = {")
    for name, positive, negative, depth, parent in leaves:
        lines.append(
            f"    {{{c_string(name)}, {c_string(positive)}, {c_string(negative)}, {float(depth):.1f}, {c_string(parent)}}},"
        )
    lines.append("};")
    lines.append("")
    lines.append(
        "const size_t mk_clements_hume_leaf_count =\n"
        "    sizeof(mk_clements_hume_leaves) / sizeof(mk_clements_hume_leaves[0]);"
    )
    lines.append("")

    lines.append("const mk_feature_node_map mk_clements_hume_feature_to_node[] = {")
    for feature, node in ftn:
        lines.append(f"    {{{c_string(feature)}, {c_string(node)}}},")
    lines.append("};")
    lines.append("")
    lines.append(
        "const size_t mk_clements_hume_feature_to_node_count =\n"
        "    sizeof(mk_clements_hume_feature_to_node) / sizeof(mk_clements_hume_feature_to_node[0]);"
    )
    lines.append("")

    lines.append("const mk_node_depth mk_clements_hume_node_depths[] = {")
    for node, depth in node_depths:
        lines.append(f"    {{{c_string(node)}, {float(depth):.1f}}},")
    lines.append("};")
    lines.append("")
    lines.append(
        "const size_t mk_clements_hume_node_depth_count =\n"
        "    sizeof(mk_clements_hume_node_depths) / sizeof(mk_clements_hume_node_depths[0]);"
    )
    lines.append("")

    lines.append("const mk_node_parent mk_clements_hume_node_parents[] = {")
    for node, parent in node_parents:
        lines.append(f"    {{{c_string(node)}, {c_string(parent)}}},")
    lines.append("};")
    lines.append("")
    lines.append(
        "const size_t mk_clements_hume_node_parent_count =\n"
        "    sizeof(mk_clements_hume_node_parents) / sizeof(mk_clements_hume_node_parents[0]);"
    )
    lines.append("")

    preset_entries: list[tuple[str, str | None, int, int]] = []
    for index, (preset_name, value) in enumerate(sorted(presets.items())):
        if value == "__flat__":
            preset_entries.append((preset_name, None, 0, 1))
            continue
        weight_symbol = f"mk_clements_hume_weight_preset_{index}"
        assert isinstance(value, dict)
        weights = sorted(value.items())
        lines.append(f"static const mk_node_weight {weight_symbol}[] = {{")
        for node, weight in weights:
            lines.append(f"    {{{c_string(str(node))}, {float(weight):.17g}}},")
        lines.append("};")
        lines.append("")
        preset_entries.append((preset_name, weight_symbol, len(weights), 0))

    lines.append("const mk_node_weight_preset mk_clements_hume_weight_presets[] = {")
    for preset_name, weight_symbol, weight_count, flat in preset_entries:
        weights_expr = weight_symbol if weight_symbol is not None else "NULL"
        lines.append(
            f"    {{{c_string(preset_name)}, {weights_expr}, {weight_count}, {flat}}},"
        )
    lines.append("};")
    lines.append("")
    lines.append(
        "const size_t mk_clements_hume_weight_preset_count =\n"
        "    sizeof(mk_clements_hume_weight_presets) / sizeof(mk_clements_hume_weight_presets[0]);"
    )
    lines.append("")

    for index, (_, path) in enumerate(feature_paths):
        lines.append(f"static const char *const mk_clements_hume_feature_path_{index}[] = {{")
        for part in path:
            lines.append(f"    {c_string(part)},")
        lines.append("};")
        lines.append("")

    lines.append("const mk_feature_path mk_clements_hume_feature_paths[] = {")
    for index, (feature, path) in enumerate(feature_paths):
        lines.append(
            f"    {{{c_string(feature)}, mk_clements_hume_feature_path_{index}, {len(path)}}},"
        )
    lines.append("};")
    lines.append("")
    lines.append(
        "const size_t mk_clements_hume_feature_path_count =\n"
        "    sizeof(mk_clements_hume_feature_paths) / sizeof(mk_clements_hume_feature_paths[0]);"
    )
    lines.append("")
    return "\n".join(lines)


def mark_from_hex(value: str) -> str:
    return chr(int(value, 16))


def emit_diacritic_map(symbol: str, data: dict[str, object]) -> str:
    lines: list[str] = []

    lines.append(f"const mk_diacritic_map {symbol}[] = {{")
    for cp, feature in sorted(data.items()):
        lines.append(f"    {{{c_string(mark_from_hex(cp))}, {c_string(str(feature))}}},")
    lines.append("};")
    lines.append("")
    lines.append(
        f"const size_t {symbol[:-1]}_count =\n"
        f"    sizeof({symbol}) / sizeof({symbol}[0]);"
    )
    lines.append("")
    return "\n".join(lines)


def emit_diacritics(diacritics: dict[str, object]) -> str:
    lines: list[str] = []
    tone_marks = diacritics.get("tone_marks", {})
    tone_levels = diacritics.get("tone_levels", {})
    valued_effects = diacritics.get("valued_effects", {})

    lines.append(emit_diacritic_map("mk_default_combining_diacritics", dict(diacritics.get("combining", {}))))
    lines.append(emit_diacritic_map("mk_default_suffix_diacritics", dict(diacritics.get("suffix", {}))))
    lines.append(emit_diacritic_map("mk_default_prefix_diacritics", dict(diacritics.get("prefix", {}))))

    tone_entries: list[tuple[str, str | None, int]] = []
    for index, (cp, levels) in enumerate(sorted(dict(tone_marks).items())):
        onset, mid, offset = [str(part) for part in levels]
        features = [
            *tone_levels["onset"][onset],
            *tone_levels["mid"][mid],
            *tone_levels["offset"][offset],
        ]
        if features:
            symbol = f"mk_default_tone_mark_{index}_features"
            lines.append(f"static const char *const {symbol}[] = {{")
            for feature in features:
                lines.append(f"    {c_string(str(feature))},")
            lines.append("};")
            lines.append("")
        else:
            symbol = None
        tone_entries.append((cp, symbol, len(features)))

    lines.append("const mk_tone_mark mk_default_tone_marks[] = {")
    for cp, symbol, count in tone_entries:
        features_expr = symbol if symbol is not None else "NULL"
        lines.append(f"    {{{c_string(mark_from_hex(cp))}, {features_expr}, {count}}},")
    lines.append("};")
    lines.append("")
    lines.append(
        "const size_t mk_default_tone_mark_count =\n"
        "    sizeof(mk_default_tone_marks) / sizeof(mk_default_tone_marks[0]);"
    )
    lines.append("")

    effect_entries: list[tuple[str, str, int, str]] = []
    for index, (modifier, effect) in enumerate(sorted(dict(valued_effects).items())):
        effect_dict = dict(effect)
        alternatives = [str(feature) for feature in effect_dict.get("features", [])]
        symbol = f"mk_default_valued_effect_{index}_alternatives"
        lines.append(f"static const char *const {symbol}[] = {{")
        for feature in alternatives:
            lines.append(f"    {c_string(feature)},")
        lines.append("};")
        lines.append("")
        effect_entries.append((str(modifier), symbol, len(alternatives), str(effect_dict.get("state", "."))))

    lines.append("const mk_valued_diacritic_effect mk_default_valued_diacritic_effects[] = {")
    for modifier, symbol, count, state in effect_entries:
        lines.append(f"    {{{c_string(modifier)}, {symbol}, {count}, '{state[0]}' }},")
    lines.append("};")
    lines.append("")
    lines.append(
        "const size_t mk_default_valued_diacritic_effect_count =\n"
        "    sizeof(mk_default_valued_diacritic_effects) / sizeof(mk_default_valued_diacritic_effects[0]);"
    )
    lines.append("")
    return "\n".join(lines)


def generate(output: Path) -> None:
    geometry = load_geometry()
    diacritics = load_diacritics()
    systems = []
    for name in CATEGORICAL_SYSTEMS:
        systems.append((name, *load_categorical(name, geometry)))
    for name in VALUED_SYSTEMS:
        systems.append((name, *load_valued(name, geometry)))

    chunks = [
        "#include \"builtin_data.h\"",
        "",
        "/* This file is generated by tools/generate_c_data.py. */",
        "",
    ]
    chunks.append(emit_geometry(geometry))
    chunks.append(emit_diacritics(diacritics))
    for name, kind, entries, geometry_map, weights, scalar_dimensions in systems:
        chunks.append(emit_system(name, kind, entries, geometry_map, weights, scalar_dimensions))

    chunks.append("const mk_builtin_system mk_builtin_systems[] = {")
    for name, kind, _, geometry_map, weights, scalar_dimensions in systems:
        prefix = c_ident(name)
        map_expr = f"{prefix}_geometry_map" if geometry_map else "NULL"
        map_count = f"{prefix.upper()}_GEOMETRY_MAP_COUNT" if geometry_map else "0"
        weights_expr = f"{prefix}_dimension_weights" if weights else "NULL"
        scalar_expr = f"{prefix}_scalar_dimensions" if scalar_dimensions else "NULL"
        scalar_count = f"{prefix.upper()}_SCALAR_DIMENSIONS_COUNT" if scalar_dimensions else "0"
        chunks.append(
            f"    {{{c_string(name)}, {kind}, {prefix}_entries, {prefix.upper()}_ENTRY_COUNT, "
            f"{map_expr}, {map_count}, {weights_expr}, {scalar_expr}, {scalar_count}}},"
        )
    chunks.append("};")
    chunks.append("")
    chunks.append(
        "const size_t mk_builtin_system_count =\n"
        "    sizeof(mk_builtin_systems) / sizeof(mk_builtin_systems[0]);"
    )
    chunks.append("")

    output.write_text("\n".join(chunks), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "src" / "generated" / "builtin_data.c",
    )
    args = parser.parse_args()
    generate(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
