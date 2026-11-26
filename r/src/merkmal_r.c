/* R bindings for merkmal.
 *
 * Includes merkmal.h and nothing else from the C core, as the Python
 * extension and the WebAssembly adapter do
 * (docs/development/adr/0001-c-api-is-the-canonical-interface.md).
 *
 * Every function is called through .Call from R/. Strings cross the boundary
 * as UTF-8: inputs are translated with translateCharUTF8 and outputs marked
 * CE_UTF8. The vectorized functions never raise for a grapheme a system
 * refuses; they return a status per element and leave the policy (NA, warning
 * or error) to the R code. Library memory is always released before an R
 * error can unwind the stack. */

#define R_NO_REMAP
#include <R.h>
#include <Rinternals.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

#include "merkmal.h"

/* ---- registries ------------------------------------------------------- */

/* A registry shared by the R objects that borrow from it. A bundle borrows a
 * system, so the registry must outlive every bundle; R runs finalizers in no
 * guaranteed order, so the registry is freed only when its own finalizer has
 * run and no bundle still holds it. */
typedef struct r_registry {
    mk_registry *registry;
    int holders;
    int released;
} r_registry;

static void r_registry_drop(r_registry *box)
{
    if (box != NULL && box->released && box->holders == 0) {
        mk_registry_free(box->registry);
        free(box);
    }
}

static void r_registry_finalize(SEXP ptr)
{
    r_registry *box = (r_registry *)R_ExternalPtrAddr(ptr);
    if (box == NULL) {
        return;
    }
    box->released = 1;
    R_ClearExternalPtr(ptr);
    r_registry_drop(box);
}

static void fail_status(mk_status status, const char *what)
{
    Rf_error("merkmal: %s: %s", what, mk_status_string(status));
}

static r_registry *get_box(SEXP ptr)
{
    r_registry *box;
    if (TYPEOF(ptr) != EXTPTRSXP) {
        Rf_error("merkmal: not a registry");
    }
    box = (r_registry *)R_ExternalPtrAddr(ptr);
    if (box == NULL || box->registry == NULL) {
        Rf_error("merkmal: the registry has been released");
    }
    return box;
}

static const char *one_string(SEXP x, const char *what)
{
    if (!Rf_isString(x) || XLENGTH(x) != 1 || STRING_ELT(x, 0) == NA_STRING) {
        Rf_error("merkmal: %s must be a single string", what);
    }
    return Rf_translateCharUTF8(STRING_ELT(x, 0));
}

/* NULL or a single string. */
static const char *optional_string(SEXP x, const char *what)
{
    return Rf_isNull(x) ? NULL : one_string(x, what);
}

static const mk_system *get_system(SEXP reg, SEXP system)
{
    const mk_system *out = NULL;
    const char *name = one_string(system, "system");
    mk_status status = mk_registry_get_system(get_box(reg)->registry, name, &out);
    if (status != MK_OK) {
        Rf_error("merkmal: unknown system '%s'", name);
    }
    return out;
}

static SEXP mkutf8(const char *s)
{
    return Rf_mkCharCE(s, CE_UTF8);
}

/* An owned string list as a character vector; frees the list. */
static SEXP take_list(mk_string_list *list)
{
    size_t n = mk_string_list_size(list);
    SEXP out = PROTECT(Rf_allocVector(STRSXP, (R_xlen_t)n));
    for (size_t i = 0; i < n; i++) {
        SET_STRING_ELT(out, (R_xlen_t)i, mkutf8(mk_string_list_get(list, i)));
    }
    mk_string_list_free(list);
    UNPROTECT(1);
    return out;
}

SEXP r_mk_build_info(void)
{
    SEXP out = PROTECT(Rf_allocVector(STRSXP, 3));
    SET_STRING_ELT(out, 0, Rf_mkChar(mk_version_string()));
    SET_STRING_ELT(out, 1, Rf_mkChar(mk_data_profile()));
    SET_STRING_ELT(out, 2, Rf_mkChar(mk_unicode_version()));
    UNPROTECT(1);
    return out;
}

SEXP r_mk_registry_new(void)
{
    r_registry *box = (r_registry *)calloc(1, sizeof *box);
    mk_status status;
    SEXP ptr;
    if (box == NULL) {
        Rf_error("merkmal: out of memory");
    }
    status = mk_registry_new_builtin(&box->registry);
    if (status != MK_OK) {
        free(box);
        fail_status(status, "creating the registry");
    }
    ptr = PROTECT(R_MakeExternalPtr(box, R_NilValue, R_NilValue));
    R_RegisterCFinalizerEx(ptr, r_registry_finalize, TRUE);
    UNPROTECT(1);
    return ptr;
}

