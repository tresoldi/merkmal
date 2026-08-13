#ifndef MK_GEOMETRY_H
#define MK_GEOMETRY_H

/* The feature geometry, and the two scorers that read it.
 *
 * The scorers live with the geometry rather than in a module of their own:
 * every step of scoring -- leaf lookup, node grouping, ordered scales, weight
 * presets -- reads a geometry table, and separating them would mean exporting
 * eight internal lookups across a header instead of keeping them static. That
 * would move the coupling, not remove it. */

#include "generated/builtin_data.h"
#include "merkmal.h"

#include <stddef.h>

/* mk_feature_view is public, in merkmal.h. Scoring reads feature sets and
 * nothing else: it has no use for a grapheme, an inventory row, or a resolved
 * entry. Taking mk_builtin_entry made five call sites fabricate one on the
 * stack, two of them inventing a grapheme string that the scorer then read to
 * decide identity. */

/* Whether the compiled geometry has anywhere to put this feature. A feature it
 * does not know contributes nothing to any distance, so a model built from such
 * features registers successfully and then scores every comparison as zero. */
int mk_geometry_knows_feature(const char *feature);

/* Whether the feature can actually move a distance, as opposed to merely
 * being a declared label. Metadata features are known but never scored. */
int mk_geometry_scores_feature(const char *feature);

/* Non-zero when a feature set holds two values of one ordered scale. */
int mk_ordinal_conflict(
    const char *const *features,
    size_t feature_count,
    const char **scale_out,
    const char **first_out,
    const char **second_out
);

/* The scoring seam. Both scorers compare two feature sets under a named weight
 * preset and report failure through mk_status, like everything else in the
 * library. They used to return the score directly and signal an unknown preset
 * with NAN, a second error channel every caller had to remember to test.
 *
 * `system` supplies the per-system scoring tables: scalar dimensions for the
 * categorical scorer, the geometry map and dimension weights for the valued
 * one. It may be NULL for the categorical scorer, which then scores against the
 * compiled geometry alone — that is the path mk_sound_distance takes.
 *
 * Identity of the two segments is a caller's question, not a scorer's: two
 * spellings of the same segment resolve to the same features and score 0.0
 * through the ordinary path. */
mk_status mk_score_categorical(
    const mk_builtin_system *system,
    mk_feature_view a,
    mk_feature_view b,
    const char *node_weights,
    double *out
);
mk_status mk_score_valued(
    const mk_builtin_system *system,
    mk_feature_view a,
    mk_feature_view b,
    const char *node_weights,
    double *out
);

#endif
