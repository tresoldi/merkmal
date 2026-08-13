# Changelog

## Unreleased

### The last two cluster defects

- **Affricates survive inside a cluster.** `features("ntʃ")` parsed as
  *n + t + ʃ*, even though the tokenizer and the recognizer both read `tʃ` as one
  segment everywhere else — the component parser was the one path still
  splitting by letter. It now looks one unit ahead and prefers a two-letter
  segment when the inventory or the complex synthesizer knows one, which is all
  the affricates and the doubly-articulated `kp`/`gb`/`ŋm` need.

  The lookahead consults the inventory and the complex synthesizer only, never
  the cluster grammars, so `mb` and `nd` stay the two-component clusters they
  are rather than being merged by a rule that would swallow any adjacent pair.

- **A doubled spelling is no longer charged for its own length.** The
  per-component penalty put `aa` at 0.233 from `aː` while a plain `a` sat at
  0.064 — so a doubled vowel was further from the long vowel than a short one
  was, and doubling is how Uralic, Austronesian and much African data write
  length. The penalty is waived when a geminate cluster meets a length-marked
  segment, because there the length it charges for is exactly what the other
  side spells out. `d(aa, aː)` is 0.113 now, below `d(aa, a)` at 0.159.

  **Waived, not reversed.** `aa` lands where `a` does rather than closer,
  because whether a doubled vowel means length or a genuine sequence is a
  property of the source that nothing here can read per form. Asserting it means
  length is the move that cost a PHOIBLE contrast when it was applied to `ɫ`
  earlier in this release. A non-geminate cluster such as `ai` still pays the
  penalty in full.

### Coverage alongside the score, and one segment series made whole

- **`mk_system_segment_distance_ex` / `merkmal.distance_with_coverage`.** A
  valued system skips any dimension where either segment has no value, so a
  score of `0.0` meant either "identical" or "nothing in common to compare" and
  a caller could not tell which. The first independent review found the sharp
  case: PHOIBLE's tone letters carry `.` on every dimension, so `˦˨` scored a
  confident `0.0` against every segment in the table, `/a/` included.

  The score is unchanged — inventing values to separate them would be
  fabricating data — but `coverage` now reports the share of the system's
  declared dimensions both segments actually had a value on. `d(˦˨, d)` is
  `(0.0, 0.0)`; `d(e, i)` in P-base UFTC, which is genuinely indistinguishable
  there, is `(0.0, 0.75)`. Same score, and now visibly not the same claim. The
  library sets no threshold: what counts as too weak a comparison depends on the
  work.

  Categorical systems score over the union of what either segment specifies, so
  the ambiguity cannot arise and coverage is 1.0 there by construction.

- **`ŋm` is one segment, not a cluster.** It is the nasal member of the `kp`/`gb`
  series — Yoruba, Ewe, Igbo — and was the one left as a two-component cluster,
  which scored it 0.73 from `kp` where `gb` sits at 0.18. Now 0.38 from `kp`,
  0.23 from `gb`, and close to both `ŋ` and `m`, which is what a doubly
  articulated segment should look like.

  Worth recording that this is a **departure from CLTS**, and a deliberate one:
  CLTS v1.4.1 reads `kp` as "from voiceless velar stop to voiceless bilabial stop
  cluster". The library already departed for `kp` and `gb` because the standard
  analysis in the languages that have them is a single segment. Extending it to
  `ŋm` makes the series coherent; leaving it out was the anomaly.

### Numeric feature vectors

`mk_system_feature_vector`, `mk_system_vector_labels`, `mk_system_vector_width`,
and `merkmal.feature_vector` / `merkmal.vector_labels` in Python. Everything
else in this library returns feature *labels* — the right shape for reasoning
about a segment, the wrong one for a model that wants numbers, which is why the
neural-phonology audience has used PanPhon instead.

The encoding follows `soundvectors` (Rubehn, Nieder, Forkel & List 2024), so the
numbers mean what the ecosystem already means by them: `+1` present, `-1`
applies and is absent, `0` does not apply or the source does not say.

That third value is the reason this belongs in the library rather than in each
caller. A valued system writes `anterior=.` for "no value" and `anterior=-` for
"absent", and a hand-written mapping tends to collapse them — silently, and in
the direction that makes a model confident about data it does not have.

**Ordered scales** cannot use `0` for a middle level, because `0` already means
"no value". A scale of *n* levels maps level *i* to *i/n*, so scale columns land
in `(0, 1]`. `vowel_height` is 0.14 for `/i/`, 0.43 for `/e/`, 1.0 for `/a/`, and
0 for `/p/`, where the scale does not apply at all.

**The basis differs by system**, because the systems differ: a valued system's
columns are its own inventory columns, a system declaring `scalar_dimensions`
uses those, and the rest use the geometry they score through. Widths are 54
(`distinctive`), 62 (`descriptive`), 38 (`phoible`), 23 (`pbase-hc`). Ask
`vector_labels` rather than assuming width or order; labels are unique within a
system, so a column is addressable by name.

No call vectorizes a token list. That is a loop, and sequence-level operations
are not this library's (`REFERENCE_LIBRARY_PLAN.md`, D2).

### Source markup says so, and two CLTS spellings resolve

- **New status `MK_ERR_SOURCE_MARKER`**, and `merkmal.SourceMarkerError` in
  Python. `<?>` is CLTS's mark for a grapheme *the source* could not convert,
  `<<...>>` is CLDF's escape for unparsed source material, and `+`, `_`, `#` are
  boundary markers. All of them are correctly refused — they are not sounds —
  but refusing them as `MK_ERR_UNKNOWN_GRAPHEME` told a caller the wrong thing:
  that merkmal lacked the segment. In Lexibank they are 33,275 tokens, so a
  transcription-QC pass could not tell its own gaps from other people's without
  string-matching the input itself.

  The Python exception subclasses `ValueError`, so code already catching that is
  unaffected; catch `SourceMarkerError` to skip the source's known gaps without
  swallowing segments the library genuinely lacks. `is_segment` stays total and
  still returns `False`. The status is **appended** to `mk_status`, so existing
  values keep their numbers.

  Deliberately narrow: the documented CLDF/CLTS conventions only. Dataset-local
  noise such as `→` and `∼` stays an unknown grapheme rather than being swept in
  on a guess about what its author meant.

