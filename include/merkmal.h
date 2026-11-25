#ifndef MERKMAL_H
#define MERKMAL_H

#include <stdbool.h>
#include <stddef.h>

#if defined(_WIN32) && defined(MERKMAL_SHARED)
#if defined(MERKMAL_BUILDING_LIBRARY)
#define MK_API __declspec(dllexport)
#else
#define MK_API __declspec(dllimport)
#endif
#elif defined(__GNUC__) || defined(__clang__)
#define MK_API __attribute__((visibility("default")))
#else
#define MK_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

/** A borrowed feature set: the array and the strings both belong to the
 * caller and must outlive the call. `features` may be NULL only when `count`
 * is 0. Feature order carries no meaning.
 *
 * A public value type rather than an opaque one: it is exactly a pointer and
 * a count, so there is nothing to hide, and every function that scores
 * features takes the same two fields. */
typedef struct mk_feature_view {
    const char *const *features;
    size_t count;
} mk_feature_view;

typedef struct mk_registry mk_registry;
typedef struct mk_system mk_system;
typedef struct mk_string_list mk_string_list;

/** Every public function that can fail returns one of these.
 *
 * New statuses are appended, never inserted, so existing values keep their
 * numbers. mk_status_string names each. */
typedef enum mk_status {
    MK_OK = 0,
    MK_ERR_INVALID_ARGUMENT,
    MK_ERR_UNKNOWN_SYSTEM,
    MK_ERR_UNKNOWN_GRAPHEME,
    MK_ERR_UNSUPPORTED_MODEL,
    MK_ERR_PARSE,
    MK_ERR_OOM,
    /** The token is CLDF/CLTS markup, not a transcription of a sound: CLTS's
     * `<?>`, CLDF's `<<...>>`, or a `+`, `_` or `#` boundary marker. The
     * source has a gap here; MK_ERR_UNKNOWN_GRAPHEME would say the library
     * lacks the sound. See docs/guide/c-api.md, Status Codes. */
    MK_ERR_SOURCE_MARKER,
    /** A registry already holds a system by that name, including a
     * compiled-in one. Nothing was installed. Its own status rather than
     * MK_ERR_INVALID_ARGUMENT, so the caller can tell it from a null pointer
     * and rename, skip or warn. See docs/guide/c-api.md, Registry. */
    MK_ERR_DUPLICATE_SYSTEM,
    /** A feature has no path in the geometry tree, so no tree distance is
     * defined for it. See mk_feature_distance. */
    MK_ERR_NO_TREE_PATH,
    /** A feature label the geometry does not know, given to
     * mk_sound_distance, or a column name a bundle does not have. Not
     * skipped: a skipped typo would score like no label at all. See
     * docs/guide/c-api.md, Geometry And Unicode. */
    MK_ERR_UNKNOWN_FEATURE
} mk_status;

/** The stable English label for a status code, in static storage that must
 * not be freed. A value outside the enum gives "unknown status". Total. */
MK_API const char *mk_status_string(mk_status status);

/** Build identity.
 *
 * The macros are the version of the header a caller compiled against; the
 * three functions below answer for the library actually linked, which can
 * differ under a shared-library upgrade. Each function returns static storage
 * and cannot fail. The version is the API's, not the data's: store
 * mk_system_semantic_fingerprint with any result kept. See docs/guide/c-api.md,
 * Build Identity. */
#define MK_VERSION_MAJOR 0
#define MK_VERSION_MINOR 9
#define MK_VERSION_PATCH 0
#define MK_VERSION_STRING "0.9.0"

/** The linked library's version, as "MAJOR.MINOR.PATCH". */
MK_API const char *mk_version_string(void);
/** The compiled-in data profile: "full" or "cc-by". See NOTICE. */
MK_API const char *mk_data_profile(void);
/** The Unicode version of the compiled-in normalization tables, e.g. "15.1.0". */
MK_API const char *mk_unicode_version(void);

/** Creates a registry containing the compiled-in systems. On MK_OK *out is
 * owned by the caller and freed with mk_registry_free; on failure it is NULL. */
MK_API mk_status mk_registry_new_builtin(mk_registry **out);
/** Frees a registry and every system in it, which invalidates every system
 * pointer and borrowed name taken from it. Tolerates NULL. */
MK_API void mk_registry_free(mk_registry *registry);

/** An owned list of system names in registration order, compiled-in systems
 * first. Free with mk_string_list_free. */
