#' Reading segments
#'
#' `is_segment()` says whether a system reads each grapheme. `get_features()`
#' returns the feature labels of each grapheme (for a valued system, labels of
#' the form `feature=value`). `diagnose()` explains a refusal: the status, the
#' longest prefix that was read, and the offending character.
#'
#' A grapheme is read through normalization (Unicode composition, equivalent
#' and obsolete letters, a leading stress mark, the standardized side of a
#' `source/standard` pair), lookup in the system's table, and derivation of
#' segments the table does not list (a base with diacritics or tones, a
#' diphthong, an affricate without a tie bar, a cluster). A valued system
#' derives a marked segment only if its own table shows what the mark does.
#'
#' @param x A character vector of graphemes, one segment each.
#' @inheritParams list_systems
#' @return `is_segment()` a logical vector; `get_features()` a named list of
#'   character vectors (`NULL` for a refused grapheme, with a warning);
#'   `diagnose()` a data frame with one row per grapheme.
#' @export
#' @examples
#' is_segment(c("tʰ", "pʰ1", "<?>"))
#' get_features("tʰ")
#' diagnose(c("tʰ", "pʰ1", "ɑ̠̠", "<?>"))
is_segment <- function(x, system = "distinctive", registry = NULL) {
  .Call(r_mk_is_segment, .registry_ptr(registry), system, .strings(x))
}

#' @rdname is_segment
#' @export
get_features <- function(x, system = "distinctive", registry = NULL) {
  x <- .strings(x)
  res <- .Call(r_mk_features, .registry_ptr(registry), system, x)
  .warn_refused(x, res[[2]])
  out <- lapply(res[[1]], function(f) if (is.null(f)) NULL else sort(f, method = "radix"))
  names(out) <- x
  out
}

#' @rdname is_segment
#' @export
diagnose <- function(x, system = "distinctive", registry = NULL) {
  x <- .strings(x)
  res <- .Call(r_mk_diagnose, .registry_ptr(registry), system, x)
  data.frame(
    grapheme = x, status = res[[1]], ok = res[[1]] == "ok",
    valid_prefix = res[[2]], offset = res[[3]], offending = res[[4]],
    stringsAsFactors = FALSE
  )
}

#' Feature vectors
#'
#' A fixed-width numeric vector per grapheme, one column per dimension the
#' system's scorer reads: `1` the feature is present, `-1` it applies and is
#' absent, `0` it does not apply, `NaN` unknown (valued systems); ordered
#' scales are levels in (0, 1]. Graphemes with equal vectors are at distance
#' zero. The encoding follows soundvectors (Rubehn, Nieder, Forkel and List
#' 2024).
#'
#' @inheritParams is_segment
#' @return `feature_vectors()` a matrix with one row per grapheme (`NA` for a
#'   refused grapheme, with a warning) and columns named by
#'   `vector_labels()`.
#' @export
#' @examples
#' m <- feature_vectors(c("p", "b", "a"), system = "phoible")
#' dim(m)
feature_vectors <- function(x, system = "distinctive", registry = NULL) {
  x <- .strings(x)
  ptr <- .registry_ptr(registry)
  res <- .Call(r_mk_feature_vectors, ptr, system, x)
  .warn_refused(x, res[[2]])
  m <- res[[1]]
  dimnames(m) <- list(x, .Call(r_mk_vector_labels, ptr, system))
  m
}

#' @rdname feature_vectors
#' @export
vector_labels <- function(system = "distinctive", registry = NULL) {
  .Call(r_mk_vector_labels, .registry_ptr(registry), system)
}
