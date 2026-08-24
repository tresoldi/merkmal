#include "merkmal.h"

#include <math.h>
#include <stdbool.h>
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

static int expect_segment(
    const mk_system *system,
    const char *grapheme,
    int expected,
    const char *label
)
{
    bool is_segment = false;
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
    mk_string_list *features = NULL;
    char *normalized = NULL;
    double distance = 0.0;
    bool is_segment = false;
    int failed = 0;

    failed |= expect_string(mk_status_string(MK_OK), "ok", "status ok");
    failed |= expect_string(
        mk_status_string(MK_ERR_UNKNOWN_GRAPHEME),
        "unknown grapheme",
        "status unknown grapheme"
    );
    failed |= expect_status(
        mk_registry_new_builtin(NULL),
        MK_ERR_INVALID_ARGUMENT,
        "registry null output"
    );
    failed |= expect_status(
        mk_string_list_new(NULL, 1, &systems),
        MK_ERR_INVALID_ARGUMENT,
        "list null items"
    );
    failed |= expect_status(
        mk_string_list_new(NULL, 0, &systems),
        MK_OK,
        "empty list"
    );
    if (mk_string_list_size(systems) != 0 || mk_string_list_get(systems, 0) != NULL) {
        fprintf(stderr, "empty list: unexpected contents\n");
        failed = 1;
    }
    mk_string_list_free(systems);
    systems = NULL;

    failed |= expect_status(mk_registry_new_builtin(&registry), MK_OK, "registry");
    failed |= expect_status(mk_registry_list_systems(registry, &systems), MK_OK, "list systems");
    if (mk_string_list_size(systems) != 7) {
        fprintf(stderr, "systems: expected 7, got %zu\n", mk_string_list_size(systems));
        failed = 1;
    }
    if (!list_contains(systems, "descriptive") ||
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
    /* Four from the inventory name, plus consonantal, obstruent and
     * non-continuant, which the generator derives because no inventory NAME
     * ever states them. */
    if (mk_string_list_size(features) != 8) {
        fprintf(stderr, "features p: expected 8, got %zu\n", mk_string_list_size(features));
        failed = 1;
    }
    mk_string_list_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "pʰ", &features),
        MK_OK,
        "features synthesized pʰ"
    );
    if (mk_string_list_size(features) != 9) {
        fprintf(stderr, "features pʰ: expected 9, got %zu\n", mk_string_list_size(features));
        failed = 1;
    }
    mk_string_list_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "b̥", &features),
        MK_OK,
        "features synthesized b̥"
    );
    if (!list_contains(features, "devoiced") || !list_contains(features, "voiced")) {
        fprintf(stderr, "features b̥: expected devoiced modifier on voiced base\n");
        failed = 1;
    }
    mk_string_list_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "t͡ʃ", &features),
        MK_OK,
        "features normalized t͡ʃ"
    );
    /* Five from the inventory name, plus the derived class features
     * (consonantal, obstruent, non-continuant, non-anterior, distributed,
     * coronal). */
    if (mk_string_list_size(features) != 11) {
        fprintf(stderr, "features t͡ʃ: expected 11, got %zu\n", mk_string_list_size(features));
        failed = 1;
    }
    mk_string_list_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(phoible, "b", &features),
        MK_OK,
        "features phoible b"
    );
    if (mk_string_list_size(features) != 38) {
        fprintf(stderr, "features phoible b: expected 38, got %zu\n", mk_string_list_size(features));
        failed = 1;
    }
    mk_string_list_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(phoible, "bʰ", &features),
        MK_OK,
        "features synthesized phoible bʰ"
    );
    if (!list_contains(features, "periodicGlottalSource=+") ||
        !list_contains(features, "spreadGlottis=+")) {
        fprintf(stderr, "features phoible bʰ: expected preserved voice and applied aspiration\n");
        failed = 1;
    }
    mk_string_list_free(features);
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
    if (!list_contains(features, "vowel") ||
        !list_contains(features, "tone-onset-3") ||
        !list_contains(features, "tone-offset-1")) {
        fprintf(stderr, "features tone vowel 31: expected base vowel and ordered tone levels\n");
        failed = 1;
    }
    mk_string_list_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "a⁵¹", &features),
        MK_OK,
        "features tone vowel 51"
    );
    if (!list_contains(features, "vowel") ||
        !list_contains(features, "tone-onset-5") ||
        !list_contains(features, "tone-mid-3") ||
        !list_contains(features, "tone-offset-1")) {
        fprintf(stderr, "features tone vowel 51: expected base vowel and a 5-3-1 contour\n");
        failed = 1;
    }
    mk_string_list_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "a³³", &features),
        MK_OK,
        "features level tone vowel a33"
    );
    if (!list_contains(features, "vowel")) {
        fprintf(stderr, "features level tone vowel a33: expected base vowel features\n");
        failed = 1;
    }
    if (list_contains(features, "tone-onset-upper") ||
        list_contains(features, "tone-offset-lower")) {
        fprintf(stderr, "features level tone vowel a33: expected neutral level tone to add no tone features\n");
        failed = 1;
    }
    mk_string_list_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "ai", &features),
        MK_OK,
        "features diphthong ai"
    );
    if (!list_contains(features, "vowel") ||
        !list_contains(features, "diphthong") ||
        !list_contains(features, "n1-open") ||
        !list_contains(features, "n2-close") ||
        !list_contains(features, "move-height-open-close")) {
        fprintf(stderr, "features diphthong ai: expected synthetic cluster features\n");
        failed = 1;
    }
    if (list_contains(features, "open") || list_contains(features, "close")) {
        fprintf(stderr, "features diphthong ai: expected no unqualified component qualities\n");
        failed = 1;
    }
    mk_string_list_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "aːi³³", &features),
        MK_OK,
        "features long level tone diphthong"
    );
    /* A mid level tone is a positive specification, not the absence of one. */
    if (!list_contains(features, "diphthong") ||
        !list_contains(features, "n1-long") ||
        !list_contains(features, "tone-present") ||
        !list_contains(features, "tone-onset-3") ||
        !list_contains(features, "tone-offset-3")) {
        fprintf(stderr, "features long level tone diphthong: expected n1-long and a mid level tone\n");
        failed = 1;
    }
    mk_string_list_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "əi³¹", &features),
        MK_OK,
        "features tone diphthong"
    );
    if (!list_contains(features, "diphthong") ||
        !list_contains(features, "n1-mid") ||
        !list_contains(features, "tone-onset-3") ||
        !list_contains(features, "tone-offset-1")) {
        fprintf(stderr, "features tone diphthong: expected cluster and ordered tone levels\n");
        failed = 1;
    }
    mk_string_list_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "ɛï³³", &features),
        MK_OK,
        "features precomposed tone diphthong"
    );
    if (!list_contains(features, "vowel") ||
        !list_contains(features, "diphthong") ||
        !list_contains(features, "n1-open-mid") ||
        !list_contains(features, "n2-close") ||
        !list_contains(features, "n2-centralized")) {
        fprintf(stderr, "features precomposed tone diphthong: expected cluster and normalized diaeresis features\n");
        failed = 1;
    }
    mk_string_list_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "kɣ", &features),
        MK_OK,
        "features mixed velar affricate"
    );
    if (!list_contains(features, "consonant") ||
        !list_contains(features, "affricate") ||
        !list_contains(features, "velar") ||
        list_contains(features, "voiceless") ||
        list_contains(features, "voiced") ||
        list_contains(features, "sibilant")) {
        fprintf(stderr, "features mixed velar affricate: expected velar affricate without phonation or sibilant\n");
        failed = 1;
    }
    mk_string_list_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "kk", &features),
        MK_OK,
        "features geminate cluster kk"
    );
    if (!list_contains(features, "consonant-cluster") ||
        !list_contains(features, "geminate")) {
        fprintf(stderr, "features geminate cluster kk: expected geminate cluster features\n");
        failed = 1;
    }
    mk_string_list_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "ḭ", &features),
        MK_OK,
        "features precomposed i creaky"
    );
    if (!list_contains(features, "vowel") || !list_contains(features, "creaky")) {
        fprintf(stderr, "features precomposed i creaky: expected vowel and creaky\n");
        failed = 1;
    }
    mk_string_list_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "ṳ", &features),
        MK_OK,
        "features precomposed u breathy"
    );
    if (!list_contains(features, "vowel") || !list_contains(features, "breathy")) {
        fprintf(stderr, "features precomposed u breathy: expected vowel and breathy\n");
        failed = 1;
    }
    mk_string_list_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "ṵː", &features),
        MK_OK,
        "features precomposed u creaky long"
    );
    if (!list_contains(features, "vowel") ||
        !list_contains(features, "creaky") ||
        !list_contains(features, "long")) {
        fprintf(stderr, "features precomposed u creaky long: expected vowel, creaky, and long\n");
        failed = 1;
    }
    mk_string_list_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "ṽ", &features),
        MK_OK,
        "features precomposed nasalized v"
    );
    if (!list_contains(features, "consonant") ||
        !list_contains(features, "nasalized") ||
        list_contains(features, "vowel")) {
        fprintf(stderr, "features precomposed nasalized v: expected nasalized consonant, not vowel\n");
        failed = 1;
    }
    mk_string_list_free(features);
    features = NULL;

    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "ŋ̀", &features),
        MK_OK,
        "features tone syllabic sonorant"
    );
    if (!list_contains(features, "syllabic") ||
        !list_contains(features, "tone-onset-2") ||
        !list_contains(features, "tone-offset-2")) {
        fprintf(stderr, "features tone syllabic sonorant: expected syllabic and ordered tone levels\n");
        failed = 1;
    }
    mk_string_list_free(features);
    features = NULL;

    /* `<?>` is CLTS markup for a grapheme the source could not convert, not a
     * sound this library is missing. It reports as such, so a caller checking
     * transcriptions can skip the source's own gaps without also skipping
     * segments merkmal genuinely lacks. */
    failed |= expect_status(
        mk_system_grapheme_features(descriptive, "<?>", &features),
        MK_ERR_SOURCE_MARKER,
        "features source markup reports its own status"
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
    /* Bare tone tokens are segments now. CLTS writes tone as its own segment
     * -- "t o ³³" -- which is the form the field's CLDF wordlists use, and
     * rejecting it left 26 Lexibank datasets unreadable. The slash forms
     * resolve because normalization takes the BIPA side of "source/BIPA". */
    failed |= expect_segment(descriptive, "¹/¹", 1, "is segment slash tone 11");
    failed |= expect_segment(descriptive, "³/¹", 1, "is segment slash tone 31");
    failed |= expect_segment(descriptive, "³¹", 1, "is segment bare tone 31");
    failed |= expect_segment(descriptive, "³⁵", 1, "is segment bare tone 35");
    failed |= expect_segment(descriptive, "⁵⁵", 1, "is segment bare tone 55");
    failed |= expect_segment(descriptive, "⁰", 1, "is segment neutral tone");
    failed |= expect_segment(descriptive, "˥˩", 1, "is segment tone letters");
    /* Still rejected: a run too long to be a contour, and neutral tone mixed
     * with a pitch level, which is not a spelling this grammar reads. */
    failed |= expect_segment(descriptive, "¹²³⁴", 0, "is segment overlong tone run");
    failed |= expect_segment(descriptive, "⁰³", 0, "is segment neutral plus level");
    /* Previously rejected: "mb" and "nd" by a two-item blocklist that accepted
     * "mp" and "nt", and the precomposed tone vowels while their canonically
     * equivalent NFD spellings were accepted. */
    failed |= expect_segment(descriptive, "mb", 1, "is segment bare mb");
    failed |= expect_segment(descriptive, "nd", 1, "is segment bare nd");
    failed |= expect_segment(descriptive, "ě", 1, "is segment precomposed e caron");
    failed |= expect_segment(descriptive, "ǎ", 1, "is segment precomposed a caron");
    failed |= expect_segment(descriptive, "ý", 1, "is segment precomposed y acute");

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

    /* Node-weight presets, reached through the scoring seam. Every preset was
     * previously verified only from Python. */
    {
        static const char *const presets[] = {
            "flat", "segmental", "ignore-tone", "ignore-length",
            "ignore-secondary", "ignore-prosodic", "tone-heavy", "tone-only"
        };
        size_t i;
        double toned = 0.0;
        double untoned = 0.0;

        for (i = 0; i < sizeof(presets) / sizeof(presets[0]); i++) {
            double value = -1.0;
            failed |= expect_status(
                mk_system_segment_distance_with_weights(
                    descriptive, "p", "b", presets[i], &value),
                MK_OK,
                presets[i]
            );
            if (!(value >= 0.0 && value <= 1.0)) {
                fprintf(stderr, "preset %s: expected a normalized value, got %.10f\n",
                    presets[i], value);
                failed = 1;
            }
        }

        /* ignore-tone zeroes the Tonal node, so two tones of one vowel collapse. */
        failed |= expect_status(
            mk_system_segment_distance_with_weights(
                descriptive, "a¹¹", "a⁵⁵", NULL, &toned),
            MK_OK,
            "distance a11 a55"
        );
        failed |= expect_status(
            mk_system_segment_distance_with_weights(
                descriptive, "a¹¹", "a⁵⁵", "ignore-tone", &untoned),
            MK_OK,
            "distance a11 a55 ignore-tone"
        );
        if (!(toned > 0.0) || untoned != 0.0) {
            fprintf(stderr,
                "ignore-tone: expected %.10f > 0 and 0.0, got %.10f and %.10f\n",
                toned, toned, untoned);
            failed = 1;
        }

        /* An unknown preset is MK_ERR_INVALID_ARGUMENT on every scoring path.
         * The cluster path used to compose its components' fallback values into
         * a plausible number and report MK_OK. */
        distance = -1.0;
        failed |= expect_status(
            mk_system_segment_distance_with_weights(
                descriptive, "p", "b", "no-such-preset", &distance),
            MK_ERR_INVALID_ARGUMENT,
            "unknown preset categorical"
        );
        distance = -1.0;
        failed |= expect_status(
            mk_system_segment_distance_with_weights(
                descriptive, "ai", "au", "no-such-preset", &distance),
            MK_ERR_INVALID_ARGUMENT,
            "unknown preset cluster"
        );
        distance = -1.0;
        failed |= expect_status(
            mk_system_segment_distance_with_weights(
                phoible, "p", "b", "no-such-preset", &distance),
            MK_ERR_INVALID_ARGUMENT,
            "unknown preset valued"
        );
    }

    /* A valued system reaches the same seam. */
    failed |= expect_status(
        mk_system_segment_distance_with_weights(phoible, "p", "b", "flat", &distance),
        MK_OK,
        "distance phoible p b flat"
    );
    if (!(distance > 0.0 && distance < 1.0)) {
        fprintf(stderr, "distance phoible p b flat: expected intermediate value, got %.10f\n", distance);
        failed = 1;
    }

    failed |= expect_status(mk_normalize_grapheme("g", &normalized), MK_OK, "normalize g");
    failed |= expect_string(normalized, "ɡ", "normalize g");
    mk_string_free(normalized);
    normalized = NULL;

    failed |= expect_status(mk_normalize_grapheme("sh/ʃ", &normalized), MK_OK, "normalize slash");
    failed |= expect_string(normalized, "ʃ", "normalize slash");
    mk_string_free(normalized);
    normalized = NULL;

    failed |= expect_status(mk_normalize_grapheme("ã", &normalized), MK_OK, "normalize nfd nasal");
    failed |= expect_string(normalized, "ã", "normalize nfd nasal");
    mk_string_free(normalized);
    normalized = NULL;

    failed |= expect_status(mk_normalize_grapheme("ü", &normalized), MK_OK, "normalize u diaeresis");
    failed |= expect_string(normalized, "ü", "normalize u diaeresis");
    mk_string_free(normalized);
    normalized = NULL;

    failed |= expect_status(mk_normalize_grapheme("ï", &normalized), MK_OK, "normalize i diaeresis");
    failed |= expect_string(normalized, "ï", "normalize i diaeresis");
    mk_string_free(normalized);
    normalized = NULL;

    failed |= expect_status(mk_normalize_grapheme("ḭ", &normalized), MK_OK, "normalize i creaky");
    failed |= expect_string(normalized, "ḭ", "normalize i creaky");
    mk_string_free(normalized);
    normalized = NULL;

    failed |= expect_status(mk_normalize_grapheme("ṳ", &normalized), MK_OK, "normalize u breathy");
    failed |= expect_string(normalized, "ṳ", "normalize u breathy");
    mk_string_free(normalized);
    normalized = NULL;

    failed |= expect_status(mk_normalize_grapheme("ṵ", &normalized), MK_OK, "normalize u creaky");
    failed |= expect_string(normalized, "ṵ", "normalize u creaky");
    mk_string_free(normalized);
    normalized = NULL;

    failed |= expect_status(mk_normalize_grapheme("ṽ", &normalized), MK_OK, "normalize v nasalized");
    failed |= expect_string(normalized, "ṽ", "normalize v nasalized");
    mk_string_free(normalized);
    normalized = NULL;

    failed |= expect_status(mk_normalize_grapheme("ˈ", &normalized), MK_OK, "normalize bare stress");
    failed |= expect_string(normalized, "", "normalize bare stress");
    mk_string_free(normalized);
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

    {
        /* IPA tone letters are Chao digits written differently and must survive
         * merging. The tokenizer grouped them into a tone run that the merge
         * step could not decode, so it judged the run all-zero and dropped it:
         * "a˥" came back as a toneless "a". */
        mk_string_list *segments = NULL;
        double letters = 0.0;
        double digits = 0.0;

        failed |= expect_status(mk_segment_ipa_merged("ka˥ba˧", &segments), MK_OK, "segment tone letters");
        if (mk_string_list_size(segments) != 4) {
            fprintf(stderr, "segment tone letters: expected 4, got %zu\n", mk_string_list_size(segments));
            failed = 1;
        }
        failed |= expect_list_item(segments, 1, "a˥", "segment tone letter kept");
        failed |= expect_list_item(segments, 3, "a˧", "segment tone letter kept 3");
        mk_string_list_free(segments);

        /* And the two notations must score the same, since they say the same
         * thing: level 1 against level 5. */
        failed |= expect_status(
            mk_system_segment_distance(descriptive, "a˩", "a˥", &letters),
            MK_OK,
            "distance tone letters"
        );
        failed |= expect_status(
            mk_system_segment_distance(descriptive, "a¹¹", "a⁵⁵", &digits),
            MK_OK,
            "distance tone digits"
        );
        if (letters != digits || !(letters > 0.0)) {
            fprintf(stderr,
                "tone notations disagree: letters %.10f, digits %.10f\n", letters, digits);
            failed = 1;
        }
    }

    {
        /* mk_split_tone undoes the merge, so a consumer that models tone as a
         * separate dimension does not have to reparse Chao digits itself. */
        char *base = NULL;
        char *tone = NULL;

        failed |= expect_status(mk_split_tone("a¹³", &base, &tone), MK_OK, "split tone");
        if (base == NULL || strcmp(base, "a") != 0) {
            fprintf(stderr, "split tone: expected base \"a\", got \"%s\"\n", base ? base : "(null)");
            failed = 1;
        }
        if (tone == NULL || strcmp(tone, "¹³") != 0) {
            fprintf(stderr, "split tone: expected tone \"¹³\", got \"%s\"\n", tone ? tone : "(null)");
            failed = 1;
        }
        mk_string_free(base);
        mk_string_free(tone);
        base = NULL;
        tone = NULL;

        /* An untoned segment is returned whole, with no tone. Not an error. */
        failed |= expect_status(mk_split_tone("kʰ", &base, &tone), MK_OK, "split untoned");
        if (base == NULL || strcmp(base, "kʰ") != 0) {
            fprintf(stderr, "split untoned: expected base \"kʰ\", got \"%s\"\n", base ? base : "(null)");
            failed = 1;
        }
        if (tone != NULL) {
            fprintf(stderr, "split untoned: expected no tone, got \"%s\"\n", tone);
            failed = 1;
        }
        mk_string_free(base);
        base = NULL;

        /* Splitting every merged segment round-trips the whole word. */
        /* The split is orthographic and does not read the run. Four digits are
         * not a contour this library accepts -- the recognizer rejects the
         * whole token -- but splitting it is a question about spelling, the
         * same separation mk_segment_ipa keeps when it splits "tʃa" into three
         * tokens that the descriptive system would have read as two. Asserted
         * so the documented split of responsibilities cannot drift into a
         * silent validation nobody asked this function for. */
        failed |= expect_status(
            mk_split_tone("a¹²³⁴", &base, &tone), MK_OK, "split does not validate the run");
        if (base == NULL || strcmp(base, "a") != 0 ||
            tone == NULL || strcmp(tone, "¹²³⁴") != 0) {
            fprintf(stderr, "split tone 4-digit: got base \"%s\" tone \"%s\"\n",
                base ? base : "(null)", tone ? tone : "(null)");
            failed = 1;
        }
        mk_string_free(base);
        mk_string_free(tone);
        base = NULL;
        tone = NULL;
        /* And the recognizer is where that token is refused. */
        failed |= expect_segment(descriptive, "a¹²³⁴", 0, "the recognizer rejects the run");

        failed |= expect_status(mk_split_tone("o³¹", &base, &tone), MK_OK, "split tone 2");
        if (base == NULL || strcmp(base, "o") != 0 || tone == NULL || strcmp(tone, "³¹") != 0) {
            fprintf(stderr, "split tone 2: got base \"%s\" tone \"%s\"\n",
                base ? base : "(null)", tone ? tone : "(null)");
            failed = 1;
        }
        mk_string_free(base);
        mk_string_free(tone);
        base = NULL;
        tone = NULL;

        /* A standalone tone cluster is not a segment, and splitting one is an
         * error rather than an empty base. */
        failed |= expect_status(
            mk_split_tone("³¹", &base, &tone),
            MK_ERR_UNKNOWN_GRAPHEME,
            "split standalone tone"
        );
        if (base != NULL || tone != NULL) {
            fprintf(stderr, "split standalone tone: expected no outputs on error\n");
            failed = 1;
        }

        failed |= expect_status(mk_split_tone(NULL, &base, &tone), MK_ERR_INVALID_ARGUMENT, "split null");
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

    /* System identity. Both were exported, documented and never called by
     * anything -- not a test, not the example, not the Python extension. The
     * kind matters to a caller because coverage means different things by it:
     * a valued system's is a real fraction, a categorical one's is 1.0 for any
     * pair that reaches a scored dimension.
     *
     * The two returns have different lifetimes behind identical signatures. The
     * name is registry-owned storage, so it stays valid as long as the registry
     * and, for a runtime model, is the text the caller supplied. The kind is a
     * static string. Nothing in the type says which; this is where it is
     * checked. */
    {
        const mk_system *valued = NULL;
        const char *name = NULL;
        const char *kind = NULL;

        failed |= expect_status(mk_system_name(toy, &name), MK_OK, "runtime system name");
        if (name == NULL || strcmp(name, "toy") != 0) {
            printf("FAIL: runtime system name is \"%s\"\n", name ? name : "(null)");
            failed = 1;
        }
        failed |= expect_status(mk_system_kind(toy, &kind), MK_OK, "runtime system kind");
        if (kind == NULL || strcmp(kind, "categorical") != 0) {
            printf("FAIL: runtime model is a %s system\n", kind ? kind : "(null)");
            failed = 1;
        }

        failed |= expect_status(mk_system_name(descriptive, &name), MK_OK, "builtin system name");
        if (name == NULL || strcmp(name, "descriptive") != 0) {
            printf("FAIL: builtin system name is \"%s\"\n", name ? name : "(null)");
            failed = 1;
        }

        /* The one pair where the kinds differ, which is the distinction the
         * function exists to report. */
        failed |= expect_status(
            mk_registry_get_system(registry, "phoible", &valued), MK_OK, "get phoible");
        failed |= expect_status(mk_system_kind(valued, &kind), MK_OK, "valued system kind");
        if (kind == NULL || strcmp(kind, "valued") != 0) {
            printf("FAIL: phoible is a %s system\n", kind ? kind : "(null)");
            failed = 1;
        }

        failed |= expect_status(
            mk_system_name(NULL, &name), MK_ERR_INVALID_ARGUMENT, "name of no system");
        failed |= expect_status(
            mk_system_kind(toy, NULL), MK_ERR_INVALID_ARGUMENT, "kind into no out-param");
    }

    /* A name already in the registry is refused rather than appended.
     * mk_registry_get_system returns the first match, so a second `toy` used to
     * install with MK_OK and then be unreachable for the rest of the registry's
     * life -- the caller told it worked, every query answered from the first
     * one. The compiled-in names are held to the same rule. */
    {
        char *why = NULL;

        failed |= expect_status(
            mk_registry_add_model_text(
                registry,
                "@model toy\n"
                "@type categorical\n"
                "@geometry clements-hume\n"
                "grapheme Z consonant voiced velar stop\n"
            ),
            MK_ERR_DUPLICATE_SYSTEM,
            "duplicate runtime model name"
        );
        failed |= expect_status(
            mk_registry_add_model_text_ex(
                registry,
                "@model descriptive\n"
                "@type categorical\n"
                "@geometry clements-hume\n"
                "grapheme Z consonant voiced velar stop\n",
                &why
            ),
            MK_ERR_DUPLICATE_SYSTEM,
            "runtime model may not shadow a compiled-in name"
        );
        if (why == NULL || strstr(why, "descriptive") == NULL) {
            printf("FAIL: duplicate diagnostic did not name the system\n");
            failed = 1;
        }
        mk_string_free(why);
        /* Refused before anything was installed, so the grapheme the rejected
         * models declared is nowhere and the first `toy` is untouched. */
        failed |= expect_segment(toy, "Z", 0, "rejected duplicate installed nothing");
        failed |= expect_segment(toy, "X", 1, "the first model is untouched");
    }
    /* A system pointer remains valid when the registry grows. */
    failed |= expect_segment(descriptive, "p", 1, "system pointer after registry growth");
    failed |= expect_status(mk_system_grapheme_features(toy, "X", &features), MK_OK, "features runtime X");
    if (mk_string_list_size(features) != 4) {
        fprintf(stderr, "features runtime X: expected 4, got %zu\n", mk_string_list_size(features));
        failed = 1;
    }
    mk_string_list_free(features);
    features = NULL;
    failed |= expect_status(mk_system_segment_distance(toy, "X", "Y", &distance), MK_OK, "distance runtime");
    if (!(distance > 0.0 && distance <= 1.0)) {
        fprintf(stderr, "distance runtime: expected positive finite value, got %.10f\n", distance);
        failed = 1;
    }

    {
        /* A runtime model's graphemes are lookup keys, so they go through the
         * same normalization a query does. A row written with a precomposed
         * "ã" used to be unreachable: the key stayed composed while every
         * query was decomposed, so neither spelling ever matched. Both must
         * now resolve, and so must the ligature the source conventions fold. */
        const mk_system *composed = NULL;

        failed |= expect_status(
            mk_registry_add_model_text(
                registry,
                "@model precomposed\n"
                "@type categorical\n"
                "@validation permissive\n"
                "grapheme ã vowel open front unrounded nasalized\n"
                "grapheme ʧ consonant voiceless post-alveolar affricate\n"
            ),
            MK_OK,
            "add precomposed model"
        );
        failed |= expect_status(
            mk_registry_get_system(registry, "precomposed", &composed),
            MK_OK,
            "get precomposed model"
        );
        failed |= expect_segment(composed, "ã", 1, "precomposed key, precomposed query");
        failed |= expect_segment(composed, "ã", 1, "precomposed key, decomposed query");
        failed |= expect_segment(composed, "ʧ", 1, "ligature key, ligature query");
        failed |= expect_segment(composed, "tʃ", 1, "ligature key, expanded query");
    }

    /* System-aware tokenization must agree with the system's own recognizer:
     * mk_segment_ipa splits untied "tʃ" and "kp" that descriptive accepts. */
    {
        static const struct {
            const char *input;
            size_t expected_count;
            const char *first;
        } cases[] = {
            {"tʃa", 2, "tʃ"},
            {"kpa", 2, "kp"},
            {"t͡ʃa", 2, "t͡ʃ"},
            {"papa", 4, "p"},
        };
        size_t c;

        for (c = 0; c < sizeof(cases) / sizeof(cases[0]); c++) {
            mk_string_list *tokens = NULL;
            size_t t;

            failed |= expect_status(
                mk_system_segment_ipa(descriptive, cases[c].input, &tokens),
                MK_OK,
                "system segment ipa"
            );
            if (mk_string_list_size(tokens) != cases[c].expected_count) {
                fprintf(
                    stderr,
                    "system segment ipa %s: expected %zu tokens, got %zu\n",
                    cases[c].input,
                    cases[c].expected_count,
                    mk_string_list_size(tokens)
                );
                failed = 1;
            }
            failed |= expect_string(
                mk_string_list_get(tokens, 0),
                cases[c].first,
                "system segment ipa first token"
            );
            for (t = 0; t < mk_string_list_size(tokens); t++) {
                failed |= expect_segment(
                    descriptive,
                    mk_string_list_get(tokens, t),
                    1,
                    "system segment ipa token is a segment"
                );
            }
            mk_string_list_free(tokens);
        }
    }

    mk_registry_free(registry);
    return failed ? 1 : 0;
}
