#include "merkmal.h"

#include "generated/builtin_data.h"
#include "generated/unicode_data.h"

/* Build identity, so bindings read it through the public header rather than
 * declaring the generated tables' symbols themselves. */

const char *mk_version_string(void)
{
    return MK_VERSION_STRING;
}

const char *mk_data_profile(void)
{
    return mki_data_profile;
}

const char *mk_unicode_version(void)
{
    return mki_unicode_version;
}
