# Package Request Consolidation Plan

This plan reviews the remaining top-level request documents from downstream
packages and decides how to proceed before deleting stale notes from the
repository.

Reviewed documents:

- `COGNATOR_PARTITION_FEEDBACK.md`
- `COGNATOR_FEEDBACK_OOV.md`
- `COGNATOR_SOUND_CLASSES_REQUEST.md`
- `MERKMAL_GAPS_from_arcaverborum.md`

Durable project documentation such as `README.md`, `C_REWRITE_PLAN.md`,
`docs/c-api.md`, `docs/distribution.md`, and `docs/runtime-model-format.md`
should stay. The four package-request notes above are historical request
artifacts and should be deleted after the live decisions below are captured.

## Current Direction

The repository is now a C99 core library with:

- compiled-in built-in models;
- caller-supplied runtime categorical models;
- a high-level C API;
- a thin native Python wrapper;
- no Go support;
- no legacy Python object model in the active package.

Old requests that assume `export-cognator`, `merkmal/go`, Python directory
model loading, or pre-C Python partition modules no longer describe the active
architecture. They should not remain as top-level guidance.

## Document Assessment

### `COGNATOR_PARTITION_FEEDBACK.md`

Status: stale.

Why:

- The document explicitly says it predates the 0.5.0 refactor.
- It proposes `export-cognator` and Python/Go partition machinery that no
  longer exists.
- Go has since been retired.
- The current C API does not expose partition-table generation.

Decision:

- Delete the document.
- Do not implement its `export-cognator` CLI shape.
- Keep one deferred roadmap item: consider a future C-level partition API only
  if a current consumer asks for it against the C library.

Possible future design:

- `mk_system_partition(...)` or `mk_system_project_features(...)` that accepts
  a feature subset and returns deterministic class labels.
- Python wrapper mirrors this with a small helper.
- No Cognator-specific preset in core merkmal.

Recommendation:

- Defer. This is not part of the current C distribution priority.

### `COGNATOR_SOUND_CLASSES_REQUEST.md`

Status: stale with one reusable idea.

Why:

- It also assumes `export-cognator`, bundle files, manifest output, and Go
  consumers.
- Its core idea, feature-subset projection, is still conceptually valid but
  belongs in a future generic partition/projection API rather than an export
  bundle.

Decision:

- Delete the document.
- Preserve the feature-subset projection idea in this consolidation plan only.
- Do not add bundle files, manifests, or an `export-cognator` command.

Recommendation:

- If partitions become active again, implement them as generic C library
  functionality:
  - input: system, grapheme list or full built-in inventory, feature subset;
  - output: deterministic partition class data;
  - no hard dependency on Cognator;
  - tests for stability and projection correctness.

### `COGNATOR_FEEDBACK_OOV.md`

Status: mostly addressed or superseded.

Old asks and current status:

| Ask | Current status |
|---|---|
| ASCII `g` normalization | Addressed: `g` resolves to IPA `ɡ`. |
| Length vowels and long consonants | Mostly addressed by compositional suffix handling. |
| Nasal vowels | Addressed for common vowels by normalization and diacritic synthesis. |
| Aspirated consonants | Addressed compositionally. |
| Palatalized/labialized consonants | Addressed compositionally for supported bases. |
| Stress-marked segments | Addressed: leading `ˈ`/`ˌ` are stripped in normalization. |
| Diphthong policy | Changed: descriptive source-authored vowel clusters are accepted. |
| `X/Y` alternation glyphs | Partially addressed by slash resolution for graphemes; slash tone/control forms remain invalid. |
| Tie-bar affricates | Addressed by tie-bar stripping/normalization. |

Decision:

- Delete the document.
- Do not create fallback TSV machinery; the current C core uses compiled-in
  normalization and `utf8proc`.
- Keep the current policy that obvious source controls and slash-delimited
  tone/control forms remain invalid.

Recommendation:

- No new implementation from this document now.
- Add future coverage only when a current C/Python consumer reports concrete
  residual tokens.

### `MERKMAL_GAPS_from_arcaverborum.md`

Status: mostly addressed, with a few deferred design areas.

Old asks and current status:

