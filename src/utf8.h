#ifndef MK_UTF8_H
#define MK_UTF8_H

/* UTF-8 encoding mechanics and Unicode-level character classification.
 * Nothing here knows what a segment is; see ipa.h for that. */

#include <stddef.h>

/* Byte length of the UTF-8 sequence at `p`, never past the terminator.
 *
 * A lead byte only claims a length; the string need not have it. This returns
 * the smaller of the claimed length and the bytes actually present, and 1 for
 * an invalid lead, so a scan always advances and never steps over the NUL.
 *
 * The bounded form is the only one exposed on purpose. This was
 * mk_utf8_char_len(unsigned char), taking just the lead byte, so nineteen call
 * sites copied or skipped as many bytes as a truncated sequence claimed:
 * mk_segment_ipa("a\xF0") read four bytes out of a two-byte allocation. */
size_t mki_utf8_step(const char *p);

/* The code point at `p`, decoded from the bytes actually present. A truncated
 * sequence yields its lead byte, which the classifiers then treat as an
 * ordinary character rather than a mark. */
unsigned int mki_utf8_codepoint(const char *p);

/* A combining mark, by code point block. */
int mki_is_combining_mark(const char *p);

/* A modifier letter or symbol: the superscripts and spacing modifiers IPA uses
 * to qualify a base segment, plus any mark the diacritic tables name. */
int mki_is_modifier_letter_or_symbol(const char *p);

#endif
