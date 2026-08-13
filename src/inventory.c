#include "inventory.h"

#include "strings.h"

void mk_inventory_row(
    const mk_builtin_system *system,
    size_t index,
    const char **scratch,
    mk_entry_view *out
)
{
    size_t count;
    const unsigned short *ids;
    size_t i;

    if (system->entries != NULL) {
        out->grapheme = system->entries[index].grapheme;
        out->features = system->entries[index].features;
        out->feature_count = system->entries[index].feature_count;
        return;
    }

    count = system->entry_feature_n[index];
    ids = system->feature_ids + system->entry_feature_at[index];
    for (i = 0; i < count; i++) {
        scratch[i] = mk_feature_name(ids[i]);
    }
    out->grapheme = mk_pool_string(system->entry_graphemes[index]);
    out->features = scratch;
    out->feature_count = count;
}

int mk_inventory_find(
    const mk_builtin_system *system,
    const char *key,
    const char **scratch,
    mk_entry_view *out
)
{
    size_t i;

    if (system == NULL || key == NULL || out == NULL) {
        return 0;
    }

    if (system->entries != NULL) {
        for (i = 0; i < system->entry_count; i++) {
            if (mk_streq(system->entries[i].grapheme, key)) {
                out->grapheme = system->entries[i].grapheme;
                out->features = system->entries[i].features;
                out->feature_count = system->entries[i].feature_count;
                return 1;
            }
        }
        return 0;
    }

    for (i = 0; i < system->entry_count; i++) {
        if (mk_streq(mk_pool_string(system->entry_graphemes[i]), key)) {
            mk_inventory_row(system, i, scratch, out);
            return 1;
        }
    }
    return 0;
}