SEXP r_mk_registry_add_model(SEXP reg, SEXP text)
{
    r_registry *box = get_box(reg);
    const char *model;
    char *diagnostic = NULL;
    mk_status status;
    char message[512];
    if (!Rf_isString(text) || XLENGTH(text) != 1 || STRING_ELT(text, 0) == NA_STRING) {
        Rf_error("merkmal: the model text must be a single string");
    }
    model = Rf_translateCharUTF8(STRING_ELT(text, 0));
    status = mk_registry_add_model_text_n(box->registry, model, strlen(model), &diagnostic);
    if (status == MK_OK) {
        return R_NilValue;
    }
    snprintf(message, sizeof message, "%s%s%s", mk_status_string(status), diagnostic != NULL ? ": " : "", diagnostic != NULL ? diagnostic : "");
    mk_string_free(diagnostic);
    Rf_error("merkmal: the model was not added: %s", message);
    return R_NilValue;
}

SEXP r_mk_list_systems(SEXP reg)
{
    mk_string_list *list = NULL;
    mk_status status = mk_registry_list_systems(get_box(reg)->registry, &list);
    if (status != MK_OK) {
        fail_status(status, "listing systems");
    }
    return take_list(list);
}

SEXP r_mk_system_kind(SEXP reg, SEXP system)
{
    const char *kind = NULL;
    mk_status status = mk_system_kind(get_system(reg, system), &kind);
    if (status != MK_OK) {
        fail_status(status, "system kind");
    }
    return Rf_mkString(kind);
}

SEXP r_mk_fingerprint(SEXP reg, SEXP system)
{
    char *payload = NULL;
    char *digest = NULL;
    SEXP out;
    mk_status status = mk_system_semantic_fingerprint(get_system(reg, system), &payload, &digest);
    if (status != MK_OK) {
        fail_status(status, "fingerprint");
    }
    out = PROTECT(Rf_allocVector(STRSXP, 2));
    SET_STRING_ELT(out, 0, mkutf8(payload));
    SET_STRING_ELT(out, 1, mkutf8(digest));
    mk_string_free(payload);
    mk_string_free(digest);
    UNPROTECT(1);
    return out;
}

SEXP r_mk_inventory(SEXP reg, SEXP system)
{
    mk_string_list *list = NULL;
    mk_status status = mk_system_inventory(get_system(reg, system), &list);
    if (status != MK_OK) {
        fail_status(status, "inventory");
    }
    return take_list(list);
}

SEXP r_mk_vector_labels(SEXP reg, SEXP system)
{
    mk_string_list *list = NULL;
    mk_status status = mk_system_vector_labels(get_system(reg, system), &list);
    if (status != MK_OK) {
        fail_status(status, "vector labels");
    }
    return take_list(list);
}

/* ---- per-grapheme functions -------------------------------------------- */

/* The status of each element as its stable English label, "ok" for MK_OK. */
static SEXP status_label(mk_status status)
{
    return Rf_mkChar(status == MK_OK ? "ok" : mk_status_string(status));
}

SEXP r_mk_is_segment(SEXP reg, SEXP system, SEXP x)
{
    const mk_system *sys = get_system(reg, system);
    R_xlen_t n = XLENGTH(x);
    SEXP out = PROTECT(Rf_allocVector(LGLSXP, n));
    for (R_xlen_t i = 0; i < n; i++) {
        bool ok = false;
        if (STRING_ELT(x, i) == NA_STRING) {
            LOGICAL(out)
            [i] = NA_LOGICAL;
            continue;
        }
        /* Every status but MK_OK is a refusal here, as in is_segment(). */
        if (mk_system_is_segment(sys, Rf_translateCharUTF8(STRING_ELT(x, i)), &ok) != MK_OK) {
            ok = false;
        }
        LOGICAL(out)
        [i] = ok ? TRUE : FALSE;
    }
    UNPROTECT(1);
    return out;
}

