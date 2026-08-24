#ifndef MK_FINGERPRINT_H
#define MK_FINGERPRINT_H

#include "merkmal.h"
#include "system.h"

/* The one internal seam for canonical fingerprint construction. The public
 * system entry point delegates here; tests exercise the public interface. */
mk_status mki_system_semantic_fingerprint(
    const mk_system *system,
    char **payload_out,
    char **digest_out
);

#endif
