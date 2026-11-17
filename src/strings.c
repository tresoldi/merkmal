#include "strings.h"

#include "array.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

char *mki_strdup_internal(const char *s)
{
    size_t len;
    char *copy;

    if (s == NULL) {
        return NULL;
    }
    len = strlen(s);
    copy = (char *)malloc(len + 1);
    if (copy == NULL) {
        return NULL;
    }
    memcpy(copy, s, len + 1);
    return copy;
}

bool mki_streq(const char *a, const char *b)
{
    if (a == NULL || b == NULL) {
        return false;
    }
    return strcmp(a, b) == 0;
}

bool mki_has_prefix(const char *s, const char *prefix)
{
    size_t n;

    if (s == NULL || prefix == NULL) {
        return false;
    }
    n = strlen(prefix);
    return strncmp(s, prefix, n) == 0;
}

bool mki_features_contain(const char *const *items, size_t count, const char *feature)
{
    size_t i;

    if (items == NULL || feature == NULL || feature[0] == '\0') {
        return false;
    }
    for (i = 0; i < count; i++) {
        if (mki_streq(items[i], feature)) {
            return true;
        }
    }
    return false;
}

mk_status mki_append_text(char **buf, size_t *len, size_t *cap, const char *s)
{
    size_t n;
    char *next;

    n = strlen(s);
    /* Room for the suffix and the terminator. A suffix so long that n + 1
     * would overflow is refused here as a failed allocation. */
    if (n == SIZE_MAX) {
        return MK_ERR_OOM;
    }
    next = (char *)mki_grow_array(*buf, cap, *len, n + 1, 1, 32);
    if (next == NULL) {
        return MK_ERR_OOM;
    }
    *buf = next;
    memcpy(*buf + *len, s, n);
    *len += n;
    (*buf)[*len] = '\0';
    return MK_OK;
}

void mki_free_items(char **items, size_t count)
{
    size_t i;

    if (items == NULL) {
        return;
    }
    for (i = 0; i < count; i++) {
        free(items[i]);
    }
    free(items);
}
