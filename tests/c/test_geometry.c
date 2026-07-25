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

int main(void)
{
    int failed = 0;

    failed |= check_feature_distances();
    failed |= check_sound_distances("tests/golden/geometry_sound_distances.tsv", 0);
    failed |= check_sound_distances("tests/golden/geometry_weighted_distances.tsv", 1);
    return failed ? 1 : 0;
}
