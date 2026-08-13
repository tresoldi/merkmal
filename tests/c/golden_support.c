#include "golden_support.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int mk_read_field(char **cursor, char *out, size_t out_size)
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

static char *mk_golden_dup(const char *s, size_t n)
{
    char *copy = (char *)malloc(n + 1);

    if (copy == NULL) {
        return NULL;
    }
    memcpy(copy, s, n);
    copy[n] = '\0';
    return copy;
}

/* Splits "consonant|voiceless|bilabial|stop" into the case's owned features. */
static int mk_golden_case_set_features(mk_golden_case *item, const char *packed)
{
    const char *start = packed;

    item->feature_count = 0;
    while (*start != '\0') {
        const char *end = strchr(start, '|');
        size_t n = end == NULL ? strlen(start) : (size_t)(end - start);

        if (item->feature_count >= MK_GOLDEN_MAX_FEATURES) {
            fprintf(stderr, "geometry case %s: more than %d features\n",
                item->name, MK_GOLDEN_MAX_FEATURES);
            return 1;
        }
        item->features[item->feature_count] = mk_golden_dup(start, n);
        if (item->features[item->feature_count] == NULL) {
            return 1;
        }
        item->feature_view[item->feature_count] = item->features[item->feature_count];
        item->feature_count++;
        if (end == NULL) {
            break;
        }
        start = end + 1;
    }
    return 0;
}

int mk_golden_cases_load(mk_golden_cases *out, const char *path)
{
    char line[1024];
    FILE *file;
    int line_no = 0;

    memset(out, 0, sizeof(*out));
    file = fopen(path, "r");
    if (file == NULL) {
        fprintf(stderr, "failed to open %s\n", path);
        return 1;
    }

    while (fgets(line, sizeof(line), file) != NULL) {
        char *cursor = line;
        char name[64];
        char packed[512];
        mk_golden_case *item;

        line_no++;
        if (line_no == 1) {
            continue;
        }
        if (!mk_read_field(&cursor, name, sizeof(name))) {
            continue;
        }
        if (!mk_read_field(&cursor, packed, sizeof(packed))) {
            fprintf(stderr, "%s:%d: case %s has no features\n", path, line_no, name);
            fclose(file);
            mk_golden_cases_free(out);
            return 1;
        }
        if (out->count >= MK_GOLDEN_MAX_CASES) {
            fprintf(stderr, "%s: more than %d cases\n", path, MK_GOLDEN_MAX_CASES);
            fclose(file);
            mk_golden_cases_free(out);
            return 1;
        }
        item = &out->items[out->count];
        memcpy(item->name, name, strlen(name) + 1);
        if (mk_golden_case_set_features(item, packed) != 0) {
            fclose(file);
            mk_golden_cases_free(out);
            return 1;
        }
        out->count++;
    }

    fclose(file);
    if (out->count == 0) {
        fprintf(stderr, "%s: no cases\n", path);
        return 1;
    }
    return 0;
}

void mk_golden_cases_free(mk_golden_cases *cases)
{
    size_t i;
    size_t j;

    for (i = 0; i < cases->count; i++) {
        for (j = 0; j < cases->items[i].feature_count; j++) {
            free(cases->items[i].features[j]);
        }
    }
    memset(cases, 0, sizeof(*cases));
}

const mk_golden_case *mk_golden_cases_find(const mk_golden_cases *cases, const char *name)
{
    size_t i;

    for (i = 0; i < cases->count; i++) {
        if (strcmp(cases->items[i].name, name) == 0) {
            return &cases->items[i];
        }
    }
    return NULL;
}
