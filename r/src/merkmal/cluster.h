#ifndef MK_CLUSTER_H
#define MK_CLUSTER_H

/* Scoring a segment written as more than one part: a diphthong, an untied
 * affricate, a geminate.
 *
 * This is a composition policy over the resolver and the geometry rather than a
 * geometry rule -- it reads resolved parts and calls a scorer -- so it sits
 * above both and below the public operations, in a module of its own rather
 * than among the public entry points in system.c.
 *
 * The numbers it composes with are data, in the geometry file's
 * `cluster_policy`, for the reason the tier cost is: changing what a diphthong
 * costs should be a reviewable diff rather than a tree edit. The rules that
 * apply them stay here, because they are rules. */

#include "resolver.h"
#include "system.h"

/* Distance between two resolutions where at least one is a cluster, in
 * [0, 1]: 0.0 for equal graphemes, and 1.0 if neither side is a cluster after
 * all.
 *
 * `coverage` may be NULL. Otherwise it receives the share of the system's
 * dimensions the comparison used, in [0, 1]: each part's coverage from the
 * scorer, weighted as its distance is (nucleus and offglides, components and
 * whole segment), with the length penalties left out because they measure no
 * dimension. 0.0 when neither side is a cluster.
 *
 * Reads the parts the resolver already worked out and never re-resolves a
 * spelling. Either side may be a plain segment: a cluster against one is scored
 * nucleus-first, with the remaining parts averaged.
 *
 * `system` must have a scorer (mki_scorer_for non-NULL); the caller checks,
 * and this does not. Only a categorical system synthesizes clusters, so this
 * is never reached for a valued one -- see mk_admits_synthesized_clusters in
 * the resolver. MK_ERR_INVALID_ARGUMENT for a NULL argument or, once anything
 * is scored, an unknown `node_weights` preset. */
mk_status mki_cluster_distance(
    const mk_system *system,
    const mki_resolution *a,
    const mki_resolution *b,
    const char *node_weights,
    double *out,
    double *coverage
);

#endif