- **`ǝ` resolves.** U+01DD TURNED E is a source convention for schwa, named
  "unrounded mid central vowel" in CLTS v1.4.1 — the name this inventory already
  gives U+0259 — and no bundled model carries it as a row of its own.

  **`ɫ` deliberately does not.** It was mapped to `lˠ` on the same CLTS reading
  and then taken out: PHOIBLE carries `ɫ` as its own inventory row with feature
  values that differ from `lˠ`, and the source-conventions table is applied
  before lookup and unconditionally, so the mapping destroyed a contrast PHOIBLE
  draws rather than adding a spelling merkmal lacked. `scripts/contrast_baseline.py`
  caught it as a single new zero-distance pair in `phoible`.

  The general defect this exposed — a source convention can override a grapheme
  the system actually has — is unfixed. It needs the resolver to try the written
  form before the rewritten one. Until then the rule is that nothing enters that
  table which any model lists as a row.

### The default is `distinctive`, and `broad` is deprecated

**Breaking, for anyone who calls without naming a system.** The default moves
from `descriptive` to `distinctive`, so `merkmal.distance("p", "b")` returns
0.1493 where it returned 0.125. Stored results computed against the old default
must be recomputed or pinned with `system="descriptive"`.

The choice is now purely about which scores better, because after the cluster
work the two recognize exactly the same graphemes — 0 disagreements over 7,396
Lexibank segment types. On BDPA gold alignments `distinctive` is not
statistically distinguishable from LingPy's SCA (−0.39%, CI crossing zero) where
the geometry-scored systems are measurably behind it (−0.79%).

**`broad` is deprecated** and will be removed in the next major version. It is
not merely "operationally identical" to `descriptive` as the README used to say:
it is now a pure duplicate, with 0 differences in feature sets, distances, or
recognition across the corpus. It still resolves, so nothing breaks today.

**A consequence worth stating, because the switch surfaced it.**
`mk_sound_distance` / `merkmal.sound_distance` is the *geometry* scorer and takes
no system. `distinctive` scores through its own `scalar_dimensions`. So feeding a
segment's default features into `sound_distance` no longer reproduces what
`distance` returns for that segment — 0.125 against 0.1493 for `p`~`b`. The two
agree only for the geometry-scored systems (`descriptive`, `broad`). There is now
a test asserting the divergence in both directions, so it is a stated property
rather than something a user discovers.

### Every categorical system reads what `descriptive` reads

Diphthongs, consonant clusters and complex segments such as `kp` were
synthesized for `descriptive` and refused by `broad` and `distinctive`, on a
hardcoded check of the system's *name*. Nothing about the synthesis was ever
descriptive-specific: components resolve through whichever system is asking, and
the cluster scorer in `system.c` never looked at the name either.

That mattered little while `descriptive` was the system to reach for. It
mattered a great deal with `distinctive` about to become the default, because
the default would have been the system least able to read the field's data —
1,188 segment types and 78,762 Lexibank tokens it rejected and `descriptive`
accepted.

| | before tone work | after tone | now |
| --- | ---: | ---: | ---: |
| `distinctive` types | 73.4% | 78.5% | **94.5%** |
| `distinctive` tokens | 95.57% | 99.16% | **99.71%** |
| median dataset, forms parsed | 95.9% | 98.2% | **100.0%** |
| datasets below 90% of forms | 52 | 27 | **3** |
| datasets below 3% of forms | 26 | 1 | **1** |

**On the alignment benchmark this restores parity with SCA**, and on a sounder
footing than the claim retracted earlier in this file. The readable subset is
now 2,091 of 2,250 pairs (**92.9%**, from 64.4%), and over it `distinctive`
scores 96.16% against SCA's 96.72% — a difference of −0.39% with a 95% CI of
[−0.95, +0.15], **not significant**. Over all pairs it is 95.00% against 96.35%.
Every point of that came from reading more data; nothing about how segments
score was changed.

- Cluster parses report `n1-`/`n2-`/`n3-` component labels, `move-` trajectories,
  and `diphthong`/`triphthong`/`complex`/`geminate`/`consonant-cluster`. None of
  them score — clusters are scored through their components — and they are now
  **declared** as unscored in the geometry, by prefix for the open-ended ones.
  They had been returned to callers as if they participated since the cluster
  paths were written; an earlier review flagged it and it was never closed.
- The contrast audit sweeps cluster spellings, taken from Lexibank by token
  frequency. Like bare tone before them, they are recognized by every
  categorical system and carried by no inventory row, so an inventory-derived
  sweep never saw them.

### Tone as its own segment, which is how the field writes it

CLTS/BIPA spells tone as a segment in its own right — `t o ³³`, not `t o³³` —
and that is the form CLDF wordlists are published in. merkmal accepted tone only
bound to a nucleus, so it could not read the tonal half of the world's
languages as they are actually encoded.

- **Bare tone tokens are segments.** Chao digit runs of one to three levels and
  IPA tone letters U+02E5–U+02E9 resolve on a new `MK_RESOLVED_TONE` path,
  carrying the tone features they already had in bound position. `merge_tone_digits`
  converts between the two spellings and is unchanged.
- **Chao neutral tone `⁰` is recognized, and is not a pitch level.** It is the
  notation for a syllable carrying no tone in a language that otherwise has
  tone — 8.3% of the tone tokens in `beidasinitic`, and that dataset's single
  largest blocking token. It gets its own privative `tone-neutral` feature
  rather than being folded into level 3 (which would claim it is mid) or level 1
  (which would claim it is low). It has no pitch target and says so.
- **Rejected, with a parse error rather than an unknown-grapheme error:** runs of
  four or more levels, and `⁰` mixed with a pitch level. The distinction matters
  — it says the token *is* tone and is spelled wrong.
- **Valued systems refuse bare tone** with `MK_ERR_UNSUPPORTED_MODEL`, the same
  policy they already applied to bound tone, because none of them declares a
  dimension a tone can move and the alternative is a confident zero.
- Tone tokens carry `tonal-autosegment`, declared in `metadata_features` and
  deliberately **not scored**. What a tone should cost against a segment is open;
  see `REFERENCE_LIBRARY_PLAN.md`. Today they compare through the geometry like
  anything else, which is a placeholder, not an answer.

**Coverage, measured over 152 Lexibank datasets** (`bench/bench_coverage.py`):

| | before | after |
| --- | ---: | ---: |
| `descriptive` tokens | 96.12% | **99.71%** |
| `broad` / `distinctive` tokens | 95.57% | **99.16%** |
| `descriptive` types | 89.5% | **94.5%** |
| datasets below 90% token coverage | 37 | **1** |
| datasets below 3% of forms parsed | **26** | **1** |
| median dataset, forms fully parsed | 95.9% | **98.2%** |

The one dataset still blocked is `williamsonbenuecongo`, which contains no tone
at all and fails on CLTS's `<?>` and `<<->>` markers.

