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
    mki_parsed_model model;
    char *diagnostic = NULL;

    /* The bytes go in as they are, through the length-taking form, rather than
     * copied into a NUL-terminated buffer: libFuzzer's own redzoned allocation
     * is then what the parser reads, so a read one byte past the input is a
     * report rather than a read into a spare terminator. It also gets embedded
     * NUL bytes into the parser, which a C-string copy could never express. */
    if (mki_parse_model_text_n((const char *)data, size, &model, &diagnostic) == MK_OK) {
        mki_parsed_model_clear(&model);
    }
    free(diagnostic);
    return 0;
}
