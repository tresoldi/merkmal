#ifndef MK_BUILTIN_DATA_H
#define MK_BUILTIN_DATA_H

/* The shape of the compiled-in data, and the tables themselves.
 *
 * Everything here is emitted by tools/generate_c_data.py into builtin_data.c
 * or describes what it emits. This header is written by hand: the generator
 * reads its struct fields and MKI_MAX_ENTRY_FEATURES rather than restating
 * them. A module that reads a table includes this header; a module that does
 * not, does not. */

#include "merkmal.h"

#include <stddef.h>

typedef enum mki_system_type {
    MKI_SYSTEM_CATEGORICAL = 1,
    MKI_SYSTEM_VALUED = 2,
    MKI_SYSTEM_TRAINED = 3
} mki_system_type;

/* One inventory row as pointers, and the storage that backs it.
 *
 * Only a model parsed at runtime ever holds rows this way; every compiled-in
 * inventory sets `entries` to NULL and uses the interned form below. So every
 * pointer here is heap storage owned by whatever holds the row -- the parsed
 * model, then the mk_system that adopts it -- and the types are not const, so
 * the destructors free them without casts.
 *
 * Readers do not touch this type. They go through mki_entry_view in
 * inventory.h, which is const because a reader really is only borrowing. */
typedef struct mki_builtin_entry {
    char *grapheme;
    char **features;
    size_t feature_count;
} mki_builtin_entry;

/* The most feature labels one compiled inventory row may carry.
 *
 * Compiled rows store 16-bit feature ids, so handing one out as
 * `const char *const *` needs an array of pointers to write into. The resolver
 * carries that array inside mki_resolution rather than allocating per lookup,
 * which is why this bound exists and why raising it costs stack on every
 * lookup. tools/generate_c_data.py reads this value and refuses to emit a row
 * that exceeds it. Runtime model rows are not checked against it. */
#define MKI_MAX_ENTRY_FEATURES 64

/* The interned string pool. Every distinct grapheme and feature label appears
 * once, NUL-terminated; the tables hold offsets into it, and rows hold 16-bit
 * feature ids that mki_feature_name maps to offsets. Offsets rather than
 * `const char *` because a pointer per feature slot costs a relocation each,
 * and offsets need none.
 *
 * The pool is cut into 2048-byte chunks, since C99 only guarantees string
 * literals of 4095 characters, and no string straddles a chunk:
 *
 *   offset = chunk index << 11 | byte within the chunk
 *
 * The returned strings are static storage. */
const char *mki_pool_string(unsigned int offset);
const char *mki_feature_name(unsigned short id);
extern const size_t mki_feature_name_count;

/* `weight` is what the dimension costs, already resolved: the leaf's explicit
 * "weight" in the geometry file, else 1/depth. Not a depth for the runtime to
 * invert: an explicit weight would then have to be emitted as a fictitious
 * depth, and nothing on the C side could tell the two apart. */
typedef struct mki_geometry_leaf {
    const char *name;
    const char *positive;
    const char *negative;
    double weight;
    const char *parent;
} mki_geometry_leaf;

/* An ordered scale, for properties where the difference between two values is a
 * quantity rather than a mismatch. Vowel height, Chao tone level, and duration
 * are all like this: /i/ is further from /a/ than from /e/, and half-long sits
 * between short and long.
 *
 * Encoding these as independent privative flags loses that. It would make /i/
 * score further from /e/ than from /a/, make a half-long vowel further from a
 * long one than a plain vowel is, and make the Chao code non-monotonic in the
 * digit.
 *
 * Cost is |level_a - level_b| / (level_count - 1) * weight, so one step on a
 * seven-point height scale costs a sixth of the full range.
 *
 * default_level is the value a segment takes when it carries no label from the
 * scale: 0-based index for scales with an unmarked default (a plain vowel is
 * short), or MKI_ORDINAL_UNDEFINED where absence means the property does not
 * apply (a consonant has no vowel height, a toneless segment no tone level).
 * An undefined scale is skipped for that pair, exactly as the leaf loop skips a
 * feature neither segment carries. */
#define MKI_ORDINAL_UNDEFINED (-1)

typedef struct mki_ordinal_scale {
    const char *name;
    const char *node;
    const char *const *levels;
    size_t level_count;
    int default_level;
    double weight;
} mki_ordinal_scale;

typedef struct mki_feature_node_map {
    const char *feature;
    const char *node;
} mki_feature_node_map;

typedef struct mki_node_depth {
    const char *node;
    double depth;
} mki_node_depth;

typedef struct mki_node_parent {
    const char *node;
    const char *parent;
} mki_node_parent;

typedef struct mki_node_weight {
    const char *node;
    double weight;
} mki_node_weight;

typedef struct mki_node_weight_preset {
    const char *name;
    const mki_node_weight *weights;
    size_t weight_count;
    int flat;
} mki_node_weight_preset;

typedef struct mki_diacritic_map {
    const char *mark;
    const char *feature;
} mki_diacritic_map;

/* A precomposed letter and its canonical decomposition, restricted to letters
 * whose every mark the feature system understands. A letter carrying any other
 * mark stays composed, and is rejected rather than read as a base plus a mark
 * the system would misread. */
typedef struct mki_decomposition {
    const char *composed;
    const char *decomposed;
} mki_decomposition;

