/* The public header must compile on its own.
 *
 * Nothing else here: including it and nothing else is the whole test. A header
 * that needs the caller to have included <stddef.h> first compiles fine inside
 * this project, where everything else already has, and fails for the first
 * consumer who includes it before anything.
 */

#include "merkmal.h"

int main(void)
{
    /* Reference one of each kind of declaration, so the test fails if a type
     * or a symbol stops being reachable through the header alone. */
    mk_registry *registry = (mk_registry *)0;
    const mk_system *system = (const mk_system *)0;
    mk_string_list *list = (mk_string_list *)0;
    mk_feature_view view;
    mk_status status = MK_OK;

    view.features = (const char *const *)0;
    view.count = 0;

    (void)registry;
    (void)system;
    (void)list;
    (void)view;
    (void)mk_status_string(status);
    return 0;
}
