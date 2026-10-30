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
#include "geometry.h"
#include "resolver.h"
#include "strings.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#include <string.h>

/* Whether a feature list carries `label`. */
static int mk_vector_has(const mk_feature_view *view, const char *label)
{
    return mki_features_contain(view->features, view->count, label);
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

/* The columns are exactly the dimensions the system's scorer reads, so two
 * graphemes with equal vectors are at distance zero. A valued system's columns
 * are its own; a system with scalar dimensions has those plus the geometry's
 * ordered scales; a leaf-scored system has the geometry's leaves, its ordered
 * scales, and one column per node-group label. The scales and node groups used
 * to be missing where the scorer read them, so in `distinctive` /a/ and /e/
 * had the same vector, and in `descriptive` /l/ and /ɮ/. */
static size_t mk_vector_node_group_count(void)
{
    size_t i;
    size_t n = 0;

    for (i = 0; i < mki_clements_hume_feature_to_node_count; i++) {
        if (mki_is_node_group_feature(mki_clements_hume_feature_to_node[i].feature)) {
            n++;
        }
    }
    return n;
}

size_t mki_vector_width_of(const mk_builtin_system *builtin)
{
    if (mk_vector_is_valued(builtin)) {
        return builtin->geometry_map_count;
    }
    if (mk_vector_uses_scalar_dimensions(builtin)) {
        return builtin->scalar_dimension_count + mki_clements_hume_ordinal_scale_count;
    }
    return mki_clements_hume_leaf_count + mki_clements_hume_ordinal_scale_count +
        mk_vector_node_group_count();
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
    char **names;
    mk_status status = MK_OK;
    size_t width;
    size_t i;
    size_t n = 0;

    if (system == NULL || system->builtin == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;
    width = mki_vector_width_of(system->builtin);
    /* +1 so a zero-width system still gets a non-NULL allocation. Every name is
     * an owned copy, so node-group labels can be composed here. */
    names = (char **)calloc(width + 1, sizeof(*names));
    if (names == NULL) {
        return MK_ERR_OOM;
    }

    if (mk_vector_is_valued(system->builtin)) {
        for (i = 0; i < system->builtin->geometry_map_count && status == MK_OK; i++) {
            names[n] = mki_strdup_internal(system->builtin->geometry_map[i].feature);
            status = names[n++] == NULL ? MK_ERR_OOM : MK_OK;
        }
    } else {
        if (mk_vector_uses_scalar_dimensions(system->builtin)) {
            for (i = 0; i < system->builtin->scalar_dimension_count && status == MK_OK; i++) {
                names[n] = mki_strdup_internal(system->builtin->scalar_dimensions[i].name);
                status = names[n++] == NULL ? MK_ERR_OOM : MK_OK;
            }
        } else {
            for (i = 0; i < mki_clements_hume_leaf_count && status == MK_OK; i++) {
                names[n] = mki_strdup_internal(mki_clements_hume_leaves[i].name);
                status = names[n++] == NULL ? MK_ERR_OOM : MK_OK;
            }
        }
        for (i = 0; i < mki_clements_hume_ordinal_scale_count && status == MK_OK; i++) {
            names[n] = mki_strdup_internal(mki_clements_hume_ordinal_scales[i].name);
            status = names[n++] == NULL ? MK_ERR_OOM : MK_OK;
        }
        if (!mk_vector_uses_scalar_dimensions(system->builtin)) {
            for (i = 0; i < mki_clements_hume_feature_to_node_count && status == MK_OK; i++) {
                const mk_feature_node_map *map = &mki_clements_hume_feature_to_node[i];
                size_t len;

                if (!mki_is_node_group_feature(map->feature)) {
                    continue;
                }
                /* "Manner=fricative": the node the scorer groups by, and the label. */
                len = strlen(map->node) + 1 + strlen(map->feature) + 1;
                names[n] = (char *)malloc(len);
                if (names[n] == NULL) {
                    status = MK_ERR_OOM;
                    break;
                }
                snprintf(names[n++], len, "%s=%s", map->node, map->feature);
            }
        }
    }

    if (status == MK_OK) {
        status = mk_string_list_new((const char *const *)names, n, out);
    }
    for (i = 0; i < n; i++) {
        free(names[i]);
    }
    free(names);
    return status;
}

/* An ordered scale's column: level i of n as i/n, so 0 keeps meaning "no value
 * on this scale". Read exactly as the scorers read it, unmarked default
 * included; ignoring the default made a vowel with no explicit level look
 * like a segment the scale does not apply to. */
static double mk_vector_scale_value(const mk_feature_view *view, const mk_ordinal_scale *scale)
{
    int level = mki_ordinal_level(*view, scale);

    if (level == MK_ORDINAL_UNDEFINED) {
        return 0.0;
    }
    return (double)(level + 1) / (double)scale->level_count;
}

/* Fill `values` from an already-resolved feature list. */
static void mk_vector_fill(
    const mk_builtin_system *builtin,
    const mk_feature_view *view,
    double *values
)
{
    size_t i;
    size_t slot = 0;

    if (mk_vector_is_valued(builtin)) {
        for (i = 0; i < builtin->geometry_map_count; i++) {
            char state = mk_vector_valued_state(view, builtin->geometry_map[i].feature);

            /* '+' and '-' assert a value. '?' says the value is unknown, which
             * is not "does not apply", so it is NaN rather than 0. '0' (does not
             * apply), the P-base 'n', 'o' and 'x', and '.' (a table that does
             * not say which) are 0. */
            if (state == '+') {
                values[i] = 1.0;
            } else if (state == '-') {
                values[i] = -1.0;
            } else if (state == '?') {
                values[i] = NAN;
            } else {
                values[i] = 0.0;
            }
        }
        return;
    }

    if (mk_vector_uses_scalar_dimensions(builtin)) {
        for (i = 0; i < builtin->scalar_dimension_count; i++) {
            const mk_scalar_dimension *dim = &builtin->scalar_dimensions[i];

            if (mk_vector_has_any(view, dim->positive, dim->positive_count)) {
                values[slot++] = 1.0;
            } else if (mk_vector_has_any(view, dim->negative, dim->negative_count)) {
                values[slot++] = -1.0;
            } else {
                values[slot++] = 0.0;
            }
        }
    } else {
        for (i = 0; i < mki_clements_hume_leaf_count; i++) {
            const mk_geometry_leaf *leaf = &mki_clements_hume_leaves[i];

            if (leaf->positive[0] != '\0' && mk_vector_has(view, leaf->positive)) {
                values[slot++] = 1.0;
            } else if (leaf->negative[0] != '\0' && mk_vector_has(view, leaf->negative)) {
                values[slot++] = -1.0;
            } else {
                values[slot++] = 0.0;
            }
        }
    }
    for (i = 0; i < mki_clements_hume_ordinal_scale_count; i++) {
        values[slot++] = mk_vector_scale_value(view, &mki_clements_hume_ordinal_scales[i]);
    }
    if (mk_vector_uses_scalar_dimensions(builtin)) {
        return;
    }
    /* Node groups one-hot: +1 the label is present, -1 its node is set by
     * another label, 0 the node is unset. Equal columns are equal label sets at
     * the node, which is all the scorer asks of a group. */
    for (i = 0; i < mki_clements_hume_feature_to_node_count; i++) {
        const mk_feature_node_map *map = &mki_clements_hume_feature_to_node[i];
        size_t k;
        int touched = 0;

        if (!mki_is_node_group_feature(map->feature)) {
            continue;
        }
        if (mk_vector_has(view, map->feature)) {
            values[slot++] = 1.0;
            continue;
        }
        for (k = 0; k < view->count; k++) {
            const char *other = view->features[k];
            size_t m;

            if (!mki_is_node_group_feature(other)) {
                continue;
            }
            for (m = 0; m < mki_clements_hume_feature_to_node_count; m++) {
                if (mki_streq(mki_clements_hume_feature_to_node[m].feature, other) &&
                    mki_streq(mki_clements_hume_feature_to_node[m].node, map->node)) {
                    touched = 1;
                    break;
                }
            }
            if (touched) {
                break;
            }
        }
        values[slot++] = touched ? -1.0 : 0.0;
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
