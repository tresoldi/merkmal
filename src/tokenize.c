/* Orthographic tokenization: a new token starts at each new base code point
 * unless a tie bar joins it to the previous one.
 *
 * The whole interface is public, so there is no tokenize.h; see merkmal.h for
 * the policy this implements and for where it deliberately disagrees with a
 * system's own inventory. */

#include "merkmal.h"

#include "array.h"
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
    char **next = (char **)mki_grow_array(*items, cap, *count, 1, sizeof(**items), 8);

    if (next == NULL) {
        return MK_ERR_OOM;
    }
    *items = next;
    (*items)[(*count)++] = token;
    return MK_OK;
}

static bool mk_is_suffix_modifier(const char *p)
{
    return mki_is_modifier_letter_or_symbol(p);
}

/* The tokens finished so far and the one being built.
 *
 * `current` is owned here until it is pushed onto `items`; everything in
 * `items` is owned here until mki_string_list_adopt takes the array. So one
 * cleanup at the end of mk_segment_ipa frees whatever exists on any path.
 *
 * `has_base` says the current token already holds a base code point, so the
 * next base starts a new token; `after_tie` says a tie bar was just appended,
 * so the next base joins this one instead. */
typedef struct mk_tokenizer {
    char **items;
    size_t count;
    size_t cap;
    char *current;
    size_t current_len;
    size_t current_cap;
    bool has_base;
    bool after_tie;
} mk_tokenizer;

/* Finishes the token being built, if there is one. On failure `current` stays
 * owned by the tokenizer. */
static mk_status mk_end_token(mk_tokenizer *t)
{
    if (t->current_len == 0) {
        return MK_OK;
    }
    if (mk_push_token(&t->items, &t->count, &t->cap, t->current) != MK_OK) {
        return MK_ERR_OOM;
    }
    t->current = NULL;
    t->current_len = 0;
    t->current_cap = 0;
    return MK_OK;
}

/* Finishes the current token and forgets the base/tie context: a space, a tone
 * run or a boundary separates what comes before from what comes after. */
static mk_status mk_break(mk_tokenizer *t)
{
    t->has_base = false;
    t->after_tie = false;
    return mk_end_token(t);
}

/* Pushes `n` bytes at `start` as a token of their own. */
static mk_status mk_push_copy(mk_tokenizer *t, const char *start, size_t n)
{
    char *token = (char *)malloc(n + 1);

    if (token == NULL) {
        return MK_ERR_OOM;
    }
    memcpy(token, start, n);
    token[n] = '\0';
    if (mk_push_token(&t->items, &t->count, &t->cap, token) != MK_OK) {
        free(token);
        return MK_ERR_OOM;
    }
    return MK_OK;
}

/* Appends one code point of `n` bytes (at most four) to the current token. */
static mk_status mk_append_code_point(mk_tokenizer *t, const char *p, size_t n)
{
    char one[5];

    memcpy(one, p, n);
    one[n] = '\0';
    return mki_append_text(&t->current, &t->current_len, &t->current_cap, one);
}

mk_status mk_segment_ipa(
    const char *utf8_in,
    mk_string_list **out
)
{
    mk_tokenizer t = {NULL, 0, 0, NULL, 0, 0, false, false};
    char *normalized = NULL;
    const char *p;
    mk_status status;

    if (utf8_in == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;

    status = mki_segmentation_nfd(utf8_in, &normalized);
    if (status != MK_OK) {
        return status;
    }

    p = normalized;
    while (*p != '\0') {
        size_t n;

        if (*p == ' ') {
            /* A space separates tokens and is not one. */
            status = mk_break(&t);
            p++;
        } else if (mki_is_chao_digit(p)) {
            /* A run of Chao digits is one token. */
            const char *start = p;

            status = mk_break(&t);
            if (status != MK_OK) {
                goto cleanup;
            }
            while (mki_is_chao_digit(p)) {
                p += mki_utf8_step(p);
            }
            status = mk_push_copy(&t, start, (size_t)(p - start));
        } else if (mki_is_boundary(p)) {
            /* A boundary marker is a token of its own. */
            status = mk_break(&t);
            if (status != MK_OK) {
                goto cleanup;
            }
            n = mki_utf8_step(p);
            status = mk_push_copy(&t, p, n);
            p += n;
        } else if (mki_has_prefix(p, "͡") || mki_has_prefix(p, "͜")) {
            /* A tie bar joins the next base to this token. */
            n = mki_utf8_step(p);
            status = mk_append_code_point(&t, p, n);
            t.after_tie = true;
            p += n;
        } else if (mki_is_combining_mark(p) || mk_is_suffix_modifier(p)) {
            /* Diacritics and modifier letters attach to the current token. */
            n = mki_utf8_step(p);
            status = mk_append_code_point(&t, p, n);
            p += n;
        } else {
            /* A base code point starts a new token unless a tie joins it. */
            if (t.has_base && !t.after_tie) {
                status = mk_end_token(&t);
                if (status != MK_OK) {
                    goto cleanup;
                }
            }
            n = mki_utf8_step(p);
            status = mk_append_code_point(&t, p, n);
            t.has_base = true;
            t.after_tie = false;
            p += n;
        }
        if (status != MK_OK) {
            goto cleanup;
        }
    }

    status = mk_end_token(&t);
    if (status != MK_OK) {
        goto cleanup;
    }
    if (mki_string_list_adopt(t.items, t.count, out) != MK_OK) {
        status = MK_ERR_OOM;
        goto cleanup;
    }
    t.items = NULL;
    t.count = 0;

cleanup:
    free(t.current);
    free(normalized);
    mki_free_items(t.items, t.count);
    return status;
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
