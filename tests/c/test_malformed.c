/* Malformed and hostile input through the public API.
 *
 * Every input here is copied into a heap buffer sized exactly to its bytes, so
 * that a read past the terminator is a heap overflow AddressSanitizer can see.
 * The same cases in a string literal would read into adjacent rodata and pass
 * silently.
 *
 * The truncated-sequence cases are a regression: mk_utf8_char_len returned the
 * length a lead byte *claims*, and nineteen call sites copied or skipped that
 * many bytes without checking the string had them, so
 * mk_segment_ipa("a\xF0") read four bytes out of a two-byte allocation. */

#include "merkmal.h"

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Bytes rather than C strings, so a case may contain an embedded NUL and so
 * that the length is explicit rather than implied. */
typedef struct malformed_case {
    const char *label;
    const char *bytes;
    size_t length;
} malformed_case;

#define CASE(label, literal) { label, literal, sizeof(literal) - 1 }

static const malformed_case cases[] = {
    /* Truncated sequences: the lead byte claims more than is there. */
    CASE("lone 4-byte lead", "\xF0"),
    CASE("lone 3-byte lead", "\xE0"),
    CASE("lone 2-byte lead", "\xC2"),
    CASE("4-byte lead after a letter", "a\xF0"),
    CASE("4-byte lead, one continuation", "\xF0\x9F"),
    CASE("3-byte lead, one continuation", "\xE2\x80"),
    CASE("truncated tie bar", "t\xCD"),
    CASE("truncated after a vowel", "a\xCC"),

    /* Continuations with no lead, and other invalid leads. */
    CASE("bare continuation", "\x80"),
    CASE("continuation run", "\x80\x80\x80"),
    CASE("invalid lead FF", "\xFF"),
    CASE("invalid lead FE", "\xFE"),

    /* Shapes the synthesizers reach for. */
    CASE("empty", ""),
    CASE("tie bar alone", "\xCD\xA1"),
    CASE("tie bar then truncated", "\xCD\xA1\xF0"),
    CASE("combining mark alone", "\xCC\x83"),
    CASE("slash with nothing after", "a/"),
    CASE("only stress marks", "\xCB\x88\xCB\x8C"),
    CASE("long tone run", "a\xC2\xB9\xC2\xB9\xC2\xB9\xC2\xB9\xC2\xB9\xC2\xB9"),
    CASE("boundary only", "+"),

    /* Found by fuzz_resolve. Two consonant components merged into one
     * inventory row, and the merged resolution was copied out of the frame
     * that owned it with a plain struct assignment -- so its `features`, which
     * aliased that frame's inline_features array, pointed at a dead stack slot
     * by the time mk_synthesize_cluster read it. AddressSanitizer called it a
     * stack-use-after-return. mk_resolution_move is the fix.
     *
     * The literal is split so that "\x96" does not swallow the following F as
     * a fourth hex digit. */
    CASE("merged cluster component escaping its frame",
        "cisntstiisi\x9c\x8b\x96" "Fve"),
};

/* Exercises everything that takes caller text. Nothing here asserts a
 * particular answer: the contract for malformed input is that the library
 * returns some status without reading out of bounds, leaking, or crashing. */
