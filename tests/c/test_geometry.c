/* Replays the geometry fixtures. A consumer only: the fixtures are produced by
 * scripts/regenerate_golden.py, so the program that grades the answers is not
 * the program that wrote them, and a build of this test cannot quietly rewrite
 * its own expectations.
 *
 * The named feature sets it scores come from tests/golden/geometry_cases.tsv.
 * They used to be C literals in this file, which meant nothing outside this
 * binary could produce the fixtures and adding a case was a code change. */

#include "merkmal.h"

#include "golden_support.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef MERKMAL_SOURCE_DIR
#define MERKMAL_SOURCE_DIR "."
#endif

static int check_feature_distances(void)
{
    char path[1024];
    char line[1024];
    FILE *file;
    int failed = 0;
    int line_no = 0;

    snprintf(path, sizeof(path), "%s/tests/golden/geometry_distances.tsv", MERKMAL_SOURCE_DIR);
    file = fopen(path, "r");
    if (file == NULL) {
        fprintf(stderr, "failed to open %s\n", path);
        return 1;
    }

    while (fgets(line, sizeof(line), file) != NULL) {
        char *cursor = line;
        char a[128];
        char b[128];
        char expected_text[128];
        int expected;
        int actual = -1;
        mk_status status;

        line_no++;
        if (line_no == 1) {
            continue;
        }
        if (!mk_read_field(&cursor, a, sizeof(a)) ||
            !mk_read_field(&cursor, b, sizeof(b)) ||
            !mk_read_field(&cursor, expected_text, sizeof(expected_text))) {
            fprintf(stderr, "%s:%d: malformed row\n", path, line_no);
            failed = 1;
            continue;
        }

        expected = (int)strtol(expected_text, NULL, 10);
        status = mk_feature_distance(a, b, &actual);
        if (status != MK_OK) {
            fprintf(stderr, "%s:%d: %s/%s returned status %d\n", path, line_no, a, b, status);
            failed = 1;
            continue;
        }
        if (actual != expected) {
            fprintf(
                stderr,
                "%s:%d: %s/%s expected %d got %d\n",
                path,
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
    return failed ? 1 : 0;
}

static int check_sound_distances(
    const mk_golden_cases *cases,
    const char *relative_path,
    int weighted
)
{
    char path[1024];
    char line[1024];
    FILE *file;
    int failed = 0;
    int line_no = 0;

    snprintf(path, sizeof(path), "%s/%s", MERKMAL_SOURCE_DIR, relative_path);
    file = fopen(path, "r");
    if (file == NULL) {
        fprintf(stderr, "failed to open %s\n", path);
        return 1;
    }

    while (fgets(line, sizeof(line), file) != NULL) {
        char *cursor = line;
        char preset[128];
        char a[128];
        char b[128];
        char expected_text[128];
        const char *node_weights = NULL;
        const mk_golden_case *features_a;
        const mk_golden_case *features_b;
        double expected;
        double actual = -1.0;
        mk_status status;

        line_no++;
        if (line_no == 1) {
            continue;
        }

        if (weighted) {
            if (!mk_read_field(&cursor, preset, sizeof(preset))) {
                fprintf(stderr, "%s:%d: malformed row\n", path, line_no);
                failed = 1;
                continue;
            }
            node_weights = strcmp(preset, "None") == 0 ? NULL : preset;
        }

        if (!mk_read_field(&cursor, a, sizeof(a)) ||
            !mk_read_field(&cursor, b, sizeof(b)) ||
            !mk_read_field(&cursor, expected_text, sizeof(expected_text))) {
            fprintf(stderr, "%s:%d: malformed row\n", path, line_no);
            failed = 1;
            continue;
        }

        features_a = mk_golden_cases_find(cases, a);
        features_b = mk_golden_cases_find(cases, b);
        if (features_a == NULL || features_b == NULL) {
            fprintf(stderr, "%s:%d: unknown feature set %s/%s\n", path, line_no, a, b);
            failed = 1;
            continue;
        }

        expected = strtod(expected_text, NULL);
        status = mk_sound_distance(
            features_a->feature_view,
            features_a->feature_count,
            features_b->feature_view,
            features_b->feature_count,
            node_weights,
            &actual
        );
        if (status != MK_OK) {
            fprintf(stderr, "%s:%d: %s/%s returned status %d\n", path, line_no, a, b, status);
            failed = 1;
            continue;
        }
        if (fabs(actual - expected) > 1e-8) {
            fprintf(
                stderr,
                "%s:%d: %s/%s expected %.10f got %.10f\n",
                path,
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
    return failed ? 1 : 0;
}

/* An unknown weight preset is an error, not a number. The scorers used to
 * report it by returning NAN, which callers had to remember to test for. */
static int check_invalid_preset(void)
{
    static const char *const features_a[] = { "consonant", "bilabial", "stop" };
    static const char *const features_b[] = { "consonant", "bilabial", "nasal" };
    double value = -1.0;
    mk_status status;

    status = mk_sound_distance(features_a, 3, features_b, 3, "no-such-preset", &value);
    if (status != MK_ERR_INVALID_ARGUMENT) {
        fprintf(stderr, "sound_distance unknown preset: expected %d, got %d\n",
            MK_ERR_INVALID_ARGUMENT, status);
        return 1;
    }

    status = mk_sound_distance(features_a, 3, features_b, 3, "flat", &value);
    if (status != MK_OK || !(value > 0.0 && value <= 1.0)) {
        fprintf(stderr, "sound_distance flat: expected a normalized value, got %d %.10f\n",
            status, value);
        return 1;
    }
    return 0;
}

int main(void)
{
    char cases_path[1024];
    mk_golden_cases cases;
    int failed = 0;

    snprintf(cases_path, sizeof(cases_path),
        "%s/tests/golden/geometry_cases.tsv", MERKMAL_SOURCE_DIR);
    if (mk_golden_cases_load(&cases, cases_path) != 0) {
        return 1;
    }

    failed |= check_feature_distances();
    failed |= check_sound_distances(&cases, "tests/golden/geometry_sound_distances.tsv", 0);
    failed |= check_sound_distances(&cases, "tests/golden/geometry_weighted_distances.tsv", 1);
    failed |= check_invalid_preset();

    mk_golden_cases_free(&cases);
    return failed ? 1 : 0;
}
