#ifndef MK_INTERNAL_H
#define MK_INTERNAL_H

#include "merkmal.h"

#include <stddef.h>

typedef enum mk_system_type {
    MK_SYSTEM_CATEGORICAL = 1,
    MK_SYSTEM_VALUED = 2,
    MK_SYSTEM_TRAINED = 3
} mk_system_type;

typedef struct mk_builtin_entry {
    const char *grapheme;
    const char *const *features;
    size_t feature_count;
} mk_builtin_entry;

/* What a scorer actually compares. Scoring reads feature sets and nothing else:
 * it has no use for a grapheme, an inventory row, or a resolved entry. Taking
 * mk_builtin_entry made five call sites fabricate one on the stack, two of them
 * inventing a grapheme string that the scorer then read to decide identity. */
typedef struct mk_feature_view {
    const char *const *features;
    size_t count;
} mk_feature_view;

typedef struct mk_geometry_leaf {
    const char *name;
    const char *positive;
    const char *negative;
    double depth;
    const char *parent;
} mk_geometry_leaf;

/* An ordered scale, for properties where the difference between two values is a
 * quantity rather than a mismatch. Vowel height, Chao tone level, and duration
 * are all like this: /i/ is further from /a/ than from /e/, and half-long sits
 * between short and long.
 *
 * Encoding these as independent privative flags loses that. It made /i/ score
 * further from /e/ than from /a/, made a half-long vowel further from a long one
 * than a plain vowel was, and made the Chao code non-monotonic in the digit.
 *
 * Cost is |level_a - level_b| / (level_count - 1) * weight, so one step on a
 * seven-point height scale costs a sixth of the full range.
 *
 * default_level is the value a segment takes when it carries no label from the
 * scale: 0-based index for scales with an unmarked default (a plain vowel is
 * short), or MK_ORDINAL_UNDEFINED where absence means the property does not
 * apply (a consonant has no vowel height, a toneless segment no tone level).
 * An undefined scale is skipped for that pair, exactly as the leaf loop skips a
 * feature neither segment carries. */
#define MK_ORDINAL_UNDEFINED (-1)

typedef struct mk_ordinal_scale {
    const char *name;
    const char *node;
    const char *const *levels;
    size_t level_count;
    int default_level;
    double weight;
} mk_ordinal_scale;

typedef struct mk_feature_node_map {
    const char *feature;
    const char *node;
} mk_feature_node_map;

typedef struct mk_node_depth {
    const char *node;
    double depth;
} mk_node_depth;

typedef struct mk_node_parent {
    const char *node;
    const char *parent;
} mk_node_parent;

typedef struct mk_node_weight {
    const char *node;
    double weight;
} mk_node_weight;

typedef struct mk_node_weight_preset {
    const char *name;
    const mk_node_weight *weights;
    size_t weight_count;
    int flat;
} mk_node_weight_preset;

typedef struct mk_diacritic_map {
    const char *mark;
    const char *feature;
} mk_diacritic_map;

/* A precomposed letter and its canonical decomposition, restricted to marks
 * the feature system understands. Compiled in so that lookup accepts the
 * same graphemes with or without utf8proc. */
typedef struct mk_decomposition {
    const char *composed;
    const char *decomposed;
} mk_decomposition;

typedef struct mk_tone_mark {
    const char *mark;
    const char *const *features;
    size_t feature_count;
} mk_tone_mark;

typedef struct mk_valued_diacritic_effect {
    const char *modifier;
    const char *const *alternatives;
    size_t alternative_count;
    char state;
} mk_valued_diacritic_effect;

typedef struct mk_feature_path {
    const char *feature;
    const char *const *path;
    size_t path_count;
} mk_feature_path;

typedef struct mk_scalar_dimension {
    const char *name;
    const char *geometry_node;
    const char *const *positive;
    size_t positive_count;
    const char *const *negative;
    size_t negative_count;
    double weight;
} mk_scalar_dimension;

typedef struct mk_builtin_system {
    const char *name;
    mk_system_type kind;
    const mk_builtin_entry *entries;
    size_t entry_count;
    const mk_feature_node_map *geometry_map;
    size_t geometry_map_count;
    const double *dimension_weights;
    const mk_scalar_dimension *scalar_dimensions;
    size_t scalar_dimension_count;
} mk_builtin_system;

struct mk_system {
    const mk_builtin_system *builtin;
    mk_builtin_system owned;
    int owns;
};

struct mk_registry {
    /* The array may grow, so each system has a stable allocation. */
    mk_system **systems;
    size_t system_count;
};

struct mk_string_list {
    char **items;
    size_t count;
};

struct mk_feature_set {
    char **items;
    size_t count;
};

