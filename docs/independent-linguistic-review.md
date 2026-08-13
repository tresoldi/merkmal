# Independent linguistic review of `merkmal`

> **Status: addressed.** This review was commissioned after the first response
> to `linguistics-and-phonology-review.md` and is kept as the record of what it
> found. Every P0 and P1 finding has since been acted on, and three claims it
> contradicted have been corrected. See
> [review-response.md](review-response.md) for the disposition of each finding,
> including the two recommendations that were deliberately declined and why.

**Reviewer perspective:** computational historical linguistics and phonological
typology.
**Date:** 2026-08-12. **Against:** working tree at `d0f57c9` plus the
uncommitted work described in `docs/review-response.md`.
**Method:** all numbers below were produced by running the installed library
(`merkmal` 0.7.0, Python wrapper) against the shipped models. Every distance is
reproducible with `merkmal.distance(a, b, system=...)`.

This review is deliberately not a re-audit of
`docs/linguistics-and-phonology-review.md`. Where I agree with that document I
say so in one line. The substance here is new ground: empirical checks of the
response's claims, and defects neither document identified.

---

## Executive summary

The response document is largely honest and the engineering discipline behind
it (declared baselines, guard scripts, provenance manifests, an explicit
`inspired-by` fidelity field) is better than what most resources in this space
ship. The README's self-description is accurate in tone. I want to say that
plainly before the criticism.

But the recent change did not do what the response claims it did, and it
introduced or left standing several defects that matter more for historical
linguistics than the ones it fixed.

The five things I would act on first:

1. **The "every zero is on the record" claim is false for five of the eight
   systems.** The guard script covers only `broad`, `descriptive`,
   `distinctive`. In a 1,100-grapheme sample, `phoible` returns exactly `0.0`
   for **42,508** distinct-grapheme pairs (7.0% of all pairs), `pbase-jfh` for
   8,413, `pbase-hc` for 2,158, `pbase-spe` for 1,808, `pbase-uftc` for 1,264.
   Named cases: `pbase-uftc` gives `d(e, i) = d(o, u) = d(y, ø) = d(a, ə) = 0`;
   `pbase-jfh` gives `d(θ, ɬ) = d(ð, ʕ) = d(x, ħ) = 0`; `pbase-hc` and
   `pbase-spe` give `d(a, ɑ) = 0`. In `phoible`, a tone letter such as `˥˦` has
   every dimension set to `.` and therefore scores `0.0` against **everything**,
   including `/a/`. And even inside `broad`, `d(aː, aːː) = 0` for 13 plain
   vowels and every consonant tested. §F1.

2. **The vowel space is not even ordinally correct in either categorical
   system.** In `broad`, `d(i, e) = 0.214` but `d(i, a) = 0.167` — the high
   front vowel is *further* from the mid front vowel than from the low front
   vowel. In `distinctive`, `d(e, ɛ) = 0.200` exceeds both `d(i, e) = 0.182` and
   `d(e, a) = 0.182`, and `/ɔ/` is closer to `/i/` (0.364) than to `/e/`
   (0.400). Vowel correspondences are half of comparative work. §F2.

3. **Tone is still contrastively lossy and its level metric is
   non-monotonic.** Under `node_weights="tone-only"`, `d(a¹¹, a⁴⁴) = 0.235` is
   *smaller* than `d(a¹¹, a³³) = 0.381`; `d(a²², a⁴⁴) = 0.471` equals the
   maximum `d(a¹¹, a⁵⁵)`; `d(a²², a⁵⁵) = 0.235` equals `d(a¹¹, a²²)`. The
   ordering is identical under default weights. Separately,
   `d(a¹, a¹¹) = 0.074 ≠ 0`, because the two-digit path never fills the mid
   slot — so the very fix the response advertises does not apply to the
   commonest Chao spelling. IPA tone letters (U+02E5–U+02E9) are unsupported
   outright, and 19 precomposed tone-bearing vowels (including the whole
   Pinyin third-tone set ǎ ě ǐ ǒ ǔ) are rejected while their canonically
   equivalent NFD forms are accepted — and `merkmal.normalize()` converts the
   accepted form into the rejected one. §F3, §F4.

4. **The scorer anti-correlates with the historical frequency of sound
   change** on a 69-pair test set built from named sound laws: mean distance
   for frequent changes 0.307 vs 0.253 for rare ones in `broad` (0.241 vs 0.205
   in `distinctive`). `d(k, tʃ) = 0.591` against `d(k, q) = 0.143` — a
   cross-linguistically routine palatalisation is scored 4.1× as costly as a
   near-unattested spontaneous uvularisation. This is a structural consequence
   of the geometry, not a tuning issue: manner differences accrue several
   half-weight leaves while an entire place change is a single 1/3-weight
   boolean. §F5, §F7.

5. **The response's headline ordering claim is empirically false.** "Every
   consonant–consonant pair scores below every consonant–vowel pair" does not
   hold: in `broad`, max C–C = 0.8286 (`ɬ̪ʲʷʰ ~ ⁿgǃ`) against min C–V = 0.6600
   (`r̪̃ː ~ ø̞̃ː`); in `distinctive`, 0.7813 (`l̪̩ ~ pf`) against 0.5714
   (`ɥ ~ i`). The cited test checks eight hand-picked pairs against `d(p, a)`.
   §V2.

Things that are fine and should not be changed: the `inspired-by` fidelity
labelling and `departures` list; the quarantine of `corecog-derived.json` and
its README, which is a model of how to retract a bad artefact; the
non-metric documentation and its guard test; the system-aware tokenizer; the
provenance manifests with honest `UNVERIFIED` fields.

**Overall judgement.** As a *candidate generator* for alignment and cognate
search the library works: on a small Latin–Germanic set it separates cognates
from controls at AUC 0.85 (`broad`) / 0.92 (`distinctive`). As a *prior for the
comparative method* it should not be used, and the README should say so more
sharply than it currently does. The problems in §F1–§F4 are correctness bugs,
not calibration disagreements, and several of them silently return a number
rather than an error.

---

## Findings

Severity: **P0** = produces silently wrong output for a normal historical-
linguistics workflow; **P1** = systematically misleading; **P2** = worth
fixing, low blast radius.

---

### F1 (P0) — Undeclared zero-distance collapses in five of eight systems, and inside `broad`

**Evidence.** `scripts/contrast_baseline.py` hard-codes
`SYSTEMS = ["broad", "descriptive", "distinctive"]` (line 36), and
`tests/golden/contrast_baseline.tsv` contains 7 rows per system for exactly
those three. The README says, without qualification:

> **Zero means "declared equivalent", and every zero is on the record.**
> `tests/golden/contrast_baseline.tsv` lists every pair of distinct graphemes
> that scores zero, with a reason.

Sampling 1,100 graphemes per valued model (≈570k unordered pairs each):

| system | zero-distance distinct pairs | rate |
| --- | ---: | ---: |
| `phoible` | 42,508 | 7.03% |
| `pbase-jfh` | 8,413 | 1.48% |
| `pbase-hc` | 2,158 | 0.38% |
| `pbase-spe` | 1,808 | 0.32% |
| `pbase-uftc` | 1,264 | 0.22% |

