# Abstract segments

An abstract segment is a feature bundle whose identity is not a grapheme. Its
values on some dimensions may be unspecified, restricted to a set of
alternatives, or declared inapplicable. Abstract segments serve historical
reconstruction, where a proto-segment that no daughter language preserves is
described by the features the evidence supports, with the remaining features
left open.

The interface is `mk_bundle_*` in `include/merkmal.h` and
`merkmal.AbstractSegment` in Python. It is not available in the WebAssembly
build.

## Design

Grapheme-based comparison cannot express such a segment, for three reasons.
A feature left open is scored as a difference, so an underspecified segment is
never at distance 0 from any of the segments it could be, and there is no test
of whether a given grapheme is consistent with it. A single "no value" state
conflates a feature that does not apply with one whose value is unknown.
Finally, a feature vector that omits dimensions the scorer reads cannot
represent the segment the scorer sees. The design addresses each of these.

1. **Basis.** A bundle has one typed cell per dimension of the system's
   feature vector. Its identity is the system, recorded with its
   [semantic fingerprint](semantic-fingerprint.md), and its cells.
2. **The feature vector is lossless.** Its columns (`feature_vector`,
   `vector_labels`) are exactly the dimensions the system's scorer reads, so
   bundles need no basis of their own.
3. **Typed cells.** Each cell holds the set of values the segment may take,
   and may also allow "does not apply" (`0`). "Unknown among the values that
   apply" (`?`) is distinct from "does not apply".
4. **Compatibility and bounds, without probabilities.** A comparison returns a
   point score over the dimensions both sides fix, with its coverage, and the
   exact minimum and maximum over all completions. A predicate states whether
   a grapheme is a completion of the bundle. No probability is assigned to
   the alternatives in a cell.
5. **Source data keep the distinction.** PHOIBLE's `0` is read as "does not
   apply"; an empty cell, or a per-phase contour such as `+,-`, as unknown
   (`?`).

## Columns per scorer

Each [scorer](geometry.md#which-scorer-a-system-uses) is a weighted mean of
per-dimension differences, so its dimensions are the columns:

| Scorer (systems) | Columns |
| --- | --- |
| `scalar` (`distinctive`) | its scalar dimensions (binary) and the geometry's ordered scales |
| `leaf` (`descriptive`, runtime categorical models) | geometry leaves (binary), one node-group column per geometry node that labels map to, and the ordered scales |
| `valued` (`phoible`, `pbase-*`) | its declared features (binary, with `0` and `?`, and the P-base third value `n`) |

In the numeric feature vector, a node-group column is written one-hot: one
column per label, `+1` if the label is present, `−1` if the node holds another
label, and `0` if the node holds none. A bundle holds the group as one cell.

Two properties hold over every grapheme of every built-in system: graphemes
with equal vectors are at distance 0, and every inventory row other than a
tone (PHOIBLE's tone rows) yields a bundle.
A bundle made from a grapheme scores as that grapheme does against any other;
the Python suite checks this, with its coverage, on 150 random pairs per
system.

## Cell grammar

| Cell | Meaning |
| --- | --- |
| `0` | the dimension does not apply; on a scale with a default level (`duration`), the segment leaves it unmarked, which reads as the default against a marked value and is not compared with another unmarked one |
| `?` | unknown; the dimension applies |
| `*` | unknown; the dimension may not apply |
| `+`, `-` (and `n` in valued systems) | a binary value |
| a level, or `lo..hi` | an ordinal level, or a range of levels (`vowel_height=close-mid..open`) |
| a label | a node-group label (`Manner=fricative`) |
| `a\|b` | alternatives: exactly one of them (`Manner=fricative\|approximant`) |
| `l1&l2` | a node group holding exactly this set of labels |
| `…\|0` | adds "may not apply" to any cell |

A bundle is written `column=cell;column=cell;…`; a column left out is `*`.
`mk_bundle_to_text` writes every column in order. An unknown column is
`MK_ERR_UNKNOWN_FEATURE` and a cell that does not parse `MK_ERR_PARSE`.

Clusters synthesized by the resolver and tones cannot be made into bundles
(`MK_ERR_UNSUPPORTED_MODEL`): a synthesized cluster has no single feature set,
and a tone has no segmental dimension.

## Scoring a bundle

- **Point score:** the system's own formula over the columns on which both
  sides hold a single value, with that scorer's skip rules. For a valued
  system, coverage is the share of declared features compared, as for
  graphemes; for a categorical system, it is the compared weight over the
  compared weight plus the weight left unspecified.
- **Bounds:** the minimum and maximum of the same ratio over all completions
  of the unspecified cells. The choice in each column is independent and the
  score has the form `Σ w·d / Σ w`, so both extremes are found exactly by
  Dinkelbach's (1967) method for fractional programming: choose in each column
  the option minimizing (or maximizing) `w·(d − λ)`, update `λ` to the
  resulting ratio, and repeat until it is stable. Completions are not
  enumerated. The Python suite checks the bounds against brute-force
  enumeration on 12 random partial bundles per system.
- **Compatibility:** a grapheme is compatible when its value lies in the
  bundle's allowed set on every column; `0` matches only `0`.
- **Display:** `mk_bundle_compatible_graphemes` lists the compatible graphemes
  of the system, nearest first. The ranking is for display and does not
  decide identity. In Python, `AbstractSegment.covering(graphemes)` returns the
  smallest bundle compatible with every grapheme given.

`0` against a value is not compared, as for graphemes in valued systems, so
reading PHOIBLE's `0` as "does not apply" leaves every point distance between
graphemes unchanged. In categorical systems, "does not apply" is the absence
of both poles of a dimension, which the scorers compare with a value; bundles
keep that rule, which is what makes a bundle from a grapheme score as the
grapheme.

The point score of a partial bundle is computed over the dimensions both
sides fix. It is not itself the score of a completion, and can therefore lie
outside `[minimum, maximum]`. The bounds answer "how far could it be"; the
point score with its coverage answers "how far is it on what is known".

## Example

In `descriptive`, a laryngeal-like segment can be written as /ħ/ with
`voice=?` and `guttural_place=?`: a voiceless or voiced guttural fricative at
an unspecified guttural place.

- It is compatible with /h ħ ɦ ʕ ʜ ʢ/, and not with /ʔ/ (it is still
  continuant) or /k/.
- Against /ʕ/, the point distance is 0 at coverage 0.78, with bounds
  [0, 0.22].
- Against /a/, the point distance is 0.670, with bounds [0.649, 0.649]: every
  completion is at the same distance, and the point score, computed on fewer
  dimensions, lies outside it.

These values are computed by `AbstractSegment.compare` with the data of this
release; `test_abstract_segment_laryngeal` in `python/tests` checks the
compatibility and the point distance against /ʕ/.

## Open problems

- **P-base cell codes.** The P-base tables use `n`, `o` and `x`, scored as a
  third value, and `.`, scored as missing. What these codes denote in the
  source extraction is not recorded, so they are not split into "does not
  apply" and "unknown" as PHOIBLE's are.

## References

- Dinkelbach, Werner. 1967. On nonlinear fractional programming. *Management
  Science* 13(7): 492–498.
