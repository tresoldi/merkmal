#include "merkmal.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

static int fail_status(mk_status status, const char *label)
{
    fprintf(stderr, "%s: %s\n", label, mk_status_string(status));
    return 1;
}

int main(void)
{
    mk_registry *registry = NULL;
    const mk_system *system = NULL;
    mk_feature_set *features = NULL;
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
    if (mk_feature_set_size(features) != 5) {
        fprintf(stderr, "features: expected 5, got %zu\n", mk_feature_set_size(features));
        failed = 1;
        goto cleanup;
    }
    mk_feature_set_free(features);
    features = NULL;

    status = mk_system_segment_distance(system, "p", "b", &distance);
    if (status != MK_OK) {
        failed = fail_status(status, "distance");
        goto cleanup;
    }
    if (fabs(distance - 0.375) > 0.0000001) {
        fprintf(stderr, "distance: expected 0.375, got %.10f\n", distance);
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
    mk_free_string(normalized);
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
    mk_free_string(normalized);
    mk_feature_set_free(features);
    mk_string_list_free(segments);
    mk_registry_free(registry);
    return failed;
}
