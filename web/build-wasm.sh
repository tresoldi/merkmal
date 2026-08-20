#!/usr/bin/env bash
#
# Builds merkmal for the browser. Requires the Emscripten SDK:
#
#   source ~/emsdk/emsdk_env.sh
#   ./web/build-wasm.sh
#
# The artifacts (merkmal.js, merkmal.wasm) are committed, so rerun this before
# deploying the page after any change under src/ or include/. This records the
# sources it built from in web/BUILD_INFO; a stale artifact cannot reach the
# deployed page unnoticed.
#
# Links with -sFILESYSTEM=0: the built-in models are compiled in.
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_dir="$(cd "$script_dir/.." && pwd)"
build_dir="$repo_dir/build/wasm"

if ! command -v emcc >/dev/null 2>&1; then
    echo "build-wasm: emcc not found; run 'source ~/emsdk/emsdk_env.sh' first" >&2
    exit 2
fi

version=$(sed -n '/^project/,/)/{s/.*VERSION \([0-9][0-9.]*\).*/\1/p;}' "$repo_dir/CMakeLists.txt" | head -1)
: "${version:=0.0.0}"

emcmake cmake -S "$repo_dir" -B "$build_dir" \
    -DCMAKE_BUILD_TYPE=Release \
    -DMERKMAL_BUILD_TESTS=OFF \
    -DMERKMAL_BUILD_EXAMPLES=OFF \
    -DMERKMAL_REQUIRE_UTF8PROC=OFF \
    -DMERKMAL_USE_UTF8PROC=OFF > /dev/null

cmake --build "$build_dir" -j"$(nproc)" > /dev/null

emcc \
    -O3 \
    -std=c99 \
    -Wall -Wextra -Wpedantic -Wconversion \
    -Wshadow -Wstrict-prototypes -Wmissing-prototypes -Wcast-qual \
    -Werror \
    -DMK_WEB_VERSION="\"$version\"" \
    "$script_dir/merkmal_wasm.c" \
    "$build_dir/libmerkmal.a" \
    -I"$repo_dir/include" \
    -sFILESYSTEM=0 \
    -sMODULARIZE=1 \
    -sEXPORT_NAME=createMerkmal \
    -sALLOW_MEMORY_GROWTH=1 \
    -sENVIRONMENT=web,node \
    -sEXPORTED_FUNCTIONS='["_merkmal_list_systems","_merkmal_grapheme_features","_merkmal_segment_distance","_merkmal_tokenize","_merkmal_distance_matrix","_merkmal_normalize","_merkmal_diagnose","_merkmal_register_model","_merkmal_version","_merkmal_free","_malloc","_free"]' \
    -sEXPORTED_RUNTIME_METHODS='["ccall","cwrap","UTF8ToString","stringToNewUTF8"]' \
    -o "$script_dir/merkmal.js"

commit="$(git -C "$repo_dir" rev-parse --short HEAD 2>/dev/null || echo unknown)"
printf 'git_commit %s\n' "$commit" > "$script_dir/BUILD_INFO"

echo "built merkmal $version ($commit):"
ls -lh "$script_dir/merkmal.js" "$script_dir/merkmal.wasm" | awk '{print "  " $9 "  " $5}'
echo
echo "preview: cd web && python3 -m http.server 8080"