/* list(features = list of character vectors or NULL, status = character) */
SEXP r_mk_features(SEXP reg, SEXP system, SEXP x)
{
    const mk_system *sys = get_system(reg, system);
    R_xlen_t n = XLENGTH(x);
    SEXP features = PROTECT(Rf_allocVector(VECSXP, n));
    SEXP statuses = PROTECT(Rf_allocVector(STRSXP, n));
    SEXP out = PROTECT(Rf_allocVector(VECSXP, 2));
    for (R_xlen_t i = 0; i < n; i++) {
        mk_string_list *list = NULL;
        mk_status status;
        if (STRING_ELT(x, i) == NA_STRING) {
            SET_STRING_ELT(statuses, i, NA_STRING);
            continue;
        }
        status = mk_system_grapheme_features(sys, Rf_translateCharUTF8(STRING_ELT(x, i)), &list);
        SET_STRING_ELT(statuses, i, status_label(status));
        if (status == MK_OK) {
            SET_VECTOR_ELT(features, i, take_list(list));
        } else {
            mk_string_list_free(list);
        }
    }
    SET_VECTOR_ELT(out, 0, features);
    SET_VECTOR_ELT(out, 1, statuses);
    UNPROTECT(3);
    return out;
}

/* list(status, valid_prefix, offset, offending) */
SEXP r_mk_diagnose(SEXP reg, SEXP system, SEXP x)
{
    const mk_system *sys = get_system(reg, system);
    R_xlen_t n = XLENGTH(x);
    SEXP status = PROTECT(Rf_allocVector(STRSXP, n));
    SEXP prefix = PROTECT(Rf_allocVector(STRSXP, n));
    SEXP offset = PROTECT(Rf_allocVector(INTSXP, n));
    SEXP offending = PROTECT(Rf_allocVector(STRSXP, n));
    SEXP out = PROTECT(Rf_allocVector(VECSXP, 4));
    for (R_xlen_t i = 0; i < n; i++) {
        mk_diagnosis d;
        const char *g;
        mk_status rc;
        char *head;
        if (STRING_ELT(x, i) == NA_STRING) {
            SET_STRING_ELT(status, i, NA_STRING);
            SET_STRING_ELT(prefix, i, NA_STRING);
            INTEGER(offset)
            [i] = NA_INTEGER;
            SET_STRING_ELT(offending, i, NA_STRING);
            continue;
        }
        g = Rf_translateCharUTF8(STRING_ELT(x, i));
        memset(&d, 0, sizeof d);
        rc = mk_system_diagnose(sys, g, &d);
        if (rc != MK_OK) {
            fail_status(rc, "diagnose");
        }
        head = R_alloc(d.valid_prefix_bytes + 1, 1);
        memcpy(head, g, d.valid_prefix_bytes);
        head[d.valid_prefix_bytes] = '\0';
        SET_STRING_ELT(status, i, status_label(d.status));
        SET_STRING_ELT(prefix, i, mkutf8(head));
        INTEGER(offset)
        [i] = (int)d.offending_offset;
        SET_STRING_ELT(offending, i, mkutf8(d.offending));
    }
    SET_VECTOR_ELT(out, 0, status);
    SET_VECTOR_ELT(out, 1, prefix);
    SET_VECTOR_ELT(out, 2, offset);
    SET_VECTOR_ELT(out, 3, offending);
    UNPROTECT(5);
    return out;
}

static const char *comparability_label(mk_comparability why)
{
    switch (why) {
    case MK_CMP_OK:
        return "ok";
    case MK_CMP_CROSS_TIER:
        return "cross-tier";
    case MK_CMP_NO_SHARED_DIMENSION:
        return "no-shared-dimension";
    }
    return "unknown";
}

/* Pairwise over equal-length a and b (recycled in R).
 * list(distance, coverage, comparability, status) */
