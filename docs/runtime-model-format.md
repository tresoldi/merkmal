# Runtime Model Format

`mk_registry_add_model_text` accepts a complete caller-supplied model as a
UTF-8 text buffer. The format is intentionally line-oriented and
grep-friendly.

This format is public for categorical models only. Valued and classfeat
runtime models are reserved for later versions.

## Syntax

```text
@model NAME
@type categorical
@geometry clements-hume
grapheme GRAPHEME FEATURE...
```

Rules:

- Blank lines are ignored.
- Lines whose first non-space character is `#` are comments.
- Fields are separated by ASCII whitespace.
- `@model` is required and names the system in the registry.
- `@type categorical` is required.
- `@geometry clements-hume` is accepted for readability and future
  compatibility. The current C implementation uses the compiled-in
  Clements-Hume geometry.
- `grapheme` rows are required. Each row supplies one UTF-8 grapheme and
  one or more categorical feature names.
- Unknown directive lines are currently ignored. Do not rely on ignored
  directives for stable metadata.

`feature` declaration rows may appear in files for human readability, but
the current parser does not use them for validation.

## Example

```text
# Minimal categorical model
@model toy
@type categorical
@geometry clements-hume

feature consonant major
feature vowel major

grapheme X consonant voiceless bilabial stop
grapheme Y vowel open front unrounded
```

```c
mk_registry *registry = NULL;
const mk_system *toy = NULL;

mk_registry_new_builtin(&registry);
mk_registry_add_model_text(registry, model_text);
mk_registry_get_system(registry, "toy", &toy);
```

## Errors

- Missing `@model`, missing `@type categorical`, or no `grapheme` rows:
  `MK_ERR_PARSE`
- Unsupported `@type`: `MK_ERR_UNSUPPORTED_MODEL`
- Empty `grapheme` row or row with no features: `MK_ERR_PARSE`
- Allocation failure: `MK_ERR_OOM`
