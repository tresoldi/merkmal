#include "cluster.h"

#include "geometry.h"
#include "strings.h"

#include <stddef.h>

static double mk_min_double(double a, double b)
{
    return a < b ? a : b;
}

static int mk_view_has(mk_feature_view view, const char *feature)
{
    return mki_features_contain(view.features, view.count, feature);
}

/* Whether a segment is explicitly marked for length, in any of the degrees the
 * geometry's duration scale carries. */
static int mk_segment_carries_length(mk_feature_view view)
{
    return mk_view_has(view, "long") ||
        mk_view_has(view, "mid-long") ||
        mk_view_has(view, "ultra-long");
}

/* Distance between two feature views, through whichever scorer the system uses.
 *
 * Identity is settled here rather than by the scorer, which sees features and
 * no grapheme: two spellings of one segment resolve to the same parts and would
 * reach 0.0 anyway, so this skips the walk. */
static mk_status mk_score_views(
    const mk_system *system,
    mk_feature_view a,
    mk_feature_view b,
    const char *node_weights,
    double *out
)
{
    return mki_scorer_for(system->builtin)(
        system->builtin, a, b, node_weights, out, NULL);
}

/* One part of a cluster against a resolved segment. */
static mk_status mk_part_to_segment(
    const mk_system *system,
    const mk_cluster_component *part,
    const mk_resolution *segment,
    const char *node_weights,
    double *out
)
{
    if (mki_streq(part->grapheme, segment->grapheme)) {
        *out = 0.0;
        return MK_OK;
    }
    return mk_score_views(
        system,
        mki_view_of_component(part),
        mki_view_of(segment),
        node_weights,
        out
    );
}

/* One part of a cluster against one part of another. */
static mk_status mk_part_to_part(
    const mk_system *system,
    const mk_cluster_component *a,
    const mk_cluster_component *b,
    const char *node_weights,
    double *out
)
{
    if (mki_streq(a->grapheme, b->grapheme)) {
        *out = 0.0;
        return MK_OK;
    }
    return mk_score_views(
        system,
        mki_view_of_component(a),
        mki_view_of_component(b),
        node_weights,
        out
    );
}

static mk_status mk_cluster_to_segment(
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
    status = mk_part_to_segment(
        system, &cluster->cluster_components[0], segment, node_weights, &part);
    if (status != MK_OK) {
        return status;
    }
    score = mki_clements_hume_cluster_nucleus_share * part;
    if (cluster->cluster_component_count > 1) {
        double rest = 0.0;
        for (i = 1; i < cluster->cluster_component_count; i++) {
            status = mk_part_to_segment(
                system, &cluster->cluster_components[i], segment, node_weights, &part);
            if (status != MK_OK) {
                return status;
            }
            rest += part;
        }
        rest /= (double)(cluster->cluster_component_count - 1);
        score += mki_clements_hume_cluster_offglide_share * rest;
    }
    /* The extra-component penalty says a two-part spelling is further from a
     * one-part segment than a one-part spelling is. That is right for `ai`
     * against `a`, and double-counting for `aa` against `aː`: the length the
     * penalty charges for is the very thing the other side spells out. It made
     * a doubled vowel further from the long vowel (0.233) than a plain short
     * one was (0.064), and doubling is how Uralic, Austronesian and much
     * African data write length.
     *
     * Waived, not reversed. `aa` lands where `a` does rather than closer,
     * because whether a doubled vowel means length or a genuine sequence is a
     * property of the source that nothing here can read per form. Claiming it
     * means length is the move that cost a PHOIBLE contrast when it was applied
     * to `ɫ`.
     *
     * The waiver is a rule and stays here; the 0.15 it waives is data. */
    if (!(mk_view_has(mki_view_of(cluster), "geminate") &&
          mk_segment_carries_length(mki_view_of(segment)))) {
        score += mki_clements_hume_cluster_length_penalty *
            (double)(cluster->cluster_component_count - 1);
    }
    *out = mk_min_double(score, 1.0);
    return MK_OK;
}

mk_status mki_cluster_distance(
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

    if (system == NULL || a == NULL || b == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    if (mki_streq(a->grapheme, b->grapheme)) {
        *out = 0.0;
        return MK_OK;
    }
    if (a->cluster_component_count == 0 && b->cluster_component_count == 0) {
        *out = 1.0;
        return MK_OK;
    }
    if (a->cluster_component_count > 0 && b->cluster_component_count == 0) {
        status = mk_cluster_to_segment(system, a, b, node_weights, &component_score);
        if (status != MK_OK) {
            return status;
        }
    } else if (a->cluster_component_count == 0 && b->cluster_component_count > 0) {
        status = mk_cluster_to_segment(system, b, a, node_weights, &component_score);
        if (status != MK_OK) {
            return status;
        }
    } else {
        size_t common = a->cluster_component_count < b->cluster_component_count ?
            a->cluster_component_count : b->cluster_component_count;
        for (i = 0; i < common; i++) {
            double part;
            status = mk_part_to_part(
                system,
                &a->cluster_components[i],
                &b->cluster_components[i],
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
            component_score += mki_clements_hume_cluster_length_penalty *
                (double)(a->cluster_component_count - common);
        }
        if (b->cluster_component_count > common) {
            component_score += mki_clements_hume_cluster_length_penalty *
                (double)(b->cluster_component_count - common);
        }
        component_score = mk_min_double(component_score, 1.0);
    }

    status = mk_score_views(
        system, mki_view_of(a), mki_view_of(b), node_weights, &segment_score);
    if (status != MK_OK) {
        return status;
    }
    score = mki_clements_hume_cluster_component_share * component_score +
        mki_clements_hume_cluster_segment_share * segment_score;
    *out = mk_min_double(score, 1.0);
    return MK_OK;
}