On the alignment benchmark, reading tone made 258 more BDPA pairs usable — the
readable subset goes from 69.8% to **81.2%** — and improved the result rather
than diluting it. `distinctive` moves from 92.91% to **93.62%** column accuracy
over all pairs, narrowing the gap to SCA from −3.09% to −2.60%, and holds
−0.66% [−1.21, −0.05] on the readable subset. The newly readable pairs are
tone-against-tone, where the ordinal Chao scale does the work; the unresolved
tone-against-segment cost rarely arises, which is the same conclusion the
saturation analysis reached from the other direction.

The contrast audit now sweeps the bare-tone recognition space and records 168
collapses, all of them one Chao contour spelled more than one way. Two things
that had not been written down anywhere fell out of doing it: a two-digit
contour fills its middle slot by **rounding the midpoint up**, so `¹²` is the
same tone as `¹²²` and a different tone from `¹¹²` — a rise reaches its target
early rather than late — and `distinctive` needed its own `tone_neutral` scalar
dimension, because a geometry leaf alone does not reach a system that scores
through `scalar_dimensions`.

### Two guards, and the bug the second one found

Both come from an adversarial review of a proposed tone design. Neither is about
tone; both are about checks that passed while the thing they claimed to check
was untrue.

- **`contrast_baseline.py` now checks that dimensions can be reached, not only
  that labels land.** It verified every label a system returns can move some
  distance, and never asked the reverse question of the artifact that does the
  scoring. For `distinctive` that artifact is its own `scalar_dimensions`, not
  the geometry, so **nine dimensions left behind by the ordinal tone rewrite**
  (`tone_onset_register`, `tone_mid_height`, and seven more) sat unreachable
  while the script printed "every scoring dimension is reachable". They are
  removed; `regenerate_golden.py --check` confirms no value moves, which is
  exactly why nothing caught them.
- **`validate_models.py` now checks that a model's scalar weights agree with the
  geometry leaves they mirror**, by asking the generator what it will emit
  rather than restating its rule. **Behavior change:** it found that an explicit
  `"weight"` on a geometry leaf was silently dropped on the scalar path, so
  `vocoid` was declared 0.8 in `geometries/clements-hume.json` and cost **1.0**
  in `distinctive` — a 25% overweight on major class, in the system intended to
  become the default, and `docs/geometry.md` documented neither number. Fixed in
  `tools/generate_c_data.py`.

  **This changes `distinctive` distances.** Measured over 24,090 pairs: mean
  distance −1.2%, per-pair ratios 0.72–1.12, and **2.69% of "is A closer than B"
  orderings flip** — a reordering, not a rescale, so a published correction
  factor cannot repair it. Stored `distinctive` distances, alignments, clusters
  and thresholds must be recomputed. On the alignment benchmark the change is a
  wash (96.79% vs 96.90% column accuracy, 94.52% vs 94.39% perfect); the reason
  to make it is that the two scoring paths now cost the same thing the same
  amount. `broad`, `descriptive` and the valued systems are unaffected — they
  score through geometry leaves, which already honoured the explicit weight.

### Two benchmarks that measure the library against the outside

Every existing guard measures merkmal against itself — golden fixtures, the
contrast baseline, the generated-data check — and all of them pass on a library
that is internally consistent and unusable in practice. These two do not.

- Added `bench/bench_coverage.py`, which measures what fraction of real CLDF
  wordlist data the library can read, and **runs in CI with per-system floors**
  so a regression fails the build. Against 152 Lexibank datasets (14,193,616
  tokens, 7,396 segment types) the current state is: `descriptive` 89.5% of
  types, `phoible` 79.2%, everything else 73.4–73.7%; token rates cluster around
  95.6%. The token rate flatters it. A form only parses if every one of its
  tokens does, and `bench/coverage_baseline.txt` records the consequence:
  **26 of 152 datasets have under 3% of their forms fully parseable**. Twenty-
  five of the 26 are blocked by tone — Sinitic, Hmong-Mien, Bai, Tai-Kadai,
  Lolo-Burmese, Karen — because CLTS/BIPA writes tone as its own segment while
  merkmal accepts it only bound to a vowel, and several of those datasets write
  it through the `source/BIPA` slash convention on top of that. The twenty-sixth,
  `williamsonbenuecongo`, has no tone tokens at all and is blocked by CLTS's
  `<?>` and `<<->>` markers.
- Added `bench/bench_alignment.py`, which scores the segment distance as an
  alignment substitution cost against LingPy's SCA classes on BDPA gold
  alignments, through an identical Needleman-Wunsch with the gap tuned per
  scorer on a held-out half. On pairs merkmal can fully read, `distinctive`
  reaches 96.79% column accuracy against SCA's 97.74% — close, but behind by a
  margin that is statistically significant (bootstrap 95% CI on the difference
  [-1.39, -0.24]). Over the whole benchmark it falls further behind (92.91% vs
  96.35%) because it cannot read 30% of the pairs. Coverage is worth several
  times more than the remaining modelling gap.
- Added `bench/corpus/`, an aggregate segment-frequency table with its own
  provenance manifest. It carries segment types and counts only — no forms,
  glosses, or language identifiers — so it does not redistribute the wordlists
  and does not inherit their licenses.

No library behavior changes.

### The data's provenance, established rather than asserted

No behavior changes: no feature set, distance, or golden fixture moves. What
changes is what the distribution says about where its data came from, and one
of those statements was wrong.

- **Corrected licensing.** `broad`, `descriptive` and `distinctive` declared
  `MIT`. They are derived from CLTS, so that was a misdeclaration in a shipped
  artifact. They now declare `CC-BY-4.0`, and the distribution declares
  `MIT AND CC-BY-4.0 AND CC-BY-SA-3.0 AND CC-BY-NC-SA-4.0`. Using these
  inventories obliges you to credit CLTS and indicate that changes were made.
- **The source is CLTS v1.4.1** (`d0dbd4bd`), established by diffing the
  inventory against every tagged CLTS release rather than from recollection:
  v1.4.1 matches 768 of 769 graphemes and 766 of 769 byte-identical NAME
  strings, against 689 and 680 for v2.0.0 and later. The three divergences are
  recorded in the manifests instead of being reconciled away. One of them is
  upstream's: v1.4.1 named `ʈʂː` "voiced", contradicting its own `ʈʂ` entry,
  and corrected it in v2.0.0.
- `classfeat` is **not** CLTS-derived — its inventory is `GRAPHEME`/`CLASS`,
  a sound-class alphabet with hand-assigned classes. It stays MIT.
