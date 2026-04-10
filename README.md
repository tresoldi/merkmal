# merkmal

`merkmal` is a standalone Python package for manipulating phonological
features. Zero runtime dependencies, Python 3.12+.

It provides:

- bundled phonological feature datasets
- pluggable feature systems (9 built-in)
- feature geometry and distance functions (Clements & Hume 1995)
- tonal geometry (Yip/Bao)
- query and analysis helpers for graphemes and feature sets
- UPA transcription support

## Installation

Install from PyPI:

```bash
pip install merkmal
```

Development install:

```bash
git clone https://github.com/tresoldi/merkmal.git
cd merkmal
pip install -e ".[dev]"
```

Run checks:

```bash
ruff check .
mypy src
pytest -q
```

## Quick start

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

## Systems

| System | Type | Features | Distance |
|--------|------|----------|----------|
| `descriptive` | categorical | articulatory | geometry-weighted |
| `broad` | categorical | simplified | geometry-weighted |
| `distinctive` | privative | Clements & Hume | geometry-weighted |
| `pbase-hc`, `-jfh`, `-spe`, `-uftc` | multi-state | 4 theoretical families | geometry-weighted |
| `phoible` | binary | 37 features | Hamming |
| `classfeat` | hybrid | sound classes + continuous | trained weights |

All systems implement the same `FeatureSystem` protocol. Distances, queries,
matrices, and natural class derivation work across all of them.

## Working with systems

You can use the lazy default registry through top-level helpers, or work
with a specific system object.

```python
import merkmal

descriptive = merkmal.get_system("descriptive")
distinctive = merkmal.get_system("distinctive")
pbase = merkmal.get_system("pbase-hc")

print(descriptive.grapheme_to_features("a"))
print(distinctive.grapheme_to_features("a"))
print(pbase.grapheme_to_representation("a"))
```

Exact reverse lookup is available when a native representation maps directly to
a known grapheme.

```python
descriptive = merkmal.get_system("descriptive")

grapheme = descriptive.features_to_grapheme(
    frozenset({"consonant", "voiced", "bilabial", "stop"})
)
print(grapheme)
# 'b'
```

## Feature queries

Use `features_to_graphemes(...)` to find all graphemes matching a feature set.
Matching is partial by default.

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

You can also supply a precomputed nested dictionary:

```python
precomputed = {"a": {"e": 1.5, "u": 2.0}, "p": {"b": 0.5}}
print(merkmal.distance("a", "e", precomputed=precomputed))
```

## Multi-state systems (P-base)

P-base-derived systems expose multi-state values (`+`, `-`, `n`, `.`, `o`, `x`)
through `FeatureState`.

```python
import merkmal

rep = merkmal.get_representation("a", system="pbase-hc")
print(rep.values["syllabic"])
# FeatureState.POSITIVE
```

The bundled P-base table is derived, not verbatim. Duplicate rows with
conflicting values have the conflicting cells downgraded to `.`
(`FeatureState.DOT`). The P-base data retains its own attribution and license
notice in `src/merkmal/data/pbase/`.

## Custom datasets

```python
from merkmal import create_registry, load_dataset

dataset = load_dataset(directory="my_feature_data")
registry = create_registry(dataset=dataset)
system = registry.get_system("descriptive")
print(system.grapheme_to_features("k"))
```

Expected files in `my_feature_data/`: `sounds.tsv`, `classes.tsv`, `features.tsv`.

## Documentation

See the [tutorials](docs/tutorials/) for worked examples covering phonological
features, typology, historical linguistics, cognate detection, and UPA
transcription.

## License

MIT. See [LICENSE](LICENSE).
