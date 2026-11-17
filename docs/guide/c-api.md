# C API

The public C API is declared in [`include/merkmal.h`](../../include/merkmal.h).
It is C99 and reports failure through explicit status codes. Public functions
are annotated with `MK_API`, so a shared-library build exports only the
supported interface. The interface is not yet declared stable; changes between
releases are recorded in [CHANGELOG.md](../../CHANGELOG.md).

## Ownership

Objects returned through output parameters are owned by the caller unless
documented otherwise.

- Registries are freed with `mk_registry_free`, bundles with `mk_bundle_free`,
  string lists with `mk_string_list_free`, and returned strings with
  `mk_string_free`.
- Strings returned by `mk_string_list_get` and `mk_system_name` are borrowed
  and remain valid only while the owning object is alive.
- `mk_system_kind`, `mk_status_string` and the build-identity functions return
  static storage, which must not be freed.

`mk_string_list` is the library's only collection type. Feature sets are
string lists whose order carries no meaning.

## System identity

```c
char *payload = NULL;
char *digest = NULL;

mk_system_semantic_fingerprint(system, &payload, &digest);
/* Store both with the result, then: */
mk_string_free(payload);
mk_string_free(digest);
```

The payload is canonical UTF-8 `key=value` text and the digest is its
lowercase SHA-256 hash. It identifies the selected model, scorer, geometry and
diacritic data, resolver, tone grammar, and baseline comparison policy. It
does not identify choices made by a particular calculation, such as a
non-default node-weight preset or the caller's tokenization policy; these are
to be recorded with the fingerprint. Either output may be `NULL`, but not both.
See [docs/method/semantic-fingerprint.md](../method/semantic-fingerprint.md).

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

The diagnosis supports the checking of transcriptions. A bare
`MK_ERR_UNKNOWN_GRAPHEME` does not distinguish a mistyped combining mark, a
convention the library does not read, and a segment the system does not
contain. `mk_system_diagnose` reports the status, the longest prefix (cut at a
character boundary) that does resolve, and the character that follows it:

| input | status | valid prefix | offending |
| --- | --- | --- | --- |
| `pʰ` | `ok` | `pʰ` | — |
| `pʰ̳zz` | unknown grapheme | `pʰ` | `̳` |
| `¹²³⁴` | parse error | `¹²³` | `⁴` |
| `<?>` | source markup, not a sound | — | `<` |

The prefix localizes the problem and is often the intended segment.
`mk_system_diagnose` returns `MK_OK` unless its arguments are unusable (NULL
arguments return `MK_ERR_INVALID_ARGUMENT`, a failed allocation `MK_ERR_OOM`):
a refused grapheme is the normal case and is reported in `out->status`.

The library does not suggest a "nearest valid grapheme". An edit-distance
search over the inventory would present a guess as an answer; the prefix is
cheaper to compute and does not claim more than is known.

## Distance with coverage

```c
mk_status mk_system_segment_distance_ex(const mk_system *system,
                                        const char *utf8_a, const char *utf8_b,
                                        const char *node_weights,
                                        double *out, double *coverage,
                                        mk_comparability *why);
```

`coverage` is required (NULL returns `MK_ERR_INVALID_ARGUMENT`); `why` may be
NULL. Otherwise the statuses are those of
`mk_system_segment_distance_with_weights`, and on failure `*out` and
`*coverage` are `0.0`.

A valued system skips any dimension on which either segment has no value (`0`
or `?` in PHOIBLE, `.` in the P-base systems), so a distance of `0.0` does not
distinguish "identical" from "nothing in common to compare". PHOIBLE's tone
letters, for example, have a value on no dimension except `tone`, on which no
other segment has one, so `˦˨` scores `0.0` against every entry in the table:
against a segment with no dimension compared, against another tone letter on
that single dimension.

`*coverage` is the share of the system's declared dimensions on which both
segments have a value, in `[0, 1]`. It is measured against the system, not the
segments, so in a valued system a segment compared with itself reports less
than 1.0 whenever it leaves a dimension without a value: `("p", "p")` in
`phoible` is 27/38. `d(˦˨, d)` in `phoible` is `(0.0, 0.0)`; `d(e, i)` in
`pbase-uftc`, which that table does not distinguish, is `(0.0, 0.75)`. The
library sets no threshold: what counts as too weak a comparison depends on the
application.

Categorical systems weigh every dimension that either segment specifies, so an
ordinary pair is fully covered. A pair that reaches no scored dimension at all
reports `0.0`.

