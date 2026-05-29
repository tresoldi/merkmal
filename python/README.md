# merkmal

`merkmal` is a phonological feature library for computational
historical linguistics. It maps IPA graphemes to feature
representations and computes geometry-weighted distances between
them, supporting nine feature systems across approximately 780
graphemes.

The library has dual implementations — a Python package (zero
runtime dependencies, Python 3.12+) and a Go module
(`golang.org/x/text` only) — that load the same pluggable model
directories and geometry files. Cross-language golden tests ensure
both implementations produce identical results.

Version 0.6.0 is the first colleague-facing release. The exported
Python API and Go `System` interface are intended to be stable
within the 0.6 series; later 0.x releases may add capabilities but
should not remove documented functions without a changelog note.

## Installation

**Python** (from PyPI):

```bash
pip install merkmal
```

Or from source (from the `python/` directory):

```bash
pip install -e ".[dev]"
```

**Go**:

```go
import merkmal "github.com/tresoldi/merkmal/go"
```

## Quick start (Python)

```python
import merkmal

# Nine built-in systems
print(merkmal.list_systems())
# ['descriptive', 'broad', 'distinctive', 'pbase-hc', 'pbase-jfh',
#  'pbase-spe', 'pbase-uftc', 'phoible', 'classfeat']

# Feature lookup
print(merkmal.get_features("p"))
# frozenset({'consonant', 'voiceless', 'bilabial', 'stop'})

# Diacritics compose automatically
print(merkmal.get_features("tʰ"))
# frozenset({'consonant', 'voiceless', 'alveolar', 'stop', 'aspirated'})

# First-class segment validity
print(merkmal.is_segment("tʰ"))             # True
print(merkmal.is_segment("not-ipa"))        # False

# Distance (normalised to [0, 1], geometry-weighted)
print(merkmal.distance("p", "b"))           # voicing: small
print(merkmal.distance("p", "f"))           # manner: larger
print(merkmal.distance("t", "d", system="classfeat"))

# IPA segmentation
phones = merkmal.segment_ipa("tʰoŋ⁵⁵")     # → ['tʰ', 'o', 'ŋ', '⁵⁵']
merged = merkmal.merge_tone_digits(phones)  # → ['tʰ', 'o⁵⁵', 'ŋ']
```

## Quick start (Go)

```go
reg, _ := merkmal.NewDefaultRegistry()
sys, _ := reg.Get("descriptive")
dist := sys.SegmentDistance("p", "b")
ok := sys.IsSegment("tʰ")

phones := merkmal.SegmentIPA("tʰoŋ⁵⁵")
merged := merkmal.MergeToneDigits(phones)
```

`NewDefaultRegistry` uses the models and geometries bundled in the
Go module. Lower-level loading is still `fs.FS`-based: use
`NewRegistry` with `os.DirFS` for disk-based models, `embed.FS` for
caller-provided compiled data, or `fstest.MapFS` for tests.

## Systems

| System | Type | Features | Distance |
|--------|------|----------|----------|
| `descriptive` | categorical | articulatory | geometry-weighted |
| `broad` | categorical | simplified | geometry-weighted |
| `distinctive` | categorical + scalar | Clements & Hume | geometry-weighted |
| `pbase-hc`, `-jfh`, `-spe`, `-uftc` | multi-state | 4 theoretical families | geometry-weighted |
| `phoible` | binary | 37 features | geometry-weighted |
| `classfeat` | hybrid | sound classes + continuous | trained weights |

All systems implement the same interface (`FeatureSystem` protocol
in Python, `System` interface in Go). Distances, queries, and
partition derivation work uniformly across all of them.

The default system is `descriptive`. It is the recommended first
choice for examples and exploratory use because its feature names
are articulatory and readable. `phoible` and the P-base systems are
available when a valued feature matrix is needed.

## Feature queries

```python
import merkmal

# Shared features of a segment set
print(merkmal.derive_class_features(["p", "t", "k"]))
# frozenset({'consonant', 'voiceless', 'stop'})

# Find all graphemes matching a feature set
vowels = merkmal.features_to_graphemes(frozenset({"vowel"}))
print(vowels[:10])

# Reverse lookup: features → grapheme
descriptive = merkmal.get_system("descriptive")
print(descriptive.features_to_grapheme(
    frozenset({"consonant", "voiced", "bilabial", "stop"})
))
# 'b'

# Minimal distinguishing matrix
matrix = merkmal.minimal_matrix(["t", "d", "s"])
print(merkmal.tabulate_matrix(matrix))
```

```text
grapheme | continuant | voiced
---------+------------+-------
t        | False      | False
d        | False      | True
s        | True       | False
```

## IPA segmentation

`segment_ipa` tokenizes raw IPA strings into individual phones,
handling tie bars, prefix/suffix modifiers, combining marks, and
Chao tone digits. `merge_tone_digits` attaches tone digit tokens
to their syllabic nucleus.

Input normalization is intentionally opinionated and stable in the
0.6 series: CLTS `source/bipa` slash notation keeps the post-slash
value, leading stress marks are stripped, ASCII `g` is accepted and
output as IPA `ɡ`, deprecated affricate ligatures are expanded, and
ASCII `:` is treated as IPA length `ː`.