Restricting to 47 everyday segments (`p t k b d g m n ŋ s z f v ʃ x h l r j w`
+ 14 vowels + `tʃ dʒ ts q ʔ θ ð ɬ ɲ ʎ ɾ ʁ ħ ʕ`):

- `pbase-uftc`: `d(e, i) = d(o, u) = d(y, ø) = d(e, æ) = d(i, æ) = d(a, ə) = d(r, ɾ) = 0`
- `pbase-jfh`: `d(θ, ɬ) = d(ð, ʕ) = d(x, ħ) = d(θ, ħ) = d(ɬ, ħ) = d(a, ɑ) = d(r, ɾ) = 0`
- `pbase-hc`, `pbase-spe`: `d(a, ɑ) = 0`

Worse, in `phoible` the tone letters that PHOIBLE ships as segments have `.`
(missing) in every dimension, so `mk_valued_distance` accumulates
`total_weight = 0` and returns `0.0`:

```
merkmal.is_segment("˥˦", system="phoible")      -> True
merkmal.distance("˥˦", "˩˨", system="phoible")  -> 0.0
merkmal.distance("˥˦", "a",  system="phoible")  -> 0.0
```

And the claim fails inside `broad` too. `ultra-long` exists only as a literal
row for ten hand-listed vowels (`eːː yːː ḭːː øːː oːː a̰ːː ɛːː æːː uːː iːː`). For
everything else the second `ː` is absorbed into `long`:

```
d(aː, aːː) = 0.0    # also ɔ ə ɨ ɯ œ ɑ ɒ ʌ ɤ ɪ ʊ ɐ — 13 plain vowels
d(pː, pːː) = 0.0    # also t k s m n l r
```

None of these 21+ pairs is in `contrast_baseline.tsv`.

**Why it matters.** A zero is the strongest statement the library can make.
`pbase-uftc` telling a user that Latin *fidēs* `/e/` and *fīdo* `/i/` are the
same segment, or `pbase-jfh` equating `/θ/` with `/ɬ/`, silently destroys the
distinction that Romance and Salishan historical phonology respectively turn
on. In `phoible` the tone-letter behaviour is strictly worse than the tone
handling the response says it fixed: the categorical systems now *reject*
tone-bearing graphemes with `MK_ERR_UNSUPPORTED_MODEL`, but `phoible` accepts
tone letters as segments and returns a confident `0.0`.

**Recommendation.**
1. Extend `contrast_baseline.py` to all eight systems immediately, and either
   declare the collapses or fail. If eight systems' worth of declarations is
   impractical (it will be — 42k rows for `phoible`), then the README claim must
   be rewritten to say the guarantee holds for the three categorical systems
   only.
2. Return a distinguishable status when `total_weight == 0` rather than `0.0`.
   The prior review's Finding 2 option B (return coverage alongside the score)
   solves this; it is currently listed as open, and this is the concrete
   argument for prioritising it.
3. Reject standalone tone letters in `phoible` the same way tone diacritics are
   rejected, or give them a tone dimension.
4. Make `ultra-long` compositional rather than lexical, and add the
   long/ultra-long pairs to the guard.

---

### F2 (P0) — The vowel space is not ordinally correct

**Evidence.** Full pairwise matrices over 16 cardinal-ish vowels. Selected
entries, `broad`:

| pair | d | pair | d |
| --- | ---: | --- | ---: |
| `i ~ e` | 0.214 | `i ~ a` | **0.167** |
| `i ~ y` | 0.167 | `i ~ ɯ` | 0.167 |
| `i ~ æ` | 0.143 | `e ~ ɛ` | 0.167 |
| `i ~ ɔ` | 0.500 | `e ~ ɔ` | 0.500 |
| `a ~ ɔ` | 0.500 | `a ~ ɑ` | 0.167 |
| `ɨ ~ ɐ` | **0.143** | `ɨ ~ ɯ` | 0.214 |

`/i/` is closer to `/a/` than to `/e/`. `/i/`, `/e/` and `/a/` are all exactly
0.500 from `/ɔ/`, so height carries no information at all in that comparison.
`/ɨ/` (close central) is closer to `/ɐ/` (near-open central) than to `/ɯ/`
(close back).

`distinctive` is different but no better:

| pair | d | pair | d |
| --- | ---: | --- | ---: |
| `e ~ ɛ` | **0.200** | `i ~ e` | 0.182 |
| `e ~ a` | 0.182 | `e ~ ɔ` | 0.400 |
| `i ~ ɔ` | **0.364** | `i ~ u` | 0.200 |
| `i ~ a` | 0.200 | `i ~ ɨ` | 0.050 |

`/e/` is further from its immediate neighbour `/ɛ/` than from `/i/` or `/a/`,
and `/ɔ/` is closer to `/i/` — the vowel maximally distant from it in both
articulatory and acoustic terms — than to `/e/`.

**Cause.** In the categorical geometry, `high` is a binary leaf (`close`
vs `open`) and `low` is a binary leaf with the eccentric pole pair
`near-open` vs `near-close`. Everything in between — `close-mid`, `mid`,
`open-mid`, `central`, `near-front`, `near-back` — reaches no leaf and is
lumped into a *single* `Dorsal` group boolean at weight 1/3 (`src/geometry.c`,
`mk_process_node_feature`). So `i ~ a` differs on one binary leaf (0.333 of a
total 2.0) while `i ~ e` differs on that leaf at half strength *plus* the whole
Dorsal boolean. In `distinctive` the intermediate heights became privative
singleton dimensions (`height_close_mid`, `height_mid`, `height_open_mid`), each
with `negative_count == 0` and therefore `divisor = 1` — full cost for a
one-step height difference, while `high`/`low` remain unspecified for all mid
vowels.

Only 14 of 113 vowels in the inventory carry `close` and 5 carry `open`; 54
carry `mid`. The two leaves that actually encode height apply to a small
minority of the vowel inventory.

**Why it matters.** Vowel correspondences are where most of the interesting
comparative work is. The Great Vowel Shift, Germanic *i*-umlaut, the
Proto-Romance seven-vowel merger, Austronesian *ə reflexes — every one of these
is a small ordered step in the vowel space, and the scorer cannot order those
steps. This is the single defect most likely to produce quietly bad alignments.

**Recommendation.** Height and backness are ordinal, not binary. Replace
`high`/`low`/`back` and the height singletons with two ordered scalar
dimensions taking values in a fixed set (e.g. height ∈ {1…7} mapped to
`[-1, 1]`, backness ∈ {1…5}), scored as `|a − b|` over the fixed range. This is
the prior review's Finding 1 alternative A applied to vowels specifically; the
response adopted it "in substance" for consonants but left the vowel space on
the boolean mechanism. Acceptance test: for the cardinal vowels, `d` must be a
monotone function of Euclidean distance in the (height, backness) grid.

---

### F3 (P0) — The Chao tone metric is non-monotonic, and two-digit tones lose the mid slot

**Evidence.** Pairwise distances between level tones `a^NN` for N ∈ 1…5, under
`node_weights="tone-only"` (`broad`; default weights give the same ordering):

