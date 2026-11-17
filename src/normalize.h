#ifndef MK_NORMALIZE_H
#define MK_NORMALIZE_H

/* Turning a written grapheme into the spelling the inventories are keyed by.
 *
 * Decomposition for lookup is driven by a table restricted to letters whose
 * marks the feature system understands. The final NFC or NFD pass is full
 * Unicode normalization from compiled tables (unicode_norm.h), the same in
 * every build. */

#include "merkmal.h"

/* Lookup normalization: resolve a slash-delimited spelling, strip leading
 * stress marks, decompose, and apply the source conventions (a model written
 * "ʧ" means the segment written "tʃ"). On MK_OK *utf8_out is an owned string,
 * possibly empty; it is NULL on failure. Returns MK_ERR_INVALID_ARGUMENT for a
 * NULL argument and MK_ERR_OOM. The same holds for the two functions below. */
mk_status mki_normalize_input_grapheme(const char *utf8_in, char **utf8_out);

/* Lookup normalization with the source conventions withheld.
 *
 * The resolver tries this against the inventory first. A convention says "a
 * source writing X means the segment written Y", which is only ever true when
 * the system does not have X itself -- and the conventions are applied before
 * lookup, so without the earlier attempt a rule would silently replace a real
 * inventory row: mapping U+026B to "lˠ" would merge two segments PHOIBLE
 * distinguishes. */
mk_status mki_normalize_input_grapheme_literal(const char *utf8_in, char **utf8_out);

/* Tokenizer normalization: decompose only, then fold ASCII digits 0-5 to
 * superscript Chao digits. The source conventions are deliberately not
 * applied, because a token is reported as the caller wrote it. */
mk_status mki_segmentation_nfd(const char *utf8_in, char **utf8_out);

#endif
