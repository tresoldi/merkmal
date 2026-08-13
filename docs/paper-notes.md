# Working notes toward a paper

Scratch material, not a draft. Records what was done, what the numbers are, how
to reproduce them, and which claims are safe to make. Written so that a paper
can be assembled from it without re-deriving anything.

**State described:** uncommitted working tree, base commit `d0f57c9`, 2026-08-13.
Every number below was measured on that state; re-measure before publication.

**Citations below are unverified.** Several come from review documents rather
than from works read directly. Each is marked. Do not put any of them in a
manuscript without checking the source says what is attributed to it.

---

## 1. What the artifact is

`merkmal` is a C99 library (with a CPython Limited-API wrapper) that maps
IPA-like graphemes to phonological feature representations and computes
configurable segment dissimilarities. It bundles eight feature systems:

| system | kind | scoring path | inventory |
| --- | --- | --- | ---: |
| `broad`, `descriptive`, `distinctive` | categorical | feature geometry | 769 graphemes |
| `pbase-hc`, `-jfh`, `-spe`, `-uftc` | valued | declared dimensions | 1,068 |
| `phoible` | valued | declared dimensions | 3,142 |

Scale: ~7,700 lines of C, Python and tooling; 18 geometry nodes, 51 leaves,
10 ordered scales, 8 weight presets.

Intended use is as a segment prior for alignment and candidate generation in
computational historical linguistics — explicitly *not* as a model of sound
change or a typological instrument.

---

## 2. Process — this may be the paper's most interesting angle

Two independent linguistic reviews, each followed by a remediation pass, each
review auditing the previous remediation.

1. **Review A** (`docs/linguistics-and-phonology-review.md`) — design review and
   implementation audit against `d0f57c9`. Nine prioritised findings.
2. **Pass 1** (`docs/review-response.md`, first half) — addressed Stages 0–1 of
   Review A's roadmap: strict validation, tone presence, tokenization policy,
   provenance, geometry naming, and the introduction of scoring dimensions for
   33 previously inert labels.
3. **Review B** (`docs/independent-linguistic-review.md`) — commissioned to
   audit Pass 1 independently. 16 findings, of which 5 P0/P1. **It contradicted
   three claims Pass 1 had made**, all three confirmed on re-measurement.
4. **Pass 2** — the substantive one: ordered scales, derived class features,
   tone redesign.

The methodological observation worth writing up: **Pass 1 fixed every symptom it
measured and left the generating defect intact.** It eliminated 802 → 7
zero-distance pairs by adding scoring dimensions, but the added dimensions were
*privative flags*, which is what caused the deeper problems Review B found. An
audit that measures "how many contrasts collapse" does not detect "the
representation cannot express ordering". The second-order property needed its
own test.

Also worth noting: Pass 1's audit was *scoped* in a way that made its own
headline claim true but misleading — it swept only bare inventory graphemes of
three of eight systems. The claim "every zero is on the record" was true of the
audited population and false of the library.

---

## 3. The central technical finding

**Ordered phonological properties encoded as unordered privative features
produce non-ordinal distances, and the failure is invisible to contrast-collapse
auditing.**

Four properties in this library are ordered: vowel height (7 levels), vowel
backness (5), duration (5), Chao tone level (5 per position × 3 positions).
Encoded as independent privative flags, each produced results that are
indefensible on inspection but that no collapse audit flags, because the
distances are all *non-zero*:

| symptom (Pass 1 state) | value |
| --- | --- |
| `/i/` further from `/e/` than from `/a/` | 0.214 vs 0.167 |
| `/i/`, `/e/`, `/a/` all equidistant from `/ɔ/` | 0.500 each |
| half-long further from long than plain is from long | 0.250 vs 0.143 |
| `ă`, `aˑ`, `aː`, `aːː` all equidistant from `a` | 0.143 each |
| Chao 2↔4 as far apart as 1↔5 | 0.471 each |
| `a¹` ≠ `a¹¹` (same level tone, two spellings) | 0.074 |