MK_API mk_status mk_registry_list_systems(
    const mk_registry *registry,
    mk_string_list **out
);

/** Looks up a system by exact name. *out is borrowed from the registry and
 * stays valid until mk_registry_free, even across later additions. An unknown
 * name returns MK_ERR_UNKNOWN_SYSTEM and sets *out to NULL. */
MK_API mk_status mk_registry_get_system(
    const mk_registry *registry,
    const char *name,
    const mk_system **out
);

/** Adds a categorical model described by the runtime text format (see
 * docs/guide/runtime-model-format.md). The text is copied; it need not outlive the
 * call. A name already registered returns MK_ERR_DUPLICATE_SYSTEM, malformed
 * or invalid text MK_ERR_PARSE, and a model type or geometry other than
 * categorical over clements-hume MK_ERR_UNSUPPORTED_MODEL. On any failure the
 * registry is unchanged.
 *
 * Validation is strict unless the model says '@validation permissive': every
 * feature must reach a scoring dimension, graphemes must be unique, and
 * unrecognized lines are rejected. Otherwise a model whose features the
 * geometry does not know would score every comparison as zero. See
 * docs/guide/c-api.md, Registry. */
MK_API mk_status mk_registry_add_model_text(
    mk_registry *registry,
    const char *model_text
);

/** As mk_registry_add_model_text, but on failure *diagnostic_out may receive
 * an owned message naming the offending line and token; free it with
 * mk_string_free. It is NULL on success. `diagnostic_out` itself may be NULL
 * when the caller does not want the detail. */
MK_API mk_status mk_registry_add_model_text_ex(
    mk_registry *registry,
    const char *model_text,
    char **diagnostic_out
);

/** As mk_registry_add_model_text_ex, but for text that need not be
 * NUL-terminated: `model_text_length` is a byte count and nothing past it is
 * read. The other two forms are this one with strlen.
 *
 * An embedded NUL returns MK_ERR_PARSE rather than truncating: it would end
 * the model early and register the part before it as if it were whole. */
MK_API mk_status mk_registry_add_model_text_n(
    mk_registry *registry,
    const char *model_text,
    size_t model_text_length,
    char **diagnostic_out
);

/** The system's registered name. *out is borrowed from the registry and
 * valid until mk_registry_free; mk_system_kind's string, behind the same
 * signature, is static instead. See docs/guide/c-api.md, Systems. */
MK_API mk_status mk_system_name(const mk_system *system, const char **out);
/** One of "categorical", "valued", or "trained", in static storage. Coverage
 * means different things by kind; see mk_system_segment_distance_ex. */
MK_API mk_status mk_system_kind(const mk_system *system, const char **out);

/** The canonical system-level semantic fingerprint and its SHA-256 digest.
 * Both outputs are owned strings, freed with mk_string_free. Either of
 * `payload_out` and `digest_out` may be NULL when the caller needs only the
 * other, but not both.
 *
 * The payload identifies the model data, scorer, geometry and diacritic
 * data, resolver and tone policies, and is separate from the library version:
 * two builds of one version can produce different results. It describes the
 * system only; record per-call choices such as a non-default weight preset or
 * a tokenization policy alongside it. See docs/method/semantic-fingerprint.md. */
MK_API mk_status mk_system_semantic_fingerprint(
    const mk_system *system,
    char **payload_out,
    char **digest_out
);

/** Whether the system recognizes this grapheme, without allocating a feature
 * result.
 *
 * Input the system does not recognize, input it recognizes and rejects (an
 * over-long Chao run), and source markup all set *out to false and return
 * MK_OK. Other failures are still returned with *out false: a tone-bearing
 * grapheme in a system without tone support is MK_ERR_UNSUPPORTED_MODEL, and
 * NULL arguments are MK_ERR_INVALID_ARGUMENT. Use mk_system_grapheme_features
 * or mk_system_diagnose when the reason matters. */
MK_API mk_status mk_system_is_segment(
    const mk_system *system,
    const char *utf8_grapheme,
    bool *out
);

/** The features of one grapheme, as an owned list in no meaningful order;
 * free with mk_string_list_free. A refusal returns MK_ERR_UNKNOWN_GRAPHEME,
 * MK_ERR_PARSE, MK_ERR_SOURCE_MARKER or MK_ERR_UNSUPPORTED_MODEL; see
 * docs/guide/c-api.md, Status Codes. */