| Ask | Current status |
|---|---|
| Public normalization API | Addressed: `mk_normalize_grapheme`, Python `normalize`. |
| Public segment validity predicate | Addressed: `mk_system_is_segment`, Python `is_segment`. |
| Continuous IPA tokenizer | Addressed for the current high-level slice: `mk_segment_ipa`, `mk_segment_ipa_merged`. It is not system-aware. |
| Tone digit merging | Addressed for superscript Chao digits (`⁰`–`⁵`): `mk_merge_tone_digits`, Python `merge_tone_digits`. ASCII digits are not Chao pitch and stay unrecognised; see `docs/c-api.md`. Splitting a merged segment back apart is `mk_split_tone`. |
| Affricate sequence normalization | Addressed for current tested spellings. |
| Generative base+diacritic fallback | Addressed broadly for categorical and valued systems, with current model/diacritic limits. |
| Attached tone-bearing nuclei | Addressed for descriptive vowel and vowel-cluster segments. |
| Standalone tone clusters | Intentionally invalid. |
| Pitch/stress accent features such as caron/acute vowels | Deferred pending a source-independent feature policy. |

Decision:

- Delete the document.
- Do not implement a broad pitch/accent policy yet.
- Keep current attached-tone support and invalid standalone-tone policy.

Recommendation:

- Treat future Arca residual work as small, evidence-driven token-policy
  increments rather than keeping this old 0.1.0 gap list as a standing roadmap.

## Current Action Plan

### 1. Delete Historical Package-Request Docs

Delete:

- `COGNATOR_PARTITION_FEEDBACK.md`
- `COGNATOR_FEEDBACK_OOV.md`
- `COGNATOR_SOUND_CLASSES_REQUEST.md`
- `MERKMAL_GAPS_from_arcaverborum.md`

Do this after this consolidation plan is reviewed.

### 2. Keep Durable Roadmap Docs

Keep:

- `C_REWRITE_PLAN.md`
- `README.md`
- `CHANGELOG.md`
- `docs/c-api.md`
- `docs/distribution.md`
- `docs/release-policy.md`
- `docs/runtime-model-format.md`
- `docs/custom-models.md`
- `docs/webassembly.md`
- `tests/golden/README.md`

Optional later cleanup:

- Convert `C_REWRITE_PLAN.md` from an active planning document into a concise
  historical architecture record plus a short live roadmap section.

### 3. Add No New Code From The Old Requests Now

Most requested behavior is either:

- already implemented in the C core;
- superseded by the architecture change;
- better handled by current consumer-specific normalization;
- or too broad for the current C distribution priority.

Do not start a partition/export subsystem merely because the old Cognator docs
requested it.

### 4. Track Only Two Future Design Areas

#### Generic Partition/Projection API

Priority: deferred.

Trigger:

- A current C/Python consumer asks for sound-class partitions against the new
  C API.

Recommended shape:

- generic feature-subset projection;
- deterministic class labels;
- no `export-cognator` bundle;
- no Cognator-specific preset;
- C API first, Python wrapper second.

#### Pitch/Accent Mark Policy

Priority: deferred.

Trigger:

- A current Arca or Cognator residual report shows that `ě`, `ǎ`, `ý`, acute,
  grave, caron, or similar marks should be validated generically.

Recommended approach:

- Do not silently map accent marks to tone features.
- First decide whether they are:
  - phonological tone/pitch;
  - stress/accent;
  - orthographic source decoration;
  - source-specific normalization artifacts.
- Implement only after that policy is explicit and tested.

## Verification Snapshot

Current behavior checked during this review:

- `g`, `tʃ`, `t͡ʃ`, `dʒ`, `d͡ʒ`, `aː`, `ã`, `kʰ`, `kʷ`, `lʲ`, `ˈd`, `ai`,
  `a³¹`, and `ṵː` validate in `descriptive`.
- `mb` remains invalid while explicit `ᵐb` remains valid.
- `¹/¹` and standalone `³¹` remain invalid.

This supports deleting the old broad OOV/gap documents without losing the
current source-token policy.

## Proposed Next Commit

After review:

1. Delete the four historical package-request docs.
2. Keep this consolidation plan temporarily as the record of extracted
   decisions.
3. Optionally commit the deletion and plan together.
4. Later, delete this consolidation plan too once the durable docs are updated
   or once the cleanup commit is accepted.
