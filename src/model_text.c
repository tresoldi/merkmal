/* The runtime-model text parser. See model_text.h. */

#include "model_text.h"

#include "array.h"
#include "geometry.h"
#include "normalize.h"
#include "strings.h"

#include <ctype.h>
#include <stdbool.h>
#include <stdint.h>
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

static void mk_free_entries(mki_builtin_entry *entries, size_t count)
{
    size_t i;

    for (i = 0; i < count; i++) {
        size_t j;

        free(entries[i].grapheme);
        for (j = 0; j < entries[i].feature_count; j++) {
            free(entries[i].features[j]);
        }
        free(entries[i].features);
    }
    free(entries);
}

void mki_parsed_model_clear(mki_parsed_model *model)
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
    mki_builtin_entry **entries,
    size_t *count,
    size_t *cap,
    char *cursor
)
{
    char *grapheme;
    char **features = NULL;
    size_t feature_count = 0;
    size_t feature_cap = 0;
    mki_builtin_entry *next_entries;

    grapheme = mk_next_token(&cursor);
    /* `+` is the word boundary of the tokenizers and is never looked up, so a
     * row for it could not be reached. */
    if (grapheme == NULL || strcmp(grapheme, "+") == 0) {
        return MK_ERR_PARSE;
    }

    while (1) {
        char *feature = mk_next_token(&cursor);
        char **next_features;
        if (feature == NULL) {
            break;
        }
        next_features = (char **)mki_grow_array(
            features, &feature_cap, feature_count, 1, sizeof(*features), 8
        );
        if (next_features == NULL) {
            mki_free_items(features, feature_count);
            return MK_ERR_OOM;
        }
        features = next_features;
        features[feature_count] = mki_strdup_internal(feature);
        if (features[feature_count] == NULL) {
            mki_free_items(features, feature_count);
            return MK_ERR_OOM;
        }
        feature_count++;
    }
    if (feature_count == 0) {
        free(features);
        return MK_ERR_PARSE;
    }

    next_entries = (mki_builtin_entry *)mki_grow_array(
        *entries, cap, *count, 1, sizeof(**entries), 8
    );
    if (next_entries == NULL) {
        mki_free_items(features, feature_count);
        return MK_ERR_OOM;
    }
    *entries = next_entries;

    /* Store the lookup key, not the spelling. Queries are normalized before
     * they reach an inventory, so a row stored as written with a precomposed
     * "ã" could never be matched, while the same row in a built-in inventory,
     * which the generator normalizes at build time, would be. Both model paths
     * share one normalization. */
    {
        char *key = NULL;
        mk_status status = mki_normalize_input_grapheme(grapheme, &key);

        if (status != MK_OK) {
            mki_free_items(features, feature_count);
            return status;
        }
        (*entries)[*count].grapheme = key;
    }
    (*entries)[*count].features = features;
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
    /* Truncation is acceptable here and only here: this builds a message for a
     * human, not a value the library acts on. A 600-character feature name
     * still produces a diagnostic naming the line and most of the token, which
     * is better than refusing to report the problem at all. */
    if (line_no > 0) {
        snprintf(buffer, sizeof(buffer), "line %d: %s: %s", line_no, message, detail);
    } else {
        snprintf(buffer, sizeof(buffer), "%s: %s", message, detail);
    }
    *out = mki_strdup_internal(buffer);
}

static int mk_compare_grapheme_pointers(const void *a, const void *b)
{
    /* Both casts add const rather than remove it. */
    const char *const *left = (const char *const *)a;
    const char *const *right = (const char *const *)b;

    return strcmp(*left, *right);
}

/* Whether any grapheme is declared twice.
 *
 * Sorted and walked once rather than compared against every earlier row. The
 * pairwise form is quadratic on text the caller supplies, and
 * mk_registry_add_model_text_n exists for exactly the inputs that makes
 * dangerous -- a mapped file, a Python bytes, a fuzzer's input. On a large
 * model it would dominate the cost of parsing; sorted, it costs about what
 * parsing does.
 *
 * The pointers are sorted, not the rows: nothing else may assume an order, and
 * a runtime model is looked up by scanning its rows anyway.
 *
 * Reports one duplicate, not all of them: whichever sorts first, not the first
 * in file order. Because this runs before the feature checks, a model with
 * both a duplicate and an unknown feature reports the duplicate. The status is
 * MK_ERR_PARSE either way; only the sentence differs. */
static mk_status mk_check_no_duplicate_grapheme(
    const mki_builtin_entry *entries,
    size_t entry_count,
    char **diagnostic
)
{
    const char **sorted;
    size_t i;

    if (entry_count < 2) {
        return MK_OK;
    }
    sorted = (const char **)malloc(entry_count * sizeof(*sorted));
    if (sorted == NULL) {
        return MK_ERR_OOM;
    }
    for (i = 0; i < entry_count; i++) {
        sorted[i] = entries[i].grapheme;
    }
    qsort(sorted, entry_count, sizeof(*sorted), mk_compare_grapheme_pointers);
    for (i = 1; i < entry_count; i++) {
        if (strcmp(sorted[i - 1], sorted[i]) == 0) {
            mk_set_diagnostic(
                diagnostic,
                0,
                "strict validation: grapheme declared more than once",
                sorted[i]
            );
            free(sorted);
            return MK_ERR_PARSE;
        }
    }
    free(sorted);
    return MK_OK;
}

