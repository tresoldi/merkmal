/* WebAssembly adapter: a JSON-in, JSON-out surface over the C ABI.
 *
 * Every entry point returns a caller-owned string (JSON) that JavaScript must
 * hand back to merkmal_free. The library is reached only through its compiled-in
 * models, so this links with -sFILESYSTEM=0. */

#include "merkmal.h"

#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef __EMSCRIPTEN__
#include <emscripten.h>
#else
#define EMSCRIPTEN_KEEPALIVE
#endif

#ifndef MK_WEB_VERSION
#define MK_WEB_VERSION "0.0.0"
#endif

/* Declared so -Wmissing-prototypes has something to match. */
EMSCRIPTEN_KEEPALIVE char *merkmal_list_systems(void);
EMSCRIPTEN_KEEPALIVE char *merkmal_grapheme_features(const char *system_name,
                                                     const char *grapheme);
EMSCRIPTEN_KEEPALIVE char *merkmal_segment_distance(const char *system_name,
                                                    const char *a,
                                                    const char *b);
EMSCRIPTEN_KEEPALIVE char *merkmal_tokenize(const char *system_name,
                                            const char *input,
                                            int merge_tones,
                                            int system_aware);
EMSCRIPTEN_KEEPALIVE char *merkmal_distance_matrix(const char *system_name,
                                                   const char *segments_csv);
EMSCRIPTEN_KEEPALIVE char *merkmal_normalize(const char *grapheme);
EMSCRIPTEN_KEEPALIVE char *merkmal_diagnose(const char *system_name,
                                            const char *grapheme);
EMSCRIPTEN_KEEPALIVE char *merkmal_register_model(const char *model_text);
EMSCRIPTEN_KEEPALIVE const char *merkmal_version(void);
EMSCRIPTEN_KEEPALIVE void merkmal_free(char *text);

/* ---- growable JSON buffer -------------------------------------------- */

typedef struct {
    char *data;
    size_t len;
    size_t cap;
} jbuf;

static void jb_init(jbuf *b)
{
    b->cap = 512;
    b->data = (char *)malloc(b->cap);
    b->len = 0;
    if (b->data)
        b->data[0] = '\0';
}

static void jb_grow(jbuf *b, size_t need)
{
    if (!b->data)
        return;
    if (b->len + need < b->cap)
        return;
    size_t nc = b->cap * 2;
    if (nc < b->len + need + 1)
        nc = b->len + need + 1;
    char *nd = (char *)realloc(b->data, nc);
    if (!nd) {
        free(b->data);
        b->data = NULL;
        return;
    }
    b->data = nd;
    b->cap = nc;
}

static void jb_cat(jbuf *b, const char *s)
{
    size_t n = strlen(s);
    jb_grow(b, n);
    if (!b->data)
        return;
    memcpy(b->data + b->len, s, n + 1);
    b->len += n;
}

static void jb_catf(jbuf *b, const char *fmt, ...)
{
    char tmp[256];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(tmp, sizeof(tmp), fmt, ap);
    va_end(ap);
    jb_cat(b, tmp);
}

static void jb_str(jbuf *b, const char *s)
{
    jb_cat(b, "\"");
    if (s) {
        for (const char *p = s; *p; p++) {
            if (*p == '"')
                jb_cat(b, "\\\"");
            else if (*p == '\\')
                jb_cat(b, "\\\\");
            else if ((unsigned char)*p < 0x20) {
                char esc[8];
                snprintf(esc, sizeof(esc), "\\u%04x", (unsigned char)*p);
                jb_cat(b, esc);
            } else {
                jb_grow(b, 1);
                if (!b->data)
                    return;
                b->data[b->len++] = *p;
                b->data[b->len] = '\0';
            }
        }
    }
    jb_cat(b, "\"");
}

static char *jb_finish(jbuf *b)
{
    if (!b->data) {
        char *oom = (char *)malloc(32);
        if (oom)
            strcpy(oom, "{\"ok\":false,\"error\":\"oom\"}");
        return oom;
    }
    return b->data;
}

