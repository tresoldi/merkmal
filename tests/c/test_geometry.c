#include "merkmal.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef MERKMAL_SOURCE_DIR
#define MERKMAL_SOURCE_DIR "."
#endif

typedef struct named_features {
    const char *name;
    const char *const *features;
    size_t feature_count;
} named_features;

static const char *const p_features[] = {"consonant", "voiceless", "bilabial", "stop"};
static const char *const b_features[] = {"consonant", "voiced", "bilabial", "stop"};
static const char *const t_features[] = {"consonant", "voiceless", "alveolar", "stop"};
static const char *const k_features[] = {"consonant", "voiceless", "velar", "stop"};
static const char *const s_features[] = {"consonant", "voiceless", "alveolar", "fricative"};
static const char *const a_features[] = {"vowel", "open", "front", "unrounded"};
static const char *const i_features[] = {"vowel", "close", "front", "unrounded"};
static const char *const u_features[] = {"vowel", "close", "back", "rounded"};

static const named_features feature_sets[] = {
    {"p", p_features, sizeof(p_features) / sizeof(p_features[0])},
    {"p-feats", p_features, sizeof(p_features) / sizeof(p_features[0])},
    {"b", b_features, sizeof(b_features) / sizeof(b_features[0])},
    {"b-feats", b_features, sizeof(b_features) / sizeof(b_features[0])},
    {"t-feats", t_features, sizeof(t_features) / sizeof(t_features[0])},
    {"k-feats", k_features, sizeof(k_features) / sizeof(k_features[0])},
    {"s-feats", s_features, sizeof(s_features) / sizeof(s_features[0])},
    {"a", a_features, sizeof(a_features) / sizeof(a_features[0])},
    {"a-feats", a_features, sizeof(a_features) / sizeof(a_features[0])},
    {"i-feats", i_features, sizeof(i_features) / sizeof(i_features[0])},
    {"u-feats", u_features, sizeof(u_features) / sizeof(u_features[0])},
};

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

static const named_features *find_features(const char *name)
{
    size_t i;

    for (i = 0; i < sizeof(feature_sets) / sizeof(feature_sets[0]); i++) {
        if (strcmp(feature_sets[i].name, name) == 0) {
            return &feature_sets[i];
        }
    }
    return NULL;
}

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
        if (!read_field(&cursor, a, sizeof(a)) ||
            !read_field(&cursor, b, sizeof(b)) ||
            !read_field(&cursor, expected_text, sizeof(expected_text))) {
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

static int check_sound_distances(const char *relative_path, int weighted)
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
        const named_features *features_a;
        const named_features *features_b;
        double expected;
        double actual = -1.0;
        mk_status status;

        line_no++;
        if (line_no == 1) {
            continue;
        }

        if (weighted) {
            if (!read_field(&cursor, preset, sizeof(preset))) {
                fprintf(stderr, "%s:%d: malformed row\n", path, line_no);
                failed = 1;
                continue;
            }
            node_weights = strcmp(preset, "None") == 0 ? NULL : preset;
        }

        if (!read_field(&cursor, a, sizeof(a)) ||
            !read_field(&cursor, b, sizeof(b)) ||
            !read_field(&cursor, expected_text, sizeof(expected_text))) {
            fprintf(stderr, "%s:%d: malformed row\n", path, line_no);
            failed = 1;
            continue;
        }

        features_a = find_features(a);
        features_b = find_features(b);
        if (features_a == NULL || features_b == NULL) {
            fprintf(stderr, "%s:%d: unknown feature set %s/%s\n", path, line_no, a, b);
            failed = 1;
            continue;
        }

        expected = strtod(expected_text, NULL);
        status = mk_sound_distance(
            features_a->features,
            features_a->feature_count,
            features_b->features,
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

/* Rewrites the three geometry fixtures from the current build. Kept in this
 * file so the named feature sets above stay the single source of truth; driven
 * by scripts/regenerate_golden.py, never by the test run itself. */
static int rewrite_fixture(const char *relative_path, int weighted, int feature_mode)
{
    char in_path[1024];
    char out_path[1024];
    char line[1024];
    FILE *in_file;
    FILE *out_file;
    int line_no = 0;

    snprintf(in_path, sizeof(in_path), "%s/%s", MERKMAL_SOURCE_DIR, relative_path);
    snprintf(out_path, sizeof(out_path), "%s/%s.new", MERKMAL_SOURCE_DIR, relative_path);
    in_file = fopen(in_path, "r");
    if (in_file == NULL) {
        fprintf(stderr, "failed to open %s\n", in_path);
        return 1;
    }
    out_file = fopen(out_path, "w");
    if (out_file == NULL) {
        fprintf(stderr, "failed to write %s\n", out_path);
        fclose(in_file);
        return 1;
    }

    while (fgets(line, sizeof(line), in_file) != NULL) {
        char *cursor = line;
        char preset[128];
        char a[128];
        char b[128];
        char expected_text[128];

        line_no++;
        if (line_no == 1) {
            fputs(line, out_file);
            continue;
        }
        preset[0] = '\0';
        if (weighted && !read_field(&cursor, preset, sizeof(preset))) {
            continue;
        }
        if (!read_field(&cursor, a, sizeof(a)) ||
            !read_field(&cursor, b, sizeof(b)) ||
            !read_field(&cursor, expected_text, sizeof(expected_text))) {
            continue;
        }

        if (feature_mode) {
            int actual = -1;
            if (mk_feature_distance(a, b, &actual) != MK_OK) {
                fclose(in_file);
                fclose(out_file);
                return 1;
            }
            fprintf(out_file, "%s\t%s\t%d\n", a, b, actual);
        } else {
            const named_features *fa = find_features(a);
            const named_features *fb = find_features(b);
            const char *node_weights = weighted && strcmp(preset, "None") != 0 ? preset : NULL;
            double actual = -1.0;

            if (fa == NULL || fb == NULL) {
                fclose(in_file);
                fclose(out_file);
                return 1;
            }
            if (mk_sound_distance(
                    fa->features, fa->feature_count,
                    fb->features, fb->feature_count,
                    node_weights, &actual) != MK_OK) {
                fclose(in_file);
                fclose(out_file);
                return 1;
            }
            if (weighted) {
                fprintf(out_file, "%s\t%s\t%s\t%.10f\n", preset, a, b, actual);
            } else {
                fprintf(out_file, "%s\t%s\t%.10f\n", a, b, actual);
            }
        }
    }

    fclose(in_file);
    fclose(out_file);
    return rename(out_path, in_path) != 0;
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

int main(int argc, char **argv)
{
    int failed = 0;

    if (argc > 1 && strcmp(argv[1], "--regenerate") == 0) {
        failed |= rewrite_fixture("tests/golden/geometry_distances.tsv", 0, 1);
        failed |= rewrite_fixture("tests/golden/geometry_sound_distances.tsv", 0, 0);
        failed |= rewrite_fixture("tests/golden/geometry_weighted_distances.tsv", 1, 0);
        return failed ? 1 : 0;
    }

    failed |= check_feature_distances();
    failed |= check_sound_distances("tests/golden/geometry_sound_distances.tsv", 0);
    failed |= check_sound_distances("tests/golden/geometry_weighted_distances.tsv", 1);
    failed |= check_invalid_preset();
    return failed ? 1 : 0;
}
