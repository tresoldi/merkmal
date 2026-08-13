#include "strings.h"

#include <stdlib.h>
#include <string.h>

char *mk_strdup_internal(const char *s)
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

int mk_streq(const char *a, const char *b)
{
    if (a == NULL || b == NULL) {
        return 0;
    }
    return strcmp(a, b) == 0;
}

int mk_has_prefix(const char *s, const char *prefix)
{
    size_t n;

    if (s == NULL || prefix == NULL) {
        return 0;
    }
    n = strlen(prefix);
    return strncmp(s, prefix, n) == 0;
}

mk_status mk_append_text(char **buf, size_t *len, size_t *cap, const char *s)
{
    size_t n;
    char *next;

    n = strlen(s);
    if (*len + n + 1 > *cap) {
        size_t new_cap = *cap == 0 ? 32 : *cap;
        while (*len + n + 1 > new_cap) {
            new_cap *= 2;
        }
        next = (char *)realloc(*buf, new_cap);
        if (next == NULL) {
            return MK_ERR_OOM;
        }
        *buf = next;
        *cap = new_cap;
    }
    memcpy(*buf + *len, s, n);
    *len += n;
    (*buf)[*len] = '\0';
    return MK_OK;
}

void mk_free_items(char **items, size_t count)
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
