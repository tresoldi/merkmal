#ifndef MK_RESOLVER_H
#define MK_RESOLVER_H

#include "generated/builtin_data.h"
#include "geometry.h"
#include "inventory.h"
#include "system.h"

/* Segment resolution: turning a written grapheme into the feature set of the
 * segment it denotes.
 *
 * Most graphemes are an inventory row and the answer is a lookup. The rest are
 * spellings no inventory lists — a base plus diacritics, a diphthong, an
 * affricate written without a tie bar — and the resolver synthesizes a feature
 * set for them from the parts. Which of those happened is `path`, and it is
 * part of the answer: it says whether a segment was attested or constructed,
 * and it is the only way a test can tell one construction from another. */

typedef enum mk_resolution_path {
    /* Nothing resolved. The value of a zeroed mk_resolution. */
    MK_RESOLVED_NONE = 0,
    /* An inventory row, matched as written. */
    MK_RESOLVED_INVENTORY,
    /* An inventory row, matched after removing tie bars. */
    MK_RESOLVED_TIE_STRIPPED,
    /* An inventory row, matched after marking the affricate as retracted. */
    MK_RESOLVED_AFFRICATE_RETRACTED,
    /* Synthesized: a vowel cluster, so a diphthong or triphthong. */
    MK_RESOLVED_VOWEL_CLUSTER,
    /* Synthesized: a base segment carrying diacritic and tone marks. */
    MK_RESOLVED_DIACRITICS,
    /* Synthesized: a complex segment written as two letters, such as an
     * untied affricate or a labial-velar stop. */
    MK_RESOLVED_COMPLEX,
    /* Synthesized: a consonant cluster. */
    MK_RESOLVED_CONSONANT_CLUSTER
} mk_resolution_path;

/* A resolved segment, and the storage behind it.
 *
 * `grapheme`, `features` and `feature_count` are the answer. Where their
 * storage lives depends on how the segment was resolved, and the rule is:
 *
 *   `features` aliases `owned_features` exactly when `owned_features` is
 *   non-NULL, and `grapheme` aliases `owned_grapheme` exactly when
 *   `owned_grapheme` is non-NULL.
 *
 * On the three inventory paths both owned_* fields are NULL and the answer
 * borrows a compiled-in or registry-owned row, valid as long as the registry
 * is. On every synthesized path the owned_* fields hold heap storage that this
 * struct owns, and `cluster_components` holds the component spellings for the
 * two cluster paths.
 *
 * mk_resolution_clear frees the owned side and is safe on either shape, but
 * only on a struct that has been zeroed or filled by mk_resolve. mk_resolve
 * zeroes `out` before doing any work; anything building one by hand must
 * memset it first, or the clear will free whatever the stack held. */
typedef struct mk_resolution {
    mk_resolution_path path;
    const char *grapheme;
    const char *const *features;
    size_t feature_count;
    char **owned_features;
    size_t owned_feature_count;
    char *owned_grapheme;
    char **cluster_components;
    size_t cluster_component_count;
    /* Scratch for the inventory paths. A compiled-in inventory stores feature
     * ids, so handing the row out as `const char *const *` needs somewhere to
     * put the pointers; keeping that array here rather than allocating one per
     * lookup is what lets the inventory paths stay allocation-free.
     *
     * On those paths `features` aliases this array. The strings it points at
     * are in the compiled pool and outlive everything, so nothing here is
     * freed and mk_resolution_clear leaves it alone. It does mean an
     * mk_resolution must not be copied by value and then used after the
     * original goes out of scope. */
    const char *inline_features[MK_MAX_ENTRY_FEATURES];
} mk_resolution;

/* The seam. Normalizes the input, then tries the inventory and each
 * synthesizer in turn.
 *
 * MK_ERR_UNKNOWN_GRAPHEME means no path recognized the input, and is how the
 * synthesizers hand off to one another; MK_ERR_PARSE means a path recognized
 * the shape and rejected the content, such as a Chao run too long to be a
 * contour. The distinction is what lets mk_system_is_segment stay total while
 * mk_system_grapheme_features reports why. */
mk_status mk_resolve(
    const mk_system *system,
    const char *utf8_grapheme,
    mk_resolution *out
);

void mk_resolution_clear(mk_resolution *resolution);

/* A stable label for the path, for diagnostics and test output. Static
 * storage; never freed. */
const char *mk_resolution_path_name(mk_resolution_path path);

/* Scoring wants the features and nothing else. */
mk_feature_view mk_view_of(const mk_resolution *resolution);

#endif
