# C API

The public C API is declared in [`include/merkmal.h`](../include/merkmal.h).
It is C99-compatible and uses explicit status codes instead of exceptions.
Public functions are annotated with `MK_API` so shared-library builds export
only the supported ABI surface.

## Migrating to 1.0

Three breaking changes, all of them mechanical. They are batched into this one
release; the surface is stable from here.

| before | after |
|---|---|
| `mk_free_string(s)` | `mk_string_free(s)` |
| `mk_system_is_segment(sys, g, int *out)` | `mk_system_is_segment(sys, g, bool *out)` |
| `mk_sound_distance(fa, na, fb, nb, w, out)` | `mk_sound_distance(view_a, view_b, w, out)` |

`mk_string_free` is a rename only. It reads the way the other destructors
already did — `mk_string_list_free`, `mk_registry_free` — where the type comes
first and the verb last.

`bool` comes from `<stdbool.h>`, which the header now includes. This is an ABI
change as well as an API one on any platform where `_Bool` and `int` differ in
size, so it rides the SOVERSION bump; recompile rather than relink.

`mk_sound_distance` takes two `mk_feature_view` values instead of four
arguments. The view is a public value type, a `const char *const *` and a
`size_t`, and it borrows: both the array and the strings must outlive the call.

```c
mk_feature_view a;
mk_feature_view b;

a.features = features_a;
a.count = feature_a_count;
b.features = features_b;
b.count = feature_b_count;
mk_sound_distance(a, b, NULL, &distance);
```

## Ownership

Objects returned through output parameters are owned by the caller unless
documented otherwise.

- Free registries with `mk_registry_free`.
- Free string lists with `mk_string_list_free`.
- Free returned strings with `mk_string_free`.
- Strings returned by `mk_string_list_get` and `mk_system_name` are borrowed
  and remain valid only while the owning object is alive.

`mk_string_list` is the library's only collection type. Feature sets are
string lists whose order carries no meaning.

## Status Codes

`mk_status` values are:

- `MK_OK`
- `MK_ERR_INVALID_ARGUMENT`
- `MK_ERR_UNKNOWN_SYSTEM`
- `MK_ERR_UNKNOWN_GRAPHEME`
- `MK_ERR_UNSUPPORTED_MODEL`
- `MK_ERR_PARSE`
- `MK_ERR_OOM`
- `MK_ERR_SOURCE_MARKER`

Three of these mean "not a segment" and are worth telling apart, because a
caller checking transcriptions wants to act differently on each:

| status | meaning |
| --- | --- |
| `MK_ERR_UNKNOWN_GRAPHEME` | no path recognized this; the library may lack the segment, or the spelling may be wrong |
| `MK_ERR_PARSE` | a path recognized the *shape* and rejected the content — an over-long Chao run is tone, spelled wrong |
| `MK_ERR_SOURCE_MARKER` | not a transcription at all: CLTS's `<?>`, CLDF's `<<...>>`, or a `+`/`_`/`#` boundary marker. The **source** has a gap here; merkmal is not missing anything |

`mk_system_is_segment` reports `false` for all three and returns `MK_OK`: the
predicate is total, and the reason comes from `mk_system_grapheme_features`.