MK_API mk_status mk_system_grapheme_features(
    const mk_system *system,
    const char *utf8_grapheme,
    mk_string_list **out
);

/** The system's distance between two graphemes, with the default weights.
 * Either grapheme failing to resolve returns its status. */
MK_API mk_status mk_system_segment_distance(
    const mk_system *system,
    const char *utf8_a,
    const char *utf8_b,
    double *out
);

/** As mk_system_segment_distance, with a named weight preset, or NULL for the
 * default. An unknown preset returns MK_ERR_INVALID_ARGUMENT. The presets are
 * listed in docs/guide/c-api.md, Systems. */
MK_API mk_status mk_system_segment_distance_with_weights(
    const mk_system *system,
    const char *utf8_a,
    const char *utf8_b,
    const char *node_weights,
    double *out
);

/** Hop count between two feature names along the geometry tree.
 *
 * Defined only over features that are points on the tree. Either feature
 * being off the tree returns MK_ERR_NO_TREE_PATH and leaves *out unwritten,
 * even when the two are the same string, so a misspelling is never 0 against
 * itself. Many labels a system returns are off the tree (`bilabial`,
 * `tone-onset-1`).
 *
 * A tree measurement, not a phonological distance: compare segments with
 * mk_system_segment_distance. See docs/guide/c-api.md, Geometry And Unicode. */
MK_API mk_status mk_feature_distance(
    const char *feature_a,
    const char *feature_b,
    int *out
);

/** Distance between two caller-provided feature sets, scored against the
 * compiled geometry with no system, registry, or grapheme involved. Both
 * views are borrowed for the call only.
 *
 * `node_weights` names a weight preset, or is NULL for the default. An unknown
 * preset returns MK_ERR_INVALID_ARGUMENT rather than a score.
 *
 * A label the geometry does not know, scored or metadata, returns
 * MK_ERR_UNKNOWN_FEATURE. Labels are privative: a negative value is the
 * opposite label (`voiceless`), never a sign (`-voice`). */
MK_API mk_status mk_sound_distance(
    mk_feature_view a,
    mk_feature_view b,
    const char *node_weights,
    double *out
);

/** Normalizes one UTF-8 grapheme to merkmal's NFC form, with its IPA
 * rewrites. *utf8_out is owned; free with mk_string_free. */
MK_API mk_status mk_normalize_grapheme(
    const char *utf8_in,
    char **utf8_out
);

/** Orthographic tokenization into an owned list (free with
 * mk_string_list_free): a new token starts at each new base code point unless
 * a tie bar joins it to the previous one.
 *
 * Stable and language-neutral, but not phonological segmentation: "tʃa"
 * splits into t, ʃ, a although the descriptive system accepts untied "tʃ".
 * Use mk_system_segment_ipa when tokens must agree with a system's inventory,
 * or supply your own boundaries. See docs/guide/c-api.md, Geometry And Unicode. */
MK_API mk_status mk_segment_ipa(
    const char *utf8_in,
    mk_string_list **out
);

/** System-aware tokenization into an owned list (free with
 * mk_string_list_free): longest match against the system's inventory and
 * synthesis grammar, so "tʃa" becomes [tʃ, a] and "kpa" becomes [kp, a] where
 * those tokens are recognized.
 *
 * Input the system does not recognize is passed through as its orthographic
 * token rather than dropped, so the function is total over its input; check
 * mk_system_is_segment per token if you need a guarantee. Longest match is a
 * policy ("kp" may be /k.p/), and results depend on the system and its
 * inventory version: record both with any stored tokenization. */
MK_API mk_status mk_system_segment_ipa(
    const mk_system *system,
    const char *utf8_in,
    mk_string_list **out
);

/** Rewrites the ASCII digits 0-5 in a UTF-8 string as the superscript Chao
 * digits, so "ma55" becomes "ma⁵⁵"; every other character is copied. No other
 * function does this: in a romanization (Jyutping ji6, Pinyin i1) ASCII digits
 * number tone categories, not pitch levels, so a caller applies it only to
 * text known to write Chao levels in ASCII. Returns an owned string; free with
 * mk_string_free. */
MK_API mk_status mk_ascii_chao_digits(const char *utf8_in, char **utf8_out);

/** Merges Chao tone tokens into the preceding eligible segment; a tone with no
 * such segment in its word, and the neutral tone `⁰`, are kept as tokens of
 * their own. `segments` is
 * borrowed; *out is a new owned list, freed with mk_string_list_free. */
