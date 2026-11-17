# 0004. MIT for code, upstream terms for data

## Context

The house standard's default license is GPL-3.0. merkmal was published at
0.9.0 under MIT for its code, and it redistributes data tables whose upstream
licenses it does not choose: CC-BY-4.0 (descriptive and distinctive),
CC-BY-SA-3.0 (PHOIBLE) and CC-BY-NC-SA-4.0 (the four P-base systems); the
classfeat model's data is MIT.

## Decision

This project departs from the default. The code stays MIT, and each data table
keeps its upstream terms. The package declares the combined SPDX expression
`MIT AND CC-BY-4.0 AND CC-BY-SA-3.0 AND CC-BY-NC-SA-4.0`. For users who cannot
accept share-alike or non-commercial terms, the `cc-by` data profile builds
without those tables.

## Consequences

- No license or license expression changes without the copyright holder's
  explicit decision, recorded in a new ADR.
- `NOTICE` is generated from the provenance manifests
  (`tools/generate_notice.py --check` in CI), and the expression must agree
  in `pyproject.toml`, `setup.py`, `NOTICE` and the README
  (docs/development/release-policy.md).
