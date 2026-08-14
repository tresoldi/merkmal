#ifndef MK_NORMALIZE_H
#define MK_NORMALIZE_H

/* Turning a written grapheme into the spelling the inventories are keyed by.
 *
 * Decomposition is driven by the compiled table rather than by utf8proc, so
 * that lookup accepts the same graphemes whether or not utf8proc is installed.
 * utf8proc, when present, only adds a final NFC or NFD pass. */

#include "merkmal.h"

/* Lookup normalization: resolve a slash-delimited spelling, strip leading
 * stress marks, decompose, and apply the source conventions (a model written
 * "ʧ" means the segment written "tʃ"). Returns an owned string. */
mk_status mki_normalize_input_grapheme(const char *utf8_in, char **utf8_out);

/* Lookup normalization with the source conventions withheld.
 *
 * The resolver tries this against the inventory first. A convention says "a
 * source writing X means the segment written Y", which is only ever true when
 * the system does not have X itself -- and this table is applied before lookup,
 * so without the earlier attempt a rule here silently replaces a real
 * inventory row. That happened: mapping U+026B to "lˠ" merged two segments
 * PHOIBLE distinguishes. Returns an owned string. */
mk_status mki_normalize_input_grapheme_literal(const char *utf8_in, char **utf8_out);

/* Tokenizer normalization: decompose only. The source conventions are
 * deliberately not applied, because a token is reported as the caller wrote
 * it. Returns an owned string. */
mk_status mki_segmentation_nfd(const char *utf8_in, char **utf8_out);

#endif
