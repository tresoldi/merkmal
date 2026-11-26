#ifndef MK_MODEL_TEXT_H
#define MK_MODEL_TEXT_H

/* The runtime-model text format: parsing caller-supplied text into inventory
 * rows, and validating them.
 *
 * This is the library's only parser of untrusted input, which is why it is its
 * own module: it can be exercised -- and fuzzed -- without a registry, and the
 * registry does not have to carry a line-oriented parser to hold a list of
 * systems. See docs/guide/runtime-model-format.md for the format itself. */

#include "generated/builtin_data.h"
#include "merkmal.h"

#include <stddef.h>

/* A parsed model, before it is installed into a registry. On MK_OK the caller
 * owns `name` and `entries` and releases them with mki_parsed_model_clear;
 * mki_parse_model_text leaves nothing allocated in it on failure. */
typedef struct mki_parsed_model {
    char *name;
    mki_builtin_entry *entries;
    size_t entry_count;
} mki_parsed_model;

/* Parses and validates `model_text`.
 *
 * Validation is strict unless the text says '@validation permissive'.
 * `diagnostic` may be NULL when the caller does not want the detail; otherwise
 * *diagnostic must be NULL on entry, is left NULL on success, and on failure
 * usually receives an owned message naming the offending line and token. Not
 * every failure has one: an unsupported @type and most allocation failures
 * leave it NULL.
 *
 * `out` is zeroed before any work unless `out` or `model_text` is NULL.
 *
 * Returns MK_ERR_INVALID_ARGUMENT for a NULL `out` or `model_text`,
 * MK_ERR_PARSE for malformed or invalid text, MK_ERR_UNSUPPORTED_MODEL for a
 * model whose @type or @geometry this implementation has no engine for, and
 * MK_ERR_OOM on allocation failure. */
mk_status mki_parse_model_text(
    const char *model_text,
    mki_parsed_model *out,
    char **diagnostic
);

/* As above, for input that is not NUL-terminated. `model_text_length` is in
 * bytes and `model_text` need not be readable past it.
 *
 * An embedded NUL is MK_ERR_PARSE. The parser splits lines with strchr on its
 * own copy, so a NUL in the middle would silently end the model early and
 * register whatever had been read so far -- a truncated inventory that looks
 * like a successful one. Refusing is the only answer that cannot be mistaken
 * for success.
 *
 * mki_parse_model_text is this function with strlen for the length. */
mk_status mki_parse_model_text_n(
    const char *model_text,
    size_t model_text_length,
    mki_parsed_model *out,
    char **diagnostic
);

/* Frees whatever a parsed model owns and zeroes it. Safe on a zeroed struct,
 * and safe to call twice. */
void mki_parsed_model_clear(mki_parsed_model *model);

#endif
