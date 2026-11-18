# Typologies

Direction costs for sound-change-sensitive scoring: for a feature, separate
costs for a change from `+` to `-` and from `-` to `+`. No part of the library
reads these files; they are source data for directed scoring, which the library
does not provide.

| File | Status | Content |
| --- | --- | --- |
| `default.json` | neutral | no direction costs, so every direction costs 1.0 |
| `lenition-bias.json` | hand-authored hypothesis | stipulated costs that make a loss of stricture cheaper than a gain; not estimated from data and not evidence of a bias |
| `corecog-derived.json` | **quarantined** | not to be used as a direction prior |

## `corecog-derived.json`

The file holds counts derived from 149,344 cognate pairs across 56 CoreCog
datasets (as recorded in the file's `source` field), transformed into direction
costs. It is not a sound-change direction prior, for the following reasons, most
of which are properties of the procedure rather than of the numbers:

1. **Direction is not identified.** The counts come from unordered pairs of
   daughter varieties. Which of two attested states is historically earlier
   cannot be recovered from such a pair; that requires a reconstructed or
   attested ancestor, or a phylogenetic model that carries direction.
2. **The orientation is undefined.** The derivation was documented as relative
   to the alphabetically first variety, but the deriving script iterates
   varieties in input order without sorting, so reordering the input rows
   reverses every label.
3. **The cost transform is inverted.** The deriving script states that the more
   frequent direction receives a cost below 1.0, then computes
   `pos_to_neg = 2.0 * (pos_to_neg / total_changes)`, which increases with
   frequency.
4. **Sampling is unweighted.** Every language pair within a cognate set
   contributes, so large sets contribute quadratically and densely sampled
   families dominate. No family weighting or effective sample size is reported.
5. **Environment is pooled.** Sound change is typically conditioned by
   neighbouring segments, syllable position, stress and morphology, none of
   which the counts distinguish.
6. **The procedure is partly circular.** The alignments were produced with the
   same dissimilarity that the resulting costs were meant to calibrate.

The deriving script is kept beside the file,
[`derive_direction_costs.py`](derive_direction_costs.py), as the record of the
procedure described above. It does not run against the current library: it
uses the pure-Python implementation that the C library replaced, and reads
CoreCog forms from local paths outside this repository. The numbers are kept, under the key `quarantined_direction_costs`,
so that a loader looking for `direction_costs` does not read them. Correcting
point 3 in place would reverse the behaviour of any existing consumer of the
file and would not address the other points; a corrected artifact requires a
new identifier, its own provenance manifest, and an explicit opt-in to directed
scoring by the caller.

## Requirements for a direction prior

Each observation carries its own evidence of direction:

```text
family, branch, ancestor_state, descendant_state,
left_context, right_context, prosodic_position,
time_depth/ordering, cognate_set, source, confidence
```

with weighting per cognate set and per family, evaluation split by whole
family rather than by word pair, and calibration reported with accuracy. For
alignment and cognate work in the absence of such data, a correspondence model
between pairs of languages, which makes no claim about direction, is the
appropriate tool.
