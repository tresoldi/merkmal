#ifndef MK_TONE_H
#define MK_TONE_H

/* Chao tone: reading the notation, and moving a tone token onto the segment it
 * belongs to. */

#include "merkmal.h"

/* The Chao pitch level a digit or tone letter denotes, 0-5, or -1 if it is
 * neither. Shared so the tokenizer, the tone-merge step and the recognizer
 * agree on what counts as tone. */
int mki_chao_level(const char *p);

/* Whether one character is a Chao digit at all. */
int mki_is_chao_digit(const char *p);

#endif
