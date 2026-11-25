/* Why a grapheme was refused. See merkmal.h for the contract.
 *
 * A status alone is enough for "can I score this?" and not for checking
 * someone's transcriptions, where the diagnosis is the point. "Unknown
 * grapheme" does not tell an author whether they mistyped one combining mark,
 * used a convention this library does not read, or wrote a sound it genuinely
 * lacks.
 *
 * What is reported is what can be established cheaply and stated without
 * guessing:
 *
 *   - the status, which already distinguishes an unknown grapheme from a
 *     malformed one and from source markup;
 *   - the longest prefix that does resolve, which is the practical repair
 *     suggestion -- `pʰ` out of `pʰ<junk>` -- and localizes the problem;
 *   - the first character beyond it, which is the thing to look at.
 *
 * Deliberately not reported: a "nearest valid grapheme" by edit distance over
 * the inventory. It would be a guess dressed as an answer, and the prefix is
 * both cheaper and more often right. */

#include "diagnose.h"

#include "resolver.h"
#include "strings.h"
#include "utf8.h"

#include <stdlib.h>
#include <string.h>

/* The longest prefix, in bytes, that diagnosis tries. A base with a hundred
 * combining marks fits; no segment comes close. */
#define MK_DIAGNOSE_MAX_PREFIX 256

mk_status mk_system_diagnose(
    const mk_system *system,
    const char *utf8_grapheme,
    mk_diagnosis *out
)
{
    mki_resolution entry;
    mk_status status;
    size_t len;
    size_t cut;
    size_t best = 0;

    if (system == NULL || utf8_grapheme == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    memset(out, 0, sizeof(*out));
    out->status = MK_OK;

    status = mki_resolve(system, utf8_grapheme, &entry);
    if (status == MK_OK) {
        mki_resolution_clear(&entry);
        out->valid_prefix_bytes = strlen(utf8_grapheme);
        out->offending_offset = out->valid_prefix_bytes;
        return MK_OK;
    }
    out->status = status;

    len = strlen(utf8_grapheme);
    /* Try every character boundary and keep the longest prefix that
     * resolves. A failing prefix does not end the walk: a longer one may still
     * resolve. Each try resolves a NUL-terminated copy, since mki_resolve reads
     * up to the terminator. Each try costs time in the prefix's length, so the
     * walk stops at MK_DIAGNOSE_MAX_PREFIX bytes, far longer than a segment,
     * and a pathological input costs no more than that. */
    cut = 0;
    while (cut < len && cut < MK_DIAGNOSE_MAX_PREFIX) {
        size_t step = mki_utf8_step(utf8_grapheme + cut);
        size_t next = cut + step;
        char *prefix;

        if (step == 0 || next > len) {
            break;
        }
        prefix = (char *)malloc(next + 1);
        if (prefix == NULL) {
            return MK_ERR_OOM;
        }
        memcpy(prefix, utf8_grapheme, next);
        prefix[next] = '\0';
        if (mki_resolve(system, prefix, &entry) == MK_OK) {
            mki_resolution_clear(&entry);
            best = next;
        }
        free(prefix);
        cut = next;
    }

    out->valid_prefix_bytes = best;
    out->offending_offset = best;
    if (best < len) {
        size_t step = mki_utf8_step(utf8_grapheme + best);

        if (step > 0 && best + step <= len && step < sizeof(out->offending)) {
            memcpy(out->offending, utf8_grapheme + best, step);
            out->offending[step] = '\0';
        }
    }
    return MK_OK;
}
