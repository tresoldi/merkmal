#ifndef MK_REGISTRY_H
#define MK_REGISTRY_H

#include "system.h"

#include <stddef.h>

struct mk_registry {
    /* The array and every system in it are owned by the registry. The array
     * may grow, so each system has its own allocation: a pointer handed out
     * by mk_registry_get_system stays valid until mk_registry_free. */
    mk_system **systems;
    size_t system_count;
};

#endif
