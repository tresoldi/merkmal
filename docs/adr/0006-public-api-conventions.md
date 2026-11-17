# 0006. `_new`/`_free` names and NUL-terminated strings in the public API

## Context

The house standard lists `_create`/`_destroy` among its ownership names and
prefers pointer plus length over NUL termination for text.

## Decision

This project keeps its own conventions, consistently:

- Constructors are `_new` (`mk_registry_new_builtin`, `mk_bundle_new`) and
  destructors `_free` (`mk_registry_free`, `mk_string_list_free`,
  `mk_string_free`). Every destructor accepts NULL. Renaming them would be a
  breaking change to every caller for no gain in clarity, since the vocabulary
  is uniform.
- Graphemes and short text are NUL-terminated UTF-8. A length-taking `_n`
  variant exists where callers hold buffers rather than strings
  (`mk_registry_add_model_text_n`). Every binding refuses a string with an
  embedded NUL before it reaches the library, so truncation cannot happen
  silently.

## Consequences

- New public functions follow `_new`/`_free`, and add an `_n` variant when a
  caller is likely to hold a buffer.
- Revisit pointer-plus-length for graphemes if a caller appears that cannot
  supply a terminated string.
