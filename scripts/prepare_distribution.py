#!/usr/bin/env python3
"""Turn a checkout into the source tree of one merkmal distribution.

`merkmal` is the full distribution and needs no preparation. `merkmal-cc-by`
carries only the built-in tables whose terms have no share-alike or
non-commercial clause -- today `descriptive` and `distinctive`, CC-BY-4.0 --
for users who cannot accept PHOIBLE's CC-BY-SA-3.0 or P-base's
CC-BY-NC-SA-4.0. It is the same code and the same `merkmal` import package; the
two distributions cannot be installed side by side.

Preparing it **rewrites the working tree in place**, so run it in a throwaway
checkout (CI does):

    python scripts/prepare_distribution.py cc-by
    python -m build --sdist --wheel

It is not enough to compile with the cc-by profile. The full table file shares
one string pool across systems, and an sdist carrying it carries the excluded
data whatever the build selects. So the script:

1. replaces src/generated/builtin_data.c with the cc-by table and removes the
   profile directory;
2. removes the excluded systems' model directories;
3. sets the package name, license expression and description in
   pyproject.toml and setup.py;
4. regenerates NOTICE from the manifests that remain;
5. says at the top of python/README.md which distribution this is.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import generate_c_data  # noqa: E402

DISTRIBUTIONS = {
    "cc-by": {
        "name": "merkmal-cc-by",
        "license": "MIT AND CC-BY-4.0",
        "summary": (
            "merkmal without the share-alike and non-commercial tables: "
            "phonological feature systems for historical linguistics"
        ),
    },
}

FULL_LICENSE = "MIT AND CC-BY-4.0 AND CC-BY-SA-3.0 AND CC-BY-NC-SA-4.0"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path.relative_to(ROOT)}: expected one {old!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def prepare(profile: str) -> None:
    spec = DISTRIBUTIONS[profile]
    every = generate_c_data.CATEGORICAL_SYSTEMS + generate_c_data.VALUED_SYSTEMS
    kept = set(generate_c_data.profile_systems(profile, every))
    excluded = [name for name in every if name not in kept]

    generated = ROOT / "src" / "generated"
    table = (generated / profile / "builtin_data.c").read_text(encoding="utf-8")
    table = table.replace('#include "../builtin_data.h"', '#include "builtin_data.h"', 1)
    (generated / "builtin_data.c").write_text(table, encoding="utf-8")
    shutil.rmtree(generated / profile)

    for name in excluded:
        shutil.rmtree(ROOT / "models" / name)

    pyproject = ROOT / "pyproject.toml"
    replace_once(pyproject, 'name = "merkmal"', f'name = "{spec["name"]}"')
    replace_once(pyproject, f'license = "{FULL_LICENSE}"', f'license = "{spec["license"]}"')
    replace_once(
        pyproject,
        'description = "Standalone phonological feature systems for historical linguistics"',
        f'description = "{spec["summary"]}"',
    )
    replace_once(ROOT / "setup.py", f'license="{FULL_LICENSE}"', f'license="{spec["license"]}"')
    replace_once(
        ROOT / "MANIFEST.in", f"include src/generated/{profile}/builtin_data.c\n", ""
    )

    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_notice.py")], check=True)

    readme = ROOT / "python" / "README.md"
    readme.write_text(
        f"> **This is `{spec['name']}`**, the distribution of merkmal that carries "
        f"only {', '.join(f'`{name}`' for name in sorted(kept))} "
        f"({spec['license']}). It leaves out "
        f"{', '.join(f'`{name}`' for name in excluded)}, whose share-alike or "
        "non-commercial terms some users cannot accept. Install `merkmal` for "
        "every system; the two provide the same `merkmal` package and cannot be "
        "installed together. `merkmal.DATA_PROFILE` says which one is loaded.\n\n"
        + readme.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    print(f"prepared {spec['name']}: kept {sorted(kept)}, removed {excluded}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("profile", choices=sorted(DISTRIBUTIONS))
    args = parser.parse_args()
    prepare(args.profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
