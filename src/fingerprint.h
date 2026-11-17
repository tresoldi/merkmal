#ifndef MK_FINGERPRINT_H
#define MK_FINGERPRINT_H

#include "merkmal.h"
#include "system.h"

/* The one internal seam for canonical fingerprint construction. The public
 * system entry point delegates here; tests exercise the public interface.
 *
 * Either output may be NULL, not both. Each non-NULL one is set to NULL first
 * and on MK_OK receives an owned string, freed with mk_string_free.
 * MK_ERR_INVALID_ARGUMENT for a NULL system or two NULL outputs, MK_ERR_OOM
 * when an allocation fails. */
mk_status mki_system_semantic_fingerprint(
    const mk_system *system,
    char **payload_out,
    char **digest_out
);

#endif
