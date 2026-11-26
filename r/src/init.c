/* Registration of the native routines (R's "Writing R Extensions", 5.4). */

#define R_NO_REMAP
#include <R.h>
#include <R_ext/Rdynload.h>
#include <Rinternals.h>
#include <stdbool.h>

SEXP r_mk_build_info(void);
SEXP r_mk_registry_new(void);
SEXP r_mk_registry_add_model(SEXP, SEXP);
SEXP r_mk_list_systems(SEXP);
SEXP r_mk_system_kind(SEXP, SEXP);
SEXP r_mk_fingerprint(SEXP, SEXP);
SEXP r_mk_inventory(SEXP, SEXP);
SEXP r_mk_vector_labels(SEXP, SEXP);
SEXP r_mk_is_segment(SEXP, SEXP, SEXP);
SEXP r_mk_features(SEXP, SEXP, SEXP);
SEXP r_mk_diagnose(SEXP, SEXP, SEXP);
SEXP r_mk_distance(SEXP, SEXP, SEXP, SEXP, SEXP);
SEXP r_mk_distance_matrix(SEXP, SEXP, SEXP, SEXP);
SEXP r_mk_feature_vectors(SEXP, SEXP, SEXP);
SEXP r_mk_normalize(SEXP);
SEXP r_mk_unicode_normalize(SEXP, SEXP);
SEXP r_mk_ascii_chao_digits(SEXP);
SEXP r_mk_segment_ipa(SEXP);
SEXP r_mk_segment_ipa_merged(SEXP);
SEXP r_mk_system_segment_ipa(SEXP, SEXP, SEXP);
SEXP r_mk_merge_tone_digits(SEXP);
SEXP r_mk_split_tone(SEXP);
SEXP r_mk_feature_distance(SEXP, SEXP);
SEXP r_mk_sound_distance(SEXP, SEXP, SEXP);
SEXP r_mk_bundle_new(SEXP, SEXP, SEXP);
SEXP r_mk_bundle_from_grapheme(SEXP, SEXP, SEXP);
SEXP r_mk_bundle_text(SEXP);
SEXP r_mk_bundle_columns(SEXP);
SEXP r_mk_bundle_column_values(SEXP, SEXP);
SEXP r_mk_bundle_get(SEXP, SEXP);
SEXP r_mk_bundle_with_cells(SEXP, SEXP, SEXP);
SEXP r_mk_bundle_compare(SEXP, SEXP, SEXP);
SEXP r_mk_bundle_compatible(SEXP, SEXP);
SEXP r_mk_bundle_compatible_graphemes(SEXP, SEXP);
SEXP r_mk_sha256(SEXP);

static const R_CallMethodDef call_methods[] = {
    {"r_mk_build_info", (DL_FUNC)&r_mk_build_info, 0},
    {"r_mk_registry_new", (DL_FUNC)&r_mk_registry_new, 0},
    {"r_mk_registry_add_model", (DL_FUNC)&r_mk_registry_add_model, 2},
    {"r_mk_list_systems", (DL_FUNC)&r_mk_list_systems, 1},
    {"r_mk_system_kind", (DL_FUNC)&r_mk_system_kind, 2},
    {"r_mk_fingerprint", (DL_FUNC)&r_mk_fingerprint, 2},
    {"r_mk_inventory", (DL_FUNC)&r_mk_inventory, 2},
    {"r_mk_vector_labels", (DL_FUNC)&r_mk_vector_labels, 2},
    {"r_mk_is_segment", (DL_FUNC)&r_mk_is_segment, 3},
    {"r_mk_features", (DL_FUNC)&r_mk_features, 3},
    {"r_mk_diagnose", (DL_FUNC)&r_mk_diagnose, 3},
    {"r_mk_distance", (DL_FUNC)&r_mk_distance, 5},
    {"r_mk_distance_matrix", (DL_FUNC)&r_mk_distance_matrix, 4},
    {"r_mk_feature_vectors", (DL_FUNC)&r_mk_feature_vectors, 3},
    {"r_mk_normalize", (DL_FUNC)&r_mk_normalize, 1},
    {"r_mk_unicode_normalize", (DL_FUNC)&r_mk_unicode_normalize, 2},
    {"r_mk_ascii_chao_digits", (DL_FUNC)&r_mk_ascii_chao_digits, 1},
    {"r_mk_segment_ipa", (DL_FUNC)&r_mk_segment_ipa, 1},
    {"r_mk_segment_ipa_merged", (DL_FUNC)&r_mk_segment_ipa_merged, 1},
    {"r_mk_system_segment_ipa", (DL_FUNC)&r_mk_system_segment_ipa, 3},
    {"r_mk_merge_tone_digits", (DL_FUNC)&r_mk_merge_tone_digits, 1},
    {"r_mk_split_tone", (DL_FUNC)&r_mk_split_tone, 1},
    {"r_mk_feature_distance", (DL_FUNC)&r_mk_feature_distance, 2},
    {"r_mk_sound_distance", (DL_FUNC)&r_mk_sound_distance, 3},
    {"r_mk_bundle_new", (DL_FUNC)&r_mk_bundle_new, 3},
    {"r_mk_bundle_from_grapheme", (DL_FUNC)&r_mk_bundle_from_grapheme, 3},
    {"r_mk_bundle_text", (DL_FUNC)&r_mk_bundle_text, 1},
    {"r_mk_bundle_columns", (DL_FUNC)&r_mk_bundle_columns, 1},
    {"r_mk_bundle_column_values", (DL_FUNC)&r_mk_bundle_column_values, 2},
    {"r_mk_bundle_get", (DL_FUNC)&r_mk_bundle_get, 2},
    {"r_mk_bundle_with_cells", (DL_FUNC)&r_mk_bundle_with_cells, 3},
    {"r_mk_bundle_compare", (DL_FUNC)&r_mk_bundle_compare, 3},
    {"r_mk_bundle_compatible", (DL_FUNC)&r_mk_bundle_compatible, 2},
    {"r_mk_bundle_compatible_graphemes", (DL_FUNC)&r_mk_bundle_compatible_graphemes, 2},
    {"r_mk_sha256", (DL_FUNC)&r_mk_sha256, 1},
    {NULL, NULL, 0},
};

void R_init_merkmal(DllInfo *dll)
{
    R_registerRoutines(dll, NULL, call_methods, NULL, NULL);
    R_useDynamicSymbols(dll, FALSE);
    R_forceSymbols(dll, TRUE);
}
