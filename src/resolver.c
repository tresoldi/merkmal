/* Segment resolution. See resolver.h for the interface and for the
 * ownership rule that governs mk_resolution. */

#include "resolver.h"

#include "ipa.h"
#include "normalize.h"
#include "strings.h"
#include "tone.h"
#include "utf8.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char *mk_remove_tie_bars(const char *text)
{
    char *out = NULL;
    size_t len = 0;
    size_t cap = 0;
    const char *p = text;

    while (*p != '\0') {
        char one[5];
        size_t n;

        if (mki_has_prefix(p, "͡")) {
            p += strlen("͡");
            continue;
        }
        if (mki_has_prefix(p, "͜")) {
            p += strlen("͜");
            continue;
        }
        n = mki_utf8_step(p);
        memcpy(one, p, n);
        one[n] = '\0';
        if (mki_append_text(&out, &len, &cap, one) != MK_OK) {
            free(out);
            return NULL;
        }
        p += n;
    }
    if (out == NULL) {
        out = mki_strdup_internal("");
    }
    return out;
}

static char *mk_insert_affricate_retraction(const char *text)
{
    if (mki_streq(text, "tʃ")) {
        return mki_strdup_internal("t̠ʃ");
    }
    if (mki_streq(text, "dʒ")) {
        return mki_strdup_internal("d̠ʒ");
    }
    return mki_strdup_internal(text);
}

/* Three attempts at the inventory, in order: as written, with tie bars
 * removed, and with the affricate retraction mark inserted. `path_out` may be
 * NULL; callers resolving a cluster component do not care which one hit. */
static mk_status mk_lookup_normalized(
    const mk_system *system,
    const char *normalized,
    const char **scratch,
    mk_entry_view *out,
    mk_resolution_path *path_out
)
{
    char *without_tie;
    char *retracted;

    if (mki_inventory_find(system->builtin, normalized, scratch, out)) {
        if (path_out != NULL) {
            *path_out = MK_RESOLVED_INVENTORY;
        }
        return MK_OK;
    }

    without_tie = mk_remove_tie_bars(normalized);
    if (without_tie == NULL) {
        return MK_ERR_OOM;
    }
    if (!mki_streq(without_tie, normalized)) {
        if (mki_inventory_find(system->builtin, without_tie, scratch, out)) {
            free(without_tie);
            if (path_out != NULL) {
                *path_out = MK_RESOLVED_TIE_STRIPPED;
            }
            return MK_OK;
        }
    }

    retracted = mk_insert_affricate_retraction(without_tie);
    free(without_tie);
    if (retracted == NULL) {
        return MK_ERR_OOM;
    }
    {
        int hit = mki_inventory_find(system->builtin, retracted, scratch, out);

        /* Freed on both paths. The view borrows the pool, never `retracted`,
         * so releasing it here does not invalidate anything in *out. */
        free(retracted);
        if (hit) {
            if (path_out != NULL) {
                *path_out = MK_RESOLVED_AFFRICATE_RETRACTED;
            }
            return MK_OK;
        }
    }
    return MK_ERR_UNKNOWN_GRAPHEME;
}

const char *mki_resolution_path_name(mk_resolution_path path)
{
    switch (path) {
    case MK_RESOLVED_INVENTORY:
        return "inventory";
    case MK_RESOLVED_TIE_STRIPPED:
        return "tie-stripped";
    case MK_RESOLVED_AFFRICATE_RETRACTED:
        return "affricate-retracted";
    case MK_RESOLVED_VOWEL_CLUSTER:
        return "vowel-cluster";
    case MK_RESOLVED_DIACRITICS:
        return "diacritics";
    case MK_RESOLVED_COMPLEX:
        return "complex";
    case MK_RESOLVED_CONSONANT_CLUSTER:
        return "consonant-cluster";
    case MK_RESOLVED_TONE:
        return "tone";
    case MK_RESOLVED_NONE:
    default:
        return "none";
    }
}

void mki_resolution_clear(mk_resolution *entry)
{
    size_t i;

    if (entry == NULL) {
        return;
    }
    for (i = 0; i < entry->owned_feature_count; i++) {
        free(entry->owned_features[i]);
    }
    free(entry->owned_features);
    free(entry->owned_grapheme);
    for (i = 0; i < entry->cluster_component_count; i++) {
        free(entry->cluster_components[i]);
    }
    free(entry->cluster_components);
    entry->grapheme = NULL;
    entry->features = NULL;
    entry->feature_count = 0;
    entry->owned_features = NULL;
    entry->owned_feature_count = 0;
    entry->owned_grapheme = NULL;
    entry->cluster_components = NULL;
    entry->cluster_component_count = 0;
}

/* Move a resolution out of a frame that is about to die.
 *
 * A plain struct assignment is not enough. On the inventory paths `features`
 * aliases the struct's own `inline_features` array, so a copy duplicates the
 * array but leaves `features` pointing into the *source*. The moment the
 * source goes out of scope the destination dangles -- which is the hazard
 * resolver.h warns about, and it was reachable: a fuzzer found
 * "cisntstiisi\234\213\226Fve" reading a dead frame through
 * mk_synthesize_cluster.
 *
 * Use this rather than `*dst = *src` for any resolution that outlives its
 * source. The owned paths need no fixup: `owned_features` is heap storage that
 * the copy inherits along with the pointer. */
static void mk_resolution_move(mk_resolution *dst, const mk_resolution *src)
{
    *dst = *src;
    if (src->features == src->inline_features) {
        dst->features = dst->inline_features;
    }
}

/* These three only read, and say so. Callers holding the mutable `char **` half
 * of an mk_resolution widen with a cast at the call, the way the call to
 * mki_ordinal_conflict below already did; C does not convert `char **` to
 * `const char *const *` on its own. Adding const is the safe direction, which
 * is why -Wcast-qual has nothing to say about it. */
static int mk_feature_list_contains(const char *const *items, size_t count, const char *feature)
{
    size_t i;

    for (i = 0; i < count; i++) {
        if (mki_streq(items[i], feature)) {
            return 1;
        }
    }
    return 0;
}

static void mk_replace_owned_feature(
    char **items,
    size_t count,
    const char *from,
    const char *to
)
{
    size_t i;

    for (i = 0; i < count; i++) {
        if (mki_streq(items[i], from)) {
            char *copy = mki_strdup_internal(to);
            if (copy != NULL) {
                free(items[i]);
                items[i] = copy;
            }
            return;
        }
    }
}

static mk_status mk_add_owned_feature(char ***items, size_t *count, size_t *cap, const char *feature)
{
    char **next;

    if (feature == NULL || feature[0] == '\0' ||
        mk_feature_list_contains((const char *const *)*items, *count, feature)) {
        return MK_OK;
    }
    if (*count + 1 > *cap) {
        size_t new_cap = *cap == 0 ? 8 : *cap * 2;
        next = (char **)realloc(*items, new_cap * sizeof(**items));
        if (next == NULL) {
            return MK_ERR_OOM;
        }
        *items = next;
        *cap = new_cap;
    }
    (*items)[*count] = mki_strdup_internal(feature);
    if ((*items)[*count] == NULL) {
        return MK_ERR_OOM;
    }
    (*count)++;
    return MK_OK;
}

static mk_status mk_replace_existing_valued_feature(
    char **items,
    size_t count,
    const char *feature,
    char state
)
{
    size_t i;
    size_t feature_len = strlen(feature);
    char *label;

    for (i = 0; i < count; i++) {
        if (strncmp(items[i], feature, feature_len) == 0 && items[i][feature_len] == '=') {
            label = (char *)malloc(feature_len + 3);
            if (label == NULL) {
                return MK_ERR_OOM;
            }
            memcpy(label, feature, feature_len);
            label[feature_len] = '=';
            label[feature_len + 1] = state;
            label[feature_len + 2] = '\0';
            free(items[i]);
            items[i] = label;
            return MK_OK;
        }
    }
    return MK_ERR_INVALID_ARGUMENT;
}

