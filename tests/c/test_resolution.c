/* Tests the resolution seam directly.
 *
 * Resolution used to be observable only as a boolean from mk_system_is_segment
 * or a feature set from mk_system_grapheme_features, so a test could say that
 * a spelling was accepted but not how — whether it came from the inventory,
 * from tie-bar stripping, or from one of four synthesizers. These cases assert
 * the path, so a change that quietly moves a segment from one construction to
 * another fails here rather than passing unnoticed. */

#include "inventory.h"
#include "resolver.h"

#include <stdio.h>
#include <string.h>

typedef struct resolution_case {
    const char *system;
    const char *grapheme;
    mk_status status;
    mk_resolution_path path;
    /* A feature the resolution must carry, or NULL to skip the check. */
    const char *feature;
} resolution_case;

static const resolution_case cases[] = {
    /* Inventory rows, matched as written. */
    { "descriptive", "p", MK_OK, MK_RESOLVED_INVENTORY, "bilabial" },
    { "descriptive", "a", MK_OK, MK_RESOLVED_INVENTORY, "vowel" },
    { "phoible", "b", MK_OK, MK_RESOLVED_INVENTORY, NULL },

    /* The descriptive inventory lists the untied affricate, so it is a plain
     * lookup there and only the tied spelling needs stripping. */
    { "descriptive", "tʃ", MK_OK, MK_RESOLVED_INVENTORY, NULL },
    { "descriptive", "t͡ʃ", MK_OK, MK_RESOLVED_TIE_STRIPPED, NULL },
    { "descriptive", "d͡ʒ", MK_OK, MK_RESOLVED_TIE_STRIPPED, NULL },

    /* PHOIBLE lists the retracted form instead, so both spellings reach it
     * only after the retraction mark is inserted. This is the one bundled
     * system that exercises that path; if the inventories ever gain an untied
     * row, this case is what will say so. */
    { "phoible", "tʃ", MK_OK, MK_RESOLVED_AFFRICATE_RETRACTED, NULL },
    { "phoible", "d͡ʒ", MK_OK, MK_RESOLVED_AFFRICATE_RETRACTED, NULL },

    /* Synthesized from a base plus diacritic and tone marks. */
    { "descriptive", "pʰ", MK_OK, MK_RESOLVED_DIACRITICS, "aspirated" },
    { "descriptive", "aː", MK_OK, MK_RESOLVED_DIACRITICS, "long" },
    { "descriptive", "ã", MK_OK, MK_RESOLVED_DIACRITICS, "nasalized" },
    { "descriptive", "a⁵⁵", MK_OK, MK_RESOLVED_DIACRITICS, "tone-present" },
    { "descriptive", "ŋ̀", MK_OK, MK_RESOLVED_DIACRITICS, "syllabic" },
    /* A prefixed nasal is a diacritic, not a cluster: the mark carries the
     * feature and the base resolves on its own. */
    { "descriptive", "ᵐb", MK_OK, MK_RESOLVED_DIACRITICS, "pre-nasalized" },
    { "descriptive", "ⁿdʳ", MK_OK, MK_RESOLVED_DIACRITICS, "rhotacized" },
    /* A complex base carrying a diacritic resolves through the diacritic path,
     * which resolves the base recursively. */
    { "descriptive", "tʂʰ", MK_OK, MK_RESOLVED_DIACRITICS, "aspirated" },

    /* Synthesized vowel clusters. */
    { "descriptive", "ai", MK_OK, MK_RESOLVED_VOWEL_CLUSTER, "diphthong" },
    { "descriptive", "aːi", MK_OK, MK_RESOLVED_VOWEL_CLUSTER, "diphthong" },
    { "descriptive", "əi³¹", MK_OK, MK_RESOLVED_VOWEL_CLUSTER, "tone-present" },
    { "descriptive", "ɛï³³", MK_OK, MK_RESOLVED_VOWEL_CLUSTER, "diphthong" },

    /* Synthesized complex segments written as two letters. */
    { "descriptive", "kp", MK_OK, MK_RESOLVED_COMPLEX, NULL },
    { "descriptive", "ɡb", MK_OK, MK_RESOLVED_COMPLEX, NULL },
    { "descriptive", "kɣ", MK_OK, MK_RESOLVED_COMPLEX, NULL },
    { "descriptive", "tʂ", MK_OK, MK_RESOLVED_COMPLEX, NULL },

    /* Synthesized consonant clusters: a bare nasal plus a stop. */
    { "descriptive", "mb", MK_OK, MK_RESOLVED_CONSONANT_CLUSTER, NULL },
    { "descriptive", "nd", MK_OK, MK_RESOLVED_CONSONANT_CLUSTER, NULL },
    { "descriptive", "ŋg", MK_OK, MK_RESOLVED_CONSONANT_CLUSTER, NULL },

    /* Rejections. Unknown means no path recognized the input; parse means a
     * path recognized the shape and rejected the content. */
    { "descriptive", "not-ipa", MK_ERR_UNKNOWN_GRAPHEME, MK_RESOLVED_NONE, NULL },
    { "descriptive", "³¹", MK_ERR_UNKNOWN_GRAPHEME, MK_RESOLVED_NONE, NULL },
    { "descriptive", "a¹²³⁴", MK_ERR_PARSE, MK_RESOLVED_NONE, NULL },
    /* A breve plus a length mark puts one segment at two points of the
     * duration scale. Both cluster kinds report it the same way: parse, not
     * unknown, because the shape was recognized and the content refused. The
     * two synthesizers disagreed about this before they shared a scan. */
    { "descriptive", "aĭː", MK_ERR_PARSE, MK_RESOLVED_NONE, NULL },
    { "descriptive", "mb̆ː", MK_ERR_PARSE, MK_RESOLVED_NONE, NULL },
    /* No dimension a tone modifier can move, so tone is refused rather than
     * silently dropped. */
    { "phoible", "a⁵⁵", MK_ERR_UNSUPPORTED_MODEL, MK_RESOLVED_NONE, NULL }
};

