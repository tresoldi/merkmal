#include "internal.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *mk_kind_name(mk_system_type kind)
{
    switch (kind) {
    case MK_SYSTEM_CATEGORICAL:
        return "categorical";
    case MK_SYSTEM_VALUED:
        return "valued";
    case MK_SYSTEM_TRAINED:
        return "trained";
    default:
        return "unknown";
    }
}

static size_t mk_utf8_char_len_local(unsigned char c)
{
    if (c < 0x80) {
        return 1;
    }
    if ((c & 0xE0) == 0xC0) {
        return 2;
    }
    if ((c & 0xF0) == 0xE0) {
        return 3;
    }
    if ((c & 0xF8) == 0xF0) {
        return 4;
    }
    return 1;
}

static int mk_has_prefix_local(const char *s, const char *prefix)
{
    size_t n;

    if (s == NULL || prefix == NULL) {
        return 0;
    }
    n = strlen(prefix);
    return strncmp(s, prefix, n) == 0;
}

static mk_status mk_append_text(char **text, size_t *len, size_t *cap, const char *suffix)
{
    size_t n;
    char *next;

    n = strlen(suffix);
    if (*len + n + 1 > *cap) {
        size_t new_cap = *cap == 0 ? 32 : *cap * 2;
        while (*len + n + 1 > new_cap) {
            new_cap *= 2;
        }
        next = (char *)realloc(*text, new_cap);
        if (next == NULL) {
            return MK_ERR_OOM;
        }
        *text = next;
        *cap = new_cap;
    }
    memcpy(*text + *len, suffix, n);
    *len += n;
    (*text)[*len] = '\0';
    return MK_OK;
}

