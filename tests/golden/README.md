# Golden test data

Expected outputs of the feature systems and the geometry, replayed by the C test
suite. A test fails on any difference between a fixture and the library's
output.

| Files | Replayed by | Content |
| --- | --- | --- |
| `{system}_features.tsv` | `tests/c/test_golden_features.c` | Features of each grapheme |
| `{system}_distances.tsv` | `tests/c/test_golden_distances.c` | Distance of each grapheme pair |
| `geometry_distances.tsv` | `tests/c/test_geometry.c` | Tree distance between two features |
| `geometry_sound_distances.tsv` | `tests/c/test_geometry.c` | Distance between two feature sets |
| `geometry_weighted_distances.tsv` | `tests/c/test_geometry.c` | The same, under each weight preset |
| `geometry_cases.tsv` | `tests/c/test_geometry.c` (input) | The named feature sets the two files above refer to |
| `contrast_baseline.tsv` | `tools/contrast_baseline.py --check` | Declared pairs of distinct graphemes at distance zero |
| `*_full.tsv`, `classfeat_*.tsv`, `*_partitions.tsv` | none | See [Fixtures not replayed](#fixtures-not-replayed) |

`{system}` is each built-in system: `descriptive`, `distinctive`, `phoible`,
`pbase-hc`, `pbase-jfh`, `pbase-spe` and `pbase-uftc`.

## Regenerating

Fixtures are rewritten only for a change to model data or scoring that is meant
to change them, and the diff is then reviewed as data. All active fixtures are
produced by one script, through the installed Python package:

```sh
python -m pip install -e . --no-build-isolation
python tools/regenerate_golden.py --check    # report differences, write nothing
python tools/regenerate_golden.py            # rewrite the fixtures
```

The C tests only read the fixtures, so no test writes the values it is checked
against, and the check needs no CMake build. The script takes the list of
graphemes and pairs from the existing files and rewrites only the values, so
coverage does not change silently. A row that no longer resolves is reported and
dropped; that is a change of contract and is recorded in CHANGELOG.md.

`src/generated/builtin_data.c` is generated separately, by
`python tools/generate_c_data.py`, which does not touch these fixtures.

### Adding coverage

Append a row with any placeholder in the value column and regenerate; the value
is filled in, and the C tests replay the row from then on:

```sh
printf 'n-feats\tt-feats\t0\n' >> tests/golden/geometry_sound_distances.tsv
python tools/regenerate_golden.py
```

A `geometry_*` row names feature sets, not graphemes. A new set is first defined
in `geometry_cases.tsv`.

## Fixtures not replayed

`{system}_features_full.tsv`, `{system}_distances_full.tsv` and the
`classfeat_*` files were produced by the Python implementation that preceded
the C library (see the repository history before release 0.9.0). No test
replays them, and `tools/regenerate_golden.py` does not rewrite them, since
rewriting them from the C library would remove the record they keep. For most
graphemes of the categorical and PHOIBLE systems they differ from the output of
the current library; they are a record, not expectations.

`descriptive_partitions.tsv` and `phoible_partitions.tsv` assign graphemes to
classes at four levels (`prosody`, `coarse`, `medium`, `fine`). No test or tool reads
them.

## `contrast_baseline.tsv`

Not a parity fixture. It lists every pair of distinct graphemes that scores
exactly zero, with a status and a reason, so that such a pair is declared
rather than discovered; for the valued systems, whose source tables do not
distinguish many segments, it records a count with examples. `python
tools/contrast_baseline.py --check` fails if an undeclared zero appears, if a
feature label can no longer affect any distance, or if a scored dimension can
no longer be reached by any grapheme.

## File formats

All files are UTF-8, tab-separated, with a header row.

### `{system}_features.tsv`

| Column | Description |
| --- | --- |
| GRAPHEME | IPA grapheme |
| FEATURES | Sorted feature strings, separated by `\|` |

In categorical systems a feature is a label (`vowel|open|front`); in valued
systems it is a `name=value` pair (`syllabic=+|voice=-`).

### `{system}_distances.tsv`

| Column | Description |
| --- | --- |
| GRAPHEME_A | First IPA grapheme |
| GRAPHEME_B | Second IPA grapheme |
| DISTANCE | `merkmal.distance(a, b, system=...)`, to 10 decimal places (a few rows at full `repr` precision) |

The archived `classfeat_distances*.tsv` files hold a different quantity, the
`grapheme_cost` of the earlier Python implementation (a blend of class and
feature costs).

### `geometry_cases.tsv`

Input, not expectation: the named feature sets scored by
`geometry_sound_distances.tsv` and `geometry_weighted_distances.tsv`, read by
both the generating script and the C test.

| Column | Description |
| --- | --- |
| NAME | Case name, referred to by SET_A and SET_B |
| FEATURES | Feature strings, separated by `\|` |

### `geometry_distances.tsv`

| Column | Description |
| --- | --- |
| FEATURE_A | Feature name |
| FEATURE_B | Feature name |
| DISTANCE | Number of edges between the two features in the geometry tree (integer) |

### `geometry_sound_distances.tsv`

| Column | Description |
| --- | --- |
| SET_A | Named feature set |
| SET_B | Named feature set |
| DISTANCE | Normalized distance between the two sets (float) |

### `geometry_weighted_distances.tsv`

| Column | Description |
| --- | --- |
| PRESET | Weight preset name, or `None` for the default weights |
| SET_A | Named feature set |
| SET_B | Named feature set |
| DISTANCE | Distance under the given preset |