/* ---- helpers --------------------------------------------------------- */

static mk_registry *shared_registry(void)
{
    static mk_registry *reg = NULL;
    if (!reg)
        mk_registry_new_builtin(&reg);
    return reg;
}

static char *error_json(mk_status status, const char *detail)
{
    jbuf b;
    jb_init(&b);
    jb_cat(&b, "{\"ok\":false,\"error\":");
    jb_str(&b, mk_status_string(status));
    if (detail) {
        jb_cat(&b, ",\"detail\":");
        jb_str(&b, detail);
    }
    jb_cat(&b, "}");
    return jb_finish(&b);
}

static mk_status get_system(const char *name, const mk_system **out)
{
    mk_registry *reg = shared_registry();
    if (!reg)
        return MK_ERR_OOM;
    return mk_registry_get_system(reg, name, out);
}

/* ---- exported functions ---------------------------------------------- */

EMSCRIPTEN_KEEPALIVE
char *merkmal_list_systems(void)
{
    mk_registry *reg = shared_registry();
    mk_string_list *names = NULL;
    jbuf b;

    if (!reg)
        return error_json(MK_ERR_OOM, NULL);
    if (mk_registry_list_systems(reg, &names) != MK_OK)
        return error_json(MK_ERR_OOM, NULL);

    jb_init(&b);
    jb_cat(&b, "{\"ok\":true,\"systems\":[");
    for (size_t i = 0; i < mk_string_list_size(names); i++) {
        const char *sname = mk_string_list_get(names, i);
        const mk_system *sys = NULL;
        const char *kind = "unknown";

        if (i > 0)
            jb_cat(&b, ",");
        mk_registry_get_system(reg, sname, &sys);
        if (sys)
            mk_system_kind(sys, &kind);
        jb_cat(&b, "{\"name\":");
        jb_str(&b, sname);
        jb_cat(&b, ",\"kind\":");
        jb_str(&b, kind);
        jb_cat(&b, "}");
    }
    jb_cat(&b, "]}");
    mk_string_list_free(names);
    return jb_finish(&b);
}

EMSCRIPTEN_KEEPALIVE
char *merkmal_grapheme_features(const char *system_name, const char *grapheme)
{
    const mk_system *sys = NULL;
    mk_string_list *features = NULL;
    mk_string_list *labels = NULL;
    mk_status status;
    jbuf b;

    if (!grapheme || !*grapheme)
        return error_json(MK_ERR_INVALID_ARGUMENT, "empty grapheme");

    status = get_system(system_name, &sys);
    if (status != MK_OK)
        return error_json(status, system_name);

    status = mk_system_grapheme_features(sys, grapheme, &features);
    if (status != MK_OK) {
        mk_diagnosis diag;
        char *normalized = NULL;

        jb_init(&b);
        jb_cat(&b, "{\"ok\":false,\"error\":");
        jb_str(&b, mk_status_string(status));

        if (mk_system_diagnose(sys, grapheme, &diag) == MK_OK) {
            char prefix[64] = "";
            if (diag.valid_prefix_bytes > 0 &&
                diag.valid_prefix_bytes < sizeof(prefix)) {
                memcpy(prefix, grapheme, diag.valid_prefix_bytes);
                prefix[diag.valid_prefix_bytes] = '\0';
            }
            jb_cat(&b, ",\"diagnosis\":{\"valid_prefix\":");
            jb_str(&b, prefix);
            jb_cat(&b, ",\"offending\":");
            jb_str(&b, diag.offending);
            jb_cat(&b, "}");
        }

        if (mk_normalize_grapheme(grapheme, &normalized) == MK_OK &&
            normalized) {
            bool is_seg = false;
            mk_system_is_segment(sys, normalized, &is_seg);
            if (is_seg) {
                jb_cat(&b, ",\"normalized\":");
                jb_str(&b, normalized);
            }
            mk_string_free(normalized);
        }

        jb_cat(&b, "}");
        return jb_finish(&b);
    }

    jb_init(&b);
    jb_cat(&b, "{\"ok\":true,\"grapheme\":");
    jb_str(&b, grapheme);
    jb_cat(&b, ",\"features\":[");
    for (size_t i = 0; i < mk_string_list_size(features); i++) {
        if (i > 0)
            jb_cat(&b, ",");
        jb_str(&b, mk_string_list_get(features, i));
    }
    jb_cat(&b, "]");

    /* Feature vector. */
    {
        size_t width = 0;
        mk_system_vector_width(sys, &width);
        mk_system_vector_labels(sys, &labels);
        if (width > 0 && labels) {
            double *vals = (double *)calloc(width, sizeof(double));
            size_t written = 0;
            if (vals &&
                mk_system_feature_vector(sys, grapheme, vals, width,
                                         &written) == MK_OK) {
                jb_cat(&b, ",\"vector\":{\"labels\":[");
                for (size_t i = 0; i < written; i++) {
                    if (i > 0)
                        jb_cat(&b, ",");
                    jb_str(&b, mk_string_list_get(labels, i));
                }
                jb_cat(&b, "],\"values\":[");
                for (size_t i = 0; i < written; i++) {
                    if (i > 0)
                        jb_cat(&b, ",");
                    jb_catf(&b, "%.6g", vals[i]);
                }
                jb_cat(&b, "]}");
            }
            free(vals);
        }
    }

    jb_cat(&b, "}");
    mk_string_list_free(features);
    mk_string_list_free(labels);
    return jb_finish(&b);
}

