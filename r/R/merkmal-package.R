#' merkmal: phonological feature systems and segment distances
#'
#' R bindings to the merkmal C library, which maps IPA transcriptions of
#' speech segments to feature representations under several feature systems
#' and computes dissimilarities between segments. The C core is compiled into
#' the package; there is no system dependency.
#'
#' Every function that reads segments takes a `system` (default
#' `"distinctive"`) and a `registry` (default: the built-in systems). The
#' functions are vectorized over their segment arguments. A segment that a
#' system cannot read gives `NA` with a warning, never a guessed value; use
#' [is_segment()] to test and [diagnose()] to learn why.
#'
#' Results depend on the system, its version and the scoring policy. Store
#' [system_fingerprint()] or [operation_fingerprint()] with any result kept.
#'
#' @keywords internal
#' @useDynLib merkmal, .registration = TRUE
"_PACKAGE"

.merkmal <- new.env(parent = emptyenv())

.default_registry <- function() {
  if (is.null(.merkmal$registry)) {
    .merkmal$registry <- mk_registry()
  }
  .merkmal$registry
}

.registry_ptr <- function(registry) {
  if (is.null(registry)) {
    registry <- .default_registry()
  }
  if (!inherits(registry, "merkmal_registry")) {
    stop("merkmal: `registry` must come from mk_registry()", call. = FALSE)
  }
  registry$ptr
}

.strings <- function(x, what = "x") {
  if (is.factor(x)) {
    x <- as.character(x)
  }
  if (!is.character(x)) {
    stop(sprintf("merkmal: `%s` must be a character vector", what), call. = FALSE)
  }
  enc2utf8(x)
}

.warn_refused <- function(x, status) {
  bad <- !is.na(status) & status != "ok"
  if (any(bad)) {
    shown <- unique(x[bad])
    more <- if (length(shown) > 5) sprintf(" and %d more", length(shown) - 5) else ""
    warning(sprintf(
      "merkmal: %d segment(s) not read, returned as NA: %s%s (see diagnose())",
      sum(bad), paste(utils::head(shown, 5), collapse = ", "), more
    ), call. = FALSE)
  }
}

#' The library behind the package
#'
#' The version of the linked C library, its data profile (`"full"`, or
#' `"cc-by"` without the PHOIBLE and P-base tables), and the Unicode version of
#' its normalization tables, which is part of what identifies a result.
#'
#' @return A named list with `version`, `data_profile` and `unicode_version`.
#' @export
#' @examples
#' build_info()
build_info <- function() {
  info <- .Call(r_mk_build_info)
  list(version = info[[1]], data_profile = info[[2]], unicode_version = info[[3]])
}