static mk_status mk_copy_entry_features(const mk_entry_view *entry, char ***items, size_t *count, size_t *cap)
{
    size_t i;
    mk_status status;

    for (i = 0; i < entry->feature_count; i++) {
        status = mk_add_owned_feature(items, count, cap, entry->features[i]);
        if (status != MK_OK) {
            return status;
        }
    }
    return MK_OK;
}

static int mk_feature_array_marks_nucleus(const char *const *items, size_t count)
{
    return mk_feature_list_contains(items, count, "vowel") ||
        mk_feature_list_contains(items, count, "syllabic") ||
        mk_feature_list_contains(items, count, "syllabic=+");
}

static int mk_feature_array_marks_sonorant(const char *const *items, size_t count)
{
    return mk_feature_list_contains(items, count, "sonorant") ||
        mk_feature_list_contains(items, count, "nasal") ||
        mk_feature_list_contains(items, count, "lateral") ||
        mk_feature_list_contains(items, count, "trill") ||
        mk_feature_list_contains(items, count, "tap") ||
        mk_feature_list_contains(items, count, "approximant");
}

static const char *mk_feature_dimension(const char *feature)
{
    if (mki_streq(feature, "close") ||
        mki_streq(feature, "near-close") ||
        mki_streq(feature, "close-mid") ||
        mki_streq(feature, "mid") ||
        mki_streq(feature, "open-mid") ||
        mki_streq(feature, "near-open") ||
        mki_streq(feature, "open")) {
        return "height";
    }
    if (mki_streq(feature, "front") ||
        mki_streq(feature, "near-front") ||
        mki_streq(feature, "central") ||
        mki_streq(feature, "near-back") ||
        mki_streq(feature, "back")) {
        return "centrality";
    }
    if (mki_streq(feature, "rounded") || mki_streq(feature, "unrounded")) {
        return "roundedness";
    }
    if (mki_streq(feature, "long") ||
        mki_streq(feature, "mid-long") ||
        mki_streq(feature, "ultra-long") ||
        mki_streq(feature, "ultra-short")) {
        return "duration";
    }
    if (mki_streq(feature, "nasalized")) {
        return "nasalization";
    }
    if (mki_streq(feature, "centralized") ||
        mki_streq(feature, "mid-centralized") ||
        mki_streq(feature, "advanced") ||
        mki_streq(feature, "retracted")) {
        return "relative";
    }
    if (mki_streq(feature, "non-syllabic") || mki_streq(feature, "syllabic")) {
        return "syllabicity";
    }
    return NULL;
}

/* A resolved entry is a grapheme, its features, and the storage behind them.
 * Scoring wants only the middle part. */
mk_feature_view mki_view_of(const mk_resolution *entry)
{
    mk_feature_view view;

    view.features = entry->features;
    view.count = entry->feature_count;
    return view;
}

static const char *mk_view_feature_for_dimension(
    mk_feature_view view,
    const char *dimension
)
{
    size_t i;

    for (i = 0; i < view.count; i++) {
        const char *candidate = view.features[i];
        const char *candidate_dimension = mk_feature_dimension(candidate);
        if (candidate_dimension != NULL && mki_streq(candidate_dimension, dimension)) {
            return candidate;
        }
    }
    return NULL;
}

static mk_status mk_add_prefixed_feature(
    char ***items,
    size_t *count,
    size_t *cap,
    const char *prefix,
    const char *feature
)
{
    char label[96];
    int written;

    if (feature == NULL || feature[0] == '\0') {
        return MK_OK;
    }
    written = snprintf(label, sizeof(label), "%s-%s", prefix, feature);
    /* A runtime model may name features of any length, and a truncated label
     * is not a shorter name for the same thing -- it is a different feature
     * that the geometry does not know and that therefore scores against
     * nothing. Refusing is the honest answer. */
    if (written < 0 || (size_t)written >= sizeof(label)) {
        return MK_ERR_PARSE;
    }
    return mk_add_owned_feature(items, count, cap, label);
}

static mk_status mk_add_movement_feature(
    char ***items,
    size_t *count,
    size_t *cap,
    const char *dimension,
    const char *from,
    const char *to
)
{
    char label[128];
    int written;

    if (dimension == NULL || from == NULL || to == NULL) {
        return MK_OK;
    }
    written = snprintf(label, sizeof(label), "move-%s-%s-%s", dimension, from, to);
    if (written < 0 || (size_t)written >= sizeof(label)) {
        return MK_ERR_PARSE;
    }
    return mk_add_owned_feature(items, count, cap, label);
}

static int mk_feature_base_present(char **items, size_t count, const char *feature)
{
    size_t i;
    size_t feature_len = strlen(feature);

    for (i = 0; i < count; i++) {
        if (strncmp(items[i], feature, feature_len) == 0 && items[i][feature_len] == '=') {
            return 1;
        }
    }
    return 0;
}

static const mk_diacritic_map *mk_match_diacritic_map(
    const mk_diacritic_map *map,
    size_t count,
    const char *text
)
{
    size_t i;

    for (i = 0; i < count; i++) {
        if (mki_has_prefix(text, map[i].mark)) {
            return &map[i];
        }
    }
    return NULL;
}

static const char *mk_match_extra_suffix_feature(const char *text, size_t *bytes_out)
{
    if (mki_has_prefix(text, "ʳ")) {
        *bytes_out = strlen("ʳ");
        return "rhotacized";
    }
    return NULL;
}

static const char *mk_match_extra_prefix_feature(const char *text, size_t *bytes_out)
{
    if (mki_has_prefix(text, "ᵐ")) {
        *bytes_out = strlen("ᵐ");
        return "pre-nasalized";
    }
    return NULL;
}

static const mk_tone_mark *mk_match_tone_mark(const char *text)
{
    size_t i;

    for (i = 0; i < mki_default_tone_mark_count; i++) {
        if (mki_has_prefix(text, mki_default_tone_marks[i].mark)) {
            return &mki_default_tone_marks[i];
        }
    }
    return NULL;
}

/* Both notations for a Chao pitch level: the superscript digits used in
 * Sinological transcription, and the IPA tone letters U+02E5-U+02E9, which are
 * the primary IPA notation and the one CLTS uses. Note the tone letters run
 * high-to-low: U+02E5 is level 5. */
static mk_status mk_add_chao_level_features(
    char ***modifiers,
    size_t *modifier_count,
    size_t *modifier_cap,
    const char *position,
    int level
)
{
    char feature[32];

    if (level < 1 || level > 5) {
        return MK_ERR_UNKNOWN_GRAPHEME;
    }

    /* One ordered label per position. The previous encoding was a register bit
     * plus a height bit, which is not monotone in the Chao digit: level 2 and
     * level 4 differ in both bits and so scored as far apart as 1 and 5. */
    /* Cannot truncate: `position` is one of two compiled-in words and `level`
     * is 1-5, checked above, so the longest result is well inside 32. */
    snprintf(feature, sizeof(feature), "tone-%s-%d", position, level);
    return mk_add_owned_feature(modifiers, modifier_count, modifier_cap, feature);
}

