/* The runtime-model parser: the library's only parser of caller-supplied text.
 *
 * It runs without a registry, which is why model_text.c exists as its own
 * module -- a harness that had to build a registry first would be fuzzing the
 * registry too. */

#include "model_text.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
    mk_parsed_model model;
    char *diagnostic = NULL;
    char *text;

    /* The API takes a NUL-terminated string, so the harness supplies one. A
     * heap copy sized to the input is what lets ASan see a read past the end. */
    text = (char *)malloc(size + 1);
    if (text == NULL) {
        return 0;
    }
    memcpy(text, data, size);
    text[size] = '\0';

    if (mk_parse_model_text(text, &model, &diagnostic) == MK_OK) {
        mk_parsed_model_clear(&model);
    }
    free(diagnostic);
    free(text);
    return 0;
}
