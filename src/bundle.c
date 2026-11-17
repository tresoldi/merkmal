/* Abstract segments: feature bundles with no grapheme as identity.
 *
 * A bundle has one cell per dimension the system's scorer reads -- the same
 * dimensions as the feature vector, except that a node group is one cell here
 * and one-hot columns there. A cell says which values the segment may have:
 * "does not apply" (NA) and any subset of the dimension's values. A cell with
 * exactly one possibility is specified.
 *
 * The point distance is the system's own scorer formula over the dimensions
 * specified on both sides, with the scorer's own skip rules, so a bundle made
 * from a grapheme scores as the grapheme does. The bounds are the extremes of
 * the same ratio over every completion of the unspecified cells. The ratio is
 * a weighted mean of independent per-dimension choices, so both extremes are
 * found exactly by Dinkelbach iteration rather than by enumeration.
 * See docs/abstract-segments.md. */

#include "merkmal.h"

#include "generated/builtin_data.h"
#include "geometry.h"
#include "inventory.h"
#include "resolver.h"
#include "strings.h"
#include "system.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MK_BUNDLE_MAX_GROUP_LABELS 64
#define MK_BUNDLE_MAX_ITERATIONS 200

typedef enum mk_scorer_kind {
    MK_SK_SCALAR,
    MK_SK_LEAF,
    MK_SK_VALUED
} mk_scorer_kind;

typedef enum mk_column_kind {
    MK_COL_BINARY,
    MK_COL_ORDINAL,
    MK_COL_GROUP
} mk_column_kind;

/* Binary values, as bits of a cell's mask. NEUTRAL is the third value the
 * P-base tables write as n, o or x, which the valued scorer reads as 0. */
#define MK_BIN_PLUS 1u
#define MK_BIN_MINUS 2u
#define MK_BIN_NEUTRAL 4u

typedef struct mk_column {
    mk_column_kind kind;
    const char *name;
    const char *node;
    double base_weight;
    double divisor;
    const mk_scalar_dimension *dimension;
    const mk_geometry_leaf *leaf;
    size_t valued_index;
    const mk_ordinal_scale *scale;
    const char *labels[MK_BUNDLE_MAX_GROUP_LABELS];
    size_t label_count;
} mk_column;

/* `na`: "does not apply" is possible. `mask`: the applicable values that are
 * possible (binary bits, ordinal levels, or for a group the labels of one
 * exact label set). `any`: a group may be any non-empty label set. `oneof`: a
 * group's mask lists alternative single labels rather than one set. */
typedef struct mk_cell {
    unsigned char na;
    unsigned char any;
    unsigned char oneof;
    uint64_t mask;
} mk_cell;

struct mk_bundle {
    const mk_system *system;
    mk_scorer_kind scorer;
    mk_column *columns;
    size_t column_count;
    mk_cell *cells;
};

/* -- columns ------------------------------------------------------------------ */

static mk_status mk_scorer_kind_of(const mk_builtin_system *builtin, mk_scorer_kind *out)
{
    if (builtin->kind == MK_SYSTEM_VALUED) {
        *out = MK_SK_VALUED;
    } else if (builtin->kind != MK_SYSTEM_CATEGORICAL) {
        return MK_ERR_UNSUPPORTED_MODEL;
    } else if (builtin->scalar_dimension_count > 0) {
        *out = MK_SK_SCALAR;
    } else {
        *out = MK_SK_LEAF;
    }
    return MK_OK;
}

static size_t mk_count_columns(const mk_builtin_system *builtin, mk_scorer_kind scorer)
{
    size_t n = 0;
    size_t i;
    size_t j;

    if (scorer == MK_SK_VALUED) {
        return builtin->geometry_map_count;
    }
    n = scorer == MK_SK_SCALAR ? builtin->scalar_dimension_count : mki_clements_hume_leaf_count;
    n += mki_clements_hume_ordinal_scale_count;
    if (scorer == MK_SK_LEAF) {
        for (i = 0; i < mki_clements_hume_feature_to_node_count; i++) {
            const mk_feature_node_map *map = &mki_clements_hume_feature_to_node[i];
            int first = 1;

            if (!mki_is_node_group_feature(map->feature)) {
                continue;
            }
            for (j = 0; j < i; j++) {
                if (mki_is_node_group_feature(mki_clements_hume_feature_to_node[j].feature) &&
                    mki_streq(mki_clements_hume_feature_to_node[j].node, map->node)) {
                    first = 0;
                    break;
                }
            }
            n += (size_t)first;
        }
    }
    return n;
}

static mk_column *mk_find_group(mk_column *columns, size_t count, const char *node)
{
    size_t i;

    for (i = 0; i < count; i++) {
        if (columns[i].kind == MK_COL_GROUP && mki_streq(columns[i].node, node)) {
            return &columns[i];
        }
    }
    return NULL;
}

