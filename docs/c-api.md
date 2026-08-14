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

## Diagnosing a refusal

```c
typedef struct mk_diagnosis {
    mk_status status;
    size_t valid_prefix_bytes;
    size_t offending_offset;
    char offending[8];
} mk_diagnosis;

mk_status mk_system_diagnose(const mk_system *system, const char *utf8_grapheme,
                             mk_diagnosis *out);
```

Checking someone's transcriptions is the workflow a validated inventory and a
fast C core should be best in the world at, and there the diagnosis *is* the
product. A bare `MK_ERR_UNKNOWN_GRAPHEME` does not tell an author whether they
mistyped one combining mark, used a convention this library does not read, or
wrote a sound it genuinely lacks.

| input | status | valid prefix | offending |
| --- | --- | --- | --- |
| `pʰ` | `ok` | `pʰ` | — |
| `pʰ̳zz` | unknown grapheme | `pʰ` | `̳` |
| `¹²³⁴` | parse error | `¹²³` | `⁴` |
| `<?>` | source markup, not a sound | — | `<` |

The longest resolving prefix localizes the problem and is usually the repair.
`mk_system_diagnose` returns `MK_OK` unless its arguments are unusable — a
refused grapheme is the normal case and is reported in `out->status`.

There is deliberately **no "nearest valid grapheme"**. An edit-distance search
over the inventory would be a guess presented as an answer, and the prefix is
both cheaper and more often right.

## Distance with coverage

```c
mk_status mk_system_segment_distance_ex(const mk_system *system,
                                        const char *utf8_a, const char *utf8_b,
                                        const char *node_weights,
                                        double *out, double *coverage,
                                        mk_comparability *why);
```

`coverage` is required — it is what this entry point is for. `why` may be NULL.

A valued system skips any dimension where either segment has no value, so `0.0`
is ambiguous between "identical" and "nothing in common to compare". PHOIBLE
writes `.` in 30,181 cells and its tone letters are `.` on every dimension, so
`˦˨` scores `0.0` against every segment in the table.

`*coverage` is measured against the system's declared dimensions, not against
the segments, so a segment compared with itself reports less than 1.0 whenever
it has a gap: `("p", "p")` on PHOIBLE is 27/38.

`*why` reports whether the pair was comparable at all:

| value | meaning |
| --- | --- |
| `MK_CMP_OK` | same tier, shared dimensions; the score is a measurement |
| `MK_CMP_CROSS_TIER` | a tone against a segment. The score is the geometry file's declared `tier_policy.cross_tier_cost`, not a measurement |
| `MK_CMP_NO_SHARED_DIMENSION` | same tier, no dimension both have a value on. A `0.0` here means "nothing to compare", not "identical" |

**Cross-tier is a policy, and the policy is data.** `tier_policy.cross_tier_cost`
lives in `geometries/clements-hume.json`, so changing it is a versioned data
change with a diff rather than a tree edit — and a later evidence-derived scorer
can carry its own without disturbing this one. It is 1.0, meaning incomparable:
gold alignments never place a tone in a column with a segment, and
`bench/sweep_tone_distance.py` saturates above roughly 0.7, so the data cannot
distinguish any cost in that region from refusing to compare. Scoring a tone
through the geometry instead gives 0.61 against a stop and 0.50 against a vowel,
which are functions of how many features the *other* segment has rather than
statements about tone.

`*coverage` is the share of the system's declared dimensions on which both
segments had a value, in `[0, 1]`. `d(˦˨, d)` in PHOIBLE is `(0.0, 0.0)`;
`d(e, i)` in P-base UFTC, genuinely indistinguishable there, is `(0.0, 0.75)`.
The library sets no threshold — what counts as too weak a comparison depends on
the work.

Categorical systems weigh any dimension either segment specifies, so an ordinary
pair is fully covered and the ambiguity does not arise. A pair reaching no
scored dimension at all still reports `0.0` rather than claiming a comparison
that did not happen.

## Feature vectors

```c
mk_status mk_system_vector_width(const mk_system *system, size_t *out);
mk_status mk_system_vector_labels(const mk_system *system, mk_string_list **out);
mk_status mk_system_feature_vector(const mk_system *system, const char *utf8_grapheme,
                                   double *values, size_t capacity, size_t *written);
```

Everything else here returns feature *labels*, which is the right shape for
reasoning about a segment and the wrong one for a model that wants numbers.

The encoding follows `soundvectors` (Rubehn, Nieder, Forkel & List 2024), so the
numbers mean what the rest of the ecosystem means by them:

