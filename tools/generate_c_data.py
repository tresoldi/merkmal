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

# Must match MK_MAX_ENTRY_FEATURES in src/generated/builtin_data.h. The
# resolver reserves this many pointer slots inside every mk_resolution, so
# raising it costs stack on every lookup.
MAX_ENTRY_FEATURES = 64


def c_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


# Bytes per pool chunk. C99 only requires a compiler to support string literals
# of 4095 characters, and adjacent literals concatenate into one, so the pool is
# cut into chunks below that limit rather than emitted as a single array. A
# power of two keeps the offset split to a shift and a mask.
POOL_CHUNK_BITS = 11
POOL_CHUNK = 1 << POOL_CHUNK_BITS


class StringPool:
    """Every distinct grapheme and feature label, stored once.

    The tables used to hold `const char *` for each of roughly 260,000 feature
    slots. That is 2.08 MB of pointers on a 64-bit target -- and one relocation
    each -- to refer to 35 KB of actual text. They now hold offsets into this
    pool, which needs one relocation per chunk and none per string.

    A string never straddles a chunk: when one will not fit in what is left,
    the chunk is padded with NULs and the string starts the next. That keeps
    the offset arithmetic to `chunk[offset >> BITS] + (offset & MASK)`, with no
    search and no per-string bookkeeping.
    """

    def __init__(self) -> None:
        self.offsets: dict[str, int] = {}
        self.chunks: list[bytearray] = [bytearray()]

    def add(self, value: str) -> int:
        known = self.offsets.get(value)
        if known is not None:
            return known
        # Byte offsets, because C indexes the array in bytes and these strings
        # are UTF-8. Character offsets would place every non-ASCII grapheme at
        # the wrong index.
        encoded = value.encode("utf-8") + b"\0"
        if len(encoded) > POOL_CHUNK:
            raise SystemExit(
                f"pool entry {value!r} is {len(encoded)} bytes, over the "
                f"{POOL_CHUNK}-byte chunk size"
            )
        if len(self.chunks[-1]) + len(encoded) > POOL_CHUNK:
            self.chunks[-1].extend(b"\0" * (POOL_CHUNK - len(self.chunks[-1])))
            self.chunks.append(bytearray())
        offset = (len(self.chunks) - 1) * POOL_CHUNK + len(self.chunks[-1])
        self.chunks[-1].extend(encoded)
        self.offsets[value] = offset
        return offset

    def emit(self, symbol: str) -> str:
        by_offset = sorted(self.offsets.items(), key=lambda item: item[1])
        lines: list[str] = []
        for index in range(len(self.chunks)):
            base = index * POOL_CHUNK
            end = base + POOL_CHUNK
            lines.append(f"static const char {symbol}_{index}[] =")
            wrote = False
            for value, offset in by_offset:
                if base <= offset < end:
                    # The terminator is its own literal so that a value ending
                    # in a digit cannot turn "\0" into a longer octal escape.
                    lines.append(f'    {c_string(value)} "\\0"')
                    wrote = True
            if not wrote:
                lines.append('    ""')
            lines.append(";")
            lines.append("")
        lines.append(f"static const char *const {symbol}_chunks[] = {{")
        for index in range(len(self.chunks)):
            lines.append(f"    {symbol}_{index},")
        lines.append("};")
        lines.append("")
        return "\n".join(lines)


