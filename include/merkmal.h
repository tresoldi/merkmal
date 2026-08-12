#ifndef MERKMAL_H
#define MERKMAL_H

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

typedef struct mk_registry mk_registry;
typedef struct mk_system mk_system;
typedef struct mk_string_list mk_string_list;
typedef struct mk_feature_set mk_feature_set;

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

/** Adds a copied categorical model described by the runtime text format. */
MK_API mk_status mk_registry_add_model_text(
    mk_registry *registry,
    const char *model_text
);

/** Returns the name of a system as borrowed registry-owned storage. */
MK_API mk_status mk_system_name(const mk_system *system, const char **out);
/** Returns the system kind as borrowed static storage. */
MK_API mk_status mk_system_kind(const mk_system *system, const char **out);

/** Tests a grapheme without allocating a feature result. */
MK_API mk_status mk_system_is_segment(
    const mk_system *system,
    const char *utf8_grapheme,
    int *out
);

/** Returns an owned feature set for one grapheme. */
MK_API mk_status mk_system_grapheme_features(
    const mk_system *system,
    const char *utf8_grapheme,
    mk_feature_set **out
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

/** Computes distance between two caller-provided feature lists. */
MK_API mk_status mk_sound_distance(
    const char *const *features_a,
    size_t feature_a_count,
    const char *const *features_b,
    size_t feature_b_count,
    const char *node_weights,
    double *out
);

/** Normalizes one UTF-8 grapheme and returns an owned string. */
MK_API mk_status mk_normalize_grapheme(
    const char *utf8_in,
    char **utf8_out
);

/** Splits UTF-8 input into an owned list of IPA segments. */
MK_API mk_status mk_segment_ipa(
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
 * On MK_OK both outputs are caller-owned and freed with mk_free_string.
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

/** Returns the number of features in a set, or zero for NULL. */
MK_API size_t mk_feature_set_size(const mk_feature_set *features);
/** Returns a borrowed feature, or NULL for an invalid index. */
MK_API const char *mk_feature_set_get(const mk_feature_set *features, size_t index);
/** Frees a feature set and all copied strings. */
MK_API void mk_feature_set_free(mk_feature_set *features);

/** Frees a string returned by a library allocation. */
MK_API void mk_free_string(char *s);

#ifdef __cplusplus
}
#endif

#endif
