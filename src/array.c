#include "array.h"

#include <stdint.h>
#include <stdlib.h>

void *mki_grow_array(
    void *items,
    size_t *cap,
    size_t count,
    size_t extra,
    size_t elem_size,
    size_t initial
)
{
    size_t needed;
    size_t new_cap;
    void *next;

    if (cap == NULL || extra == 0 || elem_size == 0 || count > SIZE_MAX - extra) {
        return NULL;
    }
    needed = count + extra;
    if (needed <= *cap) {
        return items;
    }

    new_cap = *cap == 0 ? (initial == 0 ? 1 : initial) : *cap;
    while (new_cap < needed) {
        if (new_cap > SIZE_MAX / 2) {
            /* Doubling would overflow; the exact need is the last resort. */
            new_cap = needed;
            break;
        }
        new_cap *= 2;
    }
    if (new_cap > SIZE_MAX / elem_size) {
        return NULL;
    }

    next = realloc(items, new_cap * elem_size);
    if (next == NULL) {
        return NULL;
    }
    *cap = new_cap;
    return next;
}
