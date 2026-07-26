# C API

The public C API is declared in [`include/merkmal.h`](../include/merkmal.h).
It is C99-compatible and uses explicit status codes instead of exceptions.
Public functions are annotated with `MK_API` so shared-library builds export
only the supported ABI surface.

## Ownership

Objects returned through output parameters are owned by the caller unless
documented otherwise.

- Free registries with `mk_registry_free`.
- Free string lists with `mk_string_list_free`.
- Free feature sets with `mk_feature_set_free`.
- Free returned strings with `mk_free_string`.
- Strings returned by `mk_string_list_get`, `mk_feature_set_get`, and
  `mk_system_name` are borrowed and remain valid only while the owning
  object is alive.

## Status Codes

`mk_status` values are:

- `MK_OK`
- `MK_ERR_INVALID_ARGUMENT`
- `MK_ERR_UNKNOWN_SYSTEM`
- `MK_ERR_UNKNOWN_GRAPHEME`
- `MK_ERR_UNSUPPORTED_MODEL`
- `MK_ERR_PARSE`
- `MK_ERR_OOM`

Use `mk_status_string(status)` for a stable English diagnostic label suitable
for logs and error messages. The returned string is static storage owned by
the library and must not be freed.

```c
const char *mk_status_string(mk_status status);
```

## Registry

```c
mk_status mk_registry_new_builtin(mk_registry **out);
void mk_registry_free(mk_registry *registry);
mk_status mk_registry_list_systems(const mk_registry *registry, mk_string_list **out);
mk_status mk_registry_get_system(const mk_registry *registry, const char *name, const mk_system **out);
mk_status mk_registry_add_model_text(mk_registry *registry, const char *model_text);
```

`mk_registry_new_builtin` creates a registry containing the compiled-in
models. `mk_registry_add_model_text` appends a caller-supplied runtime
model; see [runtime-model-format.md](runtime-model-format.md). Runtime models
are copied into the registry and do not depend on the lifetime of
`model_text`.

## Systems

```c
mk_status mk_system_name(const mk_system *system, const char **out);
mk_status mk_system_kind(const mk_system *system, const char **out);
mk_status mk_system_is_segment(const mk_system *system, const char *utf8_grapheme, int *out);
mk_status mk_system_grapheme_features(const mk_system *system, const char *utf8_grapheme, mk_feature_set **out);
mk_status mk_system_segment_distance(const mk_system *system, const char *utf8_a, const char *utf8_b, double *out);
mk_status mk_system_segment_distance_with_weights(const mk_system *system, const char *utf8_a, const char *utf8_b, const char *node_weights, double *out);
```

`node_weights` may be `NULL`, `"ignore-tone"`, `"ignore-prosodic"`,
`"segmental"`, `"tone-heavy"`, `"tone-only"`, or `"flat"`.

For the `descriptive` system, lookup and distance also support synthesized
source-token segments used by lexical datasets. These include vowel clusters
such as `ai`, `aːi`, and `əi³¹`, broader affricate spellings such as `tʂʰ`,
explicit prenasalized forms such as `ᵐb` and `ⁿdʳ`, labial-velar stops such as
`kpʷ` and `ɡb`, and tone-bearing sonorant nuclei such as `ŋ̀`.

Synthesized vowel clusters expose position-qualified and movement features
instead of contradictory unqualified component qualities:

```text
vowel
diphthong
n1-open
n2-close
move-height-open-close
```

The behavior is currently descriptive-only. Other categorical systems are a
roadmap item, and valued systems need a separate design pass.

## Geometry And Unicode

```c
mk_status mk_feature_distance(const char *feature_a, const char *feature_b, int *out);
mk_status mk_sound_distance(const char *const *features_a, size_t feature_a_count, const char *const *features_b, size_t feature_b_count, const char *node_weights, double *out);
mk_status mk_normalize_grapheme(const char *utf8_in, char **utf8_out);
mk_status mk_segment_ipa(const char *utf8_in, mk_string_list **out);
mk_status mk_merge_tone_digits(const mk_string_list *segments, mk_string_list **out);
mk_status mk_segment_ipa_merged(const char *utf8_in, mk_string_list **out);
```

`mk_normalize_grapheme` uses `utf8proc` when available. The fallback path
covers the IPA normalization cases used by the built-in models and tests.
Release builds should enable `utf8proc`; see
[release-policy.md](release-policy.md).

## Containers

```c
mk_status mk_string_list_new(const char *const *items, size_t count, mk_string_list **out);
size_t mk_string_list_size(const mk_string_list *list);
const char *mk_string_list_get(const mk_string_list *list, size_t index);
void mk_string_list_free(mk_string_list *list);

size_t mk_feature_set_size(const mk_feature_set *features);
const char *mk_feature_set_get(const mk_feature_set *features, size_t index);
void mk_feature_set_free(mk_feature_set *features);
```

`mk_string_list_new` copies caller-provided UTF-8 strings into an owned list.
It is useful for APIs such as `mk_merge_tone_digits` where callers provide
segments that did not originate from `mk_segment_ipa`.
