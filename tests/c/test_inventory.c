/* mk_system_inventory and mk_unicode_normalize, the two calls alteruphono 2.0
 * needs: an exact grapheme universe for rendering feature sets back to
 * graphemes, and plain NFD for its rule notation. */

#include "merkmal.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int failures = 0;

static void check(int ok, const char *what)
{
    if (!ok) {
        fprintf(stderr, "FAIL: %s\n", what);
        failures++;
    }
}

static void check_norm(const char *in, mk_normalization_form form, const char *expected)
{
    char *out = NULL;
    mk_status status = mk_unicode_normalize(in, form, &out);

    check(status == MK_OK && out != NULL && strcmp(out, expected) == 0, expected);
    mk_string_free(out);
}

static void inventory_of(const mk_registry *registry, const char *name)
{
    const mk_system *system = NULL;
    mk_string_list *list = NULL;
    size_t count;
    size_t i;
    int sorted = 1;
    int all_segments = 1;

    check(mk_registry_get_system(registry, name, &system) == MK_OK, name);
    check(mk_system_inventory(system, &list) == MK_OK && list != NULL, "inventory");
    count = mk_string_list_size(list);
    check(count > 100, "inventory is not trivially small");
    for (i = 0; i < count; i++) {
        bool is_segment = false;
        const char *g = mk_string_list_get(list, i);

        if (i > 0 && strcmp(mk_string_list_get(list, i - 1), g) >= 0) {
            sorted = 0;
        }
        if (mk_system_is_segment(system, g, &is_segment) != MK_OK || !is_segment) {
            all_segments = 0;
        }
    }
    check(sorted, "compiled inventory is in strict byte order");
    check(all_segments, "every inventory grapheme resolves");
    mk_string_list_free(list);
}

int main(void)
{
    mk_registry *registry = NULL;
    mk_string_list *list = NULL;
    char *out = (char *)1;

    check(mk_registry_new_builtin(&registry) == MK_OK, "registry");
    inventory_of(registry, "descriptive");
    inventory_of(registry, "distinctive");
    check(mk_system_inventory(NULL, &list) == MK_ERR_INVALID_ARGUMENT, "NULL system");

    check_norm("\xc3\xa9", MK_NFD, "e\xcc\x81"); /* é -> e + U+0301 */
    check_norm("e\xcc\x81", MK_NFC, "\xc3\xa9");
    check_norm("g", MK_NFD, "g"); /* no IPA rewrite to ɡ */
    check_norm("t'", MK_NFC, "t'"); /* no apostrophe rewrite */
    check_norm("a\xcc\x83\xcc\xa0", MK_NFD, "a\xcc\xa0\xcc\x83"); /* reorder: ccc 220 before 230 */
    check(mk_unicode_normalize("a", (mk_normalization_form)7, &out) == MK_ERR_INVALID_ARGUMENT && out == NULL, "bad form clears the out-pointer");
    check(mk_unicode_normalize(NULL, MK_NFD, &out) == MK_ERR_INVALID_ARGUMENT, "NULL input");

    mk_registry_free(registry);
    if (failures != 0) {
        fprintf(stderr, "%d failure(s)\n", failures);
        return 1;
    }
    return 0;
}
