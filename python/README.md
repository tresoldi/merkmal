# merkmal

merkmal maps IPA transcriptions of speech segments to phonological feature
representations under several feature systems, and computes dissimilarities
between segments from those representations. This package is the Python
interface and command line of the merkmal C99 library. The extension module,
`merkmal._native`, is built against the CPython Limited API and calls the C
library for every computation; the package contains no separate implementation.

The library, its method and its limits are documented in the
[repository](https://github.com/tresoldi/merkmal).

## Installation

```sh
python -m pip install merkmal
```

The package requires CPython 3.12 or later and has no runtime dependencies.
Wheels are `cp312-abi3`, built with `Py_LIMITED_API=0x030C0000`.

## Usage

```python
import merkmal

merkmal.list_systems()                            # names of the built-in systems
merkmal.get_features("pʰ")                        # frozenset of feature labels
merkmal.distance("p", "b")                        # 0.1429, default system
merkmal.distance("p", "b", system="phoible")      # another feature system
merkmal.distance_with_coverage("ai", "au")        # score, coverage, comparability
merkmal.segment_ipa_merged("tʰoŋ⁵⁵")              # ['tʰ', 'o⁵⁵', 'ŋ']
merkmal.merge_tone_digits(["a", "⁵", "⁵"])        # ['a⁵⁵']
```

Every function that takes `system` uses `merkmal.DEFAULT_SYSTEM`
(`distinctive`) when none is given.

| Function | Result |
| --- | --- |
| `list_systems()` | Names of the available systems |
| `get_features(g, system=)` | Feature labels of a grapheme |
| `is_segment(g, system=)` | Whether the system recognizes a grapheme; does not raise for unknown input |
| `diagnose(g, system=)` | Why a grapheme is refused: status, valid prefix, offending text |
| `distance(a, b, system=, node_weights=)` | Dissimilarity of two segments |
| `distance_with_coverage(a, b, ...)` | The same, as a `Comparison` of score, coverage and comparability (alias `compatibility_dissimilarity`) |
| `feature_vector(g, system=)`, `vector_labels(system=)` | Fixed-width numeric vector of a grapheme, and its column names |
| `fixed_space_distance(a, b, system=)` | Mean absolute difference of two feature vectors |
| `feature_distance(f1, f2)` | Number of edges between two features in the geometry tree |
| `sound_distance(features_a, features_b, node_weights=)` | Distance between two feature sets in the geometry, without a system |
| `normalize(g)` | NFC form of a grapheme, with merkmal's IPA rewrites (`ʧ` becomes `tʃ`) |
| `segment_ipa(text)` | Orthographic segmentation: a split at every base character not joined by a tie bar |
| `system_segment_ipa(text, system=)` | Segmentation by the longest sequence the system recognizes as one segment |
| `merge_tone_digits(segments)`, `segment_ipa_merged(text)` | Chao tone digits or tone letters merged into the vowel or syllabic consonant that bears them |
| `split_tone(segment)` | A merged segment split into base and tone |
| `system_fingerprint(system=)`, `operation_fingerprint(...)` | Canonical description and SHA-256 of a system, or of a system with call settings |
| `AbstractSegment` | A feature bundle not identified with a grapheme |
| `Registry` | A registry of systems that also accepts models supplied at run time |
| `load_geometry(path)`, `geometry_distance(a, b, geometry=)` | Experimental: scoring under a geometry loaded from a JSON file |

`node_weights` selects a weight preset of the geometry, such as
`"ignore-tone"`; an unknown preset raises `ValueError`. `feature_distance` and
`sound_distance` take no `system`, because they measure within the compiled
geometry, which all systems share. `feature_distance` raises `ValueError` for a
feature that is not a node of the tree, as many returned labels (`bilabial`)
are not.

`UNICODE_VERSION` is the Unicode version of the compiled normalization tables,
and `DATA_PROFILE` is `"full"`, or `"cc-by"` for a build without the PHOIBLE
and P-base tables.

### Unknown input

`is_segment()` is the predicate for tokens from external sources. For a
grapheme the system does not recognize, `get_features()` and `distance()` raise
`ValueError`; for an unknown system they raise `KeyError`. Markup of CLDF and
CLTS sources (`<?>`, `<<->>`, boundary markers) raises `SourceMarkerError`, a
subclass of `ValueError`, so that it can be handled separately from segments
the system lacks. `diagnose()` returns the
reason without raising.

### Segments derived from listed ones

In the categorical systems (`distinctive`, `descriptive`), a sequence that the
table does not list is analysed as one segment where possible: vowel sequences,
consonant clusters, affricates and prenasalized stops written without a tie
bar, precomposed letters of source orthographies, and segments carrying tone.

```python
merkmal.is_segment("aːi³³", system="descriptive")   # True
merkmal.is_segment("ñ", system="descriptive")       # True
merkmal.get_features("ai", system="descriptive")    # includes 'diphthong', 'n1-open', 'n2-close'
merkmal.get_features("st")                          # includes 'consonant-cluster', 'n1-fricative', 'n2-stop'
```

A vowel sequence carries `diphthong`, positional features of each part
(`n1-open`, `n2-close`) and features of the movement between them
(`move-height-open-close`). A consonant cluster carries `consonant-cluster` and
positional features of each component (`n1-nasal`, `n2-stop`), with `geminate`
for two identical components and `pre-nasalized` for a nasal followed by an
obstruent (`mp`, `nt`). A voiced stop after a homorganic nasal (`mb`, `nd`,
`ŋg`, `ɲɟ`, `ɳɖ`) is read as a single prenasalized stop, as is the explicit
notation `ᵐb`, `ⁿd`. The policy and system used should be recorded with any
stored tokenization, since neither reading is a phonological analysis of a
particular language.

### Models supplied at run time

A `Registry` holds the built-in systems and any categorical models added to it
in the runtime model format:

```python
registry = merkmal.Registry()
registry.add_model_text("""
@model toy
@type categorical
@geometry clements-hume
grapheme X consonant voiceless bilabial stop
""")
registry.get_features("X", system="toy")
```

A `Registry` provides `list_systems`, `get_features`, `is_segment`, `distance`,
`system_segment_ipa`, `system_fingerprint`, `operation_fingerprint`,
`model_manifest` and `add_model_text`. Each is the module-level function of the
same name, applied to that registry; the other functions read the built-in
systems only. The native registry lives as long as the object.
Module-level functions use a shared registry of the built-in systems only, so a
model added to a `Registry` is visible only through it. A name that is already
registered raises `ValueError`. The format is described in
`docs/guide/runtime-model-format.md` in the repository.

## Command line

The package installs a `merkmal` command, also available as `python -m merkmal`:

```sh
merkmal systems
merkmal features p
merkmal distance ai au
merkmal normalize ã
merkmal segment "tʃa pʰa"
merkmal --system phoible features bʰ
```

`--system` (`-s`) precedes the subcommand. The default output is meant for
reading and may change between releases. The machine-readable modes are the
stable interface; each may be given before or after the subcommand:

| Mode | Output |
| --- | --- |
| `--json` | one JSON object per invocation |
| `--jsonl` | one JSON object per record, one per line |
| `--tsv` | a header row, then one row per record |

Records by subcommand:

| Subcommand | JSON object | JSONL/TSV record |
| --- | --- | --- |
| `systems` | `{"systems": [...]}` | `system` |
| `features` | `{"system", "grapheme", "features": [...]}` | `grapheme`, `feature` |
| `distance` | `{"system", "a", "b", "distance", "coverage", "comparability"}` | the same fields |
| `normalize` | `{"input", "normalized"}` | the same fields |
| `segment` | `{"text", "segments": [...]}` | `index`, `segment` |

`system` is the system used: the one named, or `merkmal.DEFAULT_SYSTEM`. Text is
UTF-8. In TSV, a backslash, tab or newline inside a value is written `\\`, `\t`
or `\n`, so that a value never adds a column or a row. Floating-point values
are written at full precision.

The exit status is 0 on success and 1 on an error caused by the input (an
unknown system or grapheme), with a message on standard error and nothing on
standard output. A usage error, such as two modes at once, exits with 2.

## Development

From the repository root:

```sh
python -m pip install -e ".[dev]"
python -m pytest python/tests -q
python -m build --sdist --wheel
```

## License

The code is released under the MIT license. The feature data compiled into the
package carries the terms of its sources, and the distribution is licensed as
`MIT AND CC-BY-4.0 AND CC-BY-SA-3.0 AND CC-BY-NC-SA-4.0`; the `NOTICE` file
included in the distribution gives the attribution each source requires.
