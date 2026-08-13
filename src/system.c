#include "resolver.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *mk_kind_name(mk_system_type kind)
{
    switch (kind) {
    case MK_SYSTEM_CATEGORICAL:
        return "categorical";
    case MK_SYSTEM_VALUED:
        return "valued";
    case MK_SYSTEM_TRAINED:
        return "trained";
    default:
        return "unknown";
    }
}

mk_status mk_system_name(const mk_system *system, const char **out)
{
    if (system == NULL || system->builtin == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = system->builtin->name;
    return MK_OK;
}

mk_status mk_system_kind(const mk_system *system, const char **out)
{
    if (system == NULL || system->builtin == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = mk_kind_name(system->builtin->kind);
    return MK_OK;
}


mk_status mk_system_is_segment(
    const mk_system *system,
    const char *utf8_grapheme,
    int *out
)
{
    mk_resolution entry;
    mk_status status;

    if (out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = 0;
    status = mk_resolve(system, utf8_grapheme, &entry);
    if (status == MK_OK) {
        mk_resolution_clear(&entry);
        *out = 1;
        return MK_OK;
    }
    if (status == MK_ERR_UNKNOWN_GRAPHEME) {
        return MK_OK;
    }
    if (status == MK_ERR_PARSE) {
        /* Malformed input (an over-long Chao run, say) is not a segment. The
         * predicate stays total; callers who want the reason use
         * mk_system_grapheme_features, which reports MK_ERR_PARSE. */
        return MK_OK;
    }
    return status;
}

mk_status mk_system_grapheme_features(
    const mk_system *system,
    const char *utf8_grapheme,
    mk_feature_set **out
)
{
    mk_resolution entry;
    mk_status status;

    if (out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;
    status = mk_resolve(system, utf8_grapheme, &entry);
    if (status != MK_OK) {
        return status;
    }
    status = mk_feature_set_from_borrowed(entry.features, entry.feature_count, out);
    mk_resolution_clear(&entry);
    return status;
}

mk_status mk_system_segment_distance(
    const mk_system *system,
    const char *utf8_a,
    const char *utf8_b,
    double *out
)
{
    return mk_system_segment_distance_with_weights(system, utf8_a, utf8_b, NULL, out);
}

/* Cluster scoring is a composition policy over the resolver and the geometry,
 * not a geometry rule, so it stays here rather than in geometry.c. These are
 * the numbers it composes with; they are stipulated, like the geometry weights
 * they sit on top of. */
#define MK_CLUSTER_NUCLEUS_SHARE 0.7  /* first component against a plain segment */
#define MK_CLUSTER_OFFGLIDE_SHARE 0.3 /* the remaining components, averaged */
#define MK_CLUSTER_LENGTH_PENALTY 0.15 /* per component the other side lacks */
#define MK_CLUSTER_COMPONENT_SHARE 0.8 /* component agreement vs. whole-segment */
#define MK_CLUSTER_SEGMENT_SHARE 0.2   /* features of the cluster as a unit */

static double mk_min_double(double a, double b)
{
    return a < b ? a : b;
}

/* Distance from a component spelling to an already-resolved entry. A component
 * the system does not recognize is maximally far rather than an error: the
 * cluster grammar admits spellings no inventory row has. */
static mk_status mk_component_distance(
    const mk_system *system,
    const char *a_text,
    const mk_resolution *b_entry,
    const char *node_weights,
    double *out
)
{
    mk_resolution a_resolved;
    mk_status status;

    memset(&a_resolved, 0, sizeof(a_resolved));
    if (mk_resolve(system, a_text, &a_resolved) != MK_OK) {
        *out = 1.0;
        return MK_OK;
    }
    if (mk_streq(a_resolved.grapheme, b_entry->grapheme)) {
        *out = 0.0;
        status = MK_OK;
    } else {
        status = mk_score_categorical(
            system->builtin,
            mk_view_of(&a_resolved),
            mk_view_of(b_entry),
            node_weights,
            out
        );
    }
    mk_resolution_clear(&a_resolved);
    return status;
}

static mk_status mk_cluster_component_distance(
    const mk_system *system,
    const char *a_text,
    const char *b_text,
    const char *node_weights,
    double *out
)
{
    mk_resolution a_resolved;
    mk_status status;

    memset(&a_resolved, 0, sizeof(a_resolved));
    if (mk_resolve(system, a_text, &a_resolved) != MK_OK) {
        *out = 1.0;
        return MK_OK;
    }
    status = mk_component_distance(system, b_text, &a_resolved, node_weights, out);
    mk_resolution_clear(&a_resolved);
    return status;
}

static mk_status mk_distance_cluster_to_segment(
    const mk_system *system,
    const mk_resolution *cluster,
    const mk_resolution *segment,
    const char *node_weights,
    double *out
)
{
    double score;
    double part;
    size_t i;
    mk_status status;

    if (cluster->cluster_component_count == 0) {
        *out = 1.0;
        return MK_OK;
    }
    status = mk_component_distance(
        system, cluster->cluster_components[0], segment, node_weights, &part);
    if (status != MK_OK) {
        return status;
    }
    score = MK_CLUSTER_NUCLEUS_SHARE * part;
    if (cluster->cluster_component_count > 1) {
        double rest = 0.0;
        for (i = 1; i < cluster->cluster_component_count; i++) {
            status = mk_component_distance(
                system, cluster->cluster_components[i], segment, node_weights, &part);
            if (status != MK_OK) {
                return status;
            }
            rest += part;
        }
        rest /= (double)(cluster->cluster_component_count - 1);
        score += MK_CLUSTER_OFFGLIDE_SHARE * rest;
    }
    score += MK_CLUSTER_LENGTH_PENALTY * (double)(cluster->cluster_component_count - 1);
    *out = mk_min_double(score, 1.0);
    return MK_OK;
}

static mk_status mk_vowel_cluster_distance(
    const mk_system *system,
    const mk_resolution *a,
    const mk_resolution *b,
    const char *node_weights,
    double *out
)
{
    double component_score = 0.0;
    double segment_score;
    double score;
    size_t i;
    mk_status status;

    if (mk_streq(a->grapheme, b->grapheme)) {
        *out = 0.0;
        return MK_OK;
    }
    if (a->cluster_component_count == 0 && b->cluster_component_count == 0) {
        *out = 1.0;
        return MK_OK;
    }
    if (a->cluster_component_count > 0 && b->cluster_component_count == 0) {
        status = mk_distance_cluster_to_segment(system, a, b, node_weights, &component_score);
        if (status != MK_OK) {
            return status;
        }
    } else if (a->cluster_component_count == 0 && b->cluster_component_count > 0) {
        status = mk_distance_cluster_to_segment(system, b, a, node_weights, &component_score);
        if (status != MK_OK) {
            return status;
        }
    } else {
        size_t common = a->cluster_component_count < b->cluster_component_count ?
            a->cluster_component_count : b->cluster_component_count;
        for (i = 0; i < common; i++) {
            double part;
            status = mk_cluster_component_distance(
                system,
                a->cluster_components[i],
                b->cluster_components[i],
                node_weights,
                &part
            );
            if (status != MK_OK) {
                return status;
            }
            component_score += part;
        }
        component_score = common > 0 ? component_score / (double)common : 1.0;
        if (a->cluster_component_count > common) {
            component_score += MK_CLUSTER_LENGTH_PENALTY *
                (double)(a->cluster_component_count - common);
        }
        if (b->cluster_component_count > common) {
            component_score += MK_CLUSTER_LENGTH_PENALTY *
                (double)(b->cluster_component_count - common);
        }
        component_score = mk_min_double(component_score, 1.0);
    }

    status = mk_score_categorical(
        system->builtin, mk_view_of(a), mk_view_of(b), node_weights, &segment_score);
    if (status != MK_OK) {
        return status;
    }
    score = MK_CLUSTER_COMPONENT_SHARE * component_score +
        MK_CLUSTER_SEGMENT_SHARE * segment_score;
    *out = mk_min_double(score, 1.0);
    return MK_OK;
}

mk_status mk_system_segment_distance_with_weights(
    const mk_system *system,
    const char *utf8_a,
    const char *utf8_b,
    const char *node_weights,
    double *out
)
{
    mk_resolution resolved_a;
    mk_resolution resolved_b;
    mk_status status;

    if (out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = 0.0;

    status = mk_resolve(system, utf8_a, &resolved_a);
    if (status != MK_OK) {
        return status;
    }
    status = mk_resolve(system, utf8_b, &resolved_b);
    if (status != MK_OK) {
        mk_resolution_clear(&resolved_a);
        return status;
    }

    if (system->builtin->kind == MK_SYSTEM_CATEGORICAL) {
        if (resolved_a.cluster_component_count > 0 || resolved_b.cluster_component_count > 0) {
            status = mk_vowel_cluster_distance(
                system, &resolved_a, &resolved_b, node_weights, out);
        } else if (mk_streq(resolved_a.grapheme, resolved_b.grapheme)) {
            /* Two spellings of one segment. The scorer would reach 0.0 anyway;
             * this skips the walk over every leaf, group, and scale. */
            *out = 0.0;
        } else {
            status = mk_score_categorical(
                system->builtin,
                mk_view_of(&resolved_a),
                mk_view_of(&resolved_b),
                node_weights,
                out
            );
        }
    } else if (system->builtin->kind == MK_SYSTEM_VALUED) {
        if (mk_streq(resolved_a.grapheme, resolved_b.grapheme)) {
            *out = 0.0;
        } else {
            status = mk_score_valued(
                system->builtin,
                mk_view_of(&resolved_a),
                mk_view_of(&resolved_b),
                node_weights,
                out
            );
        }
    } else {
        status = MK_ERR_UNSUPPORTED_MODEL;
    }
    mk_resolution_clear(&resolved_a);
    mk_resolution_clear(&resolved_b);
    if (status != MK_OK) {
        *out = 0.0;
    }
    return status;
}

/* The most tokens a single system segment can span. "iau³³" already needs
 * four; nothing in the bundled inventories needs more, and an unbounded span
 * would let longest matching swallow whole words. */
#define MK_SYSTEM_SEGMENT_MAX_SPAN 4

mk_status mk_system_segment_ipa(
    const mk_system *system,
    const char *utf8_in,
    mk_string_list **out
)
{
    mk_string_list *orthographic = NULL;
    char **items = NULL;
    size_t count = 0;
    size_t cap = 0;
    size_t total;
    size_t index;
    mk_status status;
    size_t i;

    if (system == NULL || system->builtin == NULL || utf8_in == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;

    /* Start from the orthographic tokens so that normalization, tie bars, and
     * boundary marks keep behaving exactly as mk_segment_ipa documents, then
     * re-join runs of them that this system recognizes as one segment. */
    status = mk_segment_ipa(utf8_in, &orthographic);
    if (status != MK_OK) {
        return status;
    }
    total = mk_string_list_size(orthographic);

    index = 0;
    while (index < total) {
        size_t span = total - index > MK_SYSTEM_SEGMENT_MAX_SPAN ?
            MK_SYSTEM_SEGMENT_MAX_SPAN : total - index;
        char *candidate = NULL;
        size_t chosen = 0;

        for (; span >= 1; span--) {
            char *joined = NULL;
            size_t joined_len = 0;
            size_t joined_cap = 0;
            int is_segment = 0;

            for (i = 0; i < span; i++) {
                status = mk_append_text(
                    &joined,
                    &joined_len,
                    &joined_cap,
                    mk_string_list_get(orthographic, index + i)
                );
                if (status != MK_OK) {
                    free(joined);
                    goto fail;
                }
            }
            if (joined == NULL) {
                continue;
            }
            if (span == 1) {
                /* Nothing longer matched; keep the orthographic token even if
                 * this system does not recognize it, so the tokenizer stays
                 * total. Callers who need a guarantee check mk_system_is_segment
                 * on every token. */
                candidate = joined;
                chosen = 1;
                break;
            }
            status = mk_system_is_segment(system, joined, &is_segment);
            if (status != MK_OK) {
                free(joined);
                goto fail;
            }
            if (is_segment) {
                candidate = joined;
                chosen = span;
                break;
            }
            free(joined);
        }

        if (candidate == NULL) {
            status = MK_ERR_OOM;
            goto fail;
        }
        if (count + 1 > cap) {
            char **next;
            size_t new_cap = cap == 0 ? 8 : cap * 2;
            next = (char **)realloc(items, new_cap * sizeof(*items));
            if (next == NULL) {
                free(candidate);
                status = MK_ERR_OOM;
                goto fail;
            }
            items = next;
            cap = new_cap;
        }
        items[count++] = candidate;
        index += chosen;
    }

    mk_string_list_free(orthographic);
    status = mk_string_list_new((const char *const *)items, count, out);
    for (i = 0; i < count; i++) {
        free(items[i]);
    }
    free(items);
    return status;

fail:
    mk_string_list_free(orthographic);
    for (i = 0; i < count; i++) {
        free(items[i]);
    }
    free(items);
    return status;
}