**Fix**: a third scoring primitive alongside binary leaves and node-group
booleans — an *ordered scale* with cost `|level_a − level_b| / (n − 1) × weight`.
A scale is skipped when either segment has no value on it (a consonant has no
vowel height); `duration` is the exception, with an unmarked default of `short`.

**Second finding, same shape**: several basic features were *unreachable* —
`sonorant`, `continuant`, `anterior`, `distributed`, `consonantal`. Their leaves
existed; no inventory description string ever contains those words, so nothing
could activate them. Consequence: every manner distinction collapsed into one
`Manner` boolean, so the manner *contribution* to `d(p,f)`, `d(p,r)` and
`d(k,ʔ)` was identical regardless of how different those manners are; likewise
all six coronal places collapsed into one `Coronal` boolean. Fixed by deriving them from manner and place labels at
generation time — the derivation already existed, spelled out in one model's
`scalar_dimensions`, and simply was not applied to the geometry path.

**A regression Pass 2 introduced and the audit caught** (worth reporting
honestly, it makes a point): making place an ordered scale *per articulator*
made cross-articulator place invisible, because each scale is undefined for the
other articulator. `d(b,g)` became exactly 0. This is the same class of error as
the original defect, arrived at from the opposite direction. Fixed by adding the
privative articulator features (labial/coronal/dorsal/guttural) — which is
exactly what standard feature geometry uses articulator nodes for. The lesson:
gradient-within-category and difference-across-category are separate dimensions
and both must be represented.

---

## 4. Results

### 4.1 Contrast preservation

Exhaustive over the categorical inventory plus modifier-composed forms.

| measure | Review A | Pass 1 | Pass 2 |
| --- | ---: | ---: | ---: |
| `broad` pairs scoring zero | 802 | 7 | **0** |
| `descriptive` pairs scoring zero | 802 | 7 | **0** |
| `distinctive` pairs scoring zero | 599 | 7 | **0** |
| labels unable to affect any distance | 33 | 0 | 0 |
| scoring dimensions no grapheme can reach | 13 | 13 | **0** |
| systems audited | 3 | 3 | **8** |
| forms per categorical sweep | 778 | 778 | **1,106** |
| pairs per categorical sweep | 302,253 | 302,253 | **611,065** |

Valued systems retain zero-distance pairs (sampled at 700 forms: `pbase-hc`
1,739; `pbase-jfh` 5,722; `pbase-spe` 1,956; `pbase-uftc` 1,617; `phoible`
12,562). These are properties of the *upstream* feature tables — the P-base UFTC
feature set assigns `/e/` and `/i/` identical values on every dimension it
defines — and are recorded as counts with examples rather than removed. The
dominant contributors are underspecified cover symbols (`N`, `N?`).

### 4.2 Ordinality restored

| property | relation | values |
| --- | --- | --- |
| vowel height | d(i,e) < d(i,ɛ) < d(i,a) | 0.0752 < 0.1504 < 0.2256 |
| vowel backness | d(i,ɨ) < d(i,u) | 0.0902 < 0.2556 |
| duration | d(a,aˑ) < d(a,aː) < d(a,aːː) | 0.0282 < 0.0564 < 0.0846 |
| tone (`tone-only`) | monotone in \|Δlevel\| | 0.12, 0.24, 0.36, 0.48 |

`d(a¹, a¹¹) = 0` and `d(a˥˥, a⁵⁵) = 0` — spellings that denote one segment score
as one segment.

### 4.3 Structural distinctions restored