EMSCRIPTEN_KEEPALIVE
char *merkmal_segment_distance(const char *system_name, const char *a,
                               const char *b_seg)
{
    const mk_system *sys = NULL;
    double dist = 0.0, cov = 0.0;
    mk_comparability cmp = MK_CMP_OK;
    mk_status status;
    jbuf buf;

    if (!a || !*a || !b_seg || !*b_seg)
        return error_json(MK_ERR_INVALID_ARGUMENT, "empty segment");

    status = get_system(system_name, &sys);
    if (status != MK_OK)
        return error_json(status, system_name);

    status = mk_system_segment_distance_ex(sys, a, b_seg, NULL, &dist, &cov,
                                           &cmp);
    if (status != MK_OK)
        return error_json(status, NULL);

    jb_init(&buf);
    jb_cat(&buf, "{\"ok\":true,\"a\":");
    jb_str(&buf, a);
    jb_cat(&buf, ",\"b\":");
    jb_str(&buf, b_seg);
    jb_catf(&buf, ",\"distance\":%.6g,\"coverage\":%.6g,\"comparability\":",
            dist, cov);
    switch (cmp) {
    case MK_CMP_OK:
        jb_str(&buf, "ok");
        break;
    case MK_CMP_CROSS_TIER:
        jb_str(&buf, "cross_tier");
        break;
    case MK_CMP_NO_SHARED_DIMENSION:
        jb_str(&buf, "no_shared_dimension");
        break;
    }
    jb_cat(&buf, "}");
    return jb_finish(&buf);
}

