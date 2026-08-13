#include "utf8.h"

#include "generated/builtin_data.h"
#include "strings.h"

static size_t mk_utf8_claimed_len(unsigned char c)
{
    if (c < 0x80) {
        return 1;
    }
    if ((c & 0xE0) == 0xC0) {
        return 2;
    }
    if ((c & 0xF0) == 0xE0) {
        return 3;
    }
    if ((c & 0xF8) == 0xF0) {
        return 4;
    }
    return 1;
}

size_t mk_utf8_step(const char *p)
{
    size_t claimed = mk_utf8_claimed_len((unsigned char)*p);
    size_t i;

    for (i = 1; i < claimed; i++) {
        if (p[i] == '\0') {
            return i;
        }
    }
    return claimed;
}

unsigned int mk_utf8_codepoint(const char *p)
{
    unsigned char c = (unsigned char)p[0];

    /* Decode only what is there. A sequence cut short by the terminator falls
     * through to the lead byte below. */
    if (mk_utf8_step(p) != mk_utf8_claimed_len(c)) {
        return c;
    }
    if (c < 0x80) {
        return c;
    }
    if ((c & 0xE0) == 0xC0) {
        return ((unsigned int)(c & 0x1F) << 6) |
            (unsigned int)((unsigned char)p[1] & 0x3F);
    }
    if ((c & 0xF0) == 0xE0) {
        return ((unsigned int)(c & 0x0F) << 12) |
            ((unsigned int)((unsigned char)p[1] & 0x3F) << 6) |
            (unsigned int)((unsigned char)p[2] & 0x3F);
    }
    if ((c & 0xF8) == 0xF0) {
        return ((unsigned int)(c & 0x07) << 18) |
            ((unsigned int)((unsigned char)p[1] & 0x3F) << 12) |
            ((unsigned int)((unsigned char)p[2] & 0x3F) << 6) |
            (unsigned int)((unsigned char)p[3] & 0x3F);
    }
    return c;
}

int mk_is_combining_mark(const char *p)
{
    unsigned int cp = mk_utf8_codepoint(p);

    return (cp >= 0x0300 && cp <= 0x036F) ||
        (cp >= 0x1AB0 && cp <= 0x1AFF) ||
        (cp >= 0x1DC0 && cp <= 0x1DFF) ||
        (cp >= 0x20D0 && cp <= 0x20FF) ||
        (cp >= 0xFE20 && cp <= 0xFE2F);
}

static int mk_is_map_mark(const mk_diacritic_map *map, size_t count, const char *p)
{
    size_t i;

    for (i = 0; i < count; i++) {
        if (mk_has_prefix(p, map[i].mark)) {
            return 1;
        }
    }
    return 0;
}

int mk_is_modifier_letter_or_symbol(const char *p)
{
    unsigned int cp = mk_utf8_codepoint(p);

    if (mk_is_map_mark(mk_default_prefix_diacritics, mk_default_prefix_diacritic_count, p) ||
        mk_is_map_mark(mk_default_suffix_diacritics, mk_default_suffix_diacritic_count, p)) {
        return 1;
    }
    return (cp >= 0x02B0 && cp <= 0x02FF) ||
        (cp >= 0x1D2C && cp <= 0x1D6A) ||
        (cp >= 0x1D9B && cp <= 0x1DBF) ||
        (cp >= 0x2070 && cp <= 0x209F);
}
