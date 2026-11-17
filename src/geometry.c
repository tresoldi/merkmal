#include "geometry.h"

#include "strings.h"

#include <math.h>
#include <stddef.h>
#include <string.h>

typedef struct mk_node_group {
    const char *node;
    int touched;
    int differs;
} mk_node_group;

static bool mk_view_contains(mk_feature_view view, const char *feature)
{
    return mki_features_contain(view.features, view.count, feature);
}

static bool mk_is_leaf_feature(const char *feature)
{
    size_t i;

    for (i = 0; i < mki_clements_hume_leaf_count; i++) {
        const mki_geometry_leaf *leaf = &mki_clements_hume_leaves[i];
        if ((leaf->positive[0] != '\0' && mki_streq(leaf->positive, feature)) ||
            (leaf->negative[0] != '\0' && mki_streq(leaf->negative, feature))) {
            return true;
        }
    }
    return false;
}

static const char *mk_feature_node(const char *feature)
{
    size_t i;

    for (i = 0; i < mki_clements_hume_feature_to_node_count; i++) {
        if (mki_streq(mki_clements_hume_feature_to_node[i].feature, feature)) {
            return mki_clements_hume_feature_to_node[i].node;
        }
    }
    return NULL;
}

static const mki_feature_path *mk_find_feature_path(const char *feature)
{
    size_t i;

    for (i = 0; i < mki_clements_hume_feature_path_count; i++) {
        if (mki_streq(mki_clements_hume_feature_paths[i].feature, feature)) {
            return &mki_clements_hume_feature_paths[i];
        }
    }
    return NULL;
}

static bool mk_is_ordinal_level_feature(const char *feature)
{
    size_t i;
    size_t j;

    for (i = 0; i < mki_clements_hume_ordinal_scale_count; i++) {
        const mki_ordinal_scale *scale = &mki_clements_hume_ordinal_scales[i];
        for (j = 0; j < scale->level_count; j++) {
            if (mki_streq(scale->levels[j], feature)) {
                return true;
            }
        }
    }
    return false;
}

/* Reports a feature set that sits at two points on one ordered scale. The
 * diacritic composer can build one: breve plus length mark yields both
 * `ultra-short` and `long`, which is not a segment any language contrasts. */
bool mki_ordinal_conflict(
    const char *const *features,
    size_t feature_count,
    const char **scale_out,
    const char **first_out,
    const char **second_out
)
{
    size_t i;
    size_t j;

    for (i = 0; i < mki_clements_hume_ordinal_scale_count; i++) {
        const mki_ordinal_scale *scale = &mki_clements_hume_ordinal_scales[i];
        const char *found = NULL;

        for (j = 0; j < scale->level_count; j++) {
            if (!mki_features_contain(features, feature_count, scale->levels[j])) {
                continue;
            }
            if (found != NULL) {
                if (scale_out != NULL) {
                    *scale_out = scale->name;
                }
                if (first_out != NULL) {
                    *first_out = found;
                }
                if (second_out != NULL) {
                    *second_out = scale->levels[j];
                }
                return true;
            }
            found = scale->levels[j];
        }
    }
    return false;
}

static bool mk_is_metadata_feature(const char *feature)
{
    size_t i;

    for (i = 0; i < mki_default_metadata_feature_count; i++) {
        if (mki_streq(mki_default_metadata_features[i], feature)) {
            return true;
        }
    }
    return false;
}

bool mki_geometry_knows_feature(const char *feature)
{
    if (feature == NULL || feature[0] == '\0') {
        return false;
    }
    return mk_is_metadata_feature(feature) || mki_geometry_scores_feature(feature);
}

bool mki_geometry_scores_feature(const char *feature)
{
    if (feature == NULL || feature[0] == '\0') {
        return false;
    }
    return mk_is_leaf_feature(feature) ||
        mk_is_ordinal_level_feature(feature) ||
        mk_feature_node(feature) != NULL ||
        mk_find_feature_path(feature) != NULL;
}

