# merkmal Python Wrapper

This package exposes the `merkmal` C99 library to Python through a
CPython Limited API extension module, `merkmal._native`.

The current wrapper covers the high-level native slice:

- `list_systems`
- `get_features`
- `is_segment`
- `distance`
- `feature_distance`
- `normalize`
- `segment_ipa`
- `merge_tone_digits`
- `segment_ipa_merged`
- `Registry`

The package is intentionally native-only. The pre-C Python implementation has
been removed from the active package; old tutorials, notebooks, and research
scripts live under `docs/legacy_python/` as historical reference material.

```python
import merkmal

print(merkmal.list_systems())
print(merkmal.get_features("pʰ"))
print(merkmal.distance("p", "b", node_weights="ignore-tone"))
print(merkmal.merge_tone_digits(["a", "5", "5"]))
print(merkmal.segment_ipa_merged("tʰoŋ⁵⁵"))
```

The `descriptive` system accepts synthesized source-token segments used by
lexical datasets, including vowel clusters, selected author-defined consonant
clusters, precomposed Latin source letters, and tone-bearing nuclei:

```python
print(merkmal.is_segment("aːi³³", system="descriptive"))
print(merkmal.is_segment("ɛï³³", system="descriptive"))
print(merkmal.is_segment("kɣ", system="descriptive"))
print(merkmal.is_segment("ṵː", system="descriptive"))
print(merkmal.is_segment("ñ", system="descriptive"))
print(merkmal.get_features("ai", system="descriptive"))
print(merkmal.distance("ai", "a", system="descriptive"))
```

Vowel clusters use short synthetic features such as `diphthong`, `n1-open`,
`n2-close`, and `move-height-open-close`.
Consonant clusters use `consonant-cluster`, positional component features such
as `n1-nasal` and `n2-stop`, plus `geminate` or `pre-nasalized` when the
component sequence supports those readings. Markup/control tokens such as
`<?>`, `<<->>`, and `→` are still rejected.
Bare `mb` and `nd` resolve, as two-component clusters carrying `pre-nasalized`
alongside their `n1-`/`n2-` component features. Use the explicit notation `ᵐb`
or `ⁿd` when a single prenasalized segment is meant rather than a sequence: that
form resolves to one segment with `pre-nasalized` and no component features.

Use `is_segment()` as the non-throwing predicate for source tokens. Unknown
tokens return `False` from `is_segment()` and raise `ValueError` from
`get_features()`.

Runtime categorical models can be registered on an owned native registry:

```python
registry = merkmal.Registry()
registry.add_model_text("""
@model toy
@type categorical
@geometry clements-hume
grapheme X consonant voiceless bilabial stop
""")
print(registry.get_features("X", system="toy"))
```

`Registry` owns its C registry handle, and each of its methods is the
top-level function of the same name pointed at that registry. Top-level calls
use a shared default registry holding the built-in systems; a model added to a
`Registry` is visible only through it, and `add_model_text` refuses to touch
the shared one.

`feature_distance` takes no `system`: it measures a distance in the compiled
geometry, which every system shares.

## Development

From the repository root:

```sh
python -m pip install -e ".[dev]"
python -m pytest python/tests -q
python -m build --sdist --wheel
```

The extension is built with `Py_LIMITED_API=0x030C0000`, producing a
`cp312-abi3` wheel.
