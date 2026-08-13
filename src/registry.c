#include "internal.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void mk_free_owned_system(mk_system *system)
{
    size_t i;

    if (system == NULL || !system->owns) {
        return;
    }
    free((char *)system->owned.name);
    for (i = 0; i < system->owned.entry_count; i++) {
        size_t j;
        mk_builtin_entry *entry = (mk_builtin_entry *)&system->owned.entries[i];
        char **features = (char **)entry->features;

        free((char *)entry->grapheme);
        for (j = 0; j < entry->feature_count; j++) {
            free(features[j]);
        }
        free(features);
    }
    free((mk_builtin_entry *)system->owned.entries);
    system->builtin = NULL;
    memset(&system->owned, 0, sizeof(system->owned));
    system->owns = 0;
}

/*
 * Allocates each system separately. The registry array may be reallocated
 * when a runtime model is added, but a system returned to the caller must not
 * move as a result of that operation.
 */
mk_status mk_registry_new_builtin(mk_registry **out)
{
    mk_registry *registry;
    size_t i;

    if (out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;

    registry = (mk_registry *)calloc(1, sizeof(*registry));
    if (registry == NULL) {
        return MK_ERR_OOM;
    }

    registry->systems = (mk_system **)calloc(
        mk_builtin_system_count,
        sizeof(*registry->systems)
    );
    if (registry->systems == NULL) {
        free(registry);
        return MK_ERR_OOM;
    }
    registry->system_count = mk_builtin_system_count;

    for (i = 0; i < mk_builtin_system_count; i++) {
        registry->systems[i] = (mk_system *)calloc(1, sizeof(*registry->systems[i]));
        if (registry->systems[i] == NULL) {
            while (i > 0) {
                i--;
                free(registry->systems[i]);
            }
            free(registry->systems);
            free(registry);
            return MK_ERR_OOM;
        }
        registry->systems[i]->builtin = &mk_builtin_systems[i];
    }

    *out = registry;
    return MK_OK;
}

void mk_registry_free(mk_registry *registry)
{
    size_t i;

    if (registry == NULL) {
        return;
    }
    for (i = 0; i < registry->system_count; i++) {
        mk_free_owned_system(registry->systems[i]);
        free(registry->systems[i]);
    }
    free(registry->systems);
    free(registry);
}

mk_status mk_registry_list_systems(
    const mk_registry *registry,
    mk_string_list **out
)
{
    const char **names;
    size_t i;
    mk_status status;

    if (registry == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }

    names = (const char **)calloc(registry->system_count, sizeof(*names));
    if (names == NULL) {
        return MK_ERR_OOM;
    }
    for (i = 0; i < registry->system_count; i++) {
        names[i] = registry->systems[i]->builtin->name;
    }

    status = mk_string_list_from_borrowed(names, registry->system_count, out);
    free(names);
    return status;
}

mk_status mk_registry_get_system(
    const mk_registry *registry,
    const char *name,
    const mk_system **out
)
{
    size_t i;

    if (registry == NULL || name == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;

    for (i = 0; i < registry->system_count; i++) {
        if (mk_streq(registry->systems[i]->builtin->name, name)) {
            *out = registry->systems[i];
            return MK_OK;
        }
    }

    return MK_ERR_UNKNOWN_SYSTEM;
}

static char *mk_trim(char *line)
{
    char *end;

    while (*line != '\0' && isspace((unsigned char)*line)) {
        line++;
    }
    end = line + strlen(line);
    while (end > line && isspace((unsigned char)end[-1])) {
        end--;
    }
    *end = '\0';
    return line;
}

static char *mk_next_token(char **cursor)
{
    char *start;

    while (**cursor != '\0' && isspace((unsigned char)**cursor)) {
        (*cursor)++;
    }
    if (**cursor == '\0') {
        return NULL;
    }
    start = *cursor;
    while (**cursor != '\0' && !isspace((unsigned char)**cursor)) {
        (*cursor)++;
    }
    if (**cursor != '\0') {
        **cursor = '\0';
        (*cursor)++;
    }
    return start;
}

static void mk_free_entries(mk_builtin_entry *entries, size_t count)
{
    size_t i;

    for (i = 0; i < count; i++) {
        size_t j;
        char **features = (char **)entries[i].features;
        free((char *)entries[i].grapheme);
        for (j = 0; j < entries[i].feature_count; j++) {
            free(features[j]);
        }
        free(features);
    }
    free(entries);
}

static void mk_free_feature_array(char **features, size_t count)
{
    size_t i;

    for (i = 0; i < count; i++) {
        free(features[i]);
    }
    free(features);
}

static mk_status mk_add_parsed_entry(
    mk_builtin_entry **entries,
    size_t *count,
    size_t *cap,
    char *cursor
)
{
    char *grapheme;
    char **features = NULL;
    size_t feature_count = 0;
    size_t feature_cap = 0;
    mk_builtin_entry *next_entries;

    grapheme = mk_next_token(&cursor);
    if (grapheme == NULL) {
        return MK_ERR_PARSE;
    }

    while (1) {
        char *feature = mk_next_token(&cursor);
        char **next_features;
        if (feature == NULL) {
            break;
        }
        if (feature_count + 1 > feature_cap) {
            size_t new_cap = feature_cap == 0 ? 8 : feature_cap * 2;
            next_features = (char **)realloc(features, new_cap * sizeof(*features));
            if (next_features == NULL) {
                mk_free_feature_array(features, feature_count);
                return MK_ERR_OOM;
            }
            features = next_features;
            feature_cap = new_cap;
        }
        features[feature_count] = mk_strdup_internal(feature);
        if (features[feature_count] == NULL) {
            mk_free_feature_array(features, feature_count);
            return MK_ERR_OOM;
        }
        feature_count++;
    }
    if (feature_count == 0) {
        free(features);
        return MK_ERR_PARSE;
    }

    if (*count + 1 > *cap) {
        size_t new_cap = *cap == 0 ? 8 : *cap * 2;
        next_entries = (mk_builtin_entry *)realloc(*entries, new_cap * sizeof(**entries));
        if (next_entries == NULL) {
            mk_free_feature_array(features, feature_count);
            return MK_ERR_OOM;
        }
        *entries = next_entries;
        *cap = new_cap;
    }

    /* Store the lookup key, not the spelling. Queries are normalized before
     * they reach an inventory, so a model written with a precomposed "ã" could
     * never be matched while the same row in a built-in inventory worked --
     * the generator normalizes those at build time. The two model paths now
     * share one normalization. */
    {
        char *key = NULL;
        mk_status status = mk_normalize_input_grapheme(grapheme, &key);

        if (status != MK_OK) {
            mk_free_feature_array(features, feature_count);
            return status;
        }
        (*entries)[*count].grapheme = key;
    }
    (*entries)[*count].features = (const char *const *)features;
    (*entries)[*count].feature_count = feature_count;
    (*count)++;
    return MK_OK;
}

/* Keeps the first problem found. A caller-supplied model that fails validation
 * needs to know which line and which token, not just MK_ERR_PARSE. */
static void mk_set_diagnostic(char **out, int line_no, const char *message, const char *detail)
{
    char buffer[512];

    if (out == NULL || *out != NULL) {
        return;
    }
    if (line_no > 0) {
        snprintf(buffer, sizeof(buffer), "line %d: %s: %s", line_no, message, detail);
    } else {
        snprintf(buffer, sizeof(buffer), "%s: %s", message, detail);
    }
    *out = mk_strdup_internal(buffer);
}

/* Every feature a strict model uses must reach a scoring dimension, and every
 * grapheme must be unique. Both checks exist because a model that fails them
 * still registers and still answers every query: it just answers zero. */
static mk_status mk_validate_strict_entries(
    const mk_builtin_entry *entries,
    size_t entry_count,
    char **diagnostic
)
{
    size_t i;
    size_t j;

    for (i = 0; i < entry_count; i++) {
        for (j = 0; j < i; j++) {
            if (mk_streq(entries[i].grapheme, entries[j].grapheme)) {
                mk_set_diagnostic(
                    diagnostic,
                    0,
                    "strict validation: grapheme declared more than once",
                    entries[i].grapheme
                );
                return MK_ERR_PARSE;
            }
        }
        for (j = 0; j < entries[i].feature_count; j++) {
            if (!mk_geometry_knows_feature(entries[i].features[j])) {
                mk_set_diagnostic(
                    diagnostic,
                    0,
                    "strict validation: feature is unknown to the geometry and so cannot "
                    "affect any distance; add it to the geometry or use "
                    "'@validation permissive'",
                    entries[i].features[j]
                );
                return MK_ERR_PARSE;
            }
        }
        {
            int scorable = 0;
            for (j = 0; j < entries[i].feature_count; j++) {
                if (mk_geometry_scores_feature(entries[i].features[j])) {
                    scorable = 1;
                    break;
                }
            }
            if (!scorable) {
                mk_set_diagnostic(
                    diagnostic,
                    0,
                    "strict validation: grapheme has no feature that can affect a "
                    "distance, so every comparison involving it would score zero",
                    entries[i].grapheme
                );
                return MK_ERR_PARSE;
            }
        }
    }
    return MK_OK;
}

mk_status mk_registry_add_model_text(
    mk_registry *registry,
    const char *model_text
)
{
    return mk_registry_add_model_text_ex(registry, model_text, NULL);
}

mk_status mk_registry_add_model_text_ex(
    mk_registry *registry,
    const char *model_text,
    char **diagnostic_out
)
{
    char *copy;
    char *line;
    char *name = NULL;
    int saw_categorical = 0;
    int strict = 1;
    int line_no = 0;
    char unknown_directive[256];
    int unknown_directive_line = 0;
    char *diagnostic = NULL;
    mk_builtin_entry *entries = NULL;
    size_t entry_count = 0;
    size_t entry_cap = 0;
    mk_system **next_systems;
    mk_system *slot;
    mk_status status;

    unknown_directive[0] = '\0';
    if (diagnostic_out != NULL) {
        *diagnostic_out = NULL;
    }
    if (registry == NULL || model_text == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }

    copy = mk_strdup_internal(model_text);
    if (copy == NULL) {
        return MK_ERR_OOM;
    }

    line = copy;
    while (line != NULL) {
        char *next = strchr(line, '\n');
        char *trimmed;

        if (next != NULL) {
            *next = '\0';
            next++;
        }
        line_no++;
        trimmed = mk_trim(line);
        if (trimmed[0] != '\0' && trimmed[0] != '#') {
            if (strncmp(trimmed, "@validation", 11) == 0 && isspace((unsigned char)trimmed[11])) {
                char *cursor = trimmed + 11;
                char *token = mk_next_token(&cursor);
                if (token != NULL && strcmp(token, "permissive") == 0) {
                    strict = 0;
                } else if (token != NULL && strcmp(token, "strict") == 0) {
                    strict = 1;
                } else {
                    mk_set_diagnostic(
                        &diagnostic,
                        line_no,
                        "@validation must be 'strict' or 'permissive'",
                        token == NULL ? "(missing)" : token
                    );
                    free(copy);
                    free(name);
                    mk_free_entries(entries, entry_count);
                    goto parse_failed;
                }
            } else if (strncmp(trimmed, "@model", 6) == 0 && isspace((unsigned char)trimmed[6])) {
                char *cursor = trimmed + 6;
                char *token = mk_next_token(&cursor);
                free(name);
                name = token == NULL ? NULL : mk_strdup_internal(token);
                if (token != NULL && name == NULL) {
                    free(copy);
                    mk_free_entries(entries, entry_count);
                    return MK_ERR_OOM;
                }
            } else if (strncmp(trimmed, "@type", 5) == 0 && isspace((unsigned char)trimmed[5])) {
                char *cursor = trimmed + 5;
                char *token = mk_next_token(&cursor);
                saw_categorical = token != NULL && strcmp(token, "categorical") == 0;
                if (!saw_categorical) {
                    free(copy);
                    free(name);
                    mk_free_entries(entries, entry_count);
                    return MK_ERR_UNSUPPORTED_MODEL;
                }
            } else if (strncmp(trimmed, "grapheme", 8) == 0 && isspace((unsigned char)trimmed[8])) {
                char *cursor = trimmed + 8;
                mk_status entry_status = mk_add_parsed_entry(&entries, &entry_count, &entry_cap, cursor);
                if (entry_status != MK_OK) {
                    mk_set_diagnostic(&diagnostic, line_no, "malformed grapheme row", trimmed);
                    free(copy);
                    free(name);
                    mk_free_entries(entries, entry_count);
                    if (diagnostic_out != NULL) {
                        *diagnostic_out = diagnostic;
                    } else {
                        free(diagnostic);
                    }
                    return entry_status;
                }
            } else if (strncmp(trimmed, "@geometry", 9) == 0 && isspace((unsigned char)trimmed[9])) {
                /* Accepted for readability. The C implementation has one
                 * compiled-in geometry, so there is nothing to select yet. */
            } else if (strncmp(trimmed, "feature", 7) == 0 && isspace((unsigned char)trimmed[7])) {
                /* Readability rows. They carry no information the scorer uses,
                 * so they are accepted but never treated as a declaration. */
            } else if (unknown_directive_line == 0) {
                /* Remembered rather than rejected here: @validation may appear
                 * further down the file. */
                unknown_directive_line = line_no;
                snprintf(unknown_directive, sizeof(unknown_directive), "%s", trimmed);
            }
        }
        line = next;
    }
    free(copy);

    if (name == NULL || !saw_categorical || entry_count == 0) {
        mk_set_diagnostic(
            &diagnostic,
            0,
            "a model needs @model, '@type categorical', and at least one grapheme row",
            name == NULL ? "@model is missing" :
                (!saw_categorical ? "@type categorical is missing" : "no grapheme rows")
        );
        free(name);
        mk_free_entries(entries, entry_count);
        goto parse_failed;
    }

    if (strict) {
        if (unknown_directive_line != 0) {
            mk_set_diagnostic(
                &diagnostic,
                unknown_directive_line,
                "strict validation: unrecognized line; ignoring it would hide a typo, "
                "so use '@validation permissive' to allow it",
                unknown_directive
            );
            free(name);
            mk_free_entries(entries, entry_count);
            goto parse_failed;
        }
        status = mk_validate_strict_entries(entries, entry_count, &diagnostic);
        if (status != MK_OK) {
            free(name);
            mk_free_entries(entries, entry_count);
            goto parse_failed;
        }
    }

    next_systems = (mk_system **)realloc(
        registry->systems,
        (registry->system_count + 1) * sizeof(*registry->systems)
    );
    if (next_systems == NULL) {
        free(name);
        mk_free_entries(entries, entry_count);
        return MK_ERR_OOM;
    }
    registry->systems = next_systems;
    slot = (mk_system *)calloc(1, sizeof(*slot));
    if (slot == NULL) {
        free(name);
        mk_free_entries(entries, entry_count);
        return MK_ERR_OOM;
    }
    registry->systems[registry->system_count] = slot;
    slot->owned.name = name;
    slot->owned.kind = MK_SYSTEM_CATEGORICAL;
    slot->owned.entries = entries;
    slot->owned.entry_count = entry_count;
    slot->builtin = &slot->owned;
    slot->owns = 1;
    registry->system_count++;
    return MK_OK;

parse_failed:
    if (diagnostic_out != NULL) {
        *diagnostic_out = diagnostic;
    } else {
        free(diagnostic);
    }
    return MK_ERR_PARSE;
}
