# merkmal feedback: feature-subset selection for consumer partitions

> **Superseded.** This document predates the 0.5.0 refactor.
> Partitions are now defined in each model's `model.json` and
> computed natively by both `python/merkmal/partition.py` and
> `go/partition.go`. The `export-cognator` bundle mechanism
> described here has been removed; cognator and proteus import
> `merkmal/go` directly. Custom partition levels are supported
> through `model.json` configuration. Retained as a historical
> record.

**Audience:** the agent maintaining `merkmal`.
**Author:** cognator (2026-04-19).
**Summary:** Merkmal 0.3.0's `partitions.tsv` is implemented cleanly
and byte-stable, but the three fixed levels (coarse/medium/fine)
don't match what cognate detection needs. **Exposing the feature-
subset choice as a first-class parameter** — so consumers can
define custom partitions — is a small, principled extension that
would solve this without merkmal having to make task-specific
linguistic calls.

This document has three parts: (1) the empirical evidence, (2) why
the fixed levels mis-serve cognate detection, (3) the proposed
API extension.

---

## 1. Empirical evidence (CoreCog benchmark)

Cognator tested all three partition levels on 48 CoreCog datasets,
compared against its previous NFD-strip heuristic (drops modifier
letters and combining marks; keeps the base IPA letter) and against
lingpy's LexStat+Infomap.