- **PHOIBLE pinned to CLDF `cldf-datasets/phoible` v2.0.1** (`f36deac7f80b`).
  Content alone could not have settled this — v2.0, v2.0.1 and 3.0 match at
  98.9%, 99.5% and 99.7% of graphemes — so it stayed `UNVERIFIED` until
  answered from maintainer records rather than inferred. Its `CC-BY-SA-3.0`
  declaration was then checked against the pinned release and is correct:
  v2.0.1 declares no `dc:license` of its own, so PHOIBLE 2.0's own terms
  govern.
- **Recorded, not yet fixed:** the PHOIBLE extraction is not self-consistent.
  Against v2.0.1, 3,729 cells where upstream says `0` (not applicable) were
  written `-` rather than `.`, 761 where upstream specifies a value were
  written `.`, and 697 where upstream gives a contour were resolved to a single
  `+`/`-`. 95.43% of cells are accounted for by the intended transformation.
- Still `UNVERIFIED`: the four `pbase-*` models' release, commit and retrieval
  date, and PHOIBLE's retrieval date. P-base is distributed from a website
  rather than a versioned repository, so the diff method used above does not
  apply to it.
- Note for anyone auditing published artifacts: merkmal 0.1.0, 0.1.1 and 0.2.0
  on PyPI declare `MIT` and ship CLTS-derived data. Those releases are being
  left in place; the correction is to be disclosed on the project page.

## 1.0.0

The public C API is stable from here. Three breaking changes are batched into
this release and nothing else changes behavior; see the migration table in
[docs/c-api.md](docs/c-api.md).

- **Breaking (C):** `mk_free_string` is now `mk_string_free`. A rename only. It
  reads the way the other destructors already did — `mk_string_list_free`,
  `mk_registry_free` — type first, verb last. It was the one that read the
  other way round.
- **Breaking (C/ABI):** `mk_system_is_segment` reports through `bool *` rather
  than `int *`, and `merkmal.h` now includes `<stdbool.h>`. This is an ABI
  change wherever `_Bool` and `int` differ in size, which is most places, so it
  rides the SOVERSION bump: recompile rather than relink.
- **Breaking (C):** `mk_sound_distance` takes two `mk_feature_view` values in
  place of four arguments. `mk_feature_view` is now public — a value type
  holding a `const char *const *` and a `size_t`, borrowed for the call. It was
  already the internal scoring type; the public function was the one place a
  caller had to spell out both pairs and keep them aligned by hand.
- Added: `ctest` compiles `merkmal.h` on its own, and CI additionally compiles
  it as C++. A header that needs the caller to have included `<stddef.h>` first
  passes everywhere inside this project and fails for the first consumer who
  includes it before anything else.
- The exported surface is still 26 symbols. The Python API is unaffected.

The rest of 1.0.0, in the order it was done:

### The Python extension under sanitizers and warnings

- Added: the extension compiles at the library's warning set, minus
  `-Wcast-function-type` and `-Wmissing-prototypes`, which the CPython API
  forces on any extension. Not gated with `-Werror`, so a wheel build cannot
  fail on a warning from a compiler this project has not seen.
- Added: `MERKMAL_SANITIZE=address` builds the extension for a sanitizer run,
  and a CI job runs the wrapper suite under it with the interpreter's ASan
  runtime preloaded. `python/tests/lsan-suppressions.txt` covers the four
  CPython type allocations that live for the process, suppressed by frame
  rather than by library so that merkmal's own allocations are not covered too.
  The file also records what the job does not prove: LeakSanitizer scans the
  stack conservatively and did not report a deliberately injected leak, so leak
  coverage for the C core stays with the `ctest` suite under ASan.

### Fuzzing, static analysis, and a heap overread on malformed UTF-8

- **Fixed: a heap buffer overread on truncated UTF-8 input.**
  `mk_utf8_char_len` returned the length a lead byte *claims*, and nineteen
  call sites copied or skipped that many bytes without checking the string had
  them. `mk_segment_ipa("a\xF0")` read four bytes out of a two-byte
  allocation. Every public entry point that takes transcription text was
  affected: `mk_segment_ipa`, `mk_segment_ipa_merged`, `mk_normalize_grapheme`,
  `mk_split_tone`, and everything in the resolver reached through
  `mk_system_*`. It is now `mk_utf8_step(const char *)`, which never returns
  more than the bytes present, so a scan can neither read nor step past the
  terminator.
- Fixed: a synthesized feature label built from an over-long feature name was
  silently truncated into a different feature — one the geometry does not know,
  which therefore contributes nothing to any distance. Reachable through a
  runtime model, whose feature names are caller-supplied and unbounded.
  `mk_add_prefixed_feature`, `mk_add_movement_feature` and
  `mk_add_position_features` now return `MK_ERR_PARSE` rather than truncate.
  The two `snprintf` calls that build *diagnostics* still truncate, which is
  correct and now says so.
- Added: `fuzz/` with three libFuzzer harnesses covering the runtime-model
  parser, tokenization and normalization, and resolution against every built-in
  system. Built with `-fsanitize=fuzzer,address,undefined` behind
  `MERKMAL_BUILD_FUZZERS` (Clang only, off by default), seeded from the golden
  fixtures, and run for 60 seconds per entry point in CI.
- Added: `tests/c/test_malformed.c`, a `ctest` case replaying twenty malformed
  inputs — truncated sequences, bare continuations, invalid leads, and the
  shapes the synthesizers reach for — each in a heap buffer sized exactly to
  its bytes so an overread is visible to AddressSanitizer.
- Added: `scripts/run_static_analysis.sh` runs `gcc -fanalyzer` and
  `clang --analyze`, with the accepted findings documented in the script. CI
  fails on anything else.
- Internal: the tokenizer's five duplicated `realloc` blocks are one
  `mk_push_token`. One of them ran ahead of the branch that used it, leaving
  two `items[count++]` writes whose bound was only provable by an argument
  spanning forty lines — which Clang's analyzer reported as a null dereference,
  and which was the reason to leave the structure alone until the malformed
  cases and the fuzzers were in place to cover the change.

### Inventory lookup is a binary search: tokenization twice as fast

No public API, ABI, or behavior change; golden fixtures are byte-identical.

Grapheme lookup walked every row calling `strcmp`. The cost was linear in
inventory size at roughly 7.3 ns per row, a resolution performs up to three
lookups, and longest-match tokenization performs several resolutions per token.

| system | rows | miss, before | miss, after |
|---|---|---|---|
| descriptive | 769 | 5.6 µs | 0.07 µs |
| pbase-hc | 1,068 | 8.4 µs | 0.08 µs |
| phoible | 3,142 | 25.9 µs | 0.08 µs |

End to end, `mk_system_segment_ipa` went from 96.8 to 48.7 µs per token.
Scoring a pair moved only from 36.8 to 34.0 µs: those lookups are mostly early
hits, and the remaining time is the scorer's own walk over leaves, node groups
and ordered scales.

