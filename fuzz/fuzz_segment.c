/* Tokenization and normalization over arbitrary bytes.
 *
 * These take transcription text from wherever the caller got it, so malformed
 * UTF-8 is an input rather than an accident. A truncated sequence used to be
 * read past its end here. */

#include "merkmal.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
    mk_string_list *segments = NULL;
    char *normalized = NULL;
    char *base = NULL;
    char *tone = NULL;
    char *text;

    text = (char *)malloc(size + 1);
    if (text == NULL) {
        return 0;
    }
    memcpy(text, data, size);
    text[size] = '\0';

    if (mk_segment_ipa(text, &segments) == MK_OK) {
        mk_string_list *merged = NULL;
        if (mk_merge_tone_digits(segments, &merged) == MK_OK) {
            mk_string_list_free(merged);
        }
        mk_string_list_free(segments);
    }

    if (mk_segment_ipa_merged(text, &segments) == MK_OK) {
        mk_string_list_free(segments);
    }

    if (mk_normalize_grapheme(text, &normalized) == MK_OK) {
        mk_free_string(normalized);
    }

    if (mk_split_tone(text, &base, &tone) == MK_OK) {
        mk_free_string(base);
        mk_free_string(tone);
    }

    free(text);
    return 0;
}