| observation | Pass 1 | Pass 2 | note |
| --- | ---: | ---: | --- |
| `d(ǃ,k)` vs `d(ǃ,t)` | 0.4211 = 0.4211 | 0.4566 ≠ 0.2557 | click rear closure counted as a second place |
| `d(w,u)` vs `d(ʔ,a)` | 0.7750 = 0.7750 | 0.3872 < 0.7727 | glides are [-consonantal] |
| manner contribution to `d(p,f)`, `d(p,r)`, `d(k,ʔ)` | identical | distinct | manner was one node boolean |
| `d(p,f)`, `d(p,r)`, `d(k,ʔ)` totals | — | 0.3250, 0.6573, 0.1951 | totals also differed in Pass 1 via place |

The manner row is the precise claim: Review B measured that the *Manner
contribution* was identical across those pairs, not that the totals were. Do not
overstate it — the totals differed through place.

`d(b,g)` deserves separate mention: it was non-zero in Pass 1, became exactly 0
*during* Pass 2 when place moved to per-articulator ordered scales, and the
audit caught it before it shipped. See §3.

### 4.4 The negative result — keep this, it is the honest part

**The scorer anti-correlates with the historical frequency of sound change.**

| pair | change | frequency | distance |
| --- | --- | --- | ---: |
| k → tʃ | velar palatalisation | very common | 0.4566 |
| s → h | debuccalisation | common | 0.3101 |
| p → f | Grimm's Law | common | 0.3250 |
| k → q | uvularisation | rare unconditioned | 0.0476 |
| m → ŋ | place shift | rare unconditioned | 0.1951 |

Review B measured this over 69 pairs from named sound laws: mean 0.307 for
frequent vs 0.253 for rare in `broad` — the wrong way round. This was **not**
tuned away, deliberately (§6).

Countervailing positive result from Review B, worth reproducing properly: on ten
Latin–Germanic cognate pairs across Grimm's Law against ten controls, it
separated at AUC 0.85 (`broad`) / 0.92 (`distinctive`). **This n is far too small
to report.** If the paper makes any task claim, it needs a real held-out
evaluation with family-level splits.

---

## 5. Catalogue of defects, classified

Useful for a taxonomy section. 30+ distinct defects; these are the classes.

**A. Representation cannot express the distinction**
- ordered properties as privative flags (§3)
- unreachable features (`sonorant`, `continuant`, `anterior`, `distributed`)
- cross-articulator place invisible under per-articulator scales
- Chao level 3 emitted no features → mid tone ≡ toneless
- length as four independent flags; `V̆ː` asserted both `ultra-short` and `long`

**B. Silent no-ops — declared but inert**
- `"vocalic "` with a trailing space in a model map: the header said `vocalic`,
  the two never matched, and the dimension was absent from every distance
- `spread` mapped with no corresponding inventory column
- a state symbol `0` declared that never occurs, while the 30,181 cells actually
  written `.` were undeclared
- PHOIBLE declares a `tone` dimension that no diacritic effect ever sets

**C. Source-data errors that made distinct segments identical**
- `ʈʂː` named *voiced* though `ʈʂ` is voiceless → identical to `ɖʐː`
- `ⁿgǃ` (prenasalized plain click) named a *nasal-click* → identical to `ᵐŋǃ`
- 7 rows carrying an undescribed combining circumflex: the tone mark was
  consumed and discarded, while the same sequence elsewhere synthesised a full
  falling tone
- a Private-Use-Area codepoint U+F268; a spurious `oz̻`; a doubled `ǃǃ`
- sound class `R` "resonant" defined as `consonant,-stop` → contained /s f z tʃ/
- a leftover `XXX` "development" debug class

**D. Grammar inconsistency across layers**
- tokenization split `tʃa` into `t`,`ʃ`,`a` though the recognizer accepts untied
  `tʃ` as one segment
- a four-digit Chao run was reinterpreted in pieces, yielding two contradictory
  onset levels on one segment
- 19 precomposed tone vowels rejected while their canonically equivalent NFD
  spellings were accepted — and `normalize()` returns NFC, so the documented
  preprocessing step turned working input into failing input
- IPA tone letters U+02E5–U+02E9, the primary IPA notation, rejected outright

