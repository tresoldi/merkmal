#ifndef MERKMAL_H
#define MERKMAL_H

#include <stdbool.h>
#include <stddef.h>

#if defined(_WIN32) && defined(MERKMAL_SHARED)
#  if defined(MERKMAL_BUILDING_LIBRARY)
#    define MK_API __declspec(dllexport)
#  else
#    define MK_API __declspec(dllimport)
#  endif
#elif defined(__GNUC__) || defined(__clang__)
#  define MK_API __attribute__((visibility("default")))
#else
#  define MK_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* A borrowed feature set: the pointers and the strings both belong to the
 * caller and must outlive the call. Feature order carries no meaning.
 *
 * This is a value type on purpose. It is not opaque because there is nothing to
 * hide -- it is exactly a pointer and a count -- and making it public lets a
 * caller hand the same two fields to every function that scores features
 * instead of spelling out four arguments. */
typedef struct mk_feature_view {
    const char *const *features;
    size_t count;
} mk_feature_view;

typedef struct mk_registry mk_registry;
typedef struct mk_system mk_system;
typedef struct mk_string_list mk_string_list;

typedef enum mk_status {
    MK_OK = 0,
    MK_ERR_INVALID_ARGUMENT,
    MK_ERR_UNKNOWN_SYSTEM,
    MK_ERR_UNKNOWN_GRAPHEME,
    MK_ERR_UNSUPPORTED_MODEL,
    MK_ERR_PARSE,
    MK_ERR_OOM,
    /** The token is CLDF/CLTS markup, not a transcription of a sound.
     *
     * `<?>` is CLTS's mark for a grapheme it could not convert, `<<...>>` is
     * CLDF's escape for source material left unparsed, and `+`, `_` and `#` are
     * boundary markers. Rejecting them is correct -- they are not sounds -- but
     * a caller checking transcriptions needs to tell "your data has a known gap
     * here" apart from "this library does not support this sound", and
     * MK_ERR_UNKNOWN_GRAPHEME said only the second. In Lexibank these account
     * for 33,275 tokens.
     *
     * Appended to the enum rather than inserted, so existing values keep their
     * numbers. */
    MK_ERR_SOURCE_MARKER,
    /** A registry already holds a system by that name.
     *
     * Lookup returns the first match, so appending a second `descriptive`
     * registered successfully and was then unreachable for the rest of the
     * registry's life: the caller was told their model installed, and every
     * query for it answered from the built-in one instead. Refusing says so at
     * the point the caller can still do something about it -- rename, skip, or
     * warn -- which is why this is its own status rather than the
     * MK_ERR_INVALID_ARGUMENT this call already returns for a null pointer.
     *
     * Appended to the enum rather than inserted, so existing values keep their
     * numbers. */
    MK_ERR_DUPLICATE_SYSTEM,
    /** A feature has no path in the geometry tree, so no tree distance is
     * defined for it. See mk_feature_distance.
     *
     * Appended to the enum rather than inserted, so existing values keep their
     * numbers. */
    MK_ERR_NO_TREE_PATH
} mk_status;

/** Returns the stable English label for a status code. */
MK_API const char *mk_status_string(mk_status status);

/** Creates a registry containing the compiled-in systems. */
MK_API mk_status mk_registry_new_builtin(mk_registry **out);
/** Frees a registry and all runtime models owned by it. */
MK_API void mk_registry_free(mk_registry *registry);

/** Returns an owned list of system names. */
MK_API mk_status mk_registry_list_systems(
    const mk_registry *registry,
    mk_string_list **out
);

/** Looks up a system. The returned pointer is owned by the registry. */
MK_API mk_status mk_registry_get_system(
    const mk_registry *registry,
    const char *name,
    const mk_system **out
);

/* Adds a copied categorical model described by the runtime text format.
 *
 * Validation is strict unless the model says '@validation permissive': every
 * feature must reach a scoring dimension, graphemes must be unique, and
 * unrecognized lines are rejected. Without that, a model whose features the
 * geometry does not know registers successfully and then scores every
 * comparison as zero, which is indistinguishable from "these are identical". */
MK_API mk_status mk_registry_add_model_text(
    mk_registry *registry,
    const char *model_text
);

