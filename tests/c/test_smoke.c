#include "merkmal.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

static int expect_status(mk_status actual, mk_status expected, const char *label)
{
    if (actual != expected) {
        fprintf(stderr, "%s: expected status %d, got %d\n", label, expected, actual);
        return 1;
    }
    return 0;
}

static int expect_string(const char *actual, const char *expected, const char *label)
{
    if (actual == NULL || strcmp(actual, expected) != 0) {
        fprintf(stderr, "%s: expected %s, got %s\n", label, expected, actual ? actual : "(null)");
        return 1;
    }
    return 0;
}

static int list_contains(const mk_string_list *list, const char *value)
{
    size_t i;

    for (i = 0; i < mk_string_list_size(list); i++) {
        const char *item = mk_string_list_get(list, i);
        if (item != NULL && strcmp(item, value) == 0) {
            return 1;
        }
    }
    return 0;
}

static int features_contains(const mk_feature_set *features, const char *value)
{
    size_t i;

    for (i = 0; i < mk_feature_set_size(features); i++) {
        const char *item = mk_feature_set_get(features, i);
        if (item != NULL && strcmp(item, value) == 0) {
            return 1;
        }
    }
    return 0;
}

static int expect_list_item(
    const mk_string_list *list,
    size_t index,
    const char *expected,
    const char *label
)
{
    if (mk_string_list_size(list) <= index) {
        fprintf(stderr, "%s: missing item %zu\n", label, index);
        return 1;
    }
    return expect_string(mk_string_list_get(list, index), expected, label);
}

