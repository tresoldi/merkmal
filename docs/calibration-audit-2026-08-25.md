# Descriptive-system calibration audit — 2026-08-25

This is a local, diagnostic audit of the move from Merkmal 0.7.0
(`3d21e08312410df2eb7d72949ca935f6f9580fe3`) to 0.9.0
(`f6b958aad9d5c33da2961116e11ebad57df9a5d9`). It is not a claim that the new
geometry is empirically optimal.

## 1. Largest contractions and their feature explanations

The new descriptive resolver adds explicit structure such as `continuant`,
`sonorant`, `vocoid`, `consonantal`, and richer place/manner labels. The
following pairs were selected because they were among the largest contractions
in Cognator's linguistic fixtures:

| pair | old distance | new distance | what changed in the representation |
|---|---:|---:|---|
| `e`–`o` | 0.6667 | 0.2556 | both share `close-mid`, `continuant`, `sonorant`, `vocoid`, `vowel`; only front/back and rounding differ |
| `i`–`o` | 0.8750 | 0.3308 | richer shared vowel structure leaves height/backness/rounding as the major contrasts |
| `e`–`u` | 0.8750 | 0.3308 | same pattern as `i`–`o`, with shared vowel and continuant structure |
| `a`–`u` | 1.0000 | 0.4812 | open/front/unrounded versus close/back/rounded, but both share the enriched vowel structure |
| `i`–`w` | 0.6786 | 0.3872 | `/w/` now has `continuant`, `sonorant`, and `vocoid`, making the glide/vowel relation explicit |
| `n`–`g` | 0.7692 | 0.5000 | both share consonantal, non-continuant, and voiced structure; place and manner remain different |
| `k`–`g` | 0.3750 | 0.1190 | both share the full velar-stop structure; voicing is the residual contrast |
| `r`–`ʃ` | 1.0000 | 0.5155 | both share consonantal, continuant, and coronal structure while manner, laryngeal, and anteriority differ |

The representation changes are linguistically intelligible. They do not look
like random inventory corruption: the new features make natural class
membership more explicit and reduce distances when segments share those
classes. The important qualification is that the numerical scorer now charges
the remaining differences over a richer shared representation, so the scale
contracts substantially.

## 2. Internal contrast and model validation

The following checks were run on the current checkout:

- `python scripts/validate_models.py`: passed, with one pre-existing warning
  that PHOIBLE's retrieval provenance is not established.
- `python scripts/contrast_audit.py`: descriptive and distinctive systems cover
  all 32 representative segments and have no zero-distance contrasts. The
  valued P-base systems retain their documented upstream collapses; these are
  not silently rewritten.
- `python scripts/contrast_baseline.py --check`: passed. All returned labels
  can affect a distance and all declared scoring dimensions are reachable.
- `python -m pytest -q python/tests/test_native_wrapper.py`: 47 passed.

The exhaustive baseline reports 56 zero-distance pairs in each categorical
system over the composed inventory, but the audit attributes these to the
existing declared/compositional inventory behavior rather than dead labels or
unreachable dimensions. No new descriptive collapse was found in the focused
contrast suite.

## 3. Calibration decision

The contractions appear to be an intended consequence of the richer feature
geometry, not an obvious Merkmal implementation defect. However, internal
validation cannot establish that the weights are appropriate for historical
cognacy detection. In particular, `e`–`o`, `i`–`o`, and `e`–`u` now sit much
closer than Cognator's previous graph constants assumed.

Decision: retain the Merkmal 0.9.0 representation and scorer unchanged for
now; treat Cognator recalibration as a downstream task. Any change to geometry
weights or feature assignments requires a separate, explicitly versioned
Merkmal experiment with external phonological or task-specific evidence.

Arcaverborum is not involved in this audit and remains deferred.
