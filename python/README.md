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
lexical datasets, including vowel clusters, author-defined consonant clusters,
precomposed Latin source letters, and tone-bearing nuclei:

```python
print(merkmal.is_segment("aːi³³", system="descriptive"))
print(merkmal.is_segment("ɛï³³", system="descriptive"))
print(merkmal.is_segment("kɣ", system="descriptive"))
print(merkmal.is_segment("mb", system="descriptive"))
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

`Registry` owns its C registry handle. Top-level functions use the compiled-in
built-in registry.

## Development

From the repository root:

```sh
python -m pip install -e python
python -m pytest python/tests -q
python -m build python --wheel
```

The extension is built with `Py_LIMITED_API=0x030C0000`, producing a
`cp312-abi3` wheel.
