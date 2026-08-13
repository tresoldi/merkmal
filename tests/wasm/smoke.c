#include "merkmal.h"

#include <stdio.h>
#include <string.h>

static int fail_status(mk_status status, const char *label)
{
    fprintf(stderr, "%s: %s\n", label, mk_status_string(status));
    return 1;
}

static int has_feature(const mk_string_list *list, const char *feature)
{
    size_t i;

    for (i = 0; i < mk_string_list_size(list); i++) {
        if (strcmp(mk_string_list_get(list, i), feature) == 0) {
            return 1;
        }
    }
    return 0;
}

int main(void)
{
    mk_registry *registry = NULL;
    const mk_system *system = NULL;
    mk_string_list *features = NULL;
    mk_string_list *segments = NULL;
    char *normalized = NULL;
    double distance = 0.0;
    int failed = 0;
    mk_status status;

    status = mk_registry_new_builtin(&registry);
    if (status != MK_OK) {
        return fail_status(status, "registry");
    }

    status = mk_registry_get_system(registry, "descriptive", &system);
    if (status != MK_OK) {
        failed = fail_status(status, "system");
        goto cleanup;
    }

    status = mk_system_grapheme_features(system, "pʰ", &features);
    if (status != MK_OK) {
        failed = fail_status(status, "features");
        goto cleanup;
    }
    /* Membership, not cardinality. This assertion was pinned to a count of 5,
     * which the descriptive inventory outgrew; the exact feature set is what
     * the golden fixtures are for, and what this test needs to know is that
     * the lookup path works under Emscripten at all. */
    if (!has_feature(features, "aspirated") ||
        !has_feature(features, "bilabial") ||
        !has_feature(features, "voiceless")) {
        fprintf(stderr, "features: missing an expected feature of pʰ\n");
        failed = 1;
        goto cleanup;
    }
    mk_string_list_free(features);
    features = NULL;

    /* Invariants, not a pinned value. This compared against 0.375, which is the
     * pre-C Python figure preserved in the archived `_full` fixtures; the C
     * library answers 0.125. Exact values belong in the golden fixtures, which
     * are regenerated deliberately when scoring changes. */
    status = mk_system_segment_distance(system, "p", "p", &distance);
    if (status != MK_OK) {
        failed = fail_status(status, "distance-identity");
        goto cleanup;
    }
    if (distance != 0.0) {
        fprintf(stderr, "distance: p/p expected 0, got %.10f\n", distance);
        failed = 1;
        goto cleanup;
    }

    status = mk_system_segment_distance(system, "p", "b", &distance);
    if (status != MK_OK) {
        failed = fail_status(status, "distance");
        goto cleanup;
    }
    if (!(distance > 0.0) || !(distance < 1.0)) {
        fprintf(stderr, "distance: p/b expected within (0,1), got %.10f\n", distance);
        failed = 1;
        goto cleanup;
    }

    status = mk_normalize_grapheme("g", &normalized);
    if (status != MK_OK) {
        failed = fail_status(status, "normalize");
        goto cleanup;
    }
    if (strcmp(normalized, "ɡ") != 0) {
        fprintf(stderr, "normalize: expected IPA g, got %s\n", normalized);
        failed = 1;
        goto cleanup;
    }
    mk_string_free(normalized);
    normalized = NULL;

    status = mk_segment_ipa_merged("tʰoŋ⁵⁵", &segments);
    if (status != MK_OK) {
        failed = fail_status(status, "segment");
        goto cleanup;
    }
    if (mk_string_list_size(segments) != 3 ||
        strcmp(mk_string_list_get(segments, 1), "o⁵⁵") != 0) {
        fprintf(stderr, "segment: expected merged tone digit segment\n");
        failed = 1;
        goto cleanup;
    }

cleanup:
    mk_string_free(normalized);
    mk_string_list_free(features);
    mk_string_list_free(segments);
    mk_registry_free(registry);
    return failed;
}