MK_API mk_status mk_merge_tone_digits(
    const mk_string_list *segments,
    mk_string_list **out
);

/** mk_segment_ipa followed by mk_merge_tone_digits, into one owned list. */
MK_API mk_status mk_segment_ipa_merged(
    const char *utf8_in,
    mk_string_list **out
);

/** Inverse of mk_merge_tone_digits: separates a merged segment such as "a¹"
 * into its base grapheme ("a") and its Chao tone token ("¹").
 *
 * On MK_OK both outputs are caller-owned and freed with mk_string_free;
 * *tone_out is NULL when the segment carries no tone, which is not an error.
 * On a refusal or MK_ERR_OOM both are NULL. A token consisting only of tone
 * digits returns MK_ERR_UNKNOWN_GRAPHEME: standalone tone clusters are not
 * segments.
 *
 * The split is orthographic: it cuts at the first Chao digit without reading
 * the run, so "a¹²³⁴" splits with MK_OK though the recognizer rejects it. Use
 * mk_system_is_segment or mk_system_grapheme_features when the content
 * matters. See docs/guide/c-api.md, Geometry And Unicode. */
MK_API mk_status mk_split_tone(
    const char *segment,
    char **base_out,
    char **tone_out
);

/** Why a grapheme was refused, for checking transcriptions.
 *
 * `status` is what resolving the grapheme returns: MK_OK when it is fine, and
 * otherwise a refusal such as MK_ERR_UNKNOWN_GRAPHEME, MK_ERR_PARSE,
 * MK_ERR_SOURCE_MARKER or MK_ERR_UNSUPPORTED_MODEL (a tone-bearing grapheme
 * in a system without tone support).
 *
 * `valid_prefix_bytes` is the length in bytes of the longest prefix, cut at a
 * character boundary, that does resolve: 0 when none does and the whole
 * length when nothing is wrong. `offending_offset` is the byte offset just
 * past that prefix, and `offending` holds the UTF-8 character there,
 * NUL-terminated, empty when there is none.
 *
 * There is no "nearest valid grapheme". See docs/guide/c-api.md, Diagnosing a
 * refusal.
 */
typedef struct mk_diagnosis {
    mk_status status;
    size_t valid_prefix_bytes;
    size_t offending_offset;
    char offending[8];
} mk_diagnosis;

/** Fills `out`. A refused grapheme is the normal case and is reported in
 * `out->status` with MK_OK returned. NULL arguments return
 * MK_ERR_INVALID_ARGUMENT, and a failed allocation MK_ERR_OOM, which leaves
 * `out` partly filled. */
MK_API mk_status mk_system_diagnose(
    const mk_system *system,
    const char *utf8_grapheme,
    mk_diagnosis *out
);

/** Whether two segments were comparable at all, and if not, why not. */
typedef enum mk_comparability {
    /** They share a tier and dimensions; the score means what it says. */
    MK_CMP_OK = 0,
    /** One is a tone and the other a segment. They occupy different tiers, and
     *  the score is the geometry's declared `tier_policy.cross_tier_cost`
     *  rather than a measurement; coverage is 0.0. See docs/guide/c-api.md,
     *  Distance with coverage. */
    MK_CMP_CROSS_TIER,
    /** Same tier, but no dimension on which both have a value. A valued
     *  system's 0.0 here means "nothing to compare", not "identical". */
    MK_CMP_NO_SHARED_DIMENSION
} mk_comparability;

/** Distance, with the share of dimensions the comparison actually used.
 *
 * `coverage` is required (NULL returns MK_ERR_INVALID_ARGUMENT); `why` may be
 * NULL. Otherwise the statuses are those of
 * mk_system_segment_distance_with_weights, and on failure *out and *coverage
 * are 0.0.
 *
 * `*coverage` is the share of the system's declared dimensions on which both
 * segments have a value, in `[0, 1]`. It is relative to the system, not the
 * segment, so in a valued system a segment compared with itself is below 1.0
 * when it leaves a dimension unset. A categorical pair is fully covered
 * unless it reaches no scored dimension, which reports 0.0. The library sets
 * no threshold. See docs/guide/c-api.md, Distance with coverage.
 */
MK_API mk_status mk_system_segment_distance_ex(
    const mk_system *system,
    const char *utf8_a,
    const char *utf8_b,
    const char *node_weights,
    double *out,
    double *coverage,
    mk_comparability *why
);

