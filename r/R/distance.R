#' Distances between segments
#'
#' `distance()` scores pairs of segments in a feature system, as a number in
#' \[0, 1\]. `distance_with_coverage()` also reports what each comparison
#' compared: `coverage` is the share of the system's dimensions on which both
#' segments have a value, and `comparability` is `"ok"`, `"cross-tier"` (a tone
#' against a segment, scored at a declared constant) or `"no-shared-dimension"`
#' (a valued system's 0 here means that nothing was compared, not that the
#' segments are identical). `distance_matrix()` scores every pair of a vector of
#' segments; [stats::as.dist()] turns it into a `dist` for clustering.
#'
#' The distance is a weighted mean of differences over the dimensions either
#' segment defines, scored through a declared feature geometry. It is not a
#' metric in the valued systems, and it measures phonetic dissimilarity under a
#' description, not the probability of a sound change. Values are not on a
#' common scale across systems; compare orders of distances within a system.
#'
#' @param a,b Character vectors of graphemes, recycled to a common length.
#' @param node_weights `NULL` for the default weights, or a preset:
#'   `"ignore-tone"`, `"ignore-length"`, `"ignore-secondary"`,
#'   `"ignore-prosodic"`, `"segmental"`, `"tone-heavy"`, `"tone-only"` or
#'   `"flat"`. Record a preset with the result ([operation_fingerprint()]).
#' @inheritParams list_systems
#' @return `distance()` a numeric vector; `distance_with_coverage()` a data
#'   frame; `distance_matrix()` a symmetric matrix named by the segments. A
#'   pair with a segment the system cannot read is `NA`, with a warning.
#' @export
#' @examples
#' distance("p", c("b", "t", "a"))
#' distance("p", "b", system = "phoible")
#' distance_with_coverage("ai", "au", system = "phoible")
#' d <- distance_matrix(c("p", "b", "t", "d", "a"))
#' hclust(as.dist(d))
distance <- function(a, b, system = "distinctive", node_weights = NULL, registry = NULL) {
  res <- .pairs(a, b, system, node_weights, registry)
  res$distance
}

#' @rdname distance
#' @export
distance_with_coverage <- function(a, b, system = "distinctive", node_weights = NULL, registry = NULL) {
  res <- .pairs(a, b, system, node_weights, registry)
  data.frame(
    a = res$a, b = res$b, distance = res$distance, coverage = res$coverage,
    comparability = res$comparability, stringsAsFactors = FALSE
  )
}

#' @rdname distance
#' @param x A character vector of graphemes.
#' @export
distance_matrix <- function(x, system = "distinctive", node_weights = NULL, registry = NULL) {
  x <- .strings(x)
  res <- .Call(r_mk_distance_matrix, .registry_ptr(registry), system, x, node_weights)
  .warn_refused(x, res[[2]])
  m <- res[[1]]
  dimnames(m) <- list(x, x)
  m
}

.pairs <- function(a, b, system, node_weights, registry) {
  a <- .strings(a, "a")
  b <- .strings(b, "b")
  n <- if (length(a) == 0 || length(b) == 0) 0L else max(length(a), length(b))
  a <- rep_len(a, n)
  b <- rep_len(b, n)
  res <- .Call(r_mk_distance, .registry_ptr(registry), system, a, b, node_weights)
  status <- res[[4]]
  bad <- !is.na(status) & status != "ok"
  if (any(bad)) {
    .warn_refused(ifelse(is_segment(a[bad], system, registry), b[bad], a[bad]), status[bad])
  }
  list(a = a, b = b, distance = res[[1]], coverage = res[[2]], comparability = res[[3]])
}

#' Distances in the feature geometry
#'
#' `feature_distance()` counts the edges between two features in the geometry
#' tree (`NA` for a feature that is not a node, as many returned labels are
#' not). `sound_distance()` scores two feature sets through the geometry
#' without any system or grapheme. Both measure the geometry, not segments;
#' compare segments with [distance()].
#'
#' @param a,b For `feature_distance()`, two feature names; for
#'   `sound_distance()`, two character vectors of feature labels.
#' @inheritParams distance
#' @return An integer, or a number in \[0, 1\].
#' @export
#' @examples
#' feature_distance("voiced", "voiceless")
#' sound_distance(c("consonant", "voiceless", "bilabial", "stop"),
#'                c("consonant", "voiced", "bilabial", "stop"))
feature_distance <- function(a, b) {
  .Call(r_mk_feature_distance, .strings(a, "a"), .strings(b, "b"))
}

#' @rdname feature_distance
#' @export
sound_distance <- function(a, b, node_weights = NULL) {
  .Call(r_mk_sound_distance, .strings(a, "a"), .strings(b, "b"), node_weights)
}