def emit_uint_array(symbol: str, ctype: str, values: list[int], per_line: int = 16) -> str:
    lines = [f"static const {ctype} {symbol}[] = {{"]
    for start in range(0, len(values), per_line):
        chunk = ", ".join(str(v) for v in values[start:start + per_line])
        lines.append(f"    {chunk},")
    if not values:
        lines.append("    0,")
    lines.append("};")
    lines.append("")
    return "\n".join(lines)


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
    leaf_weights = {
        name: (1.0 / depth if explicit is None else float(explicit))
        for name, _pos, _neg, depth, _parent, explicit in geometry_leaves(tree)
    }
    for dim in raw.get("scalar_dimensions", []):
        # A scalar dimension hangs *under* its geometry node, so it sits one
        # level deeper than that node -- which is exactly where the geometry's
        # own leaf of the same name sits. Weighting it at the parent's depth
        # made every dimension one level shallower than the leaf it mirrors, so
        # the two scoring paths disagreed on all 35 shared names and
        # docs/geometry.md described neither. An explicit leaf weight wins here
        # for the same reason it wins on the geometry path: depth is a
        # stipulation, and sometimes the wrong one.
        depth = geometry_node_depth(tree, dim["geometry_node"]) or 2
        weight = leaf_weights.get(dim["name"], 1.0 / (depth + 1))
        scalar_dimensions.append(
            {
                "name": dim["name"],
                "geometry_node": dim["geometry_node"],
                "positive": list(dim.get("positive", [])),
                "negative": list(dim.get("negative", [])),
                "weight": weight,
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


def emit_system(
    name: str,
    kind: str,
    entries: list[tuple[str, list[str]]],
    geometry_map: list[tuple[str, str]],
    weights: list[float],
    scalar_dimensions: list[dict[str, object]],
    pool: StringPool,
    feature_ids: dict[str, int],
) -> str:
    prefix = c_ident(name)
    lines: list[str] = []

    grapheme_offsets: list[int] = []
    feature_at: list[int] = []
    feature_n: list[int] = []
    ids: list[int] = []

    # Rows with the same feature set share one run of ids. A quarter of the
    # rows in the bundled inventories are duplicates in this sense -- the same
    # segment described identically under different graphemes.
    runs: dict[tuple[int, ...], int] = {}

    # Sorted so that mki_inventory_find can binary-search instead of walking
    # every row. The key is the UTF-8 bytes, because that is what strcmp
    # compares; sorting by Python str would order by code point and put a
    # two-byte grapheme in a place the C search would not look.
    ordered = sorted(entries, key=lambda entry: entry[0].encode("utf-8"))
    seen: set[str] = set()
    for grapheme, _ in ordered:
        if grapheme in seen:
            raise SystemExit(
                f"{name}: grapheme {grapheme!r} appears twice. A binary search "
                f"would return either row, where the old scan always returned "
                f"the first; resolve the duplicate in the source data."
            )
        seen.add(grapheme)

    for grapheme, features in ordered:
        if len(features) > MAX_ENTRY_FEATURES:
            raise SystemExit(
                f"{name}: grapheme {grapheme!r} carries {len(features)} features, "
                f"over the MK_MAX_ENTRY_FEATURES limit of {MAX_ENTRY_FEATURES}. "
                f"Raise it in both this generator and src/generated/builtin_data.h."
            )
        grapheme_offsets.append(pool.add(grapheme))
        run = tuple(feature_ids[feature] for feature in features)
        at = runs.get(run)
        if at is None:
            at = len(ids)
            runs[run] = at
            ids.extend(run)
        feature_at.append(at)
        feature_n.append(len(features))

    lines.append(emit_uint_array(f"{prefix}_entry_graphemes", "unsigned int", grapheme_offsets))
    lines.append(emit_uint_array(f"{prefix}_entry_feature_at", "unsigned int", feature_at))
    lines.append(emit_uint_array(f"{prefix}_entry_feature_n", "unsigned char", feature_n, 32))
    lines.append(emit_uint_array(f"{prefix}_feature_ids", "unsigned short", ids, 24))
    lines.append(
        f"#define {prefix.upper()}_ENTRY_COUNT "
        f"(sizeof({prefix}_entry_graphemes) / sizeof({prefix}_entry_graphemes[0]))"
    )
    lines.append("")
    lines.append(emit_feature_node_map(f"{prefix}_geometry_map", geometry_map))
    lines.append(emit_weights(f"{prefix}_dimension_weights", weights))
    lines.append(emit_scalar_dimensions(f"{prefix}_scalar_dimensions", scalar_dimensions))
    return "\n".join(lines)


def emit_tier_policy(geometry: dict[str, object]) -> str:
    """What a tone costs against a segment, as a compiled-in constant.

    Emitted from the geometry file rather than written in C so that changing it
    is a data change with a version and a diff, not a code change -- which is
    what lets a later fitted scorer carry its own without disturbing this one.
    """
    policy = geometry.get("tier_policy", {})
    cost = float(policy.get("cross_tier_cost", 1.0))
    return (
        "const double mki_clements_hume_cross_tier_cost = "
        f"{cost:.17g};"
    )


def emit_geometry(geometry: dict[str, object]) -> str:
    tree = geometry["tree"]
    ftn = sorted(geometry.get("feature_to_node", {}).items())
    leaves = geometry_leaves(tree)
    node_depths = sorted(geometry_node_depths(tree))
    node_parents = sorted(geometry_node_parents(tree))
    feature_paths = geometry_feature_paths(tree)
    presets = geometry.get("weight_presets", {})
    lines: list[str] = []

    lines.append("const mk_geometry_leaf mki_clements_hume_leaves[] = {")
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
        "const size_t mki_clements_hume_leaf_count =\n"
        "    sizeof(mki_clements_hume_leaves) / sizeof(mki_clements_hume_leaves[0]);"
    )
    lines.append("")

    lines.append("const mk_feature_node_map mki_clements_hume_feature_to_node[] = {")
    for feature, node in ftn:
        lines.append(f"    {{{c_string(feature)}, {c_string(node)}}},")
    lines.append("};")
    lines.append("")
    lines.append(
        "const size_t mki_clements_hume_feature_to_node_count =\n"
        "    sizeof(mki_clements_hume_feature_to_node) / sizeof(mki_clements_hume_feature_to_node[0]);"
    )
    lines.append("")

    lines.append("const mk_node_depth mki_clements_hume_node_depths[] = {")
    for node, depth in node_depths:
        lines.append(f"    {{{c_string(node)}, {float(depth):.1f}}},")
    lines.append("};")
    lines.append("")
    lines.append(
        "const size_t mki_clements_hume_node_depth_count =\n"
        "    sizeof(mki_clements_hume_node_depths) / sizeof(mki_clements_hume_node_depths[0]);"
    )
    lines.append("")

    lines.append("const mk_node_parent mki_clements_hume_node_parents[] = {")
    for node, parent in node_parents:
        lines.append(f"    {{{c_string(node)}, {c_string(parent)}}},")
    lines.append("};")
    lines.append("")
    lines.append(
        "const size_t mki_clements_hume_node_parent_count =\n"
        "    sizeof(mki_clements_hume_node_parents) / sizeof(mki_clements_hume_node_parents[0]);"
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

    lines.append("const mk_node_weight_preset mki_clements_hume_weight_presets[] = {")
    for preset_name, weight_symbol, weight_count, flat in preset_entries:
        weights_expr = weight_symbol if weight_symbol is not None else "NULL"
        lines.append(
            f"    {{{c_string(preset_name)}, {weights_expr}, {weight_count}, {flat}}},"
        )
    lines.append("};")
    lines.append("")
    lines.append(
        "const size_t mki_clements_hume_weight_preset_count =\n"
        "    sizeof(mki_clements_hume_weight_presets) / sizeof(mki_clements_hume_weight_presets[0]);"
    )
    lines.append("")

    for index, (_, path) in enumerate(feature_paths):
        lines.append(f"static const char *const mk_clements_hume_feature_path_{index}[] = {{")
        for part in path:
            lines.append(f"    {c_string(part)},")
        lines.append("};")
        lines.append("")

    lines.append("const mk_feature_path mki_clements_hume_feature_paths[] = {")
    for index, (feature, path) in enumerate(feature_paths):
        lines.append(
            f"    {{{c_string(feature)}, mk_clements_hume_feature_path_{index}, {len(path)}}},"
        )
    lines.append("};")
    lines.append("")
    lines.append(
        "const size_t mki_clements_hume_feature_path_count =\n"
        "    sizeof(mki_clements_hume_feature_paths) / sizeof(mki_clements_hume_feature_paths[0]);"
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

    lines = ["const mk_decomposition mki_default_decompositions[] = {"]
    for composed, decomposed in pairs:
        lines.append(f"    {{{c_string(composed)}, {c_string(decomposed)}}},")
    lines.append("};")
    lines.append("")
    lines.append(
        "const size_t mki_default_decomposition_count =\n"
        "    sizeof(mki_default_decompositions) / sizeof(mki_default_decompositions[0]);"
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
    lines = ["const char *const mki_default_metadata_features[] = {"]
    for feature in features:
        lines.append(f"    {c_string(feature)},")
    lines.append("};")
    lines.append("")
    lines.append(
        "const size_t mki_default_metadata_feature_count =\n"
        "    sizeof(mki_default_metadata_features) / sizeof(mki_default_metadata_features[0]);"
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

    lines.append("const mk_ordinal_scale mki_clements_hume_ordinal_scales[] = {")
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
        "const size_t mki_clements_hume_ordinal_scale_count =\n"
        "    sizeof(mki_clements_hume_ordinal_scales) / sizeof(mki_clements_hume_ordinal_scales[0]);"
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

    lines.append(emit_diacritic_map("mki_default_combining_diacritics", dict(diacritics.get("combining", {}))))
    lines.append(emit_diacritic_map("mki_default_suffix_diacritics", dict(diacritics.get("suffix", {}))))
    lines.append(emit_diacritic_map("mki_default_prefix_diacritics", dict(diacritics.get("prefix", {}))))

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

    lines.append("const mk_tone_mark mki_default_tone_marks[] = {")
    for cp, symbol, count in tone_entries:
        features_expr = symbol if symbol is not None else "NULL"
        lines.append(f"    {{{c_string(mark_from_hex(cp))}, {features_expr}, {count}}},")
    lines.append("};")
    lines.append("")
    lines.append(
        "const size_t mki_default_tone_mark_count =\n"
        "    sizeof(mki_default_tone_marks) / sizeof(mki_default_tone_marks[0]);"
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

    lines.append("const mk_valued_diacritic_effect mki_default_valued_diacritic_effects[] = {")
    for modifier, symbol, count, state in effect_entries:
        lines.append(f"    {{{c_string(modifier)}, {symbol}, {count}, '{state[0]}' }},")
    lines.append("};")
    lines.append("")
    lines.append(
        "const size_t mki_default_valued_diacritic_effect_count =\n"
        "    sizeof(mki_default_valued_diacritic_effects) / sizeof(mki_default_valued_diacritic_effects[0]);"
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

    # One id space for feature labels across every system. Sorted so that the
    # emitted file is a function of the input data and nothing else.
    labels = sorted({
        feature
        for _, _, entries, _, _, _ in systems
        for _, features in entries
        for feature in features
    })
    feature_ids = {label: index for index, label in enumerate(labels)}
    if len(labels) > 0xFFFF:
        raise SystemExit(
            f"{len(labels)} distinct feature labels exceeds the 16-bit id space; "
            f"widen mk_feature_ids and the generated arrays to unsigned int."
        )

    pool = StringPool()
    label_offsets = [pool.add(label) for label in labels]

    system_chunks = [
        emit_system(name, kind, entries, geometry_map, weights, scalar_dimensions, pool, feature_ids)
        for name, kind, entries, geometry_map, weights, scalar_dimensions in systems
    ]

    chunks = [
        "#include \"builtin_data.h\"",
        "",
        "/* This file is generated by tools/generate_c_data.py. */",
        "",
    ]
    # The pool is emitted before its users but filled while emitting them, so
    # the system chunks are built first and appended below.
    chunks.append(pool.emit("mk_pool"))
    chunks.append(emit_uint_array("mk_feature_offsets", "unsigned int", label_offsets))
    chunks.append("const char *mki_pool_string(unsigned int offset)")
    chunks.append("{")
    chunks.append(f"    return mk_pool_chunks[offset >> {POOL_CHUNK_BITS}] + "
                  f"(offset & {POOL_CHUNK - 1}u);")
    chunks.append("}")
    chunks.append("")
    chunks.append("const char *mki_feature_name(unsigned short id)")
    chunks.append("{")
    chunks.append("    return mki_pool_string(mk_feature_offsets[id]);")
    chunks.append("}")
    chunks.append("")
    chunks.append(
        "const size_t mki_feature_name_count =\n"
        "    sizeof(mk_feature_offsets) / sizeof(mk_feature_offsets[0]);"
    )
    chunks.append("")
    chunks.append(emit_geometry(geometry))
    chunks.append(emit_ordinal_scales(geometry))
    chunks.append(emit_metadata_features(geometry))
    chunks.append(emit_tier_policy(geometry))
    chunks.append(emit_diacritics(diacritics))
    chunks.append(emit_decompositions(diacritics))
    chunks.extend(system_chunks)

    chunks.append("const mk_builtin_system mki_builtin_systems[] = {")
    for name, kind, _, geometry_map, weights, scalar_dimensions in systems:
        prefix = c_ident(name)
        map_expr = f"{prefix}_geometry_map" if geometry_map else "NULL"
        map_count = f"{prefix.upper()}_GEOMETRY_MAP_COUNT" if geometry_map else "0"
        weights_expr = f"{prefix}_dimension_weights" if weights else "NULL"
        scalar_expr = f"{prefix}_scalar_dimensions" if scalar_dimensions else "NULL"
        scalar_count = f"{prefix.upper()}_SCALAR_DIMENSIONS_COUNT" if scalar_dimensions else "0"
        chunks.append(
            f"    {{{c_string(name)}, {kind}, NULL, {prefix.upper()}_ENTRY_COUNT, "
            f"{prefix}_entry_graphemes, {prefix}_entry_feature_at, "
            f"{prefix}_entry_feature_n, {prefix}_feature_ids, "
            f"{map_expr}, {map_count}, {weights_expr}, {scalar_expr}, {scalar_count}}},"
        )
    chunks.append("};")
    chunks.append("")
    chunks.append(
        "const size_t mki_builtin_system_count =\n"
        "    sizeof(mki_builtin_systems) / sizeof(mki_builtin_systems[0]);"
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