mk_status mk_system_name(const mk_system *system, const char **out)
{
    if (system == NULL || system->builtin == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = system->builtin->name;
    return MK_OK;
}

mk_status mk_system_kind(const mk_system *system, const char **out)
{
    if (system == NULL || system->builtin == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = mk_kind_name(system->builtin->kind);
    return MK_OK;
}

static const mk_builtin_entry *mk_find_entry(
    const mk_builtin_system *system,
    const char *key
)
{
    size_t i;

    for (i = 0; i < system->entry_count; i++) {
        if (mk_streq(system->entries[i].grapheme, key)) {
            return &system->entries[i];
        }
    }
    return NULL;
}

static char *mk_remove_tie_bars(const char *text)
{
    char *out = NULL;
    size_t len = 0;
    size_t cap = 0;
    const char *p = text;

    while (*p != '\0') {
        if (strncmp(p, "͡", strlen("͡")) == 0) {
            p += strlen("͡");
        } else if (strncmp(p, "͜", strlen("͜")) == 0) {
            p += strlen("͜");
        } else {
            char one[5];
            size_t n;
            unsigned char c = (unsigned char)*p;
            if (c < 0x80) {
                n = 1;
            } else if ((c & 0xE0) == 0xC0) {
                n = 2;
            } else if ((c & 0xF0) == 0xE0) {
                n = 3;
            } else if ((c & 0xF8) == 0xF0) {
                n = 4;
            } else {
                n = 1;
            }
            if (len + n + 1 > cap) {
                size_t new_cap = cap == 0 ? 32 : cap * 2;
                char *next;
                while (len + n + 1 > new_cap) {
                    new_cap *= 2;
                }
                next = (char *)realloc(out, new_cap);
                if (next == NULL) {
                    free(out);
                    return NULL;
                }
                out = next;
                cap = new_cap;
            }
            memcpy(one, p, n);
            memcpy(out + len, one, n);
            len += n;
            out[len] = '\0';
            p += n;
        }
    }
    if (out == NULL) {
        out = mk_strdup_internal("");
    }
    return out;
}

static char *mk_insert_affricate_retraction(const char *text)
{
    if (mk_streq(text, "tʃ")) {
        return mk_strdup_internal("t̠ʃ");
    }
    if (mk_streq(text, "dʒ")) {
        return mk_strdup_internal("d̠ʒ");
    }
    return mk_strdup_internal(text);
}

static mk_status mk_lookup_normalized(
    const mk_system *system,
    const char *normalized,
    const mk_builtin_entry **out
)
{
    char *without_tie;
    char *retracted;

    *out = mk_find_entry(system->builtin, normalized);
    if (*out != NULL) {
        return MK_OK;
    }

    without_tie = mk_remove_tie_bars(normalized);
    if (without_tie == NULL) {
        return MK_ERR_OOM;
    }
    if (!mk_streq(without_tie, normalized)) {
        *out = mk_find_entry(system->builtin, without_tie);
        if (*out != NULL) {
            free(without_tie);
            return MK_OK;
        }
    }

    retracted = mk_insert_affricate_retraction(without_tie);
    free(without_tie);
    if (retracted == NULL) {
        return MK_ERR_OOM;
    }
    *out = mk_find_entry(system->builtin, retracted);
    free(retracted);
    if (*out != NULL) {
        return MK_OK;
    }
    return MK_ERR_UNKNOWN_GRAPHEME;
}

mk_status mk_lookup_features(
    const mk_system *system,
    const char *utf8_grapheme,
    const mk_builtin_entry **out
)
{
    char *normalized;
    mk_status status;

    if (system == NULL || system->builtin == NULL || utf8_grapheme == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;

    status = mk_normalize_input_grapheme(utf8_grapheme, &normalized);
    if (status != MK_OK) {
        return status;
    }
    status = mk_lookup_normalized(system, normalized, out);
    mk_free_string(normalized);
    return status;
}

void mk_resolved_entry_clear(mk_resolved_entry *entry)
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
    entry->grapheme = NULL;
    entry->features = NULL;
    entry->feature_count = 0;
    entry->owned_features = NULL;
    entry->owned_feature_count = 0;
    entry->owned_grapheme = NULL;
}

static int mk_feature_list_contains(char **items, size_t count, const char *feature)
{
    size_t i;

    for (i = 0; i < count; i++) {
        if (mk_streq(items[i], feature)) {
            return 1;
        }
    }
    return 0;
}

static mk_status mk_add_owned_feature(char ***items, size_t *count, size_t *cap, const char *feature)
{
    char **next;

    if (feature == NULL || feature[0] == '\0' || mk_feature_list_contains(*items, *count, feature)) {
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
    (*items)[*count] = mk_strdup_internal(feature);
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

static mk_status mk_copy_entry_features(const mk_builtin_entry *entry, char ***items, size_t *count, size_t *cap)
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

static int mk_feature_array_contains_exact(char **items, size_t count, const char *feature)
{
    size_t i;

    for (i = 0; i < count; i++) {
        if (mk_streq(items[i], feature)) {
            return 1;
        }
    }
    return 0;
}

static int mk_feature_array_contains_prefix(char **items, size_t count, const char *prefix)
{
    size_t i;
    size_t prefix_len = strlen(prefix);

    for (i = 0; i < count; i++) {
        if (strncmp(items[i], prefix, prefix_len) == 0) {
            return 1;
        }
    }
    return 0;
}

static int mk_feature_array_marks_nucleus(char **items, size_t count)
{
    return mk_feature_array_contains_exact(items, count, "vowel") ||
        mk_feature_array_contains_exact(items, count, "syllabic") ||
        mk_feature_array_contains_exact(items, count, "syllabic=+");
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
        if (mk_has_prefix_local(text, map[i].mark)) {
            return &map[i];
        }
    }
    return NULL;
}

static const mk_tone_mark *mk_match_tone_mark(const char *text)
{
    size_t i;

    for (i = 0; i < mk_default_tone_mark_count; i++) {
        if (mk_has_prefix_local(text, mk_default_tone_marks[i].mark)) {
            return &mk_default_tone_marks[i];
        }
    }
    return NULL;
}

static int mk_chao_digit_value_local(const char *p)
{
    if (mk_has_prefix_local(p, "¹")) {
        return 1;
    }
    if (mk_has_prefix_local(p, "²")) {
        return 2;
    }
    if (mk_has_prefix_local(p, "³")) {
        return 3;
    }
    if (mk_has_prefix_local(p, "⁴")) {
        return 4;
    }
    if (mk_has_prefix_local(p, "⁵")) {
        return 5;
    }
    return -1;
}

static mk_status mk_add_chao_level_features(
    char ***modifiers,
    size_t *modifier_count,
    size_t *modifier_cap,
    const char *position,
    int level
)
{
    mk_status status;
    char feature[32];

    if (level == 3) {
        return MK_OK;
    }
    if (level < 1 || level > 5) {
        return MK_ERR_UNKNOWN_GRAPHEME;
    }

    if (level == 1 || level == 2) {
        snprintf(feature, sizeof(feature), "tone-%s-lower", position);
        status = mk_add_owned_feature(modifiers, modifier_count, modifier_cap, feature);
        if (status != MK_OK) {
            return status;
        }
    } else {
        snprintf(feature, sizeof(feature), "tone-%s-upper", position);
        status = mk_add_owned_feature(modifiers, modifier_count, modifier_cap, feature);
        if (status != MK_OK) {
            return status;
        }
    }

    snprintf(
        feature,
        sizeof(feature),
        "tone-%s-%s",
        position,
        level == 1 || level == 4 ? "lowered" : "raised"
    );
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
    if (level_count == 3) {
        status = mk_add_chao_level_features(
            modifiers,
            modifier_count,
            modifier_cap,
            "mid",
            levels[1]
        );
        if (status != MK_OK) {
            return status;
        }
    }
    return mk_add_chao_level_features(
        modifiers,
        modifier_count,
        modifier_cap,
        "offset",
        levels[level_count - 1]
    );
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

    while (*p != '\0' && count < 3) {
        int value = mk_chao_digit_value_local(p);
        if (value < 1 || value > 5) {
            break;
        }
        levels[count++] = value;
        p += mk_utf8_char_len_local((unsigned char)*p);
    }

    if (count == 0) {
        return MK_ERR_UNKNOWN_GRAPHEME;
    }
    if (mk_chao_digit_value_local(p) >= 1) {
        return MK_ERR_UNKNOWN_GRAPHEME;
    }

    *bytes_out = (size_t)(p - text);
    return mk_add_chao_tone_features(modifiers, modifier_count, modifier_cap, levels, count);
}

static const mk_valued_diacritic_effect *mk_find_valued_effect(const char *modifier)
{
    size_t i;

    for (i = 0; i < mk_default_valued_diacritic_effect_count; i++) {
        if (mk_streq(mk_default_valued_diacritic_effects[i].modifier, modifier)) {
            return &mk_default_valued_diacritic_effects[i];
        }
    }
    return NULL;
}

static mk_status mk_decompose_diacritics(
    const char *normalized,
    char **base_out,
    char ***modifiers_out,
    size_t *modifier_count_out
)
{
    const char *p;
    char *base = NULL;
    size_t base_len = 0;
    size_t base_cap = 0;
    char **modifiers = NULL;
    size_t modifier_count = 0;
    size_t modifier_cap = 0;
    mk_status status = MK_OK;

    if (base_out == NULL || modifiers_out == NULL || modifier_count_out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *base_out = NULL;
    *modifiers_out = NULL;
    *modifier_count_out = 0;

    p = normalized;
    while (*p != '\0') {
        const mk_diacritic_map *prefix = mk_match_diacritic_map(
            mk_default_prefix_diacritics,
            mk_default_prefix_diacritic_count,
            p
        );
        if (prefix == NULL) {
            break;
        }
        status = mk_add_owned_feature(&modifiers, &modifier_count, &modifier_cap, prefix->feature);
        if (status != MK_OK) {
            goto fail;
        }
        p += strlen(prefix->mark);
    }

    while (*p != '\0') {
        const mk_tone_mark *tone = mk_match_tone_mark(p);
        const mk_diacritic_map *combining;
        const mk_diacritic_map *suffix;
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
            p += chao_bytes;
            continue;
        }
        if (status != MK_ERR_UNKNOWN_GRAPHEME) {
            goto fail;
        }

        combining = mk_match_diacritic_map(
            mk_default_combining_diacritics,
            mk_default_combining_diacritic_count,
            p
        );
        if (combining != NULL) {
            status = mk_add_owned_feature(&modifiers, &modifier_count, &modifier_cap, combining->feature);
            if (status != MK_OK) {
                goto fail;
            }
            p += strlen(combining->mark);
            continue;
        }

        suffix = mk_match_diacritic_map(
            mk_default_suffix_diacritics,
            mk_default_suffix_diacritic_count,
            p
        );
        if (suffix != NULL) {
            status = mk_add_owned_feature(&modifiers, &modifier_count, &modifier_cap, suffix->feature);
            if (status != MK_OK) {
                goto fail;
            }
            p += strlen(suffix->mark);
            continue;
        }

        n = mk_utf8_char_len_local((unsigned char)*p);
        memcpy(one, p, n);
        one[n] = '\0';
        status = mk_append_text(&base, &base_len, &base_cap, one);
        if (status != MK_OK) {
            goto fail;
        }
        p += n;
    }

    if (base == NULL) {
        base = mk_strdup_internal("");
        if (base == NULL) {
            status = MK_ERR_OOM;
            goto fail;
        }
    }

    *base_out = base;
    *modifiers_out = modifiers;
    *modifier_count_out = modifier_count;
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

static mk_status mk_synthesize_from_diacritics(
    const mk_system *system,
    const char *normalized,
    mk_resolved_entry *out
)
{
    char *base = NULL;
    char **modifiers = NULL;
    size_t modifier_count = 0;
    const mk_builtin_entry *base_entry = NULL;
    char **features = NULL;
    size_t count = 0;
    size_t cap = 0;
    mk_status status;
    size_t i;

    status = mk_decompose_diacritics(normalized, &base, &modifiers, &modifier_count);
    if (status != MK_OK) {
        return status;
    }
    if (modifier_count == 0 || mk_streq(base, normalized)) {
        status = MK_ERR_UNKNOWN_GRAPHEME;
        goto finish;
    }

    status = mk_lookup_normalized(system, base, &base_entry);
    if (status != MK_OK) {
        goto finish;
    }
    status = mk_copy_entry_features(base_entry, &features, &count, &cap);
    if (status != MK_OK) {
        goto finish;
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
    if (mk_feature_array_contains_prefix(modifiers, modifier_count, "tone-") &&
        !mk_feature_array_marks_nucleus(features, count)) {
        status = MK_ERR_UNKNOWN_GRAPHEME;
        goto finish;
    }

finish:
    free(base);
    mk_free_owned_feature_array(modifiers, modifier_count);
    if (status != MK_OK) {
        mk_free_owned_feature_array(features, count);
        return status;
    }
    out->owned_grapheme = mk_strdup_internal(normalized);
    if (out->owned_grapheme == NULL) {
        mk_free_owned_feature_array(features, count);
        return MK_ERR_OOM;
    }
    out->grapheme = out->owned_grapheme;
    out->owned_features = features;
    out->owned_feature_count = count;
    out->features = (const char *const *)features;
    out->feature_count = count;
    return MK_OK;
}

mk_status mk_resolve_entry(
    const mk_system *system,
    const char *utf8_grapheme,
    mk_resolved_entry *out
)
{
    char *normalized;
    const mk_builtin_entry *entry = NULL;
    mk_status status;

    if (system == NULL || system->builtin == NULL || utf8_grapheme == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    memset(out, 0, sizeof(*out));

    status = mk_normalize_input_grapheme(utf8_grapheme, &normalized);
    if (status != MK_OK) {
        return status;
    }

    status = mk_lookup_normalized(system, normalized, &entry);
    if (status == MK_OK) {
        out->grapheme = entry->grapheme;
        out->features = entry->features;
        out->feature_count = entry->feature_count;
        mk_free_string(normalized);
        return MK_OK;
    }
    if (status == MK_ERR_UNKNOWN_GRAPHEME) {
        status = mk_synthesize_from_diacritics(system, normalized, out);
    }
    mk_free_string(normalized);
    return status;
}

mk_status mk_system_is_segment(
    const mk_system *system,
    const char *utf8_grapheme,
    int *out
)
{
    mk_resolved_entry entry;
    mk_status status;

    if (out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = 0;
    status = mk_resolve_entry(system, utf8_grapheme, &entry);
    if (status == MK_OK) {
        mk_resolved_entry_clear(&entry);
        *out = 1;
        return MK_OK;
    }
    if (status == MK_ERR_UNKNOWN_GRAPHEME) {
        return MK_OK;
    }
    return status;
}

mk_status mk_system_grapheme_features(
    const mk_system *system,
    const char *utf8_grapheme,
    mk_feature_set **out
)
{
    mk_resolved_entry entry;
    mk_status status;

    if (out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;
    status = mk_resolve_entry(system, utf8_grapheme, &entry);
    if (status != MK_OK) {
        return status;
    }
    status = mk_feature_set_from_borrowed(entry.features, entry.feature_count, out);
    mk_resolved_entry_clear(&entry);
    return status;
}

mk_status mk_system_segment_distance(
    const mk_system *system,
    const char *utf8_a,
    const char *utf8_b,
    double *out
)
{
    return mk_system_segment_distance_with_weights(system, utf8_a, utf8_b, NULL, out);
}

mk_status mk_system_segment_distance_with_weights(
    const mk_system *system,
    const char *utf8_a,
    const char *utf8_b,
    const char *node_weights,
    double *out
)
{
    mk_resolved_entry resolved_a;
    mk_resolved_entry resolved_b;
    mk_builtin_entry a;
    mk_builtin_entry b;
    mk_status status;

    if (out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = 0.0;

    status = mk_resolve_entry(system, utf8_a, &resolved_a);
    if (status != MK_OK) {
        return status;
    }
    status = mk_resolve_entry(system, utf8_b, &resolved_b);
    if (status != MK_OK) {
        mk_resolved_entry_clear(&resolved_a);
        return status;
    }

    a.grapheme = resolved_a.grapheme;
    a.features = resolved_a.features;
    a.feature_count = resolved_a.feature_count;
    b.grapheme = resolved_b.grapheme;
    b.features = resolved_b.features;
    b.feature_count = resolved_b.feature_count;

    if (system->builtin->kind == MK_SYSTEM_CATEGORICAL) {
        *out = mk_categorical_distance(system->builtin, &a, &b, node_weights);
    } else if (system->builtin->kind == MK_SYSTEM_VALUED) {
        *out = mk_valued_distance(system->builtin, &a, &b, node_weights);
    } else {
        mk_resolved_entry_clear(&resolved_a);
        mk_resolved_entry_clear(&resolved_b);
        return MK_ERR_UNSUPPORTED_MODEL;
    }
    mk_resolved_entry_clear(&resolved_a);
    mk_resolved_entry_clear(&resolved_b);
    if (isnan(*out)) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    return MK_OK;
}
