#ifndef MK_SYSTEM_H
#define MK_SYSTEM_H

/* A system as the registry holds it: either a borrowed compiled-in model or
 * one parsed from caller-supplied text and owned by this struct. */

#include "generated/builtin_data.h"

struct mk_system {
    /* Points at `owned` when `owns` is set, and at a compiled-in table
     * otherwise. Everything downstream reads only through this. */
    const mk_builtin_system *builtin;
    mk_builtin_system owned;
    /* The allocation `owned.name` borrows, and NULL unless `owns`. It is held
     * separately because mk_builtin_system::name is const -- it names a string
     * literal for a compiled system -- and the destructor should not have to
     * cast that away to free what this struct allocated. */
    char *owned_name;
    int owns;
};

#endif