static int has_feature(const mk_resolution *resolution, const char *feature)
{
    size_t i;

    for (i = 0; i < resolution->feature_count; i++) {
        if (strcmp(resolution->features[i], feature) == 0) {
            return 1;
        }
    }
    return 0;
}

static int run_case(const mk_registry *registry, const resolution_case *c)
{
    const mk_system *system = NULL;
    mk_resolution resolution;
    mk_status status;
    int failed = 0;

    if (mk_registry_get_system(registry, c->system, &system) != MK_OK) {
        fprintf(stderr, "%s/%s: no such system\n", c->system, c->grapheme);
        return 1;
    }

    status = mk_resolve(system, c->grapheme, &resolution);
    if (status != c->status) {
        fprintf(stderr, "%s/%s: expected status %d, got %d\n",
            c->system, c->grapheme, c->status, status);
        mk_resolution_clear(&resolution);
        return 1;
    }
    if (resolution.path != c->path) {
        fprintf(stderr, "%s/%s: expected path %s, got %s\n",
            c->system, c->grapheme,
            mk_resolution_path_name(c->path),
            mk_resolution_path_name(resolution.path));
        failed = 1;
    }
    if (status == MK_OK) {
        /* The ownership rule in resolver.h, checked rather than assumed. */
        int borrowed = c->path == MK_RESOLVED_INVENTORY ||
            c->path == MK_RESOLVED_TIE_STRIPPED ||
            c->path == MK_RESOLVED_AFFRICATE_RETRACTED;
        if (borrowed) {
            if (resolution.owned_features != NULL || resolution.owned_grapheme != NULL) {
                fprintf(stderr, "%s/%s: inventory path should own nothing\n",
                    c->system, c->grapheme);
                failed = 1;
            }
        } else {
            if (resolution.features != (const char *const *)resolution.owned_features ||
                resolution.grapheme != resolution.owned_grapheme) {
                fprintf(stderr, "%s/%s: synthesized path must alias its owned storage\n",
                    c->system, c->grapheme);
                failed = 1;
            }
        }
        if (resolution.feature_count == 0) {
            fprintf(stderr, "%s/%s: resolved with no features\n", c->system, c->grapheme);
            failed = 1;
        }
        if (c->feature != NULL && !has_feature(&resolution, c->feature)) {
            fprintf(stderr, "%s/%s: expected feature %s\n",
                c->system, c->grapheme, c->feature);
            failed = 1;
        }
    }
    mk_resolution_clear(&resolution);
    return failed;
}

/* mk_resolution_clear must be safe on a zeroed struct and on one already
 * cleared, because every caller memsets before use and clears on every exit. */