/* The coronal class features a place implies, as the generator derives them
 * for inventory rows. Runtime synthesis uses it when a place diacritic moves a
 * segment to another place. */
typedef struct mki_place_class {
    const char *place;
    const char *anterior;
    const char *distributed;
} mki_place_class;

typedef struct mki_tone_mark {
    const char *mark;
    const char *const *features;
    size_t feature_count;
} mki_tone_mark;

typedef struct mki_valued_diacritic_effect {
    const char *modifier;
    const char *const *alternatives;
    size_t alternative_count;
    char state;
} mki_valued_diacritic_effect;

typedef struct mki_feature_path {
    const char *feature;
    const char *const *path;
    size_t path_count;
} mki_feature_path;

typedef struct mki_scalar_dimension {
    const char *name;
    const char *geometry_node;
    const char *const *positive;
    size_t positive_count;
    const char *const *negative;
    size_t negative_count;
    double weight;
} mki_scalar_dimension;

/* A system's inventory comes in one of two storages, and `entries` says which.
 *
 * Non-NULL `entries` is a runtime model: rows are mki_builtin_entry, owned by
 * the mk_system holding this struct (and so by its registry), and the four
 * interned fields are NULL. NULL `entries` is a compiled-in inventory: row i
 * is grapheme entry_graphemes[i] (a pool offset) and the entry_feature_n[i]
 * feature ids starting at feature_ids[entry_feature_at[i]].
 *
 * `entries` is the one unqualified pointer here because it is the one that is
 * never rodata. The rest point into compiled tables, or are NULL for a runtime
 * model, and `name` points at a literal for a compiled system and at
 * mk_system's owned_name for a runtime one -- borrowed either way, so it stays
 * const.
 *
 * Read rows through inventory.h rather than reaching into either form. */
typedef struct mki_builtin_system {
    const char *name;
    const char *version;
    const char *model_sha256;
    mki_system_type kind;
    mki_builtin_entry *entries;
    size_t entry_count;
    const unsigned int *entry_graphemes;
    const unsigned int *entry_feature_at;
    const unsigned char *entry_feature_n;
    const unsigned short *feature_ids;
    const mki_feature_node_map *geometry_map;
    size_t geometry_map_count;
    const double *dimension_weights;
    const mki_scalar_dimension *scalar_dimensions;
    size_t scalar_dimension_count;
} mki_builtin_system;

/* Which data profile this build carries: "full", or "cc-by" for the build
 * restricted to tables without share-alike or non-commercial terms. */
extern const char *const mki_data_profile;

extern const mki_builtin_system mki_builtin_systems[];
extern const size_t mki_builtin_system_count;
/* Hashes of the data inputs shared by every built-in fingerprint. */
extern const char *const mki_fingerprint_geometry_sha256;
extern const char *const mki_fingerprint_diacritics_sha256;
extern const mki_geometry_leaf mki_clements_hume_leaves[];
extern const size_t mki_clements_hume_leaf_count;
/* What a tone costs against a segment. Declared in the geometry file; see
 * `tier_policy` there for why it is 1.0 and what the alternatives cost. */
extern const double mki_clements_hume_cross_tier_cost;
/* How a segment written as more than one part composes. Declared in the
 * geometry file; see `cluster_policy` there for what each share does and why
 * these are data. The rules applying them are in src/cluster.c. */
extern const double mki_clements_hume_cluster_nucleus_share;
extern const double mki_clements_hume_cluster_offglide_share;
extern const double mki_clements_hume_cluster_length_penalty;
extern const double mki_clements_hume_cluster_component_share;
extern const double mki_clements_hume_cluster_segment_share;
extern const mki_ordinal_scale mki_clements_hume_ordinal_scales[];
extern const size_t mki_clements_hume_ordinal_scale_count;
extern const mki_feature_node_map mki_clements_hume_feature_to_node[];
extern const size_t mki_clements_hume_feature_to_node_count;
extern const mki_node_depth mki_clements_hume_node_depths[];
extern const size_t mki_clements_hume_node_depth_count;
extern const mki_node_parent mki_clements_hume_node_parents[];
extern const size_t mki_clements_hume_node_parent_count;
extern const mki_node_weight_preset mki_clements_hume_weight_presets[];
extern const size_t mki_clements_hume_weight_preset_count;
extern const mki_feature_path mki_clements_hume_feature_paths[];
extern const size_t mki_clements_hume_feature_path_count;
extern const mki_diacritic_map mki_default_combining_diacritics[];
extern const size_t mki_default_combining_diacritic_count;
extern const mki_diacritic_map mki_default_suffix_diacritics[];
extern const size_t mki_default_suffix_diacritic_count;
extern const mki_diacritic_map mki_default_prefix_diacritics[];
extern const size_t mki_default_prefix_diacritic_count;
extern const mki_place_class mki_default_place_classes[];
extern const size_t mki_default_place_class_count;
extern const char *const mki_default_metadata_features[];
extern const size_t mki_default_metadata_feature_count;
extern const mki_decomposition mki_default_decompositions[];
extern const size_t mki_default_decomposition_count;
extern const mki_tone_mark mki_default_tone_marks[];
extern const size_t mki_default_tone_mark_count;
extern const mki_valued_diacritic_effect mki_default_valued_diacritic_effects[];
extern const size_t mki_default_valued_diacritic_effect_count;

#endif
