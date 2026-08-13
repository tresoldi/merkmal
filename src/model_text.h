#ifndef MK_MODEL_TEXT_H
#define MK_MODEL_TEXT_H

/* The runtime-model text format: parsing caller-supplied text into inventory
 * rows, and validating them.
 *
 * This is the library's only parser of untrusted input, which is why it is its
 * own module: it can be exercised -- and fuzzed -- without a registry, and the
 * registry does not have to carry a line-oriented parser to hold a list of
 * systems. See docs/runtime-model-format.md for the format itself. */

#include "generated/builtin_data.h"
#include "merkmal.h"

#include <stddef.h>

/* A parsed model, before it is installed into a registry. On MK_OK the caller
 * owns `name` and `entries` and releases them with mk_parsed_model_clear;
 * mk_parse_model_text leaves nothing allocated on failure. */
typedef struct mk_parsed_model {
    char *name;
    mk_builtin_entry *entries;
    size_t entry_count;
} mk_parsed_model;

/* Parses and validates `model_text`.
 *
 * Validation is strict unless the text says '@validation permissive'. On
 * failure *diagnostic receives an owned message naming the offending line and
 * token; it is NULL on success, and `diagnostic` itself may be NULL when the
 * caller does not want the detail.
 *
 * Returns MK_ERR_PARSE for malformed or invalid text, MK_ERR_UNSUPPORTED_MODEL
 * for a model whose @type this implementation does not have an engine for, and
 * MK_ERR_OOM on allocation failure. */
mk_status mk_parse_model_text(
    const char *model_text,
    mk_parsed_model *out,
    char **diagnostic
);

/* Frees whatever a parsed model owns and zeroes it. Safe on a zeroed struct,
 * and safe to call twice. */
void mk_parsed_model_clear(mk_parsed_model *model);

#endif
