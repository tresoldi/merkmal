#!/usr/bin/env sh
# Run the static analyzers over the first-party sources.
#
# Two analyzers, because they find different things: GCC's -fanalyzer is
# strongest on allocation and NULL flow, Clang's is strongest on dead stores and
# path-sensitive logic.
#
# Accepted findings, deliberately not fixed:
#
#   src/resolver.c  deadcode.DeadStores on `p` in two diacritic match arms.
#     Each arm ends `p += <width>; break;` so that every arm reads the same way;
#     the last one's advance is redundant only because it happens to be last.
#     Uniformity is worth more than the two lines.
#
# Anything else is a regression and should be fixed or added here with a reason.

set -eu

root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root"

status=0
flags="-std=c99 -Iinclude -Isrc -DMK_HAVE_UTF8PROC=0"

if command -v gcc >/dev/null 2>&1; then
    printf '## gcc -fanalyzer\n'
    for source in src/*.c; do
        # shellcheck disable=SC2086
        gcc $flags -fanalyzer -fsyntax-only "$source" 2>&1 |
            grep -E 'warning:|error:' || true
    done
    printf '\n'
else
    printf '## gcc -fanalyzer: gcc not available, skipped\n\n'
fi

if command -v clang >/dev/null 2>&1; then
    printf '## clang --analyze\n'
    for source in src/*.c; do
        # shellcheck disable=SC2086
        clang --analyze -Xanalyzer -analyzer-output=text $flags "$source" -o /dev/null 2>&1 |
            grep -E '^[^ ]+:[0-9]+:[0-9]+: warning' |
            grep -v "resolver.c.*Value stored to 'p' is never read" || true
    done
    printf '\n'
else
    printf '## clang --analyze: clang not available, skipped\n\n'
fi

# Report, do not gate: the accepted-findings filter above is the gate, and it is
# narrow enough that a new finding shows up as output.
printf 'Done. Any output above other than the section headers is a new finding.\n'
exit $status
