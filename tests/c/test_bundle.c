/* Abstract segments through the public API only. The exhaustive checks --
 * bundles from graphemes score as the graphemes do in every system, and the
 * bounds equal brute-force enumeration -- run in the Python suite, which can
 * walk the inventories; this one pins the contract a C consumer sees. */
#include "merkmal.h"

#include <math.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>

static int failures = 0;

static void check(int ok, const char *label)
{
    if (!ok) {
        fprintf(stderr, "FAIL: %s\n", label);
        failures++;
    }
}

static void check_grapheme_parity(const mk_system *system, const char *a, const char *b)
{
    mk_bundle *ba = NULL;
    mk_bundle *bb = NULL;
    mk_bundle_comparison cmp;
    double expected = -1.0;
    double coverage = -1.0;
    char label[96];

    snprintf(label, sizeof(label), "parity %s/%s", a, b);
    check(mk_bundle_from_grapheme(system, a, &ba) == MK_OK, label);
    check(mk_bundle_from_grapheme(system, b, &bb) == MK_OK, label);
    check(mk_bundle_compare(ba, bb, NULL, &cmp) == MK_OK, label);
    check(mk_system_segment_distance_ex(system, a, b, NULL, &expected, &coverage, NULL) == MK_OK, label);
    check(fabs(cmp.distance - expected) < 1e-12, label);
    check(fabs(cmp.coverage - coverage) < 1e-12, label);
    check(cmp.minimum == cmp.distance && cmp.maximum == cmp.distance, label);
    mk_bundle_free(ba);
    mk_bundle_free(bb);
}

int main(void)
{
    mk_registry *registry = NULL;
    const mk_system *descriptive = NULL;
    const mk_system *distinctive = NULL;
    const mk_system *phoible = NULL;
    mk_bundle *h = NULL;
    mk_bundle *round_trip = NULL;
    mk_bundle *empty = NULL;
    mk_bundle_comparison cmp;
    mk_string_list *compatible = NULL;
    char *text = NULL;
    char *again = NULL;
    char *cell = NULL;
    bool ok = false;

    check(mk_registry_new_builtin(&registry) == MK_OK, "registry");
    check(mk_registry_get_system(registry, "descriptive", &descriptive) == MK_OK, "descriptive");
    check(mk_registry_get_system(registry, "distinctive", &distinctive) == MK_OK, "distinctive");
    check(mk_registry_get_system(registry, "phoible", &phoible) == MK_OK, "phoible");

    check_grapheme_parity(descriptive, "p", "b");
    check_grapheme_parity(descriptive, "l", "ɮ");
    check_grapheme_parity(distinctive, "a", "e");
    check_grapheme_parity(phoible, "p", "t");

    /* A laryngeal-like segment: a guttural fricative, voice and place open. */
    check(mk_bundle_from_grapheme(descriptive, "ħ", &h) == MK_OK, "ħ");
    check(mk_bundle_set(h, "voice", "?") == MK_OK, "set voice");
    check(mk_bundle_set(h, "guttural_place", "?") == MK_OK, "set place");
    check(mk_bundle_set(h, "Manner", "fricative|approximant") == MK_OK, "set manner");
    check(mk_bundle_get(h, "Manner", &cell) == MK_OK && strcmp(cell, "approximant|fricative") == 0,
          "canonical group alternatives");
    mk_string_free(cell);

    check(mk_bundle_compatible(h, "ʕ", &ok) == MK_OK && ok, "ʕ compatible");
    check(mk_bundle_compatible(h, "h", &ok) == MK_OK && ok, "h compatible");
    check(mk_bundle_compatible(h, "k", &ok) == MK_OK && !ok, "k not compatible");
    check(mk_bundle_compatible_graphemes(h, NULL, &compatible) == MK_OK &&
              mk_string_list_size(compatible) > 0, "compatible list");
    mk_string_list_free(compatible);

    {
        mk_bundle *ain = NULL;
        check(mk_bundle_from_grapheme(descriptive, "ʕ", &ain) == MK_OK, "ʕ");
        check(mk_bundle_compare(h, ain, NULL, &cmp) == MK_OK, "compare");
        /* Compatible: the dimensions both specify agree, and some completion
         * is ʕ itself. */
        check(cmp.distance == 0.0 && cmp.minimum == 0.0 && cmp.maximum > 0.0, "bounds around ʕ");
        check(cmp.coverage > 0.0 && cmp.coverage < 1.0, "partial coverage");
        mk_bundle_free(ain);
    }

    /* Text round trip is canonical. */
    check(mk_bundle_to_text(h, &text) == MK_OK, "to_text");
    check(mk_bundle_from_text(descriptive, text, &round_trip) == MK_OK, "from_text");
    check(mk_bundle_to_text(round_trip, &again) == MK_OK && strcmp(text, again) == 0, "round trip");
    mk_string_free(text);
    mk_string_free(again);

    /* Errors are statuses, never silent. */
    check(mk_bundle_set(h, "no_such_column", "+") == MK_ERR_UNKNOWN_FEATURE, "unknown column");
    check(mk_bundle_set(h, "voice", "maybe") == MK_ERR_PARSE, "bad cell");
    check(mk_bundle_set(h, "vowel_height", "open..close") == MK_ERR_PARSE, "reversed range");
    check(mk_bundle_from_grapheme(descriptive, "ai", &empty) == MK_ERR_UNSUPPORTED_MODEL, "cluster refused");
    check(mk_bundle_compare(h, round_trip, "no-such-preset", &cmp) == MK_ERR_INVALID_ARGUMENT, "bad preset");

    /* A new bundle knows nothing: every cell is `*`. */
    check(mk_bundle_new(distinctive, &empty) == MK_OK, "new");
    check(mk_bundle_get(empty, "voice", &cell) == MK_OK && strcmp(cell, "*") == 0, "new is *");
    mk_string_free(cell);
    mk_bundle_free(empty);

    mk_bundle_free(h);
    mk_bundle_free(round_trip);
    mk_registry_free(registry);
    if (failures == 0) {
        printf("bundle: ok\n");
    }
    return failures == 0 ? 0 : 1;
}
