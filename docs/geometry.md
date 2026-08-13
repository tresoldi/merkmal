# The geometry: `merkmal-clements-hume-inspired-v1`

`geometries/clements-hume.json` describes a tree of phonological nodes and
leaves that the scorer walks to turn a feature-set difference into a number.

**It is inspired by Clements & Hume (1995), not an implementation of it.** The
file keeps the name `clements-hume` as a compatibility identifier (models still
say `"default_geometry": "clements-hume"`, and `@geometry clements-hume` is
still accepted in runtime models), but its identity is
`merkmal-clements-hume-inspired-v1` and its `theory_fidelity` field says
`inspired-by`.

The distinction matters because "Clements–Hume distance" would attribute this
project's numerical choices to those authors. Clements and Hume propose a
theory of how features are organized, how they spread, and how complex and
contour segments are represented. They propose no similarity measure and no
sound-change cost.

## Departures from the source theory

The `departures` field in the JSON is the authoritative list; it is validated
to be non-empty. In summary:

1. **A `Prosodic` node.** Length, nasalization, secondary articulations,
   ejectivity, and stress are grouped under one node. The source theory does
   not place these in the feature tree this way.
2. **A `Tonal` node** with `TonalOnset` / `TonalMid` / `TonalOffset` subtrees
   encoding Chao levels. This decomposition is a merkmal design, not a
   Clements–Hume proposal.
3. **The tree is used as a numerical aggregation structure.** Base weights are
   derived mechanically as `1 / depth` (see below). The source theory implies
   no such mapping.
4. **Structural distinctions are collapsed.** Spreading, multiple association,
   and contour timing are represented structurally in the theory; here they are
   either flattened into leaves or not represented at all.
5. **Extra leaves for coverage.** Major class, release, articulatory shift, the
   length series, and secondary articulations were added so that every label
   the bundled models can return reaches the score. See below.

## The scoring rule

There are three kinds of scoring dimension.

**Leaves** are privative or binary. A leaf has a positive pole, optionally a
negative pole, and a base weight of `1 / depth` where `Root` is depth 1. A
difference costs the full weight for opposite poles, half for one pole against
an unspecified value. A leaf may override the mechanical depth weight with an
explicit `"weight"`.

That rule has to hold on both scoring paths. `broad` and `descriptive` score
through these leaves; `distinctive` scores through the `scalar_dimensions` it
declares in its own `model.json` and never reads a geometry leaf at all. Where a
dimension shares a name with a leaf, the two must cost the same, or this table
describes neither of them. They did not: an explicit `"weight"` was dropped on
the scalar path, so `vocoid` was declared 0.8 here and cost 1.0 in
`distinctive` — a 25% overweight on major class in the system this table is
most often read for. `scripts/validate_models.py` now asks the generator what
weight it will emit and fails if it disagrees with the leaf.

**Ordered scales** (`ordinal_scales`) are for properties where the difference
between two values is a quantity rather than a mismatch. Cost is
`|level_a - level_b| / (level_count - 1) * weight`, so one step on the
seven-point vowel-height scale costs a sixth of the full range.

| scale | node | levels | weight |
| --- | --- | --- | ---: |
| `vowel_height` | Dorsal | close … open (7) | 1.0 |
| `vowel_backness` | Dorsal | front … back (5) | 0.8 |
| `dorsal_place` | Dorsal | palatal … uvular (4) | 0.5 |
| `coronal_place` | Coronal | linguolabial … alveolo-palatal (6) | 0.5 |
| `labial_place` | Labial | bilabial, labio-dental | 0.3 |
| `guttural_place` | Pharyngeal | pharyngeal, epiglottal, glottal | 0.4 |
| `duration` | Prosodic | ultra-short … ultra-long (5) | 0.5 |
| `tone_{onset,mid,offset}_level` | Tonal* | Chao 1–5 | 0.4 each |

A scale is skipped for a pair when either segment has no value on it, because
the property does not apply: a consonant has no vowel height, and a toneless
segment no tone level. Major class and `tone-present` carry those differences.
`duration` is the exception — it has a `default_level` of `short`, because a
segment with no length mark is short rather than of undefined length.

These exist because the previous flag encoding lost the ordering, with results
that were not defensible: `/i/` scored further from `/e/` than from `/a/`, a
half-long vowel was further from a long one than a plain vowel was, and the
two-bit Chao code made levels 2 and 4 as far apart as 1 and 5.

**Node groups** are the fallback. A feature listed in `feature_to_node` but
owned by no leaf or scale contributes a single boolean per node: if the two
segments differ on *any* feature under that node, the node's weight is charged
once. This is coarse by construction, which is why the properties that matter
are leaves or scales.

### The weights are stipulated, not fitted

Depth-derived weights, the explicit overrides, and the scale weights were not
derived from contrast data, perceptual judgments, or observed sound changes.
They encode one assumption: that a difference higher in the tree separates two
segments more than a difference lower down, and that a bigger step on a scale
costs more than a smaller one. Both are plausible and untested.

A scorer must not infer weights from depth unless its own specification says so.
Renaming or restructuring the tree for documentation purposes must not change
numbers; changing weights requires a new scorer version.

Weight presets (`ignore-tone`, `segmental`, `tone-only`, `flat`, …) multiply node
weights along the path to `Root`, so setting `Tonal: 0.0` zeroes every tonal
leaf and scale beneath it.

## Phonetic distance is not diachronic probability

