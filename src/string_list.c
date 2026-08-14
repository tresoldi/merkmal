#include "string_list.h"

#include "strings.h"

#include <stdlib.h>

mk_status mki_string_list_from_borrowed(
    const char *const *items,
    size_t count,
    mk_string_list **out
)
{
    mk_string_list *list;
    size_t i;

    if (out == NULL || (items == NULL && count != 0)) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;

    list = (mk_string_list *)calloc(1, sizeof(*list));
    if (list == NULL) {
        return MK_ERR_OOM;
    }
    if (count != 0) {
        list->items = (char **)calloc(count, sizeof(*list->items));
        if (list->items == NULL) {
            free(list);
            return MK_ERR_OOM;
        }
    }
    list->count = count;

    for (i = 0; i < count; i++) {
        list->items[i] = mki_strdup_internal(items[i]);
        if (list->items[i] == NULL) {
            mk_string_list_free(list);
            return MK_ERR_OOM;
        }
    }

    *out = list;
    return MK_OK;
}

mk_status mki_string_list_adopt(
    char **items,
    size_t count,
    mk_string_list **out
)
{
    mk_string_list *list;

    if (out == NULL || (items == NULL && count != 0)) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;

    list = (mk_string_list *)calloc(1, sizeof(*list));
    if (list == NULL) {
        /* The caller still owns `items` and can free it. */
        return MK_ERR_OOM;
    }
    list->items = items;
    list->count = count;
    *out = list;
    return MK_OK;
}

mk_status mk_string_list_new(
    const char *const *items,
    size_t count,
    mk_string_list **out
)
{
    return mki_string_list_from_borrowed(items, count, out);
}

size_t mk_string_list_size(const mk_string_list *list)
{
    return list == NULL ? 0 : list->count;
}

const char *mk_string_list_get(const mk_string_list *list, size_t index)
{
    if (list == NULL || index >= list->count) {
        return NULL;
    }
    return list->items[index];
}

void mk_string_list_free(mk_string_list *list)
{
    size_t i;

    if (list == NULL) {
        return;
    }
    for (i = 0; i < list->count; i++) {
        free(list->items[i]);
    }
    free(list->items);
    free(list);
}

void mk_string_free(char *s)
{
    free(s);
}