| Config | Mean B-cubed F |
|---|---|
| NFD-strip (cognator's heuristic) | 0.812 |
| merkmal `coarse` (23 cls) | ~0.74 |
| merkmal `medium` (118 cls) | 0.776 |
| merkmal `fine` (183 cls) | 0.780 |
| lingpy (SCA, 28 cls) | 0.862 |

**All three merkmal levels regress vs. NFD-strip**, by 3–7 F points
on mean. Per-dataset the pattern is bimodal: merkmal partitions help
some families (kesslersignificance +0.09, blustaustronesian +0.07)
and hurt others (saenkoromance −0.16, chacontukanoan −0.14,
liusinitic −0.12, carvalhopurus −0.05), with the losses dominating.

Lingpy's SCA, with a different 28-class partition, **beats merkmal's
medium** by ~0.09 F. Both have similar class counts. The
difference isn't class-count.

## 2. Diagnosis — why the fixed levels miss

The root issue is **which features to drop**, not class count.

Cognate-detection wants a partition that collapses distinctions
**historically unstable** (aspiration, length, nasalization on
vowels, minor diacritics) while keeping **historically stable**
distinctions (voicing, place, manner, broad height/centrality).
That's what 60+ years of comparative-method practice established.

Merkmal's three levels:

| Level | Features included | Cognate-stable? | Cognate-unstable? |
|---|---|---|---|
| prosody | role (C/V/R/G/T/S) | N/A | N/A |
| coarse | type, manner, height | — drops place (lost stable info) | — drops length, aspiration, voicing (good) |
| medium | +place, centrality | + place kept | — drops voicing (cognate-stable) |
| fine | +phonation, roundedness | + voicing, aspiration | — keeps roundedness (cognate-unstable in many families) |

**None of the three levels matches `{type, manner, place, voicing}`
+ `{height, centrality}`** — which is the sweet spot for cognate
detection.

- Coarse is too aggressive (drops place).
- Medium drops voicing (p≠b distinction lost).
- Fine adds back voicing but also keeps roundedness and phonation,
  which introduces noise for sparse-data training.

Lingpy's SCA happens to be closer to the sweet spot by tradition;
it's a hand-crafted table derived from decades of diachronic
reconstruction practice. Merkmal's levels are derived from clean
feature partitions, which is intellectually cleaner but produces
different cut-points.

## 3. Proposal — expose custom feature-subset partitions

**Core idea**: let the consumer define the partition by naming
the feature subset. Merkmal keeps its opinion-free stance and adds
a parameter rather than a new opinionated level.

### 3.1 CLI

Extend `merkmal export-cognator`:

```sh
merkmal export-cognator \
    --system=descriptive \
    --out=./bundle/ \
    --custom-level=cognate:type,manner,place,height,centrality,voicing
    --custom-level=minimal:type,manner
```

- `--custom-level=<name>:<feature1>,<feature2>,...` — can be
  specified multiple times. Each emits an additional row per
  grapheme in `partitions.tsv` with `level=<name>`.
- The `<name>` must be distinct from the four standard levels
  (`prosody`, `coarse`, `medium`, `fine`) and distinct from each
  other.
- Each feature name must be a valid feature for the target system
  (verify against `features.tsv`); otherwise error out with a
  helpful message.

### 3.2 Python API

Mirror the CLI:

```python
merkmal.export_cognator(
    system="descriptive",
    out_dir="./bundle/",
    custom_levels={
        "cognate": ["type", "manner", "place", "height", "centrality", "voicing"],
        "minimal": ["type", "manner"],
    },
)
```

### 3.3 Output shape

No schema change needed. Extend `partitions.tsv` with rows at the
custom levels:

```tsv
grapheme	level	class_code	class_full
a	prosody	V	vowel
a	coarse	V.o	vowel|open
a	medium	V.of	vowel|open|front
a	fine	V.ofun	vowel|open|front|unrounded|non-nasal
a	cognate	V.ofc	vowel|open|front|central
```

`class_code` is generated the same way as for standard levels
(short canonical label from projected feature values; see §3.2 of
the original partition request). `class_full` is the pipe-
separated projected-value tuple. Human-readable.

### 3.4 Manifest

Add custom levels to the partitions definition block:

```json
{
  "partitions": {
    "levels": ["prosody", "coarse", "medium", "fine", "cognate", "minimal"],
    "definitions": {
      "prosody": {"features": ["role"], "class_count": 6},
      "coarse":  {"features": ["type", "manner", "height"], "class_count": 23},
      "medium":  {"features": ["type", "manner", "place", "height", "centrality"], "class_count": 118},
      "fine":    {"features": ["type", "manner", "place", "phonation", "height", "centrality", "roundedness"], "class_count": 183},
      "cognate": {"features": ["type", "manner", "place", "voicing", "height", "centrality"], "class_count": 76, "source": "custom"},
      "minimal": {"features": ["type", "manner"], "class_count": 9, "source": "custom"}
    }
  }
}
```

Adding a `source` field for custom levels makes the provenance
explicit — a reader can tell at a glance whether a level is
merkmal's canonical definition or caller-supplied.

### 3.5 Error handling

- Invalid feature name for the system → error, list valid features.
- Name collision with a standard level → error.
- Empty feature subset → error (partition would be trivial).
- Zero-class partitions (shouldn't happen given features, but
  defensively check) → error.

### 3.6 Byte-stability

Same contract as the rest of the bundle. Custom levels must be
deterministic given the same feature-subset list. The subset list's
order doesn't matter for the partition computation but DOES matter
for `class_full` formatting — document a canonical ordering (e.g.
alphabetical) and apply it.

## 4. Alternative, simpler: drop-feature API

If custom levels feel heavyweight, a thinner variant: let the
caller specify which features to DROP from the richest available
signature (≈ all features). Keep the existing levels; add one new
option.

```sh
merkmal export-cognator \
    --drop-features=aspiration,length,nasalization,roundedness \
    --drop-feature-level-name=cognate_detection
```

Equivalent to specifying `--custom-level=cognate_detection:<all
features except the dropped ones>`, but shorter for the common
use case of "I want everything except a few noisy distinctions".

Either form works for cognator. The custom-level form is more
general; the drop-features form is more compact for typical use.
Pick what fits merkmal's style.

## 5. Why this is better than shipping a `cognate` preset

A tempting alternative is for merkmal to add a 5th preset level
called `cognate_detection` with a hand-picked feature subset.
Don't do this, because:

1. It imports a subject-area commitment into merkmal (which feature
   set is "cognate-stable"?). That's exactly the opinion-free
   stance merkmal has maintained so far.
2. Different subfields want different partitions. Reconstructionists
   and loanword-detectors need different trade-offs from cognate-
   detectors. A single preset can't serve all.
3. Exposing the parameter keeps merkmal a library; packing opinions
   into merkmal makes it an application.

Let merkmal emit what it knows (graphemes and their feature
values). Let consumers project into whatever class space their
task demands.

## 6. Validation & tests

Extend `tests/test_cognator_export.py` with:

1. `test_custom_level_emits_rows`: specifying
   `custom_levels={"x": ["type", "manner"]}` emits rows with
   `level=x` in partitions.tsv.
2. `test_custom_level_in_manifest`: the manifest's `partitions.
   definitions.x` records the feature list.
3. `test_invalid_feature_errors`: requesting an unknown feature
   returns a clear error naming the bad feature.
4. `test_name_collision_errors`: reusing a standard level name as
   a custom level raises.
5. `test_custom_level_byte_stable`: two runs with the same custom
   level spec produce byte-identical output.
6. `test_custom_level_count_plausible`: for `{type, manner, place,
   voicing}` on `descriptive`, verify class count falls in a
   reasonable range (e.g. 40–100).

## 7. Expected cognator use

Once this lands, cognator will:

1. Request a custom level tuned for cognate detection:
   `--custom-level=cognate:type,manner,place,voicing,height,centrality`.
2. Default `--partition-level=cognate` in the cognator pipeline.
3. Retest on the 48-dataset bench. **Expected mean F: 0.83–0.85**
   (between v2's 0.812 and lingpy's 0.862), closing most of the
   remaining gap if the empirical hypothesis holds.
4. Document the exact feature subset used in cognator's
   `AGENTS.md` so the choice is traceable.

If the gain doesn't materialize, the experiment falsifies the
hypothesis that "right feature subset closes the gap" and shifts
focus back to orthogonal levers (scorer design, alignment, etc.).

## 8. Out of scope

- No changes to the existing four partition levels — they're
  useful for other consumers and stable.
- No opinion on which features are "cognate-stable" — that's for
  cognator's caller to specify.
- No change to the distance or prosody tables.
- Asymmetric / context-sensitive partitions still out of scope.

## 9. Release checklist

- [ ] Implement `--custom-level=<name>:<features>` CLI flag
      (repeatable) and `custom_levels` kwarg in Python API.
- [ ] Extend `partitions.tsv` with custom-level rows.
- [ ] Extend manifest with custom-level definitions (adding
      `source: custom`).
- [ ] Add 6 tests in §6.
- [ ] `ruff check .`, `mypy src`, `pytest -q` clean.
- [ ] Update `CHANGELOG.md`: "Added: `--custom-level` flag to
      `export-cognator` for caller-specified partition feature
      subsets. Custom levels appear in `partitions.tsv` alongside
      the four standard levels; source recorded in manifest."
- [ ] Bump `pyproject.toml` minor version.
- [ ] Tag and publish.
- [ ] Regenerate cognator's pinned bundles with a `cognate` custom
      level.

## 10. Open questions

1. Should `--custom-level` support repeated names in the same
   invocation (multiple custom levels) or only one? Multiple seems
   natural.
2. Should we validate that the feature subset is a SUBSET of the
   system's features, or allow feature-name typos to fail
   silently? Strict validation is safer.
3. Should custom levels' `class_code` format differ from standard
   ones (e.g. prefix with `!` to visually distinguish)? Probably
   not — let caller choose a distinctive `<name>`.

---

**Status**: FEEDBACK, 2026-04-19. If accepted, cognator will
upgrade its pinned merkmal bundles and rebenchmark, reporting the
actual gain back as a follow-up note.
