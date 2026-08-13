/* Why a grapheme was refused. See merkmal.h for the contract.
 *
 * Rejection used to be a single status and nothing else, which is enough for
 * "can I score this?" and useless for the workflow a validated inventory and a
 * fast C core should be best in the world at: checking someone's
 * transcriptions. There the diagnosis *is* the product. "Unknown grapheme" does
 * not tell an author whether they mistyped one combining mark, used a
 * convention this library does not read, or wrote a sound it genuinely lacks.
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

mk_status mk_system_diagnose(
    const mk_system *system,
    const char *utf8_grapheme,
    mk_diagnosis *out
)
{
    mk_resolution entry;
    mk_status status;
    size_t len;
    size_t cut;
    size_t best = 0;

    if (system == NULL || utf8_grapheme == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    memset(out, 0, sizeof(*out));
    out->status = MK_OK;

    status = mk_resolve(system, utf8_grapheme, &entry);
    if (status == MK_OK) {
        mk_resolution_clear(&entry);
        out->valid_prefix_bytes = strlen(utf8_grapheme);
        out->offending_offset = out->valid_prefix_bytes;
        return MK_OK;
    }
    out->status = status;

    len = strlen(utf8_grapheme);
    /* Walk the character boundaries forward and remember the last prefix that
     * resolved. Forward rather than backward because the answer is usually
     * short: one base letter and a mark or two, so the loop stops early on the
     * common case instead of retrying the whole string first. */
    cut = 0;
    while (cut < len) {
        size_t step = mk_utf8_step(utf8_grapheme + cut);
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
        if (mk_resolve(system, prefix, &entry) == MK_OK) {
            mk_resolution_clear(&entry);
            best = next;
        }
        free(prefix);
        cut = next;
    }

    out->valid_prefix_bytes = best;
    out->offending_offset = best;
    if (best < len) {
        size_t step = mk_utf8_step(utf8_grapheme + best);

        if (step > 0 && best + step <= len && step < sizeof(out->offending)) {
            memcpy(out->offending, utf8_grapheme + best, step);
            out->offending[step] = '\0';
        }
    }
    return MK_OK;
}
