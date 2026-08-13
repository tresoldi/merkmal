#ifndef MK_BUILTIN_DATA_H
#define MK_BUILTIN_DATA_H

/* The shape of the compiled-in data, and the tables themselves.
 *
 * Everything here is emitted by tools/generate_c_data.py into builtin_data.c
 * or describes what it emits. A module that reads a table includes this
 * header; a module that does not, does not. These declarations used to sit in
 * a shared internal.h that every translation unit pulled in whole. */

#include "merkmal.h"

#include <stddef.h>

typedef enum mk_system_type {
    MK_SYSTEM_CATEGORICAL = 1,
    MK_SYSTEM_VALUED = 2,
    MK_SYSTEM_TRAINED = 3
} mk_system_type;

/* One inventory row as pointers. This is how a model parsed at runtime holds
 * its rows; a compiled-in inventory uses the interned form below. */
typedef struct mk_builtin_entry {
    const char *grapheme;
    const char *const *features;
    size_t feature_count;
} mk_builtin_entry;

/* The most feature labels one inventory row may carry.
 *
 * Compiled rows store 16-bit feature ids, so handing one out as
 * `const char *const *` needs an array of pointers to write into. The resolver
 * carries that array inside mk_resolution rather than allocating per lookup,
 * which is why this bound exists and why raising it costs stack on every
 * lookup. tools/generate_c_data.py refuses to emit a row that exceeds it; the
 * widest row in the bundled inventories carries 44. */
#define MK_MAX_ENTRY_FEATURES 64

/* The interned string pool. Every distinct grapheme and feature label appears
 * once; the tables hold byte offsets into it.
 *
 * The tables used to hold a `const char *` for each of roughly 260,000 feature
 * slots -- 2.08 MB of pointers, and one relocation each, to name 35 KB of
 * text. Offsets need no relocations, which is what made the WebAssembly
 * payload shrink. */
const char *mk_pool_string(unsigned int offset);
const char *mk_feature_name(unsigned short id);
extern const size_t mk_feature_name_count;

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

/* A system's inventory comes in one of two storages, and `entries` says which.
 *
 * Non-NULL `entries` is a runtime model: rows are mk_builtin_entry, owned by
 * the registry, and the four interned fields are NULL. NULL `entries` is a
 * compiled-in inventory: rows live in entry_graphemes / entry_feature_at /
 * entry_feature_n / feature_ids, all of them offsets and ids into the pool.
 *
 * Read rows through inventory.h rather than reaching into either form. */
typedef struct mk_builtin_system {
    const char *name;
    mk_system_type kind;
    const mk_builtin_entry *entries;
    size_t entry_count;
    const unsigned int *entry_graphemes;
    const unsigned int *entry_feature_at;
    const unsigned char *entry_feature_n;
    const unsigned short *feature_ids;
    const mk_feature_node_map *geometry_map;
    size_t geometry_map_count;
    const double *dimension_weights;
    const mk_scalar_dimension *scalar_dimensions;
    size_t scalar_dimension_count;
} mk_builtin_system;

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

#endif