|   | 1 | 2 | 3 | 4 | 5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| **1** | 0.000 | 0.235 | 0.381 | **0.235** | 0.471 |
| **2** | 0.235 | 0.000 | 0.381 | **0.471** | **0.235** |
| **3** | 0.381 | 0.381 | 0.000 | 0.381 | 0.381 |
| **4** | 0.235 | 0.471 | 0.381 | 0.000 | 0.235 |
| **5** | 0.471 | 0.235 | 0.381 | 0.235 | 0.000 |

Read off the violations:

- `d(1, 4) = 0.235 < d(1, 3) = 0.381`. Level 1 is scored closer to level 4 than
  to level 3.
- `d(2, 4) = 0.471` equals `d(1, 5)`, the extreme. A two-step difference is
  scored as the maximum.
- `d(2, 5) = 0.235` equals `d(1, 2)`. A three-step difference equals a one-step
  difference.
- Level 3 is equidistant (0.381) from every other level.

**Cause.** `mk_add_chao_level_features` (`src/system.c:540`) encodes the level as
two features: a *register* (`lower` for 1–2, `upper` for 4–5) and a *height
within register* (`lowered` for 1 and 4, `raised` for 2 and 5), with 3 taking a
third privative feature instead. That is a two-bit code whose Hamming distance
is not a monotone function of the Chao value: 2 and 4 differ in both bits, 1 and
4 in one, 2 and 5 in one. Chao (1930) defined the digits as an *ordinal* pitch
scale; scoring them as an unordered two-bit code discards that.

**Second defect, same area.** Runs of one and three digits fill the
onset/mid/offset triple; runs of two fill onset and offset only
(`mk_add_chao_tone_features`, `level_count == 2` branch). Therefore:

```
d(a¹,  a¹¹ ) = 0.0741
d(a⁵,  a⁵⁵ ) = 0.0741
d(a³,  a³³ ) = 0.0952
d(a¹,  a¹¹¹) = 0.0        # three digits is fine
```