static mk_status mk_add_chao_tone_features(
    char ***modifiers,
    size_t *modifier_count,
    size_t *modifier_cap,
    const int *levels,
    size_t level_count
)
{
    mk_status status;

    /* Presence of tone is its own dimension. Without it a mid-level tone and a
     * toneless segment produce identical feature sets. */
    status = mk_add_owned_feature(modifiers, modifier_count, modifier_cap, "tone-present");
    if (status != MK_OK) {
        return status;
    }

    if (level_count == 1) {
        status = mk_add_chao_level_features(
            modifiers,
            modifier_count,
            modifier_cap,
            "onset",
            levels[0]
        );
        if (status != MK_OK) {
            return status;
        }
        status = mk_add_chao_level_features(
            modifiers,
            modifier_count,
            modifier_cap,
            "mid",
            levels[0]
        );
        if (status != MK_OK) {
            return status;
        }
        return mk_add_chao_level_features(
            modifiers,
            modifier_count,
            modifier_cap,
            "offset",
            levels[0]
        );
    }

    status = mk_add_chao_level_features(
        modifiers,
        modifier_count,
        modifier_cap,
        "onset",
        levels[0]
    );
    if (status != MK_OK) {
        return status;
    }
    /* A two-digit contour names its endpoints; the mid target is the midpoint
     * of the glide. Leaving the slot empty made "a¹¹" differ from "a¹", which
     * are the same level tone spelled two ways. */
    status = mk_add_chao_level_features(
        modifiers,
        modifier_count,
        modifier_cap,
        "mid",
        level_count == 3 ? levels[1] : (levels[0] + levels[level_count - 1] + 1) / 2
    );
    if (status != MK_OK) {
        return status;
    }
    return mk_add_chao_level_features(
        modifiers,
        modifier_count,
        modifier_cap,
        "offset",
        levels[level_count - 1]
    );
}

/* CLDF and CLTS markup that a Segments column carries alongside transcription.
 *
 * These are not sounds and must not resolve. But refusing them as unknown
 * graphemes told a caller doing transcription QC the wrong thing: `<?>` means
 * the *source* has a gap CLTS could not convert, not that merkmal lacks the
 * segment. In Lexibank the two commonest, `<?>` and `<<->>`, are 33,275 tokens
 * between them, so a QC pass that cannot separate them is reporting mostly
 * other people's known gaps as its own failures.
 *
 * Deliberately narrow: the documented conventions only. Dataset-specific noise
 * such as arrows stays MK_ERR_UNKNOWN_GRAPHEME rather than being swept in here
 * on a guess about what its author meant. */
static int mk_is_source_marker(const char *text)
{
    if (text == NULL || text[0] == '\0') {
        return 0;
    }
    /* CLDF boundary markers. */
    if (mki_streq(text, "+") || mki_streq(text, "_") || mki_streq(text, "#")) {
        return 1;
    }
    /* CLTS: a grapheme the conversion could not resolve. */
    if (mki_streq(text, "<?>")) {
        return 1;
    }
    /* CLDF: source material left unparsed, escaped as <<...>>. */
    if (mki_has_prefix(text, "<<")) {
        size_t len = strlen(text);
        if (len >= 4 && strcmp(text + len - 2, ">>") == 0) {
            return 1;
        }
    }
    return 0;
}

static void mk_free_owned_feature_array(char **features, size_t count);
static mk_status mk_synthesize_descriptive_complex(
    const mk_system *system,
    const char *normalized,
    mk_resolution *out
);
static mk_status mk_set_synthesized_entry(
    mk_resolution *out,
    mk_resolution_path path,
    const char *grapheme,
    char **features,
    size_t count,
    char **components,
    size_t component_count
);

/* A whole token that is nothing but tone.
 *
 * The bound spelling "a³³" resolves through the diacritic path, where tone is a
 * property of a nucleus. This is the other spelling, and it is the one CLTS
 * uses: tone as a segment of its own. Both have to work, because the corpora
 * contain both, and merge_tone_digits converts between them.
 *
 * Chao's neutral tone "⁰" is deliberately not a pitch level here. It is the
 * notation for a syllable that carries no tone in a language that otherwise
 * has tone -- 8.3% of the tone tokens in beidasinitic -- so it gets its own
 * privative feature rather than being folded into level 3 (which would claim it
 * is mid) or level 1 (which would claim it is low). It has no pitch target, and
 * saying so is cheaper than inventing one. */
static mk_status mk_synthesize_bare_tone(
    const mk_system *system,
    const char *normalized,
    mk_resolution *out
)
{
    const char *p = normalized;
    int levels[3];
    size_t count = 0;
    int neutral = 0;
    char **features = NULL;
    size_t feature_count = 0;
    size_t feature_cap = 0;
    mk_status status;

    if (normalized == NULL || normalized[0] == '\0') {
        return MK_ERR_UNKNOWN_GRAPHEME;
    }

    while (*p != '\0') {
        int value = mki_chao_level(p);
        if (value < 0) {
            /* Some non-tone character: not a bare tone token at all. Hand back
             * to the other synthesizers rather than rejecting the input. */
            return MK_ERR_UNKNOWN_GRAPHEME;
        }
        if (value == 0) {
            neutral = 1;
        } else if (count < 3) {
            levels[count] = value;
            count++;
        } else {
            count++;
        }
        p += mki_utf8_step(p);
    }

    if (neutral && count > 0) {
        /* "⁰" mixed with pitch levels is not a contour this grammar reads. */
        return MK_ERR_PARSE;
    }
    if (count > 3) {
        return MK_ERR_PARSE;
    }

    /* Valued systems declare no dimension a tone can move, so a tone token
     * there would score a confidently wrong zero against everything. Refusing
     * is the same policy those systems already apply to bound tone. */
    if (system->builtin->kind != MK_SYSTEM_CATEGORICAL) {
        return MK_ERR_UNSUPPORTED_MODEL;
    }

    status = mk_add_owned_feature(&features, &feature_count, &feature_cap, "tonal-autosegment");
    if (status != MK_OK) {
        goto fail;
    }
    if (neutral) {
        status = mk_add_owned_feature(&features, &feature_count, &feature_cap, "tone-present");
        if (status != MK_OK) {
            goto fail;
        }
        status = mk_add_owned_feature(&features, &feature_count, &feature_cap, "tone-neutral");
    } else {
        status = mk_add_chao_tone_features(
            &features, &feature_count, &feature_cap, levels, count);
    }
    if (status != MK_OK) {
        goto fail;
    }

    status = mk_set_synthesized_entry(
        out, MK_RESOLVED_TONE, normalized, features, feature_count, NULL, 0);
    if (status != MK_OK) {
        goto fail;
    }
    return MK_OK;

fail:
    mk_free_owned_feature_array(features, feature_count);
    return status;
}