static mk_status mk_build_columns(
    const mk_builtin_system *builtin,
    mk_scorer_kind scorer,
    mk_column **out,
    size_t *count_out
)
{
    size_t width = mk_count_columns(builtin, scorer);
    mk_column *columns = (mk_column *)calloc(width + 1, sizeof(*columns));
    size_t n = 0;
    size_t i;

    if (columns == NULL) {
        return MK_ERR_OOM;
    }
    if (scorer == MK_SK_VALUED) {
        for (i = 0; i < builtin->geometry_map_count; i++) {
            mk_column *c = &columns[n++];

            c->kind = MK_COL_BINARY;
            c->name = builtin->geometry_map[i].feature;
            c->node = builtin->geometry_map[i].node;
            c->base_weight = builtin->dimension_weights != NULL ? builtin->dimension_weights[i] : 0.5;
            c->divisor = 2.0;
            c->valued_index = i;
        }
    } else {
        if (scorer == MK_SK_SCALAR) {
            for (i = 0; i < builtin->scalar_dimension_count; i++) {
                const mk_scalar_dimension *d = &builtin->scalar_dimensions[i];
                mk_column *c = &columns[n++];

                c->kind = MK_COL_BINARY;
                c->name = d->name;
                c->node = d->geometry_node;
                c->base_weight = d->weight;
                c->divisor = d->negative_count == 0 ? 1.0 : 2.0;
                c->dimension = d;
            }
        } else {
            for (i = 0; i < mki_clements_hume_leaf_count; i++) {
                const mk_geometry_leaf *leaf = &mki_clements_hume_leaves[i];
                mk_column *c = &columns[n++];

                c->kind = MK_COL_BINARY;
                c->name = leaf->name;
                c->node = leaf->parent;
                c->base_weight = leaf->weight;
                c->divisor = leaf->negative[0] == '\0' ? 1.0 : 2.0;
                c->leaf = leaf;
            }
        }
        for (i = 0; i < mki_clements_hume_ordinal_scale_count; i++) {
            const mk_ordinal_scale *scale = &mki_clements_hume_ordinal_scales[i];
            mk_column *c = &columns[n++];

            if (scale->level_count > 63) {
                free(columns);
                return MK_ERR_UNSUPPORTED_MODEL;
            }
            c->kind = MK_COL_ORDINAL;
            c->name = scale->name;
            c->node = scale->node;
            c->base_weight = scale->weight;
            c->scale = scale;
        }
        if (scorer == MK_SK_LEAF) {
            for (i = 0; i < mki_clements_hume_feature_to_node_count; i++) {
                const mk_feature_node_map *map = &mki_clements_hume_feature_to_node[i];
                mk_column *c;

                if (!mki_is_node_group_feature(map->feature)) {
                    continue;
                }
                c = mk_find_group(columns, n, map->node);
                if (c == NULL) {
                    c = &columns[n++];
                    c->kind = MK_COL_GROUP;
                    c->name = map->node;
                    c->node = map->node;
                    c->base_weight = 1.0 / mki_node_depth_value(map->node);
                }
                if (c->label_count == MK_BUNDLE_MAX_GROUP_LABELS) {
                    free(columns);
                    return MK_ERR_UNSUPPORTED_MODEL;
                }
                c->labels[c->label_count++] = map->feature;
            }
        }
    }
    /* Column names must address columns. */
    for (i = 0; i < n; i++) {
        size_t j;
        for (j = 0; j < i; j++) {
            if (mki_streq(columns[i].name, columns[j].name)) {
                free(columns);
                return MK_ERR_UNSUPPORTED_MODEL;
            }
        }
    }
    *out = columns;
    *count_out = n;
    return MK_OK;
}

/* -- cells from features ------------------------------------------------------ */

static int mk_view_has(mk_feature_view view, const char *label)
{
    return label != NULL && label[0] != '\0' &&
        mki_features_contain(view.features, view.count, label);
}

static char mk_valued_state(mk_feature_view view, const char *feature)
{
    size_t len = strlen(feature);
    size_t i;

    for (i = 0; i < view.count; i++) {
        const char *item = view.features[i];
        if (strncmp(item, feature, len) == 0 && item[len] == '=') {
            return item[len + 1];
        }
    }
    return '\0';
}

static int mk_any_label(mk_feature_view view, const char *const *labels, size_t count)
{
    size_t i;
    for (i = 0; i < count; i++) {
        if (mk_view_has(view, labels[i])) {
            return 1;
        }
    }
    return 0;
}

static mk_cell mk_cell_na(void)
{
    mk_cell c;
    memset(&c, 0, sizeof(c));
    c.na = 1;
    return c;
}

static mk_cell mk_cell_mask(uint64_t mask)
{
    mk_cell c;
    memset(&c, 0, sizeof(c));
    c.mask = mask;
    return c;
}

static mk_cell mk_cell_from_view(const mk_bundle *b, const mk_column *col, mk_feature_view view)
{
    size_t i;

    if (col->kind == MK_COL_ORDINAL) {
        int level = mki_ordinal_level(view, col->scale);
        return level == MK_ORDINAL_UNDEFINED ? mk_cell_na() : mk_cell_mask((uint64_t)1 << level);
    }
    if (col->kind == MK_COL_GROUP) {
        uint64_t mask = 0;
        for (i = 0; i < col->label_count; i++) {
            if (mk_view_has(view, col->labels[i])) {
                mask |= (uint64_t)1 << i;
            }
        }
        return mask == 0 ? mk_cell_na() : mk_cell_mask(mask);
    }
    if (b->scorer == MK_SK_VALUED) {
        char state = mk_valued_state(view, col->name);
        mk_cell c;
        if (state == '+') {
            return mk_cell_mask(MK_BIN_PLUS);
        }
        if (state == '-') {
            return mk_cell_mask(MK_BIN_MINUS);
        }
        if (state == 'n' || state == 'o' || state == 'x') {
            return mk_cell_mask(MK_BIN_NEUTRAL);
        }
        if (state == '?') {
            c = mk_cell_mask(MK_BIN_PLUS | MK_BIN_MINUS);
            return c;
        }
        return mk_cell_na();
    }
    if (b->scorer == MK_SK_SCALAR) {
        const mk_scalar_dimension *d = col->dimension;
        if (mk_any_label(view, d->positive, d->positive_count)) {
            return mk_cell_mask(MK_BIN_PLUS);
        }
        if (mk_any_label(view, d->negative, d->negative_count)) {
            return mk_cell_mask(MK_BIN_MINUS);
        }
        return mk_cell_na();
    }
    if (mk_view_has(view, col->leaf->positive)) {
        return mk_cell_mask(MK_BIN_PLUS);
    }
    if (mk_view_has(view, col->leaf->negative)) {
        return mk_cell_mask(MK_BIN_MINUS);
    }
    return mk_cell_na();
}