mk_status mk_feature_distance(
    const char *feature_a,
    const char *feature_b,
    int *out
)
{
    const mki_feature_path *path_a;
    const mki_feature_path *path_b;
    size_t common;
    size_t limit;

    if (feature_a == NULL || feature_b == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }

    /* The domain first, before any equality test: a feature the tree does not
     * contain -- a misspelt one included -- has no path against itself either,
     * not a distance of 0. With both paths in hand, identity needs no special
     * case: the two paths are the same, every element is common, and the
     * arithmetic below yields 0. */
    path_a = mk_find_feature_path(feature_a);
    path_b = mk_find_feature_path(feature_b);
    if (path_a == NULL || path_b == NULL) {
        return MK_ERR_NO_TREE_PATH;
    }

    common = 0;
    limit = path_a->path_count < path_b->path_count ? path_a->path_count : path_b->path_count;
    while (common < limit && mki_streq(path_a->path[common], path_b->path[common])) {
        common++;
    }

    *out = (int)((path_a->path_count - common) + (path_b->path_count - common));
    return MK_OK;
}

static double mk_node_depth_value(const char *node)
{
    size_t i;

    for (i = 0; i < mki_clements_hume_node_depth_count; i++) {
        if (mki_streq(mki_clements_hume_node_depths[i].node, node)) {
            return mki_clements_hume_node_depths[i].depth;
        }
    }
    return 2.0;
}

static const char *mk_geometry_node_parent(const char *node)
{
    size_t i;

    for (i = 0; i < mki_clements_hume_node_parent_count; i++) {
        if (mki_streq(mki_clements_hume_node_parents[i].node, node)) {
            return mki_clements_hume_node_parents[i].parent;
        }
    }
    return "";
}

static const mki_node_weight_preset *mk_find_weight_preset(const char *name)
{
    size_t i;

    if (name == NULL) {
        return NULL;
    }
    for (i = 0; i < mki_clements_hume_weight_preset_count; i++) {
        if (mki_streq(mki_clements_hume_weight_presets[i].name, name)) {
            return &mki_clements_hume_weight_presets[i];
        }
    }
    return NULL;
}