/* As above, but on failure *diagnostic_out receives an owned message naming the
 * offending line and token. Free it with mk_string_free. It is NULL on success
 * and may be NULL on entry if the caller does not want the detail. */
MK_API mk_status mk_registry_add_model_text_ex(
    mk_registry *registry,
    const char *model_text,
    char **diagnostic_out
);

/* As _ex, but for text that is not NUL-terminated: `model_text_length` is a
 * byte count and nothing past it is read.
 *
 * This is the entry point for a caller holding a buffer rather than a C string
 * -- a mapped file, a Python `bytes`, a fuzzer's input -- none of which owe the
 * library a terminator. The other two forms are this one with strlen.
 *
 * An embedded NUL returns MK_ERR_PARSE. The format is line-oriented text; a
 * NUL in the middle would end the model early and register the truncated part
 * as if it were whole. */
MK_API mk_status mk_registry_add_model_text_n(
    mk_registry *registry,
    const char *model_text,
    size_t model_text_length,
    char **diagnostic_out
);

/* System identity, for a caller holding a system pointer rather than the name
 * it looked the system up by.
 *
 * The kind is worth asking for because coverage means different things by it.
 * A valued system skips any dimension either segment leaves unset, so its
 * coverage is a real fraction and a segment can be under 1.0 even against
 * itself; a categorical one weighs whatever either segment specifies, so an
 * ordinary pair is fully covered. See mk_system_segment_distance_ex.
 *
 * Both are borrowed, and their lifetimes differ behind identical signatures:
 * the name is registry-owned and valid as long as the registry, while the kind
 * is a static string that outlives everything. */
MK_API mk_status mk_system_name(const mk_system *system, const char **out);
/** One of "categorical", "valued", or "trained". Static storage. */
MK_API mk_status mk_system_kind(const mk_system *system, const char **out);

/* Whether the system recognizes this grapheme, without allocating a feature
 * result.
 *
 * Total: input the system does not recognize sets *out to false and returns
 * MK_OK, as does input it recognizes and rejects, such as an over-long Chao
 * run. Use mk_system_grapheme_features when the reason matters. */
MK_API mk_status mk_system_is_segment(
    const mk_system *system,
    const char *utf8_grapheme,
    bool *out
);

/** Returns the features of one grapheme, in no meaningful order. */
MK_API mk_status mk_system_grapheme_features(
    const mk_system *system,
    const char *utf8_grapheme,
    mk_string_list **out
);

/** Computes the default segment distance for a system. */
MK_API mk_status mk_system_segment_distance(
    const mk_system *system,
    const char *utf8_a,
    const char *utf8_b,
    double *out
);

/** Computes a segment distance using an optional named weight preset. */
MK_API mk_status mk_system_segment_distance_with_weights(
    const mk_system *system,
    const char *utf8_a,
    const char *utf8_b,
    const char *node_weights,
    double *out
);

/** Hop count between two feature names along the geometry tree.
 *
 * Defined only over features the tree actually contains -- 110 of them. A
 * feature the geometry reaches some other way has no tree path and no tree
 * distance: `bilabial` and `velar` are both mapped to the Place node rather
 * than being leaves under it, and an ordered-scale level such as
 * `tone-onset-1` is a position on a scale rather than a point on the tree.
 * Roughly two in five of the labels a categorical system can return are in
 * that group. Either feature being off the tree returns MK_ERR_NO_TREE_PATH.
 *
 * This used to write 999 into *out and return MK_OK, which is a second error
 * channel of the kind this library does not have elsewhere: 999 is an ordinary
 * looking integer in a function whose real answers are small ones, so a caller
 * summing or thresholding got nonsense with nothing to test. It also answered 0
 * for a feature compared with itself before checking whether it knew the
 * feature at all, so a misspelling compared with itself was confidently zero.
 * The domain is checked first now, and identity falls out of the arithmetic.
 *
 * This is a tree measurement, not a phonological distance. Two segments are
 * compared with mk_system_segment_distance, which reads node groups and ordered
 * scales as well and is defined for every feature a system returns. */
MK_API mk_status mk_feature_distance(
    const char *feature_a,
    const char *feature_b,
    int *out
);