A property worth stating plainly, because the library is aimed at historical
work: **this score does not track how likely a sound change is.** Measured over
segment pairs drawn from named sound laws, frequent changes are on average
*further* apart than rare ones. `d(k, tʃ)` is far larger than `d(k, q)`, though
velar palatalisation is among the commonest changes in the world and
unconditioned uvularisation is rare. `d(s, h)` exceeds `d(s, ʃ)`.

This is not a bug to be tuned away. Phonetic similarity and diachronic
probability are different quantities, and hand-fitting the tree until a chosen
list of sound laws came out cheap would manufacture a sound-change model with no
data behind it — precisely the failure the first review warned about. Use this
as a segment prior for alignment and candidate generation; use recurrent
correspondence patterns, estimated from language-pair data, for anything that
claims to be about change.

## Why the extra leaves exist

A label that reaches no leaf and no `feature_to_node` entry contributes nothing
to any distance. It is still parsed, still stored, and still returned to
callers — it simply cannot change a number. Thirty-three labels were in that
state, including `devoiced`, `apical`, `laminal`, `unreleased`,
`pre-nasalized`, `velarized`, `ultra-long`, and — most consequentially —
`consonant` and `vowel`.

The practical effect was that `p`~`p̥`, `t`~`t̺`, `k`~`k̚`, and `y`~`yːː` all
scored exactly zero, and that a consonant–vowel comparison was barely further
apart than a stop–fricative one. `scripts/contrast_baseline.py` now fails if
any label a system can return is unable to affect a distance, and
`scripts/validate_models.py` fails if an inventory label reaches no scoring
dimension.

Since then, `sonorant`, `continuant`, `anterior`, `distributed` and
`consonantal` have also been made real. The problem there was not the tree: the
inventory NAME strings never say those words, so the leaves existed and no
grapheme could activate them, and every manner distinction collapsed into a
single `Manner` boolean. The generator now derives them from the manner and
place labels — the same derivation `models/distinctive/model.json` already
spelled out in its `scalar_dimensions`. `scripts/contrast_baseline.py` fails if
any scoring dimension becomes unreachable again.

`vocoid` is derived rather than read from the `vowel` / `consonant` labels, and
covers the four cardinal glides as well as vowels, since /w/ and /j/ are
[-consonantal]. Without that, /w/ scored as far from /u/ as a glottal stop does
from /a/, and w~u and j~i alternations are among the most common things in
historical phonology. `consonant` and `vowel` remain in the feature output as
declared `metadata_features`: readable, and deliberately not scored, because
`vocoid` already scores that distinction.

Placements added for that reason:

| Node | Leaves | Labels |
| --- | --- | --- |
| `Root` | `vocoid` | `vowel` / `consonant` |
| `Laryngeal` | `voice_shift`, `pre_aspiration`, `pre_glottalization`, `strength` | `revoiced`/`devoiced`, `pre-aspirated`, `pre-glottalized`, `strong` |
| `Manner` | `pre_nasalization`, `nasal_click` | `pre-nasalized`, `nasal-click` |
| `Manner > Release` | four leaves | `unreleased`, `with-nasal-release`, `with-lateral-release`, `with-frication` |
| `Place > Shift` | four leaves | `advanced`/`retracted`, `raised`/`lowered`, `centralized`, `mid-centralized` |
| `Place > Coronal` | `tongue_blade` | `apical` / `laminal` |
| `Place > Labial` | `rounding_degree` | `more-rounded` / `less-rounded` |
| `Prosodic > Length` | four leaves | `long`, `mid-long`, `ultra-long`, `ultra-short` |
| `Prosodic > Secondary` | eight leaves | `labialized`, `palatalized`, `pharyngealized`, `velarized`, `labio-palatalized`, `rhotacized`, `pre-labialized`, `pre-palatalized` |
| `Tonal` | `tone_presence` | `tone-present` |
| `Tonal > Tonal{Onset,Mid,Offset}` | `tone_*_mid_level` | `tone-*-mid-level` |

Release and the secondary articulations were given their own subtrees rather
than being added as siblings under `Manner` and `Prosodic`, because features
sharing a `feature_to_node` group are compared as a single boolean: several
differences within one node would otherwise cost the same as one.

## Consequences for stored numbers

These placements changed observable output. Any distances, alignments,
clusters, or thresholds computed with an earlier build must be recomputed; do
not mix cached scores across the change. See `CHANGELOG.md`.

The library does not currently offer a parallel "v1" scorer that reproduces the
older numbers. That would mean shipping two geometries and a scorer selector,
and it is listed as remaining work in `docs/review-response.md`.

## Weight presets

| preset | zeroes |
| --- | --- |
| `ignore-tone` | `Tonal` |
| `ignore-length` | `Length` |
| `ignore-secondary` | `Secondary` |
| `ignore-prosodic` | `Prosodic` (length, secondary articulation) |
| `segmental` | `Tonal` and `Length` |
| `tone-only` | everything except `Tonal` |
| `flat` | uses weight 1 for every dimension |

`segmental` used to zero the whole `Prosodic` node, which also removed
nasalisation and ejectivity — phonemic contrasts in French, Portuguese, Hindi,
Yoruba and much of Amazonia — for anyone reaching for it to normalise away
length conventions. Nasalisation now sits under `Manner` and ejectivity under
`Laryngeal`, where they belong, and `segmental` names only what it drops.

## `deep-clements-hume.json`

A deeper variant, present as source data. It is not compiled into the C library
and nothing loads it. It carries the same caveats and has not been updated with
the coverage leaves above.
