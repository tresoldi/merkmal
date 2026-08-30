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

Validation is strict by default: every feature must be one the geometry knows,
or the model is rejected. That check exists because an unknown feature reaches
no scoring dimension, so a model built from unknown features registers cleanly
and then returns `0.0` for every comparison. Add `@validation permissive` to
opt out for exploratory work, and use `mk_registry_add_model_text_ex` to get a
message naming the offending line and token.

See [runtime-model-format.md](runtime-model-format.md) for the current format
and [geometry.md](geometry.md) for the feature names the geometry knows.
Only categorical runtime models are public for now; the parser and C data model
leave room for valued and class-feature formats later.

The Python `Registry.add_model_text` method also accepts an optional `manifest`
mapping. When supplied, it must include `name`, `version`, `source`,
`interpretation`, and `license`; the name must match `@model`. The manifest is
retained by that registry, returned by `model_manifest()`, and included in
`operation_fingerprint()` so a custom inventory's scholarly context travels
with cached results. The compact native C API remains available without this
Python metadata layer.

The pre-C Python directory-loader implementation is no longer part of the
active codebase. Historical tutorials and scripts that referenced it are kept
under `docs/legacy_python/` as reference material only.
