#include "inventory.h"

#include "strings.h"

#include <string.h>

void mki_inventory_row(
    const mk_builtin_system *system,
    size_t index,
    const char **scratch,
    mk_entry_view *out
)
{
    size_t count;
    const unsigned short *ids;
    size_t i;

    /* The two casts here and in mki_inventory_find add const rather than remove
     * it: a runtime model owns its rows as char **, and a reader gets the
     * borrowed view. C will not widen char ** to const char *const * on its
     * own, so the conversion is spelled out. */
    if (system->entries != NULL) {
        out->grapheme = system->entries[index].grapheme;
        out->features = (const char *const *)system->entries[index].features;
        out->feature_count = system->entries[index].feature_count;
        return;
    }

    count = system->entry_feature_n[index];
    ids = system->feature_ids + system->entry_feature_at[index];
    for (i = 0; i < count; i++) {
        scratch[i] = mki_feature_name(ids[i]);
    }
    out->grapheme = mki_pool_string(system->entry_graphemes[index]);
    out->features = scratch;
    out->feature_count = count;
}

int mki_inventory_find(
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
            if (mki_streq(system->entries[i].grapheme, key)) {
                out->grapheme = system->entries[i].grapheme;
                out->features = (const char *const *)system->entries[i].features;
                out->feature_count = system->entries[i].feature_count;
                return 1;
            }
        }
        return 0;
    }

    /* Compiled inventories are emitted sorted by the grapheme's UTF-8 bytes,
     * which is the order strcmp imposes, so this is a binary search. It was a
     * walk over every row: a miss in phoible's 3,142 rows cost 25.9 us, and a
     * resolution performs up to three lookups while longest-match tokenization
     * performs several resolutions per token. */
    {
        size_t low = 0;
        size_t high = system->entry_count;

        while (low < high) {
            size_t mid = low + (high - low) / 2;
            int order = strcmp(mki_pool_string(system->entry_graphemes[mid]), key);

            if (order == 0) {
                mki_inventory_row(system, mid, scratch, out);
                return 1;
            }
            if (order < 0) {
                low = mid + 1;
            } else {
                high = mid;
            }
        }
    }
    return 0;
}