- Internal: compiled inventories are emitted sorted by the grapheme's UTF-8
  bytes, the order `strcmp` imposes. The generator rejects a duplicate grapheme
  within a system — a binary search may return either row where the scan always
  returned the first. There are none in the bundled data.
- Added: `bench/bench_lookup.sh`, and `bench/baseline.txt` now records lookup
  timings alongside the footprint numbers.
- Added: `test_resolution` checks the emitted row order. A disagreement between
  Python's sort and C's `strcmp` would otherwise be silent — a grapheme that is
  present would simply stop being a segment.

### The compiled data is interned: 55% off the WebAssembly payload

No public API, ABI, or behavior change. The exported symbol list is unchanged
and every golden fixture is byte-identical; this is a change of representation
only.

The generated tables held a `const char *` for each of roughly 260,000 feature
slots — 2.08 MB of pointers on a 64-bit target, one relocation each, to name
35 KB of text. They now hold 16-bit ids into a single interned string pool.

|                              | before    | after   |
|------------------------------|-----------|---------|
| `builtin_data.o` `.rodata`   | 2,485,500 | 546,420 |
| relocations, whole library   | 282,512   | 4,008   |
| `footprint.wasm`             | 1,286,045 | 574,609 |

- Internal: `mk_builtin_system` carries either compiled storage (pool offsets
  and feature ids) or runtime storage (`mk_builtin_entry` pointers, as a model
  parsed from text produces). `src/inventory.c` hides which, so nothing above
  it changed shape.
- Internal: rows with identical feature sets share one run of ids. A quarter of
  the bundled rows are duplicates in that sense, worth a further 24.6% of the
  largest array.
- Internal: the pool is emitted in 2 KB chunks. C99 only requires support for
  string literals of 4,095 characters and adjacent literals concatenate into
  one, so a single-array pool was not strictly conforming.
- Fixed: an affricate-retraction lookup leaked its candidate spelling on a
  miss. Introduced while rewiring the lookup and caught by AddressSanitizer
  before it left this branch.
- Added: `tools/tests/` covers the generator's string pool directly — offset
  round-trips, byte offsets for non-ASCII, chunk boundaries, and the literal
  limit. `scripts/check_generated_data.py` compares the emitter against its own
  output, so it catches drift but not a consistently wrong emission.
- Added: `test_resolution` walks all 9,728 compiled rows, checking each against
  the interned storage and that each finds itself by grapheme.

### Module boundaries: internal.h dissolved, unicode.c split

Internal restructuring. No public API, ABI, or behavior change: the exported
symbol list is byte-identical to the previous commit, and every golden fixture
is unchanged.

- Internal: `src/internal.h` is gone. It had become the repository-wide
  `common.h` — 16 data-table struct definitions, 28 `extern` declarations, and
  four unrelated families of helper prototypes, included whole by every
  translation unit. Its contents now live with their owners:
  `src/generated/builtin_data.h` (table types and tables), `geometry.h`,
  `system.h`, `registry.h`, `string_list.h`, `strings.h`. Each compiles
  standalone.
- Internal: `src/unicode.c` (1,073 lines, four responsibilities) is split into
  `utf8.c` (encoding and Unicode classification), `ipa.c` (IPA orthographic
  classification), `normalize.c`, `tone.c`, and `tokenize.c`, with
  `mk_strdup_internal`, `mk_streq`, `mk_has_prefix`, `mk_append_text`, and
  `mk_free_items` collected in `strings.c`.
- Internal: the runtime-model parser moved out of `registry.c` into
  `model_text.c` behind `mk_parse_model_text`, which produces a model without
  touching a registry. `registry.c` drops from 555 lines to 209 and no longer
  contains a line-oriented parser.
- Internal: `setup.py` globs the core sources instead of listing them. The list
  existed in three places — `CMakeLists.txt`, `setup.py`, and the WebAssembly
  smoke script — so splitting a module meant remembering all three, and the one
  that gets forgotten fails only in whichever build nobody runs locally.
- `geometry.c` and `resolver.c` were left whole; see `REFACTORING_PLAN.md` for
  the measurements behind that.

### Enforced warning baseline, a testable fallback profile, and footprint measurement

- Fixed: the WebAssembly smoke test had been failing, so the `wasm` CI job was
  red. Both of its assertions were pinned to pre-C Python values — 5 features
  for `pʰ` where the descriptive inventory now gives 9, and a `p`/`b` distance
  of 0.375, which is the figure preserved in the archived `_full` fixtures
  against the C library's 0.125. It now asserts feature membership and scoring
  invariants; exact values belong to the golden fixtures, which are regenerated
  deliberately.
- Added: `MERKMAL_USE_UTF8PROC` (default `ON`). `OFF` selects the IPA-focused
  fallback even where `libutf8proc` is installed. `MERKMAL_REQUIRE_UTF8PROC=OFF`
  only ever permitted the fallback rather than selecting it, so the profile
  WebAssembly ships could not be reproduced on a developer machine that had the
  library — and was therefore covered by nothing but a 90-line smoke program.
  A new `c-fallback` CI job runs the whole C suite against it.
- Added: `MERKMAL_WERROR` (default `OFF`, enabled in CI). The compiler warning
  set is now `-Wall -Wextra -Wpedantic -Wshadow -Wconversion -Wstrict-prototypes
  -Wmissing-prototypes`; the first-party sources were already clean at it, so
  this enforces existing discipline rather than requiring new work. Downstream
  consumers building from source are unaffected.
- Added: `bench/bench_footprint.sh` and a committed `bench/baseline.txt`
  recording section sizes, relocation counts, `.wasm` bytes, and module compile
  time. The generated data is 2.49 MB of `.rodata` over 35 KB of actual string
  content, carrying 281,322 relocations; the baseline exists so that work
  against that number can be argued from measurements.

### Internal structure, and two tokenization defects

Restructuring of the C library and its Python wrapper. No distance, feature
set, or tokenization result changes except where noted as a fix.

- Fixed: IPA tone letters were dropped by tone merging. The tokenizer grouped
  `˥˦˧˨˩` into a tone run, but the merge step decoded superscripts only, judged
  the run all-zero, and discarded it — `segment_ipa_merged("a˥")` returned a
  toneless `"a"`. The library had three Chao decoders accepting three different
  alphabets; it now has one.
- Fixed: graphemes in a caller-supplied runtime model were stored as written
  while queries were normalized, so a `grapheme` row spelled with a precomposed
  `ã` could not be matched under either spelling. Runtime and built-in models
  now share one normalization, and the source conventions apply too, so a row
  written `ʧ` is reachable as `tʃ`.
