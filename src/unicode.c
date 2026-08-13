#include "internal.h"

#include <stdlib.h>
#include <string.h>

#if MK_HAVE_UTF8PROC
#include <utf8proc.h>
#endif

int mk_has_prefix(const char *s, const char *prefix)
{
    size_t n;

    if (s == NULL || prefix == NULL) {
        return 0;
    }
    n = strlen(prefix);
    return strncmp(s, prefix, n) == 0;
}

mk_status mk_append_text(char **buf, size_t *len, size_t *cap, const char *s)
{
    size_t n;
    char *next;

    n = strlen(s);
    if (*len + n + 1 > *cap) {
        size_t new_cap = *cap == 0 ? 32 : *cap;
        while (*len + n + 1 > new_cap) {
            new_cap *= 2;
        }
        next = (char *)realloc(*buf, new_cap);
        if (next == NULL) {
            return MK_ERR_OOM;
        }
        *buf = next;
        *cap = new_cap;
    }
    memcpy(*buf + *len, s, n);
    *len += n;
    (*buf)[*len] = '\0';
    return MK_OK;
}

size_t mk_utf8_char_len(unsigned char c)
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

static unsigned int mk_utf8_codepoint(const char *p)
{
    unsigned char c = (unsigned char)p[0];

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

static int mk_is_combining_mark(const char *p)
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

static int mk_is_modifier_letter_or_symbol(const char *p)
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

static void mk_free_items(char **items, size_t count)
{
    size_t i;

    if (items == NULL) {
        return;
    }
    for (i = 0; i < count; i++) {
        free(items[i]);
    }
    free(items);
}

static const char *mk_resolve_slash(const char *s)
{
    const char *last;
    const char *p;

    last = NULL;
    for (p = s; *p != '\0'; p++) {
        if (*p == '/') {
            last = p;
        }
    }
    if (last != NULL && last[1] != '\0') {
        return last + 1;
    }
    return s;
}

static const char *mk_strip_leading_stress(const char *s)
{
    while (mk_has_prefix(s, "ˈ") || mk_has_prefix(s, "ˌ")) {
        s += 2;
    }
    return s;
}

static const mk_decomposition *mk_find_decomposition(const char *p)
{
    size_t i;

    for (i = 0; i < mk_default_decomposition_count; i++) {
        if (mk_has_prefix(p, mk_default_decompositions[i].composed)) {
            return &mk_default_decompositions[i];
        }
    }
    return NULL;
}

/* Source spellings that are not canonical decompositions and so cannot come
 * from the table: the IPA script g, the six affricate ligatures, ASCII stand-ins
 * for the apostrophe and the length mark, and cedilla-c.
 *
 * "ç" is here for a specific reason. The generator emits a decomposition only
 * when every mark of the letter is one the feature system understands, and
 * cedilla is not among them, so "ç" is excluded from the table and needs a hand
 * mapping. Any other precomposed letter carrying an uninterpretable mark is
 * deliberately left composed, and therefore rejected rather than guessed at. */
static const mk_decomposition mk_source_conventions[] = {
    { "ɡ", "g" },
    { "ʣ", "dz" },
    { "ʤ", "dʒ" },
    { "ʥ", "dʑ" },
    { "ʦ", "ts" },
    { "ʧ", "tʃ" },
    { "ʨ", "tɕ" },
    { "ç", "ç" },
    { "’", "ʼ" },
    { "'", "ʼ" },
    { ":", "ː" }
};

/* Decompose a token using the compiled table.
 *
 * `source_conventions` also applies the mappings above. Lookup wants them --
 * a source writing "ʧ" means the same segment as one writing "tʃ" -- while the
 * tokenizer must not, because it reports the token as the caller wrote it.
 *
 * Decomposition is driven by the table rather than by utf8proc, so lookup
 * accepts the same graphemes whether or not utf8proc is installed. The table
 * covers only letters whose combining marks the feature system can interpret,
 * so an unsupported source letter is still rejected rather than silently
 * reinterpreted. */
static mk_status mk_decompose(
    const char *utf8_in,
    int source_conventions,
    char **utf8_out
)
{
    const char *p = utf8_in;
    char *tmp = NULL;
    size_t len = 0;
    size_t cap = 0;
    mk_status status;

    *utf8_out = NULL;
    while (*p != '\0') {
        const mk_decomposition *rule = mk_find_decomposition(p);
        size_t i;

        /* Decompose first, so that a precomposed letter and its canonically
         * equivalent sequence resolve identically. Without this, "ǎ" was
         * rejected while the NFD spelling of the same character was accepted,
         * and mk_normalize_grapheme (which returns NFC) turned accepted input
         * into rejected input. */
        if (rule == NULL && source_conventions) {
            for (i = 0; i < sizeof(mk_source_conventions) / sizeof(mk_source_conventions[0]); i++) {
                if (mk_has_prefix(p, mk_source_conventions[i].composed)) {
                    rule = &mk_source_conventions[i];
                    break;
                }
            }
        }
        if (rule != NULL) {
            status = mk_append_text(&tmp, &len, &cap, rule->decomposed);
            p += strlen(rule->composed);
        } else {
            char one[5];
            size_t n = mk_utf8_char_len((unsigned char)*p);
            memcpy(one, p, n);
            one[n] = '\0';
            status = mk_append_text(&tmp, &len, &cap, one);
            p += n;
        }
        if (status != MK_OK) {
            free(tmp);
            return status;
        }
    }

    if (tmp == NULL) {
        tmp = mk_strdup_internal("");
        if (tmp == NULL) {
            return MK_ERR_OOM;
        }
    }
    *utf8_out = tmp;
    return MK_OK;
}

mk_status mk_normalize_input_grapheme(
    const char *utf8_in,
    char **utf8_out
)
{
    if (utf8_in == NULL || utf8_out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *utf8_out = NULL;
    return mk_decompose(
        mk_strip_leading_stress(mk_resolve_slash(utf8_in)),
        1,
        utf8_out
    );
}

static const char *mk_compose_known_pair(const char *base, const char *mark)
{
    if (mk_streq(base, "a") && mk_streq(mark, "̃")) {
        return "ã";
    }
    if (mk_streq(base, "e") && mk_streq(mark, "̃")) {
        return "ẽ";
    }
    if (mk_streq(base, "i") && mk_streq(mark, "̃")) {
        return "ĩ";
    }
    if (mk_streq(base, "o") && mk_streq(mark, "̃")) {
        return "õ";
    }
    if (mk_streq(base, "u") && mk_streq(mark, "̃")) {
        return "ũ";
    }
    if (mk_streq(base, "v") && mk_streq(mark, "̃")) {
        return "ṽ";
    }
    if (mk_streq(base, "a") && mk_streq(mark, "̈")) {
        return "ä";
    }
    if (mk_streq(base, "e") && mk_streq(mark, "̈")) {
        return "ë";
    }
    if (mk_streq(base, "i") && mk_streq(mark, "̈")) {
        return "ï";
    }
    if (mk_streq(base, "o") && mk_streq(mark, "̈")) {
        return "ö";
    }
    if (mk_streq(base, "y") && mk_streq(mark, "̈")) {
        return "ÿ";
    }
    if (mk_streq(base, "a") && mk_streq(mark, "̆")) {
        return "ă";
    }
    if (mk_streq(base, "e") && mk_streq(mark, "̆")) {
        return "ĕ";
    }
    if (mk_streq(base, "i") && mk_streq(mark, "̆")) {
        return "ĭ";
    }
    if (mk_streq(base, "o") && mk_streq(mark, "̆")) {
        return "ŏ";
    }
    if (mk_streq(base, "u") && mk_streq(mark, "̆")) {
        return "ŭ";
    }
    if (mk_streq(base, "c") && mk_streq(mark, "̧")) {
        return "ç";
    }
    if (mk_streq(base, "a") && mk_streq(mark, "́")) {
        return "á";
    }
    if (mk_streq(base, "e") && mk_streq(mark, "́")) {
        return "é";
    }
    if (mk_streq(base, "i") && mk_streq(mark, "́")) {
        return "í";
    }
    if (mk_streq(base, "o") && mk_streq(mark, "́")) {
        return "ó";
    }
    if (mk_streq(base, "u") && mk_streq(mark, "́")) {
        return "ú";
    }
    if (mk_streq(base, "a") && mk_streq(mark, "̀")) {
        return "à";
    }
    if (mk_streq(base, "e") && mk_streq(mark, "̀")) {
        return "è";
    }
    if (mk_streq(base, "i") && mk_streq(mark, "̀")) {
        return "ì";
    }
    if (mk_streq(base, "o") && mk_streq(mark, "̀")) {
        return "ò";
    }
    if (mk_streq(base, "u") && mk_streq(mark, "̀")) {
        return "ù";
    }
    if (mk_streq(base, "a") && mk_streq(mark, "̂")) {
        return "â";
    }
    if (mk_streq(base, "e") && mk_streq(mark, "̂")) {
        return "ê";
    }
    if (mk_streq(base, "i") && mk_streq(mark, "̂")) {
        return "î";
    }
    if (mk_streq(base, "o") && mk_streq(mark, "̂")) {
        return "ô";
    }
    if (mk_streq(base, "u") && mk_streq(mark, "̂")) {
        return "û";
    }
    if (mk_streq(base, "u") && mk_streq(mark, "̈")) {
        return "ü";
    }
    if (mk_streq(base, "u") && mk_streq(mark, "̤")) {
        return "ṳ";
    }
    if (mk_streq(base, "i") && mk_streq(mark, "̰")) {
        return "ḭ";
    }
    if (mk_streq(base, "u") && mk_streq(mark, "̰")) {
        return "ṵ";
    }
    if (mk_streq(base, "a") && mk_streq(mark, "̄")) {
        return "ā";
    }
    if (mk_streq(base, "e") && mk_streq(mark, "̄")) {
        return "ē";
    }
    if (mk_streq(base, "i") && mk_streq(mark, "̄")) {
        return "ī";
    }
    if (mk_streq(base, "o") && mk_streq(mark, "̄")) {
        return "ō";
    }
    if (mk_streq(base, "u") && mk_streq(mark, "̄")) {
        return "ū";
    }
    return NULL;
}

mk_status mk_normalize_grapheme(
    const char *utf8_in,
    char **utf8_out
)
{
    const char *p;
    char *tmp;
    char *out;
    size_t len;
    size_t cap;
    mk_status status;

    if (utf8_in == NULL || utf8_out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *utf8_out = NULL;

    status = mk_normalize_input_grapheme(utf8_in, &tmp);
    if (status != MK_OK) {
        return status;
    }

    out = NULL;
    len = 0;
    cap = 0;
    p = tmp;
    while (*p != '\0') {
        size_t base_len = mk_utf8_char_len((unsigned char)*p);
        if (p[base_len] != '\0') {
            char base[5];
            char mark[5];
            size_t mark_len = mk_utf8_char_len((unsigned char)*(p + base_len));
            const char *composed;

            memcpy(base, p, base_len);
            base[base_len] = '\0';
            memcpy(mark, p + base_len, mark_len);
            mark[mark_len] = '\0';
            composed = mk_compose_known_pair(base, mark);
            if (composed != NULL) {
                status = mk_append_text(&out, &len, &cap, composed);
                p += base_len + mark_len;
            } else if (*p == 'g') {
                status = mk_append_text(&out, &len, &cap, "ɡ");
                p++;
            } else {
                char one[5];
                size_t n = mk_utf8_char_len((unsigned char)*p);
                memcpy(one, p, n);
                one[n] = '\0';
                status = mk_append_text(&out, &len, &cap, one);
                p += n;
            }
        } else if (*p == 'g') {
            status = mk_append_text(&out, &len, &cap, "ɡ");
            p++;
        } else {
            char one[5];
            memcpy(one, p, base_len);
            one[base_len] = '\0';
            status = mk_append_text(&out, &len, &cap, one);
            p += base_len;
        }
        if (status != MK_OK) {
            free(tmp);
            free(out);
            return status;
        }
    }
    free(tmp);

    if (out == NULL) {
        out = mk_strdup_internal("");
        if (out == NULL) {
            return MK_ERR_OOM;
        }
    }

#if MK_HAVE_UTF8PROC
    {
        utf8proc_uint8_t *nfc = utf8proc_NFC((const utf8proc_uint8_t *)out);
        free(out);
        if (nfc == NULL) {
            return MK_ERR_OOM;
        }
        out = (char *)nfc;
    }
#endif

    *utf8_out = out;
    return MK_OK;
}

static int mk_is_boundary(const char *p)
{
    return *p == '+' || *p == '.' || *p == '|' || mk_has_prefix(p, "‖");
}

static int mk_is_suffix_modifier(const char *p)
{
    return mk_is_modifier_letter_or_symbol(p);
}

/* One decoder for both Chao notations, and the only one in the library.
 *
 * The superscript digits carry levels 0-5. The IPA tone letters U+02E5-U+02E9
 * are the same notation written differently and run high to low, 5 down to 1;
 * there is no tone letter for level 0. Returns the level, or -1 when this is
 * not a Chao digit at all.
 *
 * There were three of these, with three different accepted alphabets. The
 * tokenizer grouped tone letters into a run that the merge step could not read
 * and therefore discarded as all-zero, so "a˥" lost its tone; and the
 * recognizer accepted tone letters but not the superscript zero. */
int mk_chao_level(const char *p)
{
    if (p == NULL) {
        return -1;
    }
    if (mk_has_prefix(p, "⁰")) {
        return 0;
    }
    if (mk_has_prefix(p, "¹") || mk_has_prefix(p, "˩")) {
        return 1;
    }
    if (mk_has_prefix(p, "²") || mk_has_prefix(p, "˨")) {
        return 2;
    }
    if (mk_has_prefix(p, "³") || mk_has_prefix(p, "˧")) {
        return 3;
    }
    if (mk_has_prefix(p, "⁴") || mk_has_prefix(p, "˦")) {
        return 4;
    }
    if (mk_has_prefix(p, "⁵") || mk_has_prefix(p, "˥")) {
        return 5;
    }
    return -1;
}

static int mk_is_chao_digit(const char *p)
{
    return mk_chao_level(p) >= 0;
}

static mk_status mk_segmentation_nfd(
    const char *utf8_in,
    char **utf8_out
)
{
    char *tmp = NULL;
    mk_status status;

    if (utf8_in == NULL || utf8_out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *utf8_out = NULL;

    /* The same table lookup uses, so the tokenizer and the recognizer agree on
     * which precomposed letters decompose. This used to be a separate
     * hand-written list of twenty-one letters against the table's 386, which
     * only mattered when utf8proc was absent -- exactly the build that has no
     * second chance to get it right. The source conventions are not applied
     * here: a token is reported as the caller wrote it. */
    status = mk_decompose(utf8_in, 0, &tmp);
    if (status != MK_OK) {
        return status;
    }

#if MK_HAVE_UTF8PROC
    {
        utf8proc_uint8_t *normalized = utf8proc_NFD((const utf8proc_uint8_t *)tmp);
        free(tmp);
        if (normalized == NULL) {
            return MK_ERR_OOM;
        }
        tmp = (char *)normalized;
    }
#endif

    if (tmp == NULL) {
        tmp = mk_strdup_internal("");
        if (tmp == NULL) {
            return MK_ERR_OOM;
        }
    }
    *utf8_out = tmp;
    return MK_OK;
}

static int mk_is_chao_digit_token(const char *s)
{
    const char *p = s;

    if (s == NULL || s[0] == '\0') {
        return 0;
    }
    while (*p != '\0') {
        if (!mk_is_chao_digit(p)) {
            return 0;
        }
        p += mk_utf8_char_len((unsigned char)*p);
    }
    return 1;
}

static int mk_chao_token_has_nonzero(const char *s)
{
    const char *p = s;

    while (*p != '\0') {
        if (mk_chao_level(p) > 0) {
            return 1;
        }
        p += mk_utf8_char_len((unsigned char)*p);
    }
    return 0;
}

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

static int mk_segment_is_syllabic(const char *segment)
{
    const char *p = segment;

    while (*p != '\0') {
        if (mk_has_prefix(p, "̩")) {
            return 1;
        }
        if (mk_is_combining_mark(p)) {
            p += mk_utf8_char_len((unsigned char)*p);
            continue;
        }
        if (mk_is_vowel_letter(p)) {
            return 1;
        }
        p += mk_utf8_char_len((unsigned char)*p);
    }
    return 0;
}

static mk_status mk_concat_strings(const char *a, const char *b, char **out)
{
    size_t a_len;
    size_t b_len;
    char *result;

    if (a == NULL || b == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    a_len = strlen(a);
    b_len = strlen(b);
    result = (char *)malloc(a_len + b_len + 1);
    if (result == NULL) {
        return MK_ERR_OOM;
    }
    memcpy(result, a, a_len);
    memcpy(result + a_len, b, b_len);
    result[a_len + b_len] = '\0';
    *out = result;
    return MK_OK;
}

mk_status mk_segment_ipa(
    const char *utf8_in,
    mk_string_list **out
)
{
    const char *p;
    char **items;
    size_t count;
    size_t cap;
    char *normalized;
    mk_status status;
    char *current;
    size_t current_len;
    size_t current_cap;
    int has_base;
    int after_tie;

    if (utf8_in == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;

    status = mk_segmentation_nfd(utf8_in, &normalized);
    if (status != MK_OK) {
        return status;
    }

    items = NULL;
    count = 0;
    cap = 0;
    current = NULL;
    current_len = 0;
    current_cap = 0;
    has_base = 0;
    after_tie = 0;
    p = normalized;

    while (*p != '\0') {
        size_t n;

        if (*p == ' ') {
            if (current_len > 0) {
                if (count + 1 > cap) {
                    char **next;
                    size_t new_cap = cap == 0 ? 8 : cap * 2;
                    next = (char **)realloc(items, new_cap * sizeof(*items));
                    if (next == NULL) {
                        free(current);
                        free(normalized);
                        mk_free_items(items, count);
                        return MK_ERR_OOM;
                    }
                    items = next;
                    cap = new_cap;
                }
                items[count++] = current;
                current = NULL;
                current_len = 0;
                current_cap = 0;
            }
            has_base = 0;
            after_tie = 0;
            p++;
            continue;
        }

        if (mk_is_chao_digit(p) || mk_is_boundary(p)) {
            if (current_len > 0) {
                if (count + 1 > cap) {
                    char **next;
                    size_t new_cap = cap == 0 ? 8 : cap * 2;
                    next = (char **)realloc(items, new_cap * sizeof(*items));
                    if (next == NULL) {
                        free(current);
                        free(normalized);
                        mk_free_items(items, count);
                        return MK_ERR_OOM;
                    }
                    items = next;
                    cap = new_cap;
                }
                items[count++] = current;
                current = NULL;
                current_len = 0;
                current_cap = 0;
            }
            has_base = 0;
            after_tie = 0;
        }

        if (count + 1 > cap && (mk_is_chao_digit(p) || mk_is_boundary(p))) {
            char **next;
            size_t new_cap = cap == 0 ? 8 : cap * 2;
            next = (char **)realloc(items, new_cap * sizeof(*items));
            if (next == NULL) {
                free(current);
                free(normalized);
                mk_free_items(items, count);
                return MK_ERR_OOM;
            }
            items = next;
            cap = new_cap;
        }

        if (mk_is_chao_digit(p)) {
            const char *start = p;
            char *token;
            while (mk_is_chao_digit(p)) {
                p += mk_utf8_char_len((unsigned char)*p);
            }
            n = (size_t)(p - start);
            token = (char *)malloc(n + 1);
            if (token == NULL) {
                free(normalized);
                mk_free_items(items, count);
                return MK_ERR_OOM;
            }
            memcpy(token, start, n);
            token[n] = '\0';
            items[count++] = token;
            continue;
        } else if (mk_is_boundary(p)) {
            char one[5];
            char *token;
            n = mk_utf8_char_len((unsigned char)*p);
            token = (char *)malloc(n + 1);
            if (token == NULL) {
                free(normalized);
                mk_free_items(items, count);
                return MK_ERR_OOM;
            }
            memcpy(token, p, n);
            token[n] = '\0';
            memcpy(one, p, n);
            p += n;
            items[count++] = token;
            (void)one;
            continue;
        } else if (mk_has_prefix(p, "͡") || mk_has_prefix(p, "͜")) {
            n = mk_utf8_char_len((unsigned char)*p);
            status = mk_append_text(&current, &current_len, &current_cap, mk_has_prefix(p, "͡") ? "͡" : "͜");
            if (status != MK_OK) {
                free(current);
                free(normalized);
                mk_free_items(items, count);
                return status;
            }
            after_tie = 1;
            p += n;
            continue;
        } else if (mk_is_combining_mark(p)) {
            char one[5];
            n = mk_utf8_char_len((unsigned char)*p);
            memcpy(one, p, n);
            one[n] = '\0';
            status = mk_append_text(&current, &current_len, &current_cap, one);
            if (status != MK_OK) {
                free(current);
                free(normalized);
                mk_free_items(items, count);
                return status;
            }
            p += n;
            continue;
        } else if (mk_is_suffix_modifier(p)) {
            char one[5];
            n = mk_utf8_char_len((unsigned char)*p);
            memcpy(one, p, n);
            one[n] = '\0';
            status = mk_append_text(&current, &current_len, &current_cap, one);
            if (status != MK_OK) {
                free(current);
                free(normalized);
                mk_free_items(items, count);
                return status;
            }
            p += n;
            continue;
        } else {
            char one[5];
            if (has_base && !after_tie && current_len > 0) {
                if (count + 1 > cap) {
                    char **next;
                    size_t new_cap = cap == 0 ? 8 : cap * 2;
                    next = (char **)realloc(items, new_cap * sizeof(*items));
                    if (next == NULL) {
                        free(current);
                        free(normalized);
                        mk_free_items(items, count);
                        return MK_ERR_OOM;
                    }
                    items = next;
                    cap = new_cap;
                }
                items[count++] = current;
                current = NULL;
                current_len = 0;
                current_cap = 0;
            }
            n = mk_utf8_char_len((unsigned char)*p);
            memcpy(one, p, n);
            one[n] = '\0';
            status = mk_append_text(&current, &current_len, &current_cap, one);
            if (status != MK_OK) {
                free(current);
                free(normalized);
                mk_free_items(items, count);
                return status;
            }
            has_base = 1;
            after_tie = 0;
            p += n;
            continue;
        }
    }

    if (current_len > 0) {
        if (count + 1 > cap) {
            char **next;
            size_t new_cap = cap == 0 ? 8 : cap * 2;
            next = (char **)realloc(items, new_cap * sizeof(*items));
            if (next == NULL) {
                free(current);
                free(normalized);
                mk_free_items(items, count);
                return MK_ERR_OOM;
            }
            items = next;
            cap = new_cap;
        }
        items[count++] = current;
        current = NULL;
    }
    free(normalized);

    {
        mk_string_list *list = (mk_string_list *)calloc(1, sizeof(*list));
        if (list == NULL) {
            mk_free_items(items, count);
            return MK_ERR_OOM;
        }
        list->items = items;
        list->count = count;
        *out = list;
    }

    return MK_OK;
}

mk_status mk_merge_tone_digits(
    const mk_string_list *segments,
    mk_string_list **out
)
{
    char **items;
    size_t count;
    size_t i;

    if (segments == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;
    items = NULL;
    count = 0;

    if (segments->count > 0) {
        items = (char **)calloc(segments->count, sizeof(*items));
        if (items == NULL) {
            return MK_ERR_OOM;
        }
    }

    for (i = 0; i < segments->count; i++) {
        const char *segment = segments->items[i];
        if (mk_is_chao_digit_token(segment)) {
            size_t j;

            if (!mk_chao_token_has_nonzero(segment)) {
                continue;
            }
            j = count;
            while (j > 0) {
                j--;
                if (mk_streq(items[j], "+")) {
                    break;
                }
                if (mk_segment_is_syllabic(items[j])) {
                    char *merged = NULL;
                    mk_status status = mk_concat_strings(items[j], segment, &merged);
                    if (status != MK_OK) {
                        mk_free_items(items, count);
                        return status;
                    }
                    free(items[j]);
                    items[j] = merged;
                    break;
                }
                if (j == 0) {
                    break;
                }
            }
            continue;
        }

        items[count] = mk_strdup_internal(segment);
        if (items[count] == NULL) {
            mk_free_items(items, count);
            return MK_ERR_OOM;
        }
        count++;
    }

    {
        mk_string_list *list = (mk_string_list *)calloc(1, sizeof(*list));
        if (list == NULL) {
            mk_free_items(items, count);
            return MK_ERR_OOM;
        }
        list->items = items;
        list->count = count;
        *out = list;
    }
    return MK_OK;
}

mk_status mk_segment_ipa_merged(
    const char *utf8_in,
    mk_string_list **out
)
{
    mk_string_list *segments = NULL;
    mk_status status;

    if (out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;
    status = mk_segment_ipa(utf8_in, &segments);
    if (status != MK_OK) {
        return status;
    }
    status = mk_merge_tone_digits(segments, out);
    mk_string_list_free(segments);
    return status;
}

mk_status mk_split_tone(
    const char *segment,
    char **base_out,
    char **tone_out
)
{
    const char *p;
    const char *tone_start;
    size_t base_len;

    if (segment == NULL || base_out == NULL || tone_out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *base_out = NULL;
    *tone_out = NULL;

    /* Walk forward to the first Chao digit: the merged form appends the whole
     * tone token to the nucleus, so everything from there on is the tone. */
    p = segment;
    tone_start = NULL;
    while (*p != '\0') {
        if (mk_is_chao_digit(p)) {
            tone_start = p;
            break;
        }
        p += mk_utf8_char_len((unsigned char)*p);
    }
    if (tone_start == NULL) {
        *base_out = mk_strdup_internal(segment);
        return *base_out == NULL ? MK_ERR_OOM : MK_OK;
    }
    /* A token that is nothing but tone has no base to split off; the caller is
     * holding a standalone tone cluster, which is not a segment. */
    if (tone_start == segment) {
        return MK_ERR_UNKNOWN_GRAPHEME;
    }
    base_len = (size_t)(tone_start - segment);
    *base_out = (char *)malloc(base_len + 1);
    if (*base_out == NULL) {
        return MK_ERR_OOM;
    }
    memcpy(*base_out, segment, base_len);
    (*base_out)[base_len] = '\0';
    *tone_out = mk_strdup_internal(tone_start);
    if (*tone_out == NULL) {
        free(*base_out);
        *base_out = NULL;
        return MK_ERR_OOM;
    }
    return MK_OK;
}
