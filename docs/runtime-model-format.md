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
- `@geometry clements-hume` selects the only geometry currently compiled into
  the native library (`merkmal-clements-hume-inspired-v1`, see
  [geometry.md](geometry.md)). Other geometry names are rejected; geometry
  files are not loaded at runtime yet.
- `@validation strict` (the default) or `@validation permissive` selects how
  the model is checked. See below.
- `grapheme` rows are required. Each row supplies one UTF-8 grapheme and
  one or more categorical feature names. The grapheme is normalized into a
  lookup key exactly as a query is, so a row may be written precomposed
  (`ã`) or decomposed and either spelling will match at lookup time. The
  source conventions apply too: a row written `ʧ` is reachable as `tʃ`.
- `feature` rows are accepted for readability and carry no meaning to the
  scorer. They are not treated as declarations.
- Unrecognized lines are an error under strict validation.

## Validation

Validation is **strict by default**. A strict model must satisfy:

- every feature on every `grapheme` row is known to the geometry;
- no grapheme is declared twice;
- every line is a recognized directive, a comment, a `grapheme` row, or a
  `feature` row.

The first of those is the important one. A feature the geometry does not know
reaches no scoring dimension, so a model built from such features registers
successfully and then returns `0.0` for every comparison — which is
indistinguishable from "these segments are identical". This model used to
register cleanly:

```text
@model arbitrary
@type categorical
@geometry clements-hume
grapheme X foo
grapheme Y bar
```

It now fails with:

```text
strict validation: feature is unknown to the geometry and so cannot affect any
distance; add it to the geometry or use '@validation permissive': foo
```

`@validation permissive` restores the old behaviour for exploratory work. It is
an explicit choice, and the resulting model really will score unknown features
as nothing:

```text
@model arbitrary
@type categorical
@validation permissive
grapheme X foo
grapheme Y bar
```

`mk_registry_add_model_text_ex` returns the diagnostic as an owned string, so
callers can report which line and token were rejected. The Python wrapper
raises `merkmal.NativeError` carrying the same text.

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
- Strict validation failure (unknown feature, duplicate grapheme,
  unrecognized line, bad `@validation` argument): `MK_ERR_PARSE`
- Allocation failure: `MK_ERR_OOM`

Use `mk_registry_add_model_text_ex` to get a message naming the offending line
and token rather than only the status code.