static int run_case(mk_registry *registry, const malformed_case *test)
{
    char *text;
    mk_string_list *names = NULL;
    mk_string_list *list = NULL;
    char *owned = NULL;
    char *second = NULL;
    size_t i;

    text = (char *)malloc(test->length + 1);
    if (text == NULL) {
        fprintf(stderr, "%s: out of memory\n", test->label);
        return 1;
    }
    memcpy(text, test->bytes, test->length);
    text[test->length] = '\0';

    if (mk_segment_ipa(text, &list) == MK_OK) {
        mk_string_list_free(list);
        list = NULL;
    }
    if (mk_segment_ipa_merged(text, &list) == MK_OK) {
        mk_string_list_free(list);
        list = NULL;
    }
    if (mk_normalize_grapheme(text, &owned) == MK_OK) {
        mk_string_free(owned);
        owned = NULL;
    }
    if (mk_split_tone(text, &owned, &second) == MK_OK) {
        mk_string_free(owned);
        mk_string_free(second);
        owned = NULL;
        second = NULL;
    }

    if (mk_registry_list_systems(registry, &names) == MK_OK) {
        for (i = 0; i < mk_string_list_size(names); i++) {
            const mk_system *system = NULL;
            bool is_segment = false;
            double distance = 0.0;

            if (mk_registry_get_system(registry, mk_string_list_get(names, i), &system) != MK_OK) {
                continue;
            }
            mk_system_is_segment(system, text, &is_segment);
            if (mk_system_grapheme_features(system, text, &list) == MK_OK) {
                mk_string_list_free(list);
                list = NULL;
            }
            mk_system_segment_distance(system, text, "a", &distance);
            if (mk_system_segment_ipa(system, text, &list) == MK_OK) {
                mk_string_list_free(list);
                list = NULL;
            }
        }
        mk_string_list_free(names);
    }

    free(text);
    return 0;
}

/* A grapheme declared twice is refused, and refusing it is cheap.
 *
 * The check compared every row against every earlier one, which is quadratic in
 * text the caller supplies -- and mk_registry_add_model_text_n exists for
 * exactly the inputs that makes dangerous: a mapped file, a Python bytes, a
 * fuzzer's input. A model of 32,000 distinct rows, the worst case because
 * nothing short-circuits, spent 4.7 seconds here against 0.5 for parsing the
 * same text. Sorted and walked once it is 85 ms.
 *
 * The size here is a compromise: large enough that a return of the quadratic
 * form would be obvious in the suite's runtime, small enough to stay cheap. */
static int check_duplicate_grapheme_is_rejected(void)
{
    enum { ROWS = 4000 };
    static const char header[] =
        "@model dup\n@type categorical\n@geometry clements-hume\n";
    static const char row[] = "grapheme q%d consonant voiceless bilabial stop\n";
    mk_registry *registry = NULL;
    char *diagnostic = NULL;
    char *model;
    size_t used;
    size_t capacity = sizeof(header) + (size_t)ROWS * 64;
    int i;
    int failed = 0;
    mk_status status;

    model = (char *)malloc(capacity);
    if (model == NULL) {
        printf("FAIL: out of memory building the model\n");
        return 1;
    }
    used = sizeof(header) - 1;
    memcpy(model, header, used);
    for (i = 0; i < ROWS; i++) {
        /* The last row repeats the first, so the duplicate is as far from its
         * partner as the model allows. */
        used += (size_t)snprintf(model + used, capacity - used, row,
            i == ROWS - 1 ? 0 : i);
    }

    if (mk_registry_new_builtin(&registry) != MK_OK) {
        printf("FAIL: registry\n");
        free(model);
        return 1;
    }
    status = mk_registry_add_model_text_ex(registry, model, &diagnostic);
    if (status != MK_ERR_PARSE) {
        printf("FAIL: a repeated grapheme returned status %d\n", (int)status);
        failed = 1;
    }
    if (diagnostic == NULL || strstr(diagnostic, "more than once") == NULL) {
        printf("FAIL: diagnostic did not name the repetition: %s\n",
            diagnostic ? diagnostic : "(null)");
        failed = 1;
    }
    /* Nothing was installed, so the name is still free. */
    if (failed == 0) {
        mk_string_free(diagnostic);
        diagnostic = NULL;
        model[used - strlen("grapheme q0 consonant voiceless bilabial stop\n")] = '\0';
        if (mk_registry_add_model_text(registry, model) != MK_OK) {
            printf("FAIL: the same model without the repetition was refused\n");
            failed = 1;
        }
    }
    mk_string_free(diagnostic);
    mk_registry_free(registry);
    free(model);
    return failed;
}

/* A runtime model may name features of any length. A label built from one used
 * to be truncated into a different feature -- one the geometry does not know,
 * and which therefore contributes nothing to any distance. */