extern const mk_builtin_system mk_builtin_systems[];
extern const size_t mk_builtin_system_count;
extern const mk_geometry_leaf mk_clements_hume_leaves[];
extern const size_t mk_clements_hume_leaf_count;
extern const mk_ordinal_scale mk_clements_hume_ordinal_scales[];
extern const size_t mk_clements_hume_ordinal_scale_count;
extern const mk_feature_node_map mk_clements_hume_feature_to_node[];
extern const size_t mk_clements_hume_feature_to_node_count;
extern const mk_node_depth mk_clements_hume_node_depths[];
extern const size_t mk_clements_hume_node_depth_count;
extern const mk_node_parent mk_clements_hume_node_parents[];
extern const size_t mk_clements_hume_node_parent_count;
extern const mk_node_weight_preset mk_clements_hume_weight_presets[];
extern const size_t mk_clements_hume_weight_preset_count;
extern const mk_feature_path mk_clements_hume_feature_paths[];
extern const size_t mk_clements_hume_feature_path_count;
extern const mk_diacritic_map mk_default_combining_diacritics[];
extern const size_t mk_default_combining_diacritic_count;
extern const mk_diacritic_map mk_default_suffix_diacritics[];
extern const size_t mk_default_suffix_diacritic_count;
extern const mk_diacritic_map mk_default_prefix_diacritics[];
extern const size_t mk_default_prefix_diacritic_count;
extern const char *const mk_default_metadata_features[];
extern const size_t mk_default_metadata_feature_count;
extern const mk_decomposition mk_default_decompositions[];
extern const size_t mk_default_decomposition_count;
extern const mk_tone_mark mk_default_tone_marks[];
extern const size_t mk_default_tone_mark_count;
extern const mk_valued_diacritic_effect mk_default_valued_diacritic_effects[];
extern const size_t mk_default_valued_diacritic_effect_count;

char *mk_strdup_internal(const char *s);
mk_status mk_string_list_from_borrowed(
    const char *const *items,
    size_t count,
    mk_string_list **out
);
mk_status mk_feature_set_from_borrowed(
    const char *const *items,
    size_t count,
    mk_feature_set **out
);

/* Append to a growable NUL-terminated buffer, doubling capacity as needed.
 * *text may be NULL with *len and *cap zero. Shared because the tokenizer and
 * the resolver both build strings a codepoint at a time. */
mk_status mk_append_text(char **text, size_t *len, size_t *cap, const char *suffix);

/* Byte length of the UTF-8 sequence a lead byte starts; 1 for an invalid
 * lead, so a scan always advances. */
size_t mk_utf8_char_len(unsigned char c);
int mk_has_prefix(const char *s, const char *prefix);

/* The Chao pitch level a digit or tone letter denotes, 0-5, or -1 if it is
 * neither. Shared so the tokenizer, the tone-merge step and the recognizer
 * agree on what counts as tone. */
int mk_chao_level(const char *p);

/* Whether this codepoint is one of the vowel letters the cluster grammar
 * admits and the tone-merge step treats as a nucleus. */
int mk_is_vowel_letter(const char *p);

mk_status mk_normalize_input_grapheme(
    const char *utf8_in,
    char **utf8_out
);
/* Whether the compiled geometry has anywhere to put this feature. A feature it
 * does not know contributes nothing to any distance, so a model built from such
 * features registers successfully and then scores every comparison as zero. */
int mk_geometry_knows_feature(const char *feature);
/* Whether the feature can actually move a distance, as opposed to merely
 * being a declared label. Metadata features are known but never scored. */
int mk_geometry_scores_feature(const char *feature);

/* Non-zero when a feature set holds two values of one ordered scale. */
int mk_ordinal_conflict(
    const char *const *features,
    size_t feature_count,
    const char **scale_out,
    const char **first_out,
    const char **second_out
);

/* The scoring seam. Both scorers compare two feature sets under a named weight
 * preset and report failure through mk_status, like everything else in the
 * library. They used to return the score directly and signal an unknown preset
 * with NAN, a second error channel every caller had to remember to test.
 *
 * `system` supplies the per-system scoring tables: scalar dimensions for the
 * categorical scorer, the geometry map and dimension weights for the valued
 * one. It may be NULL for the categorical scorer, which then scores against the
 * compiled geometry alone — that is the path mk_sound_distance takes.
 *
 * Identity of the two segments is a caller's question, not a scorer's: two
 * spellings of the same segment resolve to the same features and score 0.0
 * through the ordinary path. */
mk_status mk_score_categorical(
    const mk_builtin_system *system,
    mk_feature_view a,
    mk_feature_view b,
    const char *node_weights,
    double *out
);
mk_status mk_score_valued(
    const mk_builtin_system *system,
    mk_feature_view a,
    mk_feature_view b,
    const char *node_weights,
    double *out
);

int mk_streq(const char *a, const char *b);

#endif
