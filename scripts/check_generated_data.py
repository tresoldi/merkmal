"""Check that the committed C data matches the source data files."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    """Regenerate the C data in a temporary file and compare it with HEAD."""
    root = Path(__file__).resolve().parents[1]
    committed = root / "src" / "generated" / "builtin_data.c"

    with tempfile.TemporaryDirectory() as directory:
        generated = Path(directory) / "builtin_data.c"
        subprocess.run(
            [
                sys.executable,
                str(root / "tools" / "generate_c_data.py"),
                "--output",
                str(generated),
            ],
            check=True,
        )
        if generated.read_bytes() != committed.read_bytes():
            print(
                "Generated data is out of date. Run "
                "python tools/generate_c_data.py.",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
