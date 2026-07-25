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

The package is intentionally native-only. The pre-C Python implementation is
archived in `tools/legacy_python/` at the repository root for generator and
parity work; it is not installed as part of the Python package.

## Development

From the repository root:

```sh
python -m pip install -e python
python -m pytest python/tests -q
python -m build python --wheel
```

The extension is built with `Py_LIMITED_API=0x030C0000`, producing a
`cp312-abi3` wheel.
