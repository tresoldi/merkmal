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

/* Copies `items` and every string in it. */
mk_status mk_string_list_from_borrowed(
    const char *const *items,
    size_t count,
    mk_string_list **out
);

/* Takes ownership of `items` and of every string in it. Callers that have
 * already built an owned array hand it over instead of copying it and freeing
 * the original -- which is what the tokenizer used to do, and why two places
 * assembled the struct by hand rather than going through a constructor. */
mk_status mk_string_list_adopt(
    char **items,
    size_t count,
    mk_string_list **out
);

#endif
