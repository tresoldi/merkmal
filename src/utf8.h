#ifndef MK_UTF8_H
#define MK_UTF8_H

/* UTF-8 encoding mechanics and Unicode-level character classification.
 * Nothing here knows what a segment is; see ipa.h for that. */

#include <stddef.h>

/* Byte length of the UTF-8 sequence a lead byte starts; 1 for an invalid
 * lead, so a scan always advances. */
size_t mk_utf8_char_len(unsigned char c);

/* The code point at `p`. Assumes `p` holds a complete sequence, which every
 * caller guarantees by advancing with mk_utf8_char_len. */
unsigned int mk_utf8_codepoint(const char *p);

/* A combining mark, by code point block. */
int mk_is_combining_mark(const char *p);

/* A modifier letter or symbol: the superscripts and spacing modifiers IPA uses
 * to qualify a base segment, plus any mark the diacritic tables name. */
int mk_is_modifier_letter_or_symbol(const char *p);

#endif