static mk_status mk_match_chao_tone_sequence(
    const char *text,
    size_t *bytes_out,
    char ***modifiers,
    size_t *modifier_count,
    size_t *modifier_cap
)
{
    const char *p = text;
    int levels[3];
    size_t count = 0;

    if (bytes_out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *bytes_out = 0;

    /* Consume the whole run of Chao digits before deciding. Stopping at three
     * and letting the caller retry on the remainder splits "a¹²³⁴" into two
     * separate tone readings whose features contradict each other. */
    while (*p != '\0') {
        int value = mki_chao_level(p);
        if (value < 1 || value > 5) {
            break;
        }
        if (count < 3) {
            levels[count] = value;
        }
        count++;
        p += mki_utf8_step(p);
    }

    if (count == 0) {
        /* Not a tone sequence at all; the caller may try other interpretations. */
        return MK_ERR_UNKNOWN_GRAPHEME;
    }
    if (count > 3) {
        /* A tone sequence, but not one this grammar accepts. Rejecting the run
         * as a whole keeps tokenization, recognition, and feature synthesis on
         * the same tone grammar. */
        return MK_ERR_PARSE;
    }

    *bytes_out = (size_t)(p - text);
    return mk_add_chao_tone_features(modifiers, modifier_count, modifier_cap, levels, count);
}

static const mk_valued_diacritic_effect *mk_find_valued_effect(const char *modifier)
{
    size_t i;

    for (i = 0; i < mki_default_valued_diacritic_effect_count; i++) {
        if (mki_streq(mki_default_valued_diacritic_effects[i].modifier, modifier)) {
            return &mki_default_valued_diacritic_effects[i];
        }
    }
    return NULL;
}

/* A system supports tone when a tone modifier can actually move one of its
 * scored dimensions. Categorical systems score against the compiled geometry,
 * whose Tonal subtree is always present, so they always qualify.
 *
 * Declaring a tone dimension is not enough: PHOIBLE has a "tone" column mapped
 * under Tonal, but no diacritic effect ever sets it, so every tone-bearing
 * grapheme would keep tone="." and a¹¹ would compare equal to a⁵⁵. The test is
 * therefore whether some tone-derived modifier has a valued effect on a
 * dimension this system actually has. Returning "unsupported" instead of zero
 * is the honest answer: no tonal equality has been established. */
static int mk_system_supports_tone(const mk_system *system)
{
    size_t i;
    size_t j;
    size_t k;

    if (system == NULL || system->builtin == NULL) {
        return 0;
    }
    if (system->builtin->kind != MK_SYSTEM_VALUED) {
        return 1;
    }
    for (i = 0; i < mki_default_valued_diacritic_effect_count; i++) {
        const mk_valued_diacritic_effect *effect = &mki_default_valued_diacritic_effects[i];
        if (strncmp(effect->modifier, "tone-", 5) != 0) {
            continue;
        }
        for (j = 0; j < effect->alternative_count; j++) {
            for (k = 0; k < system->builtin->geometry_map_count; k++) {
                if (mki_streq(system->builtin->geometry_map[k].feature, effect->alternatives[j])) {
                    return 1;
                }
            }
        }
    }
    return 0;
}

static mk_status mk_decompose_diacritics(
    const char *normalized,
    char **base_out,
    char ***modifiers_out,
    size_t *modifier_count_out,
    int *recognized_modifier_out,
    int *tone_seen_out
)
{
    const char *p;
    char *base = NULL;
    size_t base_len = 0;
    size_t base_cap = 0;
    char **modifiers = NULL;
    size_t modifier_count = 0;
    size_t modifier_cap = 0;
    int recognized_modifier = 0;
    int tone_seen = 0;
    mk_status status = MK_OK;

    if (base_out == NULL ||
        modifiers_out == NULL ||
        modifier_count_out == NULL ||
        recognized_modifier_out == NULL ||
        tone_seen_out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *base_out = NULL;
    *modifiers_out = NULL;
    *modifier_count_out = 0;
    *recognized_modifier_out = 0;
    *tone_seen_out = 0;

    p = normalized;
    while (*p != '\0') {
        const mk_diacritic_map *prefix = mk_match_diacritic_map(
            mki_default_prefix_diacritics,
            mki_default_prefix_diacritic_count,
            p
        );
        const char *extra_prefix;
        size_t extra_prefix_bytes = 0;
        if (prefix == NULL) {
            extra_prefix = mk_match_extra_prefix_feature(p, &extra_prefix_bytes);
            if (extra_prefix == NULL) {
                break;
            }
            status = mk_add_owned_feature(&modifiers, &modifier_count, &modifier_cap, extra_prefix);
            if (status != MK_OK) {
                goto fail;
            }
            recognized_modifier = 1;
            p += extra_prefix_bytes;
            continue;
        }
        status = mk_add_owned_feature(&modifiers, &modifier_count, &modifier_cap, prefix->feature);
        if (status != MK_OK) {
            goto fail;
        }
        recognized_modifier = 1;
        p += strlen(prefix->mark);
    }

    while (*p != '\0') {
        const mk_tone_mark *tone = mk_match_tone_mark(p);
        const mk_diacritic_map *combining;
        const mk_diacritic_map *suffix;
        const char *extra_suffix;
        size_t extra_suffix_bytes = 0;
        size_t chao_bytes = 0;
        char one[5];
        size_t n;
        size_t i;

        if (tone != NULL) {
            for (i = 0; i < tone->feature_count; i++) {
                status = mk_add_owned_feature(&modifiers, &modifier_count, &modifier_cap, tone->features[i]);
                if (status != MK_OK) {
                    goto fail;
                }
            }
            recognized_modifier = 1;
            tone_seen = 1;
            p += strlen(tone->mark);
            continue;
        }

        status = mk_match_chao_tone_sequence(
            p,
            &chao_bytes,
            &modifiers,
            &modifier_count,
            &modifier_cap
        );
        if (status == MK_OK) {
            recognized_modifier = 1;
            tone_seen = 1;
            p += chao_bytes;
            continue;
        }
        if (status != MK_ERR_UNKNOWN_GRAPHEME) {
            goto fail;
        }

        combining = mk_match_diacritic_map(
            mki_default_combining_diacritics,
            mki_default_combining_diacritic_count,
            p
        );
        if (combining != NULL) {
            status = mk_add_owned_feature(&modifiers, &modifier_count, &modifier_cap, combining->feature);
            if (status != MK_OK) {
                goto fail;
            }
            recognized_modifier = 1;
            p += strlen(combining->mark);
            continue;
        }

        extra_suffix = mk_match_extra_suffix_feature(p, &extra_suffix_bytes);
        if (extra_suffix != NULL) {
            status = mk_add_owned_feature(&modifiers, &modifier_count, &modifier_cap, extra_suffix);
            if (status != MK_OK) {
                goto fail;
            }
            recognized_modifier = 1;
            p += extra_suffix_bytes;
            continue;
        }

        suffix = mk_match_diacritic_map(
            mki_default_suffix_diacritics,
            mki_default_suffix_diacritic_count,
            p
        );
        if (suffix != NULL) {
            const char *feature = suffix->feature;
            /* "aːː" is an overlong vowel. Adding "long" twice deduplicates to
             * one "long", which made it identical to "aː". */
            if (mki_streq(feature, "long") &&
                mk_feature_list_contains(
                    (const char *const *)modifiers, modifier_count, "ultra-long")) {
                /* A third length mark has no level left to promote to. */
                status = MK_ERR_PARSE;
                goto fail;
            }
            if (mki_streq(feature, "long") &&
                mk_feature_list_contains(
                    (const char *const *)modifiers, modifier_count, "long")) {
                mk_replace_owned_feature(modifiers, modifier_count, "long", "ultra-long");
                recognized_modifier = 1;
                p += strlen(suffix->mark);
                continue;
            }
            status = mk_add_owned_feature(&modifiers, &modifier_count, &modifier_cap, feature);
            if (status != MK_OK) {
                goto fail;
            }
            recognized_modifier = 1;
            p += strlen(suffix->mark);
            continue;
        }

        n = mki_utf8_step(p);
        memcpy(one, p, n);
        one[n] = '\0';
        status = mki_append_text(&base, &base_len, &base_cap, one);
        if (status != MK_OK) {
            goto fail;
        }
        p += n;
    }

    if (base == NULL) {
        base = mki_strdup_internal("");
        if (base == NULL) {
            status = MK_ERR_OOM;
            goto fail;
        }
    }

    *base_out = base;
    *modifiers_out = modifiers;
    *modifier_count_out = modifier_count;
    *recognized_modifier_out = recognized_modifier;
    *tone_seen_out = tone_seen;
    return MK_OK;

fail:
    free(base);
    if (modifiers != NULL) {
        size_t j;
        for (j = 0; j < modifier_count; j++) {
            free(modifiers[j]);
        }
        free(modifiers);
    }
    return status;
}

static void mk_free_owned_feature_array(char **features, size_t count)
{
    size_t i;

    if (features == NULL) {
        return;
    }
    for (i = 0; i < count; i++) {
        free(features[i]);
    }
    free(features);
}

static mk_status mk_apply_valued_modifiers(
    char **features,
    size_t count,
    char **modifiers,
    size_t modifier_count
)
{
    size_t i;

    for (i = 0; i < modifier_count; i++) {
        const mk_valued_diacritic_effect *effect = mk_find_valued_effect(modifiers[i]);
        size_t j;
        if (effect == NULL) {
            continue;
        }
        for (j = 0; j < effect->alternative_count; j++) {
            const char *alternative = effect->alternatives[j];
            if (mk_feature_base_present(features, count, alternative)) {
                mk_status status = mk_replace_existing_valued_feature(
                    features,
                    count,
                    alternative,
                    effect->state
                );
                if (status != MK_OK) {
                    return status;
                }
                break;
            }
        }
    }
    return MK_OK;
}

/* Whether a system synthesizes the spellings no inventory row carries:
 * diphthongs, consonant clusters, and complex segments such as "kp".
 *
 * This used to name `descriptive` and only `descriptive`. That left the other
 * categorical systems rejecting 1,188 segment types -- `ai`, `au`, `ei`, `gb`,
 * 78,762 tokens of Lexibank -- which mattered little while `descriptive` was
 * the system to reach for, and matters a great deal now that `distinctive` is
 * to become the default: the default would have been the least able to read the
 * field's data.
 *
 * Nothing about the synthesis was ever descriptive-specific. Components are
 * resolved through whichever system is asking and scored by the component path
 * in system.c, which never looked at the system's name either. */
static int mk_admits_synthesized_clusters(const mk_system *system)
{
    return system != NULL &&
        system->builtin != NULL &&
        system->builtin->kind == MK_SYSTEM_CATEGORICAL;
}

static mk_status mk_synthesize_from_diacritics(
    const mk_system *system,
    const char *normalized,
    mk_resolution *out
);

/* Hands the synthesized storage to the resolution and establishes the aliasing
 * rule resolver.h states: features == owned_features, grapheme ==
 * owned_grapheme. The caller must null its locals afterwards, because the
 * resolution owns them from here. */
static mk_status mk_set_synthesized_entry(
    mk_resolution *out,
    mk_resolution_path path,
    const char *grapheme,
    char **features,
    size_t count,
    char **components,
    size_t component_count
)
{
    out->owned_grapheme = mki_strdup_internal(grapheme);
    if (out->owned_grapheme == NULL) {
        return MK_ERR_OOM;
    }
    out->path = path;
    out->grapheme = out->owned_grapheme;
    out->owned_features = features;
    out->owned_feature_count = count;
    out->features = (const char *const *)features;
    out->feature_count = count;
    out->cluster_components = components;
    out->cluster_component_count = component_count;
    return MK_OK;
}

static mk_status mk_add_cluster_component(
    char ***components,
    size_t *count,
    size_t *cap,
    const char *start,
    size_t len
)
{
    char **next;
    char *component;

    if (*count + 1 > *cap) {
        size_t new_cap = *cap == 0 ? 4 : *cap * 2;
        next = (char **)realloc(*components, new_cap * sizeof(**components));
        if (next == NULL) {
            return MK_ERR_OOM;
        }
        *components = next;
        *cap = new_cap;
    }
    component = (char *)malloc(len + 1);
    if (component == NULL) {
        return MK_ERR_OOM;
    }
    memcpy(component, start, len);
    component[len] = '\0';
    (*components)[*count] = component;
    (*count)++;
    return MK_OK;
}

static void mk_free_cluster_components(char **components, size_t count)
{
    size_t i;

    if (components == NULL) {
        return;
    }
    for (i = 0; i < count; i++) {
        free(components[i]);
    }
    free(components);
}

static mk_status mk_add_position_features(
    char ***features,
    size_t *count,
    size_t *cap,
    const mk_resolution *component,
    size_t position
)
{
    size_t i;
    char prefix[8];
    int written;

    written = snprintf(prefix, sizeof(prefix), "n%zu", position + 1);
    if (written < 0 || (size_t)written >= sizeof(prefix)) {
        return MK_ERR_PARSE;
    }
    for (i = 0; i < component->feature_count; i++) {
        const char *feature = component->features[i];
        if (mki_streq(feature, "vowel") || mki_has_prefix(feature, "tone-")) {
            continue;
        }
        if (mk_add_prefixed_feature(features, count, cap, prefix, feature) != MK_OK) {
            return MK_ERR_OOM;
        }
    }
    return MK_OK;
}

static mk_status mk_add_cluster_movement_features(
    char ***features,
    size_t *count,
    size_t *cap,
    const mk_resolution *from,
    const mk_resolution *to
)
{
    static const char *const dimensions[] = {
        "height",
        "centrality",
        "roundedness"
    };
    size_t i;

    for (i = 0; i < sizeof(dimensions) / sizeof(dimensions[0]); i++) {
        const char *from_feature = mk_view_feature_for_dimension(mki_view_of(from), dimensions[i]);
        const char *to_feature = mk_view_feature_for_dimension(mki_view_of(to), dimensions[i]);

        if (mk_add_movement_feature(features, count, cap, dimensions[i], from_feature, to_feature) != MK_OK) {
            return MK_ERR_OOM;
        }
    }
    return MK_OK;
}

/* What separates a vowel component from a consonant component: which codepoints
 * may start one, and what the resolved features must look like. Everything
 * between those two tests -- appending the base, accumulating combining marks,
 * tone marks and modifier letters, resolving the result -- is the same for
 * both, and used to be duplicated line for line. */
typedef struct mk_component_grammar {
    /* Whether this codepoint may begin a component of this kind. Shared
     * rejections (end of input, tone) are handled by the parser. */
    int (*admits_start)(const char *p);
    /* Whether the resolved component is one of this kind. */
    int (*accepts)(const mk_resolution *component);
} mk_component_grammar;

static int mk_vowel_starts_component(const char *p)
{
    return mki_is_vowel_letter(p);
}

static int mk_vowel_component_accepted(const mk_resolution *component)
{
    return mk_feature_array_marks_nucleus(
            component->features, component->feature_count) &&
        mk_feature_list_contains(
            component->features, component->feature_count, "vowel");
}

/* Source markup and control tokens are not segments and must not start one. */
static int mk_consonant_starts_component(const char *p)
{
    return !(*p == '<' ||
        *p == '>' ||
        *p == '+' ||
        *p == '-' ||
        *p == '/' ||
        *p == '[' ||
        *p == ']' ||
        mki_has_prefix(p, "→") ||
        mki_has_prefix(p, "∼"));
}

static int mk_consonant_component_accepted(const mk_resolution *component)
{
    return mk_feature_list_contains(
            component->features, component->feature_count, "consonant") &&
        !mk_feature_list_contains(
            component->features, component->feature_count, "vowel");
}

static const mk_component_grammar mk_vowel_component_grammar = {
    mk_vowel_starts_component,
    mk_vowel_component_accepted
};

static const mk_component_grammar mk_consonant_component_grammar = {
    mk_consonant_starts_component,
    mk_consonant_component_accepted
};


static mk_status mk_parse_component_once(
    const mk_system *system,
    const mk_component_grammar *grammar,
    const char *start,
    const char **end_out,
    mk_resolution *component_out
)
{
    const char *p = start;
    char *component = NULL;
    size_t len = 0;
    size_t cap = 0;
    mk_status status;

    if (*p == '\0' || mki_chao_level(p) >= 1 || mk_match_tone_mark(p) != NULL) {
        return MK_ERR_UNKNOWN_GRAPHEME;
    }
    if (!grammar->admits_start(p)) {
        return MK_ERR_UNKNOWN_GRAPHEME;
    }

    status = mki_append_text(&component, &len, &cap, "");
    if (status != MK_OK) {
        return status;
    }
    {
        char one[5];
        size_t n = mki_utf8_step(p);
        memcpy(one, p, n);
        one[n] = '\0';
        status = mki_append_text(&component, &len, &cap, one);
        if (status != MK_OK) {
            free(component);
            return status;
        }
        p += n;
    }

    while (*p != '\0') {
        const mk_diacritic_map *combining;
        const mk_diacritic_map *suffix;
        const char *extra_suffix;
        size_t extra_suffix_bytes = 0;

        if (mki_chao_level(p) >= 1 || mk_match_tone_mark(p) != NULL) {
            break;
        }
        combining = mk_match_diacritic_map(
            mki_default_combining_diacritics,
            mki_default_combining_diacritic_count,
            p
        );
        if (combining != NULL) {
            status = mki_append_text(&component, &len, &cap, combining->mark);
            if (status != MK_OK) {
                free(component);
                return status;
            }
            p += strlen(combining->mark);
            continue;
        }
        extra_suffix = mk_match_extra_suffix_feature(p, &extra_suffix_bytes);
        if (extra_suffix != NULL) {
            char mark[5];
            memcpy(mark, p, extra_suffix_bytes);
            mark[extra_suffix_bytes] = '\0';
            status = mki_append_text(&component, &len, &cap, mark);
            if (status != MK_OK) {
                free(component);
                return status;
            }
            p += extra_suffix_bytes;
            continue;
        }
        suffix = mk_match_diacritic_map(
            mki_default_suffix_diacritics,
            mki_default_suffix_diacritic_count,
            p
        );
        if (suffix != NULL) {
            status = mki_append_text(&component, &len, &cap, suffix->mark);
            if (status != MK_OK) {
                free(component);
                return status;
            }
            p += strlen(suffix->mark);
            continue;
        }
        break;
    }

    {
        mk_entry_view entry;
        status = mk_lookup_normalized(
            system, component, component_out->inline_features, &entry, NULL);
        if (status == MK_OK) {
            component_out->grapheme = entry.grapheme;
            component_out->features = entry.features;
            component_out->feature_count = entry.feature_count;
        } else if (status == MK_ERR_UNKNOWN_GRAPHEME) {
            status = mk_synthesize_from_diacritics(system, component, component_out);
        }
    }
    if (status != MK_OK) {
        free(component);
        return status;
    }
    if (!grammar->accepts(component_out)) {
        mki_resolution_clear(component_out);
        free(component);
        return MK_ERR_UNKNOWN_GRAPHEME;
    }
    *end_out = p;
    free(component);
    return MK_OK;
}

/* One component, preferring a two-letter segment over two one-letter ones.
 *
 * A component used to be exactly one base letter plus its diacritics, so `ntʃ`
 * parsed as n + t + ʃ: the affricate came apart inside the cluster even though
 * the tokenizer and the recognizer both read `tʃ` as one segment everywhere
 * else. The knowledge was already in the library and this path was not asking
 * for it.
 *
 * The lookahead is one unit deep, which is all the two-letter segments need --
 * the affricates, and the doubly-articulated kp/gb/ŋm. It is tried against the
 * inventory and the complex synthesizer only, never against the cluster
 * grammars, so `nd` and `mb` stay the clusters they are rather than being
 * merged by a rule that would swallow any adjacent pair. */
static mk_status mk_parse_component_at(
    const mk_system *system,
    const mk_component_grammar *grammar,
    const char *start,
    const char **end_out,
    mk_resolution *component_out
)
{
    const char *first_end = NULL;
    mk_status status = mk_parse_component_once(
        system, grammar, start, &first_end, component_out);

    if (status != MK_OK) {
        return status;
    }
    if (*first_end != '\0') {
        mk_resolution second;
        const char *second_end = NULL;

        memset(&second, 0, sizeof(second));
        if (mk_parse_component_once(system, grammar, first_end, &second_end, &second) == MK_OK) {
            char *joined = NULL;
            size_t len = 0;
            size_t cap = 0;
            size_t span = (size_t)(second_end - start);
            char *text = (char *)malloc(span + 1);

            mki_resolution_clear(&second);
            if (text == NULL) {
                return MK_ERR_OOM;
            }
            memcpy(text, start, span);
            text[span] = '\0';
            if (mki_append_text(&joined, &len, &cap, text) == MK_OK) {
                mk_resolution merged;
                mk_entry_view entry;
                mk_status merged_status;

                memset(&merged, 0, sizeof(merged));
                merged_status = mk_lookup_normalized(
                    system, joined, merged.inline_features, &entry, NULL);
                if (merged_status == MK_OK) {
                    merged.grapheme = entry.grapheme;
                    merged.features = entry.features;
                    merged.feature_count = entry.feature_count;
                } else {
                    merged_status = mk_synthesize_descriptive_complex(system, joined, &merged);
                }
                if (merged_status == MK_OK && grammar->accepts(&merged)) {
                    mki_resolution_clear(component_out);
                    /* `merged` dies at the closing brace; its features may
                     * alias its own inline array, so this cannot be a plain
                     * struct assignment. */
                    mk_resolution_move(component_out, &merged);
                    *end_out = second_end;
                    free(joined);
                    free(text);
                    return MK_OK;
                }
                mki_resolution_clear(&merged);
            }
            free(joined);
            free(text);
        } else {
            mki_resolution_clear(&second);
        }
    }
    *end_out = first_end;
    return MK_OK;
}

/* A cluster grammar: what a run of components of one kind means.
 *
 * The scan is the same for both kinds -- parse components left to right,
 * record their spellings, cap at three, require at least two. What differs is
 * which components are admitted, whether a trailing tone may close the run,
 * the class labels the result carries, and which features the components
 * imply. Those four differences used to be spelled out twice, around eighty
 * lines of identical scan and cleanup. */
typedef struct mk_cluster_grammar {
    mk_resolution_path path;
    const mk_component_grammar *component;
    /* Whether a trailing tone mark or Chao run may close the cluster. Only
     * vowels bear tone; the consonant component grammar admits neither, so the
     * prologue could never fire for it in any case. */
    int accepts_tone;
    /* Class labels every cluster of this kind carries, in order. */
    const char *const *class_features;
    size_t class_feature_count;
    /* Labels chosen by component count; NULL adds none. */
    const char *two_component_feature;
    const char *three_component_feature;
    /* Features implied by the run as a whole, added before the per-position
     * labels. */
    mk_status (*cluster_features)(
        char ***features, size_t *count, size_t *cap,
        const mk_resolution *components, size_t component_count);
    /* Features implied by each adjacent pair, added after them. */
    mk_status (*transition_features)(
        char ***features, size_t *count, size_t *cap,
        const mk_resolution *components, size_t component_count);
} mk_cluster_grammar;

/* A prenasalised segment is a nasal followed by a non-nasal obstruent. Testing
 * only the first component made the geminates "mm" and "nn" prenasalised, and
 * did the same to "ŋm", which is a doubly articulated labial-velar nasal
 * rather than a nasal plus anything. */
static mk_status mk_add_prenasalization(
    char ***features,
    size_t *count,
    size_t *cap,
    const mk_resolution *components,
    size_t component_count
)
{
    if (component_count >= 2 &&
        mk_feature_list_contains(
            components[0].features, components[0].feature_count, "nasal") &&
        !mk_feature_list_contains(
            components[1].features, components[1].feature_count, "nasal") &&
        mk_feature_list_contains(
            components[1].features, components[1].feature_count, "obstruent")) {
        return mk_add_owned_feature(features, count, cap, "pre-nasalized");
    }
    return MK_OK;
}

static mk_status mk_add_vowel_movement(
    char ***features,
    size_t *count,
    size_t *cap,
    const mk_resolution *components,
    size_t component_count
)
{
    size_t i;

    for (i = 1; i < component_count; i++) {
        mk_status status = mk_add_cluster_movement_features(
            features, count, cap, &components[i - 1], &components[i]);
        if (status != MK_OK) {
            return status;
        }
    }
    return MK_OK;
}

static const char *const mk_vowel_cluster_classes[] = { "vowel" };
static const char *const mk_consonant_cluster_classes[] = {
    "consonant",
    "complex",
    "consonant-cluster"
};

static const mk_cluster_grammar mk_vowel_cluster_grammar = {
    MK_RESOLVED_VOWEL_CLUSTER,
    &mk_vowel_component_grammar,
    1,
    mk_vowel_cluster_classes,
    sizeof(mk_vowel_cluster_classes) / sizeof(mk_vowel_cluster_classes[0]),
    /* "aa" is one vowel written twice, not a glide from /a/ to /a/. Whether it
     * also means length is an orthographic convention of the source, not
     * something this library can decide, so it is marked geminate below and
     * left to the caller -- the same treatment the consonant path gives "pp". */
    "diphthong",
    "triphthong",
    NULL,
    mk_add_vowel_movement
};

static const mk_cluster_grammar mk_consonant_cluster_grammar = {
    MK_RESOLVED_CONSONANT_CLUSTER,
    &mk_consonant_component_grammar,
    0,
    mk_consonant_cluster_classes,
    sizeof(mk_consonant_cluster_classes) / sizeof(mk_consonant_cluster_classes[0]),
    /* "mb" and "nd" used to be rejected while "mp", "nt", "ŋg", "ndz" and
     * "ntʃ" were accepted. Whatever ambiguity motivated that applies
     * identically to those, and these two are the most frequent NC sequences
     * in the world's languages. The list is gone rather than extended. */
    NULL,
    NULL,
    mk_add_prenasalization,
    NULL
};

static mk_status mk_synthesize_cluster(
    const mk_system *system,
    const mk_cluster_grammar *grammar,
    const char *normalized,
    mk_resolution *out
)
{
    const char *p;
    mk_resolution components[3];
    size_t component_count = 0;
    char **component_names = NULL;
    size_t component_name_count = 0;
    size_t component_name_cap = 0;
    char **features = NULL;
    size_t feature_count = 0;
    size_t feature_cap = 0;
    mk_status status = MK_ERR_UNKNOWN_GRAPHEME;
    size_t i;

    memset(components, 0, sizeof(components));
    if (!mk_admits_synthesized_clusters(system)) {
        return MK_ERR_UNKNOWN_GRAPHEME;
    }

    p = normalized;
    while (*p != '\0') {
        const char *next = NULL;

        if (grammar->accepts_tone) {
            size_t chao_bytes = 0;
            const mk_tone_mark *tone = mk_match_tone_mark(p);

            /* Tone closes the cluster: it must follow at least two components
             * and run to the end of the token. */
            if (tone != NULL) {
                if (component_count < 2 || p[strlen(tone->mark)] != '\0') {
                    status = MK_ERR_UNKNOWN_GRAPHEME;
                    goto finish;
                }
                for (i = 0; i < tone->feature_count; i++) {
                    status = mk_add_owned_feature(
                        &features, &feature_count, &feature_cap, tone->features[i]);
                    if (status != MK_OK) {
                        goto finish;
                    }
                }
                p += strlen(tone->mark);
                break;
            }

            status = mk_match_chao_tone_sequence(
                p,
                &chao_bytes,
                &features,
                &feature_count,
                &feature_cap
            );
            if (status == MK_OK) {
                if (component_count < 2 || p[chao_bytes] != '\0') {
                    status = MK_ERR_UNKNOWN_GRAPHEME;
                    goto finish;
                }
                p += chao_bytes;
                break;
            }
            if (status != MK_ERR_UNKNOWN_GRAPHEME) {
                goto finish;
            }
        }

        if (component_count == 3) {
            status = MK_ERR_UNKNOWN_GRAPHEME;
            goto finish;
        }
        status = mk_parse_component_at(
            system, grammar->component, p, &next, &components[component_count]);
        if (status != MK_OK) {
            goto finish;
        }
        if (next == p) {
            /* A component that consumed nothing would loop forever. */
            status = MK_ERR_UNKNOWN_GRAPHEME;
            goto finish;
        }
        status = mk_add_cluster_component(
            &component_names,
            &component_name_count,
            &component_name_cap,
            p,
            (size_t)(next - p)
        );
        if (status != MK_OK) {
            goto finish;
        }
        component_count++;
        p = next;
    }

    if (component_count < 2 || component_count > 3) {
        status = MK_ERR_UNKNOWN_GRAPHEME;
        goto finish;
    }
    for (i = 0; i < grammar->class_feature_count; i++) {
        status = mk_add_owned_feature(
            &features, &feature_count, &feature_cap, grammar->class_features[i]);
        if (status != MK_OK) {
            goto finish;
        }
    }
    status = mk_add_owned_feature(
        &features,
        &feature_count,
        &feature_cap,
        component_count == 2 ?
            grammar->two_component_feature : grammar->three_component_feature
    );
    if (status != MK_OK) {
        goto finish;
    }
    if (component_count == 2 && mki_streq(component_names[0], component_names[1])) {
        status = mk_add_owned_feature(&features, &feature_count, &feature_cap, "geminate");
        if (status != MK_OK) {
            goto finish;
        }
    }
    if (grammar->cluster_features != NULL) {
        status = grammar->cluster_features(
            &features, &feature_count, &feature_cap, components, component_count);
        if (status != MK_OK) {
            goto finish;
        }
    }
    for (i = 0; i < component_count; i++) {
        status = mk_add_position_features(
            &features, &feature_count, &feature_cap, &components[i], i);
        if (status != MK_OK) {
            goto finish;
        }
    }
    if (grammar->transition_features != NULL) {
        status = grammar->transition_features(
            &features, &feature_count, &feature_cap, components, component_count);
        if (status != MK_OK) {
            goto finish;
        }
    }
    status = mk_set_synthesized_entry(
        out,
        grammar->path,
        normalized,
        features,
        feature_count,
        component_names,
        component_name_count
    );
    if (status == MK_OK) {
        features = NULL;
        component_names = NULL;
        component_name_count = 0;
    }

finish:
    for (i = 0; i < component_count; i++) {
        mki_resolution_clear(&components[i]);
    }
    mk_free_owned_feature_array(features, feature_count);
    mk_free_cluster_components(component_names, component_name_count);
    return status;
}

static mk_status mk_synthesize_descriptive_complex(
    const mk_system *system,
    const char *normalized,
    mk_resolution *out
)
{
    char **features = NULL;
    size_t count = 0;
    size_t cap = 0;
    const char *place = NULL;
    const char *phonation = NULL;
    /* Manner defaults to affricate because most entries here are ones; the
     * doubly-articulated segments set it explicitly. */
    const char *manner = "affricate";
    int sibilant = 1;
    mk_status status;

    if (!mk_admits_synthesized_clusters(system)) {
        return MK_ERR_UNKNOWN_GRAPHEME;
    }

    /* The labial-velars are one segment, not two. CLTS v1.4.1 reads `kp` as
     * "from voiceless velar stop to voiceless bilabial stop cluster", and this
     * library already departs from that for `kp` and `gb`, because in the
     * Niger-Congo languages that have them the standard analysis is a single
     * doubly-articulated segment. `ŋm` is the nasal member of exactly that
     * series -- Yoruba, Ewe, Igbo -- and was the one left as a cluster, which
     * scored it 0.73 from `kp` where `gb` scores 0.25. Extending the departure
     * is what makes the series coherent; leaving it out was the anomaly. */
    if (mki_streq(normalized, "kp")) {
        place = "labio-velar";
        phonation = "voiceless";
        manner = "stop";
        sibilant = 0;
    } else if (mki_streq(normalized, "gb")) {
        place = "labio-velar";
        phonation = "voiced";
        manner = "stop";
        sibilant = 0;
    } else if (mki_streq(normalized, "ŋm")) {
        place = "labio-velar";
        phonation = "voiced";
        manner = "nasal";
        sibilant = 0;
    } else if (mki_streq(normalized, "kx")) {
        place = "velar";
        phonation = "voiceless";
    } else if (mki_streq(normalized, "gɣ")) {
        place = "velar";
        phonation = "voiced";
    } else if (mki_streq(normalized, "kɣ")) {
        place = "velar";
    } else if (mki_streq(normalized, "ts")) {
        place = "alveolar";
        phonation = "voiceless";
    } else if (mki_streq(normalized, "dz")) {
        place = "alveolar";
        phonation = "voiced";
    } else if (mki_streq(normalized, "tʃ")) {
        place = "post-alveolar";
        phonation = "voiceless";
    } else if (mki_streq(normalized, "dʒ")) {
        place = "post-alveolar";
        phonation = "voiced";
    } else if (mki_streq(normalized, "tɕ")) {
        place = "alveolo-palatal";
        phonation = "voiceless";
    } else if (mki_streq(normalized, "dʑ")) {
        place = "alveolo-palatal";
        phonation = "voiced";
    } else if (mki_streq(normalized, "tʂ")) {
        place = "retroflex";
        phonation = "voiceless";
    } else if (mki_streq(normalized, "dʐ")) {
        place = "retroflex";
        phonation = "voiced";
    } else {
        return MK_ERR_UNKNOWN_GRAPHEME;
    }

    status = mk_add_owned_feature(&features, &count, &cap, "consonant");
    if (status != MK_OK) {
        goto fail;
    }
    status = mk_add_owned_feature(&features, &count, &cap, place);
    if (status != MK_OK) {
        goto fail;
    }
    status = mk_add_owned_feature(&features, &count, &cap, manner);
    if (status != MK_OK) {
        goto fail;
    }
    status = mk_add_owned_feature(&features, &count, &cap, phonation);
    if (status != MK_OK) {
        goto fail;
    }
    if (sibilant && !mki_streq(place, "velar")) {
        status = mk_add_owned_feature(&features, &count, &cap, "sibilant");
        if (status != MK_OK) {
            goto fail;
        }
    }
    status = mk_set_synthesized_entry(out, MK_RESOLVED_COMPLEX, normalized, features, count, NULL, 0);
    if (status == MK_OK) {
        return MK_OK;
    }

fail:
    mk_free_owned_feature_array(features, count);
    return status;
}

static mk_status mk_synthesize_from_diacritics(
    const mk_system *system,
    const char *normalized,
    mk_resolution *out
)
{
    char *base = NULL;
    char **modifiers = NULL;
    size_t modifier_count = 0;
    int recognized_modifier = 0;
    int tone_seen = 0;
    mk_entry_view base_entry;
    const char *base_scratch[MK_MAX_ENTRY_FEATURES];
    mk_resolution base_resolved;
    char **features = NULL;
    size_t count = 0;
    size_t cap = 0;
    mk_status status;
    size_t i;

    memset(&base_resolved, 0, sizeof(base_resolved));
    status = mk_decompose_diacritics(
        normalized,
        &base,
        &modifiers,
        &modifier_count,
        &recognized_modifier,
        &tone_seen
    );
    if (status != MK_OK) {
        return status;
    }
    if (!recognized_modifier || mki_streq(base, normalized)) {
        status = MK_ERR_UNKNOWN_GRAPHEME;
        goto finish;
    }
    if (tone_seen && !mk_system_supports_tone(system)) {
        status = MK_ERR_UNSUPPORTED_MODEL;
        goto finish;
    }

    status = mki_resolve(system, base, &base_resolved);
    if (status == MK_OK) {
        for (i = 0; i < base_resolved.feature_count; i++) {
            status = mk_add_owned_feature(&features, &count, &cap, base_resolved.features[i]);
            if (status != MK_OK) {
                goto finish;
            }
        }
    } else {
        status = mk_lookup_normalized(
            system, base, base_scratch, &base_entry, NULL);
        if (status != MK_OK) {
            goto finish;
        }
        status = mk_copy_entry_features(&base_entry, &features, &count, &cap);
        if (status != MK_OK) {
            goto finish;
        }
    }
    if (system->builtin->kind == MK_SYSTEM_VALUED) {
        status = mk_apply_valued_modifiers(features, count, modifiers, modifier_count);
        if (status != MK_OK) {
            goto finish;
        }
    } else {
        for (i = 0; i < modifier_count; i++) {
            status = mk_add_owned_feature(&features, &count, &cap, modifiers[i]);
            if (status != MK_OK) {
                goto finish;
            }
        }
    }
    if (tone_seen &&
        !mk_feature_array_marks_nucleus((const char *const *)features, count) &&
        mk_feature_array_marks_sonorant((const char *const *)features, count)) {
        status = mk_add_owned_feature(&features, &count, &cap, "syllabic");
        if (status != MK_OK) {
            goto finish;
        }
    }
    if (tone_seen && !mk_feature_array_marks_nucleus((const char *const *)features, count)) {
        status = MK_ERR_UNKNOWN_GRAPHEME;
        goto finish;
    }
    /* A breve plus a length mark asserts both `ultra-short` and `long`. Nothing
     * downstream can act on a segment that is at two points of one scale, and
     * silently keeping whichever came first would be arbitrary. */
    if (mki_ordinal_conflict((const char *const *)features, count, NULL, NULL, NULL)) {
        status = MK_ERR_PARSE;
        goto finish;
    }

finish:
    free(base);
    mki_resolution_clear(&base_resolved);
    mk_free_owned_feature_array(modifiers, modifier_count);
    if (status != MK_OK) {
        mk_free_owned_feature_array(features, count);
        return status;
    }
    out->owned_grapheme = mki_strdup_internal(normalized);
    if (out->owned_grapheme == NULL) {
        mk_free_owned_feature_array(features, count);
        return MK_ERR_OOM;
    }
    out->path = MK_RESOLVED_DIACRITICS;
    out->grapheme = out->owned_grapheme;
    out->owned_features = features;
    out->owned_feature_count = count;
    out->features = (const char *const *)features;
    out->feature_count = count;
    return MK_OK;
}

mk_status mki_resolve(
    const mk_system *system,
    const char *utf8_grapheme,
    mk_resolution *out
)
{
    char *normalized;
    mk_entry_view entry;
    mk_status status;

    if (system == NULL || system->builtin == NULL || utf8_grapheme == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    memset(out, 0, sizeof(*out));

    if (mk_is_source_marker(utf8_grapheme)) {
        return MK_ERR_SOURCE_MARKER;
    }

    /* The written form first. A source convention rewrites one spelling into
     * another on the grounds that the system does not have the first -- so if
     * the system does have it, the rewrite is wrong, and applying the table
     * unconditionally is how U+026B came to overwrite a PHOIBLE row. */
    {
        char *literal = NULL;

        if (mki_normalize_input_grapheme_literal(utf8_grapheme, &literal) == MK_OK) {
            mk_entry_view found;

            if (mk_lookup_normalized(
                    system, literal, out->inline_features, &found, &out->path) == MK_OK) {
                out->grapheme = found.grapheme;
                out->features = found.features;
                out->feature_count = found.feature_count;
                mk_string_free(literal);
                return MK_OK;
            }
            mk_string_free(literal);
        }
    }

    status = mki_normalize_input_grapheme(utf8_grapheme, &normalized);
    if (status != MK_OK) {
        return status;
    }

    status = mk_lookup_normalized(
        system, normalized, out->inline_features, &entry, &out->path);
    if (status == MK_OK) {
        /* Borrowed: the owned_* fields stay NULL, per the rule in resolver.h.
         * For a compiled inventory `features` aliases out->inline_features,
         * which is why that array lives in the struct and not on this stack. */
        out->grapheme = entry.grapheme;
        out->features = entry.features;
        out->feature_count = entry.feature_count;
        mk_string_free(normalized);
        return MK_OK;
    }
    if (status == MK_ERR_UNKNOWN_GRAPHEME) {
        /* Tried first: a token made only of Chao digits or tone letters is
         * unambiguous, and letting the cluster grammars see it first would have
         * them reject it for reasons that say nothing about tone. */
        status = mk_synthesize_bare_tone(system, normalized, out);
        if (status == MK_ERR_UNKNOWN_GRAPHEME) {
            status = mk_synthesize_cluster(system, &mk_vowel_cluster_grammar, normalized, out);
        }
        if (status == MK_ERR_UNKNOWN_GRAPHEME) {
            status = mk_synthesize_from_diacritics(system, normalized, out);
        }
        if (status == MK_ERR_UNKNOWN_GRAPHEME) {
            status = mk_synthesize_descriptive_complex(system, normalized, out);
        }
        if (status == MK_ERR_UNKNOWN_GRAPHEME) {
            status = mk_synthesize_cluster(system, &mk_consonant_cluster_grammar, normalized, out);
        }
    }
    mk_string_free(normalized);
    return status;
}
