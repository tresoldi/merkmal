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

typedef enum mki_resolution_path {
    /* Nothing resolved. The value of a zeroed mki_resolution. */
    MKI_RESOLVED_NONE = 0,
    /* An inventory row, matched as written. */
    MKI_RESOLVED_INVENTORY,
    /* An inventory row, matched after removing tie bars. */
    MKI_RESOLVED_TIE_STRIPPED,
    /* An inventory row, matched after marking the affricate as retracted. */
    MKI_RESOLVED_AFFRICATE_RETRACTED,
    /* Synthesized: a vowel cluster, so a diphthong or triphthong. */
    MKI_RESOLVED_VOWEL_CLUSTER,
    /* Synthesized: a base segment carrying diacritic and tone marks. */
    MKI_RESOLVED_DIACRITICS,
    /* Synthesized: a complex segment written as two letters, such as an
     * untied affricate or a labial-velar stop. */
    MKI_RESOLVED_COMPLEX,
    /* Synthesized: a consonant cluster. */
    MKI_RESOLVED_CONSONANT_CLUSTER,
    /* Synthesized: a bare tone token, carrying no segmental content.
     *
     * CLTS/BIPA writes tone as its own segment -- "t o ³³", not "t o³³" -- and
     * that is the form the field's CLDF wordlists are published in. A token on
     * this path denotes a tone and nothing else, which is why it carries the
     * `tonal-autosegment` tier label: it is not comparable to a segment on the
     * same terms two segments are comparable to each other. */
    MKI_RESOLVED_TONE
} mki_resolution_path;

/* One part of a cluster, as the resolver already worked it out.
 *
 * A cluster is synthesized by resolving each part and composing the results, so
 * by the time a cluster exists every part has been resolved once. This carries
 * that work forward, so scoring reads the part's features instead of running
 * the whole seam -- normalization, three inventory attempts, five
 * synthesizers -- again on its spelling.
 *
 * `grapheme` is the part's spelling, owned. `features` and `feature_count` are
 * the answer, and the storage rule is the one mki_resolution states:
 * `features` aliases `owned_features` when that is non-NULL and
 * `borrowed_features` otherwise, and exactly one of the two is set. A part
 * resolved from an inventory borrows strings from the compiled pool or the
 * registry, which outlive any resolution; the array holding them is still
 * owned here, because the lookup's own array is not guaranteed to outlive the
 * synthesizer's frame (for a compiled inventory it is the scratch inside a
 * stack-local mki_resolution). All of it is freed with the cluster's
 * mki_resolution. */
typedef struct mki_cluster_component {
    char *grapheme;
    const char *const *features;
    size_t feature_count;
    char **owned_features;
    size_t owned_feature_count;
    const char **borrowed_features;
} mki_cluster_component;

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
 * struct owns, and `cluster_components` holds the resolved parts for the two
 * cluster paths.
 *
 * mki_resolution_clear frees the owned side and is safe on either shape, but
 * only on a struct that has been zeroed or filled by mki_resolve. mki_resolve
 * zeroes `out` once its arguments are valid; anything building one by hand
 * must memset it first, or the clear will free whatever the stack held. */
typedef struct mki_resolution {
    mki_resolution_path path;
    const char *grapheme;
    const char *const *features;
    size_t feature_count;
    char **owned_features;
    size_t owned_feature_count;
    char *owned_grapheme;
    mki_cluster_component *cluster_components;
    size_t cluster_component_count;
    /* Scratch for the inventory paths. A compiled-in inventory stores feature
     * ids, so handing the row out as `const char *const *` needs somewhere to
     * put the pointers; keeping that array here rather than allocating one per
     * lookup is what lets the inventory paths stay allocation-free.
     *
     * For a compiled-in inventory `features` aliases this array; for a
     * registry inventory it points at registry storage and this array is
     * unused. The strings are in the compiled pool or the registry and outlive
     * the resolution, so nothing here is freed and mki_resolution_clear leaves
     * it alone. It does mean an mki_resolution must not be copied by value and
     * then used after the original goes out of scope. */
    const char *inline_features[MKI_MAX_ENTRY_FEATURES];
} mki_resolution;

/* The seam. Normalizes the input, then tries the inventory and each
 * synthesizer in turn. On MK_OK `out` holds the answer and must be released
 * with mki_resolution_clear; on any other status but MK_ERR_INVALID_ARGUMENT
 * it holds nothing to free and clearing it is still safe.
 *
 * MK_ERR_UNKNOWN_GRAPHEME means no path recognized the input, and is how the
 * synthesizers hand off to one another; MK_ERR_PARSE means a path recognized
 * the shape and rejected the content, such as a Chao run too long to be a
 * contour. The distinction is what lets mk_system_is_segment stay total while
 * mk_system_grapheme_features reports why. MK_ERR_SOURCE_MARKER means the
 * input is CLDF or CLTS markup such as `<?>` or a boundary marker, not a
 * sound. MK_ERR_UNSUPPORTED_MODEL means the input carries tone in a form the
 * system cannot score. MK_ERR_OOM is allocation failure.
 * MK_ERR_INVALID_ARGUMENT means a NULL argument; `out`, if non-NULL, is then
 * left untouched. */
mk_status mki_resolve(
    const mk_system *system,
    const char *utf8_grapheme,
    mki_resolution *out
);

void mki_resolution_clear(mki_resolution *resolution);

/* A stable label for the path, for diagnostics and test output. Static
 * storage; never freed. */
const char *mki_resolution_path_name(mki_resolution_path path);

/* The features alone, which is all scoring wants. The view borrows from its
 * argument: it is valid until that is cleared, and for an inventory
 * resolution, whose `features` may alias `inline_features`, only while that
 * struct is in scope. */
mk_feature_view mki_view_of(const mki_resolution *resolution);
mk_feature_view mki_view_of_component(const mki_cluster_component *component);

#endif
