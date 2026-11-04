/* Unicode canonical normalization. See unicode_norm.h. */

#include "unicode_norm.h"

#include "generated/unicode_data.h"

#include <stdlib.h>
#include <string.h>

/* A byte that is not part of well-formed UTF-8 rides through the code point
 * buffer under this tag and is written back as the same byte. No scalar value
 * reaches it, since those stop at U+10FFFF. */
#define MK_RAW_BYTE_TAG 0x80000000u

#define MK_HANGUL_S_BASE 0xAC00u
#define MK_HANGUL_L_BASE 0x1100u
#define MK_HANGUL_V_BASE 0x1161u
#define MK_HANGUL_T_BASE 0x11A7u
#define MK_HANGUL_L_COUNT 19u
#define MK_HANGUL_V_COUNT 21u
#define MK_HANGUL_T_COUNT 28u
#define MK_HANGUL_N_COUNT (MK_HANGUL_V_COUNT * MK_HANGUL_T_COUNT)
#define MK_HANGUL_S_COUNT (MK_HANGUL_L_COUNT * MK_HANGUL_N_COUNT)

typedef struct mk_code_points {
    unsigned int *items;
    size_t count;
    size_t cap;
} mk_code_points;

static mk_status mk_push(mk_code_points *buffer, unsigned int cp)
{
    if (buffer->count == buffer->cap) {
        size_t cap = buffer->cap == 0 ? 32 : buffer->cap * 2;
        unsigned int *next;

        if (cap > ((size_t)-1) / sizeof(*next)) {
            return MK_ERR_OOM;
        }
        next = (unsigned int *)realloc(buffer->items, cap * sizeof(*next));
        if (next == NULL) {
            return MK_ERR_OOM;
        }
        buffer->items = next;
        buffer->cap = cap;
    }
    buffer->items[buffer->count++] = cp;
    return MK_OK;
}

/* Decodes one well-formed UTF-8 scalar value, or returns 0 when the bytes at
 * `p` are not one: a stray continuation byte, a truncated or overlong
 * sequence, a surrogate, or a value past U+10FFFF. */
static size_t mk_decode(const unsigned char *p, unsigned int *out)
{
    unsigned int cp;
    size_t length;
    size_t i;

    if (p[0] < 0x80) {
        *out = p[0];
        return 1;
    }
    if (p[0] >= 0xC2 && p[0] <= 0xDF) {
        length = 2;
        cp = p[0] & 0x1Fu;
    } else if (p[0] >= 0xE0 && p[0] <= 0xEF) {
        length = 3;
        cp = p[0] & 0x0Fu;
    } else if (p[0] >= 0xF0 && p[0] <= 0xF4) {
        length = 4;
        cp = p[0] & 0x07u;
    } else {
        return 0;
    }
    for (i = 1; i < length; i++) {
        if ((p[i] & 0xC0) != 0x80) {
            return 0;
        }
        cp = (cp << 6) | (p[i] & 0x3Fu);
    }
    if ((length == 3 && cp < 0x800) ||
        (length == 4 && (cp < 0x10000 || cp > 0x10FFFF)) ||
        (cp >= 0xD800 && cp <= 0xDFFF)) {
        return 0;
    }
    *out = cp;
    return length;
}

static int mk_bisect(const unsigned int *keys, size_t count, unsigned int key, size_t *at)
{
    size_t low = 0;
    size_t high = count;

    while (low < high) {
        size_t mid = low + (high - low) / 2;
        if (keys[mid] < key) {
            low = mid + 1;
        } else {
            high = mid;
        }
    }
    *at = low;
    return low < count && keys[low] == key;
}

static unsigned int mk_combining_class(unsigned int cp)
{
    size_t at;

    if ((cp & MK_RAW_BYTE_TAG) != 0) {
        return 0;
    }
    if (mk_bisect(mki_unicode_tables.ccc_code_points, mki_unicode_tables.ccc_count, cp, &at)) {
        return mki_unicode_tables.ccc_classes[at];
    }
    return 0;
}

