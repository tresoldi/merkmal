/* Chao tone. See tone.h.
 *
 * mk_merge_tone_digits and mk_split_tone are public API and inverses of each
 * other: the first moves a tone token onto its nucleus, the second takes it
 * back off. */

#include "tone.h"

#include "ipa.h"
#include "string_list.h"
#include "strings.h"
#include "utf8.h"

#include <stdlib.h>
#include <string.h>

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

int mk_is_chao_digit(const char *p)
{
    return mk_chao_level(p) >= 0;
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
        p += mk_utf8_step(p);
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
        p += mk_utf8_step(p);
    }
    return 0;
}

static int mk_segment_is_syllabic(const char *segment)
{
    const char *p = segment;

    while (*p != '\0') {
        if (mk_has_prefix(p, "̩")) {
            return 1;
        }
        if (mk_is_combining_mark(p)) {
            p += mk_utf8_step(p);
            continue;
        }
        if (mk_is_vowel_letter(p)) {
            return 1;
        }
        p += mk_utf8_step(p);
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

    if (mk_string_list_adopt(items, count, out) != MK_OK) {
        mk_free_items(items, count);
        return MK_ERR_OOM;
    }
    return MK_OK;
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
        p += mk_utf8_step(p);
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
