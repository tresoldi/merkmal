# The feature geometry

The categorical systems are scored through a feature geometry: a tree of
phonological nodes whose leaves, ordered scales and node groups turn the
difference between two feature sets into a number in `[0, 1]`. The tree is
defined in `data/geometries/clements-hume.json` and compiled into the library.

The tree is derived from the proposal of Clements and Hume (1995) but does not
implement it. Its identity is `merkmal-clements-hume-inspired-v1`, and its
`theory_fidelity` field is `inspired-by`. The name `clements-hume` is kept as a
compatibility identifier: models declare `"default_geometry": "clements-hume"`,
and runtime models select it with `@geometry clements-hume`. Clements and Hume
describe how features are organized, how they spread, and how complex and
contour segments are represented; they propose no similarity measure and no
cost of sound change. The numerical choices described here are this library's,
and a distance computed with them should not be described as a Clements–Hume
distance.

## Departures from the source theory

The `departures` field of the geometry file is the authoritative list; the
validator requires it to be non-empty. In summary, the geometry:

1. adds a `Prosodic` node, with `Length` and `Secondary` (secondary
   articulation) beneath it; nasalization is placed under `Manner` and
   ejectivity under `Laryngeal`, so that discarding the suprasegmental
   dimensions does not also discard segmental contrasts;
2. adds a `Tonal` node with `TonalOnset`, `TonalMid` and `TonalOffset`
   subtrees for Chao (1930) tone levels, a decomposition that is not part of
   the source theory;
3. uses the tree as a numerical aggregation structure, with base weights
   derived from depth (below);
4. flattens the structural distinctions of the theory (spreading, multiple
   association, contour timing) into leaves, or does not represent them;
5. adds leaves for major class, release, articulatory shift and secondary
   articulation, and the privative articulator features (labial, coronal,
   dorsal, guttural), so that every label the bundled models return can reach
   the score;
6. scores ordered properties (vowel height and backness, place series,
   duration, tone level) on ordered scales rather than as independent
   privative features;
7. does not represent stress: the normalizer strips a leading stress mark,
   because stress is a property of the syllable rather than of the segment.

## Scoring

### The distance

Each scorer computes a weighted mean of per-dimension differences:

  d(a, b) = Σ w_i δ_i(a, b) / Σ w_i,