SEXP r_mk_distance(SEXP reg, SEXP system, SEXP a, SEXP b, SEXP weights)
{
    const mk_system *sys = get_system(reg, system);
    const char *preset = optional_string(weights, "node_weights");
    R_xlen_t n = XLENGTH(a);
    SEXP dist = PROTECT(Rf_allocVector(REALSXP, n));
    SEXP cov = PROTECT(Rf_allocVector(REALSXP, n));
    SEXP cmp = PROTECT(Rf_allocVector(STRSXP, n));
    SEXP st = PROTECT(Rf_allocVector(STRSXP, n));
    SEXP out = PROTECT(Rf_allocVector(VECSXP, 4));
    if (XLENGTH(b) != n) {
        Rf_error("merkmal: a and b must have the same length");
    }
    for (R_xlen_t i = 0; i < n; i++) {
        double d = 0.0;
        double c = 0.0;
        mk_comparability why = MK_CMP_OK;
        mk_status status;
        if (STRING_ELT(a, i) == NA_STRING || STRING_ELT(b, i) == NA_STRING) {
            REAL(dist)
            [i] = NA_REAL;
            REAL(cov)
            [i] = NA_REAL;
            SET_STRING_ELT(cmp, i, NA_STRING);
            SET_STRING_ELT(st, i, NA_STRING);
            continue;
        }
        status = mk_system_segment_distance_ex(sys, Rf_translateCharUTF8(STRING_ELT(a, i)), Rf_translateCharUTF8(STRING_ELT(b, i)), preset, &d, &c, &why);
        if (status == MK_ERR_INVALID_ARGUMENT && preset != NULL) {
            Rf_error("merkmal: unknown weight preset '%s'", preset);
        }
        REAL(dist)
        [i] = status == MK_OK ? d : NA_REAL;
        REAL(cov)
        [i] = status == MK_OK ? c : NA_REAL;
        SET_STRING_ELT(cmp, i, status == MK_OK ? Rf_mkChar(comparability_label(why)) : NA_STRING);
        SET_STRING_ELT(st, i, status_label(status));
    }
    SET_VECTOR_ELT(out, 0, dist);
    SET_VECTOR_ELT(out, 1, cov);
    SET_VECTOR_ELT(out, 2, cmp);
    SET_VECTOR_ELT(out, 3, st);
    UNPROTECT(5);
    return out;
}

/* Every pair of x, as a symmetric matrix. list(matrix, status per grapheme) */
SEXP r_mk_distance_matrix(SEXP reg, SEXP system, SEXP x, SEXP weights)
{
    const mk_system *sys = get_system(reg, system);
    const char *preset = optional_string(weights, "node_weights");
    R_xlen_t n = XLENGTH(x);
    SEXP m = PROTECT(Rf_allocMatrix(REALSXP, (int)n, (int)n));
    SEXP st = PROTECT(Rf_allocVector(STRSXP, n));
    SEXP out = PROTECT(Rf_allocVector(VECSXP, 2));
    double *v = REAL(m);
    for (R_xlen_t i = 0; i < n; i++) {
        bool ok = false;
        mk_status status;
        if (STRING_ELT(x, i) == NA_STRING) {
            SET_STRING_ELT(st, i, NA_STRING);
            continue;
        }
        status = mk_system_is_segment(sys, Rf_translateCharUTF8(STRING_ELT(x, i)), &ok);
        if (status == MK_OK && !ok) {
            mk_diagnosis d;
            memset(&d, 0, sizeof d);
            if (mk_system_diagnose(sys, Rf_translateCharUTF8(STRING_ELT(x, i)), &d) == MK_OK) {
                status = d.status;
            }
        }
        SET_STRING_ELT(st, i, status_label(status));
    }
    for (R_xlen_t i = 0; i < n; i++) {
        for (R_xlen_t j = i; j < n; j++) {
            double d = NA_REAL;
            if (STRING_ELT(st, i) != NA_STRING && STRING_ELT(st, j) != NA_STRING &&
                strcmp(CHAR(STRING_ELT(st, i)), "ok") == 0 && strcmp(CHAR(STRING_ELT(st, j)), "ok") == 0) {
                mk_status status = mk_system_segment_distance_with_weights(
                    sys, Rf_translateCharUTF8(STRING_ELT(x, i)), Rf_translateCharUTF8(STRING_ELT(x, j)), preset, &d
                );
                if (status == MK_ERR_INVALID_ARGUMENT && preset != NULL) {
                    Rf_error("merkmal: unknown weight preset '%s'", preset);
                }
                if (status != MK_OK) {
                    d = NA_REAL;
                }
            }
            v[i + j * n] = d;
            v[j + i * n] = d;
        }
    }
    SET_VECTOR_ELT(out, 0, m);
    SET_VECTOR_ELT(out, 1, st);
    UNPROTECT(3);
    return out;
}

