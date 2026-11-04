# Roadmap after 0.9.0

What comes next, carried over from the 0.9.0 release plan once its checklist
was done (the release itself is recorded in [CHANGELOG.md](../CHANGELOG.md)).
Ranked by value to users against cost. The first group in §1 is mostly
engineering; the second carries a modelling claim and needs the evaluation in
§2 behind it.

## 1. Making it more robust as a phonological tool

### Robustness

- **Caller-supplied source conventions.** The global convention table can only
  take spellings that mean one thing everywhere (`ʧ`, `ɚ`, `ˁ`). Most of the
  remaining unread Lexibank types are spellings that are consistent within a
  source and ambiguous across sources: macron below `a̱` (retracted, ATR, or a
  tone, depending on the Africanist tradition), spacing tone letters `ˉ`/`ˋ`,
  Indological `ṛ`, archiphoneme capitals `R`/`T`/`S`. A per-call or
  per-registry profile, recorded in `operation_fingerprint`, would let a user
  say what their source means without the library guessing for everyone. It
  is the orthography-profile idea, applied at the segment level.
- **Put `UNICODE_VERSION` in the system fingerprint.** Normalization decides
  which graphemes resolve, so it is part of a result's identity. It is exposed
  but not fingerprinted, because adding it changes every digest. Do it once, as
  a v2 payload, before people start storing fingerprints.
- **Cluster tokenization through longest match** (paper-notes §12.6), so that
  `ntʃ` is *n + tʃ* rather than *n + t + ʃ* under `segment_ipa` too.
- **Diacritic semantics beyond place.** This branch makes place marks
  replace place. The same question applies to manner and phonation marks on a
  base that already carries the opposite value (`b̥` vs `p`, `ʋ̞`). The
  contradictory-pair table is a start. Auditing each mark for "adds",
  "replaces" or "refuses" would turn an implicit policy into a data file.

### Linguistic coverage and modelling

- **A permissively licensed valued system.** Commercial users currently have
  no valued system they can use. PanPhon's feature table (Mortensen et al.
  2016) is the obvious candidate if its license is confirmed compatible. It
  would also make the cross-theory comparison in `manuscript-notes.md` §1 less
  dependent on four P-base variants that share an inventory, which that note
  already lists as a weakness.
- **Tone on the valued systems.** They refuse tone-bearing graphemes rather
  than return a false zero, which is correct. A structured tone value on the
  tone-bearing unit (paper-notes §12.4) would let them answer.
- **Length, gemination and syllabicity as tiers.** Long-vowel and doubled-vowel
  spellings are reconciled by a waiver in `cluster.c`. If length were a
  property of the timing tier rather than of a segment, the waiver would not
  be needed.
- **Contrastive vs. allophonic use** belongs to the typology package, not the
  core, per the scope the README already sets. It is still the most requested
  thing a segment-type catalog cannot answer.

## 2. Toward publication

There are two outputs, and they should be kept apart.

1. **A software paper (JOSS or similar).** The release, archived with a DOI,
   tests, documentation and a statement of need are what JOSS reviews, and
   most of that now exists. The README's "what the number means" section is
   the statement of need it asks for. The 0.9.0 release, its DOI and the tests it ships are what JOSS needs.
2. **A research paper** from `docs/manuscript-notes.md` and
   `docs/paper-notes.md`. The notes already list their own gaps: a by-system
   breakdown for the cross-theory disagreement, a tonal corpus, more families
   for the fitted-cost result, and the independence caveat for the P-base
   variants. Two more come out of this work:
   - **External validation against perception.** The distances are stipulated,
     and the README says so. Consonant and vowel confusion matrices (Miller &
     Nicely 1955 and later replications) are the standard independent test of
     a segment-similarity measure, and none is reported yet.
   - **The coverage story is a finding.** Most of what the default system
     cannot read in Lexibank is the sources' own CLTS markup, not unsupported
     phonetics. In `williamsonbenuecongo`, every one of the top unread tokens
     is `<?>` or `<<…>>`. That distinction belongs in the paper's coverage
     section, with token and type rates reported separately, as
     `manuscript-notes.md` §3 argues.
