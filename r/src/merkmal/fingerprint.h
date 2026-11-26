#ifndef MK_FINGERPRINT_H
#define MK_FINGERPRINT_H

#include "merkmal.h"
#include "system.h"

/* The version of everything the code decides about a result: resolution,
 * tokenization, tone handling and scoring. The data hashes in the payload
 * identify the tables; this identifies what is done with them, so that a code
 * change that moves a feature set or a distance also moves the fingerprint.
 *
 * Bump it with any change that alters a golden fixture.
 * tools/regenerate_golden.py records it beside a hash of the fixtures in
 * tests/golden/behavior.tsv, refuses to record changed fixtures under an
 * unchanged version, and with --check (in CI) fails when the two disagree.
 * 1 is every release up to 0.10.0. */
#define MKI_BEHAVIOR_VERSION "2"

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
