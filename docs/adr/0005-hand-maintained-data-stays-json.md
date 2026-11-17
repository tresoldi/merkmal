# 0005. Hand-maintained data stays JSON

## Context

The house standard prefers TOML for human-written files, partly because it
allows comments. merkmal's hand-maintained structured data is JSON:
`geometries/*.json`, `models/*/model.json` and `provenance.json`,
`diacritics/*.json` and `typologies/*.json`. Inventories are TSV.

## Decision

This project departs from the default: the files stay JSON.

- They are validated against published JSON Schemas (`schemas/*.json`) by
  `scripts/validate_models.py`, and the schemas are the contract.
- The semantic fingerprint hashes the source files' bytes (`geometry_sha256`,
  `diacritics_sha256`, `model_sha256`; docs/semantic-fingerprint.md), so
  converting them would change every system's fingerprint without any change
  in what it computes, and break the identity of stored results.
- The files are edited rarely, and their explanations belong in the
  provenance manifests and docs, which already hold them.

## Consequences

- New human-written configuration files, as opposed to these data tables,
  follow the house default and are TOML.
- A file that needs inline explanation records it in its `description` or
  provenance fields.
