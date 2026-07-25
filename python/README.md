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
