#ifndef MK_REGISTRY_H
#define MK_REGISTRY_H

#include "system.h"

#include <stddef.h>

struct mk_registry {
    /* The array may grow, so each system has a stable allocation. */
    mk_system **systems;
    size_t system_count;
};

#endif
