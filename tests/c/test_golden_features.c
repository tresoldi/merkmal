#include "merkmal.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef MERKMAL_SOURCE_DIR
#define MERKMAL_SOURCE_DIR "."
#endif

static int read_field(char **cursor, char *out, size_t out_size)
{
    size_t len = 0;
    char *p = *cursor;

    while (*p != '\0' && *p != '\t' && *p != '\n' && *p != '\r') {
        if (len + 1 < out_size) {
            out[len++] = *p;
        }
        p++;
    }
    out[len] = '\0';
    if (*p == '\t') {
        p++;
    }
    *cursor = p;
    return len > 0;
}

static int feature_set_contains(const mk_feature_set *features, const char *feature)
{
    size_t i;

    for (i = 0; i < mk_feature_set_size(features); i++) {
        const char *actual = mk_feature_set_get(features, i);
        if (actual != NULL && strcmp(actual, feature) == 0) {
            return 1;
        }
    }
    return 0;
}

static size_t expected_feature_count(const char *features)
{
    size_t count = 1;
    const char *p;

    if (features[0] == '\0') {
        return 0;
    }
    for (p = features; *p != '\0'; p++) {
        if (*p == '|') {
            count++;
        }
    }
    return count;
}

static int compare_features(
    const mk_feature_set *actual,
    char *expected_text,
    const char *label
)
{
    char *p = expected_text;
    int failed = 0;

    if (mk_feature_set_size(actual) != expected_feature_count(expected_text)) {
        fprintf(
            stderr,
            "%s: expected %zu features, got %zu\n",
            label,
            expected_feature_count(expected_text),
            mk_feature_set_size(actual)
        );
        failed = 1;
    }

    while (p != NULL && *p != '\0') {
        char *next = strchr(p, '|');
        if (next != NULL) {
            *next = '\0';
        }
        if (!feature_set_contains(actual, p)) {
            fprintf(stderr, "%s: missing feature %s\n", label, p);
            failed = 1;
        }
        p = next == NULL ? NULL : next + 1;
    }

    return failed;
}

static int check_file(
    mk_registry *registry,
    const char *system_name,
    const char *relative_path
)
{
    char path[1024];
    char line[32768];
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
        char grapheme[256];
        char expected[30000];
        mk_feature_set *actual = NULL;
        mk_status status;

        line_no++;
        if (line_no == 1) {
            continue;
        }
        if (!read_field(&cursor, grapheme, sizeof(grapheme)) ||
            !read_field(&cursor, expected, sizeof(expected))) {
            fprintf(stderr, "%s:%d: malformed row\n", relative_path, line_no);
            failed = 1;
            continue;
        }

        status = mk_system_grapheme_features(system, grapheme, &actual);
        if (status != MK_OK) {
            fprintf(stderr, "%s:%d: %s returned status %d\n", relative_path, line_no, grapheme, status);
            failed = 1;
            continue;
        }
        failed |= compare_features(actual, expected, grapheme);
        mk_feature_set_free(actual);
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
        snprintf(path, sizeof(path), "tests/golden/%s_features.tsv", systems[i]);
        failed |= check_file(registry, systems[i], path);
    }

    mk_registry_free(registry);
    return failed ? 1 : 0;
}
