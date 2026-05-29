# Bringing your own model and configuration

merkmal ships nine feature systems, a feature geometry, three
typologies, and a diacritic set. Most users will use those. But every
piece of data is *pluggable*: you can add or override any of it by
editing JSON/TSV files and pointing merkmal at them — no code changes,
in either the Python package or the Go module.

This guide covers the full, start-to-end path:

1. [How merkmal finds data](#how-merkmal-finds-data) (the search path)
2. [Bring your own model](#bring-your-own-model) (all three engine types)
3. [Custom geometry](#custom-geometry)
4. [Custom typology](#custom-typology)
5. [Custom diacritics, tone, and modifiers](#custom-diacritics-tone-and-modifiers)
6. [Validating your files](#validating-your-files)
7. [Using it from Go](#using-it-from-go)

JSON Schemas for every file type live in [`schemas/`](../schemas) — point
your editor at them for completion and validation.

---

## How merkmal finds data

merkmal resolves four kinds of data, each from its own **search path**:

| Data        | Env var (path list)   | Bundled location          |
|-------------|-----------------------|---------------------------|
| models      | `MERKMAL_MODELS`      | `models/<name>/`          |
| geometries  | `MERKMAL_GEOMETRIES`  | `geometries/<name>.json`  |
| typologies  | `MERKMAL_TYPOLOGIES`  | `typologies/<name>.json`  |
| diacritics  | `MERKMAL_DIACRITICS`  | `diacritics/<name>.json`  |

Each env var is an `os.pathsep`-separated list of directories
(`:` on Linux/macOS, `;` on Windows). The directories you list are
**layered on top of** the bundled data: a name found in one of your
directories wins, but everything you don't provide still falls back to
the built-ins. So you can drop in a single custom model and keep all
nine built-ins.

```bash
export MERKMAL_MODELS=/home/me/merkmal-data/models
python -c "import merkmal; print(merkmal.list_systems())"
# ['broad', 'classfeat', 'descriptive', 'distinctive', 'mymodel', ...]
```

To use **only** your data and exclude the built-ins, set:

```bash
export MERKMAL_DATA_ISOLATED=1
```

> **Note on installed packages.** When merkmal is installed with `pip`,
> it carries its own bundled copy of this data inside the package. The
> supported way to customize is an *external* directory via the env
> vars or the API below — not editing files inside the installed
> package (which a reinstall would overwrite) or the repository's
> top-level `models/` (which an installed package ignores).

### From Python (no env vars)

```python
import merkmal

# Load a single model directory directly:
system = merkmal.load_model_from_dir("/path/to/mymodel")
print(system.grapheme_to_features("tʰ"))

# Build a registry that layers your dirs over the built-ins:
reg = merkmal.create_registry(extra_model_dirs=["/path/to/models"])

# ...or only your models, no built-ins:
reg = merkmal.create_registry(
    register_builtin=False,
    extra_model_dirs=["/path/to/models"],
    default_system="mymodel",
)

# Register one model into an existing registry:
reg.register_dir("/path/to/mymodel")
```

---

## Bring your own model

A model is a directory containing a `model.json` plus the data files its
declared `type` needs. The `name` in `model.json` is how the system is
addressed; for bundled models it matches the directory name.

Common `model.json` fields (all types):

```json
{
  "schema_version": 1,
  "name": "mymodel",
  "version": "0.1.0",
  "type": "categorical",
  "description": "My feature system",
  "default_geometry": "clements-hume",
  "diacritics": "ipa-clts"
}
```

`diacritics` is optional; omit it to use the built-in IPA/CLTS set.
`default_geometry` names a geometry on the geometry search path.

### Type 1 — `categorical`

Features are parsed from each grapheme's descriptive name. Files:

- `inventory.tsv` — `GRAPHEME<TAB>NAME`
- `features.tsv` *(optional)* — `VALUE<TAB>FEATURE` (the feature
  vocabulary; with `"feature_extraction": "filtered"`, only words listed
  here are kept)
- `classes.tsv` *(optional)* — sound classes

```
# model.json
{ "schema_version": 1, "name": "mymodel", "version": "0.1.0",
  "type": "categorical", "description": "...",
  "default_geometry": "clements-hume", "feature_extraction": "filtered" }
```
```
# inventory.tsv
GRAPHEME	NAME
p	voiceless bilabial stop consonant
b	voiced bilabial stop consonant
```
```
# features.tsv
VALUE	FEATURE
bilabial	place
stop	manner
voiceless	phonation
voiced	phonation
consonant	type
```

### Type 2 — `valued`

Features are an explicit matrix. `inventory.tsv` has one column per
feature; `model.json` maps each feature to a geometry node and (optionally)
declares the cell symbols.

```
# model.json
{ "schema_version": 1, "name": "myvalued", "version": "0.1.0",
  "type": "valued", "description": "...", "default_geometry": "clements-hume",
  "state_symbols": { "+": 1.0, "-": -1.0, "0": null },
  "geometry_map": { "syllabic": "Manner", "voice": "Laryngeal" } }
```
```
# inventory.tsv
GRAPHEME	syllabic	voice
p	-	-
b	-	+
```

### Type 3 — `trained`

Sound classes with continuous prototype vectors and learned weights.

- `inventory.tsv` — `GRAPHEME` + columns
- `weights.json` *(optional)* — trained weights
- `model.json` declares `feature_names`, `geometry_map`,
  `sound_classes`, `class_prototypes`, and optionally `alpha`.

See [`models/classfeat/model.json`](../models/classfeat/model.json) for a
complete worked example.

---

## Custom geometry

A geometry is a tree of nodes; leaves are features. `feature_to_node`
maps non-leaf feature values to the node governing their weight, and
`weight_presets` defines named weightings (e.g. `tone-heavy`).

```json
{
  "schema_version": 1,
  "name": "mygeometry",
  "tree": {
    "name": "Root",
    "children": [
      { "name": "Laryngeal", "children": [
        { "name": "voice", "positive": "voiced", "negative": "voiceless" }
      ] }
    ]
  },
  "feature_to_node": { "aspirated": "Laryngeal" },
  "weight_presets": { "flat": "__flat__" }
}
```

Reference it from a model via `"default_geometry": "mygeometry"` and put
it on the geometry search path. (In Go, each model is loaded with the
geometry it declares.)

---

## Custom typology

Typologies encode asymmetric, diachronic direction costs:

```json
{
  "schema_version": 1,
  "name": "my-bias",
  "description": "Lenition cheaper than fortition",
  "direction_costs": {
    "continuant": { "pos_to_neg": 1.5, "neg_to_pos": 0.5 }
  }
}
```

```python
typ = merkmal.load_typology("my-bias")   # found on MERKMAL_TYPOLOGIES
```

---

## Custom diacritics, tone, and modifiers

This is what lets a fully custom feature **vocabulary** work end to end.
Diacritic composition turns `tʰ` into base `t` plus a modifier feature.
*Which feature name* a modifier produces is part of your vocabulary, so
it is configurable.

Copy the bundled [`diacritics/ipa-clts.json`](../diacritics/ipa-clts.json)
as a starting point, change the feature names, and reference it from your
model:

```json
{
  "name": "myipa",
  "suffix": { "02B0": "ASP" },
  "tone_levels": { "onset": {}, "mid": {}, "offset": {} }
}
```
```json
// in model.json
{ "...": "...", "diacritics": "myipa" }
```

Now `tʰ` decomposes to `t` + `ASP` instead of `t` + `aspirated`. Fields:

- `combining` / `suffix` / `prefix` — Unicode codepoint (uppercase hex
  string) → feature name, for combining marks, trailing modifier letters,
  and leading modifier letters respectively.
- `tone_marks` — combining tone-diacritic codepoint → `[onset, mid, offset]`
  Chao levels.
- `tone_levels` — Chao level (1–5) → feature names, per onset/mid/offset.
- `valued_effects` — for valued systems, the feature change a modifier
  applies (`{"features": [...], "state": "+"}`; the first listed feature
  present in the model is set).

IPA *recognition* and normalization (which codepoints are tie bars,
ASCII `g` → `ɡ`, ligature expansion, CLTS slash handling) are universal
and not part of this file.

---

## Validating your files

```bash
python scripts/validate_models.py /path/to/mymodel
```

Or validate against the JSON Schemas in [`schemas/`](../schemas) with any
JSON Schema tool, e.g.:

```python
import json, jsonschema
schema = json.load(open("schemas/model.schema.json"))
jsonschema.validate(json.load(open("/path/to/mymodel/model.json")), schema)
```

---

## Using it from Go

The Go module is `fs.FS`-based. Layer your own directories over the
bundled data, or load a single directory:

```go
import (
    "os"
    merkmal "github.com/tresoldi/merkmal/go"
)

// Layer custom dirs over the bundled (embedded) data:
reg, _ := merkmal.NewLayeredRegistry(
    []fs.FS{os.DirFS("/my/models"), bundledModelsFS},
    []fs.FS{os.DirFS("/my/geometries"), bundledGeometriesFS},
    []fs.FS{os.DirFS("/my/diacritics"), bundledDiacriticsFS},
)

// ...or a single model directory:
sys, _ := merkmal.LoadModelDir("/my/models/mymodel", "/my/geometries", "/my/diacritics")
```

Each model is loaded with the geometry **and** diacritic set it declares,
so a custom-vocabulary model behaves identically in Python and Go — the
cross-language golden tests enforce this.