/* -- lifecycle ------------------------------------------------------------------ */

static mk_status mk_bundle_alloc(const mk_system *system, mk_bundle **out)
{
    mk_bundle *b;
    mk_status status;

    if (system == NULL || system->builtin == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;
    b = (mk_bundle *)calloc(1, sizeof(*b));
    if (b == NULL) {
        return MK_ERR_OOM;
    }
    b->system = system;
    status = mk_scorer_kind_of(system->builtin, &b->scorer);
    if (status == MK_OK) {
        status = mk_build_columns(system->builtin, b->scorer, &b->columns, &b->column_count);
    }
    if (status == MK_OK) {
        b->cells = (mk_cell *)calloc(b->column_count + 1, sizeof(*b->cells));
        if (b->cells == NULL) {
            status = MK_ERR_OOM;
        }
    }
    if (status != MK_OK) {
        mk_bundle_free(b);
        return status;
    }
    *out = b;
    return MK_OK;
}

static uint64_t mk_full_mask(const mk_bundle *b, const mk_column *col)
{
    if (col->kind == MK_COL_ORDINAL) {
        return ((uint64_t)1 << col->scale->level_count) - 1;
    }
    if (col->kind == MK_COL_GROUP) {
        return 0;
    }
    (void)b;
    return MK_BIN_PLUS | MK_BIN_MINUS;
}

static mk_cell mk_cell_unknown(const mk_bundle *b, const mk_column *col, int na_possible)
{
    mk_cell c = mk_cell_mask(mk_full_mask(b, col));
    if (col->kind == MK_COL_GROUP) {
        c.any = 1;
    }
    c.na = (unsigned char)(na_possible != 0);
    return c;
}

mk_status mk_bundle_new(const mk_system *system, mk_bundle **out)
{
    mk_status status = mk_bundle_alloc(system, out);
    size_t i;

    if (status != MK_OK) {
        return status;
    }
    for (i = 0; i < (*out)->column_count; i++) {
        (*out)->cells[i] = mk_cell_unknown(*out, &(*out)->columns[i], 1);
    }
    return MK_OK;
}

static int mk_is_tone(mk_feature_view view)
{
    return mki_features_contain(view.features, view.count, "tonal-autosegment");
}

static void mk_fill_from_view(mk_bundle *b, mk_feature_view view)
{
    size_t i;
    for (i = 0; i < b->column_count; i++) {
        b->cells[i] = mk_cell_from_view(b, &b->columns[i], view);
    }
}

mk_status mk_bundle_from_grapheme(const mk_system *system, const char *utf8_grapheme, mk_bundle **out)
{
    mk_resolution resolved;
    mk_status status;

    if (utf8_grapheme == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;
    status = mk_bundle_alloc(system, out);
    if (status != MK_OK) {
        return status;
    }
    status = mki_resolve(system, utf8_grapheme, &resolved);
    if (status != MK_OK) {
        mk_bundle_free(*out);
        *out = NULL;
        return status;
    }
    /* A synthesized cluster has no single feature set, and a tone sits on a
     * tier with no segmental dimensions; neither is a bundle. */
    if (resolved.cluster_component_count > 0 || mk_is_tone(mki_view_of(&resolved))) {
        mki_resolution_clear(&resolved);
        mk_bundle_free(*out);
        *out = NULL;
        return MK_ERR_UNSUPPORTED_MODEL;
    }
    mk_fill_from_view(*out, mki_view_of(&resolved));
    mki_resolution_clear(&resolved);
    return MK_OK;
}

void mk_bundle_free(mk_bundle *bundle)
{
    if (bundle == NULL) {
        return;
    }
    free(bundle->columns);
    free(bundle->cells);
    free(bundle);
}

mk_status mk_bundle_copy(const mk_bundle *bundle, mk_bundle **out)
{
    mk_status status;

    if (bundle == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    status = mk_bundle_alloc(bundle->system, out);
    if (status != MK_OK) {
        return status;
    }
    memcpy((*out)->cells, bundle->cells, bundle->column_count * sizeof(*bundle->cells));
    return MK_OK;
}

mk_status mk_bundle_column_count(const mk_bundle *bundle, size_t *out)
{
    if (bundle == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = bundle->column_count;
    return MK_OK;
}

mk_status mk_bundle_column_name(const mk_bundle *bundle, size_t index, const char **out)
{
    if (bundle == NULL || out == NULL || index >= bundle->column_count) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = bundle->columns[index].name;
    return MK_OK;
}

static const char *mk_binary_value_name(unsigned bit)
{
    return bit == MK_BIN_PLUS ? "+" : (bit == MK_BIN_MINUS ? "-" : "n");
}

mk_status mk_bundle_column_values(const mk_bundle *bundle, const char *column, mk_string_list **out)
{
    const char *names[MK_BUNDLE_MAX_GROUP_LABELS + 4];
    const mk_column *col = NULL;
    size_t n = 0;
    size_t i;

    if (bundle == NULL || column == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    for (i = 0; i < bundle->column_count; i++) {
        if (mki_streq(bundle->columns[i].name, column)) {
            col = &bundle->columns[i];
        }
    }
    if (col == NULL) {
        return MK_ERR_UNKNOWN_FEATURE;
    }
    if (col->kind == MK_COL_ORDINAL) {
        for (i = 0; i < col->scale->level_count; i++) {
            names[n++] = col->scale->levels[i];
        }
    } else if (col->kind == MK_COL_GROUP) {
        for (i = 0; i < col->label_count; i++) {
            names[n++] = col->labels[i];
        }
    } else {
        names[n++] = "+";
        names[n++] = "-";
        if (bundle->scorer == MK_SK_VALUED) {
            names[n++] = "n";
        }
    }
    return mk_string_list_new(names, n, out);
}

/* -- text form ------------------------------------------------------------------ */

static int mk_popcount(uint64_t x)
{
    int n = 0;
    while (x) {
        x &= x - 1;
        n++;
    }
    return n;
}

static int mk_cell_specified(const mk_column *col, const mk_cell *c)
{
    if (c->na) {
        return !c->any && c->mask == 0;
    }
    if (col->kind == MK_COL_GROUP) {
        return !c->any && c->mask != 0 && (!c->oneof || mk_popcount(c->mask) == 1);
    }
    return mk_popcount(c->mask) == 1;
}

static int mk_label_index(const char *const *labels, size_t count, const char *text, size_t len)
{
    size_t i;
    for (i = 0; i < count; i++) {
        if (strlen(labels[i]) == len && strncmp(labels[i], text, len) == 0) {
            return (int)i;
        }
    }
    return -1;
}

/* Parses one cell. Grammar, by column kind:
 *   any column:  0 (does not apply)   ? (unknown, applies)   * (unknown, may not apply)
 *   binary:      + - n, alternatives joined by |
 *   ordinal:     a level, a range lo..hi, alternatives joined by |
 *   group:       a label, alternatives l1|l2 (one of them), or one exact set l1&l2
 * and "|0" adds "may not apply" to anything. */
static mk_status mk_parse_cell(const mk_bundle *b, const mk_column *col, const char *text, mk_cell *out)
{
    mk_cell c;
    const char *p = text;
    int saw_set = 0;
    int saw_alternative = 0;

    memset(&c, 0, sizeof(c));
    if (mki_streq(text, "*")) {
        *out = mk_cell_unknown(b, col, 1);
        return MK_OK;
    }
    if (mki_streq(text, "?")) {
        *out = mk_cell_unknown(b, col, 0);
        return MK_OK;
    }
    while (*p != '\0') {
        const char *end = p;
        size_t len;
        int alt_count = 0;

        while (*end != '\0' && *end != '|') {
            end++;
        }
        len = (size_t)(end - p);
        if (len == 0) {
            return MK_ERR_PARSE;
        }
        alt_count++;
        if (len == 1 && *p == '0') {
            c.na = 1;
        } else if (len == 1 && *p == '?') {
            mk_cell u = mk_cell_unknown(b, col, 0);
            c.mask |= u.mask;
            c.any |= u.any;
        } else if (col->kind == MK_COL_BINARY) {
            if (len == 1 && *p == '+') {
                c.mask |= MK_BIN_PLUS;
            } else if (len == 1 && *p == '-') {
                c.mask |= MK_BIN_MINUS;
            } else if (len == 1 && *p == 'n' && b->scorer == MK_SK_VALUED) {
                c.mask |= MK_BIN_NEUTRAL;
            } else {
                return MK_ERR_PARSE;
            }
        } else if (col->kind == MK_COL_ORDINAL) {
            const char *dots = NULL;
            const char *q;
            for (q = p; q + 1 < end; q++) {
                if (q[0] == '.' && q[1] == '.') {
                    dots = q;
                    break;
                }
            }
            if (dots != NULL) {
                int lo = mk_label_index(col->scale->levels, col->scale->level_count, p, (size_t)(dots - p));
                int hi = mk_label_index(col->scale->levels, col->scale->level_count, dots + 2, (size_t)(end - dots - 2));
                int k;
                if (lo < 0 || hi < 0 || lo > hi) {
                    return MK_ERR_PARSE;
                }
                for (k = lo; k <= hi; k++) {
                    c.mask |= (uint64_t)1 << k;
                }
            } else {
                int k = mk_label_index(col->scale->levels, col->scale->level_count, p, len);
                if (k < 0) {
                    return MK_ERR_PARSE;
                }
                c.mask |= (uint64_t)1 << k;
            }
        } else {
            const char *amp = memchr(p, '&', len);
            if (amp != NULL) {
                /* One exact set: only on its own, besides an optional |0. */
                const char *q = p;
                uint64_t set = 0;
                if (saw_set || saw_alternative || c.any) {
                    return MK_ERR_PARSE;
                }
                while (q < end) {
                    const char *r = memchr(q, '&', (size_t)(end - q));
                    size_t l = (size_t)((r != NULL ? r : end) - q);
                    int k = mk_label_index(col->labels, col->label_count, q, l);
                    if (k < 0) {
                        return MK_ERR_PARSE;
                    }
                    set |= (uint64_t)1 << k;
                    q = r != NULL ? r + 1 : end;
                }
                c.mask = set;
                saw_set = 1;
            } else {
                int k = mk_label_index(col->labels, col->label_count, p, len);
                if (k < 0 || saw_set) {
                    return MK_ERR_PARSE;
                }
                c.mask |= (uint64_t)1 << k;
                saw_alternative++;
            }
        }
        (void)alt_count;
        p = *end == '|' ? end + 1 : end;
        if (*end == '|' && *p == '\0') {
            return MK_ERR_PARSE;
        }
    }
    if (col->kind == MK_COL_GROUP) {
        if (c.any) {
            c.mask = 0;
            c.oneof = 0;
        } else {
            c.oneof = (unsigned char)(saw_alternative > 1);
        }
    }
    if (!c.na && !c.any && c.mask == 0) {
        return MK_ERR_PARSE;
    }
    *out = c;
    return MK_OK;
}

static int mk_column_index(const mk_bundle *b, const char *name, size_t len)
{
    size_t i;
    for (i = 0; i < b->column_count; i++) {
        if (strlen(b->columns[i].name) == len && strncmp(b->columns[i].name, name, len) == 0) {
            return (int)i;
        }
    }
    return -1;
}

mk_status mk_bundle_set(mk_bundle *bundle, const char *column, const char *state)
{
    int index;
    mk_cell cell;
    mk_status status;

    if (bundle == NULL || column == NULL || state == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    index = mk_column_index(bundle, column, strlen(column));
    if (index < 0) {
        return MK_ERR_UNKNOWN_FEATURE;
    }
    status = mk_parse_cell(bundle, &bundle->columns[index], state, &cell);
    if (status != MK_OK) {
        return status;
    }
    bundle->cells[index] = cell;
    return MK_OK;
}

typedef struct mk_text {
    char *data;
    size_t length;
    size_t capacity;
} mk_text;

static int mk_text_add(mk_text *t, const char *s)
{
    size_t len = strlen(s);
    if (t->length + len + 1 > t->capacity) {
        size_t cap = t->capacity == 0 ? 256 : t->capacity;
        char *grown;
        while (t->length + len + 1 > cap) {
            cap *= 2;
        }
        grown = (char *)realloc(t->data, cap);
        if (grown == NULL) {
            return 0;
        }
        t->data = grown;
        t->capacity = cap;
    }
    memcpy(t->data + t->length, s, len + 1);
    t->length += len;
    return 1;
}

static int mk_cell_text(const mk_bundle *b, const mk_column *col, const mk_cell *c, mk_text *t)
{
    int first = 1;
    size_t i;

    if (c->na && (c->any || c->mask == mk_full_mask(b, col)) && (col->kind != MK_COL_GROUP || c->any)) {
        return mk_text_add(t, "*");
    }
    if (c->na && !c->any && c->mask == 0) {
        return mk_text_add(t, "0");
    }
    if (col->kind == MK_COL_GROUP && c->any) {
        first = 0;
        if (!mk_text_add(t, "?")) {
            return 0;
        }
    } else if (col->kind != MK_COL_GROUP && c->mask == mk_full_mask(b, col)) {
        first = 0;
        if (!mk_text_add(t, "?")) {
            return 0;
        }
    } else if (col->kind == MK_COL_BINARY) {
        unsigned bits[3] = {MK_BIN_PLUS, MK_BIN_MINUS, MK_BIN_NEUTRAL};
        for (i = 0; i < 3; i++) {
            if (c->mask & bits[i]) {
                if ((!first && !mk_text_add(t, "|")) || !mk_text_add(t, mk_binary_value_name(bits[i]))) {
                    return 0;
                }
                first = 0;
            }
        }
    } else if (col->kind == MK_COL_ORDINAL) {
        size_t lo = 0;
        while (lo < col->scale->level_count) {
            size_t hi;
            if (!(c->mask & ((uint64_t)1 << lo))) {
                lo++;
                continue;
            }
            hi = lo;
            while (hi + 1 < col->scale->level_count && (c->mask & ((uint64_t)1 << (hi + 1)))) {
                hi++;
            }
            if (!first && !mk_text_add(t, "|")) {
                return 0;
            }
            if (!mk_text_add(t, col->scale->levels[lo])) {
                return 0;
            }
            if (hi > lo && (!mk_text_add(t, "..") || !mk_text_add(t, col->scale->levels[hi]))) {
                return 0;
            }
            first = 0;
            lo = hi + 1;
        }
    } else {
        const char *sep = c->oneof ? "|" : "&";
        for (i = 0; i < col->label_count; i++) {
            if (c->mask & ((uint64_t)1 << i)) {
                if ((!first && !mk_text_add(t, sep)) || !mk_text_add(t, col->labels[i])) {
                    return 0;
                }
                first = 0;
            }
        }
    }
    if (c->na && !mk_text_add(t, "|0")) {
        return 0;
    }
    return 1;
}

mk_status mk_bundle_get(const mk_bundle *bundle, const char *column, char **state_out)
{
    mk_text t = {NULL, 0, 0};
    int index;

    if (bundle == NULL || column == NULL || state_out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *state_out = NULL;
    index = mk_column_index(bundle, column, strlen(column));
    if (index < 0) {
        return MK_ERR_UNKNOWN_FEATURE;
    }
    if (!mk_cell_text(bundle, &bundle->columns[index], &bundle->cells[index], &t)) {
        free(t.data);
        return MK_ERR_OOM;
    }
    *state_out = t.data;
    return MK_OK;
}

mk_status mk_bundle_to_text(const mk_bundle *bundle, char **out)
{
    mk_text t = {NULL, 0, 0};
    size_t i;

    if (bundle == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;
    if (!mk_text_add(&t, "")) {
        return MK_ERR_OOM;
    }
    for (i = 0; i < bundle->column_count; i++) {
        if ((i > 0 && !mk_text_add(&t, ";")) ||
            !mk_text_add(&t, bundle->columns[i].name) ||
            !mk_text_add(&t, "=") ||
            !mk_cell_text(bundle, &bundle->columns[i], &bundle->cells[i], &t)) {
            free(t.data);
            return MK_ERR_OOM;
        }
    }
    *out = t.data;
    return MK_OK;
}

mk_status mk_bundle_from_text(const mk_system *system, const char *text, mk_bundle **out)
{
    mk_status status;
    const char *p;
    mk_bundle *b = NULL;

    if (text == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;
    status = mk_bundle_new(system, &b);
    if (status != MK_OK) {
        return status;
    }
    p = text;
    while (*p != '\0') {
        const char *end = strchr(p, ';');
        const char *eq;
        size_t len;
        int index;
        char *state;

        if (end == NULL) {
            end = p + strlen(p);
        }
        len = (size_t)(end - p);
        eq = memchr(p, '=', len);
        if (eq == NULL || eq == p) {
            mk_bundle_free(b);
            return MK_ERR_PARSE;
        }
        index = mk_column_index(b, p, (size_t)(eq - p));
        if (index < 0) {
            mk_bundle_free(b);
            return MK_ERR_UNKNOWN_FEATURE;
        }
        state = (char *)malloc((size_t)(end - eq));
        if (state == NULL) {
            mk_bundle_free(b);
            return MK_ERR_OOM;
        }
        memcpy(state, eq + 1, (size_t)(end - eq - 1));
        state[end - eq - 1] = '\0';
        status = mk_parse_cell(b, &b->columns[index], state, &b->cells[index]);
        free(state);
        if (status != MK_OK) {
            mk_bundle_free(b);
            return status;
        }
        p = *end == ';' ? end + 1 : end;
    }
    *out = b;
    return MK_OK;
}

/* -- scoring ------------------------------------------------------------------ */

/* One possible outcome of a dimension: its weight in the mean (0 when the
 * scorer skips it) and its difference. */
typedef struct mk_option {
    double weight;
    double diff;
    int counted;
} mk_option;

#define MK_MAX_OPTIONS 128

static double mk_binary_number(unsigned bit)
{
    return bit == MK_BIN_PLUS ? 1.0 : (bit == MK_BIN_MINUS ? -1.0 : 0.0);
}

/* The scorer's contribution for one value on each side. `va`/`vb` are a binary
 * bit or an ordinal level, or -1 for "does not apply". */
static mk_option mk_contribution(
    const mk_bundle *b,
    const mk_column *col,
    const mk_node_weight_preset *preset,
    int va,
    int vb
)
{
    mk_option o = {0.0, 0.0, 0};
    double w = mki_dimension_weight(preset, col->node, col->base_weight);

    if (col->kind == MK_COL_ORDINAL) {
        int steps;
        if (va < 0 || vb < 0 || col->scale->level_count < 2) {
            return o;
        }
        steps = va > vb ? va - vb : vb - va;
        o.counted = 1;
        o.weight = w;
        o.diff = (double)steps / (double)(col->scale->level_count - 1);
        return o;
    }
    if (b->scorer == MK_SK_VALUED) {
        double a;
        double v;
        if (va < 0 || vb < 0) {
            return o;
        }
        a = mk_binary_number((unsigned)va);
        v = mk_binary_number((unsigned)vb);
        if (a == 0.0 && v == 0.0) {
            return o;
        }
        o.counted = 1;
        o.weight = w;
        o.diff = fabs(a - v) / 2.0;
        return o;
    }
    {
        /* Categorical: "does not apply" is the absence of both labels, which
         * the scorer compares as 0 unless both sides are absent. */
        double a = va < 0 ? 0.0 : mk_binary_number((unsigned)va);
        double v = vb < 0 ? 0.0 : mk_binary_number((unsigned)vb);
        if (va < 0 && vb < 0) {
            return o;
        }
        o.counted = 1;
        o.weight = w;
        o.diff = fabs(a - v) / col->divisor;
        return o;
    }
}

static int mk_group_equal_possible(const mk_cell *a, const mk_cell *b)
{
    if (a->any || b->any) {
        return 1;
    }
    if (!a->oneof && !b->oneof) {
        return a->mask == b->mask;
    }
    if (a->oneof && b->oneof) {
        return (a->mask & b->mask) != 0;
    }
    if (a->oneof) {
        return mk_popcount(b->mask) == 1 && (a->mask & b->mask) != 0;
    }
    return mk_popcount(a->mask) == 1 && (a->mask & b->mask) != 0;
}

static int mk_group_single(const mk_cell *c)
{
    return !c->any && (!c->oneof || mk_popcount(c->mask) == 1);
}

static int mk_group_differ_possible(const mk_cell *a, const mk_cell *b)
{
    if (mk_group_single(a) && mk_group_single(b)) {
        return a->mask != b->mask;
    }
    return 1;
}

static int mk_group_applies(const mk_cell *c)
{
    return c->any || c->mask != 0;
}

/* Every outcome the dimension can have over the completions of both cells. */
static size_t mk_options(
    const mk_bundle *b,
    const mk_column *col,
    const mk_cell *ca,
    const mk_cell *cb,
    const mk_node_weight_preset *preset,
    mk_option *out
)
{
    size_t n = 0;

    if (col->kind == MK_COL_GROUP) {
        double w = mki_dimension_weight(preset, col->node, col->base_weight);
        int a_app = mk_group_applies(ca);
        int b_app = mk_group_applies(cb);
        if (ca->na && cb->na) {
            out[n].counted = 0;
            out[n].weight = 0.0;
            out[n++].diff = 0.0;
        }
        if ((ca->na && b_app) || (a_app && cb->na)) {
            out[n].counted = 1;
            out[n].weight = w;
            out[n++].diff = 1.0;
        }
        if (a_app && b_app) {
            if (mk_group_equal_possible(ca, cb)) {
                out[n].counted = 1;
                out[n].weight = w;
                out[n++].diff = 0.0;
            }
            if (mk_group_differ_possible(ca, cb)) {
                out[n].counted = 1;
                out[n].weight = w;
                out[n++].diff = 1.0;
            }
        }
        return n;
    }
    {
        int values_a[66];
        int values_b[66];
        size_t na = 0;
        size_t nb = 0;
        size_t i;
        size_t j;
        size_t limit = col->kind == MK_COL_ORDINAL ? col->scale->level_count : 3;

        if (ca->na) {
            values_a[na++] = -1;
        }
        if (cb->na) {
            values_b[nb++] = -1;
        }
        for (i = 0; i < limit; i++) {
            int v = col->kind == MK_COL_ORDINAL ? (int)i : (int)(1u << i);
            uint64_t bit = col->kind == MK_COL_ORDINAL ? ((uint64_t)1 << i) : (uint64_t)(1u << i);
            if (ca->mask & bit) {
                values_a[na++] = v;
            }
            if (cb->mask & bit) {
                values_b[nb++] = v;
            }
        }
        for (i = 0; i < na; i++) {
            for (j = 0; j < nb && n < MK_MAX_OPTIONS; j++) {
                mk_option o = mk_contribution(b, col, preset, values_a[i], values_b[j]);
                size_t k;
                int seen = 0;
                for (k = 0; k < n; k++) {
                    if (out[k].weight == o.weight && out[k].diff == o.diff && out[k].counted == o.counted) {
                        seen = 1;
                        break;
                    }
                }
                if (!seen) {
                    out[n++] = o;
                }
            }
        }
        return n;
    }
}

/* The extreme of sum(w*d)/sum(w) over one option per dimension. Dinkelbach:
 * for a trial ratio lambda, choose per dimension the option minimising (or
 * maximising) w*(d - lambda); the resulting ratio moves lambda monotonically
 * and stops at the optimum. A selection that compares nothing scores 0, as
 * the scorers do. */
static double mk_extreme(
    const mk_option *options,
    const size_t *offsets,
    const size_t *counts,
    size_t dims,
    int maximise
)
{
    double lambda = 0.0;
    int iteration;
    size_t i;

    {
        double num = 0.0;
        double den = 0.0;
        for (i = 0; i < dims; i++) {
            num += options[offsets[i]].weight * options[offsets[i]].diff;
            den += options[offsets[i]].weight;
        }
        lambda = den > 0.0 ? num / den : 0.0;
    }
    for (iteration = 0; iteration < MK_BUNDLE_MAX_ITERATIONS; iteration++) {
        double num = 0.0;
        double den = 0.0;
        double next;
        for (i = 0; i < dims; i++) {
            size_t k;
            size_t best = offsets[i];
            double best_value = options[best].weight * (options[best].diff - lambda);
            for (k = 1; k < counts[i]; k++) {
                const mk_option *o = &options[offsets[i] + k];
                double value = o->weight * (o->diff - lambda);
                if (maximise ? value > best_value : value < best_value) {
                    best = offsets[i] + k;
                    best_value = value;
                }
            }
            num += options[best].weight * options[best].diff;
            den += options[best].weight;
        }
        next = den > 0.0 ? num / den : 0.0;
        if (fabs(next - lambda) <= 1e-15) {
            return next;
        }
        if (maximise ? next < lambda : next > lambda) {
            return lambda;
        }
        lambda = next;
    }
    return lambda;
}

mk_status mk_bundle_compare(
    const mk_bundle *a,
    const mk_bundle *b,
    const char *node_weights,
    mk_bundle_comparison *out
)
{
    const mk_node_weight_preset *preset = NULL;
    mk_option *options;
    size_t *offsets;
    size_t *counts;
    size_t total = 0;
    size_t compared = 0;
    double num = 0.0;
    double den = 0.0;
    double partial = 0.0;
    size_t i;
    mk_status status;

    if (a == NULL || b == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    if (a->system != b->system) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    memset(out, 0, sizeof(*out));
    status = mki_resolve_weight_preset(node_weights, &preset);
    if (status != MK_OK) {
        return status;
    }
    options = (mk_option *)malloc((a->column_count * MK_MAX_OPTIONS + 1) * sizeof(*options));
    offsets = (size_t *)malloc((a->column_count + 1) * sizeof(*offsets));
    counts = (size_t *)malloc((a->column_count + 1) * sizeof(*counts));
    if (options == NULL || offsets == NULL || counts == NULL) {
        free(options);
        free(offsets);
        free(counts);
        return MK_ERR_OOM;
    }

    for (i = 0; i < a->column_count; i++) {
        const mk_column *col = &a->columns[i];
        const mk_cell *ca = &a->cells[i];
        const mk_cell *cb = &b->cells[i];
        size_t n = mk_options(a, col, ca, cb, preset, options + total);

        offsets[i] = total;
        counts[i] = n;
        if (mk_cell_specified(col, ca) && mk_cell_specified(col, cb)) {
            /* Specified on both sides: exactly one outcome. */
            if (n > 0) {
                num += options[total].weight * options[total].diff;
                den += options[total].weight;
                compared += options[total].counted != 0;
            }
        } else {
            size_t k;
            double w = 0.0;
            for (k = 0; k < n; k++) {
                if (options[total + k].weight > w) {
                    w = options[total + k].weight;
                }
            }
            partial += w;
        }
        total += n;
    }

    out->distance = den > 0.0 ? num / den : 0.0;
    if (a->scorer == MK_SK_VALUED) {
        out->coverage = a->column_count > 0 ? (double)compared / (double)a->column_count : 0.0;
    } else {
        out->coverage = den + partial > 0.0 ? den / (den + partial) : 0.0;
        if (partial == 0.0) {
            out->coverage = den > 0.0 ? 1.0 : 0.0;
        }
    }
    out->why = out->coverage == 0.0 ? MK_CMP_NO_SHARED_DIMENSION : MK_CMP_OK;
    out->minimum = mk_extreme(options, offsets, counts, a->column_count, 0);
    out->maximum = mk_extreme(options, offsets, counts, a->column_count, 1);
    free(options);
    free(offsets);
    free(counts);
    return MK_OK;
}

/* -- compatibility ---------------------------------------------------------------- */

static int mk_cells_intersect(const mk_column *col, const mk_cell *a, const mk_cell *b)
{
    if (a->na && b->na) {
        return 1;
    }
    if (col->kind == MK_COL_GROUP) {
        return mk_group_applies(a) && mk_group_applies(b) && mk_group_equal_possible(a, b);
    }
    return (a->mask & b->mask) != 0;
}

static int mk_bundles_intersect(const mk_bundle *a, const mk_bundle *b)
{
    size_t i;
    for (i = 0; i < a->column_count; i++) {
        if (!mk_cells_intersect(&a->columns[i], &a->cells[i], &b->cells[i])) {
            return 0;
        }
    }
    return 1;
}

mk_status mk_bundle_compatible(const mk_bundle *bundle, const char *utf8_grapheme, bool *out)
{
    mk_bundle *g = NULL;
    mk_status status;

    if (bundle == NULL || utf8_grapheme == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = false;
    status = mk_bundle_from_grapheme(bundle->system, utf8_grapheme, &g);
    if (status != MK_OK) {
        return status;
    }
    *out = mk_bundles_intersect(bundle, g) != 0;
    mk_bundle_free(g);
    return MK_OK;
}

typedef struct mk_ranked {
    const char *grapheme;
    double distance;
} mk_ranked;

static int mk_ranked_cmp(const void *x, const void *y)
{
    const mk_ranked *a = (const mk_ranked *)x;
    const mk_ranked *b = (const mk_ranked *)y;
    if (a->distance < b->distance) {
        return -1;
    }
    if (a->distance > b->distance) {
        return 1;
    }
    return strcmp(a->grapheme, b->grapheme);
}

mk_status mk_bundle_compatible_graphemes(
    const mk_bundle *bundle,
    const char *node_weights,
    mk_string_list **out
)
{
    const mk_builtin_system *builtin;
    const char *scratch[MK_MAX_ENTRY_FEATURES];
    mk_ranked *ranked;
    const char **names;
    size_t n = 0;
    size_t i;
    mk_bundle *row = NULL;
    mk_status status;

    if (bundle == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;
    builtin = bundle->system->builtin;
    ranked = (mk_ranked *)malloc((builtin->entry_count + 1) * sizeof(*ranked));
    names = (const char **)malloc((builtin->entry_count + 1) * sizeof(*names));
    status = mk_bundle_alloc(bundle->system, &row);
    if (ranked == NULL || names == NULL || status != MK_OK) {
        free(ranked);
        free(names);
        mk_bundle_free(row);
        return status != MK_OK ? status : MK_ERR_OOM;
    }
    for (i = 0; i < builtin->entry_count; i++) {
        mk_entry_view entry;
        mk_feature_view view;
        mk_bundle_comparison cmp;

        mki_inventory_row(builtin, i, scratch, &entry);
        view.features = entry.features;
        view.count = entry.feature_count;
        if (mk_is_tone(view)) {
            continue;
        }
        mk_fill_from_view(row, view);
        if (!mk_bundles_intersect(bundle, row)) {
            continue;
        }
        status = mk_bundle_compare(bundle, row, node_weights, &cmp);
        if (status != MK_OK) {
            break;
        }
        ranked[n].grapheme = entry.grapheme;
        ranked[n++].distance = cmp.distance;
    }
    mk_bundle_free(row);
    if (status == MK_OK) {
        qsort(ranked, n, sizeof(*ranked), mk_ranked_cmp);
        for (i = 0; i < n; i++) {
            names[i] = ranked[i].grapheme;
        }
        status = mk_string_list_new(names, n, out);
    }
    free(ranked);
    free(names);
    return status;
}
