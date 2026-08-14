#ifndef MK_IPA_H
#define MK_IPA_H

/* IPA orthographic classification: what role a character plays in a
 * transcription, as opposed to what Unicode calls it. */

/* Whether this codepoint is one of the vowel letters the cluster grammar
 * admits and the tone-merge step treats as a nucleus. */
int mki_is_vowel_letter(const char *p);

/* A segment boundary marker: morpheme, syllable, word, or phrase. */
int mki_is_boundary(const char *p);

#endif
