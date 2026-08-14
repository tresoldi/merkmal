/* What using merkmal looks like end to end: take a transcription, split it into
 * segments the chosen system recognizes, read each segment's features, score a
 * pair, and explain a token the system refuses.
 *
 * Every allocation the library hands back is freed here, and every fallible
 * call is checked, because that is the part worth copying. The library returns
 * mk_status and writes results through an out-parameter -- there is no errno to
 * consult and nothing aborts, so a caller that ignores a return value gets a
 * NULL and finds out later.
 *
 * Build and run it with the rest of the tree; `ctest -R example` runs it. */

#include "merkmal.h"

#include <stdio.h>
#include <string.h>

/* One word, in IPA, with a deliberate piece of junk at the end so that the
 * diagnostic path has something to report. */
static const char *const WORD = "pʰaːtʃi";
static const char *const JUNK = "pʰ\xcc\x80\xcc\x81q";

static int show_segments(const mk_system *system)
{
    mk_string_list *tokens = NULL;
    mk_status status;
    size_t i;
    int failed = 0;

    status = mk_system_segment_ipa(system, WORD, &tokens);
    if (status != MK_OK) {
        fprintf(stderr, "segment: %s\n", mk_status_string(status));
        return 1;
    }

    printf("%s splits into %zu segments:\n", WORD, mk_string_list_size(tokens));
    for (i = 0; i < mk_string_list_size(tokens); i++) {
        /* Borrowed: valid while `tokens` is, and not freed here. */
        const char *token = mk_string_list_get(tokens, i);
        mk_string_list *features = NULL;
        size_t j;

        printf("  %-4s ", token);
        status = mk_system_grapheme_features(system, token, &features);
        if (status != MK_OK) {
            printf("(%s)\n", mk_status_string(status));
            continue;
        }
        for (j = 0; j < mk_string_list_size(features); j++) {
            printf("%s%s", j ? " " : "", mk_string_list_get(features, j));
        }
        printf("\n");
        mk_string_list_free(features);
    }

    mk_string_list_free(tokens);
    return failed;
}

static int show_distance(const mk_system *system)
{
    double distance = 0.0;
    double coverage = 0.0;
    mk_comparability why = MK_CMP_OK;
    mk_status status;

    /* The _ex form reports how much of the comparison was real. A plain 0.0
     * from the simple call can mean "identical" or "nothing in common to
     * compare", and only `coverage` tells the two apart. */
    status = mk_system_segment_distance_ex(
        system, "p", "b", NULL, &distance, &coverage, &why
    );
    if (status != MK_OK) {
        fprintf(stderr, "distance: %s\n", mk_status_string(status));
        return 1;
    }
    printf("\nd(p, b) = %.4f  (coverage %.2f, comparability %d)\n",
        distance, coverage, (int)why);
    return 0;
}

static int show_diagnosis(const mk_system *system)
{
    mk_diagnosis diagnosis;
    mk_status status;

    memset(&diagnosis, 0, sizeof(diagnosis));
    status = mk_system_diagnose(system, JUNK, &diagnosis);
    if (status != MK_OK) {
        fprintf(stderr, "diagnose: %s\n", mk_status_string(status));
        return 1;
    }

    /* A refused grapheme is the normal case here and is reported inside the
     * struct; a non-MK_OK return would mean the arguments were unusable. */
    printf("\ndiagnosing a malformed token:\n");
    printf("  verdict            %s\n", mk_status_string(diagnosis.status));
    printf("  longest good prefix %zu bytes\n", diagnosis.valid_prefix_bytes);
    printf("  first bad byte at   %zu\n", diagnosis.offending_offset);
    if (diagnosis.offending[0] != '\0') {
        printf("  offending character %s\n", diagnosis.offending);
    }
    return 0;
}

int main(void)
{
    mk_registry *registry = NULL;
    const mk_system *system = NULL;
    mk_status status;
    int failed = 0;

    status = mk_registry_new_builtin(&registry);
    if (status != MK_OK) {
        fprintf(stderr, "registry: %s\n", mk_status_string(status));
        return 1;
    }

    /* Borrowed from the registry: valid until mk_registry_free, never freed
     * separately. */
    status = mk_registry_get_system(registry, "descriptive", &system);
    if (status != MK_OK) {
        fprintf(stderr, "system: %s\n", mk_status_string(status));
        mk_registry_free(registry);
        return 1;
    }

    failed |= show_segments(system);
    failed |= show_distance(system);
    failed |= show_diagnosis(system);

    mk_registry_free(registry);
    return failed;
}