static mk_status mk_push_decomposed(mk_code_points *buffer, unsigned int cp)
{
    size_t at;

    if (cp >= MK_HANGUL_S_BASE && cp < MK_HANGUL_S_BASE + MK_HANGUL_S_COUNT) {
        unsigned int index = cp - MK_HANGUL_S_BASE;
        unsigned int trailing = index % MK_HANGUL_T_COUNT;
        mk_status status = mk_push(buffer, MK_HANGUL_L_BASE + index / MK_HANGUL_N_COUNT);

        if (status == MK_OK) {
            status = mk_push(
                buffer,
                MK_HANGUL_V_BASE + (index % MK_HANGUL_N_COUNT) / MK_HANGUL_T_COUNT);
        }
        if (status == MK_OK && trailing != 0) {
            status = mk_push(buffer, MK_HANGUL_T_BASE + trailing);
        }
        return status;
    }
    if ((cp & MK_RAW_BYTE_TAG) == 0 &&
        mk_bisect(
            mki_unicode_tables.decomposition_code_points,
            mki_unicode_tables.decomposition_count,
            cp,
            &at)) {
        const unsigned int *parts =
            mki_unicode_tables.decomposition_pool + mki_unicode_tables.decomposition_offsets[at];
        size_t count = mki_unicode_tables.decomposition_lengths[at];
        size_t i;

        for (i = 0; i < count; i++) {
            mk_status status = mk_push(buffer, parts[i]);
            if (status != MK_OK) {
                return status;
            }
        }
        return MK_OK;
    }
    return mk_push(buffer, cp);
}

/* Canonical ordering: a stable sort of each run of non-starters by class. The
 * runs are a few marks long, so insertion sort is the right tool. */
static void mk_reorder(mk_code_points *buffer)
{
    size_t i;

    for (i = 1; i < buffer->count; i++) {
        unsigned int cp = buffer->items[i];
        unsigned int cls = mk_combining_class(cp);
        size_t j = i;

        if (cls == 0) {
            continue;
        }
        while (j > 0) {
            unsigned int before = mk_combining_class(buffer->items[j - 1]);
            if (before == 0 || before <= cls) {
                break;
            }
            buffer->items[j] = buffer->items[j - 1];
            j--;
        }
        buffer->items[j] = cp;
    }
}

static mk_status mk_decompose_text(const char *utf8_in, mk_code_points *buffer)
{
    const unsigned char *p = (const unsigned char *)utf8_in;

    while (*p != '\0') {
        unsigned int cp = 0;
        size_t length = mk_decode(p, &cp);
        mk_status status;

        if (length == 0) {
            status = mk_push(buffer, MK_RAW_BYTE_TAG | *p);
            p++;
        } else {
            status = mk_push_decomposed(buffer, cp);
            p += length;
        }
        if (status != MK_OK) {
            return status;
        }
    }
    mk_reorder(buffer);
    return MK_OK;
}

/* The primary composite of a pair, or 0 when there is none. */
static unsigned int mk_compose_pair(unsigned int first, unsigned int second)
{
    size_t at;

    if ((first & MK_RAW_BYTE_TAG) != 0 || (second & MK_RAW_BYTE_TAG) != 0) {
        return 0;
    }
    if (first >= MK_HANGUL_L_BASE && first < MK_HANGUL_L_BASE + MK_HANGUL_L_COUNT &&
        second >= MK_HANGUL_V_BASE && second < MK_HANGUL_V_BASE + MK_HANGUL_V_COUNT) {
        return MK_HANGUL_S_BASE +
            ((first - MK_HANGUL_L_BASE) * MK_HANGUL_V_COUNT + (second - MK_HANGUL_V_BASE)) *
            MK_HANGUL_T_COUNT;
    }
    if (first >= MK_HANGUL_S_BASE && first < MK_HANGUL_S_BASE + MK_HANGUL_S_COUNT &&
        (first - MK_HANGUL_S_BASE) % MK_HANGUL_T_COUNT == 0 &&
        second > MK_HANGUL_T_BASE && second < MK_HANGUL_T_BASE + MK_HANGUL_T_COUNT) {
        return first + (second - MK_HANGUL_T_BASE);
    }
    mk_bisect(
        mki_unicode_tables.composition_first,
        mki_unicode_tables.composition_count,
        first,
        &at);
    for (; at < mki_unicode_tables.composition_count &&
           mki_unicode_tables.composition_first[at] == first;
         at++) {
        if (mki_unicode_tables.composition_second[at] == second) {
            return mki_unicode_tables.composition_result[at];
        }
    }
    return 0;
}

