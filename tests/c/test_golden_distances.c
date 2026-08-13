#include "merkmal.h"

#include "golden_support.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef MERKMAL_SOURCE_DIR
#define MERKMAL_SOURCE_DIR "."
#endif

static int check_file(
    mk_registry *registry,
    const char *system_name,
    const char *relative_path
)
{
    char path[1024];
    char line[4096];
    FILE *file;
    const mk_system *system = NULL;
    int failed = 0;
    int line_no = 0;

    snprintf(path, sizeof(path), "%s/%s", MERKMAL_SOURCE_DIR, relative_path);
    file = fopen(path, "r");
    if (file == NULL) {
        fprintf(stderr, "failed to open %s\n", path);
        return 1;
    }

    if (mk_registry_get_system(registry, system_name, &system) != MK_OK) {
        fprintf(stderr, "failed to get system %s\n", system_name);
        fclose(file);
        return 1;
    }

    while (fgets(line, sizeof(line), file) != NULL) {
        char *cursor = line;
        char a[128];
        char b[128];
        char expected_text[128];
        double expected;
        double actual;
        mk_status status;

        line_no++;
        if (line_no == 1) {
            continue;
        }
        if (!mk_read_field(&cursor, a, sizeof(a)) ||
            !mk_read_field(&cursor, b, sizeof(b)) ||
            !mk_read_field(&cursor, expected_text, sizeof(expected_text))) {
            fprintf(stderr, "%s:%d: malformed row\n", relative_path, line_no);
            failed = 1;
            continue;
        }

        expected = strtod(expected_text, NULL);
        status = mk_system_segment_distance(system, a, b, &actual);
        if (status != MK_OK) {
            fprintf(stderr, "%s:%d: %s/%s returned status %d\n", relative_path, line_no, a, b, status);
            failed = 1;
            continue;
        }
        if (fabs(actual - expected) > 1e-8) {
            fprintf(
                stderr,
                "%s:%d: %s/%s expected %.10f got %.10f\n",
                relative_path,
                line_no,
                a,
                b,
                expected,
                actual
            );
            failed = 1;
        }
    }

    fclose(file);
    return failed;
}

int main(void)
{
    mk_registry *registry = NULL;
    int failed = 0;
    static const char *const systems[] = {
        "broad",
        "descriptive",
        "distinctive",
        "pbase-hc",
        "pbase-jfh",
        "pbase-spe",
        "pbase-uftc",
        "phoible",
    };
    size_t i;

    if (mk_registry_new_builtin(&registry) != MK_OK) {
        fprintf(stderr, "failed to create registry\n");
        return 1;
    }

    for (i = 0; i < sizeof(systems) / sizeof(systems[0]); i++) {
        char path[256];
        snprintf(path, sizeof(path), "tests/golden/%s_distances.tsv", systems[i]);
        failed |= check_file(registry, systems[i], path);
    }

    mk_registry_free(registry);
    return failed ? 1 : 0;
}