- Fixed: an unknown `node_weights` preset on a cluster segment such as `ai`
  returned `MK_OK` with a composed value near 0.8 instead of
  `MK_ERR_INVALID_ARGUMENT`. The scorers no longer signal failure with `NAN`.
- **Breaking (Python):** `feature_distance` no longer accepts `system`. It
  measures a distance in the compiled geometry, which every system shares; the
  argument was validated and then ignored, so a caller naming `phoible` was
  silently given clements-hume numbers.
- **Breaking (Python):** `merkmal._native._registry_*` are gone. Each operation
  is now one function taking an optional `registry`, and `Registry` methods
  call it. `merkmal.Registry` itself is unchanged apart from `system` now
  defaulting to `None` (the same default system) rather than to the literal
  `"descriptive"`.
- Added: `merkmal.Registry.system_segment_ipa`.
- Changed: adding a model to the shared default registry now raises
  `ValueError` rather than mutating what every other caller in the process
  sees. Construct a `merkmal.Registry`.
- Changed: bare `mb`, `nd`, `mp`, `nt` and `ŋg` are recognized as prenasalized
  consonant clusters; `docs/c-api.md` still described the older two-item
  blocklist.
- **Breaking (C ABI):** `mk_feature_set` is removed. It was the same struct as
  `mk_string_list` exported under a second name, with its own
  `_size` / `_get` / `_free` triple and its own translation unit.
  `mk_system_grapheme_features` now returns an `mk_string_list **`; replace
  `mk_feature_set_size` / `_get` / `_free` with the `mk_string_list`
  equivalents. The exported ABI is 26 symbols, down from 29. The Python API is
  unaffected — `get_features` still returns a `frozenset`.
- Added: `merkmal.sound_distance`, exposing `mk_sound_distance`, which was
  public C API the wrapper did not bind. It scores two feature sets against the
  compiled geometry with no system, registry, or grapheme involved.
- Internal: segment resolution moved into `src/resolver.{c,h}` behind
  `mk_resolve`, which reports which path resolved a grapheme; `src/system.c`
  went from 2298 to 473 lines. The two component parsers and the two cluster
  synthesizers became one of each, taking a grammar. Hand-written C dropped
  from 5466 to 5084 lines and the Python binding from 929 to 811.

### Second review pass: ordered scales, derived class features, tone

An independent linguistic review ([docs/independent-linguistic-review.md](docs/independent-linguistic-review.md))
found that the first pass had corrected the symptoms it measured while leaving
the underlying defect: ordered properties were encoded as unordered flags, and
several basic features were unreachable. See
[docs/review-response.md](docs/review-response.md) for the correction notice.

- **Corrected claim.** "Every consonant-consonant pair scores below every
  consonant-vowel pair" was false; it generalised from eight hand-picked pairs.
  Measured across the inventory, `broad` had a max C-C of 0.829 against a min
  C-V of 0.660. The claim is withdrawn.
- **Corrected claim.** "Every zero is on the record" covered only the bare
  inventory of the three categorical systems. It missed composed forms
  (`d(aː, aːː)` was 0) and all five valued systems (`phoible` scored zero on
  ~5% of pairs). The audit now covers all eight systems and composed forms.
- **Corrected claim.** "33 dead labels to 0" checked one direction only.
  Thirteen scoring leaves were unreachable because no inventory name ever says
  `sonorant`, `continuant`, `anterior` or `distributed`. Both directions are now
  checked.
- **Breaking (numeric): all categorical distances changed again.** Ordered
  properties are now scored as ordered scales, cost proportional to the
  difference in level.
- Fixed: the vowel space was not ordinally correct. `d(i,e)` was 0.214 while
  `d(i,a)` was 0.167, and `/i/`, `/e/` and `/a/` were all exactly 0.500 from
  `/ɔ/`. Height and backness are now seven- and five-point ordered scales.
- Fixed: the Chao tone code was not monotone in the digit. Levels 2 and 4
  differed on both the register and the height bit, so they scored as far apart
  as 1 and 5. Each position now carries an ordered level.
- Fixed: two-digit contours never filled the mid slot, so `a¹` and `a¹¹` — the
  same level tone spelled two ways — differed.
- Added: IPA tone letters U+02E5–U+02E9, the primary IPA tone notation, were
  rejected outright and are now read as pitch levels.
- Fixed: 19 precomposed tone-marked vowels (including the whole Pinyin
  third-tone set `ǎ ě ǐ ǒ ǔ`) were rejected while their canonically equivalent
  NFD spellings were accepted — and `normalize()` returns the precomposed form,
  so the documented preprocessing step turned working input into failing input.
  Decomposition is now table-driven and identical with or without utf8proc.
- Fixed: length was a set of unordered flags. A half-long vowel scored further
  from a long one than a plain vowel did, `aː` and `aːː` were identical, and
  breve-plus-length-mark asserted both `ultra-short` and `long`. Duration is now
  a five-point ordered scale, a repeated length mark means overlong, and
  contradictory values are rejected.
- Fixed: every manner distinction cost the same, because `sonorant`,
  `continuant`, `anterior` and `distributed` were never activated by any
  grapheme. They are now derived from the manner and place labels.
- Fixed: `/w/` scored as far from `/u/` as `/ʔ/` does from `/a/`. `vocoid` is
  derived and covers the cardinal glides, which are [-consonantal].
- Fixed: clicks carried the rear closure as a second place, so `/ǃ/` was exactly
  equidistant from `/k/` and `/t/`. The rear closure is now its own feature.
- Fixed: `segmental` and `ignore-prosodic` silently discarded nasalisation and
  ejectivity along with length. Both moved out of `Prosodic`; `ignore-length`
  and `ignore-secondary` presets added.
- Fixed: `mb` and `nd` were rejected by a two-item blocklist while `mp`, `nt`,
  `ŋg` and `ndz` were accepted. The blocklist is gone.
- Fixed: `pre-nasalized` was asserted for any nasal-initial cluster, so the
  geminates `mm`/`nn` and the labial-velar nasal `ŋm` carried it.
- Fixed: three inventory errors — a Private-Use-Area codepoint U+F268, a
  spurious `oz̻`, and `ǃǃ` — and seven rows carrying an undescribed combining
  circumflex, which consumed the tone mark and produced a plain mid vowel while
  the same sequence elsewhere synthesised a full falling tone.
- Fixed: `classes.tsv` defined class `R` "resonant" as `consonant,-stop`, which
  captured every fricative and affricate; and shipped a leftover `XXX`
  "development" class.
