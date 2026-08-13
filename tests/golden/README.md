# Golden Test Data

Parity expectations for the merkmal feature systems. The active C test suite
validates the native C slice against the relevant files here.

## Regenerating

The C tests replay `{model}_features.tsv`, `{model}_distances.tsv`, and the
three `geometry_*.tsv` files, and fail on any change. That is the point, so
regeneration is a deliberate step:

```sh
python -m pip install -e . --no-build-isolation
python scripts/regenerate_golden.py --check    # report drift, write nothing
python scripts/regenerate_golden.py            # rewrite, then read the diff
```

Every fixture is produced by that one script, through the installed Python
wrapper. The C tests are consumers only, so no test can rewrite the values it
is graded against, and the check needs no CMake build. `test_geometry` used to
carry a `--regenerate` mode and write the three `geometry_*.tsv` files itself,
which meant a stale build reported "no drift" while checking nothing.

The grapheme and pair lists come from the existing files, so values are
rewritten without silently changing what is covered. A row that no longer
resolves is reported and dropped, which is a contract change and belongs in the
changelog.

### Adding coverage

Add the row you want, with any placeholder in the value column, then
regenerate; the value is filled in and the C tests replay it from then on:

```sh
echo -e "n-feats\tt-feats\t0" >> tests/golden/geometry_sound_distances.tsv
python scripts/regenerate_golden.py
```

A `geometry_*` row names feature sets rather than graphemes. Those sets are
defined in `geometry_cases.tsv`, so a new one goes there first. They used to be
C literals inside `tests/c/test_geometry.c`, which is why coverage could only
ever shrink.

Regenerate `src/generated/builtin_data.c` from the source model data with
`python tools/generate_c_data.py`; that does not touch these fixtures.

### The `_full` and `classfeat` fixtures are archived, and they have drifted

`{model}_features_full.tsv`, `{model}_distances_full.tsv`, and the `classfeat_*`
files were produced by the pre-C Python implementation, archived under
`docs/legacy_python/scripts/`. No active test replays them, and
`scripts/regenerate_golden.py` deliberately leaves them alone: rewriting them
from the C build would destroy the record they exist to keep.

That record currently shows drift between the two implementations, independent
of any recent change:

- `g͡b` and `k͡p` resolve in the archived Python fixtures but not in the C
  implementation;
- roughly 670 of 834 rows in each `_features_full.tsv` differ.

Treat these files as history, not as expectations.

### `contrast_baseline.tsv`

Not a parity fixture. It records every pair of distinct graphemes that scores
exactly zero, with a status and reason, so that a collapse has to be declared
rather than discovered. `scripts/contrast_baseline.py --check` fails if an
undeclared one appears or if any label becomes unable to affect a distance.

## File formats

### `{model}_features.tsv`

| Column    | Description                                          |
|-----------|------------------------------------------------------|
| GRAPHEME  | IPA grapheme                                         |
| FEATURES  | Pipe-separated sorted feature strings                |

For categorical systems: features are plain names (`vowel|open|front`).
For valued systems: features are `name=state` pairs (`syllabic=+|voice=-`).

### `{model}_distances.tsv`

| Column     | Description                                         |
|------------|-----------------------------------------------------|
| GRAPHEME_A | First IPA grapheme                                  |
| GRAPHEME_B | Second IPA grapheme                                 |
| DISTANCE   | Distance as 10-decimal float                        |

Distance method varies by engine type:
- categorical: `segment_distance` (geometry tree on feature sets)
- valued: `segment_distance` (geometry-weighted valued distance)
- trained (classfeat): `grapheme_cost` (alpha-blended class + feature)

### `geometry_cases.tsv`

Input, not expectation. Names the feature sets the two `geometry_*sound*` files
score, so that both the producer and the C consumer read them from one place.

| Column   | Description                                            |
|----------|--------------------------------------------------------|
| NAME     | Case name, referenced by SET_A and SET_B               |
| FEATURES | Pipe-separated feature strings                         |

### `geometry_distances.tsv`

| Column    | Description                                          |
|-----------|------------------------------------------------------|
| FEATURE_A | Feature value name                                   |
| FEATURE_B | Feature value name                                   |
| DISTANCE  | Tree path distance (integer)                         |

### `geometry_sound_distances.tsv`

| Column   | Description                                           |
|----------|-------------------------------------------------------|
| SET_A    | Named feature set                                     |
| SET_B    | Named feature set                                     |
| DISTANCE | Normalized sound distance (float)                     |

### `geometry_weighted_distances.tsv`

| Column  | Description                                            |
|---------|--------------------------------------------------------|
| PRESET  | Node weights preset name (or "None")                   |
| SET_A   | Named feature set                                      |
| SET_B   | Named feature set                                      |
| DISTANCE| Distance under the given preset                        |
