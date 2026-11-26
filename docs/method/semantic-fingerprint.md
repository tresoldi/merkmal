# Semantic fingerprints

A semantic fingerprint identifies the data and policies that determine a
system's results. It is separate from the ABI version and the package version:
a feature inventory, the geometry, the resolver, the tone grammar or the scorer
can change a distance, an alignment, a cluster or a conditioning class without
any change to the ABI, and a system name such as `descriptive`, or a package
version, is therefore not sufficient provenance for a stored result.

## Interface

```c
mk_status mk_system_semantic_fingerprint(const mk_system *system,
                                         char **payload_out,
                                         char **digest_out);
```

The strings returned are owned by the caller and freed with `mk_string_free`.
Either output may be `NULL`, but not both.

Python exposes the same interface as `merkmal.system_fingerprint(system=...)`
and `Registry.system_fingerprint(system=...)`; both return
`(payload, digest)`.

## Payload, version 2

The payload is UTF-8 text, one `key=value` line per field, in this fixed
order:

| Field | Identifies |
| --- | --- |
| `schema` | The serialization and its version (`merkmal-system-fingerprint-v2`) |
| `system`, `system_kind` | The system and its declared kind |
| `model_version`, `model_sha256` | The model version and a hash of its source files, or of the canonical inventory of a runtime model |
| `scorer` | The scorer the system uses (`leaf`, `scalar` or `valued`) |
| `geometry`, `geometry_sha256` | The geometry's identity and a hash of `data/geometries/clements-hume.json` |
| `diacritics_sha256` | A hash of the diacritic data, `data/diacritics/ipa-clts.json` |
| `resolver_policy` | The resolver and normalization policy (`ipa-resolver-v1`) |
| `tone_policy` | The Chao tone grammar (`chao-tone-v1`) |
| `comparison_policy` | The segment-distance policy (`segment-distance-v2`) |
| `behavior_version` | The version of what the code does with the data: resolution, tokenization, tone handling and scoring |

The data hashes identify the tables; `behavior_version` identifies what is
done with them, so that a code change that moves a feature set or a distance
moves the fingerprint too. Version 1 of the payload had no such field, and a
fix to the resolver or a scorer left the fingerprint of results it changed
identical. The number is bumped with every change that alters a golden
fixture: `tools/regenerate_golden.py` records it in
`tests/golden/behavior.tsv` beside a hash of the fixtures, refuses to record
changed fixtures under an unchanged number, and with `--check` (run in CI)
fails when the two disagree. Releases up to 0.10.0 are behavior version 1.

The digest is the lowercase hexadecimal SHA-256 of the full payload. Both
should be stored: the digest serves as a compact join key, and the payload
makes it inspectable.

For a compiled model, `model_sha256` covers every file in
`data/models/<system>/` except `provenance.json`, in filename order, each
delimited by its name, so that correcting a citation does not change the
identity. For a runtime model, `model_version` is `runtime-model-v1` and
`model_sha256` covers the model name and a canonical inventory: rows ordered by
grapheme (of rows sharing a grapheme, the first), each feature set sorted. A
reordering of the runtime model text therefore leaves the identity unchanged.

## Scope boundary

This is a system fingerprint, not a fingerprint of a computation. It does not
include:

- a non-default weight preset or the resolved weights;
- the caller's tokenization or sequence-alignment policy;
- the Unicode version of the normalization tables (`mk_unicode_version`,
  `merkmal.UNICODE_VERSION`).

These belong to the provenance of the result and must be recorded alongside
the digest.

The resolver, tone and comparison policies, the scorer and the geometry name
are fixed identifiers compiled into the library, not hashes of the code that
implements them. The payload therefore detects a change to the data files, but
not a change to that code made without a change of identifier. Typological
sampling is outside the scope of a system identity.

## Operation fingerprints

Python also provides `operation_fingerprint(...)`, which composes the system
payload with caller-selected settings: the weight preset, tokenization, tone,
comparison and missingness policies, a geometry loaded with `load_geometry`
(by name, version and hash), and any further JSON-serializable options, with
keys sorted. Its payload begins `schema=merkmal-operation-fingerprint-v1`.
This digest, rather than the system digest, is the appropriate key for cached
distances and derived results.

## Related interfaces

For valued systems, `compatibility_dissimilarity(...)` is an alias of
`distance_with_coverage(...)` that names its semantics: a dissimilarity over
the dimensions both segments define, not a metric on a fixed space.
`fixed_space_distance(...)` is an experimental alternative: the mean absolute
difference between the two fixed-width feature vectors. It treats the vector's
zero state as neutral or unspecified and is unsuitable where another treatment
of missing values is required.

Python's `Comparison` result is a named tuple of `score`, `coverage` and
`comparability`.

## Use with stored results

A consumer that stores results computed with this library should persist the
payload and digest with them: for example, with calibration constants, fitted
thresholds and detection outputs, or beside the feature-system name in an
exported model, together with its tokenization, alignment and non-default
scoring settings. Results whose fingerprints differ should not be compared,
merged or reused from a cache without a stated reason why the difference does
not affect the question, and should otherwise be labelled as differing.