- Fixed: `typologies/lenition-bias.json` made devoicing the cheap direction,
  contradicting its own stated lenition scale.
- Fixed: two more inventory naming errors that made distinct segments
  identical — `ʈʂː` was named *voiced* though `ʈʂ` is voiceless, and `ⁿgǃ` (a
  prenasalized plain click) was named a *nasal-click*, which made it the same
  as prenasalized `ŋǃ`.
- Fixed: cross-articulator place had become invisible while the ordered place
  scales were being introduced — each scale is undefined for the other
  articulator, so `d(b, g)` was 0. The privative articulator features (labial,
  coronal, dorsal, guttural) now carry that difference.
- Result: **no pair of distinct forms scores zero in any categorical system**,
  over 611,065 pairs including modifier-composed forms; every label can affect
  a distance and every scoring dimension is reachable.
- Documented: phonetic distance does not track diachronic probability. Frequent
  changes score *further* apart than rare ones on average. This is inherent, not
  a tuning target.

### First review pass

#### Response to the external linguistics and phonology review

See [docs/review-response.md](docs/review-response.md) for the finding-by-finding
account. Highlights:

- **Breaking (numeric): categorical and `pbase-jfh` distances changed.** Every
  distance produced by `broad`, `descriptive`, and `distinctive` moved, and
  every feature set for a tone-bearing grapheme changed. Recompute stored
  distances, alignments, clusters, and thresholds; do not mix cached scores
  across this change.
- Fixed: 33 feature labels reached no scoring dimension and so could not affect
  any distance, among them `consonant`, `vowel`, `devoiced`, `apical`,
  `laminal`, `unreleased`, `velarized`, and the whole length series. As a
  result `p`~`p̥`, `t`~`t̺`, `k`~`k̚`, and `y`~`yːː` all scored exactly zero.
  Over all 302,253 inventory pairs, zero-distance pairs fell from 802/802/599
  to 7/7/7, and those 7 are now declared with reasons in
  `tests/golden/contrast_baseline.tsv`.
- Fixed: `distinctive` could not separate palatal/velar/uvular consonants,
  bilabial from labiodental, the guttural places, close-mid from mid from
  open-mid, lateral fricatives from lateral approximants, or clicks from
  implosives. Dimensions were added for each.
- Fixed: Chao level 3 produced no features, so a mid-tone segment was identical
  to a toneless one (`a` = `a³³` = `ā`). Tone now emits `tone-present` plus an
  explicit `tone-<position>-mid-level`.
- Fixed: a Chao run of four or more digits was split into two contradictory
  tone readings, so `a¹²³⁴` was accepted and carried both `tone-onset-lowered`
  and `tone-onset-raised`. Over-long runs are now rejected whole.
- Fixed: `models/pbase-jfh/model.json` mapped `"vocalic "` with a trailing
  space, so that dimension was absent from every `pbase-jfh` distance. The dead
  `spread` key was removed from `models/pbase-spe/model.json`.
- Fixed: `models/phoible/model.json` declared the state symbol `0`, which never
  occurs in its inventory, while the 30,181 cells written as `.` were
  undeclared. Its license is corrected from generic `CC-BY` to `CC-BY-SA-3.0`.
- Breaking: the valued systems (`pbase-*`, `phoible`) now return
  `MK_ERR_UNSUPPORTED_MODEL` for tone-bearing graphemes. None has a dimension a
  tone modifier can move, so they previously scored `a¹¹` and `a⁵⁵` as equal.
- Breaking: runtime model registration validates strictly by default. A model
  whose features the geometry does not know is rejected with a diagnostic
  instead of registering and then scoring every comparison as zero. Use
  `@validation permissive` to opt out.
- Breaking: the distribution declares
  `MIT AND CC-BY-SA-3.0 AND CC-BY-NC-SA-4.0`, not MIT alone. The compiled-in
  tables include PHOIBLE (share-alike) and P-base (non-commercial share-alike)
  data. See the generated `NOTICE`.
- Added: `mk_system_segment_ipa` / `merkmal.system_segment_ipa`, longest-match
  tokenization that agrees with a system's own recognizer, so `tʃa` becomes
  `[tʃ, a]` and `kpa` becomes `[kp, a]`. `mk_segment_ipa` is unchanged and now
  documented as orthographic tokenization.
- Added: `mk_registry_add_model_text_ex`, which reports which line and token a
  rejected model failed on.
- Added: per-artifact `models/*/provenance.json`, a generated `NOTICE`, and
  `scripts/generate_notice.py`. Upstream release, commit, and retrieval date
  are recorded as `UNVERIFIED` rather than guessed.
- Added: `scripts/contrast_baseline.py` (exhaustive collapse and dead-label
  audit) and `scripts/regenerate_golden.py` (reviewable fixture regeneration).
- Changed: the geometry is identified as `merkmal-clements-hume-inspired-v1`
  with an explicit `departures` list; `clements-hume` remains a compatibility
  name. See [docs/geometry.md](docs/geometry.md).
- Changed: `typologies/corecog-derived.json` is quarantined. It is not a
  sound-change direction prior: unordered daughter-daughter pairs do not
  identify direction, its stated pair orientation was wrong, and its cost
  transform was inverted. See `typologies/README.md`.
- Documented: the output is an experimental dissimilarity, not a metric, not a
  sound-change probability, and not a typological statistic. `broad` and
  `descriptive` are operationally identical at this revision.

### Earlier unreleased work

- Breaking: repository direction changed from parallel Python/Go
  implementations to a C99 core library with a native Python wrapper.
  Go support has been retired.
- Breaking: the installable Python package is now native-only. The old
  pure-Python implementation and its tests have been removed from the active
  codebase.
- Changed: Python packaging now lives at the repository root so source
  distributions include the C core and can build independently of a checkout.
- Added: C99 library skeleton, public `merkmal.h`, CMake build, compiled-in
  built-in data, C golden tests, and CPython Limited API wrapper.
- Added: C install rules, exported CMake package metadata, pkg-config metadata,
  public symbol annotations, and `mk_status_string`.
- Added: release policy documentation, sanitizer CI, and an Emscripten/Node
  smoke test for the raw C ABI with filesystem support disabled.
- Added: public C APIs for built-in registries, runtime categorical model
  registration, feature lookup, segment distance, geometry feature
  distance, sound distance with weight presets, IPA normalization,
  segmentation, and Chao tone digit merging.
- Added: `mk_split_tone` and Python `split_tone`, which separate a merged
  segment such as `a¹³` into its base grapheme and its Chao tone token.
  Consumers that model tone as its own dimension previously had to
  reimplement Chao digit parsing to undo `mk_merge_tone_digits`.
