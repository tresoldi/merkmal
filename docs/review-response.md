# Response to the linguistics and phonology review

Tracks [`linguistics-and-phonology-review.md`](linguistics-and-phonology-review.md)
(review date 2026-08-12, against `d0f57c9`) finding by finding: what changed,
what the evidence is, and what is still open.

The review's own roadmap staged the work. Stages 0 and 1 are done. Stage 2
(parallel versioned scorers, fixed-space metric distance, structured tone
types) and Stages 3–4 (empirical calibration, historical and typological
layers) are research programmes requiring data this repository does not have;
they are listed as open below rather than partly done.

## Correction notice

An earlier version of this document overstated three results. They are corrected
here and in `CHANGELOG.md`; an independent review
([independent-linguistic-review.md](independent-linguistic-review.md)) found all
three, and each is confirmed.

1. **"Every consonant-consonant pair scores below every consonant-vowel pair"
   was false.** It generalised from a test of eight hand-picked pairs against
   `d(p,a)`. Measured over the inventory, `broad` had a maximum C-C of 0.829
   against a minimum C-V of 0.660. The claim has been removed rather than
   restated; major class carries substantial weight, but heavily modified
   consonants can still out-distance a close C-V pair, and that is expected.
2. **"Every zero is on the record" held only for the population audited**, which
   was the bare inventory graphemes of the three categorical systems. It did not
   cover composed forms -- `d(aː, aːː)` was 0 -- and did not cover the five
   valued systems at all, where `phoible` scored zero on roughly 5% of pairs.
   The audit now covers all eight systems and composed forms.
3. **"33 dead labels to 0" was true only in the direction tested.** Every label
   a model returns can move a distance; the converse was never checked, and
   thirteen scoring leaves were unreachable because no inventory NAME ever
   mentions `sonorant`, `continuant`, `anterior` or `distributed`. The audit now
   checks both directions.

## Headline numbers

Measured over all inventory graphemes plus composed forms, in every built-in
system.

| Measure | Review | First pass | Now |
| --- | ---: | ---: | ---: |
| `broad` pairs scoring zero | 802 | 7 | **0** |
| `descriptive` pairs scoring zero | 802 | 7 | **0** |
| `distinctive` pairs scoring zero | 599 | 7 | **0** |
| Labels unable to affect any distance | 33 | 0 | 0 |
| Scoring dimensions no grapheme can reach | 13 | 13 | **0** |
| Systems audited | 3 | 3 | **8** |
| Forms per categorical sweep | 778 | 778 | **1,106** |
| Pairs per categorical sweep | 302,253 | 302,253 | **611,065** |

The categorical sweep now includes modifier-composed forms, not only inventory
rows, which is where `d(aː, aːː) = 0` had been hiding.

Zero-distance pairs in the valued systems remain, because they are properties of
the upstream feature tables: the P-base UFTC feature set assigns /e/ and /i/
identical values on every dimension it defines. Inventing values to separate
them would be fabricating data. They are recorded as counts with examples in
[`tests/golden/contrast_baseline.tsv`](../tests/golden/contrast_baseline.tsv)
and checked for regression.

## Finding 1 (P0) — categorical distance did not preserve contrasts

**Done.** The review's alternative A (fixed explicit dimensions with a declared
alias relation) was adopted in substance without redesigning the representation
format:

- Thirty-three labels reached no geometry node and so could not change any
  score, including `consonant` and `vowel`. Every one now has a leaf. See
  [geometry.md](geometry.md) for the placements and the reasoning.
- `distinctive` scores through its own scalar dimensions, so the same labels
  were added there, plus dimensions closing genuine representational gaps:
  dorsal consonant place (palatal/velar/uvular via `[high]`/`[back]`),
  labiodental, alveolo-palatal, the guttural places, a third vowel-height band,
  near-close/near-open, lateral fricative vs approximant, and click vs
  implosive.
- Release and secondary articulations were given their own subtrees, because
  labels sharing a `feature_to_node` group compare as one boolean: several
  differences within a node otherwise cost the same as one.
- `scripts/validate_models.py` now fails if any inventory label reaches no
  scoring dimension. `scripts/contrast_baseline.py` now fails if any label a
  system can return cannot affect a distance, and if any zero-distance pair is
  not declared.