**E. Arbitrary hard-coded policy**
- `mb` and `nd` rejected by a two-item blocklist while `mp`, `nt`, `ŋg`, `ndz`
  were accepted — the two most frequent NC sequences in the world's languages
- `pre-nasalized` asserted for any nasal-initial cluster, so geminates `mm`/`nn`
  and the labial-velar nasal `ŋm` carried it

**F. Scope leakage in configuration**
- the `segmental` preset zeroed a whole grab-bag node, silently discarding
  nasalisation and ejectivity — phonemic contrasts — along with length

**G. Claims exceeding evidence**
- "Clements–Hume geometry" for a project-specific tree with a `1/depth`
  weighting rule the source theory does not propose
- a "direction cost" artifact derived from *unordered daughter–daughter pairs*,
  with an inverted cost transform and a documented pair orientation the code
  does not implement
- a distribution declared MIT while embedding CC-BY-SA and CC-BY-NC-SA data
- three overstated claims in Pass 1's own response document

---

## 6. Decisions made and their rationale

Each of these is a defensible position that a reviewer might contest; the
rationale matters more than the choice.

**Declined: tuning the geometry so frequent sound changes score close.**
Hand-fitting weights until a chosen list of sound laws comes out cheap
manufactures a sound-change model with no data behind it. Phonetic similarity
and diachronic probability are different quantities. Documented as inherent.

**Declined: removing the valued systems' zero-distance pairs.** Would require
inventing feature values absent from the upstream tables. Published as counts
instead.

**Declined: a parallel v1 scorer reproducing the old numbers.** Would mean
shipping two geometries and a scorer selector. Listed as open work.

**Quarantined rather than corrected: the direction-cost artifact.** Its cost
transform is inverted — a plain bug — but fixing the arithmetic would not touch
the fact that unordered daughter–daughter pairs do not identify direction, and
would silently reverse the behaviour of anything already consuming it. Renamed
its key so no loader can pick it up by accident.

**Strict-by-default runtime validation.** A model whose features the geometry
does not know registers successfully and then answers `0.0` for every
comparison, indistinguishable from "these are identical". Now rejected with a
diagnostic naming the line and token; `@validation permissive` opts out.

**`UNVERIFIED` recorded rather than provenance guessed.** Upstream release,
commit and retrieval date were not recorded when the tables were produced. The
manifests say so explicitly rather than inferring from filenames.

---

## 7. Methods — the audits

Three properties, checked over the inventory plus modifier-composed forms. This
is the reusable methodological contribution.

**P1 — no undeclared collapse.** For all pairs of distinct accepted forms,
`d = 0` must appear in a checked-in baseline with a reason. Rationale: a zero is
a *claim* that two transcriptions denote the same thing; the library should have
to say so on the record.

**P2 — no dead labels.** Every label a system can return must be able to change
some distance. Implemented by probing the scorer directly: a segment carrying
only the label against one carrying a string the geometry cannot know. *For an
ordered level this probe must compare against another level of the same scale* —
probing against an unrelated label always scores zero, because the scale is
skipped when one side is undefined. (This was a real bug in the audit itself.)

**P3 — no unreachable dimensions.** The mirror of P2, and the one whose absence
let 13 leaves stay decorative for two review cycles: every scoring dimension
must be activatable by some grapheme.

P2 and P3 are duals and both are needed. P2 catches "the data says something the
model cannot score"; P3 catches "the model can score something the data never
says". Neither implies the other.

**Complexity and sampling.** Categorical sweeps are exhaustive (611,065 pairs
each). Valued sweeps are capped at 700 forms, evenly spaced, because the valued
scorer walks every declared dimension per pair and PHOIBLE alone would be >8M
comparisons. **The cap is printed on every run and recorded in the baseline** —
a silent truncation would read as "covered everything", which is precisely the
error Pass 1 made.