`MK_ERR_SOURCE_MARKER` was appended to the enum, so the other values keep their
numbers. A `switch` with a `default` is unaffected; one that enumerates every
value will warn until it handles the new one.

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
mk_status mk_registry_add_model_text_ex(mk_registry *registry, const char *model_text, char **diagnostic_out);
```

`mk_registry_new_builtin` creates a registry containing the compiled-in
models. `mk_registry_add_model_text` appends a caller-supplied runtime
model; see [runtime-model-format.md](runtime-model-format.md). Runtime models
are copied into the registry and do not depend on the lifetime of
`model_text`.

Runtime models are validated strictly unless they say `@validation
permissive`: every feature must reach a scoring dimension, graphemes must be
unique, and unrecognized lines are rejected. Without that check, a model
whose features the geometry does not know registers successfully and then
answers `0.0` for every comparison, which is indistinguishable from "these
segments are identical". Use `mk_registry_add_model_text_ex` to receive an
owned diagnostic naming the offending line and token; free it with
`mk_string_free`.

System pointers returned by `mk_registry_get_system` remain valid until the
registry is freed. Adding a model does not invalidate an existing system
pointer.

## Systems

```c
mk_status mk_system_name(const mk_system *system, const char **out);
mk_status mk_system_kind(const mk_system *system, const char **out);
mk_status mk_system_is_segment(const mk_system *system, const char *utf8_grapheme, bool *out);
mk_status mk_system_grapheme_features(const mk_system *system, const char *utf8_grapheme, mk_string_list **out);
mk_status mk_system_segment_distance(const mk_system *system, const char *utf8_a, const char *utf8_b, double *out);
mk_status mk_system_segment_distance_with_weights(const mk_system *system, const char *utf8_a, const char *utf8_b, const char *node_weights, double *out);
```

`node_weights` may be `NULL`, `"ignore-tone"`, `"ignore-prosodic"`,
`"segmental"`, `"tone-heavy"`, `"tone-only"`, or `"flat"`.

For the `descriptive` system, lookup and distance also support synthesized
source-token segments used by lexical datasets. These include vowel clusters
such as `ai`, `aːi`, `əi³¹`, and precomposed-vowel clusters such as `ɛï³³`,
precomposed vowel/modifier segments such as `ṵː`, broader affricate spellings
such as `tʂʰ` and `kɣ`, explicit prenasalized forms such as `ᵐb` and `ⁿdʳ`,
labial-velar stops such as `kpʷ` and `ɡb`, and tone-bearing sonorant nuclei
such as `ŋ̀`.

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

Use `mk_system_is_segment` as the non-throwing predicate before feature lookup
when processing untrusted source data. `mk_system_grapheme_features` reports
`MK_ERR_UNKNOWN_GRAPHEME` for unknown or invalid tokens.
Standalone tone clusters such as `³¹`, slash-delimited tone/control forms such
as `¹/¹`, and source markup/control tokens remain invalid. Bare `mb`, `nd`,
`mp`, `nt`, and `ŋg` are recognized as prenasalized consonant clusters; an
earlier two-item blocklist rejected `mb` and `nd` while accepting `mp` and
`nt`.

## Geometry And Unicode

```c
mk_status mk_feature_distance(const char *feature_a, const char *feature_b, int *out);
mk_status mk_sound_distance(mk_feature_view a, mk_feature_view b, const char *node_weights, double *out);
mk_status mk_normalize_grapheme(const char *utf8_in, char **utf8_out);
mk_status mk_segment_ipa(const char *utf8_in, mk_string_list **out);
mk_status mk_system_segment_ipa(const mk_system *system, const char *utf8_in, mk_string_list **out);
mk_status mk_merge_tone_digits(const mk_string_list *segments, mk_string_list **out);
mk_status mk_segment_ipa_merged(const char *utf8_in, mk_string_list **out);
mk_status mk_split_tone(const char *segment, char **base_out, char **tone_out);
```

There are two tokenization policies, and the choice matters.
`mk_segment_ipa` is orthographic: a token starts at each new base code
point unless a tie bar joins it to the previous one. It is stable and
language-neutral, but it disagrees with what a system accepts — it splits
`tʃa` into `t`, `ʃ`, `a` even though the descriptive system recognizes
untied `tʃ` as one segment. `mk_system_segment_ipa` does longest match
against the selected system instead, giving `[tʃ, a]` and `[kp, a]`.

Longest match is a policy, not a truth: `kp` may be /k.p/ in a language
with no labial-velar. Results depend on the selected system and its
inventory version, so record both with any stored tokenization. Input the
system does not recognize is passed through as its orthographic token
rather than dropped, so the function is total.

`mk_split_tone` inverts the merge: `"a¹³"` becomes `("a", "¹³")`. Consumers
that model tone as a dimension of its own need it, because the merged form
fuses the nucleus and its tone into one string. `*tone_out` is `NULL` for an
untoned segment, which is not an error; a token that is nothing but tone
digits returns `MK_ERR_UNKNOWN_GRAPHEME`, matching the standalone-tone policy
above. Both outputs are caller-owned and freed with `mk_string_free`.

### Chao digits are pitch, not tone-category numbers

Tone merging recognises **superscript** Chao digits (`⁰`–`⁵`) and the IPA tone
letters (`˥˦˧˨˩`), and no other digits. Excluding ASCII digits is deliberate
rather than an omission. A Chao digit is a pitch level, and a sequence of them
is a contour: `a⁵⁵` is high-level, `a³¹` is mid-falling, and the feature system
expands them into `tone-onset-*`, `tone-mid-*` and `tone-offset-*` features.

ASCII digits in transcriptions usually mean something else entirely — a tone
*category* label from a romanisation. Jyutping `ji6`, Vietnamese `mot6`,
Yoruba `ori3` and Pinyin `i1` number contrastive tone categories, and those
numbers encode no pitch: Jyutping tone 6 is not "Chao level 6", which does not
exist. Reading them as Chao digits would synthesise pitch features that the
notation never asserted, so ASCII digits stay unrecognised and surface as an
unknown grapheme.

A corpus using category numbers should carry tone in its own column rather
than inline, and let the consumer decide what the labels mean.

#### Level-to-feature mapping

Every tone-bearing form asserts `tone-present`, which is what separates a
mid-level tone from tonelessness. Each of the three positions then carries one
ordered level, `tone-onset-1` through `tone-offset-5`:

| notation | onset | mid | offset |
| --- | --- | --- | --- |
| `a⁵` / `a˥` | 5 | 5 | 5 |
| `a⁵¹` / `a˥˩` | 5 | 3 | 1 |
| `a⁵³¹` | 5 | 3 | 1 |

One digit sets all three positions. Two digits name the endpoints and the mid
slot takes the midpoint of the glide, so `a¹`, `a¹¹` and `a¹¹¹` are the same
segment. Three digits set the positions directly.

Because the levels are an ordered scale rather than independent flags, cost is
proportional to the difference in pitch: `d(a¹¹, a²²) < d(a¹¹, a³³) < d(a¹¹,
a⁵⁵)`. The earlier encoding used a register bit plus a height bit, under which
levels 2 and 4 differ on both and so scored as far apart as 1 and 5.

Both notations are accepted and mean the same thing: the superscript digits
`⁰`–`⁵` used in Sinological transcription, and the IPA tone letters
U+02E5–U+02E9 (`˥˦˧˨˩`), which are the primary IPA notation. Note the tone
letters run high to low: `˥` is level 5.

**Four or more digits are rejected as a whole.** There is no resampling policy,
and reinterpreting the run in pieces produced contradictory features: `a¹²³⁴`
used to be accepted carrying two different onset levels at once. `mk_segment_ipa`
keeps a run in a single token and the recognizer rejects that token whole, so
tokenization, `mk_system_is_segment`, and feature lookup share one tone grammar.
`mk_system_is_segment` reports `false`; `mk_system_grapheme_features` returns
`MK_ERR_PARSE` so the caller can tell malformed tone from an unknown grapheme.

#### Systems without tone support

The valued systems (`pbase-*`, `phoible`) have no dimension a tone modifier can
move. PHOIBLE declares a `tone` column mapped under `Tonal`, but no diacritic
effect ever sets it, so every tone-bearing grapheme kept `tone=.` and `a¹¹`
compared equal to `a⁵⁵`. Those systems now return `MK_ERR_UNSUPPORTED_MODEL`
for a tone-bearing grapheme rather than a zero that would read as established
tonal equality.

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
```

`mk_string_list_new` copies caller-provided UTF-8 strings into an owned list.
It is useful for APIs such as `mk_merge_tone_digits` where callers provide
segments that did not originate from `mk_segment_ipa`.
