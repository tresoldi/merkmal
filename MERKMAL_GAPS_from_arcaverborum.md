# merkmal: gaps, needs, and bugs — report from Arca Verborum

> **Partially addressed.** This report targets merkmal 0.1.0. The
> 0.5.0 refactor added compositional decomposition fallback to
> **categorical engines** (descriptive, broad, distinctive), which
> resolves §3 and most of §4 for those systems. However, the
> **valued engine** (phoible — arca's primary system) remains
> literal-lookup only: no compositional fallback, no tone-mark
> handling, no sequence normalization. The IPA segmenter (§2) and
> public `normalize()`/`is_segment()` APIs (§5) are not yet
> implemented. These items are on the merkmal roadmap, prioritised
> after plan-phase completion.

**Author:** generated during Arca Verborum IECOR transcription work, 2026-05-21
**merkmal version evaluated:** `0.1.0` (system: `phoible`, 3,142 graphemes)
**Consumer:** `~/repos/arcaverborum` — uses `merkmal.get_features` /
`grapheme_to_features` / `list_graphemes` (via `phonology.is_valid_grapheme`)
to validate and segment IPA. This report supersedes / expands the earlier
`NOTE_affricate_normalization.md`.

Arca Verborum treats a form's segments as **clean** only when every
space-separated token is recognised by merkmal's `phoible` system. Across
the 25,731-form IECOR (Indo-European) cohort, **~1,550 forms (6%) carry
real, correct IPA that merkmal rejects**, plus a much larger globally-known
**tone** cohort (196,984 forms, ~9.8% of the 2.0 M-form full database).
Everything below is a merkmal-side concern, not bad source data: the IPA is
correct; merkmal cannot tokenise/recognise it.

---

## 1. No IPA *normalization* layer (highest impact)

**Problem.** `phoible` stores the postalveolar affricates with a **retracted**
stop — `t̠ʃ` / `d̠ʒ` (U+0320) — and rejects every other standard spelling of
the same sound:

| input | recognised? |
|---|---|
| `t̠ʃ` (t + U+0320 + ʃ) | ✓ |
| `tʃ` (plain) | ✗ |
| `t͡ʃ` (tie bar U+0361) | ✗ |
| `d̠ʒ` | ✓ |
| `dʒ`, `d͡ʒ` | ✗ |

IE-CoR, Wiktionary, NorthEuraLex and most sources write the plain `tʃ`/`dʒ`
or the tie-bar `t͡ʃ`/`d͡ʒ`. `normalize_input_grapheme()` (in
`systems/categorical.py`) only does NFD + **per-character** `_IPA_EQUIVALENCES`
(`ɡ→g`, `ʼ`↔`'`), so it cannot insert the retraction diacritic between the
stop and the sibilant.

**Impact.** Measured: normalising just `tʃ→t̠ʃ`, `dʒ→d̠ʒ` recovers **854 forms
and lifts 41 IE varieties to ≥99% clean** (Russian, Hindi, Italian, Bulgarian
… all jumped to 100%). It also unblocks the whole Croatian/Slovene/Greek/Hindi
affricate tier.

**Ask.** Add a BIPA/CLTS-style **sequence** normalization step (before the
per-character pass) that maps the bare/tie-bar affricate sequences to their
canonical phoible graphemes, and ideally exposes a public `normalize(ipa)` /
`normalize_grapheme(g)` API. The variants follow for free (`tʃʰ→t̠ʃʰ`,
`dʒʱ→d̠ʒʱ`, `tʃʲ→t̠ʃʲ`) since the diacritic just inserts before any trailing
modifier.

**Temporary shim in the consumer (remove when fixed):**
`arcaverborum/src/arcaverborum/phonology.py` →
`_AFFRICATE_NORMALIZATION` / `_normalize_affricates`.

---

## 2. No continuous-IPA segmentation / tokenizer API

**Problem.** Given a continuous IPA string like `ˈkɔstɐs` or `ɡ̊ɤɾʲɪtʲ`,
there is no merkmal function that returns the phoneme tokens. The only
public segmentation helpers (`segmentation.py`) handle **tone digits**
(`merge_tone_digits`, `parse_chao_digits`).

Arca had to write its own tokenizer, and the naive approaches both fail:

- **Greedy longest-match against `list_graphemes()`** over-merges consonant
  clusters, because phoible contains clusters as units for some languages:
  `kɔstɐs → k ɔ st ɐ s` (the `st` is one token), `preto → pɾ e t u`.
- **Char-by-char** orphans combining marks and modifier letters into
  standalone invalid tokens: `d͡ʒ → d, ͡, ʒ`; `ãː → ã, ː`; `ɡ̊ → ɡ, ̊`.

A correct tokenizer needs to: attach combining marks + modifier letters
(Lm/Sk) to their base; bind affricates (`t` + retraction/tie + sibilant);
join valid diphthongs; and treat preaspiration `ʰ` (between a vowel and a
stop) as a prefix to the stop, not a suffix to the vowel.

**Ask.** Expose `segment(ipa, system=...) -> list[str]` (BIPA-aware
tokenizer) and/or `is_valid_sequence(ipa)`. This is the single most useful
thing merkmal could add for lexical-data consumers.

**Workaround in the consumer:** a hand-rolled tokenizer in the Wiktionary
ingestion (not committed to the library) — fragile, should be merkmal's job.

---

## 3. Patchy, inconsistent grapheme coverage (attested-only, not generative)

**Problem.** `phoible` is a list of *attested* graphemes, so feature-identical
diacritic combinations are accepted on some bases and rejected on others.
This makes "is this valid IPA?" depend on whether PHOIBLE happened to attest
that exact symbol, not on whether it is a well-formed sound.

Validity matrix (`get_features` via `is_valid_grapheme`), base × diacritic:

| base | plain | velarized ˠ | palatalized ʲ | devoiced ̥ | dental ̪ | aspirated ʰ | long ː |
|---|---|---|---|---|---|---|---|
| t | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ |
| d | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| k | ✓ | ✗ | ✓ | ✗ | ✗ | ✓ | ✓ |
| ɡ | ✓ | ✗ | ✓ | ✗ | ✗ | ✗ | ✓ |
| p | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ |
| b | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| s | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ |
| r | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ |
| l | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| n | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| m | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ |

E.g. velarized `lˠ nˠ tˠ` ✓ but `kˠ ɡˠ rˠ` ✗; devoiced `d̥ r̥ l̥` ✓ but
`k̥ ɡ̊ p̥` ✗; multi-diacritic combos almost always ✗ (`ɡ̊ʲ`, `kʰʲ`, `d̪̊`,
`ʰt̪`) even though each diacritic is individually supported.

**Ask.** A **generative** validity/feature check: parse a base grapheme +
its diacritics/modifiers and derive features compositionally, so any
well-formed IPA segment validates (and gets features) regardless of whether
that exact string is in the PHOIBLE attestation list. `decompose_grapheme`
already exists and looks like the right foundation — `get_features` /
`grapheme_to_features` should fall back to it when the literal lookup misses.

---

## 4. Specific category gaps (what the rejected real-IPA actually is)

Rejected-token occurrences across the 1,546 IECOR unclean forms (1,644
occurrences, 228 distinct tokens):

| category | occurrences | examples |
|---|---:|---|
| pitch / stress accent | 732 | `á í ý ɪ̀ ɑ̀ èː ìː óː ɑ̈̀ː` (Lithuanian, Vedic, Greek, Serbian/Croatian, Slovene) |
| narrow quality (raised/lowered/centralized) | 287 | `ɪ̽ ɛ̽ ó̞ é̞ e̝ː ô̞ː` |
| velarization | 147 | `rˠ ɡˠ kˠʰ` |
| pharyngealization | 133 | `a̠ˤ` (Nuristani: Kamviri, Gawri…) |
| devoicing | 113 | `ɡ̊ d̪̊ ʁ̥` (Scottish Gaelic) |
| length (on marked vowels) | 94 | `èː ìː óː ɑ̈̀ː ô̞ː` |
| nasalization | 81 | `ɹ̃ ɑ̃` |
| non-syllabic / glide | 40 | `ɑ̯ y̯` |
| aspiration / breathy | 17 | `kˠʰ` etc. |

Two of these are arguably "expected deferrals" you already plan for:

- **Tone** (digits / Chao letters / superscripts): 196,984 forms globally
  (~9.8%). Known; `merge_tone_digits` / `parse_chao_digits` exist but tone
  marks still don't pass `get_features`.
- **Pitch / stress accent** on vowels (acute/grave/circumflex/macron): the
  single biggest IE category (732). Suprasegmental — needs a policy: strip
  to a tone/stress feature, or accept-and-feature the marked vowel.

The rest (quality, velarization, pharyngealization, devoicing, length,
nasalization) are **ordinary segmental IPA** that a generative feature
parser (§3) should simply accept.

---

## 5. Minor / API ergonomics

- **No public normalization round-trip.** `normalize_input_grapheme` and
  `normalize_output_grapheme` exist but are internal to
  `systems/categorical.py`; consumers want a documented top-level
  `normalize()` and `segment()`.
- **`is_valid_grapheme` is consumer-side.** merkmal has no boolean
  "is this a recognised segment?" — consumers infer it from
  `get_features(...) is not None`. A first-class `is_segment(g, system=...)`
  would help.
- **Diacritic inventory is good and worth exposing.** `_COMBINING_TO_FEATURE`
  and `_SUFFIX/PREFIX_MODIFIER_TO_FEATURE` are exactly the tables a generative
  parser needs; exposing them (or the parser built on them) would let
  consumers stop hand-rolling tokenizers.

---

## 6. Summary of asks for the rework (incl. Go port)

1. **`segment(ipa) -> [tokens]`** — BIPA-aware tokenizer (diacritics bind to
   base, affricates/diphthongs bind, preaspiration handled). *Highest value.*
2. **Generative `get_features` / validity** — fall back to `decompose_grapheme`
   so any well-formed base+diacritics segment validates, not just PHOIBLE-
   attested strings. Fixes the inconsistency matrix (§3) and most of §4.
3. **`normalize(ipa)`** — CLTS/BIPA canonicalization, starting with affricates
   (`tʃ`/`t͡ʃ → t̠ʃ`, `dʒ`/`d͡ʒ → d̠ʒ`). Lets us delete the arca shim.
4. **Suprasegmental policy** — decide how tone and pitch/stress accents are
   represented (feature vs stripped) and make them pass validation.
5. Keep these consistent between the Python and the new Go implementation.

## 7. Consumer-side temporary shims to remove once the above land
- `arcaverborum/src/arcaverborum/phonology.py`: `_AFFRICATE_NORMALIZATION` /
  `_normalize_affricates` (delete when §1/§3 land).
- The bespoke IPA tokenizer in arca's Wiktionary ingestion (replace with
  merkmal `segment()` when §2 lands).
- ~38 IE varieties and ~197 k tonal forms currently flagged `unclean` will
  re-clean automatically once §2–§4 land — no re-transcription needed, the
  IPA is already correct in the data.
