/* Segment resolution against every built-in system.
 *
 * Resolution is where the synthesizers live -- diacritic composition, clusters,
 * complex segments -- and they build feature labels from the input, so this is
 * the harness that exercises the most code per byte.
 *
 * The registry is built once and reused: it is immutable after construction,
 * and rebuilding it per input would spend the whole run in setup. */

#include "merkmal.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

static mk_registry *registry;

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
    mk_string_list *names = NULL;
    char *text;
    size_t i;

    if (registry == NULL && mk_registry_new_builtin(&registry) != MK_OK) {
        return 0;
    }
    if (mk_registry_list_systems(registry, &names) != MK_OK) {
        return 0;
    }

    text = (char *)malloc(size + 1);
    if (text == NULL) {
        mk_string_list_free(names);
        return 0;
    }
    memcpy(text, data, size);
    text[size] = '\0';

    for (i = 0; i < mk_string_list_size(names); i++) {
        const mk_system *system = NULL;
        mk_string_list *features = NULL;
        mk_string_list *tokens = NULL;
        double distance = 0.0;
        bool is_segment = false;

        if (mk_registry_get_system(registry, mk_string_list_get(names, i), &system) != MK_OK) {
            continue;
        }
        mk_system_is_segment(system, text, &is_segment);
        if (mk_system_grapheme_features(system, text, &features) == MK_OK) {
            mk_string_list_free(features);
        }
        /* Against a segment every system has, so the pair path runs even when
         * the input itself does not resolve. */
        mk_system_segment_distance(system, text, "a", &distance);
        if (mk_system_segment_ipa(system, text, &tokens) == MK_OK) {
            mk_string_list_free(tokens);
        }
    }

    mk_string_list_free(names);
    free(text);
    return 0;
}
