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


# The inventory NAME strings say "voiceless velar stop consonant". They never
# say "obstruent", "continuant", "anterior" or "consonantal", so the geometry
# leaves for those never fired and every manner distinction collapsed into a
# single Manner group boolean: /p/~/f/, /p/~/r/ and /k/~/ʔ/ all cost the same.
# These derivations are the same ones models/distinctive/model.json already
# spells out in its scalar_dimensions; applying them here makes the leaves real
# for the categorical path too.
SONORANT_MANNERS = frozenset({"nasal", "lateral", "approximant", "trill", "tap", "vowel"})
OBSTRUENT_MANNERS = frozenset({"stop", "fricative", "affricate", "click", "implosive"})
CONTINUANT_MANNERS = frozenset({"fricative", "approximant", "trill", "vowel"})
NON_CONTINUANT_MANNERS = frozenset({"stop", "affricate", "nasal", "implosive", "click"})

ANTERIOR_PLACES = frozenset({"linguolabial", "dental", "alveolar"})
NON_ANTERIOR_PLACES = frozenset({"post-alveolar", "retroflex", "alveolo-palatal"})
DISTRIBUTED_PLACES = frozenset({"dental", "post-alveolar", "alveolo-palatal", "linguolabial"})
NON_DISTRIBUTED_PLACES = frozenset({"alveolar", "retroflex"})

# Articulator features. Each place scale is defined only for its own
# articulator, so with nothing else a labial and a dorsal have no place
# dimension in common and their difference disappears: /b/ and /g/ scored
# exactly zero. These are the privative articulator nodes of standard feature
# geometry, and they carry the cross-articulator difference that the ordered
# scales, which measure gradience *within* an articulator, cannot.
ARTICULATORS = {
    "labial": frozenset(
        {"bilabial", "labio-dental", "labial", "labio-palatal", "labio-velar"}
    ),
    "coronal": frozenset(
        {"linguolabial", "dental", "alveolar", "post-alveolar", "retroflex",
         "alveolo-palatal"}
    ),
    "dorsal": frozenset(
        {"palatal", "palatal-velar", "velar", "uvular", "labio-palatal", "labio-velar"}
    ),
    "guttural": frozenset({"pharyngeal", "epiglottal", "glottal"}),
}

# [-consonantal]: vowels and the four cardinal glides. Without this, /w/ scored
# as far from /u/ as a glottal stop does from /a/, though w~u and j~i
# alternations are among the most common things in historical phonology.
GLIDE_PLACES = frozenset({"palatal", "labio-palatal", "labio-velar", "velar"})


def derive_class_features(features: frozenset[str]) -> frozenset[str]:
    added: set[str] = set()

    if "vowel" in features or ("approximant" in features and features & GLIDE_PLACES):
        added.add("vocoid")
    else:
        added.add("consonantal")

    if features & SONORANT_MANNERS:
        added.add("sonorant")
    elif features & OBSTRUENT_MANNERS:
        added.add("obstruent")

    if features & CONTINUANT_MANNERS:
        added.add("continuant")
    elif features & NON_CONTINUANT_MANNERS:
        added.add("non-continuant")

    if features & ANTERIOR_PLACES:
        added.add("anterior")
    elif features & NON_ANTERIOR_PLACES:
        added.add("non-anterior")

    if features & DISTRIBUTED_PLACES:
        added.add("distributed")
    elif features & NON_DISTRIBUTED_PLACES:
        added.add("non-distributed")

    for articulator, places in ARTICULATORS.items():
        if features & places:
            added.add(articulator)

    return features | added


def check_ordinal_consistency(
    grapheme: str, features: frozenset[str], geometry: dict[str, object]
) -> None:
    """A segment may not sit at two points on one ordered scale.

    The diacritic composer could produce a vowel carrying both `ultra-short` and
    `long` (breve plus length mark), a contradiction nothing rejected.
    """
    for scale in geometry.get("ordinal_scales", []):
        present = sorted(features & frozenset(str(x) for x in scale["levels"]))
        if len(present) > 1:
            raise SystemExit(
                f"{grapheme!r} carries {present} on the ordered scale "
                f"{scale['name']!r}; a segment has one value on a scale"
            )


def enrich_click_features(features: frozenset[str]) -> frozenset[str]:
    if not (features & NON_PULMONIC_FEATURES):
        return features
    added = {"non-pulmonic"}
    if "click" in features or "nasal-click" in features:
        # A click has two closures. The name gives the anterior one, which is
        # its place; the rear closure is definitional of the airstream and gets
        # its own feature. Adding plain "velar" instead made the rear closure
        # compete as a place, so /ǃ/ counted as both alveolar and velar and came
        # out exactly equidistant from /k/ and /t/.
        added.add("dorsal-closure")
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


