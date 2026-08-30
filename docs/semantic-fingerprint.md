# Semantic fingerprints

## Status

Version 1 is implemented as a public, system-level provenance interface. It is
deliberately separate from the C ABI version and package version: two builds
can preserve both while changing a scientific result.

```c
mk_status mk_system_semantic_fingerprint(const mk_system *system,
                                         char **payload_out,
                                         char **digest_out);
```

Python exposes the same interface as `merkmal.system_fingerprint(system=...)`
and `Registry.system_fingerprint(system=...)`; both return `(payload, digest)`.
The strings returned by C are owned by the caller and freed with
`mk_string_free`. Either output may be `NULL`, but not both.

## Why this is needed

`merkmal` can retain ABI compatibility while a feature inventory, geometry,
resolver, tone grammar, or scorer changes a distance, alignment, cluster, or
induced conditioning class. A system name such as `descriptive`, and even a
package version, are therefore insufficient provenance for a stored result.

`cognator` calibrates thresholds on Merkmal's distance scale; `regulae` uses a
chosen system's returned feature vocabulary to form conditioning hypotheses.
Both need an identity that travels with their outputs.

## v1 canonical payload

The payload is canonical UTF-8 `key=value` text in this fixed order:

| Field | Identifies |
| --- | --- |
| `schema` | Serialization schema/version |
| `system`, `system_kind` | Selected model and its declared kind |
| `model_version`, `model_sha256` | Built model version and source-model inputs, or the canonical semantic runtime inventory |
| `scorer` | Scorer selected by the system |
| `geometry`, `geometry_sha256` | Current geometry and exact geometry input |
| `diacritics_sha256` | Exact IPA/CLTS diacritic input |
| `resolver_policy` | Resolver and normalization policy |
| `tone_policy` | Chao-tone grammar/policy |
| `comparison_policy` | Baseline segment-distance policy |

The digest is the lowercase SHA-256 hash of that full payload. Store both: the
digest is a compact join key; the payload is what makes the key inspectable.

For compiled models, `model_sha256` covers every regular model-source file
except the human provenance note, in deterministic filename order. For runtime
models, it covers the model name and a canonical inventory: rows are ordered
by grapheme and each categorical feature set is ordered lexically. Thus a
harmless reordering of the runtime text does not change its identity.

## Scope boundary

This is intentionally a system fingerprint, not yet a full computation
fingerprint. It does not include a requested non-default node-weight preset,
the resolved weights, or a caller's tokenization/sequence-alignment policy.
Those are part of the result's own provenance and callers must record them
alongside this digest. A future operation-level interface can compose them
without changing this small system-identity seam.

The currently deferred segmentation and tone design work therefore remains
deferred: v1 names the existing resolver and Chao-tone policies precisely; it
does not claim that their present semantics are final. Typological sampling
design is likewise outside this system-level identity.

Python also exposes `operation_fingerprint(...)`, which composes the system
payload with caller-selected weights, tokenization, tone, comparison, and
missingness policies plus arbitrary JSON-serializable options. Use this digest
for cached distances and higher-level results; it is intentionally distinct
from the stable system digest.

For valued systems, the existing pairwise-complete scorer is also available as
`compatibility_dissimilarity(...)`, an explicit alias for
`distance_with_coverage(...)`. It remains a compatibility dissimilarity, not a
fixed-space metric; the latter requires a separately specified scorer.

## Consumer contract

`cognator` should persist the payload and digest with calibration constants,
fitted thresholds, and detection outputs, plus its tokenization and alignment
settings. `regulae` should persist them beside the feature-system name in its
exported model provenance, plus any non-default scoring configuration.
Consumers should reject or prominently label direct comparisons, merges, or
cache reuse across unequal fingerprints unless they explicitly state why a
difference is harmless for the question.
