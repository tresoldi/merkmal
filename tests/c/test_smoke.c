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

static int expect_segment(
    const mk_system *system,
    const char *grapheme,
    int expected,
    const char *label
)
{
    int is_segment = 0;
    int failed = 0;

    failed |= expect_status(mk_system_is_segment(system, grapheme, &is_segment), MK_OK, label);
    if (is_segment != expected) {
        fprintf(stderr, "%s: expected %d, got %d\n", label, expected, is_segment);
        failed = 1;
    }
    return failed;
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
        mk_system_grapheme_features(descriptive, "ai", &features),
        MK_OK,
        "features diphthong ai"
    );
    if (!features_contains(features, "vowel") ||
        !features_contains(features, "diphthong") ||
        !features_contains(features, "n1-open") ||
        !features_contains(features, "n2-close") ||
        !features_contains(features, "move-height-open-close")) {
        fprintf(stderr, "features diphthong ai: expected synthetic cluster features\n");
        failed = 1;
    }
    if (features_contains(features, "open") || features_contains(features, "close")) {
        fprintf(stderr, "features diphthong ai: expected no unqualified component qualities\n");
        failed = 1;
    }
    mk_feature_set_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "aːi³³", &features),
        MK_OK,
        "features long level tone diphthong"
    );
    if (!features_contains(features, "diphthong") ||
        !features_contains(features, "n1-long") ||
        features_contains(features, "tone-onset-upper") ||
        features_contains(features, "tone-offset-lower")) {
        fprintf(stderr, "features long level tone diphthong: expected n1-long and neutral level tone\n");
        failed = 1;
    }
    mk_feature_set_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "əi³¹", &features),
        MK_OK,
        "features tone diphthong"
    );
    if (!features_contains(features, "diphthong") ||
        !features_contains(features, "n1-mid") ||
        !features_contains(features, "tone-offset-lower") ||
        !features_contains(features, "tone-offset-lowered")) {
        fprintf(stderr, "features tone diphthong: expected cluster and tone features\n");
        failed = 1;
    }
    mk_feature_set_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "ɛï³³", &features),
        MK_OK,
        "features precomposed tone diphthong"
    );
    if (!features_contains(features, "vowel") ||
        !features_contains(features, "diphthong") ||
        !features_contains(features, "n1-open-mid") ||
        !features_contains(features, "n2-close") ||
        !features_contains(features, "n2-centralized")) {
        fprintf(stderr, "features precomposed tone diphthong: expected cluster and normalized diaeresis features\n");
        failed = 1;
    }
    mk_feature_set_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "kɣ", &features),
        MK_OK,
        "features mixed velar affricate"
    );
    if (!features_contains(features, "consonant") ||
        !features_contains(features, "affricate") ||
        !features_contains(features, "velar") ||
        features_contains(features, "voiceless") ||
        features_contains(features, "voiced") ||
        features_contains(features, "sibilant")) {
        fprintf(stderr, "features mixed velar affricate: expected velar affricate without phonation or sibilant\n");
        failed = 1;
    }
    mk_feature_set_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "kk", &features),
        MK_OK,
        "features geminate cluster kk"
    );
    if (!features_contains(features, "consonant-cluster") ||
        !features_contains(features, "geminate")) {
        fprintf(stderr, "features geminate cluster kk: expected geminate cluster features\n");
        failed = 1;
    }
    mk_feature_set_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "ḭ", &features),
        MK_OK,
        "features precomposed i creaky"
    );
    if (!features_contains(features, "vowel") || !features_contains(features, "creaky")) {
        fprintf(stderr, "features precomposed i creaky: expected vowel and creaky\n");
        failed = 1;
    }
    mk_feature_set_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "ṳ", &features),
        MK_OK,
        "features precomposed u breathy"
    );
    if (!features_contains(features, "vowel") || !features_contains(features, "breathy")) {
        fprintf(stderr, "features precomposed u breathy: expected vowel and breathy\n");
        failed = 1;
    }
    mk_feature_set_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "ṵː", &features),
        MK_OK,
        "features precomposed u creaky long"
    );
    if (!features_contains(features, "vowel") ||
        !features_contains(features, "creaky") ||
        !features_contains(features, "long")) {
        fprintf(stderr, "features precomposed u creaky long: expected vowel, creaky, and long\n");
        failed = 1;
    }
    mk_feature_set_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "ṽ", &features),
        MK_OK,
        "features precomposed nasalized v"
    );
    if (!features_contains(features, "consonant") ||
        !features_contains(features, "nasalized") ||
        features_contains(features, "vowel")) {
        fprintf(stderr, "features precomposed nasalized v: expected nasalized consonant, not vowel\n");
        failed = 1;
    }
    mk_feature_set_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "ŋ̀", &features),
        MK_OK,
        "features tone syllabic sonorant"
    );
    if (!features_contains(features, "syllabic") ||
        !features_contains(features, "tone-onset-lower") ||
        !features_contains(features, "tone-offset-lower")) {
        fprintf(stderr, "features tone syllabic sonorant: expected syllabic and tone features\n");
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
    failed |= expect_segment(descriptive, "ai", 1, "is segment ai");
    failed |= expect_segment(descriptive, "au", 1, "is segment au");
    failed |= expect_segment(descriptive, "ei", 1, "is segment ei");
    failed |= expect_segment(descriptive, "aːi", 1, "is segment aːi");
    failed |= expect_segment(descriptive, "iau", 1, "is segment iau");
    failed |= expect_segment(descriptive, "ai³³", 1, "is segment ai³³");
    failed |= expect_segment(descriptive, "aːi³³", 1, "is segment aːi³³");
    failed |= expect_segment(descriptive, "ɐu³³", 1, "is segment ɐu³³");
    failed |= expect_segment(descriptive, "əi³¹", 1, "is segment əi³¹");
    failed |= expect_segment(descriptive, "ɛï", 1, "is segment ɛï");
    failed |= expect_segment(descriptive, "ɛï³³", 1, "is segment ɛï³³");
    failed |= expect_segment(descriptive, "ɛï³¹", 1, "is segment ɛï³¹");
    failed |= expect_segment(descriptive, "ɛï³⁵", 1, "is segment ɛï³⁵");
    failed |= expect_segment(descriptive, "ɛï⁴⁵", 1, "is segment ɛï⁴⁵");
    failed |= expect_segment(descriptive, "ɛï⁴⁵³", 1, "is segment ɛï⁴⁵³");
    failed |= expect_segment(descriptive, "ᵐb", 1, "is segment ᵐb");
    failed |= expect_segment(descriptive, "ⁿd", 1, "is segment ⁿd");
    failed |= expect_segment(descriptive, "ⁿdʳ", 1, "is segment ⁿdʳ");
    failed |= expect_segment(descriptive, "ɡb", 1, "is segment ɡb");
    failed |= expect_segment(descriptive, "gb", 1, "is segment gb");
    failed |= expect_segment(descriptive, "kp", 1, "is segment kp");
    failed |= expect_segment(descriptive, "kpʷ", 1, "is segment kpʷ");
    failed |= expect_segment(descriptive, "kx", 1, "is segment kx");
    failed |= expect_segment(descriptive, "gɣ", 1, "is segment gɣ");
    failed |= expect_segment(descriptive, "kɣ", 1, "is segment kɣ");
    failed |= expect_segment(descriptive, "tʂ", 1, "is segment tʂ");
    failed |= expect_segment(descriptive, "tʂʰ", 1, "is segment tʂʰ");
    failed |= expect_segment(descriptive, "ŋ̀", 1, "is segment ŋ̀");
    failed |= expect_segment(descriptive, "m̀", 1, "is segment m̀");
    failed |= expect_segment(descriptive, "ä", 1, "is segment ä");
    failed |= expect_segment(descriptive, "ă", 1, "is segment ă");
    failed |= expect_segment(descriptive, "ç", 1, "is segment ç");
    failed |= expect_segment(descriptive, "ḭ", 1, "is segment ḭ");
    failed |= expect_segment(descriptive, "ṳ", 1, "is segment ṳ");
    failed |= expect_segment(descriptive, "ṵ", 1, "is segment ṵ");
    failed |= expect_segment(descriptive, "ṵː", 1, "is segment ṵː");
    failed |= expect_segment(descriptive, "ṽ", 1, "is segment ṽ");
    failed |= expect_segment(descriptive, "ñ", 1, "is segment ñ");
    failed |= expect_segment(descriptive, "ń", 1, "is segment ń");
    failed |= expect_segment(descriptive, "ỹ", 1, "is segment ỹ");
    failed |= expect_segment(descriptive, "kw", 1, "is segment kw");
    failed |= expect_segment(descriptive, "gw", 1, "is segment gw");
    failed |= expect_segment(descriptive, "ŋg", 1, "is segment ŋg");
    failed |= expect_segment(descriptive, "kk", 1, "is segment kk");
    failed |= expect_segment(descriptive, "ll", 1, "is segment ll");
    failed |= expect_segment(descriptive, "tt", 1, "is segment tt");
    failed |= expect_segment(descriptive, "nn", 1, "is segment nn");
    failed |= expect_segment(descriptive, "pp", 1, "is segment pp");
    failed |= expect_segment(descriptive, "<?>", 0, "is segment markup question");
    failed |= expect_segment(descriptive, "<<->>", 0, "is segment markup deletion");
    failed |= expect_segment(descriptive, "<<[>>", 0, "is segment markup left bracket");
    failed |= expect_segment(descriptive, "→", 0, "is segment arrow");
    failed |= expect_segment(descriptive, "+", 0, "is segment plus markup");
    failed |= expect_segment(descriptive, "∼", 0, "is segment tilde markup");
    failed |= expect_segment(descriptive, "<<]>>", 0, "is segment markup right bracket");
    failed |= expect_segment(descriptive, "<<~>>", 0, "is segment markup tilde");
    failed |= expect_segment(descriptive, "<</>>", 0, "is segment markup slash");
    failed |= expect_segment(descriptive, "<<.>>", 0, "is segment markup dot");
    failed |= expect_segment(descriptive, "_", 0, "is segment underscore control");
    failed |= expect_segment(descriptive, "S", 0, "is segment S annotation");
    failed |= expect_segment(descriptive, "T", 0, "is segment T annotation");
    failed |= expect_segment(descriptive, "¹/¹", 0, "is segment slash tone 11");
    failed |= expect_segment(descriptive, "³/¹", 0, "is segment slash tone 31");
    failed |= expect_segment(descriptive, "³¹", 0, "is segment bare tone 31");
    failed |= expect_segment(descriptive, "³⁵", 0, "is segment bare tone 35");
    failed |= expect_segment(descriptive, "⁵⁵", 0, "is segment bare tone 55");
    failed |= expect_segment(descriptive, "mb", 0, "is segment bare mb");
    failed |= expect_segment(descriptive, "nd", 0, "is segment bare nd");
    failed |= expect_segment(descriptive, "ě", 0, "is segment deferred e caron");
    failed |= expect_segment(descriptive, "ǎ", 0, "is segment deferred a caron");
    failed |= expect_segment(descriptive, "ý", 0, "is segment deferred y acute");

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

    failed |= expect_status(
        mk_system_segment_distance(descriptive, "ai", "ai", &distance),
        MK_OK,
        "distance ai ai"
    );
    if (distance != 0.0) {
        fprintf(stderr, "distance ai ai: expected 0.0, got %.10f\n", distance);
        failed = 1;
    }
    {
        double ai_a = 0.0;
        double ai_i = 0.0;
        failed |= expect_status(
            mk_system_segment_distance(descriptive, "ai", "a", &ai_a),
            MK_OK,
            "distance ai a"
        );
        failed |= expect_status(
            mk_system_segment_distance(descriptive, "ai", "i", &ai_i),
            MK_OK,
            "distance ai i"
        );
        if (!(ai_a < ai_i)) {
            fprintf(stderr, "distance ai endpoint weighting: expected ai~a < ai~i, got %.10f %.10f\n", ai_a, ai_i);
            failed = 1;
        }
    }
    failed |= expect_status(
        mk_system_segment_distance(descriptive, "ai", "au", &distance),
        MK_OK,
        "distance ai au"
    );
    if (!(distance > 0.0 && distance < 1.0)) {
        fprintf(stderr, "distance ai au: expected finite nonzero normalized value, got %.10f\n", distance);
        failed = 1;
    }
    failed |= expect_status(
        mk_system_segment_distance(descriptive, "ai³³", "aːi³³", &distance),
        MK_OK,
        "distance tone clusters"
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

    failed |= expect_status(mk_normalize_grapheme("ï", &normalized), MK_OK, "normalize i diaeresis");
    failed |= expect_string(normalized, "ï", "normalize i diaeresis");
    mk_free_string(normalized);
    normalized = NULL;

    failed |= expect_status(mk_normalize_grapheme("ḭ", &normalized), MK_OK, "normalize i creaky");
    failed |= expect_string(normalized, "ḭ", "normalize i creaky");
    mk_free_string(normalized);
    normalized = NULL;

    failed |= expect_status(mk_normalize_grapheme("ṳ", &normalized), MK_OK, "normalize u breathy");
    failed |= expect_string(normalized, "ṳ", "normalize u breathy");
    mk_free_string(normalized);
    normalized = NULL;

    failed |= expect_status(mk_normalize_grapheme("ṵ", &normalized), MK_OK, "normalize u creaky");
    failed |= expect_string(normalized, "ṵ", "normalize u creaky");
    mk_free_string(normalized);
    normalized = NULL;

    failed |= expect_status(mk_normalize_grapheme("ṽ", &normalized), MK_OK, "normalize v nasalized");
    failed |= expect_string(normalized, "ṽ", "normalize v nasalized");
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
