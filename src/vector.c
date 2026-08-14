/* Fixed-width numeric feature vectors. See merkmal.h for the contract.
 *
 * Everything else in this library hands back feature *labels*, which is the
 * right shape for reasoning about a segment and the wrong one for any model
 * that wants numbers. Writing the label-to-number mapping by hand is easy to
 * get wrong in a way nothing catches: the valued systems mix a three-way value
 * with a missingness marker in the same cell, so `anterior=.` and `anterior=-`
 * both look like "not plus" to a naive reader and mean different things.
 *
 * The convention is the one the CLTS-adjacent `soundvectors` uses (Rubehn,
 * Nieder, Forkel & List 2024), because a vector nobody else can read is not
 * worth much:
 *
 *   +1  the feature is present
 *   -1  the feature applies to this kind of segment and is absent
 *    0  the feature does not apply, or the source does not say
 *
 * Ordered scales cannot use that, because 0 already means "not applicable" and
 * a scale's middle level is not that. A scale with n levels maps level i to
 * i/n, so its values live in (0, 1] and 0 stays free to mean "no value on this
 * scale". Mixing a bounded ordinal with a three-valued flag in one vector is a
 * little untidy; ambiguity about what 0 means would be worse.
 *
 * The basis differs by system because the systems genuinely differ: a valued
 * system's columns are its inventory's own feature columns, a system with
 * declared scalar_dimensions uses those, and the rest use the geometry it
 * scores through. mk_system_vector_labels reports whichever it is, so a caller
 * never has to guess the width or the order. */

#include "vector.h"

#include "generated/builtin_data.h"
#include "resolver.h"
#include "strings.h"

#include <stdlib.h>

#include <string.h>

/* Whether a feature list carries `label`. */
static int mk_vector_has(const mk_feature_view *view, const char *label)
{
    size_t i;

    if (label == NULL || label[0] == '\0') {
        return 0;
    }
    for (i = 0; i < view->count; i++) {
        if (mki_streq(view->features[i], label)) {
            return 1;
        }
    }
    return 0;
}

/* Any of `labels` present. */
static int mk_vector_has_any(
    const mk_feature_view *view,
    const char *const *labels,
    size_t count
)
{
    size_t i;

    for (i = 0; i < count; i++) {
        if (mk_vector_has(view, labels[i])) {
            return 1;
        }
    }
    return 0;
}

/* A valued system writes its cells as "name=state". Returns the state
 * character, or 0 when the feature is absent from the list entirely. */
static char mk_vector_valued_state(const mk_feature_view *view, const char *feature)
{
    size_t len = strlen(feature);
    size_t i;

    for (i = 0; i < view->count; i++) {
        const char *item = view->features[i];

        if (strncmp(item, feature, len) == 0 && item[len] == '=') {
            return item[len + 1];
        }
    }
    return '\0';
}

static int mk_vector_is_valued(const mk_builtin_system *builtin)
{
    return builtin->kind != MK_SYSTEM_CATEGORICAL;
}

static int mk_vector_uses_scalar_dimensions(const mk_builtin_system *builtin)
{
    return builtin->scalar_dimensions != NULL && builtin->scalar_dimension_count > 0;
}

size_t mki_vector_width_of(const mk_builtin_system *builtin)
{
    if (mk_vector_is_valued(builtin)) {
        return builtin->geometry_map_count;
    }
    if (mk_vector_uses_scalar_dimensions(builtin)) {
        return builtin->scalar_dimension_count;
    }
    return mki_clements_hume_leaf_count + mki_clements_hume_ordinal_scale_count;
}