def geometry_leaves(
    tree: dict[str, object], depth: int = 1
) -> list[tuple[str, str, str, int, str, float | None]]:
    result: list[tuple[str, str, str, int, str, float | None]] = []
    parent = str(tree["name"])
    for child in tree.get("children", []):
        if "children" in child:
            result.extend(geometry_leaves(child, depth + 1))
        else:
            # A leaf may override the mechanical 1/depth base weight. Depth is a
            # stipulation about how much a difference should cost, and it is
            # sometimes the wrong one: major class sits at the root but should
            # not outweigh every segmental property combined.
            weight = child.get("weight")
            result.append(
                (
                    str(child["name"]),
                    str(child.get("positive", "")),
                    str(child.get("negative", "")),
                    depth,
                    parent,
                    None if weight is None else float(weight),
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
            enriched = derive_class_features(enrich_click_features(features))
            check_ordinal_consistency(grapheme, enriched, geometry)
            entries[normalize_input_grapheme(grapheme)] = sorted(enriched)
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
    for name, positive, negative, depth, parent, weight in leaves:
        # The runtime reads `depth` only as 1/depth, so an explicit weight is
        # expressed as the depth that produces it.
        effective = float(depth) if weight is None else 1.0 / float(weight)
        lines.append(
            f"    {{{c_string(name)}, {c_string(positive)}, {c_string(negative)}, {effective:.17g}, {c_string(parent)}}},"
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


def emit_decompositions(diacritics: dict[str, object]) -> str:
    """Precomposed letters whose decomposition merkmal can interpret.

    Lookup used a hand-written else-if chain covering acute/grave/macron/
    circumflex on a few vowels. Everything else it left composed, so `ǎ` was
    rejected while its canonically equivalent NFD form was accepted -- and
    `mk_normalize_grapheme` returns NFC, so the documented preprocessing step
    turned working input into failing input.

    Deriving the table here rather than calling utf8proc_NFD at lookup time
    keeps the two build configurations in step: the fallback build and the
    utf8proc build accept exactly the same graphemes.
    """
    known_marks = {mark_from_hex(cp) for cp in diacritics.get("combining", {})}
    known_marks |= {mark_from_hex(cp) for cp in diacritics.get("tone_marks", {})}

    pairs: list[tuple[str, str]] = []
    for codepoint in range(0x00C0, 0x2100):
        char = chr(codepoint)
        if unicodedata.category(char) not in {"Ll", "Lu"}:
            continue
        decomposed = unicodedata.normalize("NFD", char)
        if decomposed == char or len(decomposed) < 2:
            continue
        base, marks = decomposed[0], decomposed[1:]
        if unicodedata.category(base) not in {"Ll", "Lu"}:
            continue
        # Only letters whose marks mean something here. Decomposing anything
        # else would turn an unsupported letter into a base plus a mark the
        # feature system would then misread.
        if not all(mark in known_marks for mark in marks):
            continue
        pairs.append((char, decomposed))

    lines = ["const mk_decomposition mk_default_decompositions[] = {"]
    for composed, decomposed in pairs:
        lines.append(f"    {{{c_string(composed)}, {c_string(decomposed)}}},")
    lines.append("};")
    lines.append("")
    lines.append(
        "const size_t mk_default_decomposition_count =\n"
        "    sizeof(mk_default_decompositions) / sizeof(mk_default_decompositions[0]);"
    )
    lines.append("")
    return "\n".join(lines)


def emit_metadata_features(geometry: dict[str, object]) -> str:
    """Labels a model may carry that deliberately do not score.

    They are known to the geometry, so strict validation accepts them, but they
    cannot be all a grapheme has: a model built only from metadata would answer
    zero for every comparison, which is what strict validation exists to catch.
    """
    features = sorted(geometry.get("metadata_features", {}))
    lines = ["const char *const mk_default_metadata_features[] = {"]
    for feature in features:
        lines.append(f"    {c_string(feature)},")
    lines.append("};")
    lines.append("")
    lines.append(
        "const size_t mk_default_metadata_feature_count =\n"
        "    sizeof(mk_default_metadata_features) / sizeof(mk_default_metadata_features[0]);"
    )
    lines.append("")
    return "\n".join(lines)


def emit_ordinal_scales(geometry: dict[str, object]) -> str:
    scales = list(geometry.get("ordinal_scales", []))
    lines: list[str] = []

    for index, scale in enumerate(scales):
        symbol = f"mk_clements_hume_ordinal_levels_{index}"
        lines.append(f"static const char *const {symbol}[] = {{")
        for level in scale["levels"]:
            lines.append(f"    {c_string(str(level))},")
        lines.append("};")
        lines.append("")

    lines.append("const mk_ordinal_scale mk_clements_hume_ordinal_scales[] = {")
    for index, scale in enumerate(scales):
        default = scale.get("default_level")
        default_expr = "MK_ORDINAL_UNDEFINED" if default is None else str(int(default))
        lines.append(
            f"    {{{c_string(str(scale['name']))}, {c_string(str(scale['node']))}, "
            f"mk_clements_hume_ordinal_levels_{index}, {len(scale['levels'])}, "
            f"{default_expr}, {float(scale['weight']):.17g}}},"
        )
    lines.append("};")
    lines.append("")
    lines.append(
        "const size_t mk_clements_hume_ordinal_scale_count =\n"
        "    sizeof(mk_clements_hume_ordinal_scales) / sizeof(mk_clements_hume_ordinal_scales[0]);"
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
        # "tone-present" is what separates a mid-level tone from tonelessness;
        # every tone mark asserts it, including the all-mid macron.
        features = [
            "tone-present",
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
    chunks.append(emit_ordinal_scales(geometry))
    chunks.append(emit_metadata_features(geometry))
    chunks.append(emit_diacritics(diacritics))
    chunks.append(emit_decompositions(diacritics))
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
