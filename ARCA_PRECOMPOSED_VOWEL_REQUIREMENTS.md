# Arca requirement: precomposed vowels, vowel-tone clusters, and residual token policy

**Author:** generated from Arca Verborum validation work, 2026-07-26
**Consumer:** `../arcaverborum`
**Context:** merkmal is now a C99 core library with a native Python wrapper.

## Current state

Arca now uses the local `../merkmal` Python wrapper to validate
space-separated segment tokens in the `descriptive` system. After the latest
merkmal broadening for author-defined consonant clusters and selected
precomposed Latin source letters, a full Arca rebuild completed cleanly:

- `7308` varieties built
- `2,007,699` forms emitted
- `105,736` forms still marked `unclean`
- `321` unclean forms are tonal+malformed residuals

The recent consonant-cluster change recovered `2,234` forms relative to the
previous aggregate. The remaining high-frequency invalid tokens are now mostly
markup/control tokens plus a smaller but linguistically meaningful class of
precomposed vowel symbols and vowel-plus-tone clusters.

## Observed residual tokens

Top invalid tokens after the rebuild:

| token | count | likely class |
|---|---:|---|
| `<?>` | 22324 | source markup / unknown placeholder |
| `<<->>` | 5277 | source markup |
| `+` | 1936 | source control / separator |
| `∼` | 440 | source control / separator |
| `<<[>>` | 183 | source markup |
| `<<]>>` | 183 | source markup |
| `→` | 128 | source control |
| `<<~>>` | 105 | source markup |
| `¹/¹` | 87 | tone/control cluster |
| `S` | 77 | probably source annotation, not segment |
| `³/¹` | 76 | tone/control cluster |
| `<</>>` | 72 | source markup |
| `³¹` | 70 | tone cluster |
| `ṳ` | 68 | precomposed vowel-like segment |
| `<<.>>` | 64 | source markup |
| `⁵⁵` | 56 | tone cluster |
| `ě` | 54 | precomposed vowel + tone/quality |
| `ḭ` | 50 | precomposed vowel + diacritic |
| `ǎ` | 46 | precomposed vowel + tone/quality |
| `ṵ` | 45 | precomposed vowel + diacritic |
| `_` | 45 | source control |
| `ṵː` | 45 | precomposed vowel + length |
| `ṽ` | 42 | precomposed vowel + nasalization |
| `T` | 42 | probably source annotation, not segment |
| `³⁵` | 41 | tone cluster |

## Required design discussion

The markup/control tokens should not be made valid segments merely to improve
Arca's clean count. They are curation/noise indicators and should remain
invalid in merkmal unless a source-specific normalization layer explicitly
maps them away before segment validation.

The vowel-like tokens are different. They appear to represent ordinary source
transcription practice where a vowel, quality modifier, length marker, or tone
mark is encoded as a single precomposed Unicode character or as a compact
cluster. These should be considered for first-class merkmal support.

## Requirement 1: precomposed vowel normalization

merkmal should decide whether precomposed Latin vowel symbols should normalize
to existing decomposed descriptive segments before feature lookup.

Examples from Arca:

| input | likely normalized form | notes |
|---|---|---|
| `ě` | `ě` | caron may encode tone, pitch, or quality depending on source |
| `ǎ` | `ǎ` | same policy question as `ě` |
| `ý` | `ý` | acute currently behaves as tone-like in some paths |
| `ḭ` | `ḭ` or `i` + below mark | confirm intended feature for U+032D/U+0330-like source value |
| `ṳ` | `ṳ` or `u` + below mark | confirm exact Unicode decomposition and feature mapping |
| `ṵ` | `ṵ` or `u` + below mark | confirm exact Unicode decomposition and feature mapping |
| `ṽ` | `ṽ` or vowel-like `ũ` depending source convention | needs manual linguistic review |

The implementation should prefer Unicode-aware normalization over ad hoc token
tables where Unicode decomposition already gives the intended base plus
combining mark. If canonical Unicode decomposition does not match merkmal's
feature model, add explicit mappings with tests and documentation.

## Requirement 2: vowel plus tone/length clusters

Tokens such as `ṵː` should validate if the base precomposed vowel is accepted
and the suffix modifier is already a valid segment modifier. The same principle
should apply to future tokens combining a vowel with length, nasalization,
creaky/breathy marks, or tone marks.

Expected behavior:

- Validate the whole token as a single segment when the author/source presents
  it as one segment.
- Preserve the base vowel features.
- Add modifier-derived features such as `long`, `nasalized`, `creaky`,
  `breathy`, or tone/pitch features according to the existing descriptive
  feature vocabulary.
- Reject tokens that combine vowel material with obvious source markup or
  separators, such as slash-delimited `¹/¹`, unless a deliberate tone-cluster
  model says otherwise.

## Requirement 3: tone cluster policy

Arca still sees tokens like `³¹`, `³⁵`, `⁵⁵`, and slash-delimited forms such
as `¹/¹` and `³/¹`.

merkmal should separate two cases:

1. **Tone sequences that are legitimate single tonal units**, such as
   superscript tone digits or Chao-style clusters. These can be valid
   descriptive tone segments if merkmal's model treats tone as segmental or
   segment-attached.
2. **Slash/control forms**, such as `¹/¹`, which likely encode alternatives,
   comparisons, or source markup. These should remain invalid unless a clear
   data source proves they are intended as single phonological segments.

The key design point is that accepting tone clusters should not accidentally
make separators and editorial notation valid segments.

## Requirement 4: tests and acceptance criteria

Add native C tests and Python-wrapper tests for each accepted class. Suggested
initial test cases:

- Accept: `ě`, `ǎ`, `ý` if the selected policy treats caron/acute vowels as
  segmental vowel-tone or vowel-quality clusters.
- Accept: `ḭ`, `ṳ`, `ṵ`, `ṵː`, `ṽ` only after the Unicode decomposition and
  intended features are confirmed.
- Accept: `³¹`, `³⁵`, `⁵⁵` if tone clusters are in-scope for descriptive
  validation.
- Reject: `<?>`, `<<->>`, `<<[>>`, `<<]>>`, `<<~>>`, `<</>>`, `<<.>>`, `+`,
  `∼`, `→`, `_`, `S`, `T`.
- Reject by default: `¹/¹`, `³/¹`, and other slash-delimited tone/control
  tokens until there is an explicit positive policy for them.

## Suggested next step

Before implementing, inspect Unicode decomposition for the vowel tokens and
decide which combining marks should be true descriptive features versus
normalization-only aliases. The core design question is whether merkmal should
model these as:

1. normalized aliases of existing vowel + modifier segments;
2. generated vowel-modifier compounds; or
3. literal exception entries with manually assigned features.

Option 2 is likely the best long-term direction because it keeps behavior
consistent with the recent consonant-cluster work: if the author considers a
well-formed complex vowel/tone cluster to be one segment, merkmal can validate
it as one segment and explain it compositionally.