| value | meaning |
| ---: | --- |
| `+1` | the feature is present |
| `-1` | it applies to this kind of segment and is absent |
| `0` | it does not apply, or the source does not say |

That last row is why this is worth having in the library rather than in each
caller: a valued system writes `anterior=.` for "no value" and `anterior=-` for
"absent", and a hand-written mapping tends to collapse them.

**Ordered scales** cannot use `0` for a middle level, since `0` already means "no
value". A scale of *n* levels maps level *i* to *i/n*, so scale columns land in
`(0, 1]` and `0` still means the scale does not apply. `vowel_height` is 0.14 for
`/i/`, 0.43 for `/e/`, 1.0 for `/a/`, and 0 for `/p/`.

**The basis differs by system**, because the systems differ: a valued system's
columns are its own inventory columns, a system declaring `scalar_dimensions`
uses those, and the rest use the geometry they score through. Widths today are
54 for `distinctive`, 62 for `descriptive`, 38 for `phoible`, 23 for `pbase-hc`.
Call `mk_system_vector_labels` rather than assuming either width or order; the
labels are unique within a system, so a column is addressable by name.

There is no call that vectorizes a token list. It is a loop over
`mk_system_feature_vector`, and the library does not own sequence-level
operations (see `REFERENCE_LIBRARY_PLAN.md`, D2).

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
mk_status mk_registry_add_model_text_n(mk_registry *registry, const char *model_text, size_t model_text_length, char **diagnostic_out);
```

`mk_registry_new_builtin` creates a registry containing the compiled-in
models. `mk_registry_add_model_text` appends a caller-supplied runtime
model; see [runtime-model-format.md](runtime-model-format.md). Runtime models
are copied into the registry and do not depend on the lifetime of
`model_text`.

A name already in the registry is refused with `MK_ERR_DUPLICATE_SYSTEM`,
including the compiled-in names. `mk_registry_get_system` returns the first
match, so a second system under an existing name would install successfully and
then be unreachable for the rest of the registry's life. Nothing is installed
when the name is taken, so the registry is unchanged and the caller can rename
and retry. There is no shadowing: a runtime model cannot override a built-in by
reusing its name.

Runtime models are validated strictly unless they say `@validation
permissive`: every feature must reach a scoring dimension, graphemes must be
unique, and unrecognized lines are rejected. Without that check, a model
whose features the geometry does not know registers successfully and then
answers `0.0` for every comparison, which is indistinguishable from "these
segments are identical". Use `mk_registry_add_model_text_ex` to receive an
owned diagnostic naming the offending line and token; free it with
`mk_string_free`.

The first two forms take a NUL-terminated string.
`mk_registry_add_model_text_n` takes a pointer and a byte count instead, for a
caller holding a buffer that owes the library no terminator — a mapped file,
a Python `bytes`, a fuzzer's input. Nothing past `model_text_length` is read.
The other two forms are this one with `strlen`.

An embedded NUL byte returns `MK_ERR_PARSE` rather than truncating. The format
is line-oriented text, and a NUL in the middle would otherwise end the model
early and register the part before it as though it were the whole thing.

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

`mk_system_name` and `mk_system_kind` answer for a caller holding a system
pointer rather than the name it looked the system up by. The kind — one of
`categorical`, `valued`, `trained` — is worth asking for because coverage means
different things by it: a valued system's is a real fraction, a categorical
one's is 1.0 for any pair reaching a scored dimension. Their lifetimes differ
behind identical signatures: the name is registry-owned, the kind is static.

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

`mk_feature_distance` counts hops along the geometry tree, and is defined only
over the 110 features the tree contains. A feature the geometry reaches some
other way has no tree path and no tree distance: `bilabial` and `velar` are
mapped to the `Place` node rather than being leaves under it, and an
ordered-scale level such as `tone-onset-1` is a position on a scale. Roughly two
in five of the labels a categorical system can return are in that group, and
either feature being off the tree returns `MK_ERR_NO_TREE_PATH`.

It is a tree measurement, not a phonological distance. For two segments use
`mk_system_segment_distance`, which reads node groups and ordered scales too and
is defined for every feature a system returns.

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

The split is orthographic, like `mk_segment_ipa` and for the same reason: it
finds the first Chao digit and cuts there without reading the run. `"a¹²³⁴"`
splits into `("a", "¹²³⁴")` and returns `MK_OK`, even though four digits are
rejected as a contour and `mk_system_is_segment` reports `false` for that token.
Its one error is about shape — there is no base to split off — never about the
content of the run. A caller who needs the content checked has
`mk_system_is_segment` and `mk_system_grapheme_features`, which return
`MK_ERR_PARSE` where this returns a clean split.

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
