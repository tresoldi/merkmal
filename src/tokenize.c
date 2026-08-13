/* Orthographic tokenization: a new token starts at each new base code point
 * unless a tie bar joins it to the previous one.
 *
 * The whole interface is public, so there is no tokenize.h; see merkmal.h for
 * the policy this implements and for where it deliberately disagrees with a
 * system's own inventory. */

#include "merkmal.h"

#include "ipa.h"
#include "normalize.h"
#include "string_list.h"
#include "strings.h"
#include "tone.h"
#include "utf8.h"

#include <stdlib.h>
#include <string.h>

/* Push an owned token onto the array, growing it as needed.
 *
 * This replaced five copies of the same realloc block, one of which ran ahead
 * of the branch that used it so that two later `items[count++]` writes had no
 * visible bound. Those were safe -- the pre-grow covered them -- but only by an
 * argument spanning forty lines, and Clang's analyzer reported them as null
 * dereferences because it could not make that argument either. */
static mk_status mk_push_token(char ***items, size_t *count, size_t *cap, char *token)
{
    if (*count + 1 > *cap) {
        char **next;
        size_t new_cap = *cap == 0 ? 8 : *cap * 2;

        next = (char **)realloc(*items, new_cap * sizeof(**items));
        if (next == NULL) {
            return MK_ERR_OOM;
        }
        *items = next;
        *cap = new_cap;
    }
    (*items)[(*count)++] = token;
    return MK_OK;
}

static int mk_is_suffix_modifier(const char *p)
{
    return mk_is_modifier_letter_or_symbol(p);
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
                if (mk_push_token(&items, &count, &cap, current) != MK_OK) {
                    free(current);
                    free(normalized);
                    mk_free_items(items, count);
                    return MK_ERR_OOM;
                }
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
                if (mk_push_token(&items, &count, &cap, current) != MK_OK) {
                    free(current);
                    free(normalized);
                    mk_free_items(items, count);
                    return MK_ERR_OOM;
                }
                current = NULL;
                current_len = 0;
                current_cap = 0;
            }
            has_base = 0;
            after_tie = 0;
        }

        if (mk_is_chao_digit(p)) {
            const char *start = p;
            char *token;
            while (mk_is_chao_digit(p)) {
                p += mk_utf8_step(p);
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
            if (mk_push_token(&items, &count, &cap, token) != MK_OK) {
                free(token);
                free(current);
                free(normalized);
                mk_free_items(items, count);
                return MK_ERR_OOM;
            }
            continue;
        } else if (mk_is_boundary(p)) {
            char *token;
            n = mk_utf8_step(p);
            token = (char *)malloc(n + 1);
            if (token == NULL) {
                free(normalized);
                mk_free_items(items, count);
                return MK_ERR_OOM;
            }
            memcpy(token, p, n);
            token[n] = '\0';
            p += n;
            if (mk_push_token(&items, &count, &cap, token) != MK_OK) {
                free(token);
                free(current);
                free(normalized);
                mk_free_items(items, count);
                return MK_ERR_OOM;
            }
            continue;
        } else if (mk_has_prefix(p, "͡") || mk_has_prefix(p, "͜")) {
            n = mk_utf8_step(p);
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
            n = mk_utf8_step(p);
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
            n = mk_utf8_step(p);
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
                if (mk_push_token(&items, &count, &cap, current) != MK_OK) {
                    free(current);
                    free(normalized);
                    mk_free_items(items, count);
                    return MK_ERR_OOM;
                }
                current = NULL;
                current_len = 0;
                current_cap = 0;
            }
            n = mk_utf8_step(p);
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
        if (mk_push_token(&items, &count, &cap, current) != MK_OK) {
            free(current);
            free(normalized);
            mk_free_items(items, count);
            return MK_ERR_OOM;
        }
        current = NULL;
    }
    free(normalized);

    if (mk_string_list_adopt(items, count, out) != MK_OK) {
        mk_free_items(items, count);
        return MK_ERR_OOM;
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
