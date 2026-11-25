# Runtime model format

`mk_registry_add_model_text` accepts a complete caller-supplied model as a
UTF-8 text buffer. The format is line-oriented, so that a model can be read,
compared and searched with ordinary text tools.

The format is public for categorical models only. Other model types are
refused with `MK_ERR_UNSUPPORTED_MODEL`.

## Syntax

```text
@format_version 1
@model NAME
@type categorical
@geometry clements-hume
grapheme GRAPHEME FEATURE...
```

Rules:

- Blank lines are ignored.
- Lines whose first non-space character is `#` are comments.
- Fields are separated by ASCII whitespace.
- `@model` is required, appears once, and gives one name: the system's name
  in the registry.
- `@type categorical` is required.
- `@geometry clements-hume` selects the geometry compiled into the library
  (`merkmal-clements-hume-inspired-v1`; see
  [geometry.md](../method/geometry.md)). It is optional, since this is the only
  geometry available. Any other name is refused with
  `MK_ERR_UNSUPPORTED_MODEL`; geometry files are not loaded at run time.
- `@validation strict` (the default) or `@validation permissive` selects how
  the model is checked; see [Validation](#validation).
- `@format_version 1` declares the version of this text format. It is
  optional, and a model without it is read as version 1. A model that declares
  a newer version than the library reads is refused with
  `MK_ERR_UNSUPPORTED_MODEL` and a diagnostic, rather than read as if it were
  this format, since a later version may give an existing line a new meaning.
  A value that is not a positive integer is `MK_ERR_PARSE`. The declaration is
  recommended for any model kept in a file.
- At least one `grapheme` row is required. `+` cannot be a grapheme: it marks
  a word boundary for the tokenizers and is never looked up. Each row supplies one UTF-8
  grapheme and one or more categorical feature names. The grapheme is
  normalized into a lookup key exactly as a query is, so a row may be written
  precomposed (`ã`) or decomposed, and either spelling matches at lookup time.
  The source conventions also apply: a row written `ʧ` is reachable as `tʃ`.
- `feature` rows are accepted for readability and have no effect on scoring.
  They are not declarations.
- Under strict validation any other line is an error.

## Validation

Validation is **strict by default**. A strict model must satisfy the following
conditions:

- every feature on every `grapheme` row is known to the geometry;
- every grapheme carries at least one feature that is scored;
- no grapheme is declared twice;
- every line is a recognized directive, a comment, a `grapheme` row or a
  `feature` row.

The first two conditions guard against a silent failure. A feature the
geometry does not know reaches no scoring dimension, so a model built from
such features would register and then return `0.0` for every comparison,
which cannot be told apart from "these segments are identical". Under strict
validation, the model

```text
@model arbitrary
@type categorical
@geometry clements-hume
grapheme X foo
grapheme Y bar
```

is refused with `MK_ERR_PARSE` and the diagnostic

```text
strict validation: feature is unknown to the geometry and so cannot affect any
distance; add it to the geometry or use '@validation permissive': foo
```

`@validation permissive` disables these checks, for exploratory work. It is an
explicit choice, and the resulting model scores unknown features as
contributing nothing:

```text
@model arbitrary
@type categorical
@validation permissive
grapheme X foo
grapheme Y bar
```

`mk_registry_add_model_text_ex` returns the diagnostic as an owned string, so
that a caller can report which line and token were rejected. The Python
wrapper raises `merkmal.NativeError` with the same diagnostic in its message.

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
  `MK_ERR_PARSE`.
- A `@type` other than `categorical`, a `@geometry` other than
  `clements-hume`, or a `@format_version` newer than the library reads:
  `MK_ERR_UNSUPPORTED_MODEL`.
- A `grapheme` row with no features, or a malformed directive argument (a bad
  `@validation` or `@format_version` value): `MK_ERR_PARSE`.
- Strict validation failure (unknown feature, grapheme without a scored
  feature, duplicate grapheme, unrecognized line): `MK_ERR_PARSE`.
- A model name already in the registry: `MK_ERR_DUPLICATE_SYSTEM`.
- An embedded NUL byte (`mk_registry_add_model_text_n`): `MK_ERR_PARSE`.
- Allocation failure: `MK_ERR_OOM`.

`mk_registry_add_model_text_ex` gives a message naming the offending line and
token in addition to the status code.
