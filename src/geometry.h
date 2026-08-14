#ifndef MK_GEOMETRY_H
#define MK_GEOMETRY_H

/* The feature geometry, and the three scorers that read it.
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
int mki_geometry_knows_feature(const char *feature);

/* Whether the feature can actually move a distance, as opposed to merely
 * being a declared label. Metadata features are known but never scored. */
int mki_geometry_scores_feature(const char *feature);

/* Non-zero when a feature set holds two values of one ordered scale. */
int mki_ordinal_conflict(
    const char *const *features,
    size_t feature_count,
    const char **scale_out,
    const char **first_out,
    const char **second_out
);

/* The scoring seam.
 *
 * A scorer compares two feature sets under a named weight preset and reports
 * failure through mk_status, like everything else in the library. Scorers used
 * to return the score directly and signal an unknown preset with NAN, a second
 * error channel every caller had to remember to test.
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
    const mk_builtin_system *system,
    mk_feature_view a,
    mk_feature_view b,
    const char *node_weights,
    double *out,
    double *coverage
);

/* Which scorer a system is scored by. Never NULL for a system the library can
 * score, NULL for one it cannot -- which is the only place the caller has to
 * decide anything.
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
 * The selection used to be two tests on two different fields in two files: a
 * `kind` test in system.c chose categorical against valued, and a test on
 * `scalar_dimension_count` inside the categorical body chose scalar against
 * leaf. The second was invisible from this header, and it was the one that
 * picked the scorer for `distinctive` -- the default system. */
mki_scorer mki_scorer_for(const mk_builtin_system *system);

/* A stable label for a scorer, for diagnostics and test output: "leaf",
 * "scalar", "valued", or "none" for a kind nothing scores. Static storage;
 * never freed. Which scorer a system reaches is part of the answer, the same
 * way a resolution path is -- see mki_resolution_path_name. */
const char *mki_scorer_name(mki_scorer scorer);

#endif