static int check_long_feature_name_is_rejected(void)
{
    char model[1024];
    char feature[600];
    mk_registry *registry = NULL;
    char *diagnostic = NULL;
    mk_status status;
    int failed = 0;

    memset(feature, 'x', sizeof(feature) - 1);
    feature[sizeof(feature) - 1] = '\0';
    snprintf(model, sizeof(model),
             "@model longfeature\n@type categorical\n@validation permissive\n"
             "grapheme q %s\n", feature);

    if (mk_registry_new_builtin(&registry) != MK_OK) {
        return 1;
    }
    status = mk_registry_add_model_text_ex(registry, model, &diagnostic);
    /* Permissive validation accepts the model; what matters is that nothing
     * downstream silently invents a truncated feature from it. */
    if (status == MK_OK) {
        const mk_system *system = NULL;
        mk_string_list *features = NULL;

        if (mk_registry_get_system(registry, "longfeature", &system) == MK_OK &&
            mk_system_grapheme_features(system, "q", &features) == MK_OK) {
            size_t i;
            for (i = 0; i < mk_string_list_size(features); i++) {
                const char *name = mk_string_list_get(features, i);
                if (strlen(name) < strlen(feature) && strncmp(name, feature, 40) == 0) {
                    fprintf(stderr,
                            "long feature name was silently truncated to %zu bytes\n",
                            strlen(name));
                    failed = 1;
                }
            }
            mk_string_list_free(features);
        }
    }
    mk_string_free(diagnostic);
    mk_registry_free(registry);
    return failed;
}

/* mk_registry_add_model_text_n takes bytes, so it is the one entry point that
 * can be handed a model with no terminator and a model containing a NUL.
 *
 * The buffer here is sized exactly to the model and is deliberately not
 * terminated: if the parser ever reaches for a terminator that a caller did not
 * promise, this reads off the end of the allocation and ASan says so. */
static int check_unterminated_and_embedded_nul(void)
{
    static const char model[] =
        "@model unterminated\n"
        "@type categorical\n"
        "@validation permissive\n"
        "grapheme Q consonant\n";
    const size_t length = sizeof(model) - 1;
    mk_registry *registry = NULL;
    char *diagnostic = NULL;
    char *bytes;
    int failed = 0;

    if (mk_registry_new_builtin(&registry) != MK_OK) {
        fprintf(stderr, "could not build the registry\n");
        return 1;
    }

    bytes = (char *)malloc(length);
    if (bytes == NULL) {
        mk_registry_free(registry);
        return 1;
    }
    memcpy(bytes, model, length);

    if (mk_registry_add_model_text_n(registry, bytes, length, &diagnostic) != MK_OK) {
        fprintf(stderr, "unterminated model: rejected (%s)\n",
            diagnostic == NULL ? "no diagnostic" : diagnostic);
        failed = 1;
    }
    mk_string_free(diagnostic);
    diagnostic = NULL;

    /* The same bytes with a NUL in the middle must be refused rather than
     * quietly registered as whatever preceded it. */
    bytes[length / 2] = '\0';
    if (mk_registry_add_model_text_n(registry, bytes, length, &diagnostic) != MK_ERR_PARSE) {
        fprintf(stderr, "embedded NUL in a model: expected MK_ERR_PARSE\n");
        failed = 1;
    }
    mk_string_free(diagnostic);

    free(bytes);
    mk_registry_free(registry);
    return failed;
}

int main(void)
{
    mk_registry *registry = NULL;
    size_t i;
    int failed = 0;

    if (mk_registry_new_builtin(&registry) != MK_OK) {
        fprintf(stderr, "could not build the registry\n");
        return 1;
    }
    for (i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
        failed |= run_case(registry, &cases[i]);
    }
    mk_registry_free(registry);

    failed |= check_duplicate_grapheme_is_rejected();
    failed |= check_long_feature_name_is_rejected();
    failed |= check_unterminated_and_embedded_nul();
    return failed ? 1 : 0;
}
