#!/usr/bin/env sh
# Build and run the lookup benchmark against the library sources.
#
# It is built here rather than as a CMake target because mk_inventory_find is
# internal, and because a benchmark that needs a configured build directory is
# a benchmark nobody runs.
#
# Usage: bench/bench_lookup.sh [build_dir]

set -eu

build_dir="${1:-build/bench}"
cc="${CC:-cc}"
mkdir -p "$build_dir"

root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root"

$cc -std=c99 -O2 -DNDEBUG -DMK_HAVE_UTF8PROC=0 \
    -Iinclude -Isrc \
    bench/bench_lookup.c src/*.c src/generated/*.c \
    -o "$build_dir/bench_lookup"

"$build_dir/bench_lookup"
