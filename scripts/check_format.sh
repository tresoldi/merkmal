#!/usr/bin/env sh
# Fail if any first-party C file is not formatted by the repository's
# .clang-format. Generated tables are excluded by .clang-format-ignore.
#
# Usage: scripts/check_format.sh          check (CI)
#        scripts/check_format.sh --fix    reformat in place
#
# Formatting is mechanical (STYLE.md): run --fix in a commit of its own, never
# mixed with a functional change.
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root"
files=$(git ls-files '*.c' '*.h' | grep -v '^src/generated/')
if [ "${1:-}" = "--fix" ]; then
    # shellcheck disable=SC2086
    clang-format -i $files
else
    # shellcheck disable=SC2086
    clang-format --dry-run --Werror $files
fi