`a⁵⁵` / `a³³` / `a¹¹` is the dominant Chao spelling for level tones in Sinitic,
Tai-Kadai and Hmong-Mien sources. The fix the response headlines ("Level 3 now
emits an explicit `tone-<position>-mid-level`, and every tone-bearing form emits
`tone-present`") does not reach the two-digit path.

**Third defect.** `d(a, a³³) = 0.368 > d(a, a⁵⁵) = 0.304`. A toneless vowel is
scored *further* from a mid level tone than from a high level tone, because the
mid encoding adds a privative leaf that the toneless form lacks while leaving
both binary leaves unspecified. For tonogenesis work this is backwards: a
toneless proto-form compared with a daughter's mid/unmarked register should be
the cheapest match available.

**Why it matters.** Historical tonology in Sinitic, Tai, Hmong-Mien and
Vietnamese proceeds by matching tone *categories* across languages whose
phonetic realisations differ (Haudricourt 1954; Matisoff 1973). A pitch-distance
measure is at best a weak proxy for that, but it must at minimum be monotone in
pitch, or a Cantonese 55 ~ Mandarin 44 correspondence and a Cantonese 22 ~
Mandarin 44 correspondence become indistinguishable.

**Recommendation.** Replace the register/height bit pair with a single ordered
scalar per position: `value = (level − 3) / 2` over `[-1, 1]`, distance
`|a − b| / 2`. That makes level 3 the midpoint (fixing the third defect too),
makes the metric monotone, and needs no new leaves. Fill the mid slot for
two-digit runs by interpolation (`(levels[0] + levels[1]) / 2`) or by leaving all
runs of length ≥ 2 with mid unspecified — either is consistent; the current
split is not. Add a test asserting `d(a^i, a^j)` is monotone in `|i − j|` and
that `d(a^i, a^ii) == 0`.

---

### F4 (P0) — Tone is silently deleted for 14 inventory rows, and two of seven declared tone marks are unreachable

**Evidence, part 1.** The same diacritic sequence U+031E U+0302 is read two
different ways depending on whether the exact byte string happens to be a row in
`inventory.tsv`:

```
'ê̞ː'  (0x65 0x31e 0x302 0x2d0)  in inventory: yes
   name:  "long unrounded mid front vowel"
   feats: front, long, mid, unrounded, vowel          <- no tone

'î̞'   (0x69 0x31e 0x302)        in inventory: no
   feats: close, front, lowered, tone-mid-mid-level,
          tone-offset-lower, tone-offset-raised,
          tone-onset-lowered, tone-onset-upper,
          tone-present, unrounded, vowel               <- full falling tone
```

Fourteen inventory rows are in the first state (`ê̞ː ê̞ˑ ô̞ ô̞ː ô̞ˑ ø̞̂ ø̞̂ˑ` ×
systems); at least a dozen structurally identical synthesised graphemes
(`î̞ î̞ː î̞ˑ û̞ û̞ː û̞ˑ ŷ̞ˑ ɔ̞̂ː ɔ̞̂ˑ ɛ̞̂ ɛ̞̂ˑ ɪ̞̂ …`) are in the second.

`tests/golden/contrast_baseline.tsv` records the resulting 7 zero-distance pairs
as `source-collision`, with the reason "the combining circumflex (U+0302) is not
described and cannot be represented". That is accurate about the *source name*
but understates the consequence: the circumflex is not merely undescribed, it is
*consumed and discarded*, and the same sequence produces a full falling-tone
bundle two rows over. A genuine falling-tone mid vowel `/ê̞ː/` — perfectly
ordinary in Vietnamese or a Kra-Dai language — is unrepresentable in these
systems and produces no error.

**Evidence, part 2.** `diacritics/ipa-clts.json` declares seven `tone_marks`:
U+0300, 0301, 0302, 0304, 030B, 030C, 030F. Two of them are unreachable through
the normal input path, and `merkmal.normalize()` actively creates the failure:

```
merkmal.is_segment("ǎ")      -> True      # decomposed caron
merkmal.normalize("ǎ")       -> "ǎ"       # NFC
merkmal.is_segment("ǎ")            -> False     # rejected
```

Across 15 vowel bases × 7 tone marks, **19** precomposed forms are rejected
while their canonically equivalent NFD forms are accepted:

```
ǎ ȁ  ě ȅ  ǐ ȉ  ő ǒ ȍ  ű ǔ ȕ  ỳ ý ŷ ȳ  ǽ ǣ  ǿ
```

This includes the entire Pinyin third-tone set (ǎ ě ǐ ǒ ǔ) and all four
tone-marked `y` forms. The CHANGELOG entry for `3d21e08` says "Support
precomposed source vowels"; the support covers acute/grave/macron/circumflex on
a/e/i but not caron, double grave, or double acute, and not `y`, `æ`, `ø`.

**Why it matters.** Chinese dialect data, Vietnamese, and any African
orthography using the caron for a rising tone will fail wholesale, and the
failure mode is `MK_ERR_UNKNOWN_GRAPHEME` rather than a silent wrong answer —
which is better, but the `normalize()` interaction means a caller doing the
documented preprocessing step turns working input into failing input.

**Recommendation.**
1. Normalise to NFD internally before lookup, or complete the precomposed table.
   Add a property test: for every accepted grapheme `g`,
   `is_segment(normalize(g)) == is_segment(g)`.
2. Delete the 14 stray-circumflex inventory rows rather than declaring their
   collision. They are duplicate transcriptions of `e̞ː`, `o̞`, `ø̞` with an
   undescribed diacritic; keeping them shadows the tone synthesis path.
3. Support IPA tone letters U+02E5–U+02E9 in the categorical systems. Currently
   `a˥`, `a˧`, `a˥˩`, `a˦˥` are all rejected, which is the primary IPA tone
   notation and the one CLTS uses.

---

### F5 (P1) — The scorer anti-correlates with the historical frequency of sound change

**Evidence.** I built 52 segment pairs from named, well-attested sound laws
(Grimm, Verner, Western Romance lenition, Romance/Slavic/Sinitic palatalisation,
Greek and Iranian *s > h*, Japanese *\*p > ɸ > h*, Latin rhotacism, High German
consonant shift, RUKI, th-fronting, affricate simplification, glottalling) and
17 pairs representing changes that are rare or effectively unattested as
unconditioned shifts (spontaneous *k > q*, *t > ʈ*, *p > t*, *p > k*, *m > ŋ*,
*s > ɬ*, *b > ɓ*, unconditioned *e > o* and *a > u*).

| system | mean d, frequent (n=52) | mean d, rare (n=17) |
| --- | ---: | ---: |
| `broad` | **0.3070** | 0.2525 |
| `distinctive` | **0.2405** | 0.2049 |

The sample is IE-heavy and my "rare" list contains a few changes that are in
fact common (*i > y*, *l > ʎ*), which biases *against* the finding — so the true
gap is if anything larger. Individual rankings:

| historically frequent | d (`broad`) | historically rare | d (`broad`) | ratio |
| --- | ---: | --- | ---: | ---: |
| `k > tʃ` (Romance, Slavic, Bantu, Sinitic) | 0.5909 | `k > q` | 0.1429 | **4.1×** |
| `s > h` (Greek, Iranian, Spanish) | 0.3684 | `s > ʃ` | 0.1176 | **3.1×** |
| `t > ts` (High German) | 0.4500 | `t > ʈ` | 0.1429 | **3.1×** |
| `p > f` (Grimm) | 0.3571 | `p > t` | 0.2500 | 1.4× |
| `j > dʒ` | 0.5909 | `m > ŋ` | 0.2500 | 2.4× |
| `l > w` (l-vocalisation) | 0.3684 | `p > ʈ` | 0.2500 | 1.5× |

**Cause.** Decomposing `d(k, tʃ)` by hand against `src/geometry.c`:

```
k  = {consonant, stop, velar, voiceless}
tʃ = {consonant, affricate, post-alveolar, sibilant, voiceless}

leaves:   voice        w=0.5   both voiceless      diff 0
          strident     w=0.5   0 vs 1 (privative)  diff 0.500
          delayed_rel  w=0.5   0 vs 1 (privative)  diff 0.500
          vocoid       w=1.0   both consonant      diff 0
groups:   Manner       w=0.5   stop vs ∅           diff 0.500
          Dorsal       w=0.333 velar vs ∅          diff 0.333
          Coronal      w=0.333 ∅ vs post-alveolar  diff 0.333
                                       ------------------------
          total weight 3.667                       diff 2.167   d = 0.5909
```

versus `d(k, q)`: identical except the Dorsal group differs and nothing else, so
`0.333 / 2.333 = 0.1429`. **A manner change costs 1.333 units; an entire place
change costs 0.333.** That 4:1 ratio is the whole story, and it is a direct
consequence of manner being spread over many half-weight `Manner` leaves while
place is a single group boolean per articulator node.

**A side effect the response does not mention.** The new `vocoid` leaf at
weight 1.0 contributes 1.0 to the *denominator* of every consonant–consonant
comparison while contributing 0 to the numerator. Without it, `d(k, q)` would be
`0.333 / 1.333 = 0.250`. Adding major class therefore did not only separate C
from V — it compressed every within-class contrast by roughly 40%. Anyone with a
threshold calibrated on the previous build needs to know that the *shape* of the
consonant distance distribution changed, not just its separation from vowels.

**Why it matters.** Recurrent correspondences, not universal similarity, are the
evidence base for reconstruction (List 2019; List, Forkel & Hill 2022). A
universal segment prior earns its place at exactly one point in the pipeline:
seeding an alignment before correspondences are known. At that point, penalising
every manner-changing sound law is the wrong bias, because manner-changing laws
(spirantisation, affrication, lenition, debuccalisation) are precisely the ones
that make cognates hard to spot. Place-changing laws are rarer and easier.

**The honest positive result.** I ran a Needleman–Wunsch aligner over ten
Latin–Germanic cognate pairs across Grimm's Law and ten matched controls, with
`GAP = 0.55` and length-normalised cost. Cognates separate from controls at
AUC 0.850 (`broad`) and 0.920 (`distinctive`); mean cognate cost 0.310 vs
control 0.428 (`broad`). It works as a candidate generator. But the worst
cognate (`duo ~ two`, 0.496) exceeds the best control (0.352), and the
correspondences that push cognates into the control range are exactly the manner
changes (`d ~ t` is fine at 0.214; `k ~ h` at 0.250 is fine; but `p ~ f` at
0.357 and `t ~ θ` at 0.357 are not).

**Recommendation.**
1. Do not describe the number as a prior for the comparative method anywhere.
   The README's "candidate generation, exploratory comparison" framing is right;
   keep it and make the manner/place asymmetry explicit in `docs/geometry.md`,
   with the `d(k,tʃ)` vs `d(k,q)` decomposition above.
2. Ship a documented `place-heavy` weight preset (e.g. `Manner: 0.5`,
   `Place: 1.5`) so users can compensate without editing the geometry. This is
   cheap and honest — a knob, labelled as a knob, like `lenition-bias.json`.
3. Longer term, the prior review's Finding 1 option C (a learned pair-cost
   table) is the only real answer, and the correspondence-pattern literature
   already provides the training signal.

---

### F6 (P1) — Glides are maximally distant from their vowel counterparts

**Evidence.**

| pair | `broad` | `distinctive` | reference |
| --- | ---: | ---: | --- |
| `w ~ u` | **0.7750** | 0.5714 | |
| `j ~ i` | **0.7750** | 0.5714 | |
| `ɰ ~ ɯ` | 0.7750 | 0.5714 | |
| `ɥ ~ y` | 0.7750 | 0.5714 | |
| `ʔ ~ a` | 0.7750 | 0.7500 | (for comparison) |
| `n ~ a` | 0.7750 | 0.6719 | (for comparison) |
| `w ~ v` | 0.3571 | 0.3448 | |

In `broad`, `d(w, u)` is *numerically identical* to `d(ʔ, a)` and `d(n, a)`.

**Cause.** `/w/` and `/j/` carry `consonant` and `approximant`; the `vocoid`
leaf at weight 1.0 fires at full strength. In `distinctive` the effect is
tripled: `vocoid`, `sonorant` (+`vowel` / −`consonant`) and `syllabic`
(+`vowel` / −`consonant`) are three near-collinear dimensions all separating C
from V.

**Why it matters.** Vowel–glide alternation is the single most common
non-identity correspondence in comparative work: PIE *w*/*u* and *y*/*i* ablaut,
Latin `u`~`v`, Sanskrit sandhi, Austronesian glide formation, Greek digamma
loss. Scoring `u ~ w` at the same cost as `a ~ ʔ` guarantees that any aligner
using this prior will prefer a gap over the correct correspondence in exactly
those cases.