mk_status mk_system_vector_width(const mk_system *system, size_t *out)
{
    if (system == NULL || system->builtin == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = mki_vector_width_of(system->builtin);
    return MK_OK;
}

mk_status mk_system_vector_labels(const mk_system *system, mk_string_list **out)
{
    const char **names;
    mk_status status;
    size_t width;
    size_t i;
    size_t n = 0;

    if (system == NULL || system->builtin == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;
    width = mki_vector_width_of(system->builtin);
    /* +1 so a zero-width system still gets a non-NULL allocation. */
    names = (const char **)malloc((width + 1) * sizeof(*names));
    if (names == NULL) {
        return MK_ERR_OOM;
    }

    if (mk_vector_is_valued(system->builtin)) {
        for (i = 0; i < system->builtin->geometry_map_count; i++) {
            names[n++] = system->builtin->geometry_map[i].feature;
        }
    } else if (mk_vector_uses_scalar_dimensions(system->builtin)) {
        for (i = 0; i < system->builtin->scalar_dimension_count; i++) {
            names[n++] = system->builtin->scalar_dimensions[i].name;
        }
    } else {
        for (i = 0; i < mki_clements_hume_leaf_count; i++) {
            names[n++] = mki_clements_hume_leaves[i].name;
        }
        for (i = 0; i < mki_clements_hume_ordinal_scale_count; i++) {
            names[n++] = mki_clements_hume_ordinal_scales[i].name;
        }
    }

    status = mk_string_list_new(names, n, out);
    free(names);
    return status;
}

/* Fill `values` from an already-resolved feature list. */
static void mk_vector_fill(
    const mk_builtin_system *builtin,
    const mk_feature_view *view,
    double *values
)
{
    size_t i;

    if (mk_vector_is_valued(builtin)) {
        for (i = 0; i < builtin->geometry_map_count; i++) {
            char state = mk_vector_valued_state(view, builtin->geometry_map[i].feature);

            /* '+' and '-' are the only states that assert anything. The P-base
             * tables also write 'n', 'o' and 'x', and PHOIBLE writes '.', all of
             * which say the cell has no value rather than a negative one. */
            values[i] = state == '+' ? 1.0 : (state == '-' ? -1.0 : 0.0);
        }
        return;
    }

    if (mk_vector_uses_scalar_dimensions(builtin)) {
        for (i = 0; i < builtin->scalar_dimension_count; i++) {
            const mk_scalar_dimension *dim = &builtin->scalar_dimensions[i];

            if (mk_vector_has_any(view, dim->positive, dim->positive_count)) {
                values[i] = 1.0;
            } else if (mk_vector_has_any(view, dim->negative, dim->negative_count)) {
                values[i] = -1.0;
            } else {
                values[i] = 0.0;
            }
        }
        return;
    }

    for (i = 0; i < mki_clements_hume_leaf_count; i++) {
        const mk_geometry_leaf *leaf = &mki_clements_hume_leaves[i];

        if (mk_vector_has(view, leaf->positive)) {
            values[i] = 1.0;
        } else if (mk_vector_has(view, leaf->negative)) {
            values[i] = -1.0;
        } else {
            values[i] = 0.0;
        }
    }
    for (i = 0; i < mki_clements_hume_ordinal_scale_count; i++) {
        const mk_ordinal_scale *scale = &mki_clements_hume_ordinal_scales[i];
        size_t slot = mki_clements_hume_leaf_count + i;
        size_t level;

        values[slot] = 0.0;
        for (level = 0; level < scale->level_count; level++) {
            if (mk_vector_has(view, scale->levels[level])) {
                /* (0, 1], so 0 keeps meaning "no value on this scale" rather
                 * than colliding with a middle level. */
                values[slot] = (double)(level + 1) / (double)scale->level_count;
                break;
            }
        }
    }
}

mk_status mk_system_feature_vector(
    const mk_system *system,
    const char *utf8_grapheme,
    double *values,
    size_t capacity,
    size_t *written
)
{
    mk_resolution entry;
    mk_feature_view view;
    mk_status status;
    size_t width;

    if (system == NULL || system->builtin == NULL || values == NULL || written == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *written = 0;
    width = mki_vector_width_of(system->builtin);
    if (capacity < width) {
        /* Reporting the width even on failure means a caller can size a buffer
         * from one failed call rather than needing mk_system_vector_width. */
        *written = width;
        return MK_ERR_INVALID_ARGUMENT;
    }

    status = mki_resolve(system, utf8_grapheme, &entry);
    if (status != MK_OK) {
        return status;
    }
    view = mki_view_of(&entry);
    mk_vector_fill(system->builtin, &view, values);
    mki_resolution_clear(&entry);
    *written = width;
    return MK_OK;
}