/** Number of columns a system's feature vectors have. Fixed per system. */
MK_API mk_status mk_system_vector_width(const mk_system *system, size_t *out);

/** Column names for a system's feature vectors, in order.
 *
 * The basis differs by system, because the systems do. The columns are exactly
 * the dimensions the system's scorer reads, so graphemes with equal vectors
 * are at distance zero:
 * - a valued system: its own inventory columns;
 * - a system declaring scalar_dimensions: those, then the geometry's ordered
 *   scales (vowel height, backness, ...);
 * - the rest: the geometry's leaves, its ordered scales, then one column per
 *   node-group label, named `Node=label` (`Manner=fricative`).
 * Ask rather than assume. Free with mk_string_list_free.
 */
MK_API mk_status mk_system_vector_labels(const mk_system *system, mk_string_list **out);

/**
 * Lists the graphemes of a system's own inventory, in the order the system
 * stores them (UTF-8 byte order for a compiled-in system, file order for a
 * runtime model). Graphemes the resolver would synthesize from a base and
 * diacritics are not included: that set is unbounded. Free with
 * mk_string_list_free.
 */
MK_API mk_status mk_system_inventory(const mk_system *system, mk_string_list **out);

/** Unicode canonical normalization forms for mk_unicode_normalize. */
typedef enum mk_normalization_form {
    MK_NFD = 0,
    MK_NFC = 1
} mk_normalization_form;

/**
 * Plain Unicode canonical normalization (UAX #15) of a NUL-terminated UTF-8
 * string, at the Unicode version merkmal's tables carry. Unlike
 * mk_normalize_grapheme it applies no IPA rewrites. Malformed bytes pass
 * through unchanged. Returns an owned string; free with mk_string_free.
 */
MK_API mk_status mk_unicode_normalize(
    const char *utf8_in,
    mk_normalization_form form,
    char **utf8_out
);

/** Writes a fixed-width numeric vector for a grapheme.
 *
 * `values` must have room for mk_system_vector_width entries; on
 * MK_ERR_INVALID_ARGUMENT from too small a buffer, `*written` reports the width
 * needed, so one failed call is enough to size it. A grapheme that does not
 * resolve returns its refusal status with `*written` 0.
 *
 * Encoding, following `soundvectors` (Rubehn, Nieder, Forkel & List 2024); see
 * docs/guide/c-api.md, Feature vectors:
 *
 * - `+1` the feature is present
 * - `-1` it applies to this kind of segment and is absent
 * - `0` it does not apply (or, in a table that does not distinguish the two,
 *   it does not apply or the source does not say)
 * - `NaN` a valued system's `?`: the value is not known here
 *
 * Ordered scales cannot use `0` for a middle level, since `0` already means "no
 * value". A scale of n levels maps level i to i/n, so scale columns land in
 * (0, 1] and `0` still means the scale does not apply.
 *
 * In a categorical system the segment columns are followed by `components`,
 * the number of parts of a synthesized cluster (0 for a single segment), and
 * three blocks of segment columns, one per part (`c1:...`, `c2:...`,
 * `c3:...`), zero where there is no part. Graphemes with equal vectors are at
 * distance zero, clusters included.
 */
MK_API mk_status mk_system_feature_vector(
    const mk_system *system,
    const char *utf8_grapheme,
    double *values,
    size_t capacity,
    size_t *written
);

/** Abstract segments: feature bundles with no grapheme as identity.
 *
 * A bundle belongs to one system and has one cell per dimension that system's
 * scorer reads: binary columns, ordered scales (`vowel_height`), and, for
 * leaf-scored systems, one cell per node group (`Manner`). A cell holds every
 * value the segment may have. Text form of a cell:
 *
 *   0  the dimension does not apply      ?  unknown, applies     *  unknown, may not apply
 *   binary   + - (and n, the P-base third value, in valued systems); alternatives a|b
 *   ordinal  a level, a range lo..hi, alternatives a|b
 *   group    a label, alternatives l1|l2 (exactly one of them), or one exact set l1&l2
 *
 * and `|0` adds "may not apply" to anything. A whole bundle is
 * `column=cell;column=cell...`; columns left out are `*`.
 *
 * Identity is the system (record its semantic fingerprint) and the cells,
 * never a grapheme. See docs/method/abstract-segments.md. */
typedef struct mk_bundle mk_bundle;