For a synthesized cluster (a diphthong, an untied consonant sequence), coverage
combines the coverage of each part comparison with the weights the distance
gives that part: nucleus and offglides, then components and the whole segment.
The length penalties that place `ai` further from `a` than `a` is from itself
measure no dimension and do not enter the coverage. Only categorical systems
synthesize clusters, so a cluster pair is fully covered unless one of its part
comparisons is not.

`*why` reports whether the pair was comparable at all:

| value | meaning |
| --- | --- |
| `MK_CMP_OK` | same tier, shared dimensions; the score is a measurement |
| `MK_CMP_CROSS_TIER` | a tone against a segment. The score is the geometry file's declared `tier_policy.cross_tier_cost`, not a measurement, and coverage is `0.0` |
| `MK_CMP_NO_SHARED_DIMENSION` | same tier, no dimension on which both have a value. A `0.0` here means "nothing to compare", not "identical" |

The cross-tier cost is part of the data, not of the code: it is
`tier_policy.cross_tier_cost` in
[`data/geometries/clements-hume.json`](../../data/geometries/clements-hume.json),
so a change to it is a versioned data change. Its value is 1.0, meaning
incomparable. The reasons are given in the note beside it in that file: expert
alignments never place a tone in the same column as a segment, the alignment
sweep in `bench/sweep_tone_distance.py` does not distinguish costs above about
0.7 from refusing to compare, and a cost computed through the geometry would
depend on how many features the other segment has rather than on any property
of tone.

## Feature vectors

```c
mk_status mk_system_vector_width(const mk_system *system, size_t *out);
mk_status mk_system_vector_labels(const mk_system *system, mk_string_list **out);
mk_status mk_system_feature_vector(const mk_system *system, const char *utf8_grapheme,
                                   double *values, size_t capacity, size_t *written);
```

The other lookup functions return feature *labels*. These functions return a
fixed-width numeric vector, for statistical and machine-learning models that
require numbers. `values` must have room for `mk_system_vector_width` entries;
when the buffer is too small the call returns `MK_ERR_INVALID_ARGUMENT` and
`*written` reports the width needed. A grapheme that does not resolve returns
its refusal status with `*written` set to 0.

The encoding follows `soundvectors` (Rubehn et al. 2024):

| value | meaning |
| ---: | --- |
| `+1` | the feature is present |
| `-1` | it applies to this kind of segment and is absent |
| `0` | it does not apply (or, in a table that does not distinguish the two, the source does not say) |
| `NaN` | a valued system's `?`: the value is not known |

The distinction between the last three rows is the reason the mapping is part
of the library: a valued system separates "does not apply" (`0` in PHOIBLE),
"unknown" (`?`) and "absent" (`-`), and a mapping written by each caller can
easily conflate them.

**Ordered scales** cannot use `0` for a middle level, since `0` already means
that the scale does not apply. A scale of *n* levels maps level *i* to *i/n*,
so scale columns lie in `(0, 1]`. In `distinctive`, `vowel_height` is 0.14 for
`i`, 0.43 for `e`, 1.0 for `a`, and 0 for `p`.

**The basis differs by system.** The columns are exactly the dimensions the
system's scorer reads, so graphemes with equal vectors are at distance zero. A
valued system's columns are its own inventory columns. A system that declares
`scalar_dimensions` uses those, followed by the geometry's ordered scales. The
remaining systems use the geometry's leaves, its ordered scales, and one-hot
node-group columns named `Node=label` (+1 when the label is present, −1 when
the node is set by another label, 0 when the node is unset). The widths in the
built-in data are 64 for `distinctive`, 68 for `descriptive`, 38 for `phoible`
and 23 for `pbase-hc`. Callers should obtain the width and order from
`mk_system_vector_width` and `mk_system_vector_labels` rather than assume them;
the labels are unique within a system, so a column can be addressed by name.

There is no function that vectorizes a token list: that is a loop over
`mk_system_feature_vector`. The library provides segment-level operations
only.

## Abstract segments

```c
mk_status mk_bundle_new(const mk_system *system, mk_bundle **out);
mk_status mk_bundle_from_grapheme(const mk_system *system, const char *g, mk_bundle **out);
mk_status mk_bundle_from_text(const mk_system *system, const char *text, mk_bundle **out);
mk_status mk_bundle_set(mk_bundle *b, const char *column, const char *cell);
mk_status mk_bundle_compare(const mk_bundle *a, const mk_bundle *b, const char *weights,
                            mk_bundle_comparison *out);
mk_status mk_bundle_compatible(const mk_bundle *b, const char *g, bool *out);
mk_status mk_bundle_compatible_graphemes(const mk_bundle *b, const char *weights,
                                         mk_string_list **out);
```

