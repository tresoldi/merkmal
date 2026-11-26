#include "cluster.h"

#include "geometry.h"
#include "strings.h"

#include <stddef.h>

static double mk_min_double(double a, double b)
{
    return a < b ? a : b;
}

static bool mk_view_has(mk_feature_view view, const char *feature)
{
    return mki_features_contain(view.features, view.count, feature);
}

/* Whether a segment is explicitly marked for length, in any of the degrees the
 * geometry's duration scale carries. */
static bool mk_segment_carries_length(mk_feature_view view)
{
    return mk_view_has(view, "long") ||
        mk_view_has(view, "mid-long") ||
        mk_view_has(view, "ultra-long");
}

/* How sonorous a part is, for choosing the nucleus: a vowel above everything
 * else and an open vowel above a close one; a vowel marked non-syllabic as a
 * glide; then approximants, liquids, nasals, fricatives, affricates and
 * stops. Only the order matters. */
static int mk_sonority(mk_feature_view view)
{
    static const char *const heights[] = {
        "close",
        "near-close",
        "close-mid",
        "mid",
        "open-mid",
        "near-open",
        "open",
    };
    size_t i;

    if (mk_view_has(view, "vowel") && !mk_view_has(view, "non-syllabic")) {
        for (i = sizeof(heights) / sizeof(heights[0]); i > 0; i--) {
            if (mk_view_has(view, heights[i - 1])) {
                return 100 + (int)i;
            }
        }
        return 100;
    }
    if (mk_view_has(view, "vowel") || mk_view_has(view, "approximant")) {
        return 80;
    }
    if (mk_view_has(view, "trill") || mk_view_has(view, "tap") || mk_view_has(view, "lateral")) {
        return 70;
    }
    if (mk_view_has(view, "nasal")) {
        return 60;
    }
    if (mk_view_has(view, "fricative")) {
        return 40;
    }
    if (mk_view_has(view, "affricate")) {
        return 30;
    }
    return 20;
}

/* The part that carries the cluster: the most sonorous, the first on a tie.
 * Taking the first part regardless put a rising diphthong next to its glide:
 * `ia` was nearer `i` (0.22) than `a` (0.30). */
static size_t mk_nucleus_index(const mki_resolution *cluster)
{
    size_t best = 0;
    int best_sonority = -1;
    size_t i;

    for (i = 0; i < cluster->cluster_component_count; i++) {
        int sonority = mk_sonority(mki_view_of_component(&cluster->cluster_components[i]));

        if (sonority > best_sonority) {
            best = i;
            best_sonority = sonority;
        }
    }
    return best;
}

/* Distance between two feature views, through whichever scorer the system
 * uses, and its coverage when `coverage` is non-NULL. Not checked for a NULL
 * scorer: see mki_cluster_distance in cluster.h. */
static mk_status mk_score_views(
    const mk_system *system,
    mk_feature_view a,
    mk_feature_view b,
    const char *node_weights,
    double *out,
    double *coverage
)
{
    return mki_scorer_for(system->builtin)(
        system->builtin, a, b, node_weights, out, coverage
    );
}

/* `a` and `b` weighted, normalized so the result stays in [0, 1] when both
 * are. Coverage is combined with the distance's own weights, but a weight
 * that has no term on one side (a lone nucleus) must not pull it down. */
static double mk_weighted(double wa, double a, double wb, double b)
{
    return (wa * a + wb * b) / (wa + wb);
}

/* One part of a cluster against a resolved segment.
 *
 * Identity is settled by grapheme here and in mk_part_to_part rather than by
 * the scorer, which sees features and no grapheme: two spellings of one
 * segment resolve to the same parts and would reach 0.0 anyway, so the test
 * only skips the walk. Only when no coverage is asked for: the scorer is what
 * says how much of the system a segment covers, even against itself. */
static mk_status mk_part_to_segment(
    const mk_system *system,
    const mki_cluster_component *part,
    const mki_resolution *segment,
    const char *node_weights,
    double *out,
    double *coverage
)
{
    if (coverage == NULL && mki_streq(part->grapheme, segment->grapheme)) {
        *out = 0.0;
        return MK_OK;
    }
    return mk_score_views(
        system,
        mki_view_of_component(part),
        mki_view_of(segment),
        node_weights,
        out,
        coverage
    );
}

/* One part of a cluster against one part of another. */
static mk_status mk_part_to_part(
    const mk_system *system,
    const mki_cluster_component *a,
    const mki_cluster_component *b,
    const char *node_weights,
    double *out,
    double *coverage
)
{
    if (coverage == NULL && mki_streq(a->grapheme, b->grapheme)) {
        *out = 0.0;
        return MK_OK;
    }
    return mk_score_views(
        system,
        mki_view_of_component(a),
        mki_view_of_component(b),
        node_weights,
        out,
        coverage
    );
}

/* A cluster against a plain segment. *coverage, when asked for, weighs each
 * part's coverage as the score weighs its distance; the extra-component
 * penalty is not a measurement and does not enter it. */
