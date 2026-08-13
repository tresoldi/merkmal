#!/usr/bin/env sh
set -eu

if ! command -v emcc >/dev/null 2>&1; then
    echo "error: emcc is required for the WebAssembly smoke test" >&2
    exit 127
fi
if ! command -v node >/dev/null 2>&1; then
    echo "error: node is required for the WebAssembly smoke test" >&2
    exit 127
fi

build_dir="${1:-build/wasm-smoke}"
mkdir -p "$build_dir"

emcc \
    -std=c99 \
    -DMK_HAVE_UTF8PROC=0 \
    -Iinclude \
    -Isrc \
    src/*.c \
    src/generated/*.c \
    tests/wasm/smoke.c \
    -sENVIRONMENT=node \
    -sEXIT_RUNTIME=1 \
    -sFILESYSTEM=0 \
    -o "$build_dir/merkmal-wasm-smoke.js"

node "$build_dir/merkmal-wasm-smoke.js"
