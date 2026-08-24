/* Tests the scoring seam directly.
 *
 * Which scorer a system reaches used to be decided in two places on two
 * different fields: a `kind` test in system.c chose categorical against valued,
 * and a test on `scalar_dimension_count` inside the categorical body chose
 * scalar against leaf. The second was invisible from geometry.h and it was the
 * one that picked the scorer for `distinctive`, the default system. These cases
 * assert which scorer a system selects, so a change that quietly moves a system
 * from one to another fails here rather than passing unnoticed.
 *
 * The second half covers mk_system_segment_distance_ex, which had no C test at
 * all: its only coverage was through the Python wrapper. */

#include "geometry.h"
#include "merkmal.h"
#include "system.h"

#include <stdio.h>
#include <string.h>

static int failures = 0;

static void fail(const char *what, const char *detail)
{
    printf("FAIL %s: %s\n", what, detail);
    failures++;
}

typedef struct scorer_case {
    const char *system;
    const char *scorer;
} scorer_case;

/* Every compiled-in system, and the scorer it is scored by. `distinctive` is
 * the only one carrying scalar dimensions of its own; the other categorical
 * system and every runtime model fall to leaf. */
static const scorer_case scorer_cases[] = {
    { "descriptive", "leaf" },
    { "distinctive", "scalar" },
    { "phoible", "valued" },
    { "pbase-hc", "valued" },
    { "pbase-jfh", "valued" },
    { "pbase-spe", "valued" },
    { "pbase-uftc", "valued" }
};

static void check_selection(mk_registry *registry)
{
    size_t i;

    for (i = 0; i < sizeof(scorer_cases) / sizeof(scorer_cases[0]); i++) {
        const mk_system *system = NULL;
        const char *got;

        if (mk_registry_get_system(registry, scorer_cases[i].system, &system) != MK_OK) {
            fail(scorer_cases[i].system, "system not found");
            continue;
        }
        got = mki_scorer_name(mki_scorer_for(system->builtin));
        if (strcmp(got, scorer_cases[i].scorer) != 0) {
            char detail[128];
            snprintf(detail, sizeof(detail), "expected %s, got %s",
                scorer_cases[i].scorer, got);
            fail(scorer_cases[i].system, detail);
        }
    }
}

/* mk_sound_distance scores against the compiled geometry with no system at all,
 * so the selector has to answer for a NULL one rather than leaving the caller
 * to special-case it. A NULL system can never select valued, which is the
 * scorer that would read a geometry map it does not have. */
static void check_null_system_selects_leaf(void)
{
    mki_scorer scorer = mki_scorer_for(NULL);

    if (strcmp(mki_scorer_name(scorer), "leaf") != 0) {
        fail("null system", "did not select leaf");
    }
}

/* A runtime model declares no scalar dimensions, so it is scored by leaf like
 * the compiled categorical system that declares none. */
static void check_runtime_model_selects_leaf(void)
{
    static const char model[] =
        "@model toy\n"
        "@type categorical\n"
        "@geometry clements-hume\n"
        "grapheme X consonant voiceless bilabial stop\n";
    mk_registry *registry = NULL;
    const mk_system *system = NULL;

    if (mk_registry_new_builtin(&registry) != MK_OK) {
        fail("runtime model", "registry");
        return;
    }
    if (mk_registry_add_model_text(registry, model) != MK_OK) {
        fail("runtime model", "add_model_text");
        mk_registry_free(registry);
        return;
    }
    if (mk_registry_get_system(registry, "toy", &system) != MK_OK) {
        fail("runtime model", "get_system");
        mk_registry_free(registry);
        return;
    }
    if (strcmp(mki_scorer_name(mki_scorer_for(system->builtin)), "leaf") != 0) {
        fail("runtime model", "did not select leaf");
    }
    mk_registry_free(registry);
}