where the sums run over the dimensions on which at least one of the two
segments has a value, w_i is the weight of dimension i, and δ_i is in
`[0, 1]`. A dimension on which neither segment has a value contributes nothing
to either sum. If no dimension qualifies, the score is 0 and the coverage is 0
(see [coverage](#coverage-and-comparability)).

The leaf scorer reads three kinds of dimension.

**Leaves** are privative (a positive pole only) or binary (a positive and a
negative pole). The base weight of a leaf is `1 / depth` of the node it hangs
from, with `Root` at depth 1, unless the leaf declares an explicit `weight`.
`vocoid` (major class, directly under `Root`) is set to 0.8 rather than the
depth-derived 1.0, and the four articulator leaves under `Place` to 0.4 each
rather than 0.5. For a binary leaf, opposite poles cost the
full weight and one pole against no value costs half of it; for a privative
leaf, presence against absence costs the full weight.

**Ordered scales** (`ordinal_scales`) represent properties whose values are
ordered, so that the difference between two values is a number of steps. The
cost of a pair is `|level_a − level_b| / (level_count − 1) × weight`; one step
on the seven-level vowel-height scale costs one sixth of the scale's weight.

| Scale | Node | Levels | Weight |
| --- | --- | --- | ---: |
| `vowel_height` | `Dorsal` | close … open (7) | 1.0 |
| `vowel_backness` | `Dorsal` | front … back (5) | 0.8 |
| `dorsal_place` | `Dorsal` | palatal … uvular (6) | 0.5 |
| `coronal_place` | `Coronal` | linguolabial … alveolo-palatal (6) | 0.5 |
| `labial_place` | `Labial` | bilabial, labio-dental (2) | 0.3 |
| `guttural_place` | `Pharyngeal` | pharyngeal, epiglottal, glottal (3) | 0.4 |
| `duration` | `Length` | ultra-short … ultra-long (5) | 0.5 |
| `tone_onset_level`, `tone_mid_level`, `tone_offset_level` | `TonalOnset`, `TonalMid`, `TonalOffset` | Chao levels 1–5 (5) | 0.4 each |

A scale is skipped for a pair when either segment has no value on it, because
the property does not apply: a consonant has no vowel height and a toneless
segment no tone level. Those differences are carried by the major-class leaf
and by `tone_presence`. `duration` is the exception: its `default_level` is
`short`, because a segment without a length mark is short rather than of
undefined length, so `a` and `aː` differ. Two segments that both leave it
unmarked are not compared on it: their agreement says nothing, and counted, it
gave every pair a shared dimension (so coverage could not report a pair that
reaches nothing else) and diluted every other difference.

**Node groups** are the remaining case. A feature that `feature_to_node` maps
to a node, and that belongs to no leaf and no scale, contributes to a single
boolean for that node: if the two segments differ on any such feature under
the node, the node's weight, `1 / depth`, is charged once. This is coarse by
construction; properties whose individual differences matter are leaves or
scales. For the same reason, release and secondary articulation have subtrees
of their own (`Manner > Release`, `Prosodic > Secondary`) whose members are
leaves, rather than being grouped under `Manner` and `Prosodic`, where several
differences would cost the same as one.

### Which scorer a system uses

The scorer is selected in one place, `mki_scorer_for` in `src/geometry.c`, and
is part of the system's [semantic fingerprint](semantic-fingerprint.md).

- **leaf**: `descriptive` and categorical models registered at run time. It
  reads the leaves, scales and node groups above.
- **scalar**: `distinctive`, which declares its own `scalar_dimensions` in
  `data/models/distinctive/model.json`, each attached to a geometry node. It
  reads those dimensions and the geometry's ordered scales, and no geometry
  leaf. A dimension that measures what a geometry leaf measures names that
  leaf (`geometry_leaf`), is attached to the leaf's node and takes its weight,
  so `distinctive` and `descriptive` price the same property alike. From
  `distinctive` 3.0.0 its `continuant`, `anterior` and `distributed`
  dimensions read the derived labels below, as `descriptive`'s leaves do (they
  omitted nasals, trills, vowels, linguolabials and dentals), and a `glide`
  dimension reads the derived `vocoid`/`consonantal`, so that /w/ is nearer
  /u/ than /b/. Its `vocoid` dimension stays the vowel/consonant major class:
  read from the derived label instead, it put `distinctive` significantly
  below SCA as an alignment cost (−1.03 points against −0.22 with both;
  [evaluation](evaluation.md)). The four
  dimensions with no counterpart in the geometry (`fricative`, `click`,
  `implosive` and `apical`) declare their weight, set to that of the leaves
  under the same node. The generator and `tools/validate_models.py` refuse a
  dimension that does neither.
- **valued**: `phoible` and the four `pbase-*` systems. Each declared feature
  is mapped to a geometry node and weighted `1 / depth` of that node. A
  feature is compared only when both segments have a value on it (`+`, `−`, or
  the third value P-base writes `n`, `o` or `x`, read as 0); `0` (does not
  apply), `?` (unknown) and `.` are not compared, nor is a feature on which
  both segments have the third value. The difference is `|a − b| / 2`, so `+`
  against `−` costs the full weight and either against the third value half.

Weight presets apply to all three scorers through the node each dimension is
attached to.

### Coverage and comparability

Every comparison can also return a coverage and a comparability
(`mk_system_segment_distance_ex`; `distance_with_coverage` in Python). For a
valued system, coverage is the share of the declared features that were
compared. For a categorical system it is 1 when any dimension was compared and
0 otherwise. A pair with no dimension in common is reported as
`no-shared-dimension`, and its score of 0 means that nothing was compared, not
that the segments are identical.

A tone and a segment are not compared on a shared scale, in any system. Their
distance is the geometry's declared `tier_policy.cross_tier_cost`, 1.0, with
coverage 0 and comparability `cross-tier`. A tone is a token the resolver marks
`tonal-autosegment` in a categorical system, or a PHOIBLE row valued
`tone=+`; PHOIBLE's tone rows have no value on any segmental dimension. The geometry would otherwise assign such a pair a
cost that depends on how many features the segment carries rather than on any
property of the tone; a caller who needs a finite cost reads the comparability
and supplies one. The value is data rather than code
([ADR 0007](../development/adr/0007-scoring-policy-is-data.md)).

### Segments written as more than one part

A diphthong, a geminate, or an affricate written without a tie bar is scored
through its parts, with the five shares of `cluster_policy` in the geometry
file. The score is `component_share` (0.8) of a part-by-part score plus
`segment_share` (0.2) of the two scored as single segments, capped at 1.
Against a plain segment, the part-by-part score gives the cluster's nucleus
`nucleus_share` (0.7) and the remaining parts, averaged, `offglide_share`
(0.3), and adds `length_penalty` (0.15) for each part beyond the first. The
nucleus is the most sonorous part (a vowel over a glide or consonant, a more
open vowel over a closer one, a vowel marked non-syllabic as a glide), the
first on a tie, so `ia` and `ai` both have `a` as nucleus. A geminate against
a segment that carries a length feature pays no length penalty and no
whole-segment term, so `aa` against `aː` scores as `a` does.
Between two clusters, it is the mean score of corresponding parts plus
`length_penalty` for each part without a counterpart. The rules are in
`src/cluster.c`; the numbers are stipulated, like the node weights.

## Reachability of the labels

A label that reaches no leaf, scale or node group is still parsed, stored and
returned, but cannot change any distance. Every label a bundled system can
return either reaches a scoring dimension or is a declared metadata feature.
Two checks enforce this: `tools/validate_models.py` fails if an inventory
label reaches no scoring dimension, and `tools/contrast_baseline.py` fails if
a label cannot affect any distance or if a scoring dimension can no longer be
reached by any segment.

The CLTS feature names of the inventories do not contain the major-class and
manner features, so they are derived from the manner and place labels: by the
generator for compiled rows, and by `src/classes.c`, with the same rules, for
the complex segments the resolver synthesizes (`mb`, `kp`, `tʂ`) and for the
rows of a runtime model. The derivation is:

- `vocoid` for vowels and for approximants at a palatal, labio-palatal,
  labio-velar or velar place (the glides /j ɥ w ɰ/, which are
  [−consonantal]); `consonantal` otherwise;
- `obstruent` for a stop, fricative, affricate, click or implosive that is not
  nasal, `sonorant` otherwise for a nasal, lateral, approximant, trill, tap or
  vowel (so the lateral fricatives and affricates `ɬ ɮ tɬ` are obstruents);
  `continuant` or `non-continuant`, from the manner;
- `anterior` or `non-anterior`, `distributed` or `non-distributed`, from the
  coronal place;
- the articulator features `labial`, `coronal`, `dorsal` and `guttural`, from
  the place. Each place scale is defined within one articulator only, so these
  carry the difference between articulators.

The leaves added for this purpose, beyond those of the source theory, are:

| Node | Leaves | Labels |
| --- | --- | --- |
| `Root` | `vocoid` | `vocoid` / `consonantal` |
| `Laryngeal` | `voice_shift`, `pre_aspiration`, `pre_glottalization`, `strength` | `revoiced` / `devoiced`, `pre-aspirated`, `pre-glottalized`, `strong` |
| `Manner` | `pre_nasalization`, `nasal_click` | `pre-nasalized`, `nasal-click` |
| `Manner > Release` | four leaves | `unreleased`, `with-nasal-release`, `with-lateral-release`, `with-frication` |
| `Place` | four articulator leaves | `labial`, `coronal`, `dorsal`, `guttural` |
| `Place > Shift` | four leaves | `advanced` / `retracted`, `raised` / `lowered`, `centralized`, `mid-centralized` |
| `Place > Coronal` | `tongue_blade` | `apical` / `laminal` |
| `Place > Labial` | `rounding_degree` | `more-rounded` / `less-rounded` |
| `Prosodic > Secondary` | eight leaves | `labialized`, `palatalized`, `pharyngealized`, `velarized`, `labio-palatalized`, `rhotacized`, `pre-labialized`, `pre-palatalized` |
| `Tonal` | `tone_presence`, `tone_neutral` | `tone-present`, `tone-neutral` |

Length (`ultra-short`, `mid-long`, `long`, `ultra-long`) and the Chao levels
(`tone-onset-1` … `tone-offset-5`) are levels of the ordered scales `duration`
and `tone_*_level`, not leaves.

`tone_neutral` represents `⁰`, the neutral tone of Chao-style transcription: a
syllable without tone in a language that otherwise has tone. It is not a pitch
level, so it activates this leaf and none of the level scales. Treating it as
level 3 would assert that it is mid, and as level 1 that it is low.

Some labels are returned to callers but deliberately not scored; they are
listed, with the reason for each, in `metadata_features` and
`metadata_feature_prefixes` of the geometry file:

- `consonant` and `vowel`, readable duplicates of the derived `consonantal`
  and `vocoid`, which carry the distinction;
- `tonal-autosegment`, which marks a token that is a tone and nothing else, as
  CLTS writes it;
- structural labels (`diphthong`, `triphthong`, `complex`, `geminate`,
  `consonant-cluster`) and the per-component prefixes `n1-`, `n2-`, `n3-` and
  `move-`, since a cluster is scored through its parts.

## Weights

The depth-derived weights, the explicit overrides and the scale weights are
stipulated. They are not estimated from contrast data, perceptual judgements
or observed sound changes. They encode two assumptions: that a difference
higher in the tree separates two segments more than a difference lower down,
and that a larger step on an ordered scale costs more than a smaller one.
Neither assumption has been tested against such data.

Because the weights follow from the structure, a change to the tree can change
distances even when it is meant only to rename or regroup nodes. Any change to
the geometry file changes `geometry_sha256` in the semantic fingerprint, and a
change that moves a distance is a data release
([release policy](../development/release-policy.md)). Distances, alignments,
clusters or thresholds computed under one geometry version should not be
combined with those computed under another; the library provides no scorer
that reproduces an earlier geometry.

### Weight presets

A preset multiplies the weight of every dimension by the factors given for the
nodes on its path to `Root`, so that `Tonal: 0.0` removes every tonal leaf and
scale.

| Preset | Effect |
| --- | --- |
| `ignore-tone` | `Tonal` × 0 |
| `ignore-length` | `Length` × 0 |
| `ignore-secondary` | `Secondary` × 0 |
| `ignore-prosodic` | `Prosodic` × 0 (length and secondary articulation) |
| `segmental` | `Tonal` × 0 and `Length` × 0 |
| `tone-heavy` | `Tonal` × 2 |
| `tone-only` | `Laryngeal`, `Manner`, `Place`, `TongueRoot` and `Prosodic` × 0; the `vocoid` leaf under `Root` is still scored |
| `flat` | weight 1 for every dimension |

Because the distance is a weighted mean, a preset changes the share of the
score that each node's differences take, not the scale of the score: under
`tone-heavy`, tonal differences weigh more and non-tonal differences less. A preset that is not the default is not part of the system
fingerprint and must be recorded with the result
([semantic fingerprints](semantic-fingerprint.md#scope-boundary)).

## Phonetic distance and sound change

The score measures phonetic dissimilarity under the geometry, not the
probability of a sound change. The two diverge systematically. In the default
system, d(k, tʃ) = 0.37 and d(k, q) = 0.05, although velar palatalization is
among the most frequently attested changes and unconditioned uvularization is
rare; likewise d(s, h) = 0.28 exceeds d(s, ʃ) = 0.13, although s > h is a
common change. Adjusting the tree until a chosen list of sound laws became
cheap would produce a model of sound change with no data behind it. The score
is suited to use as a segment prior in alignment and candidate generation;
claims about change require correspondence patterns estimated from language
data.

## Effects of the place encoding

Place is encoded as one ordered scale per articulator plus the articulator
labels, and some distances follow from that encoding rather than from any
claim about the sounds. In the default system:

- d(p, k) = 0.20 is smaller than d(p, t) = d(t, k) = 0.24, because coronals
  carry two further dimensions (`anterior`, `distributed`) that a labial or a
  dorsal leaves unset, so a coronal differs from both on more of them.
- `kp` is a level of the dorsal scale between velar and uvular, so it is as
  far from `q` as from `k` (0.11).
- Palatals are dorsal: d(c, k) = 0.07 but d(c, t) = 0.24, and d(ç, x) = 0.06 is
  much smaller than d(ç, ɕ) = 0.28.
- `a` is front, as in CLTS, so d(a, ɑ) = 0.16 is close to d(a, i) = 0.20.

Moving labial-velars off the dorsal scale, or palatals to the coronal side,
would be a change of data with these consequences in view; none is made here.

## The deep variant

`data/geometries/deep-clements-hume.json` is a deeper variant of the tree. It
is not compiled into the C library. Python callers can load it with
`merkmal.load_geometry(path)` and score already resolved feature sets with
`merkmal.geometry_distance(...)`; this path is experimental and separate from
`merkmal.distance(...)`. Its results are subject to the same caveats, and a
result computed with it must be identified by that geometry (as
`operation_fingerprint(geometry=...)` does) and calibrated separately.

## Open problems

- The weights are stipulated (see [Weights](#weights)); no estimate from
  perceptual, contrastive or diachronic data is available.
- The cost of a tone against a segment is not derived from the geometry; the
  library declares such pairs incomparable.
- Stress is not represented.

## References

- Chao, Yuen Ren. 1930. A system of tone-letters. *Le Maître Phonétique*
  45: 24–27.
- Clements, G. N. and Elizabeth V. Hume. 1995. The internal organization of
  speech sounds. In John A. Goldsmith (ed.), *The handbook of phonological
  theory*, 245–306. Oxford: Blackwell.
