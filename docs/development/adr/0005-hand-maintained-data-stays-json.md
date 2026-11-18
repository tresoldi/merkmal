# 0005. Hand-maintained data stays JSON

## Context

The house standard prefers TOML for human-written files, partly because it
allows comments. merkmal's hand-maintained structured data is JSON:
`data/geometries/*.json`, `data/models/*/model.json` and `provenance.json`,
`data/diacritics/*.json` and `data/typologies/*.json`. Inventories are TSV.

## Decision

This project departs from the default: the files stay JSON.

- `tools/validate_models.py` checks the geometry and model files (required
  fields, identifiers, coverage, provenance), and the generators refuse what
  they cannot read. There are no JSON Schemas: the validator is the one
  statement of what a valid file is, so it cannot disagree with another.
- The semantic fingerprint hashes the source files' bytes (`geometry_sha256`,
  `diacritics_sha256`, `model_sha256`; docs/method/semantic-fingerprint.md), so
  converting them would change every system's fingerprint without any change
  in what it computes, and break the identity of stored results.
- The files are edited rarely, and their explanations belong in the
  provenance manifests and docs, which already hold them.

## Consequences

- New human-written configuration files, as opposed to these data tables,
  follow the house default and are TOML.
- A file that needs inline explanation records it in its `description` or
  provenance fields.
