#!/usr/bin/env sh
# Record the compiled footprint of the library, with the generated data broken
# out separately.
#
# The generated data dominates: it is mostly arrays of pointers into a small
# pool of strings, and every one of those pointers is a relocation. That costs
# bytes in the .wasm payload and work at instantiate time, so the relocation
# count is tracked as a first-class number alongside the section sizes.
#
# Usage: bench/bench_footprint.sh [build_dir]
# Writes a report to stdout. Compare against bench/baseline.txt.

set -eu

build_dir="${1:-build/footprint}"
cc="${CC:-cc}"
mkdir -p "$build_dir"

root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root"

printf '# merkmal footprint report\n'
printf '# compiler: %s\n' "$($cc --version 2>/dev/null | head -1)"
printf '# flags: -std=c99 -O2 -DNDEBUG -DMK_HAVE_UTF8PROC=0\n'
printf '\n'

# --- native objects -------------------------------------------------------

printf '## native objects (-O2 -DNDEBUG)\n\n'
printf '%-28s %10s %10s %10s\n' 'object' 'text' 'rodata' 'relocs'

total_text=0
total_rodata=0
total_relocs=0

for source in src/*.c src/generated/*.c; do
    object="$build_dir/$(echo "$source" | tr '/' '_').o"
    $cc -std=c99 -O2 -DNDEBUG -DMK_HAVE_UTF8PROC=0 \
        -Iinclude -Isrc -c "$source" -o "$object"

    text=$(size -A "$object" | awk '$1 == ".text" { print $2 }')
    rodata=$(size -A "$object" | awk '$1 ~ /^\.rodata/ { sum += $2 } END { print sum + 0 }')
    if command -v readelf >/dev/null 2>&1; then
        relocs=$(readelf -r "$object" 2>/dev/null | grep -c '^0' || true)
    else
        relocs='n/a'
    fi
    : "${text:=0}"

    printf '%-28s %10s %10s %10s\n' "$(basename "$source")" "$text" "$rodata" "$relocs"

    total_text=$((total_text + text))
    total_rodata=$((total_rodata + rodata))
    case "$relocs" in
        ''|*[!0-9]*) ;;
        *) total_relocs=$((total_relocs + relocs)) ;;
    esac
done

printf '%-28s %10s %10s %10s\n' 'TOTAL' "$total_text" "$total_rodata" "$total_relocs"
printf '\n'

# The string content the pointer tables refer to, for scale: the gap between
# this and rodata is what the compaction work is aimed at.
pool=$(size -A "$build_dir/src_generated_builtin_data.c.o" |
    awk '$1 ~ /^\.rodata\.str/ { sum += $2 } END { print sum + 0 }')
printf 'generated string content: %s bytes\n' "$pool"
printf '\n'

# --- WebAssembly ----------------------------------------------------------

printf '## WebAssembly (emcc, fallback Unicode path)\n\n'

if ! command -v emcc >/dev/null 2>&1; then
    printf 'emcc not available; skipped\n'
    exit 0
fi

emcc \
    -std=c99 \
    -O2 \
    -DNDEBUG \
    -DMK_HAVE_UTF8PROC=0 \
    -Iinclude \
    -Isrc \
    src/*.c \
    src/generated/*.c \
    tests/wasm/smoke.c \
    -sENVIRONMENT=node \
    -sEXIT_RUNTIME=1 \
    -sFILESYSTEM=0 \
    -o "$build_dir/footprint.js" >/dev/null 2>&1

wasm_bytes=$(wc -c < "$build_dir/footprint.wasm")
js_bytes=$(wc -c < "$build_dir/footprint.js")
printf 'footprint.wasm: %s bytes\n' "$wasm_bytes"
printf 'footprint.js:   %s bytes\n' "$js_bytes"

if command -v wasm-objdump >/dev/null 2>&1; then
    printf '\nsection sizes:\n'
    wasm-objdump -h "$build_dir/footprint.wasm" | sed 's/^/  /'
else
    printf '(wasm-objdump not available; section breakdown skipped)\n'
fi

if command -v node >/dev/null 2>&1; then
    # Compile/validate time for the module bytes, measured inside one process.
    # Timing `node footprint.js` instead would measure node's own startup, which
    # is an order of magnitude larger and varies more than the signal.
    printf '\n'
    node -e '
        const fs = require("fs");
        const bytes = fs.readFileSync(process.argv[1]);
        let best = Infinity;
        for (let i = 0; i < 10; i++) {
            const t = process.hrtime.bigint();
            new WebAssembly.Module(bytes);
            const ms = Number(process.hrtime.bigint() - t) / 1e6;
            if (ms < best) best = ms;
        }
        process.stdout.write(
            "compile time (best of 10): " + best.toFixed(1) + " ms\n");
    ' "$build_dir/footprint.wasm"
fi
