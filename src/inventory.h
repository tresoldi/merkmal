#ifndef MK_INVENTORY_H
#define MK_INVENTORY_H

/* Reading inventory rows, whichever storage the system uses.
 *
 * A compiled-in inventory stores rows as pool offsets and feature ids; a model
 * parsed at runtime stores them as pointers. Everything above this module sees
 * one shape, mk_entry_view, and does not care which it came from. */

#include "generated/builtin_data.h"

#include <stddef.h>

/* One inventory row, as borrowed strings.
 *
 * `grapheme` always points into compiled or registry-owned storage and is
 * valid as long as the registry is. `features` points either at
 * registry-owned storage or at the caller's scratch array -- see
 * mk_inventory_find. */
typedef struct mk_entry_view {
    const char *grapheme;
    const char *const *features;
    size_t feature_count;
} mk_entry_view;

/* Finds the row whose grapheme equals `key`, returning 1 on a hit.
 *
 * `scratch` must have room for MK_MAX_ENTRY_FEATURES pointers. For a
 * compiled-in inventory the returned `features` aliases it, so it must outlive
 * every use of `out` -- the resolver satisfies this by keeping the array
 * inside the mk_resolution it is filling. It is untouched, and unaliased, for
 * a runtime model.
 *
 * The strings themselves are never in the scratch: only the pointers to them
 * are, so the row's text stays valid for the life of the registry either way. */
int mk_inventory_find(
    const mk_builtin_system *system,
    const char *key,
    const char **scratch,
    mk_entry_view *out
);

/* Fills `out` with row `index`, which must be below system->entry_count. Same
 * scratch contract as mk_inventory_find. Lets a caller walk an inventory
 * without knowing its storage; the tests use it to check every compiled row. */
void mk_inventory_row(
    const mk_builtin_system *system,
    size_t index,
    const char **scratch,
    mk_entry_view *out
);

#endif