A bundle is a feature specification without a grapheme: one cell per dimension
the system's scorer reads, each holding the values the segment may have. A
comparison reports the scorer's distance over the dimensions both sides
specify, its coverage, and the exact minimum and maximum over every completion.
The cell grammar and semantics are described in
[docs/method/abstract-segments.md](../method/abstract-segments.md). A bundle
borrows its system and must be freed before the registry.

## Status codes

`mk_status` values are:

- `MK_OK`
- `MK_ERR_INVALID_ARGUMENT`
- `MK_ERR_UNKNOWN_SYSTEM`
- `MK_ERR_UNKNOWN_GRAPHEME`
- `MK_ERR_UNSUPPORTED_MODEL`
- `MK_ERR_PARSE`
- `MK_ERR_OOM`
- `MK_ERR_SOURCE_MARKER`
- `MK_ERR_DUPLICATE_SYSTEM`: a registry already holds a system by that name
- `MK_ERR_NO_TREE_PATH`: `mk_feature_distance` on a feature with no path in the geometry tree
- `MK_ERR_UNKNOWN_FEATURE`: `mk_sound_distance` or a bundle given a label or column the geometry does not know

New values are appended, so existing values keep their numbers. A `switch`
with a `default` label is unaffected by an addition; one that enumerates every
value will warn until it handles the new one.

Three statuses mean "not a segment", and a caller checking transcriptions will
usually treat them differently:

| status | meaning |
| --- | --- |
| `MK_ERR_UNKNOWN_GRAPHEME` | no path recognized the input; the system may lack the segment, or the spelling may be wrong |
| `MK_ERR_PARSE` | a path recognized the *shape* and rejected the content, as with a Chao run of four or more digits |
| `MK_ERR_SOURCE_MARKER` | not a transcription: CLTS's `<?>`, CLDF's `<<...>>`, or a `+`, `_` or `#` boundary marker. The gap is in the source, not in the library |