/* One row per grapheme, NA rows for refusals. list(matrix, status) */
SEXP r_mk_feature_vectors(SEXP reg, SEXP system, SEXP x)
{
    const mk_system *sys = get_system(reg, system);
    size_t width = 0;
    R_xlen_t n = XLENGTH(x);
    mk_status status = mk_system_vector_width(sys, &width);
    SEXP m;
    SEXP st;
    SEXP out;
    double *row;
    if (status != MK_OK) {
        fail_status(status, "vector width");
    }
    m = PROTECT(Rf_allocMatrix(REALSXP, (int)n, (int)width));
    st = PROTECT(Rf_allocVector(STRSXP, n));
    out = PROTECT(Rf_allocVector(VECSXP, 2));
    row = (double *)R_alloc(width > 0 ? width : 1, sizeof(double));
    for (R_xlen_t i = 0; i < n; i++) {
        size_t written = 0;
        if (STRING_ELT(x, i) == NA_STRING) {
            status = MK_ERR_INVALID_ARGUMENT;
            SET_STRING_ELT(st, i, NA_STRING);
        } else {
            status = mk_system_feature_vector(sys, Rf_translateCharUTF8(STRING_ELT(x, i)), row, width, &written);
            SET_STRING_ELT(st, i, status_label(status));
        }
        for (size_t k = 0; k < width; k++) {
            REAL(m)
            [i + (R_xlen_t)k * n] = status == MK_OK && k < written ? row[k] : NA_REAL;
        }
    }
    SET_VECTOR_ELT(out, 0, m);
    SET_VECTOR_ELT(out, 1, st);
    UNPROTECT(3);
    return out;
}

/* ---- strings and tokenization ------------------------------------------ */

typedef mk_status (*string_fn)(const char *, char **);

static mk_status nfc(const char *in, char **out)
{
    return mk_unicode_normalize(in, MK_NFC, out);
}

static mk_status nfd(const char *in, char **out)
{
    return mk_unicode_normalize(in, MK_NFD, out);
}

static SEXP map_strings(SEXP x, string_fn fn, const char *what)
{
    R_xlen_t n = XLENGTH(x);
    SEXP out = PROTECT(Rf_allocVector(STRSXP, n));
    for (R_xlen_t i = 0; i < n; i++) {
        char *s = NULL;
        mk_status status;
        if (STRING_ELT(x, i) == NA_STRING) {
            SET_STRING_ELT(out, i, NA_STRING);
            continue;
        }
        status = fn(Rf_translateCharUTF8(STRING_ELT(x, i)), &s);
        if (status != MK_OK) {
            mk_string_free(s);
            fail_status(status, what);
        }
        SET_STRING_ELT(out, i, mkutf8(s));
        mk_string_free(s);
    }
    UNPROTECT(1);
    return out;
}

SEXP r_mk_normalize(SEXP x)
{
    return map_strings(x, mk_normalize_grapheme, "normalize");
}

SEXP r_mk_unicode_normalize(SEXP x, SEXP form)
{
    const char *f = one_string(form, "form");
    if (strcmp(f, "NFC") == 0) {
        return map_strings(x, nfc, "unicode_normalize");
    }
    if (strcmp(f, "NFD") == 0) {
        return map_strings(x, nfd, "unicode_normalize");
    }
    Rf_error("merkmal: form must be \"NFC\" or \"NFD\"");
    return R_NilValue;
}

SEXP r_mk_ascii_chao_digits(SEXP x)
{
    return map_strings(x, mk_ascii_chao_digits, "ascii_chao_digits");
}

typedef mk_status (*split_fn)(const char *, mk_string_list **);

static SEXP map_splits(SEXP x, split_fn fn, const mk_system *sys, const char *what)
{
    R_xlen_t n = XLENGTH(x);
    SEXP out = PROTECT(Rf_allocVector(VECSXP, n));
    for (R_xlen_t i = 0; i < n; i++) {
        mk_string_list *list = NULL;
        mk_status status;
        const char *text;
        if (STRING_ELT(x, i) == NA_STRING) {
            SET_VECTOR_ELT(out, i, Rf_ScalarString(NA_STRING));
            continue;
        }
        text = Rf_translateCharUTF8(STRING_ELT(x, i));
        status = sys != NULL ? mk_system_segment_ipa(sys, text, &list) : fn(text, &list);
        if (status != MK_OK) {
            mk_string_list_free(list);
            fail_status(status, what);
        }
        SET_VECTOR_ELT(out, i, take_list(list));
    }
    UNPROTECT(1);
    return out;
}

SEXP r_mk_segment_ipa(SEXP x)
{
    return map_splits(x, mk_segment_ipa, NULL, "segment_ipa");
}

SEXP r_mk_segment_ipa_merged(SEXP x)
{
    return map_splits(x, mk_segment_ipa_merged, NULL, "segment_ipa_merged");
}

