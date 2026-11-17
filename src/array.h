#ifndef MK_ARRAY_H
#define MK_ARRAY_H

/* Growing a heap array by doubling, with the size arithmetic checked.
 *
 * Every growable buffer in the library -- token lists, feature lists, parsed
 * model rows, code-point buffers, text being built -- used to spell out its own
 * `cap == 0 ? 8 : cap * 2` and `realloc(p, cap * sizeof *p)`, and only one of
 * them checked that the multiplication fit. This is that code once, checked. */

#include <stddef.h>

/* Returns an array with room for at least `count + extra` elements of
 * `elem_size` bytes, and updates *cap to the new capacity.
 *
 * `items` is the current array (NULL when *cap is 0) holding `count` elements.
 * If it already has room it is returned unchanged. Otherwise it is reallocated
 * to the first doubling of *cap (or of `initial`, for an empty array) that
 * fits, and the elements are kept.
 *
 * Returns NULL on allocation failure or if the size does not fit in a size_t.
 * In that case `items` is still valid, still owned by the caller, and *cap is
 * unchanged, so the caller frees what it has exactly as on any other failure.
 *
 * Call as `next = mki_grow_array(items, &cap, count, 1, sizeof *items, 8);` and
 * assign `items = next` only after the NULL check. The pointer is returned,
 * rather than updated through a `void **`, because a `char ***` or a
 * `struct row **` is not a `void **` and casting one to it is not valid C.
 *
 * `extra` and `elem_size` must be non-zero. */
void *mki_grow_array(
    void *items,
    size_t *cap,
    size_t count,
    size_t extra,
    size_t elem_size,
    size_t initial
);

#endif
