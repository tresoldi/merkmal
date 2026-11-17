# Architecture decision records

Decisions that shape the project, written down so they are not relitigated by
accident (house standard, Architecture Decision Records). Each is short:
context, decision, consequences. A decision that departs from
[the house standard](../house-standard.md) says so.

| ADR | Decision |
| --- | --- |
| [0001](0001-c-api-is-the-canonical-interface.md) | The C API is the canonical interface; bindings wrap only `merkmal.h` |
| [0002](0002-unicode-normalization-is-compiled-in.md) | Unicode normalization is compiled in; utf8proc is a test oracle only |
| [0003](0003-generated-artifacts-are-committed.md) | Generated C tables and the WebAssembly build are committed |
| [0004](0004-mit-for-code-upstream-terms-for-data.md) | MIT for code, upstream terms for data (departs from the GPL-3.0 default) |
| [0005](0005-hand-maintained-data-stays-json.md) | Hand-maintained data stays JSON with JSON Schemas (departs from TOML) |
| [0006](0006-public-api-conventions.md) | `_new`/`_free` names and NUL-terminated strings in the public API |
| [0007](0007-scoring-policy-is-data.md) | Scoring policy numbers are data in the geometry file |
| [0008](0008-the-command-line-is-python.md) | The command line is the Python package's, with JSON/JSONL/TSV as its contract |

New ADRs take the next number. An ADR is superseded by a new one that says so,
not edited into a different decision.