/* Canonical composition, as in UAX #15: each character composes with the last
 * starter unless a character of equal or higher class stands between them. */
static void mk_compose(mk_code_points *buffer)
{
    size_t starter = 0;
    size_t write = 1;
    size_t read;
    unsigned int last_class;

    if (buffer->count == 0) {
        return;
    }
    last_class = mk_combining_class(buffer->items[0]);
    if (last_class != 0) {
        last_class = 256; /* no starter yet, so nothing may compose */
    }
    for (read = 1; read < buffer->count; read++) {
        unsigned int cp = buffer->items[read];
        unsigned int cls = mk_combining_class(cp);
        unsigned int composite = mk_compose_pair(buffer->items[starter], cp);

        if (composite != 0 && (last_class < cls || last_class == 0)) {
            buffer->items[starter] = composite;
            continue;
        }
        if (cls == 0) {
            starter = write;
        }
        last_class = cls;
        buffer->items[write++] = cp;
    }
    buffer->count = write;
}

static mk_status mk_encode(const mk_code_points *buffer, char **utf8_out)
{
    size_t bytes = 1;
    size_t i;
    char *out;
    char *w;

    for (i = 0; i < buffer->count; i++) {
        unsigned int cp = buffer->items[i];
        bytes += (cp & MK_RAW_BYTE_TAG) ? 1 : cp < 0x80 ? 1 : cp < 0x800 ? 2 : cp < 0x10000 ? 3 : 4;
    }
    out = (char *)malloc(bytes);
    if (out == NULL) {
        return MK_ERR_OOM;
    }
    w = out;
    for (i = 0; i < buffer->count; i++) {
        unsigned int cp = buffer->items[i];

        if ((cp & MK_RAW_BYTE_TAG) != 0) {
            *w++ = (char)(unsigned char)(cp & 0xFFu);
        } else if (cp < 0x80) {
            *w++ = (char)cp;
        } else if (cp < 0x800) {
            *w++ = (char)(unsigned char)(0xC0u | (cp >> 6));
            *w++ = (char)(unsigned char)(0x80u | (cp & 0x3Fu));
        } else if (cp < 0x10000) {
            *w++ = (char)(unsigned char)(0xE0u | (cp >> 12));
            *w++ = (char)(unsigned char)(0x80u | ((cp >> 6) & 0x3Fu));
            *w++ = (char)(unsigned char)(0x80u | (cp & 0x3Fu));
        } else {
            *w++ = (char)(unsigned char)(0xF0u | (cp >> 18));
            *w++ = (char)(unsigned char)(0x80u | ((cp >> 12) & 0x3Fu));
            *w++ = (char)(unsigned char)(0x80u | ((cp >> 6) & 0x3Fu));
            *w++ = (char)(unsigned char)(0x80u | (cp & 0x3Fu));
        }
    }
    *w = '\0';
    *utf8_out = out;
    return MK_OK;
}

static mk_status mk_normalize(const char *utf8_in, int compose, char **utf8_out)
{
    mk_code_points buffer = { NULL, 0, 0 };
    mk_status status;

    if (utf8_in == NULL || utf8_out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *utf8_out = NULL;
    status = mk_decompose_text(utf8_in, &buffer);
    if (status == MK_OK) {
        if (compose) {
            mk_compose(&buffer);
        }
        status = mk_encode(&buffer, utf8_out);
    }
    free(buffer.items);
    return status;
}

mk_status mki_unicode_nfd(const char *utf8_in, char **utf8_out)
{
    return mk_normalize(utf8_in, 0, utf8_out);
}

mk_status mki_unicode_nfc(const char *utf8_in, char **utf8_out)
{
    return mk_normalize(utf8_in, 1, utf8_out);
}