A fourth refusal, `MK_ERR_UNSUPPORTED_MODEL`, is returned for a tone-bearing
grapheme in a system without tone support (see
[Systems without tone support](#systems-without-tone-support)).

`mk_system_is_segment` reports `false` for the three statuses in the table and
returns `MK_OK`; `mk_system_grapheme_features` or `mk_system_diagnose` gives
the reason.

`mk_status_string(status)` returns a stable English label suitable for logs
and error messages, in static storage that must not be freed. A value outside
the enumeration gives `"unknown status"`.

```c
const char *mk_status_string(mk_status status);
```

## Build identity

```c
#define MK_VERSION_MAJOR 0
#define MK_VERSION_MINOR 9
#define MK_VERSION_PATCH 0
#define MK_VERSION_STRING "0.9.0"

const char *mk_version_string(void);   /* the linked library's version */
const char *mk_data_profile(void);     /* "full" or "cc-by" */
const char *mk_unicode_version(void);  /* Unicode version of the NFC/NFD tables */
```

The macros describe the header a caller compiled against and the functions
the library actually linked; the two can differ after a shared-library
upgrade. All three functions return static storage and cannot fail. The
version is that of the API. The data profile and the Unicode version can also
change a result between builds of one version, and
`mk_system_semantic_fingerprint` is the value to store with any result that is
kept.

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
systems; `mk_registry_list_systems` lists them in registration order,
compiled-in systems first. `mk_registry_add_model_text` adds a caller-supplied
runtime model in the format described in
[runtime-model-format.md](runtime-model-format.md). The model text is copied
into the registry and need not outlive the call. On any failure the registry
is unchanged.

A name already in the registry, including the name of a compiled-in system, is
refused with `MK_ERR_DUPLICATE_SYSTEM`. Since `mk_registry_get_system` looks a
system up by name, a second system under an existing name would be
unreachable; the caller can instead rename the model and retry. A runtime
model therefore cannot replace a built-in system by reusing its name.

Runtime models are validated strictly unless they declare `@validation
permissive`: every feature must be known to the geometry, every grapheme must
carry a feature that is scored, graphemes must be unique, and unrecognized
lines are rejected. Without this check, a model whose features the geometry
does not know would register and then return `0.0` for every comparison,
which cannot be told apart from "these segments are identical".
`mk_registry_add_model_text_ex` returns, on failure, an owned diagnostic
naming the offending line and token; it is freed with `mk_string_free`.

The first two forms take a NUL-terminated string.
`mk_registry_add_model_text_n` takes a pointer and a byte count, for a buffer
without a terminator, such as a mapped file or a Python `bytes` object, and
reads nothing past `model_text_length`. The other two forms are equivalent to
this one with `strlen`. An embedded NUL byte returns `MK_ERR_PARSE` rather than
truncating the text: the format is line-oriented, and a NUL would otherwise
end the model early and register the part before it as the whole model.

System pointers returned by `mk_registry_get_system` remain valid until the
registry is freed. Adding a model does not invalidate an existing system
pointer.

## Systems

```c
mk_status mk_system_name(const mk_system *system, const char **out);
mk_status mk_system_kind(const mk_system *system, const char **out);
mk_status mk_system_inventory(const mk_system *system, mk_string_list **out);
mk_status mk_system_is_segment(const mk_system *system, const char *utf8_grapheme, bool *out);
mk_status mk_system_grapheme_features(const mk_system *system, const char *utf8_grapheme, mk_string_list **out);
mk_status mk_system_segment_distance(const mk_system *system, const char *utf8_a, const char *utf8_b, double *out);
mk_status mk_system_segment_distance_with_weights(const mk_system *system, const char *utf8_a, const char *utf8_b, const char *node_weights, double *out);
```

`mk_system_name` and `mk_system_kind` serve a caller that holds a system
pointer but not the name under which it was looked up. The kind is one of
`categorical`, `valued` or `trained`; no built-in system is of kind
`trained`. The kind determines what coverage means: in a valued system it is a
fraction of the declared dimensions, in a categorical one it is 1.0 for any
pair that reaches a scored dimension. The two functions have the same
signature but different lifetimes: the name is owned by the registry, the kind
is static.

`mk_system_inventory` lists the graphemes of the system's own table (in UTF-8
byte order for a compiled-in system, in file order for a runtime model).
Graphemes the resolver derives from a base segment and diacritics are not
included, since that set is unbounded.

`node_weights` may be `NULL` (the default weights) or one of the presets
`"flat"`, `"ignore-length"`, `"ignore-prosodic"`, `"ignore-secondary"`,
`"ignore-tone"`, `"segmental"`, `"tone-heavy"` and `"tone-only"`, defined in
[`data/geometries/clements-hume.json`](../../data/geometries/clements-hume.json).
An unknown preset returns `MK_ERR_INVALID_ARGUMENT`.

In the categorical systems (among the built-in ones, `distinctive` and
`descriptive`), lookup and distance also accept segments that are not listed in the table but
are synthesized from listed ones, as they occur in lexical datasets: vowel
sequences such as `ai`, `aːi`, `əi³¹` and `ɛï³³`, precomposed vowels with
modifiers such as `ṵː`, affricates written without a tie bar such as `tʂʰ` and
`kɣ`, prenasalized consonants such as `ᵐb`, `ⁿdʳ`, `mb` and `nd`, labial-velar
stops such as `kpʷ` and `ɡb`, and tone-bearing syllabic consonants such as
`ŋ̀`. The valued systems do not synthesize segments; they accept only the
sequences their source tables list.

A synthesized vowel sequence carries position-qualified and movement features
rather than the contradictory unqualified qualities of its components:

```text
vowel
diphthong
n1-open
n2-close
move-height-open-close
```

`mk_system_is_segment` is a predicate for screening untrusted source data
before feature lookup; `mk_system_grapheme_features` returns the refusal
status for input it does not accept. A token that is only tone, such as `³¹`
or `˦˨`, is accepted by the categorical systems as a tone segment carrying the
unscored feature `tonal-autosegment`; source markup is refused with
`MK_ERR_SOURCE_MARKER`.

## Geometry and Unicode

```c
mk_status mk_feature_distance(const char *feature_a, const char *feature_b, int *out);
mk_status mk_sound_distance(mk_feature_view a, mk_feature_view b, const char *node_weights, double *out);
mk_status mk_normalize_grapheme(const char *utf8_in, char **utf8_out);
mk_status mk_unicode_normalize(const char *utf8_in, mk_normalization_form form, char **utf8_out);
mk_status mk_segment_ipa(const char *utf8_in, mk_string_list **out);
mk_status mk_system_segment_ipa(const mk_system *system, const char *utf8_in, mk_string_list **out);
mk_status mk_merge_tone_digits(const mk_string_list *segments, mk_string_list **out);
mk_status mk_segment_ipa_merged(const char *utf8_in, mk_string_list **out);
mk_status mk_split_tone(const char *segment, char **base_out, char **tone_out);
```

`mk_feature_distance` counts the edges between two features along the
geometry tree, and is defined only for the 110 features the tree contains.
Many features that a system returns are reached by the scorer in another way
and have no tree path: `bilabial` and `velar` are mapped to the `Place` node
rather than being leaves under it, and an ordered-scale level such as
`tone-onset-1` is a position on a scale. If either feature is off the tree,
the function returns `MK_ERR_NO_TREE_PATH` and leaves `*out` unwritten.

A status is used rather than a sentinel distance because the real results are
small integers, and a sentinel such as `999` would be indistinguishable from
an ordinary value to a caller that sums or thresholds them. The domain is
checked before identity: a feature the tree does not contain, including a
misspelt one, returns `MK_ERR_NO_TREE_PATH` even when compared with itself.

The result is a tree measurement, not a phonological distance. Segments are
compared with `mk_system_segment_distance`, which also reads node groups and
ordered scales and is defined for every feature a system returns.

`mk_sound_distance` scores two caller-supplied feature sets against the
compiled geometry, without a system. Both views are borrowed for the duration
of the call: the array and the strings belong to the caller. A label that the
geometry knows neither as a scored nor as a metadata feature returns
`MK_ERR_UNKNOWN_FEATURE` rather than being skipped, since a skipped label
(`foo`, or a misspelling) would score exactly like an absent one. Labels are
privative: a negative value is expressed by the opposite label (`voiceless`),
never by a sign (`-voice`).

```c
mk_feature_view a;
mk_feature_view b;

a.features = features_a;
a.count = feature_a_count;
b.features = features_b;
b.count = feature_b_count;
mk_sound_distance(a, b, NULL, &distance);
```

There are two tokenization policies, and the choice affects the results.
`mk_segment_ipa` is orthographic: a token starts at each new base code point
unless a tie bar joins it to the previous one. It is stable and
language-neutral, but it does not agree with what a system accepts: it splits
`tʃa` into `t`, `ʃ`, `a`, although the categorical systems recognize untied
`tʃ` as one segment. `mk_system_segment_ipa` instead takes the longest match
against the selected system, giving `[tʃ, a]` and `[kp, a]`.

Longest match is a policy, not an analysis: `kp` may be /k.p/ in a language
without labial-velars. Results depend on the selected system and its
inventory version, and both should be recorded with any stored tokenization.
Input the system does not recognize is passed through as its orthographic
token rather than dropped, so the function is total over its input.

`mk_merge_tone_digits` attaches each token consisting only of Chao tone
characters to the nearest preceding syllabic segment (one containing a vowel
letter or U+0329) within the same `+`-delimited word, so that `tʰ`, `o`, `ŋ`,
`⁵⁵` becomes `tʰ`, `o⁵⁵`, `ŋ`. A tone token with no such segment before it,
and a token consisting only of `⁰`, is dropped. `mk_segment_ipa_merged` is
`mk_segment_ipa` followed by this merge.

`mk_split_tone` is the inverse of the merge: `"a¹³"` becomes `("a", "¹³")`. It
serves consumers that model tone as a separate dimension, since the merged
form joins the nucleus and its tone in one string. `*tone_out` is `NULL` for
an untoned segment, which is not an error. A token that consists only of tone
characters returns `MK_ERR_UNKNOWN_GRAPHEME`, since there is no base to split
off. Both outputs are owned by the caller and freed with `mk_string_free`.

The split is orthographic, like `mk_segment_ipa`: it cuts at the first Chao
character without reading the run. `"a¹²³⁴"` splits into `("a", "¹²³⁴")` and
returns `MK_OK`, although a run of four levels is not a valid contour and
`mk_system_is_segment` reports `false` for that token. Its only error concerns
shape (no base to split off), never the content of the run. Callers that need
the content checked use `mk_system_is_segment` or
`mk_system_grapheme_features`, which return `MK_ERR_PARSE` for that token.

`mk_normalize_grapheme` returns merkmal's NFC form of a grapheme together with
its IPA rewrites; `mk_unicode_normalize` applies plain Unicode canonical
normalization (NFC or NFD, UAX #15) without IPA rewrites, and passes malformed
bytes through unchanged. The tokenizers work in NFD. All of these use compiled
Unicode tables and normalize identically in every build; see
[installation.md](installation.md#unicode-normalization).

### Chao digits are pitch, not tone-category numbers

Tone is recognized in two notations: the **superscript** Chao digits (`⁰`–`⁵`)
used in Sinological transcription, and the IPA tone letters U+02E5–U+02E9
(`˥˦˧˨˩`), which are the primary IPA notation. The tone letters run from high
to low: `˥` is level 5. There is no tone letter for level 0. No other digits
are read as tone.

A Chao digit is a pitch level, and a sequence of digits is a contour: `a⁵⁵` is
high level, `a³¹` mid falling. The feature system expands them into
`tone-onset-*`, `tone-mid-*` and `tone-offset-*` features.

ASCII digits in transcriptions usually denote something else: a tone
*category* in a romanization. Jyutping `ji6`, Vietnamese `mot6`, Yoruba `ori3`
and Pinyin `i1` number contrastive tone categories, and these numbers encode no
pitch: Jyutping tone 6 is not Chao level 6, which does not exist. Reading them
as Chao digits would assert pitch features that the notation does not assert,
so ASCII digits are not recognized and a token containing them is an unknown
grapheme. A corpus that uses category numbers should carry tone in a separate
column and leave its interpretation to the consumer.

`⁰` denotes Chao's neutral tone, a syllable without tone in a language that
otherwise has tone. It is not a pitch level: as a tone token of its own it
carries `tone-present` and `tone-neutral` and none of the ordered levels. It is
not combined with pitch levels in one run (`MK_ERR_PARSE`), and it is not
accepted bound to a nucleus (`a⁰` is `MK_ERR_UNKNOWN_GRAPHEME`).

#### Level-to-feature mapping

Every tone-bearing form carries `tone-present`, which distinguishes a mid level
tone from the absence of tone. Each of the three positions then carries one
ordered level, from `tone-onset-1` to `tone-offset-5`:

| notation | onset | mid | offset |
| --- | --- | --- | --- |
| `a⁵` / `a˥` | 5 | 5 | 5 |
| `a⁵¹` / `a˥˩` | 5 | 3 | 1 |
| `a⁵³¹` | 5 | 3 | 1 |

One digit sets all three positions. Two digits name the endpoints and the mid
position takes the midpoint of the glide, so `a¹`, `a¹¹` and `a¹¹¹` are the
same segment. Three digits set the positions directly.

Because the levels form an ordered scale rather than independent features, the
cost of a difference grows with the difference in pitch:
`d(a¹¹, a²²) < d(a¹¹, a³³) < d(a¹¹, a⁵⁵)`.

**A run of four or more levels is rejected as a whole.** No resampling policy
is defined, and reading the run in parts would assign contradictory levels to
one position. `mk_segment_ipa` keeps the run in a single token and the
recognizer rejects that token, so tokenization, `mk_system_is_segment` and
feature lookup share one tone grammar. `mk_system_is_segment` reports `false`;
`mk_system_grapheme_features` returns `MK_ERR_PARSE`, so that malformed tone
can be told apart from an unknown grapheme.

#### Systems without tone support

The valued systems (`pbase-*`, `phoible`) define no dimension that a tone mark
on a segment can set, so a tone-bearing segment would score as if it carried
no tone, and `a¹¹` would compare equal to `a⁵⁵`. These systems therefore return
`MK_ERR_UNSUPPORTED_MODEL` for a tone-bearing segment and for a bare tone token
that their table does not list, rather than a zero that would read as tonal
identity.

## Containers

```c
mk_status mk_string_list_new(const char *const *items, size_t count, mk_string_list **out);
size_t mk_string_list_size(const mk_string_list *list);
const char *mk_string_list_get(const mk_string_list *list, size_t index);
void mk_string_list_free(mk_string_list *list);
```

`mk_string_list_new` copies caller-provided UTF-8 strings into an owned list.
It serves functions such as `mk_merge_tone_digits` when the segments do not
come from `mk_segment_ipa`.

## References

- Rubehn, Arne, Jessica Nieder, Robert Forkel and Johann-Mattis List. 2024.
  Generating feature vectors from phonetic transcriptions in cross-linguistic
  data formats. In *Proceedings of the Society for Computation in Linguistics
  2024*.
