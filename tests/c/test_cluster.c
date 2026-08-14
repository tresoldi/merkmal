/* Tests the cluster seam directly.
 *
 * A cluster is a segment written as more than one part -- a diphthong, an
 * untied affricate, a geminate. Scoring one is a composition policy with five
 * stipulated numbers behind it, and until this file the only way to reach any
 * of it was a public distance call, which reports one double and says nothing
 * about how the parts contributed.
 *
 * The first half asserts the thing that makes the seam work: a resolved cluster
 * carries its parts' features, so scoring never resolves a spelling twice. The
 * second half asserts the composition rules those features feed. */

#include "cluster.h"
#include "merkmal.h"
#include "resolver.h"
#include "strings.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

static int failures = 0;

static void fail(const char *what, const char *detail)
{
    printf("FAIL %s: %s\n", what, detail);
    failures++;
}

static const mk_system *system_named(mk_registry *registry, const char *name)
{
    const mk_system *system = NULL;

    if (mk_registry_get_system(registry, name, &system) != MK_OK) {
        fail(name, "system not found");
        return NULL;
    }
    return system;
}

/* The parts a cluster resolved from must arrive carrying features. When they
 * carried only a spelling, scoring re-ran the whole resolution seam on each of
 * them -- up to six times for one comparison of two clusters. */
static void check_parts_carry_features(const mk_system *system)
{
    static const char *const spellings[] = { "ai", "au", "aa", "iau" };
    size_t s;

    for (s = 0; s < sizeof(spellings) / sizeof(spellings[0]); s++) {
        mk_resolution resolved;
        size_t i;

        if (mki_resolve(system, spellings[s], &resolved) != MK_OK) {
            fail(spellings[s], "did not resolve");
            continue;
        }
        if (resolved.cluster_component_count < 2) {
            fail(spellings[s], "resolved with fewer than two parts");
            mki_resolution_clear(&resolved);
            continue;
        }
        for (i = 0; i < resolved.cluster_component_count; i++) {
            const mk_cluster_component *part = &resolved.cluster_components[i];
            mk_feature_view view = mki_view_of_component(part);

            if (part->grapheme == NULL || part->grapheme[0] == '\0') {
                fail(spellings[s], "a part has no spelling");
            }
            if (view.count == 0 || view.features == NULL) {
                fail(spellings[s], "a part carries no features");
            }
            /* Exactly one storage half is set, the rule resolver.h states. */
            if ((part->owned_features == NULL) == (part->borrowed_features == NULL)) {
                fail(spellings[s], "a part's storage halves are both or neither");
            }
            if (part->features != (const char *const *)part->owned_features &&
                part->features != (const char *const *)part->borrowed_features) {
                fail(spellings[s], "a part's features alias neither half");
            }
        }
        mki_resolution_clear(&resolved);
    }
}

/* The five numbers are the geometry file's, not a tree edit's. */
static void check_policy_is_data(void)
{
    if (!(fabs(mki_clements_hume_cluster_nucleus_share - 0.7) < 1e-12) ||
        !(fabs(mki_clements_hume_cluster_offglide_share - 0.3) < 1e-12) ||
        !(fabs(mki_clements_hume_cluster_length_penalty - 0.15) < 1e-12) ||
        !(fabs(mki_clements_hume_cluster_component_share - 0.8) < 1e-12) ||
        !(fabs(mki_clements_hume_cluster_segment_share - 0.2) < 1e-12)) {
        fail("cluster policy", "the compiled shares are not the declared ones");
    }
    if (fabs(mki_clements_hume_cluster_component_share +
             mki_clements_hume_cluster_segment_share - 1.0) > 1e-12) {
        fail("cluster policy", "component and segment shares do not sum to 1");
    }
    if (fabs(mki_clements_hume_cluster_nucleus_share +
             mki_clements_hume_cluster_offglide_share - 1.0) > 1e-12) {
        fail("cluster policy", "nucleus and offglide shares do not sum to 1");
    }
}

static int distance(const mk_system *system, const char *a, const char *b, double *out)
{
    if (mk_system_segment_distance(system, a, b, out) != MK_OK) {
        fail(a, "distance failed");
        return 0;
    }
    return 1;
}