int main(void)
{
    mk_registry *registry = NULL;
    mk_string_list *systems = NULL;
    const mk_system *descriptive = NULL;
    const mk_system *phoible = NULL;
    const mk_system *toy = NULL;
    mk_feature_set *features = NULL;
    char *normalized = NULL;
    double distance = 0.0;
    int is_segment = 0;
    int failed = 0;

    failed |= expect_string(mk_status_string(MK_OK), "ok", "status ok");
    failed |= expect_string(
        mk_status_string(MK_ERR_UNKNOWN_GRAPHEME),
        "unknown grapheme",
        "status unknown grapheme"
    );

    failed |= expect_status(mk_registry_new_builtin(&registry), MK_OK, "registry");
    failed |= expect_status(mk_registry_list_systems(registry, &systems), MK_OK, "list systems");
    if (mk_string_list_size(systems) != 8) {
        fprintf(stderr, "systems: expected 8, got %zu\n", mk_string_list_size(systems));
        failed = 1;
    }
    if (!list_contains(systems, "broad") ||
        !list_contains(systems, "distinctive") ||
        !list_contains(systems, "pbase-uftc")) {
        fprintf(stderr, "systems: missing expanded built-in names\n");
        failed = 1;
    }
    mk_string_list_free(systems);

    failed |= expect_status(
        mk_registry_get_system(registry, "descriptive", &descriptive),
        MK_OK,
        "get descriptive"
    );
    failed |= expect_status(
        mk_registry_get_system(registry, "phoible", &phoible),
        MK_OK,
        "get phoible"
    );

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "p", &features),
        MK_OK,
        "features p"
    );
    if (mk_feature_set_size(features) != 4) {
        fprintf(stderr, "features p: expected 4, got %zu\n", mk_feature_set_size(features));
        failed = 1;
    }
    mk_feature_set_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "pʰ", &features),
        MK_OK,
        "features synthesized pʰ"
    );
    if (mk_feature_set_size(features) != 5) {
        fprintf(stderr, "features pʰ: expected 5, got %zu\n", mk_feature_set_size(features));
        failed = 1;
    }
    mk_feature_set_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "b̥", &features),
        MK_OK,
        "features synthesized b̥"
    );
    if (!features_contains(features, "devoiced") || !features_contains(features, "voiced")) {
        fprintf(stderr, "features b̥: expected devoiced modifier on voiced base\n");
        failed = 1;
    }
    mk_feature_set_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "t͡ʃ", &features),
        MK_OK,
        "features normalized t͡ʃ"
    );
    if (mk_feature_set_size(features) != 5) {
        fprintf(stderr, "features t͡ʃ: expected 5, got %zu\n", mk_feature_set_size(features));
        failed = 1;
    }
    mk_feature_set_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(phoible, "b", &features),
        MK_OK,
        "features phoible b"
    );
    if (mk_feature_set_size(features) != 38) {
        fprintf(stderr, "features phoible b: expected 38, got %zu\n", mk_feature_set_size(features));
        failed = 1;
    }
    mk_feature_set_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(phoible, "bʰ", &features),
        MK_OK,
        "features synthesized phoible bʰ"
    );
    if (!features_contains(features, "periodicGlottalSource=+") ||
        !features_contains(features, "spreadGlottis=+")) {
        fprintf(stderr, "features phoible bʰ: expected preserved voice and applied aspiration\n");
        failed = 1;
    }
    mk_feature_set_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_is_segment(descriptive, "not-ipa", &is_segment),
        MK_OK,
        "is segment unknown"
    );
    if (is_segment != 0) {
        fprintf(stderr, "is segment unknown: expected 0, got %d\n", is_segment);
        failed = 1;
    }

    failed |= expect_status(
        mk_system_is_segment(descriptive, "a³¹", &is_segment),
        MK_OK,
        "is segment tone vowel 31"
    );
    if (is_segment != 1) {
        fprintf(stderr, "is segment tone vowel 31: expected 1, got %d\n", is_segment);
        failed = 1;
    }

    failed |= expect_status(
        mk_system_is_segment(descriptive, "a⁵¹", &is_segment),
        MK_OK,
        "is segment tone vowel 51"
    );
    if (is_segment != 1) {
        fprintf(stderr, "is segment tone vowel 51: expected 1, got %d\n", is_segment);
        failed = 1;
    }

    failed |= expect_status(
        mk_system_is_segment(descriptive, "a³³", &is_segment),
        MK_OK,
        "is segment level tone vowel a33"
    );
    if (is_segment != 1) {
        fprintf(stderr, "is segment level tone vowel a33: expected 1, got %d\n", is_segment);
        failed = 1;
    }

    failed |= expect_status(
        mk_system_is_segment(descriptive, "ə³³", &is_segment),
        MK_OK,
        "is segment level tone vowel schwa33"
    );
    if (is_segment != 1) {
        fprintf(stderr, "is segment level tone vowel schwa33: expected 1, got %d\n", is_segment);
        failed = 1;
    }

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "a³¹", &features),
        MK_OK,
        "features tone vowel 31"
    );
    if (!features_contains(features, "vowel") ||
        !features_contains(features, "tone-offset-lower") ||
        !features_contains(features, "tone-offset-lowered")) {
        fprintf(stderr, "features tone vowel 31: expected base vowel and offset tone features\n");
        failed = 1;
    }
    mk_feature_set_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "a⁵¹", &features),
        MK_OK,
        "features tone vowel 51"
    );
    if (!features_contains(features, "vowel") ||
        !features_contains(features, "tone-onset-upper") ||
        !features_contains(features, "tone-onset-raised") ||
        !features_contains(features, "tone-offset-lower") ||
        !features_contains(features, "tone-offset-lowered")) {
        fprintf(stderr, "features tone vowel 51: expected base vowel and onset/offset tone features\n");
        failed = 1;
    }
    mk_feature_set_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "a³³", &features),
        MK_OK,
        "features level tone vowel a33"
    );
    if (!features_contains(features, "vowel")) {
        fprintf(stderr, "features level tone vowel a33: expected base vowel features\n");
        failed = 1;
    }
    if (features_contains(features, "tone-onset-upper") ||
        features_contains(features, "tone-offset-lower")) {
        fprintf(stderr, "features level tone vowel a33: expected neutral level tone to add no tone features\n");
        failed = 1;
    }
    mk_feature_set_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "<?>", &features),
        MK_ERR_UNKNOWN_GRAPHEME,
        "features unknown still raises status"
    );
    failed |= expect_status(
        mk_system_is_segment(descriptive, "p³¹", &is_segment),
        MK_OK,
        "is segment tone consonant"
    );
    if (is_segment != 0) {
        fprintf(stderr, "is segment tone consonant: expected 0, got %d\n", is_segment);
        failed = 1;
    }
    failed |= expect_status(
        mk_system_is_segment(descriptive, "p³³", &is_segment),
        MK_OK,
        "is segment level tone consonant"
    );
    if (is_segment != 0) {
        fprintf(stderr, "is segment level tone consonant: expected 0, got %d\n", is_segment);
        failed = 1;
    }

    failed |= expect_status(
        mk_system_segment_distance(descriptive, "p", "b", &distance),
        MK_OK,
        "distance p b"
    );
    if (!(distance > 0.0 && distance < 1.0)) {
        fprintf(stderr, "distance p b: expected intermediate value, got %.10f\n", distance);
        failed = 1;
    }

    failed |= expect_status(
        mk_system_segment_distance(descriptive, "p", "not-ipa", &distance),
        MK_ERR_UNKNOWN_GRAPHEME,
        "distance unknown"
    );

    failed |= expect_status(mk_normalize_grapheme("g", &normalized), MK_OK, "normalize g");
    failed |= expect_string(normalized, "ɡ", "normalize g");
    mk_free_string(normalized);
    normalized = NULL;

    failed |= expect_status(mk_normalize_grapheme("sh/ʃ", &normalized), MK_OK, "normalize slash");
    failed |= expect_string(normalized, "ʃ", "normalize slash");
    mk_free_string(normalized);
    normalized = NULL;

    failed |= expect_status(mk_normalize_grapheme("ã", &normalized), MK_OK, "normalize nfd nasal");
    failed |= expect_string(normalized, "ã", "normalize nfd nasal");
    mk_free_string(normalized);
    normalized = NULL;

    failed |= expect_status(mk_normalize_grapheme("ü", &normalized), MK_OK, "normalize u diaeresis");
    failed |= expect_string(normalized, "ü", "normalize u diaeresis");
    mk_free_string(normalized);
    normalized = NULL;

    failed |= expect_status(mk_normalize_grapheme("ˈ", &normalized), MK_OK, "normalize bare stress");
    failed |= expect_string(normalized, "", "normalize bare stress");
    mk_free_string(normalized);
    normalized = NULL;

    {
        mk_string_list *segments = NULL;
        failed |= expect_status(mk_segment_ipa("tʰoŋ⁵⁵", &segments), MK_OK, "segment ipa");
        if (mk_string_list_size(segments) != 4) {
            fprintf(stderr, "segment ipa: expected 4, got %zu\n", mk_string_list_size(segments));
            failed = 1;
        }
        failed |= expect_string(mk_string_list_get(segments, 0), "tʰ", "segment 0");
        failed |= expect_string(mk_string_list_get(segments, 3), "⁵⁵", "segment 3");
        mk_string_list_free(segments);
    }

    {
        mk_string_list *segments = NULL;
        failed |= expect_status(mk_segment_ipa("ⁿda", &segments), MK_OK, "segment prenasalized");
        if (mk_string_list_size(segments) != 2) {
            fprintf(stderr, "segment prenasalized: expected 2, got %zu\n", mk_string_list_size(segments));
            failed = 1;
        }
        failed |= expect_list_item(segments, 0, "ⁿd", "segment prenasalized 0");
        failed |= expect_list_item(segments, 1, "a", "segment prenasalized 1");
        mk_string_list_free(segments);
    }

    {
        mk_string_list *segments = NULL;
        failed |= expect_status(mk_segment_ipa("n̥a", &segments), MK_OK, "segment combining");
        if (mk_string_list_size(segments) != 2) {
            fprintf(stderr, "segment combining: expected 2, got %zu\n", mk_string_list_size(segments));
            failed = 1;
        }
        failed |= expect_list_item(segments, 0, "n̥", "segment combining 0");
        failed |= expect_list_item(segments, 1, "a", "segment combining 1");
        mk_string_list_free(segments);
    }

    {
        mk_string_list *segments = NULL;
        failed |= expect_status(mk_segment_ipa_merged("tʰo³¹pan¹³", &segments), MK_OK, "segment merged tones");
        if (mk_string_list_size(segments) != 5) {
            fprintf(stderr, "segment merged tones: expected 5, got %zu\n", mk_string_list_size(segments));
            failed = 1;
        }
        failed |= expect_list_item(segments, 1, "o³¹", "segment merged tones 1");
        failed |= expect_list_item(segments, 3, "a¹³", "segment merged tones 3");
        mk_string_list_free(segments);
    }

    {
        mk_string_list *segments = NULL;
        failed |= expect_status(mk_segment_ipa_merged("k+a⁰", &segments), MK_OK, "segment zero tone");
        if (mk_string_list_size(segments) != 3) {
            fprintf(stderr, "segment zero tone: expected 3, got %zu\n", mk_string_list_size(segments));
            failed = 1;
        }
        failed |= expect_list_item(segments, 1, "+", "segment zero tone boundary");
        failed |= expect_list_item(segments, 2, "a", "segment zero tone dropped");
        mk_string_list_free(segments);
    }

    failed |= expect_status(
        mk_registry_add_model_text(
            registry,
            "@model toy\n"
            "@type categorical\n"
            "@geometry clements-hume\n"
            "feature consonant major\n"
            "grapheme X consonant voiceless bilabial stop\n"
            "grapheme Y vowel open front unrounded\n"
        ),
        MK_OK,
        "add runtime model"
    );
    failed |= expect_status(mk_registry_get_system(registry, "toy", &toy), MK_OK, "get runtime model");
    failed |= expect_status(mk_system_grapheme_features(toy, "X", &features), MK_OK, "features runtime X");
    if (mk_feature_set_size(features) != 4) {
        fprintf(stderr, "features runtime X: expected 4, got %zu\n", mk_feature_set_size(features));
        failed = 1;
    }
    mk_feature_set_free(features);
    features = NULL;
    failed |= expect_status(mk_system_segment_distance(toy, "X", "Y", &distance), MK_OK, "distance runtime");
    if (!(distance > 0.0 && distance <= 1.0)) {
        fprintf(stderr, "distance runtime: expected positive finite value, got %.10f\n", distance);
        failed = 1;
    }

    mk_registry_free(registry);
    return failed ? 1 : 0;
}