Supporting checks: exact identifier matching (whitespace, duplicates), geometry
node resolution, state-symbol coverage, feature-to-dimension coverage,
provenance completeness with content hashes, and a generated data bill of
materials.

---

## 8. Reproduction

```sh
cmake -S . -B build/c-debug -DCMAKE_BUILD_TYPE=Debug
cmake --build build/c-debug
python -m pip install -e ".[dev]" --no-build-isolation

ctest --test-dir build/c-debug --output-on-failure   # 4 suites
python -m pytest python/tests -q                     # 25 tests

python scripts/validate_models.py                    # schema, coverage, provenance
python scripts/contrast_baseline.py --check          # P1/P2/P3, ~4 min
python scripts/contrast_baseline.py --max-valued-forms 0   # exhaustive, ~1 h
python scripts/generate_notice.py --check            # data bill of materials
python scripts/regenerate_golden.py --check --build-dir build/c-debug
```

Regenerating after an intended data change:

```sh
python tools/generate_c_data.py                      # rebuild compiled tables
python scripts/regenerate_golden.py --build-dir build/c-debug
python scripts/contrast_baseline.py --write          # then review UNDECLARED rows
python scripts/generate_notice.py --restamp && python scripts/generate_notice.py
```

Key API for measurement:

```python
import merkmal
merkmal.distance(a, b, system="descriptive", node_weights="tone-only")
merkmal.get_features(g, system=...)
merkmal.system_segment_ipa(s, system=...)   # longest match, agrees with is_segment
merkmal.segment_ipa(s)                       # orthographic, deliberately different
```

Presets: `ignore-tone`, `ignore-length`, `ignore-secondary`, `ignore-prosodic`,
`segmental`, `tone-only`, `flat`.

---

## 9. Candidate framings

**(a) Methods / resource paper — safest.** "Auditing phonological feature
resources for representational adequacy." Contribution: three checkable
properties (P1–P3), the observation that P2 and P3 are duals, an implementation,
and a case study finding 30+ defects in a resource that passed its existing
tests. Claims are about the *method*, and all are demonstrated.

**(b) Squib / cautionary note.** "Ordered phonological properties encoded as
privative features." Narrow, sharp, fully supported by §3. Probably the most
publishable per unit of work.

**(c) Negative-result note.** "Segment dissimilarity does not track sound-change
frequency." Needs the correlation study done properly — Review B's 69 pairs are
a starting point, not a result. Would need a principled sample of changes with
frequency estimates from an actual database.

**(d) Full system paper.** Needs §4.4's task evaluation done at scale, with
family-level holdout and baselines (exact match, flat Hamming, sound classes,
language-pair correspondence model). Not currently supported.

**Do not claim**: that the distances are validated against any task; that they
are metric (they are not — a live counterexample is asserted in the test suite);
that the weights are anything but stipulated; anything typological.

---

## 10. Limitations and threats to validity

- **No external validation.** No perceptual judgments, no gold alignments, no
  held-out correspondence task. Every improvement is argued from internal
  coherence and phonological reasoning, not measured against a target.
- **Weights are stipulated.** `1/depth`, explicit overrides, scale weights — all
  hand-set. The ordinality *relations* are principled; the magnitudes are not.
- **Improvements are not independent of the auditor.** The same reasoning that
  found the defects chose the fixes. A third review would likely find more.
- **The valued systems are sampled**, not swept, for the collapse count.
- **`broad` and `descriptive` remain operationally identical** — byte-identical
  inventories, identical outputs. Two public names implying a choice that does
  not exist.
- **Cluster and diphthong labels (`n1-*`, `move-*`, `diphthong`) are unscored
  annotations.** Scoring runs through a separate component-averaging path.
  Documented, not fixed.
- **The 769-grapheme inventory is heavily skewed** — Review B reports 64% dental
  by place. Fine for a segment catalog, disqualifying for anything typological.
- **Tone remains segment-level.** No tone-bearing unit, association, floating
  tones, sandhi, or register systems.
