# 0007. Scoring policy numbers are data

## Context

Some scoring choices are policy rather than geometry: what a tone costs
against a segment, and how a cluster's parts are weighted against each other
and against the whole. Written into C, a change to one of them is a code edit
that a reviewer has to recognize as a change in results.

## Decision

These numbers live in the geometry file, `geometries/clements-hume.json`:
`tier_policy.cross_tier_cost`, and `cluster_policy` (nucleus and offglide
shares, component and segment shares, the length penalty). The generator
compiles them into the tables; the rules that apply them stay in C
(`src/system.c`, `src/cluster.c`).

## Consequences

- Changing a policy number is a data change with a diff, under the data
  release rules, and it changes `geometry_sha256` in the semantic fingerprint.
- A later scorer can carry its own policy without disturbing this one.