SEXP r_mk_system_segment_ipa(SEXP reg, SEXP system, SEXP x)
{
    return map_splits(x, NULL, get_system(reg, system), "system_segment_ipa");
}

/* A character vector of segments in, the merged segments out. */
SEXP r_mk_merge_tone_digits(SEXP segments)
{
    R_xlen_t n = XLENGTH(segments);
    const char **items = (const char **)R_alloc(n > 0 ? (size_t)n : 1, sizeof(char *));
    mk_string_list *in = NULL;
    mk_string_list *merged = NULL;
    mk_status status;
    for (R_xlen_t i = 0; i < n; i++) {
        if (STRING_ELT(segments, i) == NA_STRING) {
            Rf_error("merkmal: segments must not contain NA");
        }
        items[i] = Rf_translateCharUTF8(STRING_ELT(segments, i));
    }
    status = mk_string_list_new(items, (size_t)n, &in);
    if (status != MK_OK) {
        fail_status(status, "merge_tone_digits");
    }
    status = mk_merge_tone_digits(in, &merged);
    mk_string_list_free(in);
    if (status != MK_OK) {
        mk_string_list_free(merged);
        fail_status(status, "merge_tone_digits");
    }
    return take_list(merged);
}

/* list(base, tone, status) */
SEXP r_mk_split_tone(SEXP x)
{
    R_xlen_t n = XLENGTH(x);
    SEXP base = PROTECT(Rf_allocVector(STRSXP, n));
    SEXP tone = PROTECT(Rf_allocVector(STRSXP, n));
    SEXP st = PROTECT(Rf_allocVector(STRSXP, n));
    SEXP out = PROTECT(Rf_allocVector(VECSXP, 3));
    for (R_xlen_t i = 0; i < n; i++) {
        char *b = NULL;
        char *t = NULL;
        mk_status status;
        if (STRING_ELT(x, i) == NA_STRING) {
            SET_STRING_ELT(base, i, NA_STRING);
            SET_STRING_ELT(tone, i, NA_STRING);
            SET_STRING_ELT(st, i, NA_STRING);
            continue;
        }
        status = mk_split_tone(Rf_translateCharUTF8(STRING_ELT(x, i)), &b, &t);
        SET_STRING_ELT(base, i, status == MK_OK ? mkutf8(b) : NA_STRING);
        SET_STRING_ELT(tone, i, status == MK_OK && t != NULL ? mkutf8(t) : NA_STRING);
        SET_STRING_ELT(st, i, status_label(status));
        mk_string_free(b);
        mk_string_free(t);
    }
    SET_VECTOR_ELT(out, 0, base);
    SET_VECTOR_ELT(out, 1, tone);
    SET_VECTOR_ELT(out, 2, st);
    UNPROTECT(4);
    return out;
}

/* ---- the geometry ------------------------------------------------------ */

SEXP r_mk_feature_distance(SEXP a, SEXP b)
{
    int hops = 0;
    mk_status status = mk_feature_distance(one_string(a, "feature a"), one_string(b, "feature b"), &hops);
    if (status == MK_ERR_NO_TREE_PATH) {
        return Rf_ScalarInteger(NA_INTEGER);
    }
    if (status != MK_OK) {
        fail_status(status, "feature_distance");
    }
    return Rf_ScalarInteger(hops);
}

static mk_feature_view view_of(SEXP x, const char ***store)
{
    mk_feature_view view;
    R_xlen_t n = XLENGTH(x);
    *store = (const char **)R_alloc(n > 0 ? (size_t)n : 1, sizeof(char *));
    for (R_xlen_t i = 0; i < n; i++) {
        if (STRING_ELT(x, i) == NA_STRING) {
            Rf_error("merkmal: feature sets must not contain NA");
        }
        (*store)[i] = Rf_translateCharUTF8(STRING_ELT(x, i));
    }
    view.features = *store;
    view.count = (size_t)n;
    return view;
}

SEXP r_mk_sound_distance(SEXP a, SEXP b, SEXP weights)
{
    const char **sa;
    const char **sb;
    double d = 0.0;
    mk_feature_view va = view_of(a, &sa);
    mk_feature_view vb = view_of(b, &sb);
    mk_status status = mk_sound_distance(va, vb, optional_string(weights, "node_weights"), &d);
    if (status != MK_OK) {
        fail_status(status, "sound_distance");
    }
    return Rf_ScalarReal(d);
}