static void check_coverage(mk_registry *registry)
{
    const mk_system *phoible = NULL;
    const mk_system *descriptive = NULL;
    const mk_system *distinctive = NULL;
    double score;
    double coverage;
    mk_comparability why;

    if (mk_registry_get_system(registry, "phoible", &phoible) != MK_OK ||
        mk_registry_get_system(registry, "descriptive", &descriptive) != MK_OK ||
        mk_registry_get_system(registry, "distinctive", &distinctive) != MK_OK) {
        fail("coverage", "system not found");
        return;
    }

    /* A segment against itself is not fully covered. A valued system skips the
     * dimensions the segment leaves unset, and PHOIBLE's /p/ leaves 11 of its
     * 38 cells at `.`. This answered 1.0 until the identity shortcut stopped
     * speaking for the scorer: that 1.0 was coverage relative to the segment,
     * where the documented quantity is relative to the system's dimensions. */
    if (mk_system_segment_distance_ex(
            phoible, "p", "p", NULL, &score, &coverage, &why) != MK_OK) {
        fail("phoible p/p", "status");
    } else {
        if (score != 0.0) {
            fail("phoible p/p", "score is not 0.0");
        }
        if (!(coverage > 0.0 && coverage < 1.0)) {
            char detail[128];
            snprintf(detail, sizeof(detail),
                "expected partial coverage, got %.10f", coverage);
            fail("phoible p/p", detail);
        }
        if (why != MK_CMP_OK) {
            fail("phoible p/p", "why is not MK_CMP_OK");
        }
    }

    /* The same pair without asking for coverage takes the identity shortcut,
     * and both routes must agree on the score. */
    if (mk_system_segment_distance(phoible, "p", "p", &score) != MK_OK || score != 0.0) {
        fail("phoible p/p", "shortcut disagrees with the scorer");
    }

    /* PHOIBLE's tone letters carry `.` on every dimension, so there is nothing
     * to compare against a segment. Same tier, no shared dimension. */
    if (mk_system_segment_distance_ex(
            phoible, "˦˨", "d", NULL, &score, &coverage, &why) != MK_OK) {
        fail("phoible tone/d", "status");
    } else if (coverage != 0.0 || why != MK_CMP_NO_SHARED_DIMENSION) {
        fail("phoible tone/d", "expected zero coverage and no-shared-dimension");
    }

    /* Both categorical scorers weigh any dimension either segment sets, so an
     * ordinary pair is fully covered. leaf answers for descriptive, scalar for
     * distinctive, and they report coverage the same way. */
    if (mk_system_segment_distance_ex(
            descriptive, "p", "b", NULL, &score, &coverage, &why) != MK_OK ||
        coverage != 1.0 || why != MK_CMP_OK) {
        fail("descriptive p/b", "expected full coverage");
    }
    if (mk_system_segment_distance_ex(
            distinctive, "p", "b", NULL, &score, &coverage, &why) != MK_OK ||
        coverage != 1.0 || why != MK_CMP_OK) {
        fail("distinctive p/b", "expected full coverage");
    }

    /* Coverage is the reason this entry point exists, so it is required rather
     * than optional -- unlike `why`, which may be NULL. */
    if (mk_system_segment_distance_ex(
            phoible, "p", "b", NULL, &score, NULL, &why) != MK_ERR_INVALID_ARGUMENT) {
        fail("null coverage", "expected MK_ERR_INVALID_ARGUMENT");
    }
    if (mk_system_segment_distance_ex(
            phoible, "p", "b", NULL, &score, &coverage, NULL) != MK_OK) {
        fail("null why", "why must stay optional");
    }
}

int main(void)
{
    mk_registry *registry = NULL;

    if (mk_registry_new_builtin(&registry) != MK_OK) {
        printf("FAIL: could not create registry\n");
        return 1;
    }

    check_selection(registry);
    check_null_system_selects_leaf();
    check_runtime_model_selects_leaf();
    check_coverage(registry);

    mk_registry_free(registry);
    if (failures > 0) {
        printf("%d scoring check(s) failed\n", failures);
        return 1;
    }
    printf("scoring tests passed\n");
    return 0;
}