/* Distance between two caller-provided feature sets, scored against the
 * compiled geometry with no system, registry, or grapheme involved.
 *
 * `node_weights` names a weight preset, or is NULL for the default. An unknown
 * preset returns MK_ERR_INVALID_ARGUMENT rather than a score. */
MK_API mk_status mk_sound_distance(
    mk_feature_view a,
    mk_feature_view b,
    const char *node_weights,
    double *out
);

/** Normalizes one UTF-8 grapheme and returns an owned string. */
MK_API mk_status mk_normalize_grapheme(
    const char *utf8_in,
    char **utf8_out
);

/* Orthographic tokenization: a new token starts at each new base code point
 * unless a tie bar joins it to the previous one. This is stable and
 * language-neutral, but it is not phonological segmentation, and it disagrees
 * with what a system recognizes: "tʃa" splits into t, ʃ, a even though the
 * descriptive system accepts untied "tʃ" as one segment. Use
 * mk_system_segment_ipa when tokens must agree with a system's own inventory,
 * or supply your own boundaries when the analysis is authoritative. */
MK_API mk_status mk_segment_ipa(
    const char *utf8_in,
    mk_string_list **out
);

/* System-aware tokenization: longest match against the system's inventory and
 * synthesis grammar, so "tʃa" becomes [tʃ, a] and "kpa" becomes [kp, a] where
 * those tokens are recognized.
 *
 * Longest match is a policy, not a truth: "kp" may be /k.p/ in a language that
 * has no labial-velar. Results also depend on the selected system and its
 * inventory version, so record both alongside any stored tokenization.
 *
 * Input that the system does not recognize is passed through as its
 * orthographic token rather than dropped, so the function is total. Check
 * mk_system_is_segment per token if you need a guarantee. */
MK_API mk_status mk_system_segment_ipa(
    const mk_system *system,
    const char *utf8_in,
    mk_string_list **out
);

/** Merges Chao tone tokens into the preceding eligible segment. */
MK_API mk_status mk_merge_tone_digits(
    const mk_string_list *segments,
    mk_string_list **out
);

/** Segments IPA input and merges Chao tone tokens in one operation. */
MK_API mk_status mk_segment_ipa_merged(
    const char *utf8_in,
    mk_string_list **out
);

/* Inverse of the merge step: separates a merged segment such as "a¹" into its
 * base grapheme ("a") and its Chao tone token ("¹"). Without this, a consumer
 * that models tone as its own dimension has to reimplement Chao digit parsing
 * to undo what mk_merge_tone_digits did.
 *
 * On MK_OK both outputs are caller-owned and freed with mk_string_free.
 * *tone_out is NULL when the segment carries no tone, which is not an error.
 * A token consisting only of tone digits returns MK_ERR_UNKNOWN_GRAPHEME,
 * matching the policy that standalone tone clusters are not segments.
 *
 * The split is orthographic and does not read the tone run: it finds the first
 * Chao digit and cuts there. "a¹²³⁴" splits into ("a", "¹²³⁴") and returns
 * MK_OK, though four digits are not a contour this library accepts and
 * mk_system_is_segment reports false for that token. That is the same
 * separation mk_segment_ipa keeps, which splits "tʃa" into three tokens while
 * the descriptive system recognizes "tʃ" as one segment: an orthographic
 * operation answers about spelling, and whether the result denotes a segment is
 * a question for the recognizer.
 *
 * So the one error here is about *shape* -- there is no base to split off --
 * and never about the content of the run. A caller who needs the content
 * checked calls mk_system_is_segment or mk_system_grapheme_features, which
 * report MK_ERR_PARSE for a run this one splits without complaint. */
MK_API mk_status mk_split_tone(
    const char *segment,
    char **base_out,
    char **tone_out
);

/** Why a grapheme was refused, for checking transcriptions.
 *
 * `status` is what mk_system_grapheme_features would return: MK_OK when the
 * grapheme is fine, and otherwise MK_ERR_UNKNOWN_GRAPHEME, MK_ERR_PARSE or
 * MK_ERR_SOURCE_MARKER, which already say different things.
 *
 * `valid_prefix_bytes` is the longest prefix that does resolve -- `pʰ` out of a
 * mistyped `pʰ` plus junk -- which localizes the problem and is usually the
 * repair. It is 0 when nothing resolves and the whole length when nothing is
 * wrong.
 *
 * `offending_offset` is the byte offset just past that prefix, and `offending`
 * holds the character there as a NUL-terminated UTF-8 string, empty when there
 * is none.
 *
 * There is deliberately no "nearest valid grapheme": an edit-distance search
 * over the inventory would be a guess presented as an answer, and the prefix is
 * cheaper and more often right.
 */
