# merkmal → cognator: partition-class export

> **Superseded.** This document predates the 0.5.0 refactor.
> The `export-cognator` bundle mechanism has been removed.
> Cognator now imports `merkmal/go` directly and builds
> partition tables via `merkmal.BuildPartitionTable()`. The
> feature-subset projection design proposed here was
> implemented natively in both `python/merkmal/partition.py`
> and `go/partition.go`, with partition level definitions
> stored in each model's `model.json`. Retained as a
> historical record.
>
> The repository has since moved again to a C99 core library with a
> native Python wrapper, and Go support has been retired. Treat this
> file as historical design input, not current API documentation.

**Audience:** the agent maintaining `merkmal`.
**Author:** cognator (2026-04-18).
**Goal:** extend the existing `export-cognator` bundle with a
grapheme → **partition-class** mapping at configurable granularity,
derived from merkmal's own feature system. This lets cognator
densify its correspondence-table learning (the way lingpy's SCA
reduction does) without cognator having to hand-roll a coarse-
grained grapheme taxonomy or heuristically strip diacritics.

**Important stance.** cognator has measured a ~0.05 mean-F gap to
lingpy on 48 CoreCog datasets and the dominant remaining factor is
class-level training density. A naive port of lingpy's SCA table
would close that gap, but it would also import lingpy's specific
design choices (voicing collapsed into place-class, hand-crafted
28-class partition, no granularity knob). We want merkmal's
partition-classes **derived from merkmal's feature data, with the
granularity choice exposed to the consumer** — not a copy of
lingpy's handcraft.

---

## 0. What's in place today

- `merkmal/src/merkmal/data/classes.tsv` (20 rows) defines **natural
  classes** as overlapping sets of graphemes sharing a feature
  (e.g. `P` = "bilabial consonant", `S` = "plosive consonant"). A
  grapheme typically belongs to several. Useful for feature queries;
  **not a partition**.
- `export-cognator` (§3.3 of `COGNATOR_EXPORT_REQUEST.md`) already
  emits `classes.tsv` **only for systems that expose a class
  reduction** — currently just `classfeat`. Other systems emit no
  class file. That's correct for the natural-class notion but leaves
  cognator without a coarse-grained reduction for training.

## 1. What cognator needs

A **partition** — every grapheme in the system maps to exactly one
class label — at a granularity the consumer can choose. Fewer
classes = denser correspondence training (at the cost of losing
distinctions). More classes = finer but sparser training.

Concrete use case in cognator: correspondence table `C[source_class,
target_class]` is accumulated from aligned form-pair columns. If
there are 700+ classes (raw graphemes), most cells are empty or
near-empty and log-odds are unreliable. If there are ~30 classes,
each cell has tens to hundreds of observations and log-odds are
statistically meaningful. This is lingpy's SCA advantage; we want
the merkmal-native equivalent.

## 2. Proposed approach — feature-subset projection

**Principle**: merkmal already assigns each grapheme a set of
feature values. A partition is induced by **projecting** each
grapheme's feature tuple onto a chosen subset of features, then
grouping graphemes whose projected signature is identical.

**Example on `descriptive`:**

If the subset is `{type, manner, place}`, then:

- `p` (consonant, stop, bilabial, voiceless) → projection `(consonant, stop, bilabial)`
- `b` (consonant, stop, bilabial, voiced) → `(consonant, stop, bilabial)`
- `pʰ` (consonant, stop, bilabial, voiceless, aspirated) → `(consonant, stop, bilabial)`

All three map to the same class. Call it `C.stop.bilabial` or
canonicalize as `P` (a short code) — see §3.2 for the label scheme.

If the subset is `{type, manner, place, voicing}`, then `p` ≠ `b`
(different voicing), so they end up in separate classes. Aspiration
is still collapsed.

**Why this is merkmal-native**:

1. Classes come from the system's own feature definitions. No
   hand-crafted 28-row table. The partition is a deterministic
   function of the feature assignment already in `sounds.tsv`.
2. Granularity is a first-class parameter: choose which features
   participate in the signature. Different consumers pick different
   levels.
3. Generalizes to every merkmal system. `descriptive`, `broad`,
   `distinctive`, `pbase-*`, `phoible`, `classfeat` all have
   features; the same projection mechanism works on each.
4. Transparent provenance: the export manifest records which
   features defined each partition, so a reader can reconstruct
   the logic from primary data.

**Compared to lingpy's SCA**: SCA is a fixed 28-class hand-crafted
partition with no granularity knob and no feature-derivation
contract. Ours is data-derived at caller-specified granularity,
and self-consistent with the rest of merkmal.

## 3. Output shape

Extend `export-cognator`'s bundle with one additional file:

```
<dir>/partitions.tsv
```

**Always emitted** (every system has features, so every system can
produce partitions). Columns:

| Column | Type | Description |
|---|---|---|
| `grapheme` | string | NFC UTF-8, as in `distances.tsv`. |
| `level` | string | Level name (see §3.1). |
| `class_code` | string | Short canonical label; see §3.2. |
| `class_full` | string | Pipe-separated projected feature values, human-readable. |