The ordering improved as well as the count: previously `p`~`s` (0.70) was
barely closer than `p`~`a` (0.68), which is not a defensible ordering for any
use of the number. Major class now carries real weight, and the ordinary
consonant and vowel pairs asserted in
`test_major_class_dominates_within_class_differences` sit well below it. This is
*not* a claim that every C-C pair scores below every C-V pair; see the
correction notice above.

**Open:** `broad` and `descriptive` remain operationally identical — same
inventory bytes, same feature sets, same distances. The review's options are to
define and test a real broadening transform or to deprecate the name. Neither
has been done; the README says so plainly rather than implying a choice exists.

## Finding 2 (P0) — the valued score is a dissimilarity, not a metric

**Documented, not changed.** Adding a fixed-space metric scorer alongside the
pairwise-complete one is Stage 2: it needs a second scorer identity, versioned
independently of the model data, and a verified reading of what the P-base
states `n`, `o`, `x`, and `.` actually mean — which the review says must come
from provenance rather than be guessed, and that provenance is still
`UNVERIFIED`.

What did change is that the claim is now correct everywhere. The README states
that the output is not a metric, gives a live counterexample
(`d(ðˠ, mʲ) = 0.3113 > 0.0943 + 0.2091` in `pbase-hc`), and warns against
metric-dependent indexing and clustering.
`test_valued_scorer_is_documented_as_nonmetric` fails if that counterexample
ever stops holding, so the documentation cannot silently go stale.

**Open:** fixed-space distance with explicit `missing` vs `neutral`; returning
comparison coverage alongside the score; independent `scorer_id` /
`scorer_version`.

## Finding 3 (P0) — tone was contrastively lossy, and the parser inconsistent

**Done**, via the review's option B (extend the flat features) as the immediate
corrective release; option A (a structured tone object on a tone-bearing unit)
remains the long-term data model.

- Chao level 3 produced no features at all, so `a` and `a³³` had identical
  representations and compared equal — as did `a` and `ā`, since the macron is
  `[3,3,3]`. Each position now carries an ordered level `tone-<position>-<1..5>`
  and every tone-bearing form emits `tone-present`.
- The first pass at this used a register bit plus a height bit, which the second
  review showed is not monotone in the Chao digit: levels 2 and 4 differ in both
  bits, so they scored as far apart as 1 and 5. The ordered level replaces it,
  and cost is now proportional to the difference in pitch level.
- Two-digit contours never filled the mid slot, so `a¹` and `a¹¹` — the same
  level tone spelled two ways — differed. A two-digit contour now takes the
  midpoint of its glide, and `a¹` ≡ `a¹¹` ≡ `a¹¹¹`.
- IPA tone letters U+02E5–U+02E9, the primary IPA notation, were rejected
  outright. They are now read as the same pitch levels as the superscript
  digits.
- Runs of four or more Chao digits are now rejected atomically. Previously
  `a¹²³⁴` was accepted: the recognizer refused `¹²³` on seeing a fourth digit,
  the caller fell through and appended `¹` to the base, then parsed `²³⁴`
  separately, yielding `tone-onset-lowered` *and* `tone-onset-raised` on the
  same segment.
- Tokenization, `is_segment`, and feature lookup now agree: `segment_ipa` keeps
  a digit run in one token, and the recognizer rejects that token whole.
- Valued systems have no dimension a tone modifier can move. PHOIBLE has a
  `tone` column mapped under `Tonal`, but no diacritic effect ever sets it, so
  `a¹¹` and `a⁵⁵` compared equal. Those systems now return
  `MK_ERR_UNSUPPORTED_MODEL` for tone-bearing graphemes instead of a falsely
  precise zero.

**Open:** a structured `Tone` type with register, contour, association, and the
original spelling preserved; per-model `tone_support = none | categorical |
contour` declarations. Tone sandhi, floating tones and register systems remain
out of scope for a segment-level representation.

## Finding 4 (P1) — segmentation disagreed with recognition

**Done**, via the review's recommendation to expose the policies separately
rather than change the old function in place.

`mk_system_segment_ipa` / `merkmal.system_segment_ipa` does longest match
against the selected system, so `tʃa` → `[tʃ, a]` and `kpa` → `[kp, a]`, and
tie-bar spelling no longer changes the token sequence. `mk_segment_ipa` is
unchanged and now documented as orthographic tokenization, with its
disagreement with the recognizer stated in the header. Supplying your own
boundaries is documented as the preferred input for historical corpora.

