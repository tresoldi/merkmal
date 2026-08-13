/* What resolution costs, and how much of it is the inventory scan.
 *
 * mk_inventory_find walks every row calling mk_streq -- up to 9,728 string
 * comparisons for a miss, and the longest-match tokenizer issues several
 * lookups per token. Whether that is worth replacing with a binary search is a
 * question about measured share of time, not about the shape of the loop, so
 * this reports the whole operation and the scan separately.
 *
 * Built by bench/bench_lookup.sh against the library sources, because
 * mk_inventory_find is internal.
 *
 * C99 clock() is used rather than clock_gettime so the benchmark builds
 * wherever the library does. It measures CPU time, which is what is wanted
 * here, and the loops run long enough that its resolution does not matter. */

#include "inventory.h"
#include "merkmal.h"
#include "system.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* A transcription corpus stands in for the real workload: tokenizing and
 * scoring wordlists is what a caller at corpus scale does. These are ordinary
 * IPA words, deliberately mixing segments that hit the inventory directly with
 * ones that need a synthesizer. */
static const char *const words[] = {
    "kʰɑtʰa", "tʃiŋ", "mbaŋga", "pʰoːl", "ǃxũː",
    "swɛːt", "jɑrɪk", "ndzuma", "ɸaɾu", "tsʰɤŋ",
    "aiwa", "koŋ⁵⁵", "ʔabu", "ɡʷent", "ʈʂʰən",
    "θriː", "lɔŋgi", "ɲaha", "qχaba", "wuːðr"
};
#define WORD_COUNT (sizeof(words) / sizeof(words[0]))

static double seconds_since(clock_t start)
{
    return (double)(clock() - start) / (double)CLOCKS_PER_SEC;
}

int main(void)
{
    mk_registry *registry = NULL;
    const mk_system *system = NULL;
    const char *scratch[MK_MAX_ENTRY_FEATURES];
    mk_entry_view view;
    clock_t start;
    double elapsed;
    size_t i;
    size_t round;
    size_t rounds;
    size_t tokens = 0;
    size_t pairs = 0;
    size_t lookups = 0;

    if (mk_registry_new_builtin(&registry) != MK_OK ||
        mk_registry_get_system(registry, "descriptive", &system) != MK_OK) {
        fprintf(stderr, "could not build the registry\n");
        return 1;
    }

    printf("corpus: %zu words, system: descriptive, inventory: %zu rows\n\n",
           (size_t)WORD_COUNT, system->builtin->entry_count);

    /* 1. System-aware tokenization: longest match, so several lookups per
     *    token, which is the case the scan cost compounds in. */
    rounds = 200;
    start = clock();
    for (round = 0; round < rounds; round++) {
        for (i = 0; i < WORD_COUNT; i++) {
            mk_string_list *out = NULL;
            if (mk_system_segment_ipa(system, words[i], &out) == MK_OK) {
                tokens += mk_string_list_size(out);
                mk_string_list_free(out);
            }
        }
    }
    elapsed = seconds_since(start);
    printf("tokenize      %8.3f s for %8zu tokens   %8.1f us/token\n",
           elapsed, tokens, elapsed * 1e6 / (double)tokens);

    /* 2. Scoring pairs, which resolves two graphemes per call. */
    rounds = 400;
    start = clock();
    for (round = 0; round < rounds; round++) {
        for (i = 0; i + 1 < WORD_COUNT; i++) {
            double distance = 0.0;
            char a[8];
            char b[8];

            /* One segment each, so this measures resolve-and-score rather
             * than tokenization. */
            memcpy(a, "p", 2);
            memcpy(b, "b", 2);
            a[0] = (char)('a' + (int)(i % 26));
            b[0] = (char)('a' + (int)((i + 3) % 26));
            if (mk_system_segment_distance(system, a, b, &distance) == MK_OK) {
                pairs++;
            }
        }
    }
    elapsed = seconds_since(start);
    printf("distance      %8.3f s for %8zu pairs    %8.1f us/pair\n",
           elapsed, pairs, elapsed * 1e6 / (double)pairs);

    /* 3. The scan alone, on a miss -- the worst case, and the one a binary
     *    search would help most. A hit stops early and is cheaper. */
    rounds = 20000;
    start = clock();
    for (round = 0; round < rounds; round++) {
        if (mk_inventory_find(system->builtin, "\xef\xbf\xbd-absent", scratch, &view)) {
            fprintf(stderr, "the miss key unexpectedly hit\n");
            return 1;
        }
        lookups++;
    }
    elapsed = seconds_since(start);
    printf("scan (miss)   %8.3f s for %8zu lookups  %8.1f us/lookup\n",
           elapsed, lookups, elapsed * 1e6 / (double)lookups);

    lookups = 0;
    rounds = 20000;
    start = clock();
    for (round = 0; round < rounds; round++) {
        if (!mk_inventory_find(system->builtin, "p", scratch, &view)) {
            fprintf(stderr, "the hit key unexpectedly missed\n");
            return 1;
        }
        lookups++;
    }
    elapsed = seconds_since(start);
    printf("scan (hit)    %8.3f s for %8zu lookups  %8.1f us/lookup\n",
           elapsed, lookups, elapsed * 1e6 / (double)lookups);

    mk_registry_free(registry);
    return 0;
}
