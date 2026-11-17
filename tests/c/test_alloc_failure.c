/* Allocation failure, at every allocation, in the entry points whose cleanup
 * paths are otherwise unreachable.
 *
 * malloc, calloc and realloc are wrapped at link time (-Wl,--wrap, so Linux
 * only; see CMakeLists.txt). For each operation the test fails allocation 0,
 * then 1, then 2, ... until a run completes without reaching the failure
 * point. Every run must return MK_OK or MK_ERR_OOM. Under the address
 * sanitizer a crash, double free or leak on any of those paths fails the test.
 *
 * Guards against mk_system_segment_ipa freeing its orthographic tokens twice
 * when the final list allocation fails, and against the cluster synthesizer
 * leaking a parsed component ("kpa", "pʰa", "mbu", "tsʰo") when recording it
 * fails. */
#include "merkmal.h"
#include "profile.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void *__real_malloc(size_t size);
void *__real_calloc(size_t count, size_t size);
void *__real_realloc(void *ptr, size_t size);
void *__wrap_malloc(size_t size);
void *__wrap_calloc(size_t count, size_t size);
void *__wrap_realloc(void *ptr, size_t size);

/* -1: never fail. Otherwise the zero-based allocation to fail. */
static long fail_at = -1;
static long seen = 0;

static int should_fail(void)
{
    return fail_at >= 0 && seen++ == fail_at;
}

void *__wrap_malloc(size_t size)
{
    return should_fail() ? NULL : __real_malloc(size);
}

void *__wrap_calloc(size_t count, size_t size)
{
    return should_fail() ? NULL : __real_calloc(count, size);
}

void *__wrap_realloc(void *ptr, size_t size)
{
    return should_fail() ? NULL : __real_realloc(ptr, size);
}

static const mk_system *descriptive = NULL;
static const mk_system *phoible = NULL;

static const char toy_model[] =
    "@model toy\n"
    "@type categorical\n"
    "@geometry clements-hume\n"
    "# a comment\n"
    "feature readability row\n"
    "grapheme X consonant voiceless bilabial stop\n"
    "grapheme Y consonant voiced bilabial stop\n"
    "grapheme Z consonant voiced alveolar nasal\n";

enum { OP_COUNT = 7 };

static const char *const op_names[OP_COUNT] = {
    "mk_segment_ipa",
    "mk_system_segment_ipa (descriptive)",
    "mk_system_segment_ipa (phoible)",
    "mk_system_segment_distance_ex (diphthong)",
    "mk_system_segment_distance_ex (phoible)",
    "mk_system_segment_distance_ex (cross-tier)",
    "mk_registry_add_model_text_n"
};

static mk_status run(int op)
{
    mk_string_list *list = NULL;
    mk_status status = MK_OK;
    double distance = 0.0;
    double coverage = 0.0;
    mk_comparability why = MK_CMP_OK;

    switch (op) {
    case 0:
        status = mk_segment_ipa("t͡ʃa pʰa¹² kʷe + ŋ̊ɔ̃ː", &list);
        break;
    case 1:
        status = mk_system_segment_ipa(descriptive, "tʃa kpa mbu aiu³³ pʰa tsʰo t͡sɛ", &list);
        break;
    case 2:
        status = mk_system_segment_ipa(phoible, "tʃa pʰa ŋ", &list);
        break;
    case 3:
        status = mk_system_segment_distance_ex(
            descriptive, "ai³³", "au", NULL, &distance, &coverage, &why);
        break;
    case 4:
        status = mk_system_segment_distance_ex(
            phoible, "p", "b", NULL, &distance, &coverage, &why);
        break;
    case 5:
        status = mk_system_segment_distance_ex(
            descriptive, "a", "³³", NULL, &distance, &coverage, &why);
        break;
    default: {
        /* The registry is built with allocation failure off: what is under
         * test is the parse and the registration, not the built-in setup. */
        mk_registry *registry = NULL;
        char *diagnostic = NULL;
        long saved = fail_at;

        fail_at = -1;
        if (mk_registry_new_builtin(&registry) != MK_OK) {
            return MK_ERR_INVALID_ARGUMENT;
        }
        fail_at = saved;
        status = mk_registry_add_model_text_n(
            registry, toy_model, sizeof(toy_model) - 1, &diagnostic);
        fail_at = -1;
        mk_string_free(diagnostic);
        mk_registry_free(registry);
        fail_at = saved;
        break;
    }
    }
    mk_string_list_free(list);
    return status;
}

int main(void)
{
    mk_registry *registry = NULL;
    int failures = 0;
    int op;

    if (mk_registry_new_builtin(&registry) != MK_OK ||
        mk_registry_get_system(registry, "descriptive", &descriptive) != MK_OK) {
        fprintf(stderr, "FAIL: setup\n");
        return 1;
    }
    /* PHOIBLE is not in the cc-by profile; its operations reuse descriptive. */
    if (profile_lacks_system(registry, "phoible")) {
        phoible = descriptive;
    } else if (mk_registry_get_system(registry, "phoible", &phoible) != MK_OK) {
        fprintf(stderr, "FAIL: phoible\n");
        return 1;
    }

    for (op = 0; op < OP_COUNT; op++) {
        long n;
        int completed = 0;

        for (n = 0; !completed && n < 100000; n++) {
            mk_status status;

            fail_at = n;
            seen = 0;
            status = run(op);
            fail_at = -1;
            /* Fewer allocations than n: the injected failure never happened. */
            completed = seen <= n;
            if (completed && status != MK_OK) {
                fprintf(stderr, "FAIL: %s: clean run returned %s\n",
                        op_names[op], mk_status_string(status));
                failures++;
            } else if (!completed && status != MK_OK && status != MK_ERR_OOM) {
                fprintf(stderr, "FAIL: %s: allocation %ld failed and it returned %s\n",
                        op_names[op], n, mk_status_string(status));
                failures++;
            }
        }
        if (!completed) {
            fprintf(stderr, "FAIL: %s: never completed\n", op_names[op]);
            failures++;
        }
    }

    mk_registry_free(registry);
    if (failures == 0) {
        printf("alloc_failure: ok\n");
    }
    return failures == 0 ? 0 : 1;
}
