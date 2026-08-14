#!/usr/bin/env sh
# Prove that the built library exports the public API and nothing else.
#
# C has one symbol namespace, so a static consumer sees every external name in
# the archive whether or not it is part of the contract. For a long time 66 of
# the 97 names in libmerkmal.a were internal -- mki_resolve, mki_streq,
# mki_parse_model_text and the compiled tables -- and they were spelled mk_,
# exactly like the 31 that are promises. Nothing distinguished the two, so
# STYLE.md's claim that mk_ meant "public" was true only by intention.
#
# The rule this enforces: mk_ is the public contract, mki_ is internal. Adding a
# cross-module helper called mk_something is now a test failure rather than a
# silent widening of the API.
#
# Usage: check_public_symbols.sh <path-to-libmerkmal.a>

set -eu

if [ $# -ne 1 ]; then
    echo "usage: $0 <path-to-libmerkmal.a>" >&2
    exit 2
fi

archive=$1
root=$(cd "$(dirname "$0")/.." && pwd)
header="$root/include/merkmal.h"

if [ ! -f "$archive" ]; then
    echo "no such archive: $archive" >&2
    exit 2
fi

if ! command -v nm >/dev/null 2>&1; then
    echo "nm not available; skipping the public-symbol check" >&2
    exit 0
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# Declared: every mk_-prefixed name the public header names.
grep -oE '\bmk_[a-z0-9_]+\(' "$header" | tr -d '(' | sort -u > "$work/declared"

# Exported: every defined external symbol in the archive. T/D/R/B/W covers
# functions, mutable and read-only data, BSS, and weak definitions.
#
# Leading underscores are dropped from consideration: that namespace is
# reserved to the implementation, and a sanitized build puts real symbols
# there -- AddressSanitizer emits an __odr_asan indicator per global, which is
# instrumentation, not API. First-party code may not define such a name, so
# nothing of ours hides behind this.
nm -g --defined-only "$archive" |
    awk '$2 ~ /^[TDRBW]$/ { print $3 }' |
    grep -v '^_' | sort -u > "$work/exported"

grep '^mk_' "$work/exported" > "$work/exported_public" || true
grep -v '^mki\?_' "$work/exported" > "$work/unprefixed" || true

status=0

if [ -s "$work/unprefixed" ]; then
    echo "exported symbols carrying neither the mk_ nor the mki_ prefix:" >&2
    sed 's/^/  /' "$work/unprefixed" >&2
    status=1
fi

undeclared=$(comm -23 "$work/exported_public" "$work/declared")
if [ -n "$undeclared" ]; then
    echo "exported as public API but not declared in include/merkmal.h:" >&2
    echo "$undeclared" | sed 's/^/  /' >&2
    echo "rename these to mki_ if they are internal." >&2
    status=1
fi

missing=$(comm -13 "$work/exported_public" "$work/declared")
if [ -n "$missing" ]; then
    echo "declared in include/merkmal.h but not exported by the library:" >&2
    echo "$missing" | sed 's/^/  /' >&2
    status=1
fi

if [ "$status" -eq 0 ]; then
    echo "public surface: $(wc -l < "$work/declared" | tr -d ' ') mk_ symbols, \
$(grep -c '^mki_' "$work/exported" || true) internal mki_ symbols"
fi

exit "$status"
