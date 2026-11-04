#ifndef MK_TEST_PROFILE_H
#define MK_TEST_PROFILE_H

/* Whether a test may skip a built-in system because this build's data profile
 * does not carry it.
 *
 * Only the cc-by profile omits systems (PHOIBLE and P-base), and only there is
 * an absent system a skip. In a full build the answer is always no, so a
 * system that went missing still fails the test that needs it. CMake defines
 * MERKMAL_TEST_DATA_PROFILE_CC_BY for the cc-by profile. */

#include "merkmal.h"

static int profile_lacks_system(const mk_registry *registry, const char *name)
{
#ifdef MERKMAL_TEST_DATA_PROFILE_CC_BY
    const mk_system *system = NULL;
    return mk_registry_get_system(registry, name, &system) == MK_ERR_UNKNOWN_SYSTEM;
#else
    (void)registry;
    (void)name;
    return 0;
#endif
}

#endif
