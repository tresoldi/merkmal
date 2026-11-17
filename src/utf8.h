#ifndef MK_UTF8_H
#define MK_UTF8_H

/* UTF-8 encoding mechanics and Unicode-level character classification.
 * Nothing here knows what a segment is; see ipa.h for that. */

#include <stdbool.h>
#include <stddef.h>

/* Byte length of the UTF-8 sequence at `p`, from 1 to 4, never past the
 * terminator.
 *
 * A lead byte only claims a length; the string need not have it. This returns
 * the smaller of the claimed length and the bytes actually present, and 1 for
 * an invalid lead, so a scan always advances and never steps over the NUL.
 * `p` itself must not point at the terminator: there the answer is 1.
 *
 * The bounded form is the only one exposed on purpose. A length taken from the
 * lead byte alone would let a caller copy or skip as many bytes as a truncated
 * sequence claims: mk_segment_ipa("a\xF0") would read four bytes out of a
 * two-byte allocation. */
size_t mki_utf8_step(const char *p);

/* The code point at `p`, decoded from the bytes actually present. A truncated
 * sequence yields its lead byte, which the classifiers then treat as an
 * ordinary character rather than a mark. */
unsigned int mki_utf8_codepoint(const char *p);

/* A combining mark, by code point block. */
bool mki_is_combining_mark(const char *p);

/* A modifier letter or symbol: the superscripts and spacing modifiers IPA uses
 * to qualify a base segment, plus any mark the diacritic tables name. */
bool mki_is_modifier_letter_or_symbol(const char *p);

#endif
