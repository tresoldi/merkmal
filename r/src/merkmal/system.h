#ifndef MK_SYSTEM_H
#define MK_SYSTEM_H

/* A system as the registry holds it: either a borrowed compiled-in model or
 * one parsed from caller-supplied text and owned by this struct. */

#include "merkmal.h"

#include "generated/builtin_data.h"

struct mk_system {
    /* Points at `owned` when `owns` is set, and at a compiled-in table
     * otherwise. Everything downstream reads only through this. */
    const mki_builtin_system *builtin;
    mki_builtin_system owned;
    /* The allocation `owned.name` borrows, and NULL unless `owns`. It is held
     * separately because mki_builtin_system::name is const -- it names a string
     * literal for a compiled system -- and the destructor should not have to
     * cast that away to free what this struct allocated. */
    char *owned_name;
    bool owns;
};

/* Whether a resolved segment is a tone. In a categorical system the resolver
 * marks a tone token `tonal-autosegment`. PHOIBLE lists tones as rows of its
 * own, valued `tone=+` and with no value on any segmental dimension; no other
 * row has `tone=+`. A tone and a segment are on different tiers. */
bool mki_view_is_tone(mk_feature_view view);

#endif