/* ---- abstract segments (bundles) --------------------------------------- */

typedef struct r_bundle {
    mk_bundle *bundle;
    r_registry *owner;
} r_bundle;

static void r_bundle_finalize(SEXP ptr)
{
    r_bundle *rb = (r_bundle *)R_ExternalPtrAddr(ptr);
    if (rb == NULL) {
        return;
    }
    mk_bundle_free(rb->bundle);
    rb->owner->holders--;
    r_registry_drop(rb->owner);
    free(rb);
    R_ClearExternalPtr(ptr);
}

static SEXP wrap_bundle(mk_bundle *bundle, r_registry *owner, SEXP reg)
{
    r_bundle *rb = (r_bundle *)calloc(1, sizeof *rb);
    SEXP ptr;
    if (rb == NULL) {
        mk_bundle_free(bundle);
        Rf_error("merkmal: out of memory");
    }
    rb->bundle = bundle;
    rb->owner = owner;
    owner->holders++;
    ptr = PROTECT(R_MakeExternalPtr(rb, R_NilValue, reg));
    R_RegisterCFinalizerEx(ptr, r_bundle_finalize, TRUE);
    UNPROTECT(1);
    return ptr;
}

static r_bundle *get_bundle(SEXP ptr)
{
    r_bundle *rb;
    if (TYPEOF(ptr) != EXTPTRSXP) {
        Rf_error("merkmal: not an abstract segment");
    }
    rb = (r_bundle *)R_ExternalPtrAddr(ptr);
    if (rb == NULL) {
        Rf_error("merkmal: the abstract segment has been released");
    }
    return rb;
}

SEXP r_mk_bundle_new(SEXP reg, SEXP system, SEXP text)
{
    r_registry *box = get_box(reg);
    const mk_system *sys = get_system(reg, system);
    const char *t = optional_string(text, "text");
    mk_bundle *bundle = NULL;
    mk_status status = (t == NULL || t[0] == '\0') ? mk_bundle_new(sys, &bundle) : mk_bundle_from_text(sys, t, &bundle);
    if (status != MK_OK) {
        mk_bundle_free(bundle);
        fail_status(status, "abstract segment");
    }
    return wrap_bundle(bundle, box, reg);
}

SEXP r_mk_bundle_from_grapheme(SEXP reg, SEXP system, SEXP grapheme)
{
    r_registry *box = get_box(reg);
    const mk_system *sys = get_system(reg, system);
    mk_bundle *bundle = NULL;
    mk_status status = mk_bundle_from_grapheme(sys, one_string(grapheme, "grapheme"), &bundle);
    if (status != MK_OK) {
        mk_bundle_free(bundle);
        fail_status(status, "abstract segment from a grapheme");
    }
    return wrap_bundle(bundle, box, reg);
}

SEXP r_mk_bundle_text(SEXP ptr)
{
    char *text = NULL;
    SEXP out;
    mk_status status = mk_bundle_to_text(get_bundle(ptr)->bundle, &text);
    if (status != MK_OK) {
        fail_status(status, "abstract segment text");
    }
    out = PROTECT(Rf_allocVector(STRSXP, 1));
    SET_STRING_ELT(out, 0, mkutf8(text));
    mk_string_free(text);
    UNPROTECT(1);
    return out;
}

SEXP r_mk_bundle_columns(SEXP ptr)
{
    const mk_bundle *bundle = get_bundle(ptr)->bundle;
    size_t n = 0;
    SEXP out;
    mk_status status = mk_bundle_column_count(bundle, &n);
    if (status != MK_OK) {
        fail_status(status, "abstract segment columns");
    }
    out = PROTECT(Rf_allocVector(STRSXP, (R_xlen_t)n));
    for (size_t i = 0; i < n; i++) {
        const char *name = NULL;
        status = mk_bundle_column_name(bundle, i, &name);
        if (status != MK_OK) {
            fail_status(status, "abstract segment column");
        }
        SET_STRING_ELT(out, (R_xlen_t)i, mkutf8(name));
    }
    UNPROTECT(1);
    return out;
}

SEXP r_mk_bundle_column_values(SEXP ptr, SEXP column)
{
    mk_string_list *list = NULL;
    mk_status status = mk_bundle_column_values(get_bundle(ptr)->bundle, one_string(column, "column"), &list);
    if (status != MK_OK) {
        fail_status(status, "column values");
    }
    return take_list(list);
}

