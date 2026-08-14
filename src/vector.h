#ifndef MK_VECTOR_H
#define MK_VECTOR_H

/* Fixed-width numeric feature vectors. See vector.c for the encoding and why
 * it is the one it is. */

#include "generated/builtin_data.h"
#include "merkmal.h"
#include "system.h"

/* The width for a system, without needing an mk_system wrapper. */
size_t mki_vector_width_of(const mk_builtin_system *builtin);

#endif
