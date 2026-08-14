#ifndef MK_CLUSTER_H
#define MK_CLUSTER_H

/* Scoring a segment written as more than one part: a diphthong, an untied
 * affricate, a geminate.
 *
 * This is a composition policy over the resolver and the geometry rather than a
 * geometry rule -- it reads resolved parts and calls a scorer -- so it sits
 * above both and below the public operations. It lived in system.c, which meant
 * the file holding the public entry points also held 220 lines of stipulated
 * scoring policy that nothing could reach except through a distance call.
 *
 * The numbers it composes with are data, in the geometry file's
 * `cluster_policy`, for the reason the tier cost is: changing what a diphthong
 * costs should be a reviewable diff rather than a tree edit. The rules that
 * apply them stay here, because they are rules. */

#include "resolver.h"
#include "system.h"

/* Distance between two resolutions where at least one is a cluster.
 *
 * Reads the parts the resolver already worked out and never re-resolves a
 * spelling. Either side may be a plain segment: a cluster against one is scored
 * nucleus-first, with the remaining parts averaged.
 *
 * Only a categorical system synthesizes clusters, so this is never reached for
 * a valued one -- see mk_admits_synthesized_clusters in the resolver. */
mk_status mki_cluster_distance(
    const mk_system *system,
    const mk_resolution *a,
    const mk_resolution *b,
    const char *node_weights,
    double *out
);

#endif
