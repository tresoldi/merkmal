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

## Installation

Python (from the `python/` directory):

```bash
cd python
pip install -e ".[dev]"
```

Go:

```go
import merkmal "github.com/tresoldi/merkmal/go"
```

Run checks:

```bash
# Python (from python/)
ruff check .
mypy merkmal/
pytest tests/ -q

# Go (from go/)
go test ./...
go vet ./...
```

## Quick start (Python)

```python
import merkmal

# Built-in systems
print(merkmal.list_systems())
# ['descriptive', 'broad', 'distinctive', 'pbase-hc', 'pbase-jfh',
#  'pbase-spe', 'pbase-uftc', 'phoible', 'classfeat']

# Basic grapheme lookup
print(merkmal.get_features("p"))
# frozenset({'consonant', 'voiceless', 'bilabial', 'stop'})

# Predefined sound classes
print(merkmal.get_class_features("V"))
# frozenset({'vowel'})

# Distance
print(merkmal.distance("a", "e"))
print(merkmal.distance("p", "b", system="classfeat"))
```

## Quick start (Go)

```go
modelsFS := os.DirFS("models")
geomFS := os.DirFS("geometries")
reg, _ := merkmal.NewRegistry(modelsFS, geomFS)
sys, _ := reg.Get("descriptive")
dist := sys.SegmentDistance("p", "b")
```

All Go loading is `fs.FS`-based. Use `os.DirFS` for disk-based
models, `embed.FS` for compiled-in data, or `fstest.MapFS` for
tests.

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

## Working with systems

The Python package exposes a lazy default registry through
top-level helpers, or individual system objects can be obtained
directly.

```python
import merkmal

descriptive = merkmal.get_system("descriptive")
distinctive = merkmal.get_system("distinctive")
pbase = merkmal.get_system("pbase-hc")

print(descriptive.grapheme_to_features("a"))
print(distinctive.grapheme_to_features("a"))
print(pbase.grapheme_to_representation("a"))
```

Exact reverse lookup is available when a native representation maps
directly to a known grapheme.

```python
descriptive = merkmal.get_system("descriptive")

grapheme = descriptive.features_to_grapheme(
    frozenset({"consonant", "voiced", "bilabial", "stop"})
)
print(grapheme)
# 'b'
```

## Feature queries

Use `features_to_graphemes(...)` to find all graphemes matching a
feature set. Matching is partial by default.

```python
import merkmal

vowels = merkmal.features_to_graphemes(frozenset({"vowel"}))
print(vowels[:10])

# Exact matching
features = merkmal.get_features("a")
print(merkmal.features_to_graphemes(features, exact=True))
```

## Natural classes and matrices

```python
import merkmal

# Shared features of a segment set
print(merkmal.derive_class_features(["p", "t", "k"]))
# frozenset({'consonant', 'voiceless', 'stop'})

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

## Distance

```python
import merkmal

print(merkmal.distance("a", "e"))
print(merkmal.distance("a", "u"))
print(merkmal.distance("p", "b"))
print(merkmal.distance("t", "d", system="pbase-hc"))
```

A precomputed nested dictionary can also be supplied:

```python
precomputed = {"a": {"e": 1.5, "u": 2.0}, "p": {"b": 0.5}}
print(merkmal.distance("a", "e", precomputed=precomputed))
```

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
├── python/                 Python package (v0.5.0)
│   ├── pyproject.toml
│   ├── merkmal/
│   └── tests/
├── go/                     Go module (github.com/tresoldi/merkmal/go)
│   ├── go.mod
│   ├── merkmal.go          System interface, Role, DistanceOption
│   └── *.go
├── tests/golden/           cross-language parity expectations
├── scripts/                model validation scripts
├── docs/                   tutorials and notebooks
└── paper/                  extended guides (programmer + linguist perspectives)
```

## Documentation

See the [tutorials](docs/tutorials/) for worked examples covering
phonological features, typology, historical linguistics, and
cognate detection. Extended guides are available under
[paper/](paper/).

## License

MIT. See [LICENSE](LICENSE).
