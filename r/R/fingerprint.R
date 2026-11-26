#' Identity of results
#'
#' A distance depends on the system, its version, the geometry, the diacritic
#' data, the resolver, the tone grammar and the scoring policy; a package
#' version does not identify them all. `system_fingerprint()` returns the
#' system's semantic fingerprint: a short text naming each of these, and its
#' SHA-256 digest, a compact key for stored results.
#'
#' `operation_fingerprint()` adds the caller's settings (a weight preset, the
#' segmentation and other policies, and any further options) to the system
#' payload. It is the key for cached distances and derived results. The
#' payload and digest are those of the Python package's
#' `operation_fingerprint()` for the same settings. Options may be strings,
#' logicals, integers (`3L`), `NULL`, and lists or vectors of these; give other
#' numbers as integers or strings, since a JSON number's form would differ
#' between languages.
#'
#' The Unicode version of the normalization tables ([build_info()]) is not part
#' of either fingerprint; record it alongside.
#'
#' @inheritParams distance
#' @param tokenization_policy,tone_policy,comparison_policy,missingness_policy
#'   Free-text names of the policies used, `"default"` when not set.
#' @param ... Further options, named.
#' @return A list with `payload` and `digest`.
#' @export
#' @examples
#' system_fingerprint()$digest
#' operation_fingerprint(system = "phoible", node_weights = "ignore-tone",
#'                       tokenization_policy = "system")$digest
system_fingerprint <- function(system = "distinctive", registry = NULL) {
  fp <- .Call(r_mk_fingerprint, .registry_ptr(registry), system)
  list(payload = fp[[1]], digest = fp[[2]])
}

#' @rdname system_fingerprint
#' @export
operation_fingerprint <- function(system = "distinctive", node_weights = NULL,
                                  tokenization_policy = "default", tone_policy = "default",
                                  comparison_policy = "default", missingness_policy = "default",
                                  ..., registry = NULL) {
  options <- list(...)
  if (length(options) > 0 && (is.null(names(options)) || any(names(options) == ""))) {
    stop("merkmal: options must be named", call. = FALSE)
  }
  operation <- list(
    system_payload = system_fingerprint(system, registry)$payload,
    node_weights = node_weights,
    tokenization_policy = tokenization_policy,
    tone_policy = tone_policy,
    comparison_policy = comparison_policy,
    missingness_policy = missingness_policy,
    options = structure(options, names = names(options) %||% character())
  )
  payload <- paste0("schema=merkmal-operation-fingerprint-v1\n", .json(operation, object = TRUE), "\n")
  list(payload = payload, digest = .Call(r_mk_sha256, enc2utf8(payload)))
}

`%||%` <- function(x, y) if (is.null(x)) y else x

# JSON as Python's json.dumps(sort_keys=True, separators=(",", ":"),
# ensure_ascii=False) writes it, for the values operation_fingerprint accepts.
.json <- function(x, object = FALSE) {
  if (is.null(x)) {
    return("null")
  }
  if (is.list(x)) {
    keys <- names(x)
    if (object || !is.null(keys)) {
      if (length(x) == 0) {
        return("{}")
      }
      order <- order(keys, method = "radix")
      parts <- vapply(order, function(i) paste0(.json_string(keys[[i]]), ":", .json(x[[i]])), "")
      return(paste0("{", paste(parts, collapse = ","), "}"))
    }
    return(paste0("[", paste(vapply(x, .json, ""), collapse = ","), "]"))
  }
  if (length(x) != 1) {
    return(paste0("[", paste(vapply(as.list(x), .json, ""), collapse = ","), "]"))
  }
  if (is.na(x)) {
    stop("merkmal: options cannot contain NA", call. = FALSE)
  }
  if (is.character(x)) {
    return(.json_string(x))
  }
  if (is.logical(x)) {
    return(if (x) "true" else "false")
  }
  if (is.integer(x)) {
    return(as.character(x))
  }
  stop("merkmal: give numeric options as integers (3L) or strings", call. = FALSE)
}

.json_string <- function(s) {
  s <- enc2utf8(s)
  codes <- utf8ToInt(s)
  out <- vapply(codes, function(cp) {
    if (cp == 34L) {
      "\\\""
    } else if (cp == 92L) {
      "\\\\"
    } else if (cp == 10L) {
      "\\n"
    } else if (cp == 13L) {
      "\\r"
    } else if (cp == 9L) {
      "\\t"
    } else if (cp == 8L) {
      "\\b"
    } else if (cp == 12L) {
      "\\f"
    } else if (cp < 32L) {
      sprintf("\\u%04x", cp)
    } else {
      intToUtf8(cp)
    }
  }, "")
  paste0("\"", paste(out, collapse = ""), "\"")
}