SEXP r_mk_bundle_get(SEXP ptr, SEXP column)
{
    char *cell = NULL;
    SEXP out;
    mk_status status = mk_bundle_get(get_bundle(ptr)->bundle, one_string(column, "column"), &cell);
    if (status != MK_OK) {
        fail_status(status, "cell");
    }
    out = PROTECT(Rf_allocVector(STRSXP, 1));
    SET_STRING_ELT(out, 0, mkutf8(cell));
    mk_string_free(cell);
    UNPROTECT(1);
    return out;
}

/* A new bundle with some cells replaced; the original is unchanged, as R
 * values are. */
SEXP r_mk_bundle_with_cells(SEXP ptr, SEXP columns, SEXP cells)
{
    r_bundle *rb = get_bundle(ptr);
    mk_bundle *copy = NULL;
    R_xlen_t n = XLENGTH(columns);
    mk_status status = mk_bundle_copy(rb->bundle, &copy);
    if (status != MK_OK) {
        fail_status(status, "copy");
    }
    for (R_xlen_t i = 0; i < n; i++) {
        const char *column = Rf_translateCharUTF8(STRING_ELT(columns, i));
        status = mk_bundle_set(copy, column, Rf_translateCharUTF8(STRING_ELT(cells, i)));
        if (status != MK_OK) {
            mk_bundle_free(copy);
            Rf_error("merkmal: cell '%s': %s", column, mk_status_string(status));
        }
    }
    return wrap_bundle(copy, rb->owner, R_ExternalPtrProtected(ptr));
}

SEXP r_mk_bundle_compare(SEXP a, SEXP b, SEXP weights)
{
    mk_bundle_comparison cmp;
    SEXP out;
    SEXP names;
    mk_status status = mk_bundle_compare(get_bundle(a)->bundle, get_bundle(b)->bundle, optional_string(weights, "node_weights"), &cmp);
    if (status != MK_OK) {
        fail_status(status, "compare");
    }
    out = PROTECT(Rf_allocVector(VECSXP, 5));
    names = PROTECT(Rf_allocVector(STRSXP, 5));
    SET_VECTOR_ELT(out, 0, Rf_ScalarReal(cmp.distance));
    SET_VECTOR_ELT(out, 1, Rf_ScalarReal(cmp.coverage));
    SET_VECTOR_ELT(out, 2, Rf_ScalarReal(cmp.minimum));
    SET_VECTOR_ELT(out, 3, Rf_ScalarReal(cmp.maximum));
    SET_VECTOR_ELT(out, 4, Rf_mkString(comparability_label(cmp.why)));
    SET_STRING_ELT(names, 0, Rf_mkChar("distance"));
    SET_STRING_ELT(names, 1, Rf_mkChar("coverage"));
    SET_STRING_ELT(names, 2, Rf_mkChar("minimum"));
    SET_STRING_ELT(names, 3, Rf_mkChar("maximum"));
    SET_STRING_ELT(names, 4, Rf_mkChar("comparability"));
    Rf_setAttrib(out, R_NamesSymbol, names);
    UNPROTECT(2);
    return out;
}

SEXP r_mk_bundle_compatible(SEXP ptr, SEXP x)
{
    const mk_bundle *bundle = get_bundle(ptr)->bundle;
    R_xlen_t n = XLENGTH(x);
    SEXP out = PROTECT(Rf_allocVector(LGLSXP, n));
    for (R_xlen_t i = 0; i < n; i++) {
        bool ok = false;
        if (STRING_ELT(x, i) == NA_STRING ||
            mk_bundle_compatible(bundle, Rf_translateCharUTF8(STRING_ELT(x, i)), &ok) != MK_OK) {
            LOGICAL(out)
            [i] = STRING_ELT(x, i) == NA_STRING ? NA_LOGICAL : FALSE;
            continue;
        }
        LOGICAL(out)
        [i] = ok ? TRUE : FALSE;
    }
    UNPROTECT(1);
    return out;
}

SEXP r_mk_bundle_compatible_graphemes(SEXP ptr, SEXP weights)
{
    mk_string_list *list = NULL;
    mk_status status = mk_bundle_compatible_graphemes(get_bundle(ptr)->bundle, optional_string(weights, "node_weights"), &list);
    if (status != MK_OK) {
        fail_status(status, "compatible graphemes");
    }
    return take_list(list);
}