EMSCRIPTEN_KEEPALIVE
char *merkmal_tokenize(const char *system_name, const char *input,
                       int merge_tones, int system_aware)
{
    const mk_system *sys = NULL;
    mk_string_list *segments = NULL;
    mk_string_list *merged = NULL;
    mk_status status;
    jbuf b;

    if (!input || !*input)
        return error_json(MK_ERR_INVALID_ARGUMENT, "empty input");

    status = get_system(system_name, &sys);
    if (status != MK_OK)
        return error_json(status, system_name);

    if (system_aware)
        status = mk_system_segment_ipa(sys, input, &segments);
    else
        status = mk_segment_ipa(input, &segments);
    if (status != MK_OK)
        return error_json(status, NULL);

    if (merge_tones) {
        mk_status ms = mk_merge_tone_digits(segments, &merged);
        if (ms == MK_OK) {
            mk_string_list_free(segments);
            segments = merged;
            merged = NULL;
        }
    }

    jb_init(&b);
    jb_cat(&b, "{\"ok\":true,\"segments\":[");
    for (size_t i = 0; i < mk_string_list_size(segments); i++) {
        const char *seg = mk_string_list_get(segments, i);
        bool recognized = false;
        mk_system_is_segment(sys, seg, &recognized);

        if (i > 0)
            jb_cat(&b, ",");
        jb_cat(&b, "{\"grapheme\":");
        jb_str(&b, seg);
        jb_catf(&b, ",\"recognized\":%s}", recognized ? "true" : "false");
    }
    jb_cat(&b, "]}");
    mk_string_list_free(segments);
    return jb_finish(&b);
}

EMSCRIPTEN_KEEPALIVE
char *merkmal_distance_matrix(const char *system_name,
                              const char *segments_csv)
{
    const mk_system *sys = NULL;
    mk_status status;
    jbuf b;

    /* Parse comma-separated segments. */
    char **items = NULL;
    size_t count = 0;
    size_t cap = 0;

    if (!segments_csv || !*segments_csv)
        return error_json(MK_ERR_INVALID_ARGUMENT, "empty input");

    status = get_system(system_name, &sys);
    if (status != MK_OK)
        return error_json(status, system_name);

    {
        const char *p = segments_csv;
        while (*p) {
            while (*p == ' ' || *p == '\t')
                p++;
            if (!*p || *p == ',') {
                if (*p == ',')
                    p++;
                continue;
            }
            const char *end = p;
            while (*end && *end != ',')
                end++;
            const char *trim = end;
            while (trim > p && (trim[-1] == ' ' || trim[-1] == '\t'))
                trim--;

            if (trim > p) {
                size_t len = (size_t)(trim - p);
                if (count >= cap) {
                    cap = cap ? cap * 2 : 16;
                    char **ni = (char **)realloc(items, cap * sizeof(char *));
                    if (!ni)
                        goto csv_oom;
                    items = ni;
                }
                items[count] = (char *)malloc(len + 1);
                if (!items[count])
                    goto csv_oom;
                memcpy(items[count], p, len);
                items[count][len] = '\0';
                count++;
                if (count > 100)
                    break;
            }
            p = (*end == ',') ? end + 1 : end;
        }
    }

    jb_init(&b);
    jb_cat(&b, "{\"ok\":true,\"segments\":[");
    for (size_t i = 0; i < count; i++) {
        if (i > 0)
            jb_cat(&b, ",");
        jb_str(&b, items[i]);
    }
    jb_cat(&b, "],\"recognized\":[");
    for (size_t i = 0; i < count; i++) {
        bool rec = false;
        mk_system_is_segment(sys, items[i], &rec);
        if (i > 0)
            jb_cat(&b, ",");
        jb_cat(&b, rec ? "true" : "false");
    }
    jb_cat(&b, "],\"matrix\":[");
    for (size_t i = 0; i < count; i++) {
        if (i > 0)
            jb_cat(&b, ",");
        jb_cat(&b, "[");
        for (size_t j = 0; j < count; j++) {
            double dist = 0.0;
            if (j > 0)
                jb_cat(&b, ",");
            if (mk_system_segment_distance(sys, items[i], items[j], &dist) ==
                MK_OK)
                jb_catf(&b, "%.6g", dist);
            else
                jb_cat(&b, "null");
        }
        jb_cat(&b, "]");
    }
    jb_cat(&b, "]}");

    for (size_t i = 0; i < count; i++)
        free(items[i]);
    free(items);
    return jb_finish(&b);

csv_oom:
    for (size_t i = 0; i < count; i++)
        free(items[i]);
    free(items);
    return error_json(MK_ERR_OOM, NULL);
}

