#ifndef MK_GOLDEN_SUPPORT_H
#define MK_GOLDEN_SUPPORT_H

#include <stddef.h>

/* Shared by every fixture-replaying test. The TSV reader was copied verbatim
 * into three of them. */

/* Reads one tab-delimited field into `out`, advancing `*cursor` past it and
 * past the tab. Returns non-zero when the field was non-empty. */
int mk_read_field(char **cursor, char *out, size_t out_size);

/* A named feature set, the unit the geometry fixtures are keyed by.
 *
 * These live in tests/golden/geometry_cases.tsv rather than as C literals in
 * a test, so the fixtures can be produced by something other than the binary
 * that replays them, and so adding a case is a data change. */
#define MK_GOLDEN_MAX_CASES 128
#define MK_GOLDEN_MAX_FEATURES 32

typedef struct mk_golden_case {
    char name[64];
    char *features[MK_GOLDEN_MAX_FEATURES];
    const char *feature_view[MK_GOLDEN_MAX_FEATURES];
    size_t feature_count;
} mk_golden_case;

typedef struct mk_golden_cases {
    mk_golden_case items[MK_GOLDEN_MAX_CASES];
    size_t count;
} mk_golden_cases;

/* Loads the case table. Returns 0 on success, non-zero after reporting to
 * stderr. `path` is the full path to geometry_cases.tsv. */
int mk_golden_cases_load(mk_golden_cases *out, const char *path);

void mk_golden_cases_free(mk_golden_cases *cases);

const mk_golden_case *mk_golden_cases_find(const mk_golden_cases *cases, const char *name);

#endif