static mk_status mk_resolve_weight_preset(
    const char *node_weights,
    const mki_node_weight_preset **out
)
{
    if (out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;
    if (node_weights == NULL || node_weights[0] == '\0' || mki_streq(node_weights, "None")) {
        return MK_OK;
    }
    *out = mk_find_weight_preset(node_weights);
    return *out == NULL ? MK_ERR_INVALID_ARGUMENT : MK_OK;
}

static double mk_direct_node_weight(
    const mki_node_weight_preset *preset,
    const char *node
)
{
    size_t i;

    if (preset == NULL) {
        return 1.0;
    }
    for (i = 0; i < preset->weight_count; i++) {
        if (mki_streq(preset->weights[i].node, node)) {
            return preset->weights[i].weight;
        }
    }
    return 1.0;
}

static double mk_resolved_node_weight(
    const mki_node_weight_preset *preset,
    const char *node
)
{
    const char *current;
    double weight = 1.0;

    if (preset == NULL) {
        return 1.0;
    }
    current = node;
    while (current != NULL && current[0] != '\0') {
        weight *= mk_direct_node_weight(preset, current);
        current = mk_geometry_node_parent(current);
    }
    return weight;
}

static double mk_dimension_weight(
    const mki_node_weight_preset *preset,
    const char *node,
    double base_weight
)
{
    if (preset != NULL && preset->flat) {
        return 1.0;
    }
    return base_weight * mk_resolved_node_weight(preset, node);
}

/* Finds or appends the group for `node`, without a bounds check. Groups are
 * made only for nodes mk_feature_node returns, so `groups` needs one slot per
 * distinct node in mki_clements_hume_feature_to_node; the 128 in mk_score_leaf
 * is far above what the compiled geometry has. */
static mk_node_group *mk_get_group(
    mk_node_group *groups,
    size_t *count,
    const char *node
)
{
    size_t i;

    for (i = 0; i < *count; i++) {
        if (mki_streq(groups[i].node, node)) {
            return &groups[i];
        }
    }
    groups[*count].node = node;
    groups[*count].touched = 1;
    groups[*count].differs = 0;
    (*count)++;
    return &groups[*count - 1];
}

static void mk_process_node_feature(
    mk_feature_view a,
    mk_feature_view b,
    const char *feature,
    mk_node_group *groups,
    size_t *group_count
)
{
    const char *node;
    mk_node_group *group;
    int in_a;
    int in_b;

    if (mk_is_leaf_feature(feature) || mk_is_ordinal_level_feature(feature)) {
        /* Scored by the leaf loop or by an ordered scale. Letting it also fire
         * the node-group boolean would charge one difference twice. */
        return;
    }
    node = mk_feature_node(feature);
    if (node == NULL) {
        return;
    }

    in_a = mk_view_contains(a, feature);
    in_b = mk_view_contains(b, feature);
    group = mk_get_group(groups, group_count, node);
    if (in_a != in_b) {
        group->differs = 1;
    }
}

bool mki_is_node_group_feature(const char *feature)
{
    if (feature == NULL || mk_is_leaf_feature(feature) || mk_is_ordinal_level_feature(feature)) {
        return false;
    }
    return mk_feature_node(feature) != NULL;
}

/* The first matching level, in scale order, wins. Compiled rows cannot carry
 * two labels from one scale (the generator refuses them) and neither can a
 * synthesized segment (the resolver refuses it); a runtime model row or a
 * feature set handed to mk_sound_distance can, and is read at whichever of
 * the two comes first in the scale. */
static int mk_ordinal_level(
    mk_feature_view view,
    const mki_ordinal_scale *scale
)
{
    size_t i;

    for (i = 0; i < scale->level_count; i++) {
        if (mk_view_contains(view, scale->levels[i])) {
            return (int)i;
        }
    }
    return scale->default_level;
}

int mki_ordinal_level(mk_feature_view view, const mki_ordinal_scale *scale)
{
    return mk_ordinal_level(view, scale);
}

static void mk_accumulate_ordinal_scales(
    mk_feature_view a,
    mk_feature_view b,
    const mki_node_weight_preset *preset,
    double *total_weight,
    double *total_diff
)
{
    size_t i;

    for (i = 0; i < mki_clements_hume_ordinal_scale_count; i++) {
        const mki_ordinal_scale *scale = &mki_clements_hume_ordinal_scales[i];
        int level_a = mk_ordinal_level(a, scale);
        int level_b = mk_ordinal_level(b, scale);
        double weight;
        double span;
        int steps;

        /* The property does not apply to at least one of the two segments:
         * a consonant has no vowel height, a toneless segment no tone level.
         * Major class and tone presence carry that difference already. */
        if (level_a == MKI_ORDINAL_UNDEFINED || level_b == MKI_ORDINAL_UNDEFINED) {
            continue;
        }
        if (scale->level_count < 2) {
            continue;
        }

        weight = mk_dimension_weight(preset, scale->node, scale->weight);
        *total_weight += weight;
        steps = level_a > level_b ? level_a - level_b : level_b - level_a;
        span = (double)(scale->level_count - 1);
        *total_diff += weight * ((double)steps / span);
    }
}

static double mk_dimension_value(
    mk_feature_view view,
    const mki_scalar_dimension *dimension
)
{
    size_t i;

    for (i = 0; i < dimension->positive_count; i++) {
        if (mk_view_contains(view, dimension->positive[i])) {
            return 1.0;
        }
    }
    for (i = 0; i < dimension->negative_count; i++) {
        if (mk_view_contains(view, dimension->negative[i])) {
            return -1.0;
        }
    }
    return 0.0;
}

/* Every scorer opens the same way: zero what it will write, then resolve the
 * weight preset, which is the only thing that can fail before a feature is
 * read. */
static mk_status mk_score_begin(
    const char *node_weights,
    double *out,
    double *coverage,
    const mki_node_weight_preset **preset
)
{
    if (out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = 0.0;
    if (coverage != NULL) {
        *coverage = 0.0;
    }
    return mk_resolve_weight_preset(node_weights, preset);
}

/* Coverage for the two categorical scorers. Both skip a dimension neither
 * segment sets, so a pair that sets none of them arrives here having weighed
 * nothing: the 0.0 it scores means "nothing to compare", not "identical". Real
 * inventory rows always reach some dimension; feature sets handed straight to
 * mk_sound_distance need not. */
static double mk_categorical_coverage(double total_weight)
{
    return total_weight > 0.0 ? 1.0 : 0.0;
}

static mk_status mk_score_scalar(
    const mki_builtin_system *system,
    mk_feature_view a,
    mk_feature_view b,
    const char *node_weights,
    double *out,
    double *coverage
)
{
    size_t i;
    double total_weight = 0.0;
    double total_diff = 0.0;
    const mki_node_weight_preset *preset = NULL;
    mk_status status = mk_score_begin(node_weights, out, coverage, &preset);

    if (status != MK_OK) {
        return status;
    }
    if (system == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }

    for (i = 0; i < system->scalar_dimension_count; i++) {
        const mki_scalar_dimension *dimension = &system->scalar_dimensions[i];
        double a_val = mk_dimension_value(a, dimension);
        double b_val = mk_dimension_value(b, dimension);
        double weight;
        double divisor;

        if (a_val == 0.0 && b_val == 0.0) {
            continue;
        }

        weight = mk_dimension_weight(preset, dimension->geometry_node, dimension->weight);
        total_weight += weight;
        divisor = dimension->negative_count == 0 ? 1.0 : 2.0;
        total_diff += weight * fabs(a_val - b_val) / divisor;
    }

    mk_accumulate_ordinal_scales(a, b, preset, &total_weight, &total_diff);

    *out = total_weight > 0.0 ? total_diff / total_weight : 0.0;
    if (coverage != NULL) {
        *coverage = mk_categorical_coverage(total_weight);
    }
    return MK_OK;
}

static mk_status mk_score_leaf(
    const mki_builtin_system *system,
    mk_feature_view a,
    mk_feature_view b,
    const char *node_weights,
    double *out,
    double *coverage
)
{
    double total_weight = 0.0;
    double total_diff = 0.0;
    size_t i;
    mk_node_group groups[128];
    size_t group_count;
    const mki_node_weight_preset *preset = NULL;
    mk_status status = mk_score_begin(node_weights, out, coverage, &preset);

    /* Scores against the compiled geometry alone, so it has no use for the
     * system and tolerates a NULL one. */
    (void)system;
    if (status != MK_OK) {
        return status;
    }

    for (i = 0; i < mki_clements_hume_leaf_count; i++) {
        const mki_geometry_leaf *leaf = &mki_clements_hume_leaves[i];
        double weight = mk_dimension_weight(preset, leaf->parent, leaf->weight);
        int a_pos = leaf->positive[0] != '\0' && mk_view_contains(a, leaf->positive);
        int a_neg = leaf->negative[0] != '\0' && mk_view_contains(a, leaf->negative);
        int b_pos = leaf->positive[0] != '\0' && mk_view_contains(b, leaf->positive);
        int b_neg = leaf->negative[0] != '\0' && mk_view_contains(b, leaf->negative);
        double a_val;
        double b_val;
        double divisor;

        total_weight += weight;
        if (!a_pos && !a_neg && !b_pos && !b_neg) {
            total_weight -= weight;
            continue;
        }

        a_val = a_pos ? 1.0 : (a_neg ? -1.0 : 0.0);
        b_val = b_pos ? 1.0 : (b_neg ? -1.0 : 0.0);
        divisor = leaf->negative[0] == '\0' ? 1.0 : 2.0;
        total_diff += weight * fabs(a_val - b_val) / divisor;
    }

    memset(groups, 0, sizeof(groups));
    group_count = 0;
    for (i = 0; i < a.count; i++) {
        mk_process_node_feature(a, b, a.features[i], groups, &group_count);
    }
    for (i = 0; i < b.count; i++) {
        if (!mk_view_contains(a, b.features[i])) {
            mk_process_node_feature(a, b, b.features[i], groups, &group_count);
        }
    }

    for (i = 0; i < group_count; i++) {
        double weight = mk_dimension_weight(
            preset,
            groups[i].node,
            1.0 / mk_node_depth_value(groups[i].node)
        );
        total_weight += weight;
        if (groups[i].differs) {
            total_diff += weight;
        }
    }

    mk_accumulate_ordinal_scales(a, b, preset, &total_weight, &total_diff);

    *out = total_weight > 0.0 ? total_diff / total_weight : 0.0;
    if (coverage != NULL) {
        *coverage = mk_categorical_coverage(total_weight);
    }
    return MK_OK;
}

static bool mk_label_value(
    mk_feature_view view,
    const char *feature,
    double *out
)
{
    size_t i;
    size_t feature_len = strlen(feature);

    for (i = 0; i < view.count; i++) {
        const char *label = view.features[i];
        if (strncmp(label, feature, feature_len) == 0 && label[feature_len] == '=') {
            char state = label[feature_len + 1];
            /* Not compared: '0' the feature does not apply, '?' its value is
             * unknown here, '.' a table that does not say which of the two. */
            if (state == '.' || state == '0' || state == '?') {
                return false;
            }
            if (state == '+') {
                *out = 1.0;
            } else if (state == '-') {
                *out = -1.0;
            } else {
                *out = 0.0;
            }
            return true;
        }
    }
    return false;
}

static mk_status mk_score_valued(
    const mki_builtin_system *system,
    mk_feature_view a,
    mk_feature_view b,
    const char *node_weights,
    double *out,
    double *coverage
)
{
    size_t i;
    size_t compared = 0;
    double total_weight = 0.0;
    double total_diff = 0.0;
    const mki_node_weight_preset *preset = NULL;
    mk_status status = mk_score_begin(node_weights, out, coverage, &preset);

    if (status != MK_OK) {
        return status;
    }
    /* Reads the system's geometry map, so unlike the two categorical scorers it
     * cannot answer without one. mki_scorer_for never hands a NULL system here. */
    if (system == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }

    for (i = 0; i < system->geometry_map_count; i++) {
        double a_val = 0.0;
        double b_val = 0.0;
        int a_ok = mk_label_value(a, system->geometry_map[i].feature, &a_val);
        int b_ok = mk_label_value(b, system->geometry_map[i].feature, &b_val);
        double weight;

        if (!a_ok || !b_ok) {
            continue;
        }
        if (a_val == 0.0 && b_val == 0.0) {
            continue;
        }
        compared++;

        weight = system->dimension_weights != NULL ? system->dimension_weights[i] : 0.5;
        weight = mk_dimension_weight(preset, system->geometry_map[i].node, weight);
        total_weight += weight;
        total_diff += weight * fabs(a_val - b_val) / 2.0;
    }

    *out = total_weight > 0.0 ? total_diff / total_weight : 0.0;
    /* The share of the system's declared dimensions on which both segments
     * actually had a value. Without it, a score of 0.0 is ambiguous between
     * "identical" and "nothing in common to compare" -- and the second happens:
     * PHOIBLE writes `.` in many cells, and a pair whose overlap is entirely
     * `.` would score a confident zero. See docs/c-api.md. */
    if (coverage != NULL) {
        *coverage = system->geometry_map_count > 0
            ? (double)compared / (double)system->geometry_map_count
            : 0.0;
    }
    return MK_OK;
}

mki_scorer mki_scorer_for(const mki_builtin_system *system)
{
    /* No system is the compiled geometry alone, which is what leaf scores. */
    if (system == NULL) {
        return mk_score_leaf;
    }
    if (system->kind == MKI_SYSTEM_VALUED) {
        return mk_score_valued;
    }
    if (system->kind != MKI_SYSTEM_CATEGORICAL) {
        /* MKI_SYSTEM_TRAINED names a kind the library has no scorer for.
         * Saying so here gives callers one answer to test instead of each
         * guessing what such a kind means. */
        return NULL;
    }
    /* Declared dimensions of its own, so it is scored on those and never reads
     * a geometry leaf. Only `distinctive` carries them among the compiled
     * systems; a model parsed at runtime declares none and is scored by leaf. */
    if (system->scalar_dimension_count > 0) {
        return mk_score_scalar;
    }
    return mk_score_leaf;
}

const char *mki_scorer_name(mki_scorer scorer)
{
    if (scorer == mk_score_leaf) {
        return "leaf";
    }
    if (scorer == mk_score_scalar) {
        return "scalar";
    }
    if (scorer == mk_score_valued) {
        return "valued";
    }
    return "none";
}

mk_status mk_sound_distance(
    mk_feature_view a,
    mk_feature_view b,
    const char *node_weights,
    double *out
)
{
    size_t i;

    if (out == NULL ||
        (a.count > 0 && a.features == NULL) ||
        (b.count > 0 && b.features == NULL)) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = 0.0;
    for (i = 0; i < a.count; i++) {
        if (!mki_geometry_knows_feature(a.features[i])) {
            return MK_ERR_UNKNOWN_FEATURE;
        }
    }
    for (i = 0; i < b.count; i++) {
        if (!mki_geometry_knows_feature(b.features[i])) {
            return MK_ERR_UNKNOWN_FEATURE;
        }
    }
    return mki_scorer_for(NULL)(NULL, a, b, node_weights, out, NULL);
}

mk_status mki_resolve_weight_preset(const char *name, const mki_node_weight_preset **out)
{
    return mk_resolve_weight_preset(name, out);
}

double mki_dimension_weight(const mki_node_weight_preset *preset, const char *node, double base_weight)
{
    return mk_dimension_weight(preset, node, base_weight);
}

double mki_node_depth_value(const char *node)
{
    return mk_node_depth_value(node);
}

const char *mki_feature_node(const char *feature)
{
    return mk_feature_node(feature);
}
