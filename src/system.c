#include "resolver.h"

#include "cluster.h"
#include "fingerprint.h"

#include "string_list.h"
#include "strings.h"

#include <stdbool.h>
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

mk_status mk_system_semantic_fingerprint(
    const mk_system *system,
    char **payload_out,
    char **digest_out
)
{
    return mki_system_semantic_fingerprint(system, payload_out, digest_out);
}


mk_status mk_system_is_segment(
    const mk_system *system,
    const char *utf8_grapheme,
    bool *out
)
{
    mk_resolution entry;
    mk_status status;

    if (out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = false;
    status = mki_resolve(system, utf8_grapheme, &entry);
    if (status == MK_OK) {
        mki_resolution_clear(&entry);
        *out = true;
        return MK_OK;
    }
    if (status == MK_ERR_UNKNOWN_GRAPHEME) {
        return MK_OK;
    }
    if (status == MK_ERR_PARSE || status == MK_ERR_SOURCE_MARKER) {
        /* Malformed input (an over-long Chao run, say) and source markup
         * (`<?>`, a boundary marker) are both "not a segment". The predicate
         * stays total; callers who want the reason use
         * mk_system_grapheme_features, which reports which it was. */
        return MK_OK;
    }
    return status;
}

mk_status mk_system_grapheme_features(
    const mk_system *system,
    const char *utf8_grapheme,
    mk_string_list **out
)
{
    mk_resolution entry;
    mk_status status;

    if (out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;
    status = mki_resolve(system, utf8_grapheme, &entry);
    if (status != MK_OK) {
        return status;
    }
    status = mki_string_list_from_borrowed(entry.features, entry.feature_count, out);
    mki_resolution_clear(&entry);
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

/* A tone token carries this and nothing else does. See the resolver. */
static int mk_is_tonal_autosegment(mk_feature_view view)
{
    return mki_features_contain(view.features, view.count, "tonal-autosegment");
}

static mk_status mk_distance_with_coverage(
    const mk_system *system,
    const char *utf8_a,
    const char *utf8_b,
    const char *node_weights,
    double *out,
    double *coverage,
    mk_comparability *why
)
{
    mk_resolution resolved_a;
    mk_resolution resolved_b;
    mki_scorer scorer;
    mk_status status;

    if (out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = 0.0;

    status = mki_resolve(system, utf8_a, &resolved_a);
    if (status != MK_OK) {
        return status;
    }
    status = mki_resolve(system, utf8_b, &resolved_b);
    if (status != MK_OK) {
        mki_resolution_clear(&resolved_a);
        return status;
    }

    /* Cross-tier before anything else. A tone and a segment share no dimension
     * by construction, so scoring them through the geometry returns a number
     * built entirely from how many features the *other* one has -- 0.61 against
     * a stop, 0.50 against a vowel -- which is not a statement about tone and
     * sits below the cost at which an aligner stops matching the two. Gold
     * alignments never put them in one column. */
    if (mk_is_tonal_autosegment(mki_view_of(&resolved_a)) !=
        mk_is_tonal_autosegment(mki_view_of(&resolved_b))) {
        *out = mki_clements_hume_cross_tier_cost;
        if (coverage != NULL) {
            *coverage = 0.0;
        }
        if (why != NULL) {
            *why = MK_CMP_CROSS_TIER;
        }
        mki_resolution_clear(&resolved_a);
        mki_resolution_clear(&resolved_b);
        return MK_OK;
    }

    scorer = mki_scorer_for(system->builtin);
    if (scorer == NULL) {
        status = MK_ERR_UNSUPPORTED_MODEL;
    } else if (resolved_a.cluster_component_count > 0 ||
               resolved_b.cluster_component_count > 0) {
        /* Only a categorical system synthesizes clusters, so this never runs
         * for a valued one. See mk_admits_synthesized_clusters in the resolver. */
        status = mki_cluster_distance(
            system, &resolved_a, &resolved_b, node_weights, out);
    } else if (coverage == NULL &&
               mki_streq(resolved_a.grapheme, resolved_b.grapheme)) {
        /* Two spellings of one segment. The scorer would reach 0.0 anyway; this
         * skips the walk over every leaf, group, and scale.
         *
         * Only when no coverage was asked for. A segment compared with itself
         * is not fully covered: a valued system skips the dimensions the
         * segment leaves unset, and PHOIBLE's /p/ leaves 11 of them unset. This
         * used to answer 1.0 for that pair, which is a different quantity from
         * the one mk_system_segment_distance_ex documents. */
        *out = 0.0;
    } else {
        status = scorer(
            system->builtin,
            mki_view_of(&resolved_a),
            mki_view_of(&resolved_b),
            node_weights,
            out,
            coverage
        );
    }
    mki_resolution_clear(&resolved_a);
    mki_resolution_clear(&resolved_b);
    if (status != MK_OK) {
        *out = 0.0;
        if (coverage != NULL) {
            *coverage = 0.0;
        }
        return status;
    }
    /* Same tier, nothing in common. The score is 0.0 and does not mean
     * "identical"; saying which is the whole point of this channel. */
    if (why != NULL && coverage != NULL && *coverage == 0.0) {
        *why = MK_CMP_NO_SHARED_DIMENSION;
    }
    return status;
}

mk_status mk_system_segment_distance_with_weights(
    const mk_system *system,
    const char *utf8_a,
    const char *utf8_b,
    const char *node_weights,
    double *out
)
{
    return mk_distance_with_coverage(system, utf8_a, utf8_b, node_weights, out, NULL, NULL);
}

mk_status mk_system_segment_distance_ex(
    const mk_system *system,
    const char *utf8_a,
    const char *utf8_b,
    const char *node_weights,
    double *out,
    double *coverage,
    mk_comparability *why
)
{
    if (coverage == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    if (why != NULL) {
        *why = MK_CMP_OK;
    }
    /* Every scorer reports its own coverage, so there is nothing to assert on
     * their behalf here. This used to seed 1.0 and let only the valued path
     * overwrite it, which meant the categorical answer was stated by a caller
     * that never looked inside the body it was speaking for. */
    return mk_distance_with_coverage(system, utf8_a, utf8_b, node_weights, out, coverage, why);
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

            for (i = 0; i < span; i++) {
                status = mki_append_text(
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
                candidate = joined;
                chosen = 1;
                break;
            }
            /* Merge adjacent orthographic tokens only when the combined
             * string is explicitly in the inventory or is a known complex
             * segment (affricate, labio-velar, prenasalized stop).  The
             * old code called mk_system_is_segment here, which runs the
             * full resolver including consonant-cluster synthesis and
             * therefore merged ANY consonant combination (th, ph, st…). */
            {
                mk_resolution res;
                status = mki_resolve(system, joined, &res);
                if (status == MK_OK) {
                    bool merge = (res.path == MK_RESOLVED_INVENTORY ||
                                  res.path == MK_RESOLVED_TIE_STRIPPED ||
                                  res.path == MK_RESOLVED_AFFRICATE_RETRACTED ||
                                  res.path == MK_RESOLVED_COMPLEX);
                    mki_resolution_clear(&res);
                    if (merge) {
                        candidate = joined;
                        chosen = span;
                        break;
                    }
                } else if (status != MK_ERR_UNKNOWN_GRAPHEME &&
                           status != MK_ERR_PARSE &&
                           status != MK_ERR_SOURCE_MARKER) {
                    free(joined);
                    goto fail;
                }
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
    /* The tokens are already owned; hand them over rather than copying every
     * one and freeing the original. */
    status = mki_string_list_adopt(items, count, out);
    if (status != MK_OK) {
        goto fail;
    }
    return MK_OK;

fail:
    mk_string_list_free(orthographic);
    for (i = 0; i < count; i++) {
        free(items[i]);
    }
    free(items);
    return status;
}