**Open:** per-phenomenon policy switches (affricate, coarticulation,
prenasalization, vowel sequence, explicit boundaries) and alternative
tokenizations for ambiguous input. The current function has one policy, and
says so.

## Finding 5 (P1) — "Clements–Hume" named a custom tree

**Done**, via the review's option A. The geometry's identity is
`merkmal-clements-hume-inspired-v1`, `theory_fidelity` is `inspired-by`, and a
validated-non-empty `departures` list records each divergence. `clements-hume`
is kept as a compatibility name so existing `default_geometry` values and
`@geometry` lines keep working; the validator resolves either.
[geometry.md](geometry.md) documents every node, the `1 / depth` weighting rule
as a stipulation rather than a finding, and the fact that renaming must not
change numbers.

## Finding 6 (P1) — the archived CoreCog direction prior

**Quarantined**, via the review's option A, and deliberately not corrected in
place. `typologies/corecog-derived.json` now carries `status: quarantined`, the
six reasons, and its numbers under the renamed key
`quarantined_direction_costs` so a loader looking for `direction_costs` cannot
pick them up. `typologies/README.md` and a banner on
`docs/legacy_python/scripts/derive_direction_costs.py` explain that fixing the
inverted `pos_to_neg = 2.0 * ratio` alone would not make the output valid — it
would not touch the fact that unordered daughter–daughter pairs do not identify
direction — and would silently reverse anything already consuming the file.

**Open:** the redesign itself (options B and C), which needs directed
ancestor–descendant data or language-pair correspondence models.

## Finding 7 (P1) — validation did not enforce semantic integrity

**Done**, via the review's option A for both the static and runtime paths.

Static (`scripts/validate_models.py`), all now hard errors:

- exact `geometry_map` ↔ inventory-header agreement in both directions;
- leading/trailing whitespace in any identifier;
- geometry nodes, weight-preset nodes, and scalar-dimension nodes must exist;
- a feature may not be owned by two leaves;
- duplicate dimension names, and labels listed as both positive and negative;
- state symbols must cover every value the inventory uses;
- `default_geometry` must resolve to a real geometry name;
- every inventory label must reach a scoring dimension;
- complete provenance with a recognized SPDX identifier, matching hashes, and
  agreement with `model.json`.

It caught two further real defects while being written: `models/phoible`
declared state symbol `0`, which does not occur in its inventory, while the
30,181 cells actually written as `.` were undeclared; and its license was
recorded as generic `CC-BY`.

Runtime (`mk_registry_add_model_text`) is now **strict by default**. The
review's probe fails to register with an actionable message:

```text
strict validation: feature is unknown to the geometry and so cannot affect any
distance; add it to the geometry or use '@validation permissive': foo
```

`@validation permissive` is the documented opt-out. `mk_registry_add_model_text_ex`
returns the diagnostic as an owned string; the Python wrapper raises
`NativeError` carrying it.

The two mismatches the review named are fixed: `"vocalic "` in
`models/pbase-jfh/model.json` lost its trailing space, restoring a dimension
that had been absent from every `pbase-jfh` distance, and the dead `spread`
key was removed from `models/pbase-spe/model.json`.

## Finding 8 (P2) — segment catalogs are not a typological sample

**Accepted as scope**, via the review's option A. The README states that these
are segment-type catalogs, that they carry no inventory membership, doculect,
genealogy, area, or sampling weight, and that "PHOIBLE coverage" means coverage
of segment types rather than of languages. No typological frequency function is
offered. A language-indexed layer stays out of the core.

## Finding 9 (P2) — provenance and licensing

**Done for structure, incomplete for content — deliberately.** Each model
directory has a `provenance.json` with artifact id and version, upstream name,
release, URL, commit/DOI, retrieval date, transformation, citation, SPDX
license, redistribution notes, and SHA-256 of every input file.

`NOTICE` is generated from those manifests by `scripts/generate_notice.py`
(`--check` fails if stale), and the distribution now declares
`MIT AND CC-BY-SA-3.0 AND CC-BY-NC-SA-4.0` rather than MIT alone, with `NOTICE`
shipped as a license file. PHOIBLE's license is corrected to `CC-BY-SA-3.0`.

Upstream release, commit, and retrieval date are recorded as `UNVERIFIED`
rather than guessed. The review is explicit that provenance must be established
rather than inferred from filenames, and that information does not exist in
this repository. The validator reports these as warnings so they stay visible.

