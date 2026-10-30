# Abstract segments

**Status: implemented, 2026-10-30** (C API `mk_bundle_*` in `merkmal.h`;
Python `merkmal.AbstractSegment`; WASM not yet). Requested for the
historical-inference work (`tresoldi/framework`, `08_latent_elements.md`;
constitution v0.2.0 §6.8). There, an ancestral segment that no daughter keeps
(a "laryngeal") is reported as a feature bundle whose identity is never a
grapheme, with features the evidence does not decide left unspecified.

## What the library does today (measured at 7bb6e3e)

* **No grapheme-free segment.** Every entry point takes a grapheme, except
  `mk_sound_distance`, which compares two label lists through the geometry.
* **Underspecification scores as difference.** A guttural fricative with
  place and voice left open is 0.068 from each of ħ, ʕ and h in `descriptive`.
  It is never 0 from any of them, and there is no way to ask whether a grapheme
  is consistent with it.
* **Unknown labels are ignored silently.** `sound_distance(["consonant",
  "foo"], p)` and `["consonant", "-voice"]` both score 0.554, exactly what the
  empty set scores.
* **"Does not apply" and "unknown" share one value.** PHOIBLE's `0`, empty
  cells and per-phase contours were all written `.`. `feature_vector` documents
  `0` as "does not apply, or the source does not say".
* **The vector loses what the scorer reads.** Graphemes with identical vectors
  but non-zero distance: `distinctive` 232 pairs (`a` and `e`: height and
  backness are scored on the geometry's ordinal scales but are not columns),
  `descriptive` 7 pairs (`l`/`ɮ`, `r`/`ɹ`: manner is scored as a node group and
  is not a column). The five valued systems lose nothing.

## Decisions (author, 2026-10-30)

1. **Basis:** one typed state per column of the system's vector basis. A
   bundle's identity is the system (with its semantic fingerprint) and its
   states, never a grapheme.
2. **The vector is made lossless**, rather than given a separate bundle basis:
   the columns become exactly the dimensions the system's scorer reads. This is
   a breaking change to `feature_vector` and `vector_labels`.
3. **Typed column states.**
   * Binary columns: `+`, `−`.
   * Ordinal columns: a level, or an interval of levels.
   * Node-group columns: a label, or a set of alternative labels.
   * Every column also allows `0` (does not apply) and `?` (unspecified among
     the values that apply).
4. **Scoring is compatibility plus bounds.**
   * The point score skips every column where either side is not a single
     value, and reports coverage.
   * Exact minimum and maximum distances are given over all completions.
   * A predicate says whether a grapheme is compatible with a bundle.
   * No probability is invented. (A per-column `p(+)` was considered and left
     out: nothing would read it.)
5. **The data are split where the source says:** PHOIBLE `0` becomes
   inapplicable, and an empty cell or a contour becomes unknown.
6. **C core and Python** now, WASM afterwards. The silent-ignore bug is fixed
   in the same series.

## Columns per scorer

Each scorer is a weighted mean of per-dimension differences, so the columns
are its dimensions:

| scorer (systems) | columns |
|---|---|
| `scalar` (`distinctive`) | its scalar dimensions (binary) + the geometry's ordinal scales |
| `leaf` (`descriptive`, runtime categorical models) | geometry leaves (binary) + one node-group column per geometry node that labels map to + ordinal scales |
| `valued` (`phoible`, `pbase-*`) | its declared dimensions (binary, with `0` and `?`) |

In the numeric vector, a node-group column is written one-hot: one column per
label, `+1` if present, `−1` if the node is set to another label, and `0` if
the node is unset. A bundle holds the group as one typed column.

Acceptance: over every grapheme of every built-in system, graphemes with equal
vectors have distance 0, and a bundle made from a grapheme scores exactly as
the grapheme does against every other grapheme. Both are checked
exhaustively in CI.

## Scoring a bundle

* **Point score:** the system's own formula over the columns where both
  sides hold a single value, with that scorer's skip rules unchanged.
  Coverage is the share of weight compared, among the columns either side
  sets.
* **Bounds:** the minimum and maximum of the same ratio over all completions
  of the partial columns. Each column's choice is independent, and the score is
  `Σ w·d / Σ w`, so the extremes are found exactly by Dinkelbach iteration
  (choose per column the option minimising `w·(d − λ)`, update `λ`, repeat),
  without enumerating completions.
* **Compatible:** the grapheme's value lies in the bundle's allowed set on
  every column, and `0` matches only `0`.
* **Display:** compatible graphemes of the system, ranked by point distance.
  Ranking is not identity; it never decides anything.

`0` against a value is skipped, as it is today for valued systems, so the data
split does not change any point distance between graphemes. In categorical
systems, "does not apply" is the absence of both labels, and the scorer
compares it with a value; bundles keep that rule, which is what lets a bundle
from a grapheme score exactly as the grapheme.

For a partial bundle, the point score is computed over the dimensions both
sides fix. It is not itself a completion, so it can lie outside
`[minimum, maximum]`. Against /a/, the laryngeal-like bundle below scores
0.615, with bounds [0.649, 0.649]. Report the bounds when the question is
"how far could it be"; report the point score with its coverage when the
question is "how far is it on what we know".

## As built

* **Columns and text.** `vowel_height=close-mid..open`, `Manner=fricative|approximant`
  (one of them), `Manner=affricate&fricative` (one exact set), `voice=?`,
  `round=0`, `*` for unknown and possibly inapplicable, and `|0` to add "may not
  apply". A whole bundle is `column=cell;...`; columns left out are `*`, and
  `mk_bundle_to_text` writes every column in order.
* **Clusters and tones.** These are refused (`MK_ERR_UNSUPPORTED_MODEL`). A
  synthesized cluster has no single feature set, and a tone has no
  segmental dimension.
* **Checked:**
  * every grapheme of every built-in system makes a bundle;
  * on 21,000 random pairs, bundle distance and coverage equal the scorer's
    (≤ 1e-12), and the suite keeps 150 pairs per system;
  * on 420 partial bundles, the bounds equal brute-force enumeration exactly,
    and the suite keeps 12 per system;
  * the C suite passes under AddressSanitizer.
* **The laryngeal case** (`descriptive`): /ħ/ with `voice=?` and
  `guttural_place=?`.
  * It is compatible with /h ħ ɦ ʕ ʜ ʢ/, not with /ʔ/ (continuant is still
    fixed) nor with /k/.
  * Against /ʕ/: distance 0 at coverage 0.66, bounds [0, 0.34].

## Open

* **P-base cell codes.** The tables use `n`, `o` and `x`, scored today as a
  third value, and `.`, scored as missing. The 2019 extraction kept no record of
  what they mean, so they are not split until that is known.