**Recommendation.** Leave `vocoid` unspecified (value 0) for approximants,
rather than `−1`. That gives glides a half-cost against both vowels and true
consonants, which is the linguistically right answer and is a one-line change to
the `sonorant`/`vocoid` dimension definitions. Alternatively model sonority as
an ordered scale rather than a binary. Acceptance test:
`d(w, u) < d(w, p)` and `d(j, i) < d(j, t)`, neither of which holds today: in
`broad`, `d(w, u) = 0.775` against `d(w, p) = 0.571`, and `d(j, i) = 0.775`
against `d(j, t) = 0.625`. The glide is further from its own vowel than from a
stop.

---

### F7 (P1) — The most basic manner and place features are inert; the new Laryngeal and TongueRoot leaves are decorative

**Evidence.** I enumerated every feature label the categorical systems can
return over all 7,356 graphemes reachable through `classes.tsv`, and checked
each geometry leaf for activation. These leaves are **never** activated by any
grapheme in any bundled categorical model:

| leaf | poles | weight |
| --- | --- | ---: |
| `sonorant` | `sonorant` / `obstruent` | 0.5 |
| `continuant` | `continuant` | 0.5 |
| `anterior` | `anterior` | 0.333 |
| `distributed` | `distributed` | 0.333 |
| `strength` | `strong` (fortis) | 0.5 |
| `centralization` | `centralized` | 0.333 |
| `mid_centralization` | `mid-centralized` | 0.333 |
| `rhotacized_feature` | `rhotacized` | 0.333 |
| `pre_labialized_feature` | `pre-labialized` | 0.333 |
| `pre_palatalized_feature` | `pre-palatalized` | 0.333 |
| `stress_feature` | `primary-stress` | 0.5 |

`atr` is activated by exactly one grapheme (`retracted-tongue-root` ×1,
`advanced-tongue-root` ×0).

The consequence is that all manner distinctions run through the `Manner` *group
boolean*, which lumps `{stop, fricative, approximant, trill, click, implosive}`
into one bit. So the Manner contribution to `d(p, f)`, `d(p, r)`, `d(ǃ, ɓ)` and
`d(k, ʔ)` is identical. Likewise all six coronal places
(`dental, alveolar, post-alveolar, retroflex, alveolo-palatal, linguolabial`)
are one `Coronal` bit, and ten dorsal/vowel-height labels are one `Dorsal` bit.

Empirically, a click is exactly equidistant from a velar and a coronal stop —
`d(ǃ, k) = d(ǃ, t)` to the last digit, 0.4211 in `broad` and 0.3194 in
`distinctive` — because `/ǃ/` carries both `alveolar` and `velar`, so both group
booleans fire either way.

