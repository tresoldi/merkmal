/* The WebAssembly adapter compiled natively: its output is parsed by
 * JSON.parse in the demonstration, so every number it writes must be valid
 * JSON. A valued system's unknown value is NaN in a feature vector, and
 * printf writes NaN as `nan`. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Defined in web/merkmal_wasm.c. */
char *merkmal_grapheme_features(const char *system_name, const char *grapheme);
void merkmal_free(char *text);

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
#ifdef MERKMAL_TEST_DATA_PROFILE_CC_BY
    /* No system in the cc-by profile has an unknown value. */
    return 77;
#else
    /* PHOIBLE leaves some dimensions of `a` unknown. */
    char *json = merkmal_grapheme_features("phoible", "a");
    int failed = 0;

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
