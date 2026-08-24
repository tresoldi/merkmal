# Semantic fingerprints

## Status

This is a design contract, not a public API yet. It defines what a future
fingerprint must identify before an implementation is added. It is deliberately
separate from the C ABI version and package version.

## Problem

`merkmal` can keep ABI compatibility while changing a scientific result. A
feature inventory, geometry, resolver, tone grammar, scorer, or weight preset
can move distances and change an alignment, cluster, or induced conditioning
class. A system name such as `descriptive`, and even the package version, are
therefore inadequate provenance for a stored result.

`cognator` demonstrates this concretely: calibration constants are expressed on
Merkmal's distance scale, and a change in the descriptive feature inventory
changed its clustering behaviour. `regulae`'s conditioning vocabulary is the
feature set returned by the selected system, so the same issue changes the
hypotheses it can discover.

## Proposed object

The public API should expose an immutable `mk_semantic_fingerprint` for a
fully specified computation, with a canonical text and SHA-256 digest. Its
canonical payload must include:

| Field | Identifies |
| --- | --- |
| `schema` | Fingerprint serialization schema/version |
| `system` | Selected model name and model semantic version |
| `model_sha256` | Canonical source model payload after generation inputs are fixed |
| `scorer` | Scorer identity and scorer semantic version (`leaf`, `scalar`, `valued`, or a future scorer) |
| `geometry` | Geometry identity/version and canonical geometry hash, when used |
| `weight_preset` | Requested preset and canonical resolved weights |
| `resolver` | Resolver and normalization policy version, including diacritic data hash |
| `tokenization_policy` | Orthographic, system-longest-match, or an explicit caller policy/version |
| `tone_policy` | Current tone grammar/version and the selected tier policy |
| `comparison_policy` | Missing-value and cross-tier policy, including whether coverage was requested |

The library should expose both the canonical UTF-8 payload and its digest. A
digest alone is compact but not auditable; the payload alone is auditable but
awkward as an identifier. Callers must not construct either independently.

## Scope rules

- A bare system fingerprint may omit call-specific fields such as a weight
  preset, but must identify every generated model/resolver/scorer input.
- A computation fingerprint must include all fields in the table. Two results
  are comparable only if their computation fingerprints match, unless a caller
  explicitly declares which differences are harmless for its question.
- Runtime models need the same canonicalization protocol. Their identity cannot
  be their user-provided name alone.
- A source-code change that cannot affect the canonical payload need not change
  the fingerprint; an ABI bump is a separate concern.

## Integration contract

`cognator` should record the computation fingerprint next to fitted thresholds,
calibration data, and all detection outputs. `regulae` should record it next to
the feature-system name in exported model provenance. Consumers should reject
or prominently label attempts to compare, merge, or score cached results from
different fingerprints.

## Deferred implementation

No C or Python API is added in this change. Implementation is deferred until a
single canonical representation of generated model, geometry, resolver, and
tone inputs is agreed and can be regression-tested across native and WASM
builds.