Sort key: `(grapheme, level)`.

Row count per system: `|graphemes| × |levels|`.

### 3.1 Levels

Each system defines its own set of levels (because features differ
per system). Four standard levels are required; systems may
define additional system-specific levels if they have more
relevant features.

| Level | Purpose | Typical class count |
|---|---|---|
| `prosody` | Mirrors the existing `prosody.tsv` role (C/V/R/G/T/S/X). Already in the bundle; repeat here for consistent schema. | 6–7 |
| `coarse` | Feature subset covering the big articulatory divisions: for consonants `(type, manner)`; for vowels `(type, height)`. Collapses place. | 8–15 |
| `medium` | Add place distinctions: for consonants `(type, manner, place)`; for vowels `(type, height, centrality)`. Closest in spirit to SCA's 28-class size without copying SCA. | 20–35 |
| `fine` | Add voicing for consonants, rounding for vowels. `(type, manner, place, voicing)` / `(type, height, centrality, roundness)`. | 40–70 |

The actual feature subset per level per system is **merkmal's
call**, driven by which features are available and linguistically
load-bearing in that system. The manifest (§3.4) must list the
subset used for each level so consumers can audit.

**Per-system level definitions (proposed default):**

| System | coarse | medium | fine |
|---|---|---|---|
| `descriptive` | type, manner / type, height | + place / + centrality | + voicing / + roundness |
| `broad` | type, manner / type, height | + place / + centrality | + voicing / + roundness |
| `distinctive` | sonorant, continuant / sonorant, high | + coronal, dorsal / + back, low | + voice / + round |
| `pbase-hc` | consonantal, sonorant / syllabic, high | + labial, coronal, dorsal / + back, low | + voice / + round |
| `pbase-jfh`/`-spe`/`-uftc` | analogous | analogous | analogous |
| `phoible` | consonantal, sonorant / syllabic, high | + labial, coronal, dorsal / + back, low | + voice / + round |
| `classfeat` | derived from its own class scheme at three natural cut-points | | |

**Note:** for `classfeat`, you already have a 1-level class
assignment (the current `classes.tsv`). Use that as `medium`, and
derive `coarse` / `fine` by coarsening / refining it, or accept
that `classfeat`'s `coarse` and `medium` collapse.

### 3.2 Class code generation

The `class_code` is a short, stable identifier derived deterministically
from the projected feature tuple. Proposal:

- Start from the tuple, e.g. `(consonant, stop, bilabial)`.
- Concatenate the first letter of each non-type value: `SB` (stop-bilabial).
- Prefix with a type sigil: `C` for consonant, `V` for vowel,
  `T` for tone, `S` for suprasegmental.
- Resolve collisions deterministically by appending a numeric suffix
  in a stable order (alphabetical by class_full).

Examples on `descriptive`, `medium` level:

| Projected tuple | class_code | class_full |
|---|---|---|
| (consonant, stop, bilabial) | `C.sb` | `consonant\|stop\|bilabial` |
| (consonant, stop, alveolar) | `C.sa` | `consonant\|stop\|alveolar` |
| (consonant, stop, velar) | `C.sv` | `consonant\|stop\|velar` |
| (consonant, fricative, labio-dental) | `C.fl` | `consonant\|fricative\|labio-dental` |
| (vowel, open, front) | `V.of` | `vowel\|open\|front` |

The specific code-generation scheme isn't critical — pick one and
document it. What matters is that (a) codes are stable across runs
(byte-stability), (b) `class_full` is unambiguous, and (c) the
table is reproducible from features alone.

**Alternative**: use just `class_full` (no short code) as the class
identifier. Longer labels but zero ambiguity. Acceptable.

### 3.3 Handling unmappable graphemes

Some graphemes may lack a feature in the projected subset
(missing voicing annotation, etc.). Emit them with `class_code =
"X"` and `class_full = "unclassified:<reason>"`, matching the
existing `prosody.tsv` X-role handling. Log a warning listing
unclassified graphemes at export time (same channel as the
existing prosody-X warning).

### 3.4 Manifest additions

Add a `partitions` block to `manifest.json`:

```json
{
  ...,
  "partitions": {
    "levels": ["prosody", "coarse", "medium", "fine"],
    "definitions": {
      "prosody": {
        "features": ["<derived from prosody.tsv>"],
        "class_count": 6
      },
      "coarse": {
        "features": ["type", "manner", "height"],
        "class_count": 11
      },
      "medium": {
        "features": ["type", "manner", "place", "height", "centrality"],
        "class_count": 28
      },
      "fine": {
        "features": ["type", "manner", "place", "voicing", "height", "centrality", "roundness"],
        "class_count": 52
      }
    }
  },
  "files": {
    ...,
    "partitions.tsv": {
      "present": true,
      "sha256": "...",
      "rows": 3112,
      "bytes": ...
    }
  }
}
```

Document that the `features` list records the subset used — this
is the audit trail that lets consumers verify the partition is
derived from data, not handcraft.

