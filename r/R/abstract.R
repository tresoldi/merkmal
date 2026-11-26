#' Abstract segments
#'
#' An abstract segment is a feature bundle with no grapheme as its identity:
#' one cell per dimension of a system, each holding every value the segment
#' may have. It describes a reconstructed or underspecified sound ("a voiceless
#' stop, place unknown") and is compared with exact bounds over every
#' completion of the unspecified cells.
#'
#' Cells are written `0` (does not apply), `?` (unknown, applies), `*` (unknown,
#' may not apply), a value (`+`, `-`, a level, a label), alternatives `a|b`, a
#' range of levels `lo..hi`, or for a node group an exact set `l1&l2`; `|0` adds
#' "may not apply". A bundle is `column=cell;column=cell`, and columns left out
#' are `*`.
#'
#' @param text A bundle in text form; `""` leaves every cell `*`.
#' @param grapheme A grapheme, for a fully specified bundle.
#' @param segment,a,b Abstract segments.
#' @param column A column name, from `segment_columns()`.
#' @param ... Cells to replace, as `column = "cell"`; quote names that are not
#'   syntactic, such as `` `vowel_height` = "2..3" ``.
#' @param x A character vector of graphemes.
#' @inheritParams distance
#' @return `abstract_segment()`, `abstract_segment_from_grapheme()` and
#'   `with_cells()` an abstract segment; `segment_columns()` and
#'   `column_values()` character vectors; `cells()` a named character vector;
#'   `compare_abstract()` a list with `distance`, `coverage`, `minimum`,
#'   `maximum` and `comparability`; `is_compatible()` a logical vector;
#'   `compatible_graphemes()` the system's graphemes compatible with the
#'   segment, nearest first (for display; the order never decides identity).
#' @export
#' @examples
#' p <- abstract_segment_from_grapheme("p")
#' stop <- with_cells(p, labial = "*", coronal = "*", dorsal = "*")
#' is_compatible(stop, c("t", "k", "b", "a"))
#' compare_abstract(stop, abstract_segment_from_grapheme("b"))
abstract_segment <- function(text = "", system = "distinctive", registry = NULL) {
  ptr <- .registry_ptr(registry)
  .wrap_segment(.Call(r_mk_bundle_new, ptr, system, enc2utf8(text)), system)
}

#' @rdname abstract_segment
#' @export
abstract_segment_from_grapheme <- function(grapheme, system = "distinctive", registry = NULL) {
  ptr <- .registry_ptr(registry)
  .wrap_segment(.Call(r_mk_bundle_from_grapheme, ptr, system, enc2utf8(grapheme)), system)
}

.wrap_segment <- function(ptr, system) {
  structure(list(ptr = ptr, system = system), class = "merkmal_abstract_segment")
}

.segment_ptr <- function(segment) {
  if (!inherits(segment, "merkmal_abstract_segment")) {
    stop("merkmal: not an abstract segment", call. = FALSE)
  }
  segment$ptr
}

#' @rdname abstract_segment
#' @export
segment_columns <- function(segment) {
  .Call(r_mk_bundle_columns, .segment_ptr(segment))
}

#' @rdname abstract_segment
#' @export
column_values <- function(segment, column) {
  .Call(r_mk_bundle_column_values, .segment_ptr(segment), enc2utf8(column))
}

#' @rdname abstract_segment
#' @export
cells <- function(segment) {
  columns <- segment_columns(segment)
  vapply(columns, function(col) .Call(r_mk_bundle_get, .segment_ptr(segment), col), "")
}

#' @rdname abstract_segment
#' @export
with_cells <- function(segment, ...) {
  new <- list(...)
  if (length(new) == 0) {
    return(segment)
  }
  if (is.null(names(new)) || any(names(new) == "")) {
    stop("merkmal: cells must be named by column", call. = FALSE)
  }
  values <- vapply(new, function(v) enc2utf8(as.character(v)), "")
  ptr <- .Call(r_mk_bundle_with_cells, .segment_ptr(segment), enc2utf8(names(new)), unname(values))
  .wrap_segment(ptr, segment$system)
}

#' @rdname abstract_segment
#' @export
compare_abstract <- function(a, b, node_weights = NULL) {
  .Call(r_mk_bundle_compare, .segment_ptr(a), .segment_ptr(b), node_weights)
}

#' @rdname abstract_segment
#' @export
is_compatible <- function(segment, x) {
  .Call(r_mk_bundle_compatible, .segment_ptr(segment), .strings(x))
}

#' @rdname abstract_segment
#' @export
compatible_graphemes <- function(segment, node_weights = NULL) {
  .Call(r_mk_bundle_compatible_graphemes, .segment_ptr(segment), node_weights)
}

#' @export
as.character.merkmal_abstract_segment <- function(x, ...) {
  .Call(r_mk_bundle_text, x$ptr)
}

#' @export
format.merkmal_abstract_segment <- function(x, ...) {
  as.character(x)
}

#' @export
print.merkmal_abstract_segment <- function(x, ...) {
  cat("<merkmal abstract segment, ", x$system, ">\n", as.character(x), "\n", sep = "")
  invisible(x)
}
