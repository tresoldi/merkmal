#ifndef MK_UNICODE_NORM_H
#define MK_UNICODE_NORM_H

/* Unicode canonical normalization, NFD and NFC, from compiled tables.
 *
 * These are the whole of UAX #15's canonical forms -- full decomposition,
 * canonical reordering, canonical composition with blocking, and Hangul -- not
 * an approximation for the letters IPA happens to use. Every build runs them,
 * so a given commit normalizes identically everywhere, at the Unicode version
 * in mki_unicode_version.
 *
 * Bytes that are not well-formed UTF-8 are passed through unchanged and treated
 * as starters with no decomposition, so neither function fails on hostile
 * input except by running out of memory (MK_ERR_OOM). A NULL argument is
 * MK_ERR_INVALID_ARGUMENT. On failure *utf8_out is NULL. */

#include "merkmal.h"

/* An owned copy with every run of combining marks in canonical order and
 * nothing decomposed. Two spellings that differ only in the order of their
 * marks, and are canonically equivalent, become one. */
mk_status mki_unicode_reorder(const char *utf8_in, char **utf8_out);

/* Owned NFD of a NUL-terminated UTF-8 string. */
mk_status mki_unicode_nfd(const char *utf8_in, char **utf8_out);

/* Owned NFC of a NUL-terminated UTF-8 string. */
mk_status mki_unicode_nfc(const char *utf8_in, char **utf8_out);

#endif
