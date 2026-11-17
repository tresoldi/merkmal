# Typologies

Source data for direction-sensitive scoring. Nothing here is loaded by the C
library yet; these files are staged for later support.

## Status

| File | Status | Use |
| --- | --- | --- |
| `default.json` | active | symmetric costs (all 1.0), i.e. no direction effect |
| `lenition-bias.json` | hand-authored hypothesis | a stated bias, not an estimate; treat as a knob, not evidence |
| `corecog-derived.json` | **quarantined** | do not load as a direction prior |

## Why `corecog-derived.json` is quarantined

It was described as an empirical sound-change direction prior. It is not one,
for reasons that are structural rather than fixable by editing the numbers:

1. **Direction is not identified.** The counts come from unordered pairs of two
   daughter varieties. Which of two attested states is historically earlier
   cannot be recovered from such a pair; that requires a reconstructed or
   attested ancestor, or a phylogenetic model that carries direction.
2. **The orientation is not what was documented.** The file claimed direction
   was relative to the alphabetically first variety. The deriving script
   iterates varieties in input encounter order and never sorts, so re-ordering
   the input rows flips every label.
3. **The cost transform is inverted.** `derive_direction_costs.py` states that
   the more frequent direction should receive a discount below `1.0`, then
   computes `pos_to_neg = 2.0 * (pos_to_neg / total_changes)`, which *increases*
   with frequency.
4. **Sampling is unweighted.** Every language pair within a cognate set is
   emitted, so large sets contribute quadratically and densely sampled families
   dominate. No family weighting or effective sample size is reported.
5. **Environment is pooled away**, although sound change is typically
   conditioned by neighbouring segments, syllable position, stress, and
   morphology.
6. **The procedure is partly circular**: the alignments were produced with the
   same dissimilarity the resulting numbers were meant to calibrate.

The numbers are kept as a record of what was run. The key was renamed to
`quarantined_direction_costs` so that a loader looking for `direction_costs`
cannot pick them up by accident.

Point 3 is a plain bug, but fixing it in place would silently reverse the
behaviour of anything already consuming the file, and it would not repair
points 1, 2, and 4–6. A corrected artifact should get a new identifier and its
own provenance manifest, and callers should have to opt into directed scoring
explicitly.

## What a replacement would need

Each observation must carry its own direction evidence:

```text
family, branch, ancestor_state, descendant_state,
left_context, right_context, prosodic_position,
time_depth/ordering, cognate_set, source, confidence
```

with per-cognate-set and per-family weighting, evaluation split by whole family
rather than by word pair, and calibration reported alongside accuracy. Until
then, a language-pair correspondence model — which does not claim direction at
all — is the more honest tool for alignment and cognate work.
