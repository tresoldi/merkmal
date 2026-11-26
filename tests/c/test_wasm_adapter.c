/* The WebAssembly adapter compiled natively: its output is parsed by
 * JSON.parse in the demonstration, so every number it writes must be valid
 * JSON. A valued system's unknown value is NaN in a feature vector, and
 * printf writes NaN as `nan`. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Defined in web/merkmal_wasm.c. */
char *merkmal_grapheme_features(const char *system_name, const char *grapheme);
char *merkmal_distance_matrix(const char *system_name, const char *segments_csv);
void merkmal_free(char *text);

/* A list longer than the matrix takes is refused, not cut short: it used to
 * drop every segment after the 101st without a word. */
static int check_matrix_bound(void)
{
    char csv[512];
    char *json;
    int failed = 0;
    size_t used = 0;
    int i;

    for (i = 0; i < 101; i++) {
        used += (size_t)snprintf(csv + used, sizeof(csv) - used, "%sa", i ? "," : "");
    }
    json = merkmal_distance_matrix("descriptive", csv);
    if (json == NULL || strstr(json, "\"ok\":false") == NULL ||
        strstr(json, "at most 100 segments") == NULL) {
        fprintf(stderr, "101 segments were not refused: %.120s\n", json ? json : "(null)");
        failed = 1;
    }
    merkmal_free(json);
    /* 100 is still accepted. */
    csv[used - 2] = '\0';
    json = merkmal_distance_matrix("descriptive", csv);
    if (json == NULL || strstr(json, "\"ok\":true") == NULL) {
        fprintf(stderr, "100 segments were refused\n");
        failed = 1;
    }
    merkmal_free(json);
    return failed;
}

/* Counts the `null` entries of the vector's values array, or returns -1 if an
 * entry is neither a JSON number nor null. */
static int count_nulls(const char *json)
{
    const char *p = strstr(json, "\"values\":[");
    int nulls = 0;

    if (p == NULL) {
        return -1;
    }
    p += strlen("\"values\":[");
    while (*p != ']') {
        char *end = NULL;

        if (strncmp(p, "null", 4) == 0) {
            nulls++;
            p += 4;
        } else if ((*p >= '0' && *p <= '9') || *p == '-') {
            (void)strtod(p, &end);
            p = end;
        } else {
            return -1;
        }
        if (*p == ',') {
            p++;
        } else if (*p != ']') {
            return -1;
        }
    }
    return nulls;
}

int main(void)
{
    int failed = check_matrix_bound();
#ifdef MERKMAL_TEST_DATA_PROFILE_CC_BY
    /* No system in the cc-by profile has an unknown value. */
    return failed ? 1 : 77;
#else
    /* PHOIBLE leaves some dimensions of `a` unknown. */
    char *json = merkmal_grapheme_features("phoible", "a");

    if (json == NULL || strstr(json, "\"ok\":true") == NULL) {
        fprintf(stderr, "features of a in phoible: %s\n", json ? json : "(null)");
        failed = 1;
    } else if (count_nulls(json) <= 0) {
        fprintf(stderr, "vector values are not numbers and nulls: %s\n", json);
        failed = 1;
    }
    merkmal_free(json);
    return failed;
#endif
}
