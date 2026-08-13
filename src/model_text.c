/* The runtime-model text parser. See model_text.h. */

#include "model_text.h"

#include "geometry.h"
#include "normalize.h"
#include "strings.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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

void mk_parsed_model_clear(mk_parsed_model *model)
{
    if (model == NULL) {
        return;
    }
    free(model->name);
    mk_free_entries(model->entries, model->entry_count);
    model->name = NULL;
    model->entries = NULL;
    model->entry_count = 0;
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
                mk_free_items(features, feature_count);
                return MK_ERR_OOM;
            }
            features = next_features;
            feature_cap = new_cap;
        }
        features[feature_count] = mk_strdup_internal(feature);
        if (features[feature_count] == NULL) {
            mk_free_items(features, feature_count);
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
            mk_free_items(features, feature_count);
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
            mk_free_items(features, feature_count);
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

mk_status mk_parse_model_text(
    const char *model_text,
    mk_parsed_model *out,
    char **diagnostic
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
    mk_builtin_entry *entries = NULL;
    size_t entry_count = 0;
    size_t entry_cap = 0;
    mk_status status;

    if (out == NULL || model_text == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    out->name = NULL;
    out->entries = NULL;
    out->entry_count = 0;
    unknown_directive[0] = '\0';

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
                        diagnostic,
                        line_no,
                        "@validation must be 'strict' or 'permissive'",
                        token == NULL ? "(missing)" : token
                    );
                    status = MK_ERR_PARSE;
                    goto failed;
                }
            } else if (strncmp(trimmed, "@model", 6) == 0 && isspace((unsigned char)trimmed[6])) {
                char *cursor = trimmed + 6;
                char *token = mk_next_token(&cursor);
                free(name);
                name = token == NULL ? NULL : mk_strdup_internal(token);
                if (token != NULL && name == NULL) {
                    status = MK_ERR_OOM;
                    goto failed;
                }
            } else if (strncmp(trimmed, "@type", 5) == 0 && isspace((unsigned char)trimmed[5])) {
                char *cursor = trimmed + 5;
                char *token = mk_next_token(&cursor);
                saw_categorical = token != NULL && strcmp(token, "categorical") == 0;
                if (!saw_categorical) {
                    status = MK_ERR_UNSUPPORTED_MODEL;
                    goto failed;
                }
            } else if (strncmp(trimmed, "grapheme", 8) == 0 && isspace((unsigned char)trimmed[8])) {
                char *cursor = trimmed + 8;
                status = mk_add_parsed_entry(&entries, &entry_count, &entry_cap, cursor);
                if (status != MK_OK) {
                    mk_set_diagnostic(diagnostic, line_no, "malformed grapheme row", trimmed);
                    goto failed;
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
    copy = NULL;

    if (name == NULL || !saw_categorical || entry_count == 0) {
        mk_set_diagnostic(
            diagnostic,
            0,
            "a model needs @model, '@type categorical', and at least one grapheme row",
            name == NULL ? "@model is missing" :
                (!saw_categorical ? "@type categorical is missing" : "no grapheme rows")
        );
        status = MK_ERR_PARSE;
        goto failed;
    }

    if (strict) {
        if (unknown_directive_line != 0) {
            mk_set_diagnostic(
                diagnostic,
                unknown_directive_line,
                "strict validation: unrecognized line; ignoring it would hide a typo, "
                "so use '@validation permissive' to allow it",
                unknown_directive
            );
            status = MK_ERR_PARSE;
            goto failed;
        }
        status = mk_validate_strict_entries(entries, entry_count, diagnostic);
        if (status != MK_OK) {
            goto failed;
        }
    }

    out->name = name;
    out->entries = entries;
    out->entry_count = entry_count;
    return MK_OK;

failed:
    free(copy);
    free(name);
    mk_free_entries(entries, entry_count);
    return status;
}