EMSCRIPTEN_KEEPALIVE
char *merkmal_normalize(const char *grapheme)
{
    char *normalized = NULL;
    mk_status status;
    jbuf b;

    if (!grapheme || !*grapheme)
        return error_json(MK_ERR_INVALID_ARGUMENT, "empty input");

    status = mk_normalize_grapheme(grapheme, &normalized);
    if (status != MK_OK)
        return error_json(status, NULL);

    jb_init(&b);
    jb_cat(&b, "{\"ok\":true,\"input\":");
    jb_str(&b, grapheme);
    jb_cat(&b, ",\"normalized\":");
    jb_str(&b, normalized);
    jb_catf(&b, ",\"changed\":%s}",
            strcmp(grapheme, normalized) != 0 ? "true" : "false");
    mk_string_free(normalized);
    return jb_finish(&b);
}

EMSCRIPTEN_KEEPALIVE
char *merkmal_diagnose(const char *system_name, const char *grapheme)
{
    const mk_system *sys = NULL;
    mk_diagnosis diag;
    mk_status status;
    jbuf b;

    if (!grapheme || !*grapheme)
        return error_json(MK_ERR_INVALID_ARGUMENT, "empty grapheme");

    status = get_system(system_name, &sys);
    if (status != MK_OK)
        return error_json(status, system_name);

    status = mk_system_diagnose(sys, grapheme, &diag);
    if (status != MK_OK)
        return error_json(status, NULL);

    {
        char prefix[128] = "";
        if (diag.valid_prefix_bytes > 0 &&
            diag.valid_prefix_bytes < sizeof(prefix)) {
            memcpy(prefix, grapheme, diag.valid_prefix_bytes);
            prefix[diag.valid_prefix_bytes] = '\0';
        }

        jb_init(&b);
        jb_cat(&b, "{\"ok\":true,\"status\":");
        jb_str(&b, mk_status_string(diag.status));
        jb_cat(&b, ",\"valid_prefix\":");
        jb_str(&b, prefix);
        jb_cat(&b, ",\"offending\":");
        jb_str(&b, diag.offending);
        jb_cat(&b, "}");
    }
    return jb_finish(&b);
}

EMSCRIPTEN_KEEPALIVE
char *merkmal_register_model(const char *model_text)
{
    mk_registry *reg = shared_registry();
    char *diagnostic = NULL;
    mk_status status;
    jbuf b;

    if (!reg)
        return error_json(MK_ERR_OOM, NULL);
    if (!model_text || !*model_text)
        return error_json(MK_ERR_INVALID_ARGUMENT, "empty model text");

    status = mk_registry_add_model_text_ex(reg, model_text, &diagnostic);
    if (status != MK_OK) {
        char *result = error_json(status, diagnostic);
        mk_string_free(diagnostic);
        return result;
    }

    /* Extract the model name from the @model line. */
    {
        char name[128] = "unknown";
        const char *line = model_text;
        while (*line) {
            while (*line == ' ' || *line == '\t')
                line++;
            if (strncmp(line, "@model", 6) == 0) {
                const char *p = line + 6;
                while (*p == ' ' || *p == '\t')
                    p++;
                const char *end = p;
                while (*end && *end != ' ' && *end != '\t' && *end != '\n' &&
                       *end != '\r')
                    end++;
                size_t len =
                    (size_t)(end - p) < sizeof(name) - 1
                        ? (size_t)(end - p)
                        : sizeof(name) - 1;
                memcpy(name, p, len);
                name[len] = '\0';
                break;
            }
            while (*line && *line != '\n')
                line++;
            if (*line == '\n')
                line++;
        }

        jb_init(&b);
        jb_cat(&b, "{\"ok\":true,\"name\":");
        jb_str(&b, name);
        jb_cat(&b, "}");
    }
    return jb_finish(&b);
}

EMSCRIPTEN_KEEPALIVE
const char *merkmal_version(void)
{
    return MK_WEB_VERSION;
}

EMSCRIPTEN_KEEPALIVE
void merkmal_free(char *text)
{
    free(text);
}
