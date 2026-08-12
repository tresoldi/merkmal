#include "merkmal.h"

#include <stdio.h>

int main(void)
{
    mk_registry *registry = NULL;
    const mk_system *system = NULL;
    double distance = 0.0;
    mk_status status;

    status = mk_registry_new_builtin(&registry);
    if (status != MK_OK) {
        fprintf(stderr, "registry: %s\n", mk_status_string(status));
        return 1;
    }
    status = mk_registry_get_system(registry, "descriptive", &system);
    if (status == MK_OK) {
        status = mk_system_segment_distance(system, "p", "b", &distance);
    }
    mk_registry_free(registry);
    if (status != MK_OK || distance <= 0.0) {
        fprintf(stderr, "installed API smoke test failed\n");
        return 1;
    }
    return 0;
}