- **UBSan was not run** (runtime absent on the dev machine); ASan is clean.

---

## 11. Related work to check

**All attributions below are unverified.** Several are second-hand from review
documents.

- Clements & Hume (1995), "The Internal Organization of Speech Sounds", in *The
  Handbook of Phonological Theory*, 245–306. Used here as the *inspiration* for
  the tree. Verify what it does and does not claim — it proposes no metric.
- List (2019), "Automatic Inference of Sound Correspondence Patterns across
  Multiple Languages", *Computational Linguistics* 45(1). The key anchor for
  "correspondences, not universal similarity, are the evidence base."
- List, Forkel & Hill (2022), on trimmed alignments and correspondence patterns.
- Moran & McCloy (eds.) (2019), *PHOIBLE 2.0*. Inventory-indexed; its feature
  set is PHOIBLE's own, loosely based on Hayes with additions attributed to
  Moisik & Esling — verify.
- List, Anderson, Tresoldi & Forkel (2024), *CLTS 2.3.0*. A reference catalog.
  **Note**: the categorical inventories' relationship to any CLTS release is
  asserted nowhere and should not be claimed.
- Mielke, *P-base*. Source of the four valued systems.
- Kondrak's ALINE and LingPy's SCA — cited in Review B as precedent for
  restricting C–V matching in alignment. Verify.
- Jakobson, Fant & Halle — tense/lax, and the acoustic feature set behind
  `pbase-jfh`. Note that `pbase-jfh` is an *acoustic* feature set mapped onto an
  articulatory tree; the mapping is a weighting convenience, not an alignment
  claim.
- Lass (1984), Kirchner (1998) — cited in Review B for the lenition scale, used
  to identify an inverted sign in a hand-authored typology file. Verify.

---

## 12. Open work

Roughly in dependency order.

1. **Task evaluation.** Held-out cognate/alignment benchmark, family-level
   splits, baselines (exact match, flat Hamming, sound classes, language-pair
   correspondence model). Everything in framing (d) depends on this.
2. **Fixed-space metric scorer** with explicit `missing` vs `neutral`, alongside
   the pairwise-complete one. Blocked on establishing what the P-base state
   symbols `n`, `o`, `x`, `.` actually mean — which is blocked on provenance.
3. **Establish provenance.** Upstream releases, commits, retrieval dates. Blocks
   (2) and any reproducibility claim.
4. **Structured tone type** on a tone-bearing unit, preserving original spelling.
5. **Resolve `broad`/`descriptive`** — real broadening transform or deprecation.
6. **Cluster tokenization** through the same longest-match path as
   `system_segment_ipa`, so `ntʃ` is *n + tʃ* rather than *n + t + ʃ*.
7. **Language-indexed layer** if typology is ever a goal — doculect, inventory
   membership, genealogy, area, sampling. Separate package.
8. **Correlation study** for framing (c), properly sampled.

---

## 13. Artifact inventory

| path | what |
| --- | --- |
| `docs/linguistics-and-phonology-review.md` | Review A |
| `docs/independent-linguistic-review.md` | Review B |
| `docs/review-response.md` | disposition of every finding, incl. correction notice |
| `docs/geometry.md` | scoring model, departures from the source theory, weights |
| `scripts/contrast_baseline.py` | the P1/P2/P3 audit |
| `scripts/validate_models.py` | schema, coverage, provenance validation |
| `scripts/regenerate_golden.py` | reviewable fixture regeneration |
| `scripts/generate_notice.py` | data bill of materials |
| `tests/golden/contrast_baseline.tsv` | the declared-collapse record |
| `models/*/provenance.json` | per-artifact provenance with content hashes |
| `NOTICE` | generated licensing record |
| `typologies/README.md` | the quarantine and its reasoning |
| `CHANGELOG.md` | both passes, breaking changes flagged |

Everything in this document is reproducible from those.
