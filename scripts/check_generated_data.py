"""Check that the committed C data matches the source data files."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path


def regenerate(
    root: Path, script: str, committed: Path, directory: str, extra: list[str] | None = None
) -> bool:
    generated = Path(directory) / f"{committed.parent.name}-{committed.name}"
    subprocess.run(
        [sys.executable, str(root / "tools" / script), *(extra or []), "--output", str(generated)],
        check=True,
    )
    if generated.read_bytes() != committed.read_bytes():
        print(
            f"{committed.relative_to(root)} is out of date. Run python tools/{script}.",
            file=sys.stderr,
        )
        return False
    return True


def main() -> int:
    """Regenerate the C data in a temporary directory and compare it with HEAD."""
    root = Path(__file__).resolve().parents[1]
    builtin = root / "src" / "generated" / "builtin_data.c"
    unicode_tables = root / "src" / "generated" / "unicode_data.c"
    ok = True

    with tempfile.TemporaryDirectory() as directory:
        ok &= regenerate(root, "generate_c_data.py", builtin, directory)
        ok &= regenerate(
            root,
            "generate_c_data.py",
            root / "src" / "generated" / "cc-by" / "builtin_data.c",
            directory,
            ["--profile", "cc-by"],
        )

        # The Unicode tables are a function of the interpreter's unicodedata,
        # so they can only be reproduced by an interpreter with the same
        # Unicode version. Any other interpreter skips rather than fails;
        # tests/c/test_unicode.c checks the tables against utf8proc instead.
        match = re.search(
            r'mki_unicode_version = "([^"]+)"', unicode_tables.read_text(encoding="utf-8")
        )
        recorded = match.group(1) if match else "?"
        if recorded == unicodedata.unidata_version:
            ok &= regenerate(root, "generate_unicode_data.py", unicode_tables, directory)
        else:
            print(
                f"skipping {unicode_tables.relative_to(root)}: it records Unicode "
                f"{recorded} and this interpreter has {unicodedata.unidata_version}",
                file=sys.stderr,
            )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
