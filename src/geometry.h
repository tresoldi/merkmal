#ifndef MK_GEOMETRY_H
#define MK_GEOMETRY_H

/* The feature geometry, and the three scorers that read it.
 *
 * The scorers live with the geometry rather than in a module of their own:
 * every step of scoring -- leaf lookup, node grouping, ordered scales, weight
 * presets -- reads a geometry table, and separating them would mean exporting
 * the internal lookups across a header instead of keeping them static. That
 * would move the coupling, not remove it. */

#include "generated/builtin_data.h"
#include "merkmal.h"

#include <stdbool.h>
#include <stddef.h>

/* The scorers take mk_feature_view (public, in merkmal.h) and nothing richer.
 * Scoring reads feature sets only: it has no use for a grapheme, an inventory
 * row or a resolved entry, and taking one would make callers that have only
 * features fabricate it, grapheme included, for a scorer that must not decide
 * identity by grapheme. */

/* Whether the compiled geometry has anywhere to put this feature, metadata
 * included. False for NULL and "". A feature it does not know contributes
 * nothing to any distance, which is why strict model validation refuses one:
 * a model built from such features would register and then score every
 * comparison as zero. */
bool mki_geometry_knows_feature(const char *feature);

/* Whether the feature can actually move a distance, as opposed to merely
 * being a declared label. Metadata features are known but never scored. False
 * for NULL and "". */
bool mki_geometry_scores_feature(const char *feature);

/* Whether the leaf scorer compares this feature as a member of a node group:
 * it maps to a geometry node and is neither a leaf value nor a level of an
 * ordered scale. Such features are the one-hot columns of a leaf-scored
 * system's feature vector. */
bool mki_is_node_group_feature(const char *feature);

/* A feature set's position on an ordered scale, exactly as the scorers read
 * it: the first level label present, else the scale's unmarked default, else
 * MKI_ORDINAL_UNDEFINED. */
int mki_ordinal_level(mk_feature_view view, const mki_ordinal_scale *scale);

/* The weighting the scorers use, for code that scores outside a feature view
 * (abstract segments, bundle.c). Same functions, so a bundle made from a
 * grapheme weighs each dimension exactly as the scorer does.
 *
 * mki_resolve_weight_preset: a NULL, empty or "None" name selects no preset
 * (*out NULL, MK_OK); an unknown name, or a NULL out, is
 * MK_ERR_INVALID_ARGUMENT. The preset is static storage.
 * mki_node_depth_value is 2.0 for a node the geometry does not list.
 * mki_feature_node is NULL for a feature mapped to no node; otherwise static. */
mk_status mki_resolve_weight_preset(const char *name, const mki_node_weight_preset **out);
double mki_dimension_weight(const mki_node_weight_preset *preset, const char *node, double base_weight);
double mki_node_depth_value(const char *node);
const char *mki_feature_node(const char *feature);

/* True when a feature set holds two levels of one ordered scale. Each non-NULL
 * output then receives the scale's name and the two levels in scale order, all
 * static storage; on false the outputs are untouched. */
bool mki_ordinal_conflict(
    const char *const *features,
    size_t feature_count,
    const char **scale_out,
    const char **first_out,
    const char **second_out
);

/* The scoring seam.
 *
 * A scorer compares two feature sets under a named weight preset and reports
 * failure through mk_status, like everything else in the library, not through
 * a NAN score, which would be a second error channel every caller had to
 * remember to test. *out is a distance in [0, 1]. MK_ERR_INVALID_ARGUMENT
 * means a NULL `out`, an unknown preset name, or a NULL system for the scalar
 * or valued scorer; whenever `out` is non-NULL it and `coverage` are zeroed
 * first, so they read 0.0 after a failure.
 *
 * `coverage` may be NULL. When given, it receives the share of the comparison
 * that actually happened -- the thing that separates "identical" from "nothing
 * to compare". Every scorer reports it, because the caller cannot know which
 * one it reached and must not have to.
 *
 * Identity of the two segments is a caller's question, not a scorer's: two
 * spellings of the same segment resolve to the same features and score 0.0
 * through the ordinary path. */
typedef mk_status (*mki_scorer)(
    const mki_builtin_system *system,
    mk_feature_view a,
    mk_feature_view b,
    const char *node_weights,
    double *out,
    double *coverage
);

/* Which scorer a system is scored by. Never NULL for a system the library can
 * score, NULL for one it cannot (MKI_SYSTEM_TRAINED) -- which is the only place
 * the caller has to decide anything.
 *
 * Three scorers, selected here and nowhere else:
 *
 *   leaf    the compiled geometry's leaves, node groups and ordered scales.
 *           Takes a NULL system and scores against the geometry alone, which
 *           is the path mk_sound_distance and every runtime model take.
 *   scalar  the system's own declared scalar dimensions, plus ordered scales.
 *           Never reads a geometry leaf.
 *   valued  the system's geometry map and dimension weights, reading `name=state`
 *           cells. Requires a system; a NULL one can never select it.
 *
 * Both tests, on `kind` and on `scalar_dimension_count`, are made here and
 * nowhere else. The second picks the scorer for `distinctive`, the default
 * system, and a test hidden inside a scorer body would be invisible from this
 * header. */
mki_scorer mki_scorer_for(const mki_builtin_system *system);

/* A stable label for a scorer, for diagnostics and test output: "leaf",
 * "scalar", "valued", or "none" for a kind nothing scores. Static storage;
 * never freed. Which scorer a system reaches is part of the answer, the same
 * way a resolution path is -- see mki_resolution_path_name. */
const char *mki_scorer_name(mki_scorer scorer);

#endif
