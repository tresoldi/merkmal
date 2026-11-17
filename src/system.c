#include "resolver.h"

#include "array.h"
#include "cluster.h"
#include "fingerprint.h"

#include "string_list.h"
#include "strings.h"

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *mk_kind_name(mki_system_type kind)
{
    switch (kind) {
    case MKI_SYSTEM_CATEGORICAL:
        return "categorical";
    case MKI_SYSTEM_VALUED:
        return "valued";
    case MKI_SYSTEM_TRAINED:
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
    mki_resolution entry;
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
    mki_resolution entry;
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
static bool mk_is_tonal_autosegment(mk_feature_view view)
{
    return mki_features_contain(view.features, view.count, "tonal-autosegment");
}

/* The score for two resolved segments, with coverage and comparability when
 * asked for. The caller owns and clears both resolutions. */
static mk_status mk_score_resolved(
    const mk_system *system,
    const mki_resolution *a,
    const mki_resolution *b,
    const char *node_weights,
    double *out,
    double *coverage,
    mk_comparability *why
)
{
    mki_scorer scorer;
    mk_status status;

    /* Cross-tier before anything else. A tone and a segment share no dimension
     * by construction, so scoring them through the geometry would return a
     * number built entirely from how many features the *other* one has, which
     * is not a statement about tone and sits below the cost at which an aligner
     * stops matching the two. Gold alignments never put them in one column.
     * See docs/guide/c-api.md, Distance with coverage. */
    if (mk_is_tonal_autosegment(mki_view_of(a)) != mk_is_tonal_autosegment(mki_view_of(b))) {
        *out = mki_clements_hume_cross_tier_cost;
        if (coverage != NULL) {
            *coverage = 0.0;
        }
        if (why != NULL) {
            *why = MK_CMP_CROSS_TIER;
        }
        return MK_OK;
    }

    scorer = mki_scorer_for(system->builtin);
    if (scorer == NULL) {
        return MK_ERR_UNSUPPORTED_MODEL;
    }
    if (a->cluster_component_count > 0 || b->cluster_component_count > 0) {
        /* Only a categorical system synthesizes clusters, so this never runs
         * for a valued one. See mk_admits_synthesized_clusters in the resolver. */
        status = mki_cluster_distance(system, a, b, node_weights, out, coverage);
    } else if (coverage == NULL && mki_streq(a->grapheme, b->grapheme)) {
        /* Two spellings of one segment. The scorer would reach 0.0 anyway; this
         * skips the walk over every leaf, group, and scale.
         *
         * Only when no coverage was asked for. A segment compared with itself
         * is not necessarily fully covered: a valued system skips the
         * dimensions the segment leaves unset (PHOIBLE's /p/ has gaps), so
         * answering 1.0 here would be coverage relative to the segment, not the
         * system-relative quantity mk_system_segment_distance_ex documents. */
        *out = 0.0;
        status = MK_OK;
    } else {
        status = scorer(
            system->builtin, mki_view_of(a), mki_view_of(b), node_weights, out, coverage
        );
    }

    /* Same tier, nothing in common. The score is 0.0 and does not mean
     * "identical"; saying which is the whole point of this channel. */
    if (status == MK_OK && why != NULL && coverage != NULL && *coverage == 0.0) {
        *why = MK_CMP_NO_SHARED_DIMENSION;
    }
    return status;
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
    mki_resolution resolved_a;
    mki_resolution resolved_b;
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

    status = mk_score_resolved(
        system, &resolved_a, &resolved_b, node_weights, out, coverage, why
    );
    mki_resolution_clear(&resolved_a);
    mki_resolution_clear(&resolved_b);
    if (status != MK_OK) {
        *out = 0.0;
        if (coverage != NULL) {
            *coverage = 0.0;
        }
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
    /* Not seeded here: every scorer reports its own coverage, and a value set
     * by this caller would speak for a scorer it never looked inside. */
    return mk_distance_with_coverage(system, utf8_a, utf8_b, node_weights, out, coverage, why);
}

/* The most tokens a single system segment can span. "iau³³" already needs
 * four; nothing in the bundled inventories needs more, and an unbounded span
 * would let longest matching swallow whole words. */
#define MK_SYSTEM_SEGMENT_MAX_SPAN 4

/* Concatenates `span` orthographic tokens starting at `index`. */
static mk_status mk_join_tokens(
    const mk_string_list *tokens,
    size_t index,
    size_t span,
    char **out
)
{
    char *joined = NULL;
    size_t joined_len = 0;
    size_t joined_cap = 0;
    size_t i;

    for (i = 0; i < span; i++) {
        mk_status status = mki_append_text(
            &joined, &joined_len, &joined_cap, mk_string_list_get(tokens, index + i)
        );
        if (status != MK_OK) {
            free(joined);
            return status;
        }
    }
    *out = joined;
    return MK_OK;
}

/* Whether this system reads `joined` as one segment, for the purpose of
 * merging orthographic tokens.
 *
 * Only when the combined string is explicitly in the inventory or is a known
 * complex segment (affricate, labio-velar, prenasalized stop). Not
 * mk_system_is_segment: it accepts any resolution path, including
 * consonant-cluster synthesis, and so would merge ANY consonant combination
 * (th, ph, st...).
 *
 * A refusal (unknown, malformed, source marker) is a plain no; anything else,
 * such as running out of memory, is returned. */
static mk_status mk_merges_as_one_segment(
    const mk_system *system,
    const char *joined,
    bool *merge
)
{
    mki_resolution res;
    mk_status status = mki_resolve(system, joined, &res);

    *merge = false;
    if (status == MK_OK) {
        *merge = res.path == MKI_RESOLVED_INVENTORY ||
            res.path == MKI_RESOLVED_TIE_STRIPPED ||
            res.path == MKI_RESOLVED_AFFRICATE_RETRACTED ||
            res.path == MKI_RESOLVED_COMPLEX;
        mki_resolution_clear(&res);
        return MK_OK;
    }
    if (status == MK_ERR_UNKNOWN_GRAPHEME ||
        status == MK_ERR_PARSE ||
        status == MK_ERR_SOURCE_MARKER) {
        return MK_OK;
    }
    return status;
}

/* The longest run of orthographic tokens at `index`, up to
 * MK_SYSTEM_SEGMENT_MAX_SPAN, that the system reads as one segment, falling
 * back to the single token. On MK_OK *segment is an owned string and *span
 * says how many tokens it consumed. */
static mk_status mk_longest_segment_at(
    const mk_system *system,
    const mk_string_list *tokens,
    size_t index,
    char **segment,
    size_t *span
)
{
    size_t total = mk_string_list_size(tokens);
    size_t try_span = total - index > MK_SYSTEM_SEGMENT_MAX_SPAN ? MK_SYSTEM_SEGMENT_MAX_SPAN : total - index;

    *segment = NULL;
    *span = 0;
    for (; try_span >= 1; try_span--) {
        char *joined = NULL;
        bool merge = false;
        mk_status status = mk_join_tokens(tokens, index, try_span, &joined);

        if (status != MK_OK) {
            return status;
        }
        if (joined == NULL) {
            continue;
        }
        if (try_span == 1) {
            *segment = joined;
            *span = 1;
            return MK_OK;
        }
        status = mk_merges_as_one_segment(system, joined, &merge);
        if (status != MK_OK || merge) {
            if (status == MK_OK) {
                *segment = joined;
                *span = try_span;
            } else {
                free(joined);
            }
            return status;
        }
        free(joined);
    }
    /* Unreachable: a span of one always returns above, because
     * mki_append_text allocates even for an empty token. Reported as the
     * allocation failure a NULL `joined` would mean. */
    return MK_ERR_OOM;
}

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
        char *segment = NULL;
        size_t span = 0;
        char **next;

        status = mk_longest_segment_at(system, orthographic, index, &segment, &span);
        if (status != MK_OK) {
            goto cleanup;
        }
        next = (char **)mki_grow_array(items, &cap, count, 1, sizeof(*items), 8);
        if (next == NULL) {
            free(segment);
            status = MK_ERR_OOM;
            goto cleanup;
        }
        items = next;
        items[count++] = segment;
        index += span;
    }

    /* The tokens are already owned; hand them over rather than copying every
     * one and freeing the original. */
    status = mki_string_list_adopt(items, count, out);
    if (status == MK_OK) {
        items = NULL;
        count = 0;
    }

cleanup:
    /* Freed once, here and nowhere else: freeing it before the adopt as well
     * would be a double free whenever the adopt fails. */
    mk_string_list_free(orthographic);
    mki_free_items(items, count);
    return status;
}
