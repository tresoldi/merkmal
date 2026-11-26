/* Segment resolution. See resolver.h for the interface and for the
 * ownership rule that governs mki_resolution. */

#include "resolver.h"

#include "array.h"
#include "classes.h"
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
    mki_entry_view *out,
    mki_resolution_path *path_out
)
{
    char *without_tie;
    char *retracted;

    if (mki_inventory_find(system->builtin, normalized, scratch, out)) {
        if (path_out != NULL) {
            *path_out = MKI_RESOLVED_INVENTORY;
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
                *path_out = MKI_RESOLVED_TIE_STRIPPED;
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

        /* Freed on both paths. The view borrows the inventory's storage, never
         * `retracted`, so releasing it here does not invalidate anything in
         * *out. */
        free(retracted);
        if (hit) {
            if (path_out != NULL) {
                *path_out = MKI_RESOLVED_AFFRICATE_RETRACTED;
            }
            return MK_OK;
        }
    }
    return MK_ERR_UNKNOWN_GRAPHEME;
}

const char *mki_resolution_path_name(mki_resolution_path path)
{
    switch (path) {
    case MKI_RESOLVED_INVENTORY:
        return "inventory";
    case MKI_RESOLVED_TIE_STRIPPED:
        return "tie-stripped";
    case MKI_RESOLVED_AFFRICATE_RETRACTED:
        return "affricate-retracted";
    case MKI_RESOLVED_VOWEL_CLUSTER:
        return "vowel-cluster";
    case MKI_RESOLVED_DIACRITICS:
        return "diacritics";
    case MKI_RESOLVED_COMPLEX:
        return "complex";
    case MKI_RESOLVED_CONSONANT_CLUSTER:
        return "consonant-cluster";
    case MKI_RESOLVED_TONE:
        return "tone";
    case MKI_RESOLVED_NONE:
    default:
        return "none";
    }
}

static void mk_free_cluster_components(mki_cluster_component *components, size_t count);

void mki_resolution_clear(mki_resolution *entry)
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
    mk_free_cluster_components(entry->cluster_components, entry->cluster_component_count);
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
 * A plain struct assignment is not enough. On the compiled-inventory paths
 * `features` aliases the struct's own `inline_features` array, so a copy
 * duplicates the array but leaves `features` pointing into the *source*. The
 * moment the source goes out of scope the destination dangles -- the hazard
 * resolver.h warns about, and a reachable one: mk_parse_component_at moves a
 * stack-local resolution into a slot of mk_synthesize_cluster's frame.
 *
 * Use this rather than `*dst = *src` for any resolution that outlives its
 * source. The owned paths need no fixup: `owned_features` is heap storage that
 * the copy inherits along with the pointer. */
static void mk_resolution_move(mki_resolution *dst, const mki_resolution *src)
{
    *dst = *src;
    if (src->features == src->inline_features) {
        dst->features = dst->inline_features;
    }
}

/* The read-only feature-list helpers take `const char *const *`. Callers
 * holding the mutable `char **` half of an mki_resolution widen with a cast at
 * the call, as the call to mki_ordinal_conflict below does; C does not convert
 * `char **` to `const char *const *` on its own. Adding const is the safe
 * direction, which is why -Wcast-qual has nothing to say about it. */
static bool mk_feature_list_contains(const char *const *items, size_t count, const char *feature)
{
    return mki_features_contain(items, count, feature);
}

static mk_status mk_replace_owned_feature(
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

            if (copy == NULL) {
                return MK_ERR_OOM;
            }
            free(items[i]);
            items[i] = copy;
            return MK_OK;
        }
    }
    return MK_OK;
}

