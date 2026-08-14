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

    /* The bytes go in as they are. The harness used to copy them into a
     * NUL-terminated buffer because that was the only entry point; feeding the
     * length-taking form directly means libFuzzer's own redzoned allocation is
     * what the parser reads, so a read one byte past the input is a report
     * rather than a read into the harness's spare terminator.
     *
     * It also gets embedded NUL bytes into the parser, which the copy could
     * never express. */
    if (mki_parse_model_text_n((const char *)data, size, &model, &diagnostic) == MK_OK) {
        mki_parsed_model_clear(&model);
    }
    free(diagnostic);
    return 0;
}
