#ifndef MK_STRING_LIST_H
#define MK_STRING_LIST_H

/* The library's only collection type. Feature sets are string lists whose
 * order carries no meaning. */

#include "merkmal.h"

#include <stddef.h>

struct mk_string_list {
    char **items;
    size_t count;
};

/* Copies `items` and every string in it; the caller keeps its own.
 * MK_ERR_INVALID_ARGUMENT when `out` is NULL or `items` is NULL with a
 * non-zero count; MK_ERR_OOM leaves nothing allocated. *out is NULL on any
 * failure. */
mk_status mki_string_list_from_borrowed(
    const char *const *items,
    size_t count,
    mk_string_list **out
);

/* Takes ownership of `items` and of every string in it, on MK_OK only: on
 * MK_ERR_INVALID_ARGUMENT (as for mki_string_list_from_borrowed) or MK_ERR_OOM
 * the caller still owns them and frees them as on any other failure. For a
 * caller that has already built an owned array, so it need not copy every
 * string and free the original. */
mk_status mki_string_list_adopt(
    char **items,
    size_t count,
    mk_string_list **out
);

#endif