## 4. CLI extension

No new subcommand. The existing `merkmal export-cognator` emits
`partitions.tsv` automatically. Optionally:

```sh
merkmal export-cognator --system=descriptive --out=dir \
    [--partition-level-features=coarse:type,manner \
     --partition-level-features=medium:type,manner,place]
```

An advanced flag for researchers who want a specific feature
subset. Not required for cognator's use — defaults per §3.1 are
fine.

## 5. Byte-stability and reproducibility

Same contract as the rest of the bundle (§4 of
`COGNATOR_EXPORT_REQUEST.md`): two invocations with the same
merkmal version and `SOURCE_DATE_EPOCH` produce byte-identical
`partitions.tsv` and updated manifest. Class-code assignment must
be deterministic (lexicographic tiebreaks).

## 6. Tests to add

In `tests/test_cognator_export.py`:

1. `test_partitions_covers_inventory`: every grapheme in the system
   appears in `partitions.tsv` for every level.
2. `test_partitions_is_partition_per_level`: within each level,
   each grapheme maps to exactly one `class_code`.
3. `test_partitions_class_counts_monotone`:
   `count(prosody) ≤ count(coarse) ≤ count(medium) ≤ count(fine)`.
   Refinement order must hold; violations indicate a misconfigured
   feature subset.
4. `test_partitions_byte_stable`: under `SOURCE_DATE_EPOCH`,
   re-running produces identical TSV bytes.
5. `test_partitions_manifest_matches_output`: for each level, the
   distinct `class_code` count in the TSV matches the manifest's
   `class_count`.
6. `test_partitions_round_trip`: load `partitions.tsv`, group by
   `class_code`, assert that every pair of graphemes in the same
   class shares identical projected feature values.

## 7. How cognator will use it

- Load `partitions.tsv` alongside `distances.tsv` and `prosody.tsv`.
- Pick a level per-run (defaulting to `medium` = ~28–35 classes).
- When training correspondence tables, map each grapheme to its
  `class_code` at that level; learn log-odds over class pairs.
- When scoring at alignment time, look up both graphemes' class
  codes and use the class-level log-odds, blended with the
  grapheme-level merkmal distance prior.

The current cognator NFD-strip heuristic (`tʰ → t`, `aː → a`) will
be replaced by this merkmal-derived partition lookup. Expected
improvement: +0.02 to +0.05 mean F on the 48-dataset CoreCog bench,
concentrated on datasets with few lects and dense forms where
class-training density dominates.

## 8. Out of scope

Noting explicitly so nothing leaks in:

- **No hand-crafted SCA copy.** If the `medium` level happens to
  end up close to SCA's 28 classes, that's a byproduct of
  projecting merkmal's own features, not a design target.
- **No asymmetric classes.** Partitions are undirected. (Future
  merkmal work on asymmetric distances / directional classes is a
  separate concern.)
- **No context-sensitive classes.** A grapheme's class is a
  function of the grapheme alone — onset vs. coda / stressed vs.
  unstressed distinctions stay out. (If needed later, add a
  separate `partitions_contextual.tsv`.)
- **No multi-class membership.** Natural classes
  (overlapping sets) remain in `classes.tsv` and are orthogonal to
  this request.

## 9. Release checklist

- [ ] Implement partition derivation per system, with per-level
      feature subsets documented in code and manifest.
- [ ] Add `partitions.tsv` to `export-cognator`'s output.
- [ ] Add 6 tests in §6 to `tests/test_cognator_export.py`.
- [ ] `ruff check .`, `mypy src`, `pytest -q` clean.
- [ ] Update `CHANGELOG.md`: "Added: `partitions.tsv` in cognator
      export — feature-subset-derived grapheme partition at four
      granularity levels (prosody, coarse, medium, fine). Derived
      from each system's own features; transparent per-level
      feature subset recorded in manifest."
- [ ] Bump `pyproject.toml` minor version.
- [ ] Tag and publish.
- [ ] Regenerate cognator's pinned bundles under
      `cognator/tests/fixtures/merkmal/<system>/` and update the
      SHA pins.

## 10. Open questions for merkmal's agent

1. Is there a system where the proposed `coarse/medium/fine` feature
   choices don't make sense (e.g. `phoible` is binary-only; does
   the projection still yield a sensible 11/28/52-class hierarchy)?
   If so, propose alternate subsets per system and document.
2. Should `fine` include aspiration? In descriptive, aspiration is a
   feature. Adding it would produce ~70-class fine. My default
   above omits it; feel free to include if features support it
   cleanly.
3. The existing `classes.tsv` file remains as-is (natural classes,
   not a partition). Confirm: we add `partitions.tsv` **alongside**
   it in the export bundle, without modifying the original.

---

**Status**: REQUEST, 2026-04-18. Once implemented, cognator will
pin the merkmal version and the `partitions.tsv` SHA in its test
fixtures, then swap the current NFD-strip heuristic for a
`merkmal.LoadPartition(bundle, "medium")` lookup.