/* Under strict validation every grapheme must be unique, every feature must be
 * known to the geometry, and every grapheme must have at least one feature
 * that scores. A model that fails them would still register and answer every
 * query, just not usefully: an unknown or unscored feature contributes zero to
 * every distance. */
static mk_status mk_validate_strict_entries(
    const mki_builtin_entry *entries,
    size_t entry_count,
    char **diagnostic
)
{
    size_t i;
    size_t j;
    mk_status status;

    status = mk_check_no_duplicate_grapheme(entries, entry_count, diagnostic);
    if (status != MK_OK) {
        return status;
    }

    for (i = 0; i < entry_count; i++) {
        for (j = 0; j < entries[i].feature_count; j++) {
            if (!mki_geometry_knows_feature(entries[i].features[j])) {
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
                if (mki_geometry_scores_feature(entries[i].features[j])) {
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

mk_status mki_parse_model_text(
    const char *model_text,
    mki_parsed_model *out,
    char **diagnostic
)
{
    if (model_text == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    return mki_parse_model_text_n(model_text, strlen(model_text), out, diagnostic);
}

/* The newest runtime model text format this library reads. A model that
 * declares a newer one is refused rather than read as if it were this one: a
 * later format may give an existing line a different meaning. */
#define MK_MODEL_TEXT_FORMAT_VERSION 1L

/* Checks the value of a `@format_version` line: a positive decimal integer no
 * newer than MK_MODEL_TEXT_FORMAT_VERSION. */
static mk_status mk_check_format_version(const char *token, int line_no, char **diagnostic)
{
    const char *p;
    long version = 0;

    if (token == NULL || token[0] == '\0') {
        mk_set_diagnostic(diagnostic, line_no, "@format_version needs a version number", "(missing)");
        return MK_ERR_PARSE;
    }
    for (p = token; *p != '\0'; p++) {
        if (*p < '0' || *p > '9') {
            mk_set_diagnostic(diagnostic, line_no, "@format_version must be a positive integer", token);
            return MK_ERR_PARSE;
        }
        /* Saturates rather than overflows: any version past the supported one
         * is refused the same way. */
        if (version <= MK_MODEL_TEXT_FORMAT_VERSION) {
            version = version * 10 + (*p - '0');
        }
    }
    if (version < 1) {
        mk_set_diagnostic(diagnostic, line_no, "@format_version must be a positive integer", token);
        return MK_ERR_PARSE;
    }
    if (version > MK_MODEL_TEXT_FORMAT_VERSION) {
        mk_set_diagnostic(
            diagnostic,
            line_no,
            "model text format version is newer than this library reads (it reads version 1)",
            token
        );
        return MK_ERR_UNSUPPORTED_MODEL;
    }
    return MK_OK;
}

/* What the parser has gathered so far. Everything a pointer here holds is
 * owned by the parse until mki_parse_model_text_n hands it to `out`. */
typedef struct mk_model_parse {
    char *name;
    bool saw_categorical;
    bool strict;
    /* The first line nothing recognized, kept rather than rejected because
     * '@validation permissive' may come later in the file. Diagnostic text
     * only, so truncation is acceptable. */
    char unknown_directive[256];
    int unknown_directive_line;
    mki_builtin_entry *entries;
    size_t entry_count;
    size_t entry_cap;
} mk_model_parse;

/* The arguments of `line` if it is the directive `keyword` followed by
 * whitespace, and NULL otherwise. A keyword alone on its line, or run into
 * other text ("@modelx"), is not the directive. */
static char *mk_directive_args(char *line, const char *keyword)
{
    size_t n = strlen(keyword);

    if (strncmp(line, keyword, n) == 0 && isspace((unsigned char)line[n])) {
        return line + n;
    }
    return NULL;
}

/* One trimmed, non-blank, non-comment line. */
static mk_status mk_parse_line(
    mk_model_parse *parse,
    char *trimmed,
    int line_no,
    char **diagnostic
)
{
    char *args;
    char *token;

    if ((args = mk_directive_args(trimmed, "@validation")) != NULL) {
        token = mk_next_token(&args);
        if (token != NULL && strcmp(token, "permissive") == 0) {
            parse->strict = false;
        } else if (token != NULL && strcmp(token, "strict") == 0) {
            parse->strict = true;
        } else {
            mk_set_diagnostic(
                diagnostic,
                line_no,
                "@validation must be 'strict' or 'permissive'",
                token == NULL ? "(missing)" : token
            );
            return MK_ERR_PARSE;
        }
    } else if ((args = mk_directive_args(trimmed, "@format_version")) != NULL) {
        token = mk_next_token(&args);
        return mk_check_format_version(token, line_no, diagnostic);
    } else if ((args = mk_directive_args(trimmed, "@model")) != NULL) {
        /* One name, once: a second @model or a second word would otherwise be
         * dropped or silently replace the first. */
        token = mk_next_token(&args);
        if (parse->name != NULL) {
            mk_set_diagnostic(diagnostic, line_no, "@model is declared more than once", trimmed);
            return MK_ERR_PARSE;
        }
        if (token == NULL || mk_next_token(&args) != NULL) {
            mk_set_diagnostic(diagnostic, line_no, "@model takes exactly one name", trimmed);
            return MK_ERR_PARSE;
        }
        parse->name = mki_strdup_internal(token);
        if (parse->name == NULL) {
            return MK_ERR_OOM;
        }
    } else if ((args = mk_directive_args(trimmed, "@type")) != NULL) {
        token = mk_next_token(&args);
        parse->saw_categorical = token != NULL && strcmp(token, "categorical") == 0;
        if (!parse->saw_categorical) {
            return MK_ERR_UNSUPPORTED_MODEL;
        }
    } else if ((args = mk_directive_args(trimmed, "grapheme")) != NULL) {
        mk_status status = mk_add_parsed_entry(
            &parse->entries, &parse->entry_count, &parse->entry_cap, args
        );
        if (status != MK_OK) {
            mk_set_diagnostic(diagnostic, line_no, "malformed grapheme row", trimmed);
            return status;
        }
    } else if ((args = mk_directive_args(trimmed, "@geometry")) != NULL) {
        token = mk_next_token(&args);
        /* Runtime geometry registration is not implemented yet. Do not accept
         * a name and silently score it with another geometry: that makes a
         * reproducibility declaration false. */
        if (token == NULL || strcmp(token, "clements-hume") != 0) {
            mk_set_diagnostic(
                diagnostic,
                line_no,
                "unsupported runtime geometry (only 'clements-hume' is compiled)",
                token == NULL ? "(missing)" : token
            );
            return MK_ERR_UNSUPPORTED_MODEL;
        }
    } else if (mk_directive_args(trimmed, "feature") != NULL) {
        /* Readability rows. They carry no information the scorer uses, so they
         * are accepted but never treated as a declaration. */
    } else if (parse->unknown_directive_line == 0) {
        parse->unknown_directive_line = line_no;
        snprintf(parse->unknown_directive, sizeof(parse->unknown_directive), "%s", trimmed);
    }
    return MK_OK;
}

/* The checks that need the whole file: the required directives, and under
 * strict validation, no unrecognized line and every row's features known. */
static mk_status mk_check_model(const mk_model_parse *parse, char **diagnostic)
{
    if (parse->name == NULL || !parse->saw_categorical || parse->entry_count == 0) {
        mk_set_diagnostic(
            diagnostic,
            0,
            "a model needs @model, '@type categorical', and at least one grapheme row",
            parse->name == NULL ? "@model is missing" : (!parse->saw_categorical ? "@type categorical is missing" : "no grapheme rows")
        );
        return MK_ERR_PARSE;
    }
    if (!parse->strict) {
        return MK_OK;
    }
    if (parse->unknown_directive_line != 0) {
        mk_set_diagnostic(
            diagnostic,
            parse->unknown_directive_line,
            "strict validation: unrecognized line; ignoring it would hide a typo, "
            "so use '@validation permissive' to allow it",
            parse->unknown_directive
        );
        return MK_ERR_PARSE;
    }
    return mk_validate_strict_entries(parse->entries, parse->entry_count, diagnostic);
}

mk_status mki_parse_model_text_n(
    const char *model_text,
    size_t model_text_length,
    mki_parsed_model *out,
    char **diagnostic
)
{
    mk_model_parse parse = {NULL, false, true, {0}, 0, NULL, 0, 0};
    char *copy;
    char *line;
    int line_no = 0;
    mk_status status;

    if (out == NULL || model_text == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    out->name = NULL;
    out->entries = NULL;
    out->entry_count = 0;

    /* Before the copy: see model_text.h on why an embedded NUL is refused. */
    if (memchr(model_text, '\0', model_text_length) != NULL) {
        mk_set_diagnostic(diagnostic, 0, "model text contains an embedded NUL byte", "");
        return MK_ERR_PARSE;
    }

    if (model_text_length == SIZE_MAX) {
        return MK_ERR_OOM;
    }
    copy = (char *)malloc(model_text_length + 1);
    if (copy == NULL) {
        return MK_ERR_OOM;
    }
    memcpy(copy, model_text, model_text_length);
    copy[model_text_length] = '\0';

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
            status = mk_parse_line(&parse, trimmed, line_no, diagnostic);
            if (status != MK_OK) {
                goto failed;
            }
        }
        line = next;
    }
    free(copy);
    copy = NULL;

    status = mk_check_model(&parse, diagnostic);
    if (status != MK_OK) {
        goto failed;
    }

    out->name = parse.name;
    out->entries = parse.entries;
    out->entry_count = parse.entry_count;
    return MK_OK;

failed:
    free(copy);
    free(parse.name);
    mk_free_entries(parse.entries, parse.entry_count);
    return status;
}