static int check_clear_is_total(void)
{
    mk_resolution resolution;

    memset(&resolution, 0, sizeof(resolution));
    mk_resolution_clear(&resolution);
    mk_resolution_clear(&resolution);
    mk_resolution_clear(NULL);
    if (resolution.path != MK_RESOLVED_NONE || resolution.features != NULL) {
        fprintf(stderr, "clear: expected a zeroed resolution\n");
        return 1;
    }
    if (strcmp(mk_resolution_path_name(MK_RESOLVED_NONE), "none") != 0) {
        fprintf(stderr, "path name: expected none\n");
        return 1;
    }
    return 0;
}

static int check_invalid_arguments(void)
{
    mk_resolution resolution;
    int failed = 0;

    if (mk_resolve(NULL, "p", &resolution) != MK_ERR_INVALID_ARGUMENT) {
        fprintf(stderr, "resolve: expected invalid argument for a NULL system\n");
        failed = 1;
    }
    return failed;
}

/* Every compiled row, through the interned storage.
 *
 * The golden fixtures cover the graphemes they name; this covers all 9,728
 * rows, which is what makes a bad pool offset or a truncated feature run show
 * up as a failure rather than as a wrong answer for some segment nobody
 * sampled. Each row must also resolve back to itself: that exercises
 * mk_inventory_find against the same data mk_inventory_row reports. */
static int check_every_compiled_row(void)
{
    const char *scratch[MK_MAX_ENTRY_FEATURES];
    size_t s;
    size_t i;
    size_t j;
    size_t rows = 0;
    int failed = 0;

    for (s = 0; s < mk_builtin_system_count; s++) {
        const mk_builtin_system *system = &mk_builtin_systems[s];

        for (i = 0; i < system->entry_count; i++) {
            mk_entry_view row;
            mk_entry_view found;
            const char *found_scratch[MK_MAX_ENTRY_FEATURES];

            mk_inventory_row(system, i, scratch, &row);
            rows++;

            if (row.grapheme == NULL || row.grapheme[0] == '\0') {
                fprintf(stderr, "%s row %zu: empty grapheme\n", system->name, i);
                failed = 1;
                continue;
            }
            if (row.feature_count == 0 || row.feature_count > MK_MAX_ENTRY_FEATURES) {
                fprintf(stderr, "%s row %zu (%s): feature count %zu out of range\n",
                        system->name, i, row.grapheme, row.feature_count);
                failed = 1;
                continue;
            }
            for (j = 0; j < row.feature_count; j++) {
                if (row.features[j] == NULL || row.features[j][0] == '\0') {
                    fprintf(stderr, "%s row %zu (%s): empty feature at %zu\n",
                            system->name, i, row.grapheme, j);
                    failed = 1;
                }
            }

            if (!mk_inventory_find(system, row.grapheme, found_scratch, &found)) {
                fprintf(stderr, "%s row %zu (%s): does not find itself\n",
                        system->name, i, row.grapheme);
                failed = 1;
                continue;
            }
            if (found.feature_count != row.feature_count) {
                fprintf(stderr, "%s (%s): found %zu features, row has %zu\n",
                        system->name, row.grapheme, found.feature_count, row.feature_count);
                failed = 1;
            }
        }
    }

    if (rows == 0) {
        fprintf(stderr, "no compiled rows were walked\n");
        failed = 1;
    }
    return failed;
}

/* Every feature id names a distinct, non-empty string. A pool offset that
 * lands mid-string still yields a plausible-looking C string, so identity is
 * checked rather than just non-emptiness. */
static int check_feature_name_table(void)
{
    size_t i;
    int failed = 0;

    for (i = 0; i < mk_feature_name_count; i++) {
        const char *name = mk_feature_name((unsigned short)i);
        if (name == NULL || name[0] == '\0') {
            fprintf(stderr, "feature id %zu has no name\n", i);
            failed = 1;
            continue;
        }
        if (i > 0 && strcmp(mk_feature_name((unsigned short)(i - 1)), name) >= 0) {
            fprintf(stderr, "feature ids are not in sorted order at %zu (%s)\n", i, name);
            failed = 1;
        }
    }
    return failed;
}

int main(void)
{
    mk_registry *registry = NULL;
    size_t i;
    int failed = 0;

    if (mk_registry_new_builtin(&registry) != MK_OK) {
        fprintf(stderr, "could not build the registry\n");
        return 1;
    }

    for (i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
        failed |= run_case(registry, &cases[i]);
    }
    failed |= check_clear_is_total();
    failed |= check_invalid_arguments();
    failed |= check_every_compiled_row();
    failed |= check_feature_name_table();

    mk_registry_free(registry);
    return failed ? 1 : 0;
}