/** A bundle against a bundle.
 *
 * `distance`: the system's scorer formula over the dimensions specified on
 * both sides, with its own skip rules; a bundle made from a grapheme scores as
 * that grapheme does. `coverage`: for a valued system, the share of declared
 * dimensions compared, as mk_system_segment_distance_ex reports it; for a
 * categorical one, the compared weight over the compared weight plus the
 * weight left unspecified. `minimum` and `maximum`: the exact extremes of the
 * distance over every completion of the unspecified cells. */
typedef struct mk_bundle_comparison {
    double distance;
    double coverage;
    double minimum;
    double maximum;
    mk_comparability why;
} mk_bundle_comparison;

/** A bundle with every cell `*`. Free with mk_bundle_free. */
MK_API mk_status mk_bundle_new(const mk_system *system, mk_bundle **out);
/** A fully specified bundle from a grapheme. Clusters the resolver
 *  synthesizes and tones return MK_ERR_UNSUPPORTED_MODEL: neither is one
 *  feature set on the segmental tier. */
MK_API mk_status mk_bundle_from_grapheme(const mk_system *system, const char *utf8_grapheme, mk_bundle **out);
/** Parses the text form above. An unknown column is MK_ERR_UNKNOWN_FEATURE,
 *  a bad cell MK_ERR_PARSE. */
MK_API mk_status mk_bundle_from_text(const mk_system *system, const char *text, mk_bundle **out);
/** An independent copy over the same borrowed system. Free with
 *  mk_bundle_free. */
MK_API mk_status mk_bundle_copy(const mk_bundle *bundle, mk_bundle **out);
/** Tolerates NULL. Free every bundle before the registry its system is in. */
MK_API void mk_bundle_free(mk_bundle *bundle);
/** Canonical text, every column in order. Owned; free with mk_string_free. */
MK_API mk_status mk_bundle_to_text(const mk_bundle *bundle, char **out);
MK_API mk_status mk_bundle_column_count(const mk_bundle *bundle, size_t *out);
/** Borrowed; valid as long as the registry. An index at or past
 * mk_bundle_column_count returns MK_ERR_INVALID_ARGUMENT. */
MK_API mk_status mk_bundle_column_name(const mk_bundle *bundle, size_t index, const char **out);
/** The values a column can take, in order. */
MK_API mk_status mk_bundle_column_values(const mk_bundle *bundle, const char *column, mk_string_list **out);
/** Replaces one cell, written in the cell grammar of docs/method/abstract-segments.md.
 *  An unknown column is MK_ERR_UNKNOWN_FEATURE and a cell that does not parse
 *  is MK_ERR_PARSE; on any failure the bundle is unchanged. */
MK_API mk_status mk_bundle_set(mk_bundle *bundle, const char *column, const char *cell);
/** Owned canonical text of one cell; free with mk_string_free. */
MK_API mk_status mk_bundle_get(const mk_bundle *bundle, const char *column, char **cell_out);
/** Both bundles must belong to the same system object. */
MK_API mk_status mk_bundle_compare(
    const mk_bundle *a,
    const mk_bundle *b,
    const char *node_weights,
    mk_bundle_comparison *out
);
/** Whether the grapheme is one of the bundle's completions. */
MK_API mk_status mk_bundle_compatible(const mk_bundle *bundle, const char *utf8_grapheme, bool *out);
/** The system's graphemes compatible with the bundle, nearest first (ties by
 *  grapheme). For display: the ranking never decides identity. */
MK_API mk_status mk_bundle_compatible_graphemes(
    const mk_bundle *bundle,
    const char *node_weights,
    mk_string_list **out
);

/** Creates an owned list holding copies of `count` caller-provided strings;
 * the caller keeps `items`. Free with mk_string_list_free. */
MK_API mk_status mk_string_list_new(
    const char *const *items,
    size_t count,
    mk_string_list **out
);
/** Returns the number of items in a list, or zero for NULL. */
MK_API size_t mk_string_list_size(const mk_string_list *list);
/** A borrowed item, valid until the list is freed, or NULL for a NULL list
 * or an index at or past the size. */
MK_API const char *mk_string_list_get(const mk_string_list *list, size_t index);
/** Frees a string list and all its strings. Tolerates NULL. */
MK_API void mk_string_list_free(mk_string_list *list);

/** Frees a string the library allocated. Tolerates NULL. */
MK_API void mk_string_free(char *s);

#ifdef __cplusplus
}
#endif

#endif