**Open:** a maintainer must establish the upstream releases and re-stamp the
manifests before the next data release; the CLTS relationship of the
categorical inventories in particular is asserted nowhere and should not be.

## Second review pass

An independent review
([independent-linguistic-review.md](independent-linguistic-review.md)) found
that the first pass fixed the symptoms it measured while leaving the shared
cause: **ordered properties were encoded as unordered privative flags**, and
several basic features were unreachable. Both are now addressed.

### Ordered scales

Vowel height and backness, the place series, duration, and Chao tone level are
now `ordinal_scales`: cost is proportional to the difference in level rather
than to a mismatch. This fixes, in one mechanism, results that were each
indefensible on their own:

- `/i/` scored further from `/e/` (0.214) than from `/a/` (0.167), and `/i/`,
  `/e/`, `/a/` were all exactly 0.500 from `/ɔ/`.
- A half-long vowel was further from a long one than a plain vowel was, `aː` and
  `aːː` were identical, and breve-plus-length-mark asserted both `ultra-short`
  and `long`.
- The two-bit Chao code was not monotone in the digit: levels 2 and 4 differ on
  both bits, so they scored as far apart as 1 and 5.

### Features that no grapheme could reach

`sonorant`, `continuant`, `anterior` and `distributed` had leaves, and no
inventory NAME ever says those words, so every manner distinction collapsed into
one `Manner` boolean and all six coronal places into one `Coronal` boolean. The
generator now derives them, as `models/distinctive/model.json` already did in
its `scalar_dimensions`. `vocoid` is likewise derived and covers the cardinal
glides, because `/w/` scored as far from `/u/` as `/ʔ/` does from `/a/`.

`stress_feature` was removed rather than made reachable: normalization strips a
leading stress mark, since stress is a property of the syllable.

### Tone

Ordered levels per position; a two-digit contour fills its mid slot by
interpolation, so `a¹` ≡ `a¹¹` ≡ `a¹¹¹`; IPA tone letters U+02E5–U+02E9 are
accepted; and 19 precomposed tone vowels (the Pinyin third-tone set among them)
that were rejected while their NFD spellings passed now resolve, through a
compiled decomposition table that behaves identically with and without utf8proc.

### Documented rather than changed

- **The valued systems have no major-class dimension.** `vocoid` is a
  categorical-path leaf; `pbase-*` and `phoible` score through their own
  declared dimensions, none of which separates consonants from vowels the way
  the categorical systems now do. Consonant-vowel pairs are therefore not
  specially distant there. This is a property of the upstream feature sets.
- **`pbase-jfh` is an acoustic feature set on an articulatory tree.** The
  Jakobson-Fant-Halle features (`compact`, `diffuse`, `grave`, `flat`,
  `strident`) are acoustic; the geometry's nodes are articulatory. The mapping
  is a convenience for weighting, not a claim that the two systems align.

### What was declined

**Tuning the tree so that historically frequent changes score close.** The
review measured that the scorer anti-correlates with change frequency —
`d(k, tʃ)` far exceeds `d(k, q)`. That is real and is now documented in
[geometry.md](geometry.md) and the README. It is not fixed, because fixing it by
hand would mean fitting a sound-change model to a chosen list of sound laws with
no data behind it, which is the failure the first review warned about. Phonetic
similarity and diachronic probability are different quantities; the honest move
is to say so.

**Removing the valued systems' zero-distance pairs.** They are properties of the
upstream feature tables — the P-base UFTC feature set assigns `/e/` and `/i/`
identical values on every dimension it defines. Inventing values would be
fabricating data. They are published as counts and checked for regression.

## What this changed in observable output

Distances changed for every categorical system and for `pbase-jfh`. Feature
sets changed for every tone-bearing grapheme. Stored distances, alignments,
clusters, and thresholds computed with an earlier build must be recomputed; do
not mix cached scores across this change. Golden fixtures were regenerated with
`scripts/regenerate_golden.py`, which reports drift and refuses to touch the
archived pre-C parity data.

## Checks that now guard this

```sh
python scripts/validate_models.py            # schema, coverage, provenance
python scripts/contrast_baseline.py --check  # no undeclared collapse, no dead labels
python scripts/generate_notice.py --check    # NOTICE matches the manifests
python scripts/regenerate_golden.py --check  # fixtures match the build
ctest --test-dir build/c-debug               # C tests
python -m pytest python/tests                # wrapper and regression tests
```
