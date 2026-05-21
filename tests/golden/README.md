# Golden Test Data

Cross-language parity expectations for the merkmal feature systems.
Both the Python test suite and the Go test suite validate against
these files.

## Regenerating

From the repo root:

```sh
source ~/.venvs/new_chl/bin/activate
python tests/generate_golden.py
```

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