typedef struct mk_diagnosis {
    mk_status status;
    size_t valid_prefix_bytes;
    size_t offending_offset;
    char offending[8];
} mk_diagnosis;

/** Fills `out`. Returns MK_OK unless the arguments are unusable: a refused
 *  grapheme is the normal case and is reported in `out->status`. */
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
     *  rather than a measurement. Gold alignments never place a tone in a
     *  column with a segment. */
    MK_CMP_CROSS_TIER,
    /** Same tier, but no dimension on which both have a value. A valued
     *  system's 0.0 here means "nothing to compare", not "identical". */
    MK_CMP_NO_SHARED_DIMENSION
} mk_comparability;

/** Distance, with the share of dimensions the comparison actually used.
 *
 * A valued system skips any dimension where either segment has no value, so a
 * score of `0.0` is ambiguous: it can mean "identical" or "nothing in common to
 * compare". PHOIBLE writes `.` in 30,181 cells, and a pair whose overlap is
 * entirely `.` scored a confident zero with no way for a caller to tell.
 *
 * `*coverage` is the share of the system's declared dimensions on which both
 * segments had a value, in `[0, 1]`. Treat a low value as a weak comparison
 * however your work requires -- the library does not decide a threshold.
 *
 * It is relative to the system, not to the segment, so a segment compared with
 * *itself* is not 1.0 unless it has a value on every dimension: PHOIBLE leaves
 * 11 of /p/'s 38 cells empty, and `("p", "p")` reports 27/38.
 *
 * Categorical systems weigh any dimension either segment specifies, so an
 * ordinary pair is fully covered and the ambiguity does not arise. A pair that
 * reaches no scored dimension at all still reports 0.0 rather than claiming a
 * comparison that did not happen.
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
 * The basis differs by system, because the systems do: a valued system's
 * columns are its own inventory columns, a system declaring scalar_dimensions
 * uses those, and the rest use the geometry they score through. Ask rather than
 * assume. Free with mk_string_list_free.
 */
MK_API mk_status mk_system_vector_labels(const mk_system *system, mk_string_list **out);

/** Writes a fixed-width numeric vector for a grapheme.
 *
 * `values` must have room for mk_system_vector_width entries; on
 * MK_ERR_INVALID_ARGUMENT from too small a buffer, `*written` reports the width
 * needed, so one failed call is enough to size it.
 *
 * Encoding, following `soundvectors` (Rubehn, Nieder, Forkel & List 2024) so
 * that the numbers mean what the rest of the ecosystem means by them:
 *
 * - `+1` the feature is present
 * - `-1` it applies to this kind of segment and is absent
 * - `0` it does not apply, or the source does not say
 *
 * Ordered scales cannot use `0` for a middle level, since `0` already means "no
 * value". A scale of n levels maps level i to i/n, so scale columns land in
 * (0, 1] and `0` still means the scale does not apply.
 */
MK_API mk_status mk_system_feature_vector(
    const mk_system *system,
    const char *utf8_grapheme,
    double *values,
    size_t capacity,
    size_t *written
);

/** Creates an owned copy of a caller-provided string list. */
MK_API mk_status mk_string_list_new(
    const char *const *items,
    size_t count,
    mk_string_list **out
);
/** Returns the number of items in a list, or zero for NULL. */
MK_API size_t mk_string_list_size(const mk_string_list *list);
/** Returns a borrowed item, or NULL for an invalid index. */
MK_API const char *mk_string_list_get(const mk_string_list *list, size_t index);
/** Frees a string list and all copied strings. */
MK_API void mk_string_list_free(mk_string_list *list);

/* Frees a string the library allocated. Tolerates NULL.
 *
 * Named for the thing it frees, like mk_string_list_free and mk_registry_free.
 * It was mk_free_string, the one destructor that read the other way round. */
MK_API void mk_string_free(char *s);

#ifdef __cplusplus
}
#endif

#endif
