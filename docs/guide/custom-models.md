# Custom models

The built-in models are compiled into the library. A caller can add models of
its own at run time through the registry API; the library does not read
environment variables or search model directories.

A runtime model is a line-oriented UTF-8 text:

```text
@model toy
@type categorical
@geometry clements-hume
grapheme X consonant voiceless bilabial stop
grapheme Y vowel open front unrounded
```

The complete text is passed to the registry:

```c
mk_registry_add_model_text(registry, model_text);
```

Validation is strict by default: every feature must be known to the geometry,
or the model is rejected. An unknown feature reaches no scoring dimension, so
a model built from unknown features would register and then return `0.0` for
every comparison. `@validation permissive` disables the check for exploratory
work, and `mk_registry_add_model_text_ex` returns a message naming the
offending line and token.

The format is specified in
[runtime-model-format.md](runtime-model-format.md), and the feature names the
geometry knows are listed in [geometry.md](../method/geometry.md). Only
categorical runtime models are supported.

In Python, `Registry.add_model_text` also accepts an optional `manifest`
mapping. When given, it must include `name`, `version`, `source`,
`interpretation` and `license`, and the name must match `@model`. The manifest
is kept by that registry, returned by `Registry.model_manifest()`, and included
in `Registry.operation_fingerprint()`, so that the scholarly context of a
custom inventory is recorded with results derived from it. The model is
registered before the manifest is checked, so a model whose manifest is
rejected remains registered. The C API has no manifest.
