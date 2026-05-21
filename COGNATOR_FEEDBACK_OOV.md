# merkmal feedback: out-of-vocabulary graphemes in arcaverborum

> **Superseded.** This document predates the 0.5.0 refactor.
> Cognator now imports `merkmal/go` directly and handles grapheme
> normalization via compositional decomposition. Most OOV issues
> described below (length vowels, nasal vowels, aspirated
> consonants, secondary articulations) are resolved by the
> compositional pipeline. Retained as a historical record.

**From:** cognator (2026-04-18).
**Against:** merkmal 0.2.0, `descriptive` system (778 graphemes).
**Source:** arcaverborum CoreCog 2025-10-08, 451,935 forms across
58 Lexibank-derived datasets, ~2.03 M segments after tokenization.

Scope of this note: inform the merkmal roadmap about what phonemes
merkmal must learn for cognator to run at full coverage on the
arcaverborum corpus. **Not a blocker for cognator development** —
cognator's OOV policy assigns maximum distance and carries on, but
every missing grapheme is a lost signal.

## Headline numbers

- 2,968 distinct OOV types in the CoreCog corpus.
- Top 60 OOV types account for ~57% of all OOV events.
- OOV events: ~1.1% of all segments at the 60-type threshold, much
  less at the tail. Individually small; collectively consequential
  for large-family experiments (Indo-European: lots of length and
  nasal vowels; Tibeto-Burman: aspirates and tone).

## Patterns (in descending impact)

### 1. ASCII `g` vs IPA `ɡ` (23,356 events)

`g` (U+0067, Latin small g) appears in 50 datasets. Merkmal's
`descriptive` has only `ɡ` (U+0261, Latin small script g). This is
a pure Unicode normalization issue, best fixed via the
`fallback.tsv` channel:

```tsv
input	target	note
g	ɡ	U+0067 Latin g → U+0261 IPA voiced velar stop
```

**Recommendation**: populate `fallback.tsv` with at least this
entry in the next merkmal release. Consider shipping a curated
initial fallback file rather than leaving it empty.

### 2. Length vowels (~42,000 events across 10+ graphemes)

Missing: `aː`, `iː`, `oː`, `uː`, `eː`, `ɔː`, `ɛː`, `ɑː`, `ɨː`,
`æː`, and long geminates `lː`, `nː`, `tː`.

**Recommendation**: add length-marked vowels and geminate consonants
as first-class graphemes. Distance to the short counterpart should
be small (a length-feature displacement); distance to unrelated
vowels inherits the short-vowel geometry.

### 3. Nasal vowels (~22,000 events)

Missing: `ã`, `ĩ`, `ũ`, `õ`, `ẽ`, `ɨ̃`. Present in 25+ datasets, load
bearing for Indo-Aryan, South American families, Bantu.

**Recommendation**: add nasal counterparts of every oral vowel.
Feature difference is a single nasality displacement.

### 4. Aspirated consonants (~13,000 events)

Missing: `kʰ`, `tʰ`, `pʰ`, `tsʰ`, `tɕʰ`. Load bearing for
Sino-Tibetan and Indo-Aryan.

### 5. Palatalized + labialized consonants (~10,000 events)

Missing: `kʷ`, `lʲ`, `tʲ`, `nʲ`, `rʲ`, `mʷ`, `pʷ`, `gʷ`, also
`tʷ`, `dʷ` likely. Secondary-articulation modifiers.

### 6. Stress-marked segments (~20,000 events, bdpa-specific)

The bdpa dataset tokenizes stress into the grapheme itself:
`ˈd`, `ˈv`, `ˈs`, `ˈn`, `ˈk`, `ˈɡ`, `ˈp`, `ˈm`, `ˈt`, `ˈb`, `ˈj`,
`ˈu`, `ˈo`, `ˈr`, `ˈʒ` (U+02C8 PRIMARY STRESS prefix).

**Recommendation**: consumer-side pre-processing should strip
leading `ˈ`/`ˌ` from the grapheme before merkmal lookup. Cognator
will add this as an input-normalization step; merkmal need not
add every stress-marked variant. Flag in the docs.

### 7. Diphthongs (~4,000 events)

Arcaverborum sometimes tokenizes diphthongs as a single grapheme:
`ai`, `ei`, `au`. This is a tokenization-convention mismatch;
merkmal expects segmented input.

**Recommendation**: this is probably a cognator-side
pre-processing concern (split `ai` → `a i`), not a merkmal
grapheme to add. Confirm — do you prefer merkmal to learn
diphthongs, or cognator to split them?

### 8. Alternation glyphs (`á/a`, `í/i`, `o./o`) (~4,000 events)

Source data encodes "allophonic alternation on the transcriber's
judgement" as `X/Y`. Mostly `carvalhopurus` + `sagartst`
datasets. Should be cognator-side: split on `/` and keep the first
variant, or apply both as alternatives.

**Recommendation**: cognator-side handling; note in merkmal's
docs under "unsupported conventions we normalise upstream".

### 9. Accented vowels without IPA form (`á`, `ɑ̈`, etc.)

Missing. Most are iecor / Indo-European. Some are purely
orthographic (stress marks); some are genuinely phonological
(central vowels with diaeresis).

### 10. Combining-tie affricates (`t͡s` with U+0361)

Missing when tied; present when un-tied (`ts`). Should normalize
out the tie.

## Concrete asks

| # | Ask | Effort | Priority |
|---|---|---|---|
| 1 | Populate `fallback.tsv` with at least `g → ɡ` in next release | minutes | high — 23k events |
| 2 | Add length vowels `Vː` for every V | small | high |
| 3 | Add nasal vowels `Ṽ` for every V | small | high |
| 4 | Add aspirated consonants | small | medium |
| 5 | Add palatalized/labialized consonant variants | medium | medium |
| 6 | Document stress-mark normalization as consumer responsibility | minutes | low |
| 7 | Decide diphthong policy (merkmal adds vs. consumer splits) | design discussion | low |
| 8 | Document `X/Y` alternation glyphs as out of scope | minutes | low |
| 9 | Normalize combining tie `◌͡◌` → un-tied in merkmal loader | small | medium |

## Reproducing this scan

Cognator ships `cmd/oovscan`:

```sh
# From the cognator workspace root
go run ./cmd/oovscan --data=<arcaverborum forms.csv> --top=N
```

Reads `tests/fixtures/merkmal/descriptive/` by default; pass
`--bundle` to scan against another system.

## What cognator does in the meantime

- OOV graphemes score `d = 1.0` against everything except themselves
  (identity = 0).
- Tones are normalized upstream per the framework principle (tone
  is a nucleus property) — stress marks will be normalized upstream
  too.
- Cognator emits an `oov_report.tsv` alongside every run so users
  know what they lost coverage on.

**Status**: FEEDBACK, 2026-04-18. No version blockers; this is a
roadmap document. A followup feedback file may land as cognator's
real runs reveal secondary issues (e.g. tone grapheme coverage
gaps that currently pass under shape-based detection).
