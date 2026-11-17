# 0001. The C API is the canonical interface

## Context

merkmal is used from C, Python, the browser (WebAssembly) and the command
line. If any binding reaches past the public header into internal symbols, the
public API stops being the whole contract, and an internal change can break a
binding without any test of the public API noticing.

## Decision

`include/merkmal.h` is the only interface to the computation. Every binding
and adapter is a thin wrapper over it: `python/src/merkmal_module.c` and
`web/merkmal_wasm.c` include `merkmal.h` and nothing from `src/`. Names
spelled `mk_` are public; everything internal is `mki_`. Build identity the
bindings need (version, data profile, Unicode version) is exposed through the
public header too.

## Consequences

- `scripts/check_public_symbols.sh` (the `public_symbols` test) fails if the
  library exports anything outside the public set.
- A feature a binding needs is first a public C function, with its contract in
  the header and a C test.
- Tests of internal modules link `merkmal_internal`, a static build of the
  same sources that is never installed.