static mk_status mk_add_owned_feature(char ***items, size_t *count, size_t *cap, const char *feature)
{
    char **next;

    if (feature == NULL || feature[0] == '\0' ||
        mk_feature_list_contains((const char *const *)*items, *count, feature)) {
        return MK_OK;
    }
    next = (char **)mki_grow_array(*items, cap, *count, 1, sizeof(**items), 8);
    if (next == NULL) {
        return MK_ERR_OOM;
    }
    *items = next;
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

static mk_status mk_copy_entry_features(const mki_entry_view *entry, char ***items, size_t *count, size_t *cap)
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

static bool mk_feature_array_marks_nucleus(const char *const *items, size_t count)
{
    return mk_feature_list_contains(items, count, "vowel") ||
        mk_feature_list_contains(items, count, "syllabic") ||
        mk_feature_list_contains(items, count, "syllabic=+");
}

static bool mk_feature_array_marks_sonorant(const char *const *items, size_t count)
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

mk_feature_view mki_view_of(const mki_resolution *entry)
{
    mk_feature_view view;

    view.features = entry->features;
    view.count = entry->feature_count;
    return view;
}

mk_feature_view mki_view_of_component(const mki_cluster_component *component)
{
    mk_feature_view view;

    view.features = component->features;
    view.count = component->feature_count;
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

static bool mk_feature_base_present(char **items, size_t count, const char *feature)
{
    size_t i;
    size_t feature_len = strlen(feature);

    for (i = 0; i < count; i++) {
        if (strncmp(items[i], feature, feature_len) == 0 && items[i][feature_len] == '=') {
            return true;
        }
    }
    return false;
}

static const mki_diacritic_map *mk_match_diacritic_map(
    const mki_diacritic_map *map,
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

static const mki_tone_mark *mk_match_tone_mark(const char *text)
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

    /* One ordered label per position, not a register bit plus a height bit:
     * that pair is not monotone in the Chao digit, so level 2 and level 4
     * would differ in both bits and score as far apart as 1 and 5.
     *
     * Cannot truncate: `position` is one of three compiled-in words and
     * `level` is 1-5, checked above, so the longest result is well inside
     * 32. */
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
     * of the glide. Leaving the slot empty would make "a¹¹" differ from "a¹",
     * which are the same level tone spelled two ways. */
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
 * graphemes would tell a caller doing transcription QC the wrong thing: `<?>`
 * means the *source* has a gap CLTS could not convert, not that merkmal lacks
 * the segment. They are common in Lexibank, `<?>` and `<<->>` above all, so a
 * QC pass that cannot separate them reports other people's known gaps as its
 * own failures; mki_resolve returns MK_ERR_SOURCE_MARKER for them instead.
 *
 * Deliberately narrow: the documented conventions only. Dataset-specific noise
 * such as arrows stays MK_ERR_UNKNOWN_GRAPHEME rather than being swept in here
 * on a guess about what its author meant. */
static bool mk_is_source_marker(const char *text)
{
    if (text == NULL || text[0] == '\0') {
        return false;
    }
    /* CLDF boundary markers. */
    if (mki_streq(text, "+") || mki_streq(text, "_") || mki_streq(text, "#")) {
        return true;
    }
    /* CLTS: a grapheme the conversion could not resolve. */
    if (mki_streq(text, "<?>")) {
        return true;
    }
    /* CLDF: source material left unparsed, escaped as <<...>>. */
    if (mki_has_prefix(text, "<<")) {
        size_t len = strlen(text);
        if (len >= 4 && strcmp(text + len - 2, ">>") == 0) {
            return true;
        }
    }
    return false;
}

static void mk_free_owned_feature_array(char **features, size_t count);
static mk_status mk_synthesize_descriptive_complex(
    const mk_system *system,
    const char *normalized,
    mki_resolution *out
);
static mk_status mk_set_synthesized_entry(
    mki_resolution *out,
    mki_resolution_path path,
    const char *grapheme,
    char **features,
    size_t count,
    mki_cluster_component *components,
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
 * has tone, so it gets its own privative feature rather than being folded into level 3 (which would claim it
 * is mid) or level 1 (which would claim it is low). It has no pitch target, and
 * saying so is cheaper than inventing one. */
static mk_status mk_synthesize_bare_tone(
    const mk_system *system,
    const char *normalized,
    mki_resolution *out
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
    if (system->builtin->kind != MKI_SYSTEM_CATEGORICAL) {
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
            &features, &feature_count, &feature_cap, levels, count
        );
    }
    if (status != MK_OK) {
        goto fail;
    }

    status = mk_set_synthesized_entry(
        out, MKI_RESOLVED_TONE, normalized, features, feature_count, NULL, 0
    );
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

/* The learned effect of a mark in a valued system, or NULL when the system
 * cannot express it. */
static const mki_valued_effect *mk_find_valued_effect(const mk_system *system, const char *modifier)
{
    size_t i;

    for (i = 0; i < system->builtin->valued_effect_count; i++) {
        if (mki_streq(system->builtin->valued_effects[i].modifier, modifier)) {
            return &system->builtin->valued_effects[i];
        }
    }
    return NULL;
}

/* A system supports tone when a tone modifier can actually move one of its
 * scored dimensions. Categorical systems score against the compiled geometry,
 * whose Tonal subtree is always present, so they always qualify.
 *
 * Declaring a tone dimension is not enough: PHOIBLE has a "tone" column mapped
 * under Tonal, but no row pairs a toneless segment with a toned one, so no
 * tone effect is learned and every tone-bearing grapheme would keep tone="."
 * (a¹¹ equal to a⁵⁵). The test is therefore whether the system learned an
 * effect for some tone modifier. Returning "unsupported" instead of zero is
 * the honest answer: no tonal equality has been established. */
static bool mk_system_supports_tone(const mk_system *system)
{
    size_t i;

    if (system == NULL || system->builtin == NULL) {
        return false;
    }
    if (system->builtin->kind != MKI_SYSTEM_VALUED) {
        return true;
    }
    for (i = 0; i < system->builtin->valued_effect_count; i++) {
        const mki_valued_effect *effect = &system->builtin->valued_effects[i];

        if (strncmp(effect->modifier, "tone-", 5) == 0 && effect->feature_count > 0) {
            return true;
        }
    }
    return false;
}

/* The marks written on the current letter, as spans of the label. A mark
 * written twice on one letter adds nothing, since the features are a set:
 * "tʰʰ" would be "tʰ" and "á́" would be "á". Such a label is refused rather
 * than read as the shorter one. The same mark on two letters ("t̥ʃ̥",
 * "kʷkʷ") marks each of them, and the length mark may repeat: "aːː" is
 * overlong. */
#define MK_MAX_MARKS 64

typedef struct mk_mark_span {
    const char *start;
    size_t bytes;
} mk_mark_span;

static mk_status mk_note_mark(mk_mark_span *seen, size_t *count, const char *start, size_t bytes)
{
    size_t i;

    for (i = 0; i < *count; i++) {
        if (seen[i].bytes == bytes && memcmp(seen[i].start, start, bytes) == 0) {
            return MK_ERR_PARSE;
        }
    }
    if (*count == MK_MAX_MARKS) {
        /* More distinct marks than any segment carries. */
        return MK_ERR_PARSE;
    }
    seen[*count].start = start;
    seen[*count].bytes = bytes;
    (*count)++;
    return MK_OK;
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
    mk_mark_span marks[MK_MAX_MARKS];
    size_t mark_count = 0;
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
        const mki_diacritic_map *prefix = mk_match_diacritic_map(
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
            status = mk_note_mark(marks, &mark_count, p, extra_prefix_bytes);
            if (status != MK_OK) {
                goto fail;
            }
            status = mk_add_owned_feature(&modifiers, &modifier_count, &modifier_cap, extra_prefix);
            if (status != MK_OK) {
                goto fail;
            }
            recognized_modifier = 1;
            p += extra_prefix_bytes;
            continue;
        }
        status = mk_note_mark(marks, &mark_count, p, strlen(prefix->mark));
        if (status != MK_OK) {
            goto fail;
        }
        status = mk_add_owned_feature(&modifiers, &modifier_count, &modifier_cap, prefix->feature);
        if (status != MK_OK) {
            goto fail;
        }
        recognized_modifier = 1;
        p += strlen(prefix->mark);
    }

    while (*p != '\0') {
        const mki_tone_mark *tone = mk_match_tone_mark(p);
        const mki_diacritic_map *combining;
        const mki_diacritic_map *suffix;
        const char *extra_suffix;
        size_t extra_suffix_bytes = 0;
        size_t chao_bytes = 0;
        char one[5];
        size_t n;
        size_t i;

        if (tone != NULL) {
            status = mk_note_mark(marks, &mark_count, p, strlen(tone->mark));
            if (status != MK_OK) {
                goto fail;
            }
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
            status = mk_note_mark(marks, &mark_count, p, strlen(combining->mark));
            if (status != MK_OK) {
                goto fail;
            }
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
            status = mk_note_mark(marks, &mark_count, p, extra_suffix_bytes);
            if (status != MK_OK) {
                goto fail;
            }
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
            /* "aːː" is an overlong vowel. Adding "long" twice would
             * deduplicate to one "long" and make it identical to "aː". */
            if (mki_streq(feature, "long") &&
                mk_feature_list_contains(
                    (const char *const *)modifiers, modifier_count, "ultra-long"
                )) {
                /* A third length mark has no level left to promote to. */
                status = MK_ERR_PARSE;
                goto fail;
            }
            if (mki_streq(feature, "long") &&
                mk_feature_list_contains(
                    (const char *const *)modifiers, modifier_count, "long"
                )) {
                status = mk_replace_owned_feature(modifiers, modifier_count, "long", "ultra-long");
                if (status != MK_OK) {
                    goto fail;
                }
                recognized_modifier = 1;
                p += strlen(suffix->mark);
                continue;
            }
            if (!mki_streq(feature, "long")) {
                status = mk_note_mark(marks, &mark_count, p, strlen(suffix->mark));
                if (status != MK_OK) {
                    goto fail;
                }
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
        mark_count = 0;
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

/* Applies each mark's learned effect to a valued base row. A mark the system
 * has no effect for is refused (MK_ERR_UNSUPPORTED_MODEL), as tone is: read as
 * nothing, it made `pʰ` equal to `p` in a system with no aspiration feature,
 * and the refusal is the honest answer. */
static mk_status mk_apply_valued_modifiers(
    const mk_system *system,
    char **features,
    size_t count,
    char **modifiers,
    size_t modifier_count
)
{
    size_t i;

    for (i = 0; i < modifier_count; i++) {
        const mki_valued_effect *effect = mk_find_valued_effect(system, modifiers[i]);
        size_t j;

        if (effect == NULL) {
            return MK_ERR_UNSUPPORTED_MODEL;
        }
        for (j = 0; j < effect->feature_count; j++) {
            if (mk_feature_base_present(features, count, effect->features[j])) {
                mk_status status = mk_replace_existing_valued_feature(
                    features, count, effect->features[j], effect->states[j]
                );
                if (status != MK_OK) {
                    return status;
                }
            }
        }
    }
    return MK_OK;
}

/* Whether a system synthesizes the spellings no inventory row carries:
 * diphthongs, consonant clusters, and complex segments such as "kp".
 *
 * Every categorical system does, not only `descriptive`. Limiting it to one
 * system would leave the others, `distinctive` the default among them,
 * rejecting common segments such as `ai`, `au`, `ei` and `gb` in the field's
 * data.
 *
 * Nothing about the synthesis is system-specific. Components are resolved
 * through whichever system is asking and scored by mki_cluster_distance in
 * cluster.c, which does not look at the system's name either. */
static bool mk_admits_synthesized_clusters(const mk_system *system)
{
    return system != NULL &&
        system->builtin != NULL &&
        system->builtin->kind == MKI_SYSTEM_CATEGORICAL;
}

/* Diacritics that assert opposite values of one property. A segment carrying
 * both is a contradiction, not a combination: `s̪̩̯` is syllabic and
 * non-syllabic, `ts̪̻̺` apical and laminal. Kept, the two labels would cancel
 * or overlap and score 0.0 against the segment with either mark alone, which
 * the contrast audit counts as a collapse. Refused the way a breve plus a
 * length mark is. Inventory rows are looked up before synthesis,
 * so no row is affected. */
static const char *const mk_contradictory_modifiers[][2] = {
    {"syllabic", "non-syllabic"},
    {"apical", "laminal"},
    {"advanced", "retracted"},
    {"raised", "lowered"},
    {"more-rounded", "less-rounded"},
    {"advanced-tongue-root", "retracted-tongue-root"}
};

static bool mk_modifiers_contradict(const char *const *features, size_t count)
{
    size_t i;

    for (i = 0; i < sizeof(mk_contradictory_modifiers) / sizeof(mk_contradictory_modifiers[0]); i++) {
        if (mki_features_contain(features, count, mk_contradictory_modifiers[i][0]) &&
            mki_features_contain(features, count, mk_contradictory_modifiers[i][1])) {
            return true;
        }
    }
    return false;
}

/* Removes one owned label, keeping the order of the rest. */
static void mk_remove_owned_feature(char **items, size_t *count, const char *feature)
{
    size_t i;

    for (i = 0; i < *count; i++) {
        if (mki_streq(items[i], feature)) {
            free(items[i]);
            memmove(&items[i], &items[i + 1], (*count - i - 1) * sizeof(*items));
            (*count)--;
            return;
        }
    }
}

static const mki_place_class *mk_find_place_class(const char *place)
{
    size_t i;

    for (i = 0; i < mki_default_place_class_count; i++) {
        if (mki_streq(mki_default_place_classes[i].place, place)) {
            return &mki_default_place_classes[i];
        }
    }
    return NULL;
}

/* Applies a categorical modifier that names a place, such as dental U+032A.
 *
 * Diacritic synthesis is otherwise additive, which is right for "aspirated" and
 * wrong for a place: `n` is alveolar, and adding "dental" to it would put the
 * segment at two points of the coronal scale, which the ordinal guard refuses
 * as a parse error. Every stack the inventory does not list -- `n̪̊`, `t̪ʲʰ`,
 * `ɹ̪`, `d̪̤`, `ɾ̪` -- would then fail in the categorical systems while the
 * valued ones read it.
 *
 * A place diacritic restates where the segment is made, so it replaces the
 * base's level on the same scale. The coronal class labels the generator
 * derived from the base's place are re-derived from the new one, but only when
 * the base carried them: a system that does not use them is not given them. A
 * base with no level on that scale (`p̪`) keeps the additive behaviour. */
static mk_status mk_apply_place_modifier(
    char ***features,
    size_t *count,
    size_t *cap,
    const char *modifier,
    int *applied
)
{
    const mki_place_class *target = mk_find_place_class(modifier);
    int had_anterior;
    int had_distributed;
    size_t i;
    size_t j;
    int replaced = 0;
    mk_status status;

    *applied = 0;
    if (target == NULL) {
        return MK_OK;
    }
    for (i = 0; i < mki_clements_hume_ordinal_scale_count; i++) {
        const mki_ordinal_scale *scale = &mki_clements_hume_ordinal_scales[i];
        int on_scale = 0;

        for (j = 0; j < scale->level_count; j++) {
            if (mki_streq(scale->levels[j], modifier)) {
                on_scale = 1;
            }
        }
        if (!on_scale) {
            continue;
        }
        for (j = 0; j < scale->level_count; j++) {
            if (!mki_streq(scale->levels[j], modifier) &&
                mk_feature_list_contains(
                    (const char *const *)*features, *count, scale->levels[j]
                )) {
                mk_remove_owned_feature(*features, count, scale->levels[j]);
                replaced = 1;
            }
        }
    }
    if (!replaced) {
        return MK_OK;
    }

    had_anterior =
        mk_feature_list_contains((const char *const *)*features, *count, "anterior") ||
        mk_feature_list_contains((const char *const *)*features, *count, "non-anterior");
    had_distributed =
        mk_feature_list_contains((const char *const *)*features, *count, "distributed") ||
        mk_feature_list_contains((const char *const *)*features, *count, "non-distributed");
    mk_remove_owned_feature(*features, count, "anterior");
    mk_remove_owned_feature(*features, count, "non-anterior");
    mk_remove_owned_feature(*features, count, "distributed");
    mk_remove_owned_feature(*features, count, "non-distributed");
    status = mk_add_owned_feature(features, count, cap, modifier);
    if (status == MK_OK && had_anterior) {
        status = mk_add_owned_feature(features, count, cap, target->anterior);
    }
    if (status == MK_OK && had_distributed) {
        status = mk_add_owned_feature(features, count, cap, target->distributed);
    }
    *applied = 1;
    return status;
}

static mk_status mk_synthesize_from_diacritics(
    const mk_system *system,
    const char *normalized,
    mki_resolution *out
);

/* Hands the synthesized storage to the resolution and establishes the aliasing
 * rule resolver.h states: features == owned_features, grapheme ==
 * owned_grapheme. The caller must null its locals afterwards, because the
 * resolution owns them from here. */
static mk_status mk_set_synthesized_entry(
    mki_resolution *out,
    mki_resolution_path path,
    const char *grapheme,
    char **features,
    size_t count,
    mki_cluster_component *components,
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

static void mk_clear_cluster_component(mki_cluster_component *component)
{
    size_t i;

    for (i = 0; i < component->owned_feature_count; i++) {
        free(component->owned_features[i]);
    }
    free(component->owned_features);
    free(component->borrowed_features);
    free(component->grapheme);
    memset(component, 0, sizeof(*component));
}

static void mk_free_cluster_components(mki_cluster_component *components, size_t count)
{
    size_t i;

    if (components == NULL) {
        return;
    }
    for (i = 0; i < count; i++) {
        mk_clear_cluster_component(&components[i]);
    }
    free(components);
}

/* Reserves a part of a cluster and records its spelling. The features follow
 * once the cluster's own feature set has been built from them -- see
 * mk_attach_component_features. */
static mk_status mk_add_cluster_component(
    mki_cluster_component **components,
    size_t *count,
    size_t *cap,
    const char *start,
    size_t len
)
{
    mki_cluster_component *slot;
    char *grapheme;

    {
        mki_cluster_component *next = (mki_cluster_component *)mki_grow_array(
            *components, cap, *count, 1, sizeof(**components), 4
        );
        if (next == NULL) {
            return MK_ERR_OOM;
        }
        *components = next;
    }
    grapheme = (char *)malloc(len + 1);
    if (grapheme == NULL) {
        return MK_ERR_OOM;
    }
    memcpy(grapheme, start, len);
    grapheme[len] = '\0';

    slot = &(*components)[*count];
    memset(slot, 0, sizeof(*slot));
    slot->grapheme = grapheme;
    (*count)++;
    return MK_OK;
}

/* Whether two resolved parts denote the same segment, which is what makes a
 * two-part cluster a geminate.
 *
 * Decided from features, not by comparing the spellings byte for byte, because
 * mk_add_prenasalization decides from features too, and two rules about the
 * same two parts should not disagree about what "the same" means.
 *
 * Featural and spelling equality agree on every pair of distinct inventory
 * segments in the three categorical systems, and on the tone spellings the
 * contrast baseline declares equivalent. They differ only where a mark is
 * redundant: a nasal vowel written with a second nasal mark, a creaky one with
 * a second creaky mark. Those are one segment written twice, which is what a
 * geminate is, so the featural answer is also the right one for them.
 *
 * A false geminate would need two genuinely different segments with identical
 * features. Those score exactly zero against each other, which is the
 * undeclared collapse tools/contrast_baseline.py sweeps the categorical
 * systems for and fails on.
 *
 * Equal counts plus one-way containment: a resolved feature set does not repeat
 * a label. */
static bool mk_same_segment(const mki_resolution *a, const mki_resolution *b)
{
    size_t i;

    if (a->feature_count != b->feature_count) {
        return false;
    }
    for (i = 0; i < a->feature_count; i++) {
        if (!mki_features_contain(b->features, b->feature_count, a->features[i])) {
            return false;
        }
    }
    return true;
}

/* Carries a part's resolved features into the record, so scoring never has to
 * resolve the spelling again.
 *
 * Called after the cluster's own feature set has been composed, because that
 * composition reads the parts. Takes ownership: a synthesized part's array
 * moves across and `resolved` is left holding nothing, so the caller's clear is
 * a no-op for it. An inventory part's strings are borrowed from the compiled
 * pool or the registry and stay borrowed, but the array pointing at them is
 * copied -- for a compiled inventory it is `resolved`'s own inline scratch,
 * which dies with mk_synthesize_cluster's frame. That copy is one small
 * allocation per part, against re-resolving every part's spelling on every
 * cluster comparison. On MK_ERR_OOM the slot has no features and `resolved`
 * still owns its own. */
static mk_status mk_attach_component_features(
    mki_cluster_component *slot,
    mki_resolution *resolved
)
{
    slot->feature_count = resolved->feature_count;
    if (resolved->owned_features != NULL) {
        slot->owned_features = resolved->owned_features;
        slot->owned_feature_count = resolved->owned_feature_count;
        slot->features = (const char *const *)slot->owned_features;
        resolved->owned_features = NULL;
        resolved->owned_feature_count = 0;
        resolved->features = NULL;
        resolved->feature_count = 0;
        return MK_OK;
    }
    slot->borrowed_features = (const char **)malloc(
        (resolved->feature_count == 0 ? 1 : resolved->feature_count) *
        sizeof(*slot->borrowed_features)
    );
    if (slot->borrowed_features == NULL) {
        slot->feature_count = 0;
        return MK_ERR_OOM;
    }
    memcpy(
        slot->borrowed_features,
        resolved->features,
        resolved->feature_count * sizeof(*slot->borrowed_features)
    );
    slot->features = (const char *const *)slot->borrowed_features;
    return MK_OK;
}

static mk_status mk_add_position_features(
    char ***features,
    size_t *count,
    size_t *cap,
    const mki_resolution *component,
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
        mk_status status = mk_add_prefixed_feature(features, count, cap, prefix, feature);

        if (status != MK_OK) {
            return status;
        }
    }
    return MK_OK;
}

static mk_status mk_add_cluster_movement_features(
    char ***features,
    size_t *count,
    size_t *cap,
    const mki_resolution *from,
    const mki_resolution *to
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

        mk_status status = mk_add_movement_feature(features, count, cap, dimensions[i], from_feature, to_feature);

        if (status != MK_OK) {
            return status;
        }
    }
    return MK_OK;
}

/* What separates a vowel component from a consonant component: which codepoints
 * may start one, and what the resolved features must look like. Everything
 * between those two tests -- appending the base, accumulating combining marks
 * and modifier letters, resolving the result -- is the same for both. */
typedef struct mk_component_grammar {
    /* Whether this codepoint may begin a component of this kind. Shared
     * rejections (end of input, tone) are handled by the parser. */
    bool (*admits_start)(const char *p);
    /* Whether the resolved component is one of this kind. */
    bool (*accepts)(const mki_resolution *component);
} mk_component_grammar;

static bool mk_vowel_starts_component(const char *p)
{
    return mki_is_vowel_letter(p);
}

static bool mk_vowel_component_accepted(const mki_resolution *component)
{
    return mk_feature_array_marks_nucleus(
               component->features, component->feature_count
           ) &&
        mk_feature_list_contains(
               component->features, component->feature_count, "vowel"
        );
}

/* Source markup and control tokens are not segments and must not start one. */
static bool mk_consonant_starts_component(const char *p)
{
    return !(*p == '<' || *p == '>' || *p == '+' || *p == '-' || *p == '/' || *p == '[' || *p == ']' || mki_has_prefix(p, "→") || mki_has_prefix(p, "∼"));
}

static bool mk_consonant_component_accepted(const mki_resolution *component)
{
    return mk_feature_list_contains(
               component->features, component->feature_count, "consonant"
           ) &&
        !mk_feature_list_contains(
               component->features, component->feature_count, "vowel"
        );
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
    mki_resolution *component_out
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
    /* A prefix modifier (`ⁿ` in `ⁿph`) belongs to the base that follows it. */
    for (;;) {
        const mki_diacritic_map *prefix = mk_match_diacritic_map(
            mki_default_prefix_diacritics, mki_default_prefix_diacritic_count, p
        );

        if (prefix == NULL || p[strlen(prefix->mark)] == '\0') {
            break;
        }
        status = mki_append_text(&component, &len, &cap, prefix->mark);
        if (status != MK_OK) {
            free(component);
            return status;
        }
        p += strlen(prefix->mark);
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
        const mki_diacritic_map *combining;
        const mki_diacritic_map *suffix;
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
        mki_entry_view entry;
        status = mk_lookup_normalized(
            system, component, component_out->inline_features, &entry, NULL
        );
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
 * On MK_OK component_out owns the component and *end_out is just past it; on
 * failure component_out holds nothing to free.
 *
 * Not just one base letter plus its diacritics: that would parse `ntʃ` as
 * n + t + ʃ, taking apart inside a cluster the affricate the tokenizer and the
 * recognizer read as one segment everywhere else.
 *
 * The lookahead is one unit deep, which is all the two-letter segments need --
 * the affricates, the doubly-articulated kp/gb/ŋm, and the prenasalized stops
 * such as `mb` and `nd`, so `mbr` is mb + r. It is tried against the inventory
 * and the complex synthesizer only, never against the cluster grammars, so a
 * pair merges only when it spells one known segment; a rule that accepted any
 * cluster would swallow every adjacent pair. */
static mk_status mk_parse_component_at(
    const mk_system *system,
    const mk_component_grammar *grammar,
    const char *start,
    const char **end_out,
    mki_resolution *component_out
)
{
    const char *first_end = NULL;
    mk_status status = mk_parse_component_once(
        system, grammar, start, &first_end, component_out
    );

    if (status != MK_OK) {
        return status;
    }
    if (*first_end != '\0') {
        mki_resolution second;
        const char *second_end = NULL;
        mk_status second_status;

        memset(&second, 0, sizeof(second));
        /* The look-ahead asks whether two components read as one segment. A
         * refusal means no; running out of memory is a failure, not a no. */
        second_status = mk_parse_component_once(system, grammar, first_end, &second_end, &second);
        if (second_status == MK_ERR_OOM) {
            mki_resolution_clear(component_out);
            return MK_ERR_OOM;
        }
        if (second_status == MK_OK) {
            char *joined = NULL;
            size_t len = 0;
            size_t cap = 0;
            size_t span = (size_t)(second_end - start);
            char *text = (char *)malloc(span + 1);

            mki_resolution_clear(&second);
            if (text == NULL) {
                /* The first component is already in component_out, owned;
                 * clear it so the failure leaves nothing behind. */
                mki_resolution_clear(component_out);
                return MK_ERR_OOM;
            }
            memcpy(text, start, span);
            text[span] = '\0';
            if (mki_append_text(&joined, &len, &cap, text) != MK_OK) {
                free(joined);
                free(text);
                mki_resolution_clear(component_out);
                return MK_ERR_OOM;
            }
            {
                mki_resolution merged;
                mki_entry_view entry;
                mk_status merged_status;

                memset(&merged, 0, sizeof(merged));
                merged_status = mk_lookup_normalized(
                    system, joined, merged.inline_features, &entry, NULL
                );
                if (merged_status == MK_OK) {
                    merged.grapheme = entry.grapheme;
                    merged.features = entry.features;
                    merged.feature_count = entry.feature_count;
                } else {
                    merged_status = mk_synthesize_descriptive_complex(system, joined, &merged);
                }
                if (merged_status == MK_ERR_OOM) {
                    free(joined);
                    free(text);
                    mki_resolution_clear(component_out);
                    return MK_ERR_OOM;
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
 * imply; those four are what this struct holds. */
typedef struct mk_cluster_grammar {
    mki_resolution_path path;
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
        char ***features, size_t *count, size_t *cap, const mki_resolution *components, size_t component_count
    );
    /* Features implied by each adjacent pair, added after them. */
    mk_status (*transition_features)(
        char ***features, size_t *count, size_t *cap, const mki_resolution *components, size_t component_count
    );
} mk_cluster_grammar;

/* A prenasalised segment is a nasal followed by a non-nasal obstruent. Testing
 * only the first component would make the geminates "mm" and "nn"
 * prenasalised, and "ŋm" too, which is a doubly articulated labial-velar nasal
 * rather than a nasal plus anything. */
static mk_status mk_add_prenasalization(
    char ***features,
    size_t *count,
    size_t *cap,
    const mki_resolution *components,
    size_t component_count
)
{
    if (component_count >= 2 &&
        mk_feature_list_contains(
            components[0].features, components[0].feature_count, "nasal"
        ) &&
        !mk_feature_list_contains(
            components[1].features, components[1].feature_count, "nasal"
        ) &&
        mk_feature_list_contains(
            components[1].features, components[1].feature_count, "obstruent"
        )) {
        return mk_add_owned_feature(features, count, cap, "pre-nasalized");
    }
    return MK_OK;
}

static mk_status mk_add_vowel_movement(
    char ***features,
    size_t *count,
    size_t *cap,
    const mki_resolution *components,
    size_t component_count
)
{
    size_t i;

    for (i = 1; i < component_count; i++) {
        mk_status status = mk_add_cluster_movement_features(
            features, count, cap, &components[i - 1], &components[i]
        );
        if (status != MK_OK) {
            return status;
        }
    }
    return MK_OK;
}

static const char *const mk_vowel_cluster_classes[] = {"vowel"};
static const char *const mk_consonant_cluster_classes[] = {
    "consonant",
    "complex",
    "consonant-cluster"
};

static const mk_cluster_grammar mk_vowel_cluster_grammar = {
    MKI_RESOLVED_VOWEL_CLUSTER,
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
    MKI_RESOLVED_CONSONANT_CLUSTER,
    &mk_consonant_component_grammar,
    0,
    mk_consonant_cluster_classes,
    sizeof(mk_consonant_cluster_classes) / sizeof(mk_consonant_cluster_classes[0]),
    /* No list of refused NC sequences. "mb" and "nd" are the most frequent
     * in the world's languages, and any ambiguity that would argue for
     * refusing them applies identically to "mp", "nt", "ŋg", "ndz" and
     * "ntʃ". */
    NULL,
    NULL,
    mk_add_prenasalization,
    NULL
};

/* Tone is a property of the syllable, not of one vowel in it: `ái`, `a¹i`,
 * `ai¹` and `áá` carry one high or level tone over the whole cluster. This
 * removes every tone mark and Chao run that follows the first character into
 * `*untoned`, adds the tone's features once, and refuses (UNKNOWN_GRAPHEME) a
 * token whose tones differ, since a contour across two vowels written as two
 * tones is not a reading this grammar makes. A token with no tone is copied. */
static mk_status mk_take_syllable_tone(
    const char *normalized,
    char **untoned,
    char ***features,
    size_t *feature_count,
    size_t *feature_cap
)
{
    const char *p = normalized;
    const char *first_tone = NULL;
    size_t first_len = 0;
    size_t length = strlen(normalized);
    char *out = (char *)malloc(length + 1);
    size_t used = 0;

    *untoned = NULL;
    if (out == NULL) {
        return MK_ERR_OOM;
    }
    while (*p != '\0') {
        const mki_tone_mark *mark = p == normalized ? NULL : mk_match_tone_mark(p);
        size_t tone_len = 0;
        mk_status status = MK_ERR_UNKNOWN_GRAPHEME;

        if (mark != NULL) {
            tone_len = strlen(mark->mark);
        } else if (p != normalized) {
            char **scratch = NULL;
            size_t scratch_count = 0;
            size_t scratch_cap = 0;

            status = mk_match_chao_tone_sequence(p, &tone_len, &scratch, &scratch_count, &scratch_cap);
            mk_free_owned_feature_array(scratch, scratch_count);
            if (status != MK_OK && status != MK_ERR_UNKNOWN_GRAPHEME) {
                free(out);
                return status;
            }
            if (status != MK_OK) {
                tone_len = 0;
            }
        }
        if (tone_len == 0) {
            size_t step = mki_utf8_step(p);

            memcpy(out + used, p, step);
            used += step;
            p += step;
            continue;
        }
        if (first_tone == NULL) {
            first_tone = p;
            first_len = tone_len;
        } else if (tone_len != first_len || memcmp(p, first_tone, tone_len) != 0) {
            free(out);
            return MK_ERR_UNKNOWN_GRAPHEME;
        }
        p += tone_len;
    }
    out[used] = '\0';
    if (first_tone != NULL) {
        mk_status status;
        const mki_tone_mark *mark = mk_match_tone_mark(first_tone);

        if (mark != NULL) {
            size_t i;

            for (i = 0; i < mark->feature_count; i++) {
                status = mk_add_owned_feature(features, feature_count, feature_cap, mark->features[i]);
                if (status != MK_OK) {
                    free(out);
                    return status;
                }
            }
        } else {
            size_t bytes = 0;

            status = mk_match_chao_tone_sequence(first_tone, &bytes, features, feature_count, feature_cap);
            if (status != MK_OK) {
                free(out);
                return status;
            }
        }
    }
    *untoned = out;
    return MK_OK;
}

static mk_status mk_synthesize_cluster(
    const mk_system *system,
    const mk_cluster_grammar *grammar,
    const char *normalized,
    mki_resolution *out
)
{
    const char *p;
    mki_resolution components[3];
    size_t component_count = 0;
    mki_cluster_component *component_names = NULL;
    size_t component_name_count = 0;
    size_t component_name_cap = 0;
    char **features = NULL;
    size_t feature_count = 0;
    size_t feature_cap = 0;
    mk_status status = MK_ERR_UNKNOWN_GRAPHEME;
    char *untoned = NULL;
    size_t i;

    memset(components, 0, sizeof(components));
    if (!mk_admits_synthesized_clusters(system)) {
        return MK_ERR_UNKNOWN_GRAPHEME;
    }

    p = normalized;
    if (grammar->accepts_tone) {
        status = mk_take_syllable_tone(normalized, &untoned, &features, &feature_count, &feature_cap);
        if (status != MK_OK) {
            goto finish;
        }
        p = untoned;
    }
    while (*p != '\0') {
        const char *next = NULL;

        if (component_count == 3) {
            status = MK_ERR_UNKNOWN_GRAPHEME;
            goto finish;
        }
        status = mk_parse_component_at(
            system, grammar->component, p, &next, &components[component_count]
        );
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
            &features, &feature_count, &feature_cap, grammar->class_features[i]
        );
        if (status != MK_OK) {
            goto finish;
        }
    }
    status = mk_add_owned_feature(
        &features,
        &feature_count,
        &feature_cap,
        component_count == 2 ? grammar->two_component_feature : grammar->three_component_feature
    );
    if (status != MK_OK) {
        goto finish;
    }
    if (component_count == 2 && mk_same_segment(&components[0], &components[1])) {
        status = mk_add_owned_feature(&features, &feature_count, &feature_cap, "geminate");
        if (status != MK_OK) {
            goto finish;
        }
    }
    if (grammar->cluster_features != NULL) {
        status = grammar->cluster_features(
            &features, &feature_count, &feature_cap, components, component_count
        );
        if (status != MK_OK) {
            goto finish;
        }
    }
    /* The class labels a segment of this class carries (`vocoid`,
     * `consonantal`, ...), so that the whole-cluster term compares the
     * cluster with a segment on the dimensions a segment has. Without them a
     * diphthong's own view shared no dimension with a vowel's. */
    {
        const char *added[MKI_MAX_CLASS_FEATURES];
        size_t added_count =
            mki_class_features((const char *const *)features, feature_count, added);
        size_t k;

        for (k = 0; k < added_count; k++) {
            status = mk_add_owned_feature(&features, &feature_count, &feature_cap, added[k]);
            if (status != MK_OK) {
                goto finish;
            }
        }
    }
    for (i = 0; i < component_count; i++) {
        status = mk_add_position_features(
            &features, &feature_count, &feature_cap, &components[i], i
        );
        if (status != MK_OK) {
            goto finish;
        }
    }
    if (grammar->transition_features != NULL) {
        status = grammar->transition_features(
            &features, &feature_count, &feature_cap, components, component_count
        );
        if (status != MK_OK) {
            goto finish;
        }
    }
    for (i = 0; i < component_count; i++) {
        status = mk_attach_component_features(&component_names[i], &components[i]);
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
    /* Every slot, not only the first component_count: a component that parsed
     * and then failed to be recorded is filled but not yet counted, and leaked
     * whenever recording it ran out of memory. The slots start zeroed and the
     * clear is idempotent, so the unused ones cost nothing. */
    for (i = 0; i < sizeof(components) / sizeof(components[0]); i++) {
        mki_resolution_clear(&components[i]);
    }
    mk_free_owned_feature_array(features, feature_count);
    mk_free_cluster_components(component_names, component_name_count);
    free(untoned);
    return status;
}

static mk_status mk_synthesize_untied_complex(
    const mk_system *system,
    const char *normalized,
    mki_resolution *out
);

/* A tie bar asserts one segment, which is what this synthesizer builds, so it
 * matches the spelling with the ties removed, as the inventory lookup does for
 * rows; otherwise `tʂ` would read and `t͡ʂ` would not. The cluster grammars never see the tie-stripped form: a tie bar must not be
 * read as licensing a two-segment cluster. */
static mk_status mk_synthesize_descriptive_complex(
    const mk_system *system,
    const char *normalized,
    mki_resolution *out
)
{
    char *untied = mk_remove_tie_bars(normalized);
    mk_status status;

    if (untied == NULL) {
        return MK_ERR_OOM;
    }
    status = mk_synthesize_untied_complex(system, untied, out);
    free(untied);
    return status;
}

/* The table below fixes the features of each complex segment, so it applies
 * only to a system that lists both letters of the spelling. A runtime model
 * listing `t` alone would otherwise resolve `tʃ` with labels it never
 * declared. Every spelling in the table is two code points. */
static bool mk_lists_both_parts(const mk_system *system, const char *normalized)
{
    const char *scratch[MKI_MAX_ENTRY_FEATURES];
    mki_entry_view view;
    char first[8];
    size_t first_len = mki_utf8_step(normalized);

    if (first_len == 0 || first_len >= sizeof(first)) {
        return false;
    }
    memcpy(first, normalized, first_len);
    first[first_len] = '\0';
    return mki_inventory_find(system->builtin, first, scratch, &view) &&
        mki_inventory_find(system->builtin, normalized + first_len, scratch, &view);
}

static mk_status mk_synthesize_untied_complex(
    const mk_system *system,
    const char *normalized,
    mki_resolution *out
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
    int prenasalized = 0;
    mk_status status;

    if (!mk_admits_synthesized_clusters(system)) {
        return MK_ERR_UNKNOWN_GRAPHEME;
    }

    /* The labial-velars are one segment, not two. CLTS v1.4.1 reads `kp` as
     * "from voiceless velar stop to voiceless bilabial stop cluster", and this
     * library departs from that for `kp` and `gb`, because in the Niger-Congo
     * languages that have them the standard analysis is a single
     * doubly-articulated segment. `ŋm` is the nasal member of exactly that
     * series -- Yoruba, Ewe, Igbo -- so it gets the same departure: left as a
     * cluster it would score far from `kp` while `gb` scores close, and the
     * series would not be coherent. */
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
    } else if (mki_streq(normalized, "mb")) {
        place = "bilabial";
        phonation = "voiced";
        manner = "stop";
        sibilant = 0;
        prenasalized = 1;
    } else if (mki_streq(normalized, "nd")) {
        place = "alveolar";
        phonation = "voiced";
        manner = "stop";
        sibilant = 0;
        prenasalized = 1;
    } else if (mki_streq(normalized, "ŋg")) {
        place = "velar";
        phonation = "voiced";
        manner = "stop";
        sibilant = 0;
        prenasalized = 1;
    } else if (mki_streq(normalized, "ɲɟ")) {
        place = "palatal";
        phonation = "voiced";
        manner = "stop";
        sibilant = 0;
        prenasalized = 1;
    } else if (mki_streq(normalized, "ɳɖ")) {
        place = "retroflex";
        phonation = "voiced";
        manner = "stop";
        sibilant = 0;
        prenasalized = 1;
    } else {
        return MK_ERR_UNKNOWN_GRAPHEME;
    }
    if (!mk_lists_both_parts(system, normalized)) {
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
    if (prenasalized) {
        status = mk_add_owned_feature(&features, &count, &cap, "pre-nasalized");
        if (status != MK_OK) {
            goto fail;
        }
    }
    /* The class and articulator labels every inventory row carries. Without
     * them `mb` and `ŋg` share no place dimension and score 0.0, and `mb` is
     * farther from `b` than `ᵐb` is. */
    {
        const char *added[MKI_MAX_CLASS_FEATURES];
        size_t added_count = mki_class_features((const char *const *)features, count, added);
        size_t k;

        for (k = 0; k < added_count; k++) {
            status = mk_add_owned_feature(&features, &count, &cap, added[k]);
            if (status != MK_OK) {
                goto fail;
            }
        }
    }
    status = mk_set_synthesized_entry(out, MKI_RESOLVED_COMPLEX, normalized, features, count, NULL, 0);
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
    mki_resolution *out
)
{
    char *base = NULL;
    char **modifiers = NULL;
    size_t modifier_count = 0;
    int recognized_modifier = 0;
    int tone_seen = 0;
    mki_entry_view base_entry;
    const char *base_scratch[MKI_MAX_ENTRY_FEATURES];
    mki_resolution base_resolved;
    mki_resolution_path base_path = MKI_RESOLVED_NONE;
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
    if (status == MK_OK && base_resolved.cluster_component_count > 0) {
        status = MK_ERR_UNKNOWN_GRAPHEME;
        goto finish;
    }
    if (status == MK_OK) {
        base_path = base_resolved.path;
        for (i = 0; i < base_resolved.feature_count; i++) {
            status = mk_add_owned_feature(&features, &count, &cap, base_resolved.features[i]);
            if (status != MK_OK) {
                goto finish;
            }
        }
    } else if (status == MK_ERR_OOM) {
        goto finish;
    } else {
        status = mk_lookup_normalized(
            system, base, base_scratch, &base_entry, &base_path
        );
        if (status != MK_OK) {
            goto finish;
        }
        status = mk_copy_entry_features(&base_entry, &features, &count, &cap);
        if (status != MK_OK) {
            goto finish;
        }
    }
    if (system->builtin->kind == MKI_SYSTEM_VALUED) {
        status = mk_apply_valued_modifiers(system, features, count, modifiers, modifier_count);
        if (status != MK_OK) {
            goto finish;
        }
    } else {
        for (i = 0; i < modifier_count; i++) {
            int applied = 0;

            status = mk_apply_place_modifier(
                &features, &count, &cap, modifiers[i], &applied
            );
            if (status == MK_OK && !applied) {
                status = mk_add_owned_feature(&features, &count, &cap, modifiers[i]);
            }
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
     * silently keeping whichever came first would be arbitrary. Contradictory
     * diacritics (mk_contradictory_modifiers) are refused for the same
     * reason. */
    if (mki_ordinal_conflict((const char *const *)features, count, NULL, NULL, NULL) ||
        mk_modifiers_contradict((const char *const *)features, count)) {
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
    out->path = MKI_RESOLVED_DIACRITICS;
    /* A tone is not part of the segment it marks for tokenization: `ŋ⁵⁵`
     * stays `ŋ` and `⁵⁵`, which the tone merge then associates. */
    out->base_path = tone_seen ? MKI_RESOLVED_NONE : base_path;
    out->grapheme = out->owned_grapheme;
    out->owned_features = features;
    out->owned_feature_count = count;
    out->features = (const char *const *)features;
    out->feature_count = count;
    return MK_OK;
}

/* Whether a valued row has `feature=+`. */
static bool mk_valued_plus(const mki_entry_view *view, const char *feature)
{
    size_t len = strlen(feature);
    size_t i;

    for (i = 0; i < view->feature_count; i++) {
        const char *label = view->features[i];

        if (strncmp(label, feature, len) == 0 && label[len] == '=' && label[len + 1] == '+') {
            return true;
        }
    }
    return false;
}

/* A prenasalized segment written with a modifier letter, read as the row a
 * valued system spells with a full nasal letter. PHOIBLE writes `mb`, `nd`,
 * `ŋg`, and no `ⁿd`; its prenasalized rows differ too much from their bases
 * for one learned effect, so the modifier would otherwise be refused (and
 * before, was ignored: `ⁿd` read as `d`). `ⁿ` takes the nasal homorganic with
 * the base: `m` for a labial, `ŋ` or `ɲ` for a dorsal, `ɳ` for a retroflex,
 * `n` otherwise. On a hit the result is the listed row. */
static mk_status mk_valued_prenasal_spelling(
    const mk_system *system,
    const char *normalized,
    mki_resolution *out
)
{
    static const struct {
        const char *mark;
        const char *nasal;
    } marks[] = {
        {"ⁿ", NULL},
        {"ᵐ", "m"},
        {"ᵑ", "ŋ"},
        {"ᶮ", "ɲ"},
        {"ᶯ", "ɳ"},
    };
    const char *rest = NULL;
    const char *nasal = NULL;
    char base[8];
    char *spelled;
    mki_entry_view found;
    size_t i;
    size_t base_len;
    mk_status status;

    if (system->builtin->kind != MKI_SYSTEM_VALUED) {
        return MK_ERR_UNKNOWN_GRAPHEME;
    }
    for (i = 0; i < sizeof(marks) / sizeof(marks[0]); i++) {
        if (mki_has_prefix(normalized, marks[i].mark)) {
            rest = normalized + strlen(marks[i].mark);
            nasal = marks[i].nasal;
            break;
        }
    }
    if (rest == NULL || *rest == '\0') {
        return MK_ERR_UNKNOWN_GRAPHEME;
    }
    if (nasal == NULL) {
        mki_entry_view letter;

        base_len = mki_utf8_step(rest);
        if (base_len == 0 || base_len >= sizeof(base)) {
            return MK_ERR_UNKNOWN_GRAPHEME;
        }
        memcpy(base, rest, base_len);
        base[base_len] = '\0';
        if (!mki_inventory_find(system->builtin, base, out->inline_features, &letter)) {
            return MK_ERR_UNKNOWN_GRAPHEME;
        }
        if (mk_valued_plus(&letter, "labial") && !mk_valued_plus(&letter, "dorsal")) {
            nasal = "m";
        } else if (mk_valued_plus(&letter, "dorsal")) {
            nasal = mk_valued_plus(&letter, "front") ? "ɲ" : "ŋ";
        } else if (!mk_valued_plus(&letter, "anterior") && !mk_valued_plus(&letter, "distributed") &&
                   mk_valued_plus(&letter, "coronal")) {
            nasal = "ɳ";
        } else {
            nasal = "n";
        }
    }
    spelled = (char *)malloc(strlen(nasal) + strlen(rest) + 1);
    if (spelled == NULL) {
        return MK_ERR_OOM;
    }
    strcpy(spelled, nasal);
    strcat(spelled, rest);
    status = mk_lookup_normalized(system, spelled, out->inline_features, &found, &out->path);
    free(spelled);
    if (status != MK_OK) {
        return status;
    }
    out->grapheme = found.grapheme;
    out->features = found.features;
    out->feature_count = found.feature_count;
    return MK_OK;
}

mk_status mki_resolve(
    const mk_system *system,
    const char *utf8_grapheme,
    mki_resolution *out
)
{
    char *normalized;
    mki_entry_view entry;
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
     * the system does have it, the rewrite is wrong. Applied unconditionally,
     * the table would let a mapping such as U+026B `ɫ` to `lˠ` merge two
     * segments a PHOIBLE inventory distinguishes. */
    {
        char *literal = NULL;

        if (mki_normalize_input_grapheme_literal(utf8_grapheme, &literal) == MK_OK) {
            mki_entry_view found;

            if (mk_lookup_normalized(
                    system, literal, out->inline_features, &found, &out->path
                ) == MK_OK) {
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
        system, normalized, out->inline_features, &entry, &out->path
    );
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
         * unambiguous, and the cluster grammars, seeing it first, would reject
         * it for reasons that say nothing about tone. */
        status = mk_synthesize_bare_tone(system, normalized, out);
        if (status == MK_ERR_UNKNOWN_GRAPHEME) {
            status = mk_valued_prenasal_spelling(system, normalized, out);
        }
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
