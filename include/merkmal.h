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
    MK_ERR_OOM
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

/** Returns the name of a system as borrowed registry-owned storage. */
MK_API mk_status mk_system_name(const mk_system *system, const char **out);
/** Returns the system kind as borrowed static storage. */
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

/** Returns the geometry distance between two feature names. */
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
 * matching the policy that standalone tone clusters are not segments. */
MK_API mk_status mk_split_tone(
    const char *segment,
    char **base_out,
    char **tone_out
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
