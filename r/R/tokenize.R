#' Normalization and segmentation
#'
#' `normalize()` gives merkmal's normalized form of each grapheme (NFC with its
#' IPA rewrites, so that `ʧ` becomes `tʃ`), for display and for comparing
#' spellings; pass graphemes to the other functions as written.
#' `unicode_normalize()` is plain Unicode normalization at the library's
#' Unicode version.
#'
#' `segment_ipa()` splits text at every base character not joined by a tie bar.
#' `system_segment_ipa()` takes the longest sequence the system reads as one
#' segment, so `"tʃa"` gives `tʃ`, `a`; input the system does not read is kept
#' as its orthographic token. `segment_ipa_merged()` and `merge_tone_digits()`
#' attach Chao tone digits to the vowel or syllabic consonant that bears them;
#' `split_tone()` undoes that. `ascii_chao_digits()` rewrites ASCII digits 0-5
#' as Chao digits, for text known to write pitch levels in ASCII (not for
#' romanizations whose digits number tone categories).
#'
#' Neither segmentation is a phonological analysis (`kp` may be a cluster);
#' record the policy and system with any stored segmentation.
#'
#' @param x A character vector.
#' @param form `"NFC"` or `"NFD"`.
#' @param segments A character vector of segments.
#' @inheritParams list_systems
#' @return `normalize()`, `unicode_normalize()` and `ascii_chao_digits()` a
#'   character vector; the segmenters a list of character vectors, one per
#'   element of `x`; `merge_tone_digits()` a character vector; `split_tone()` a
#'   data frame with `base` and `tone` (`NA` when there is none).
#' @export
#' @examples
#' normalize("ʧ")
#' segment_ipa("tʃa")
#' system_segment_ipa(c("tʃa", "kpa"))
#' segment_ipa_merged("tʰoŋ⁵⁵")
#' split_tone("o⁵⁵")
#' ascii_chao_digits("ma55")
normalize <- function(x) {
  .Call(r_mk_normalize, .strings(x))
}

#' @rdname normalize
#' @export
unicode_normalize <- function(x, form = c("NFC", "NFD")) {
  .Call(r_mk_unicode_normalize, .strings(x), match.arg(form))
}

#' @rdname normalize
#' @export
segment_ipa <- function(x) {
  .Call(r_mk_segment_ipa, .strings(x))
}

#' @rdname normalize
#' @export
system_segment_ipa <- function(x, system = "distinctive", registry = NULL) {
  .Call(r_mk_system_segment_ipa, .registry_ptr(registry), system, .strings(x))
}

#' @rdname normalize
#' @export
segment_ipa_merged <- function(x) {
  .Call(r_mk_segment_ipa_merged, .strings(x))
}

#' @rdname normalize
#' @export
merge_tone_digits <- function(segments) {
  .Call(r_mk_merge_tone_digits, .strings(segments, "segments"))
}

#' @rdname normalize
#' @export
split_tone <- function(x) {
  x <- .strings(x)
  res <- .Call(r_mk_split_tone, x)
  .warn_refused(x, res[[3]])
  data.frame(segment = x, base = res[[1]], tone = res[[2]], stringsAsFactors = FALSE)
}

#' @rdname normalize
#' @export
ascii_chao_digits <- function(x) {
  .Call(r_mk_ascii_chao_digits, .strings(x))
}