static void check_composition(const mk_system *system)
{
    double ai_au;
    double ai_a;
    double au_ai;
    double self;
    double aa_long;
    double aa_short;

    /* A cluster against itself is zero, and the score does not depend on which
     * side is which. */
    if (distance(system, "ai", "ai", &self) && self != 0.0) {
        fail("ai/ai", "a cluster is not zero against itself");
    }
    if (distance(system, "ai", "au", &ai_au) &&
        distance(system, "au", "ai", &au_ai) &&
        fabs(ai_au - au_ai) > 1e-12) {
        fail("ai/au", "not symmetric");
    }

    /* Two clusters sharing a nucleus and differing on the offglide are closer
     * than a cluster is to a plain segment, which pays the extra-part penalty. */
    if (distance(system, "ai", "a", &ai_a) && !(ai_au < ai_a)) {
        fail("ai/au vs ai/a", "sharing a nucleus is not closer than losing a part");
    }

    /* The length penalty is waived when a geminate meets a segment that spells
     * the length out, and charged when it meets one that does not. `aa` against
     * `aː` is the pair the waiver exists for. */
    if (distance(system, "aa", "aː", &aa_long) &&
        distance(system, "aa", "a", &aa_short) &&
        !(aa_long < aa_short)) {
        fail("aa/aː", "the length penalty was not waived against a long vowel");
    }
}

/* Geminacy is decided from the parts' features, not from their spellings.
 *
 * The two rules agree on every pair of distinct inventory segments. They differ
 * only where a mark is redundant -- a nasal vowel written with a second nasal
 * mark resolves to the features of one nasal vowel -- and that pair is one
 * segment written twice, which is what a geminate is. It is the only observable
 * difference between the rules, so it is what a revert to byte comparison would
 * fail on. */
static void check_geminacy_is_featural(const mk_system *system)
{
    static const struct {
        const char *token;
        int geminate;
        const char *why;
    } cases[] = {
        { "aa", 1, "one segment written twice" },
        { "ai", 0, "two different vowels" },
        { "au", 0, "two different vowels" },
        /* A creaky ultra-long /a/ against the same vowel with the creaky mark
         * written a second time: "a" U+0330 U+02D0 U+02D0, then the same with a
         * second U+0330. Different bytes, nine identical features. Spelled out
         * in escapes because stacked combining marks render ambiguously, and
         * this case only means anything if the bytes are exact. */
        { "a\xcc\xb0\xcb\x90\xcb\x90" "a\xcc\xb0\xcb\x90\xcb\x90\xcc\xb0", 1,
          "a redundant mark does not make it a different segment" },
    };
    size_t i;

    for (i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
        mk_resolution resolved;
        int geminate;

        if (mki_resolve(system, cases[i].token, &resolved) != MK_OK) {
            fail(cases[i].token, "did not resolve");
            continue;
        }
        if (resolved.cluster_component_count != 2) {
            fail(cases[i].token, "did not resolve to two parts");
            mki_resolution_clear(&resolved);
            continue;
        }
        geminate = mki_features_contain(
            resolved.features, resolved.feature_count, "geminate");
        if (geminate != cases[i].geminate) {
            fail(cases[i].why, cases[i].geminate ?
                "expected geminate" : "expected not geminate");
        }
        mki_resolution_clear(&resolved);
    }
}

/* mki_cluster_distance is reached with two plain segments only through a
 * caller's mistake, and answers rather than reading past a component array
 * that is not there. */
static void check_two_plain_segments(const mk_system *system)
{
    mk_resolution a;
    mk_resolution b;
    double out = -1.0;

    if (mki_resolve(system, "p", &a) != MK_OK || mki_resolve(system, "b", &b) != MK_OK) {
        fail("plain segments", "did not resolve");
        return;
    }
    if (mki_cluster_distance(system, &a, &b, NULL, &out) != MK_OK || out != 1.0) {
        fail("plain segments", "expected 1.0 for a pair with no parts");
    }
    if (mki_cluster_distance(NULL, &a, &b, NULL, &out) != MK_ERR_INVALID_ARGUMENT) {
        fail("plain segments", "a NULL system should be rejected");
    }
    mki_resolution_clear(&a);
    mki_resolution_clear(&b);
}

int main(void)
{
    mk_registry *registry = NULL;
    const mk_system *descriptive;

    if (mk_registry_new_builtin(&registry) != MK_OK) {
        printf("FAIL: could not create registry\n");
        return 1;
    }
    descriptive = system_named(registry, "descriptive");
    if (descriptive != NULL) {
        check_parts_carry_features(descriptive);
        check_composition(descriptive);
        check_geminacy_is_featural(descriptive);
        check_two_plain_segments(descriptive);
    }
    check_policy_is_data();

    mk_registry_free(registry);
    if (failures > 0) {
        printf("%d cluster check(s) failed\n", failures);
        return 1;
    }
    printf("cluster tests passed\n");
    return 0;
}
