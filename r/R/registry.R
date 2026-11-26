#' Registries of feature systems
#'
#' A registry holds the built-in feature systems and any categorical models
#' added at run time. Functions that take a `registry` use a shared built-in
#' registry when it is `NULL`, so most code never creates one.
#'
#' A model is given in merkmal's line-oriented text format: a header naming
#' the model, then one `grapheme` row per segment with its feature labels. A
#' row that names `consonant` or `vowel` receives the class and articulator
#' labels that the compiled tables carry. Validation is strict unless the
#' model says `@validation permissive`.
#'
#' @param registry A registry from `mk_registry()`.
#' @param text The model, as one string.
#' @return `mk_registry()` a new registry; `add_model()` the registry,
#'   invisibly, after adding the model (an error says why a model was refused).
#' @export
#' @examples
#' reg <- mk_registry()
#' add_model(reg, paste(
#'   "@model toy", "@type categorical",
#'   "grapheme p consonant voiceless bilabial stop",
#'   "grapheme t consonant voiceless alveolar stop",
#'   "grapheme b consonant voiced bilabial stop",
#'   sep = "\n"
#' ))
#' distance(c("b", "t"), "p", system = "toy", registry = reg)
mk_registry <- function() {
  structure(list(ptr = .Call(r_mk_registry_new)), class = "merkmal_registry")
}

#' @rdname mk_registry
#' @export
add_model <- function(registry, text) {
  if (!inherits(registry, "merkmal_registry")) {
    stop("merkmal: `registry` must come from mk_registry()", call. = FALSE)
  }
  text <- .strings(text, "text")
  if (length(text) > 1) {
    text <- paste(text, collapse = "\n")
  }
  .Call(r_mk_registry_add_model, registry$ptr, text)
  invisible(registry)
}

#' @export
print.merkmal_registry <- function(x, ...) {
  cat("<merkmal registry>", paste(list_systems(registry = x), collapse = ", "), "\n")
  invisible(x)
}

#' Feature systems
#'
#' `list_systems()` names the systems of a registry, built-in ones first.
#' `system_kind()` says whether a system is `"categorical"` (segments are sets
#' of labels) or `"valued"` (segments have `+`, `-`, `0` or unknown values on a
#' fixed set of features). `system_inventory()` lists the graphemes of the
#' system's own table; segments derived from them (a base with diacritics, a
#' diphthong) are read too but not listed.
#'
#' @param system Name of a feature system.
#' @param registry A registry from [mk_registry()], or `NULL` for the built-in
#'   systems.
#' @return A character vector, or for `system_kind()` a string.
#' @export
#' @examples
#' list_systems()
#' system_kind("phoible")
#' head(system_inventory("distinctive"))
list_systems <- function(registry = NULL) {
  .Call(r_mk_list_systems, .registry_ptr(registry))
}

#' @rdname list_systems
#' @export
system_kind <- function(system = "distinctive", registry = NULL) {
  .Call(r_mk_system_kind, .registry_ptr(registry), system)
}

#' @rdname list_systems
#' @export
system_inventory <- function(system = "distinctive", registry = NULL) {
  .Call(r_mk_inventory, .registry_ptr(registry), system)
}