```python
import merkmal

merkmal.segment_ipa("t͡ʃaŋ⁵⁵")
# ['t͡ʃ', 'a', 'ŋ', '⁵⁵']

merkmal.merge_tone_digits(["t͡ʃ", "a", "ŋ", "⁵⁵"])
# ['t͡ʃ', 'a⁵⁵', 'ŋ']

# Grapheme decomposition
base, mods = merkmal.decompose_grapheme("tʰ")
# ('t', frozenset({'aspirated'}))
```

## Distance

Distances are normalised to [0, 1]. The Clements & Hume (1995)
feature geometry tree gives structure-aware weights: features
higher in the tree contribute more.

```python
import merkmal

# Across systems
merkmal.distance("p", "b")                    # voicing contrast
merkmal.distance("p", "b", system="classfeat") # trained weights

# Tonal distance with weight presets
merkmal.distance("a⁵⁵", "a³⁵", system="distinctive")
merkmal.distance("a⁵⁵", "a³⁵", system="distinctive",
                 node_weights="tone-heavy")
merkmal.distance("a⁵⁵", "a³⁵", system="distinctive",
                 node_weights="segmental")    # ignores tone
```

## Typological direction costs

The typology module encodes diachronic priors (e.g. lenition is
more frequent than fortition) as asymmetric direction costs,
separate from the synchronic geometry.

```python
import merkmal

typ = merkmal.load_typology("lenition-bias")
print(typ.cost_for("continuant", +1))  # stop → fricative (lenition)
print(typ.cost_for("continuant", -1))  # fricative → stop (fortition)
```

Three bundled typologies: `default` (symmetric), `lenition-bias`,
`corecog-derived` (learned from Lexibank cognate data).

## Multi-state systems (P-base)

P-base-derived systems expose multi-state values (`+`, `-`, `n`,
`.`, `o`, `x`) through `FeatureState`.

```python
import merkmal

rep = merkmal.get_representation("a", system="pbase-hc")
print(rep.values["syllabic"])
# FeatureState.POSITIVE
```

The bundled P-base table is derived, not verbatim. Duplicate rows
with conflicting values have the conflicting cells downgraded to
`.` (`FeatureState.DOT`). The P-base data retains its own
attribution and license notice.

## Custom models and configuration

Every feature system, geometry, typology, and diacritic set is a
pluggable data file. Point merkmal at an external directory to add your
own — layered on top of the built-ins by default:

```python
import merkmal

system = merkmal.load_model_from_dir("/path/to/mymodel")
reg = merkmal.create_registry(extra_model_dirs=["/path/to/models"])
```

Or via environment variables (`os.pathsep`-separated lists):
`MERKMAL_MODELS`, `MERKMAL_GEOMETRIES`, `MERKMAL_TYPOLOGIES`,
`MERKMAL_DIACRITICS`; `MERKMAL_DATA_ISOLATED=1` excludes the built-ins.
This works start to end, including a fully custom feature vocabulary
(the diacritic/tone/modifier → feature mapping is itself a data file).
See [docs/custom-models.md](https://github.com/tresoldi/merkmal/blob/main/docs/custom-models.md).

## Repository structure

```
merkmal/
├── models/                 pluggable model directories (data)
│   ├── descriptive/        model.json + inventory.tsv + features.tsv + classes.tsv
│   ├── broad/
│   ├── distinctive/
│   ├── phoible/            model.json + inventory.tsv (37 feature columns)
│   ├── pbase-{hc,jfh,spe,uftc}/
│   └── classfeat/          model.json + inventory.tsv + weights.json
├── geometries/
│   └── clements-hume.json  Clements & Hume (1995) feature geometry tree
├── typologies/             direction cost files for asymmetric distance
├── python/                 Python package (v0.6.0)
│   ├── pyproject.toml
│   ├── README.md
│   ├── LICENSE
│   ├── merkmal/            package code + bundled data
│   └── tests/
├── go/                     Go module (github.com/tresoldi/merkmal/go)
│   ├── data/               bundled models/geometries for NewDefaultRegistry
│   ├── go.mod
│   ├── merkmal.go          System interface, Role, DistanceOption
│   └── *.go
├── tests/golden/           cross-language parity expectations (10k+ entries)
├── scripts/                model validation scripts
└── docs/                   getting started notebook and tutorials
```

## Documentation

The **[Getting Started notebook](docs/notebooks/getting_started.ipynb)**
walks through the full API with worked examples: feature lookup,
natural classes, distances across systems, sound change modelling
(Grimm's law, lenition chains, tonogenesis), tone, and a small
cognate detection experiment with Austronesian data.

Four additional tutorials cover specific topics in depth:
[phonological features](docs/tutorials/01_phonology.py),
[typology](docs/tutorials/02_typology.py),
[historical linguistics](docs/tutorials/03_historical_linguistics.py), and
[cognate detection](docs/tutorials/04_cognate_detection.py).

## License

MIT. See [LICENSE](LICENSE).
