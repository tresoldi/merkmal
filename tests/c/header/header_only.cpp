/* The same, through a C++ compiler: the header declares extern "C", and a
 * consumer compiling C++ is the reason that block is there. */

#include "merkmal.h"

int main()
{
    mk_registry *registry = nullptr;
    mk_feature_view view;

    view.features = nullptr;
    view.count = 0;
    (void)registry;
    (void)view;
    (void)mk_status_string(MK_OK);
    return 0;
}