**On `strong` under Laryngeal specifically** (the review question). Fortis/lenis
is not a laryngeal feature in any standard treatment — it is a cover term for a
bundle of duration, aspiration and articulatory tension (cf. Jakobson, Fant &
Halle's tense/lax). Placing it under Laryngeal is defensible only as a rough
proxy for aspiration/voicing. But since no bundled grapheme carries it, the
placement is untestable and contributes nothing. The same applies to
`centralized`, `mid-centralized`, `rhotacized`, `pre-labialized`,
`pre-palatalized`, `primary-stress`. The response counts these as coverage
work; they are inert either way.

**On ATR.** Advanced/retracted tongue root vowel harmony is the defining
prosodic system of much of Niger-Congo and Nilo-Saharan. One grapheme carries
`retracted-tongue-root` and none carries `advanced-tongue-root`. The `TongueRoot`
node exists and weighs 0.5, and does nothing.

**Recommendation.** The problem is not the geometry, it is that the inventory
NAME strings never say `sonorant`, `obstruent`, `continuant`, `anterior` or
`ATR`. Derive them: `sonorant` from `{nasal, lateral, approximant, trill, tap,
vowel}`, `continuant` from `{fricative, approximant, trill, vowel}` vs
`{stop, affricate, nasal, implosive, click}`, `anterior`/`distributed` from the
coronal place labels — the `distinctive` model already does exactly this in its
`scalar_dimensions`, so the mapping exists and just needs to be applied to the
geometry path. Until then, `docs/geometry.md`'s table of "placements added for
coverage" should mark which of them no bundled model can reach.

---

### F8 (P1) — The inventory is not a balanced segment catalog, and contains three outright data errors

**Evidence.** The 778-grapheme categorical inventory decomposes as 665
consonants and 113 vowels. By place:

```
dental 501   velar 32   post-alveolar 29   alveolar 21   retroflex 15
bilabial 13  palatal 13  uvular 13  linguolabial 12  labio-dental 9
alveolo-palatal 8  glottal 4  labial 3  epiglottal 3  labio-velar 2
pharyngeal 2  labio-palatal 1  palatal-velar 1
```

**64% of the inventory is dental.** By base segment (stripping modifiers):

```
d 62   l 54   r 48   dz 47   t 47   n 45   z 41   s 37   ɬ 35   tɬ 32   ts 29
...
p 2    k 2    b 2    m 1    g 1    ŋ 1    f 1    v 1    ʃ 1    x 1    j 1    w 1
```

`/d/` gets 62 modified forms; `/m/`, `/g/`, `/ŋ/`, `/f/`, `/w/`, `/j/` get one
each. This is not a designed catalog; it looks like a coronal-heavy slice of a
larger source that was never completed or rebalanced.

Data errors found:

1. **A grapheme spelled `k` + U+F268** — "voiceless velar lateral affricate".
   U+F268 is in the Unicode **Private Use Area**: it has no standard meaning,
   is not interchangeable between systems, and renders only under a private
   font mapping. Presumably intended as `kʟ̝̥`, or the modern U+1DF04. It is the
   only PUA codepoint in the inventory.
2. **`oz̻`** — "voiced laminal alveolar sibilant fricative". The leading `o` is
   spurious; the segment is `z̻`. The library accepts `oz̻` as a single segment
   and returns consonant features for it.
3. **`ǃǃ`** — used for the retroflex click. Because `system_segment_ipa` does
   greedy longest match, a genuine sequence of two alveolar clicks is
   untokenizable: `merkmal.system_segment_ipa("ǃǃa") -> ["ǃǃ", "a"]`.

**Why it matters.** Any aggregate computed over the inventory — mean distance,
nearest-neighbour statistics, a normalisation constant, a distance
distribution used to set a cognate threshold — inherits the coronal skew. This
is separate from, and in addition to, the "these are segment types, not a
language sample" caveat the README already makes: even as a catalog of *types*
it is not balanced.

**Recommendation.** State the skew in the README next to the existing typology
disclaimer (one sentence: "the categorical inventory is dominated by modified
coronals and is not a balanced sample of segment types either"). Fix or remove
the three bad rows. If the coronal expansion was deliberate, document why.

---

### F9 (P1) — `classes.tsv` ships a sound-class scheme with a plain linguistic error and a leftover debug class

**Evidence.** `models/*/classes.tsv` defines 20 classes. Two are wrong:

| class | description | definition | members |
| --- | --- | --- | ---: |
| `R` | "resonant" | `consonant,-stop` | 4,558 |
| `XXX` | "development" | `vowel,open,front,unrounded,long,nasalized` | 7 |

Class `R` contains `/s/`, `/f/`, `/z/`, `/tʃ/` — defining resonant as "consonant
and not stop" makes every fricative and affricate a resonant. 4,558 of 7,356
graphemes (62%) are labelled resonant.

Class `XXX` "development" is a leftover: its members are
`ã̤ː ḁ̯̃ː ãː̈ ãː̟ ḁ̃ː ã̯ː ãː`, its FEATURES field is just the feature list of `ãː`, and
"development" is not a linguistic description.

The scheme is also not a partition — the classes are overlapping predicates with
no assignment function, so `/k/` is simultaneously in `C`, `K`, `S`, `SVL`. And
compared with a Dolgopolsky-style class alphabet (as used for cognate detection
in LingPy), it is missing precisely the distinctions such schemes exist to make:
no coronal-obstruent class, no separation of `/m/` from `/n/`, no glide class.

**On the typology disclaimer** (the review question). The README's disclaimer is
correctly *worded* but incorrectly *scoped*. It disclaims typological
frequency, inventory membership, and sampling weight, and no API function
returns a typological statistic — that part is fine. But `classes.tsv` is a
shipped, authoritative-looking artefact with no documentation, no provenance
manifest entry, no validation beyond a row count
(`scripts/validate_models.py:337-343` only reports `len(cr)`), and no API. It is
the most likely thing in this repository for someone to load directly with
`pandas.read_csv` and treat as a sound-class scheme. Its class-membership counts
(4,558 "resonants") are exactly the shape of a statistic that looks typological
and is not.

Mitigating: `classes.tsv` is **not** in `MANIFEST.in` and therefore not shipped
in the sdist or wheel. It is repo-only (and duplicated under `go/data/`).

**Recommendation.** Either fix `R` (`consonant, +{nasal, lateral, approximant,
trill, tap}`), delete `XXX`, document the scheme's provenance and intended use,
and validate class definitions against the feature vocabulary — or delete
`classes.tsv` from the active tree and move it to `docs/legacy_python/`
alongside the other archived material. Half-shipping it is the worst option.

---

### F10 (P1) — Descriptive cluster and diphthong synthesis is unprincipled

Six separate problems in `mk_synthesize_descriptive_consonant_cluster` and
`mk_synthesize_vowel_cluster`.

**(a) A two-item hardcoded blocklist.** `src/system.c:1649`:

```c
if (mk_streq(normalized, "mb") || mk_streq(normalized, "nd")) {
    return MK_ERR_UNKNOWN_GRAPHEME;
}
```

`mb` and `nd` are rejected while `mp`, `nt`, `ŋg`, `ŋk`, `ndz`, `ntʃ`, `ŋm`,
`mm`, `nn` are all accepted as clusters. These are the two most frequent NC
sequences in the world's languages (Bantu, Austronesian, Mesoamerican). If the
concern is ambiguity between a prenasalised unit and a cluster, it applies
identically to `mp` and `nt`. The documentation
(`docs/c-api.md:110`, `python/README.md:53`) states the policy but gives no
linguistic rationale.

**(b) `pre-nasalized` is asserted for any nasal-initial cluster.** Therefore the
geminates `mm` and `nn` are marked `pre-nasalized`, as is `ŋm` — which is a
doubly-articulated labial-velar nasal (Yoruba, Ewe, Igbo), not a prenasalised
segment.

**(c) `/kp/` is a unit, `/ŋm/` is a cluster.** `kp` resolves to a single
`labio-velar stop`; its nasal counterpart `ŋm` resolves to a two-component
cluster. These are the same phonological object type.

**(d) Affricates break apart inside clusters.** `system_segment_ipa` correctly
returns `["tʃ", "a"]` for `tʃa`, but the cluster parser returns
`n1-stop / n2-fricative / n3-…` for `ntʃ` and `tʃk`. So `/ntʃ/` is represented
as *n + t + ʃ*, not *n + tʃ*.

**(e) Doubled spellings of long/geminate segments are further from the
length-marked form than the plain segment is.**

```
d(aa, aː) = 0.3057     d(a, aː) = 0.1429
d(pp, pː) = 0.3263     d(p, pː) = 0.1250
```

`aa` is analysed as a diphthong with `move-height-open-open`. Doubled vowels and
consonants are standard orthographic practice for length in Uralic, Austronesian
and much African data, and appear constantly in CLDF wordlists.

**(f) Every synthesised cluster label is unknown to the geometry.**

```
merkmal.feature_distance("diphthong", "consonant")           -> 999
merkmal.feature_distance("n1-front", "consonant")            -> 999
merkmal.feature_distance("move-height-open-close", ...)      -> 999
merkmal.feature_distance("geminate" | "complex" | "consonant-cluster", ...) -> 999
```

These are returned to callers and never scored. This is the exact "dead label"
condition the response claims to have eliminated ("Labels unable to affect any
distance: 0"); the checker enumerates only the 778 inventory graphemes, so it
never sees them. Clusters are scored through a separate component-averaging
path, which is a reasonable design — but the labels are then decorative, and a
caller reading `move-height-open-close` reasonably assumes it participates.

Consequences visible in numbers: `d(ai, ia) = 0.1333 = d(ai, au)`. A rising and
falling diphthong with reversed trajectories are as close as `/ai/` and `/au/`,
because only the positional component distances count and the `move-*` features
do nothing.

**Recommendation.** Delete the `mb`/`nd` blocklist or extend it to a principled,
documented rule. Emit `pre-nasalized` only when the first component is a nasal
*and* the second is a non-nasal obstruent. Treat `ŋm` as a unit like `kp`. Run
cluster components through the same longest-match tokenizer as
`mk_system_segment_ipa`. Map `aa`/`pp` to the length representation (or document
that they are not). Either register `diphthong`/`n1-*`/`move-*` in the geometry
or mark them in the API docs as descriptive-only, unscored annotations.

---

### F11 (P1) — Length is a set of unordered flags, not a quantity

**Evidence** (`broad`):

```
d(a, ă)   = 0.1429     # ultra-short
d(a, aˑ)  = 0.1429     # half-long
d(a, aː)  = 0.1429     # long
d(a, aːː) = 0.1429     # (collapses to long, see F1)
d(aˑ, aː) = 0.2500     # half-long vs long is FURTHER than plain vs long
d(ă, aː)  = 0.2500
```

Four privative leaves (`long`, `mid-long`, `ultra-long`, `ultra-short`) under
`Prosodic > Length`, each independent. Nothing encodes that ultra-short < short
< half-long < long < ultra-long.

Additionally, `V̆ː` (breve + length mark) yields **both** `ultra-short` and
`long` on the same segment, for all 21 vowels tested. That is a contradiction the
representation permits and the validator does not catch.

**Why it matters.** Finnic three-way quantity, Latin and Greek vowel length,
Estonian's Q1/Q2/Q3, compensatory lengthening, and mora-based reconstruction all
require length to be ordered. The current model cannot express "one step
longer".

**Recommendation.** One ordered scalar dimension over
`{ultra-short, short, half-long, long, ultra-long}` mapped to `[-1, 1]`,
replacing the four privative leaves. Reject `V̆ː`-type contradictions in the
diacritic composer.

---

### F12 (P2) — Weight coherence of the new subtrees

Taking the review's specific questions in order.

**Is major class at weight 1.0 proportionate?** For alignment, yes. Restricting
C–V matching is standard practice (Kondrak's ALINE and LingPy's SCA both do it),
and the resulting C–C / C–V separation is broadly what an aligner wants. Two
caveats: (i) the glide problem in §F6 is a real cost of the hard binary; (ii) the
1.0 in the denominator compressed every within-class contrast by ~40% (§F5), and
that is not documented.

**Are `advanced`/`retracted` and `raised`/`lowered` sensibly one `Shift`
node?** As bookkeeping, yes — they are both "small articulatory displacement"
diacritics and grouping them keeps them from each costing as much as a place
change. But note the weight: a `Shift` leaf is at depth 3 (w = 1/3), the same
weight as the entire `Dorsal` group boolean. So `t` vs `t̟` (advanced) costs the
same as `t` vs a different dorsal place. That is too much for a diacritic whose
whole point is sub-phonemic adjustment. `Shift` should sit deeper, or its leaves
should carry an explicit reduced weight.

**Does `[high]`/`[back]` double duty make `/k/` implausibly close to `/u/`?**
Only in the valued systems and `distinctive`, and the effect is small.
`distinctive`: `d(k, u) = 0.6786` vs `d(k, i) = 0.7500`; `pbase-hc`:
`d(k, u) = 0.443` vs `d(p, a) = 0.518`. The dimension definitions
(`high` +: `close, near-close, palatal, palatal-velar, velar, labio-palatal,
labio-velar`; `back` +: `back, near-back, uvular, velar, labio-velar`) reproduce
the standard SPE analysis (Chomsky & Halle 1968), where velars are
`[+high, +back]`. So it is defensible phonology with a mild and predictable
artefact: velars are pulled toward back vowels and palatals toward front vowels.
Given §F2, this is not where I would spend effort. In the *categorical*
geometry the question does not arise: `/k/` carries only `velar`, which reaches
the `Dorsal` group boolean and never the `high`/`back` leaves.

**Is `strong` (fortis) under Laryngeal right?** No, but it does not matter — no
bundled grapheme carries it (§F7). Fortis/lenis is a duration + tension +
aspiration bundle, not a laryngeal primitive. Remove the leaf rather than
defend the placement.

**Are `Release` and `Secondary` coherently weighted?** `Secondary` has eight
leaves at depth 3 (w = 1/3 each). So `t` vs `tʲ` costs 1/3 — the same as a full
place change, and the same as any one of `Release`'s four leaves. Palatalisation
is a first-order historical process (Slavic, Goidelic, Sinitic, Bantu) and
`unreleased` is a narrow-transcription detail; giving them equal weight is
incoherent. Either flatten `Release` into `Manner` and accept that several
release differences cost as one, or push `Release` deeper. As it stands, an
unreleased final stop is treated as a comparably large event to velarisation.

---

### F13 (P2) — The valued systems have no major-class dominance, and the README does not say so

`pbase-jfh` maps `vocalic` to `Manner` (weight 0.5); no valued system has a
Root-level major-class dimension. Result:

| system | `d(p, a)` | `d(p, s)` | ratio |
| --- | ---: | ---: | ---: |
| `broad` | 0.775 | 0.526 | 1.5 |
| `distinctive` | 0.750 | 0.469 | 1.6 |
| `pbase-jfh` | 0.421 | 0.237 | 1.8 |
| `phoible` | 0.333 | 0.128 | 2.6 |

The response's headline improvement is categorical-only. The README lists the
eight systems without noting that they have materially different scoring
semantics beyond metric/non-metric.

---

### F14 (P2) — JFH acoustic features are mapped onto an articulatory tree

`models/pbase-jfh/model.json` maps `grave → Place`, `compact → Dorsal`,
`diffuse → Dorsal`, `flat → Labial`, `sharp → Coronal`. These are *acoustic*
features from Jakobson, Fant & Halle (1952); they have no articulator-node
interpretation, and `grave` in particular cuts across labial, velar and
pharyngeal places by design. Because `tools/generate_c_data.py` derives each
dimension's weight as `1 / depth(mapped_node)`, this theoretically arbitrary
assignment directly sets the numbers: `grave` gets 0.5 (Place, depth 2),
`compact` and `diffuse` get 0.333 (Dorsal, depth 3).

Not urgent — `pbase-jfh` is a niche model — but the file should carry a note
that the mapping is a weighting device, not a claim about JFH.

---

### F15 (P2) — `typologies/lenition-bias.json` targets features the data never supplies, and contradicts its own rationale

The file's stated rationale is "Losing stricture is cheaper than gaining it".
Three of its five keys are `continuant`, `sonorant`, `nasal`; `continuant` and
`sonorant` are never activated by any categorical grapheme (§F7), so the bias
would be a no-op for the two features that carry most of its intent.

Separately, `voice: {pos_to_neg: 0.85, neg_to_pos: 1.15}` makes
voiced → voiceless the *cheap* direction. On the standard lenition scale
(voiceless stop > voiced stop > fricative > approximant > zero; cf. Lass 1984,
Kirchner 1998) voicing is a lenition and devoicing a fortition, so the sign
appears inverted relative to the file's own description. Since the file is inert
this is harmless today, but it is the same class of error the CoreCog quarantine
note calls out as "a plain bug" (point 3 of `typologies/README.md`), in a file
the README presents as usable.

---

### F16 (P2) — `segmental` / `ignore-prosodic` discards nasalisation with length

```
d(a, ã), preset="segmental"     -> 0.0
d(a, aː), preset="segmental"    -> 0.0
d(t, tʲ), preset="segmental"    -> 0.0
```

`Prosodic` groups length, nasalisation, secondary articulation, ejectivity and
stress, so zeroing it zeroes all five. A user comparing languages with different
length transcription conventions (the usual reason to reach for `segmental`)
silently loses the nasal contrast — which is phonemic in French, Portuguese,
Hindi, Yoruba, and much of Amazonia. Ejectivity too, which is phonemic
everywhere it occurs.

**Recommendation.** Add `ignore-length` (`Length: 0.0`) as a preset. Nasalisation
and ejectivity should arguably not live under `Prosodic` at all — they are
segmental contrasts, not prosody — but at minimum the presets should let users
separate them.

---

## Verification of `docs/review-response.md`

### Verified

| Claim | Result |
| --- | --- |
| 7 zero-distance pairs per categorical system | **Verified and strengthened.** Over the full 7,356-grapheme recognition space reachable via `classes.tsv` (not just the 778-row inventory), I find exactly 7 identical-feature groups per system, the same 7 pairs. |
| `broad` and `descriptive` are operationally identical | **Verified.** `inventory.tsv` files are byte-identical; 0 of 30,000 sampled pairwise distances differ. |
| Valued scorer is non-metric, with the stated counterexample | **Verified.** `pbase-hc`: `d(ðˠ, mʲ) = 0.311321 > d(ðˠ, d̪ʲ) + d(d̪ʲ, mʲ) = 0.094340 + 0.209119 = 0.303459`. |
| `pbase-jfh`'s `"vocalic "` trailing space fixed | **Verified.** `vocalic` is present in `geometry_map` and active. |
| Tone-bearing graphemes rejected in valued systems | **Verified for diacritics and Chao digits** — `a¹¹` and `á` both return `MK_ERR_UNSUPPORTED_MODEL` in `pbase-hc` and `phoible`. **Not true for standalone tone letters**: `phoible` accepts `˥˦` as a segment and scores it `0.0` against everything (§F1). |
| Chao runs of ≥4 digits rejected atomically | **Verified.** `a¹²³⁴` is rejected; tokenizer and recognizer agree. |
| Chao level 3 emits an explicit mid feature; `tone-present` on every tone-bearing form | **Verified for 1-digit and 3-digit runs.** **Not for 2-digit runs** — the mid slot is never filled, so `d(a¹, a¹¹) = 0.0741` (§F3). |
| `mk_system_segment_ipa` does system-aware longest match | **Verified.** `tʃa → [tʃ, a]`, `kpa → [kp, a]`, `t͡ʃa → [t͡ʃ, a]`, `a¹¹ma⁵⁵ → [a¹¹, m, a⁵⁵]`. |
| Geometry identity, `theory_fidelity`, non-empty `departures` | **Verified.** `merkmal-clements-hume-inspired-v1`, `inspired-by`, 5 departures, `clements-hume` retained as a compatibility name. Accurate and well done. |
| CoreCog prior quarantined under a renamed key | **Verified.** `quarantined_direction_costs`, `status: quarantined`, six reasons in `typologies/README.md`. The reasoning there is correct and the decision not to "fix" point 3 in place is the right call. |
| Runtime strict validation with `@validation permissive` opt-out | **Verified.** |

### Contradicted or materially overstated

| Claim | Finding |
| --- | --- |
| "Now every consonant–consonant pair scores below every consonant–vowel pair" | **False.** `broad`: max C–C = 0.8286 (`ɬ̪ʲʷʰ ~ ⁿgǃ`) > min C–V = 0.6600 (`r̪̃ː ~ ø̞̃ː`). `distinctive`: 0.7813 (`l̪̩ ~ pf`) > 0.5714 (`ɥ ~ i`). The cited test `test_major_class_dominates_within_class_differences` checks eight hand-picked pairs against `d(p, a)` only, and does not establish the general claim. |
| README: "every pair of distinct graphemes that scores zero" is in `contrast_baseline.tsv` | **False for five of eight systems** (42,508 undeclared zeros in `phoible` alone) **and false within `broad`** for 13 `Vː ~ Vːː` pairs plus every `Cː ~ Cːː` pair tested. The guard covers 3 systems and 778 graphemes (§F1). |
| "Labels unable to affect any distance: 0" | **True only for the 778-row inventory.** Descriptive synthesis returns `diphthong`, `triphthong`, `complex`, `geminate`, `consonant-cluster`, `n1-*`, `n2-*`, `n3-*`, `move-*`; the geometry knows none of them (§F10f). |
| Finding 3 "Done" — tone contrastively adequate | **Partly.** The 1- and 3-digit paths are fixed; the 2-digit path is not, and it is the commonest spelling. The resulting level metric is non-monotonic, `d(a, a³³) > d(a, a⁵⁵)`, IPA tone letters are unsupported, and 19 precomposed tone vowels are rejected while `normalize()` produces them (§F3, §F4). |
| CHANGELOG `3d21e08` "Support precomposed source vowels" | **Incomplete.** Caron, double grave and double acute are not covered, nor `y`, `æ`, `ø` bases; 19 forms rejected. |
| Finding 1 "Done" — categorical distance preserves contrasts | **For consonants, largely.** For vowels the fix did not reach the height dimension, which remains non-ordinal in both categorical systems (§F2). |
| Finding 8 "Accepted as scope" — typology out of the core | **Correct in the API, incomplete in the data.** `classes.tsv` ships an unvalidated, undocumented sound-class scheme with a plainly wrong `resonant` class and a leftover `XXX "development"` class (§F9). |

---

## What I would do next, in order

1. Extend `contrast_baseline.py` to all eight systems, and make
   `total_weight == 0` a distinguishable status rather than `0.0` (§F1).
2. Replace vowel height, backness, tone level and length with ordered scalar
   dimensions (§F2, §F3, §F11). These are four instances of the same mistake —
   encoding an ordinal scale as unordered booleans — and one design change fixes
   all four.
3. Fix the two-digit Chao path, normalise to NFD before lookup, and delete the
   14 stray-circumflex inventory rows (§F3, §F4).
4. Give approximants an unspecified `vocoid` value (§F6).
5. Derive `sonorant`, `continuant`, `anterior`, `distributed` from the place and
   manner labels, using the mapping `distinctive` already has (§F7).
6. Delete the `mb`/`nd` blocklist and fix `pre-nasalized` (§F10).
7. Fix or archive `classes.tsv` (§F9).

Items 1–4 are correctness. Items 5–7 are coherence. None requires data the
repository does not have.

---

## Works referenced

Accurate attributions only; where I am relying on general knowledge of a work
rather than a specific page, I have kept the claim correspondingly general.

- Chao, Y.-R. (1930). A system of tone letters. *Le Maître Phonétique*. — the
  origin of the 1–5 digit scale, which is ordinal.
- Chomsky, N. & Halle, M. (1968). *The Sound Pattern of English*. — the
  `[high]`/`[back]` analysis of velars that `distinctive` reproduces.
- Clements, G. N. & Hume, E. V. (1995). The internal organization of speech
  sounds. In Goldsmith (ed.), *The Handbook of Phonological Theory*. — the
  geometry's stated inspiration; proposes no metric, as `docs/geometry.md`
  correctly says.
- Haudricourt, A.-G. (1954). De l'origine des tons en vietnamien. *Journal
  Asiatique*. — tonogenesis from segmental sources.
- Jakobson, R., Fant, G. & Halle, M. (1952). *Preliminaries to Speech Analysis*.
  — the acoustic feature set underlying `pbase-jfh`.
- Kirchner, R. (1998). *An Effort-Based Approach to Consonant Lenition*. PhD
  thesis, UCLA. — lenition scales, relevant to §F15.
- Kondrak, G. (2000). A new algorithm for the alignment of phonetic sequences.
  *NAACL*. — feature-based alignment with major-class constraints.
- Lass, R. (1984). *Phonology: An Introduction to Basic Concepts*. — standard
  presentation of the lenition/fortition scale.
- List, J.-M. (2019). Automatic inference of sound correspondence patterns
  across multiple languages. *Computational Linguistics* 45(1). — correspondence
  patterns as the evidence base, not universal similarity.
- List, J.-M., Forkel, R. & Hill, N. (2022). Work on automated phonological
  reconstruction from trimmed alignments and correspondence patterns. — same
  point, applied to reconstruction.
- Matisoff, J. (1973). Tonogenesis in Southeast Asia. In Hyman (ed.),
  *Consonant Types and Tone*. — tone categories vs pitch realisation.
- Yip, M. (2002). *Tone*. Cambridge University Press. — register vs contour
  systems, and why a single pitch-distance measure does not serve both.