- Documented: Chao digits are pitch levels, not tone-category numbers.
  Superscript `⁰`-`⁵` merge; ASCII digits such as Jyutping `ji6` or Yoruba
  `ori3` label tone categories, carry no pitch, and stay unrecognised
  rather than synthesising tone features the notation never asserted.
- Added: Python wrapper access to `node_weights`, tone-digit merging,
  merged IPA segmentation, and a minimal native `Registry` for runtime model
  text.
- Added: descriptive source-token synthesis for vowel clusters, explicit
  complex consonants, broader affricate spellings, and tone-bearing nuclei.
- Added: Arca-driven residual descriptive support for precomposed-vowel
  clusters such as `ɛï³³` and mixed velar affricate source tokens such as
  `kɣ`.
- Added: compositional descriptive support for precomposed vowel/modifier
  source tokens such as `ḭ`, `ṳ`, `ṵ`, and `ṵː`, plus `ṽ` as a nasalized
  consonant.
- Changed: bare `mb` and `nd`, standalone tone clusters, slash-delimited
  tone/control forms, and source markup/control tokens remain invalid source
  segments.
- Added: public documentation for C distribution, the C API, and the
  line-oriented runtime categorical model format.
- Changed: pre-C Python tutorials, notebooks, and research scripts are archived under
  `docs/legacy_python/` until they are rewritten for the native API.
- Changed: generated C data now comes directly from the top-level source data
  files instead of importing archived Python loaders.

## 0.6.0

- Added: `segment_ipa(ipa) → [phones]` — IPA tokenizer that handles
  tie bars, prefix/suffix modifiers, combining marks, and Chao tone
  digits. Exported from the public API along with `decompose_grapheme`
  and `compose_grapheme`.
- Added: `MergeToneDigits` in the Go module, matching the Python
  `merge_tone_digits`. Fixed `ParseChaoDigits` handling of all-zero
  input.
- Added: sequence normalization (`normalize_sequences`) — fallback
  normalizations for postalveolar affricates (tie-bar stripping,
  retraction).
- Added: valued engine compositional fallback — valued engines
  (phoible, pbase-*) now resolve unknown graphemes via
  `decompose_grapheme` + modifier-to-feature mapping, matching the
  categorical engine's compositional chain.
- Added: CLTS normalization — slash stripping, ligature resolution,
  ASCII-colon parsing, and stress mark normalization for broader
  input compatibility.
- Added: typology module (`typology.py`) with `DirectionCost` and
  `Typology` types for asymmetric distance computation. Three
  bundled typologies: `default`, `lenition-bias`, `corecog-derived`.
- Added: geometry comparison and weight learning infrastructure
  (`paper/`).
- Added: 10,000+ cross-language golden test entries covering all
  nine systems (features, distances, partitions, geometry).
- Fixed: `parse_chao_digits` and `merge_tone_digits` restored to
  public API after accidental omission in 0.5.0.
- Cleaned up: removed one-time migration scripts, fixed import
  sorting.

## 0.5.0

- **Breaking**: data-code decoupling. Feature inventories, geometry
  tree, partition definitions, and per-system metadata moved from
  Python source files to pluggable model directories (`models/`) and
  geometry files (`geometries/`). Both Python and Go implementations
  load these data files at runtime.
- **Breaking**: Python package moved from `src/merkmal/` to
  `python/merkmal/`. Engine implementations reorganized into
  `engines/categorical.py`, `engines/valued.py`, `engines/trained.py`.
- Added: native Go module (`go/`) implementing the full `System`
  interface — model loading, geometry-weighted distance, partition
  derivation, grapheme normalization. All `fs.FS`-based for
  embedding flexibility.
- Added: cross-language golden test data (`tests/golden/`) pinning
  feature extractions, pairwise distances, and partition assignments
  across all nine systems. Both test suites validate against these.
- Added: `model.py` / `model.go` — generic model loader that reads
  `model.json` and dispatches to the appropriate engine by type.
- Added: `geometry.py` / `geometry.go` — geometry loader from JSON,
  replacing the hardcoded tree in the old `geometry.py`.
- Added: `partition.py` / `partition.go` — partition derivation from
  model config, replacing hardcoded slot definitions.
- Added: `registry.py` / `registry.go` — model discovery from the
  `models/` directory.
- Removed: `cognator_export.py` and the `export-cognator` CLI
  subcommand. Downstream Go packages now import `merkmal/go`
  directly.
- Removed: UPA transcription adapter (`upa.py`). Consumers requiring
  UPA-to-IPA mapping should handle conversion upstream.
- Removed: `exporters.py`, `data/` directory (data now in `models/`).

## 0.4.0

- Added: `--custom-level` flag to `export-cognator` for caller-specified
  partition feature subsets (repeatable as
  `--custom-level=name:feat1,feat2,...`). Mirrored in the Python API as
  the `custom_levels=` kwarg of `merkmal.export_cognator` and
  `merkmal.export_all_systems`. Custom levels appear in `partitions.tsv`
  alongside the four standard levels; their feature subsets and source
  are recorded in the manifest with `source: custom`.

## 0.3.0

- Added: `partitions.tsv` in cognator export — feature-subset-derived
  grapheme partition at four granularity levels (prosody, coarse,
  medium, fine). Derived from each system's own features; transparent
  per-level feature subset recorded in manifest.

## 0.2.0

- Added: `export-cognator` subcommand for static export of feature
  distances, classes, prosody, and fallback data to a byte-stable
  bundle consumed by cognator. Exposed as `merkmal.export_cognator`
  (single system) and `merkmal.export_all_systems` (every registered
  system). Bundles are reproducible under `SOURCE_DATE_EPOCH` and
  include SHA-256 hashes in `manifest.json`.
- Added: `merkmal` console script entry point (also runnable via
  `python -m merkmal`).

## 0.1.1

- Fix cross-process non-determinism in `sound_distance` and
  `valued_geometry_distance`. Set unions are now sorted before
  iteration so floating-point accumulation order is stable
  regardless of Python's hash randomization seed.

## 0.1.0

Initial public release.

- Nine built-in feature systems: descriptive, broad, distinctive,
  pbase-hc, pbase-jfh, pbase-spe, pbase-uftc, phoible, classfeat.
- Feature geometry tree for structured distance (Clements & Hume 1995).
- Tonal geometry (Yip 1980, Bao 1999): register, contour, onset/mid/offset.
- ClassFeat: trained hybrid system (sound classes + continuous features).
- Compositional segment decomposition via Unicode NFD.
- UPA transcription adapter.
- Analysis layer: queries, matrices, natural class derivation, distance, export.
- Zero runtime dependencies, Python 3.12+.