static mk_status mk_cluster_to_segment(
    const mk_system *system,
    const mki_resolution *cluster,
    const mki_resolution *segment,
    const char *node_weights,
    double *out,
    double *coverage
)
{
    double score;
    double part;
    double part_coverage = 0.0;
    double nucleus_coverage = 0.0;
    size_t nucleus;
    size_t i;
    mk_status status;

    if (cluster->cluster_component_count == 0) {
        *out = 1.0;
        if (coverage != NULL) {
            *coverage = 0.0;
        }
        return MK_OK;
    }
    nucleus = mk_nucleus_index(cluster);
    status = mk_part_to_segment(
        system, &cluster->cluster_components[nucleus], segment, node_weights, &part,
        coverage == NULL ? NULL : &nucleus_coverage
    );
    if (status != MK_OK) {
        return status;
    }
    score = mki_clements_hume_cluster_nucleus_share * part;
    if (coverage != NULL) {
        *coverage = nucleus_coverage;
    }
    if (cluster->cluster_component_count > 1) {
        double rest = 0.0;
        double rest_coverage = 0.0;
        for (i = 0; i < cluster->cluster_component_count; i++) {
            if (i == nucleus) {
                continue;
            }
            status = mk_part_to_segment(
                system, &cluster->cluster_components[i], segment, node_weights, &part,
                coverage == NULL ? NULL : &part_coverage
            );
            if (status != MK_OK) {
                return status;
            }
            rest += part;
            rest_coverage += part_coverage;
        }
        rest /= (double)(cluster->cluster_component_count - 1);
        rest_coverage /= (double)(cluster->cluster_component_count - 1);
        score += mki_clements_hume_cluster_offglide_share * rest;
        if (coverage != NULL) {
            *coverage = mk_weighted(
                mki_clements_hume_cluster_nucleus_share, nucleus_coverage,
                mki_clements_hume_cluster_offglide_share, rest_coverage
            );
        }
    }
    /* The extra-component penalty says a two-part spelling is further from a
     * one-part segment than a one-part spelling is. That is right for `ai`
     * against `a`, and double-counting for `aa` against `aː`: the length the
     * penalty charges for is the very thing the other side spells out. Charged,
     * it would put a doubled vowel further from the long vowel than a plain
     * short one is, and doubling is how Uralic, Austronesian and much African
     * data write length.
     *
     * Waived, not reversed. `aa` lands where `a` does rather than closer,
     * because whether a doubled vowel means length or a genuine sequence is a
     * property of the source that nothing here can read per form, and claiming
     * more than the source says is how contrasts get merged.
     *
     * The waiver is a rule and stays here; the penalty it waives is data
     * (`cluster_policy` in the geometry file). */
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
    const mki_resolution *a,
    const mki_resolution *b,
    const char *node_weights,
    double *out,
    double *coverage
)
{
    double component_score = 0.0;
    double component_coverage = 0.0;
    double segment_score;
    double segment_coverage = 0.0;
    double score;
    double *want_component = coverage == NULL ? NULL : &component_coverage;
    size_t i;
    mk_status status;

    if (system == NULL || a == NULL || b == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    /* Equal spellings score 0.0 either way; the scorer still has to run when
     * coverage is asked for, because only it can say what was covered. */
    if (coverage == NULL && mki_streq(a->grapheme, b->grapheme)) {
        *out = 0.0;
        return MK_OK;
    }
    if (a->cluster_component_count == 0 && b->cluster_component_count == 0) {
        *out = 1.0;
        if (coverage != NULL) {
            *coverage = 0.0;
        }
        return MK_OK;
    }
    if (a->cluster_component_count > 0 && b->cluster_component_count == 0) {
        status = mk_cluster_to_segment(
            system, a, b, node_weights, &component_score, want_component
        );
        if (status != MK_OK) {
            return status;
        }
    } else if (a->cluster_component_count == 0 && b->cluster_component_count > 0) {
        status = mk_cluster_to_segment(
            system, b, a, node_weights, &component_score, want_component
        );
        if (status != MK_OK) {
            return status;
        }
    } else {
        size_t common = a->cluster_component_count < b->cluster_component_count ? a->cluster_component_count : b->cluster_component_count;
        for (i = 0; i < common; i++) {
            double part;
            double part_coverage = 0.0;
            status = mk_part_to_part(
                system,
                &a->cluster_components[i],
                &b->cluster_components[i],
                node_weights,
                &part,
                want_component == NULL ? NULL : &part_coverage
            );
            if (status != MK_OK) {
                return status;
            }
            component_score += part;
            component_coverage += part_coverage;
        }
        component_score = common > 0 ? component_score / (double)common : 1.0;
        component_coverage = common > 0 ? component_coverage / (double)common : 0.0;
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

    /* A doubled segment against one marked for length is the case the
     * length-penalty waiver in mk_cluster_to_segment exists for, and the
     * whole-segment term would undo it: `aa` carries `diphthong`, `geminate`
     * and the position labels that `aː` lacks, so d(aa, aː) was 0.11 against
     * d(a, aː) = 0.06. The parts alone are scored, so that `aa` lands where
     * `a` does. */
    {
        const mki_resolution *single =
            a->cluster_component_count == 0 ? a : (b->cluster_component_count == 0 ? b : NULL);
        const mki_resolution *doubled = single == a ? b : a;

        if (single != NULL && mk_view_has(mki_view_of(doubled), "geminate") &&
            mk_segment_carries_length(mki_view_of(single))) {
            *out = component_score;
            if (coverage != NULL) {
                *coverage = component_coverage;
            }
            return MK_OK;
        }
    }

    status = mk_score_views(
        system, mki_view_of(a), mki_view_of(b), node_weights, &segment_score,
        coverage == NULL ? NULL : &segment_coverage
    );
    if (status != MK_OK) {
        return status;
    }
    score = mki_clements_hume_cluster_component_share * component_score +
        mki_clements_hume_cluster_segment_share * segment_score;
    *out = mk_min_double(score, 1.0);
    if (coverage != NULL) {
        *coverage = mk_weighted(
            mki_clements_hume_cluster_component_share, component_coverage,
            mki_clements_hume_cluster_segment_share, segment_coverage
        );
    }
    return MK_OK;
}
