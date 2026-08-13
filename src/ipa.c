#include "ipa.h"

#include "strings.h"

/* The vowel letters the cluster grammar and the tone-merge step both need.
 * This set was written out twice, in two files, in two different orders. */
int mk_is_vowel_letter(const char *p)
{
    return *p == 'a' || *p == 'e' || *p == 'i' || *p == 'o' || *p == 'u' ||
        mk_has_prefix(p, "y") || mk_has_prefix(p, "ɛ") ||
        mk_has_prefix(p, "ɔ") || mk_has_prefix(p, "ə") ||
        mk_has_prefix(p, "ɨ") || mk_has_prefix(p, "ʉ") ||
        mk_has_prefix(p, "ɯ") || mk_has_prefix(p, "ɵ") ||
        mk_has_prefix(p, "œ") || mk_has_prefix(p, "æ") ||
        mk_has_prefix(p, "ɐ") || mk_has_prefix(p, "ɑ") ||
        mk_has_prefix(p, "ʌ") || mk_has_prefix(p, "ɪ") ||
        mk_has_prefix(p, "ʊ") || mk_has_prefix(p, "ɤ") ||
        mk_has_prefix(p, "ø") || mk_has_prefix(p, "ɘ") ||
        mk_has_prefix(p, "ɜ") || mk_has_prefix(p, "ɞ") ||
        mk_has_prefix(p, "ɒ") || mk_has_prefix(p, "ɶ") ||
        mk_has_prefix(p, "ɿ") || mk_has_prefix(p, "ʅ");
}

int mk_is_boundary(const char *p)
{
    return *p == '+' || *p == '.' || *p == '|' || mk_has_prefix(p, "‖");
}
