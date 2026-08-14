#include "ipa.h"

#include "strings.h"

/* The vowel letters the cluster grammar and the tone-merge step both need.
 * This set was written out twice, in two files, in two different orders. */
int mki_is_vowel_letter(const char *p)
{
    return *p == 'a' || *p == 'e' || *p == 'i' || *p == 'o' || *p == 'u' ||
        mki_has_prefix(p, "y") || mki_has_prefix(p, "ɛ") ||
        mki_has_prefix(p, "ɔ") || mki_has_prefix(p, "ə") ||
        mki_has_prefix(p, "ɨ") || mki_has_prefix(p, "ʉ") ||
        mki_has_prefix(p, "ɯ") || mki_has_prefix(p, "ɵ") ||
        mki_has_prefix(p, "œ") || mki_has_prefix(p, "æ") ||
        mki_has_prefix(p, "ɐ") || mki_has_prefix(p, "ɑ") ||
        mki_has_prefix(p, "ʌ") || mki_has_prefix(p, "ɪ") ||
        mki_has_prefix(p, "ʊ") || mki_has_prefix(p, "ɤ") ||
        mki_has_prefix(p, "ø") || mki_has_prefix(p, "ɘ") ||
        mki_has_prefix(p, "ɜ") || mki_has_prefix(p, "ɞ") ||
        mki_has_prefix(p, "ɒ") || mki_has_prefix(p, "ɶ") ||
        mki_has_prefix(p, "ɿ") || mki_has_prefix(p, "ʅ");
}

int mki_is_boundary(const char *p)
{
    return *p == '+' || *p == '.' || *p == '|' || mki_has_prefix(p, "‖");
}
