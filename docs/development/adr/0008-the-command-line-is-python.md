# 0008. The command line is the Python package's

## Context

The house standard prefers a command line over the C core, shipped as a
single executable where practical. merkmal's `merkmal` command is the Python
package's (`python/merkmal/cli.py`), installed by pip.

## Decision

The command line stays in the Python package for now. It calls the C library
through the extension, so the computation is still the C core's (ADR 0001).
Its stable contract is the `--json`, `--jsonl` and `--tsv` modes and the exit
status (python/README.md, Command line); the default human output may change.

## Consequences

- Using the command line needs Python; the C library alone has no executable.
- A C executable over `merkmal.h` remains possible, and would have to keep the
  same subcommands, modes and records so that scripts work with either.
