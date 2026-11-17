/* mki_grow_array: growth, the unchanged-on-failure contract, and the size
 * arithmetic it exists to check. */
#include "array.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static int failures = 0;

static void check(int ok, const char *label)
{
    if (!ok) {
        fprintf(stderr, "FAIL: %s\n", label);
        failures++;
    }
}

int main(void)
{
    int *items = NULL;
    int *next;
    size_t cap = 0;
    size_t count = 0;
    size_t i;

    /* An empty array starts at `initial` and doubles from there. */
    for (i = 0; i < 100; i++) {
        next = (int *)mki_grow_array(items, &cap, count, 1, sizeof(*items), 4);
        check(next != NULL, "grow");
        if (next == NULL) {
            break;
        }
        items = next;
        items[count++] = (int)i;
    }
    check(cap == 128, "doubling from 4 reaches 128 for 100 items");
    for (i = 0; i < count; i++) {
        check(items[i] == (int)i, "contents survive growth");
    }

    /* Room already there: same pointer, same capacity. */
    next = (int *)mki_grow_array(items, &cap, count, 1, sizeof(*items), 4);
    check(next == items && cap == 128, "no-op when it fits");

    /* A request several doublings away is met in one call. */
    next = (int *)mki_grow_array(items, &cap, count, 1000, sizeof(*items), 4);
    check(next != NULL && cap == 2048, "multi-step doubling");
    if (next != NULL) {
        items = next;
    }

    /* Overflow is refused, and the array and capacity are left alone. */
    {
        size_t before = cap;
        next = (int *)mki_grow_array(items, &cap, SIZE_MAX, 1, sizeof(*items), 4);
        check(next == NULL && cap == before, "count + extra overflows");
        next = (int *)mki_grow_array(items, &cap, SIZE_MAX / 2, 1, sizeof(*items), 4);
        check(next == NULL && cap == before, "capacity * elem_size overflows");
        check(items[0] == 0 && items[99] == 99, "array untouched after refusal");
    }

    /* Degenerate arguments are refused rather than read as a no-op. */
    check(mki_grow_array(items, NULL, 0, 1, sizeof(*items), 4) == NULL, "null capacity");
    check(mki_grow_array(items, &cap, 0, 0, sizeof(*items), 4) == NULL, "zero extra");
    check(mki_grow_array(items, &cap, 0, 1, 0, 4) == NULL, "zero element size");

    free(items);
    if (failures == 0) {
        printf("array: ok\n");
    }
    return failures == 0 ? 0 : 1;
}
