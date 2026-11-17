#!/usr/bin/env sh
# Fail if any first-party C file is not formatted by the repository's
# .clang-format. Generated tables are excluded by .clang-format-ignore.
#
# Usage: tools/check_format.sh          check (CI)
#        tools/check_format.sh --fix    reformat in place
#
# Formatting is mechanical (STYLE.md): run --fix in a commit of its own, never
# mixed with a functional change.
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root"
if ! command -v clang-format >/dev/null 2>&1; then
    echo "check_format: clang-format not found; install it (e.g. apt-get install clang-format)" >&2
    exit 127
fi
# Major versions of clang-format can lay out the same code differently, so a
# failure with no code change usually means a different version: say which
# one decided.
echo "check_format: $(clang-format --version)"

files=$(git ls-files '*.c' '*.h' | grep -v '^src/generated/')
if [ "${1:-}" = "--fix" ]; then
    # shellcheck disable=SC2086
    clang-format -i $files
    echo "check_format: reformatted; commit this on its own"
else
    # shellcheck disable=SC2086
    if ! clang-format --dry-run --Werror $files; then
        echo "check_format: the files above differ from .clang-format." >&2
        echo "check_format: if no code changed, this clang-format version formats differently;" >&2
        echo "check_format: run tools/check_format.sh --fix and commit that alone." >&2
        exit 1
    fi
    echo "check_format: all first-party C files are formatted"
fi
