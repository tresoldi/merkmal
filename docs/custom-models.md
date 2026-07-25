# Custom Models

The C library now treats built-in models as compiled data and accepts
caller-supplied runtime models through the registry API. It does not search
environment variables or load model directories by itself.

For the first native slice, runtime models use a simple line-oriented UTF-8
format:

```text
@model toy
@type categorical
@geometry clements-hume
grapheme X consonant voiceless bilabial stop
grapheme Y vowel open front unrounded
```

Pass the complete model text to:

```c
mk_registry_add_model_text(registry, model_text);
```

See [runtime-model-format.md](runtime-model-format.md) for the current format.
Only categorical runtime models are public for now; the parser and C data model
leave room for valued and class-feature formats later.

The pre-C Python directory-loader implementation is archived under
`tools/legacy_python/` for data generation and parity work. It is not part of
the installable Python package and should not be treated as a supported runtime
API.
