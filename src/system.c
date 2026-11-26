#include "resolver.h"

#include "array.h"
#include "cluster.h"
#include "fingerprint.h"

#include "string_list.h"
#include "strings.h"
#include "utf8.h"

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *mk_kind_name(mki_system_type kind)
{
    switch (kind) {
    case MKI_SYSTEM_CATEGORICAL:
        return "categorical";
    case MKI_SYSTEM_VALUED:
        return "valued";
    case MKI_SYSTEM_TRAINED:
        return "trained";
    default:
        return "unknown";
    }
}

mk_status mk_system_name(const mk_system *system, const char **out)
{
    if (system == NULL || system->builtin == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = system->builtin->name;
    return MK_OK;
}

mk_status mk_system_kind(const mk_system *system, const char **out)
{
    if (system == NULL || system->builtin == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = mk_kind_name(system->builtin->kind);
    return MK_OK;
}

mk_status mk_system_semantic_fingerprint(
    const mk_system *system,
    char **payload_out,
    char **digest_out
)
{
    return mki_system_semantic_fingerprint(system, payload_out, digest_out);
}


mk_status mk_system_is_segment(
    const mk_system *system,
    const char *utf8_grapheme,
    bool *out
)
{
    mki_resolution entry;
    mk_status status;

    if (out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = false;
    status = mki_resolve(system, utf8_grapheme, &entry);
    if (status == MK_OK) {
        mki_resolution_clear(&entry);
        *out = true;
        return MK_OK;
    }
    if (status == MK_ERR_UNKNOWN_GRAPHEME) {
        return MK_OK;
    }
    if (status == MK_ERR_PARSE || status == MK_ERR_SOURCE_MARKER) {
        /* Malformed input (an over-long Chao run, say) and source markup
         * (`<?>`, a boundary marker) are both "not a segment". The predicate
         * stays total; callers who want the reason use
         * mk_system_grapheme_features, which reports which it was. */
        return MK_OK;
    }
    return status;
}

mk_status mk_system_grapheme_features(
    const mk_system *system,
    const char *utf8_grapheme,
    mk_string_list **out
)
{
    mki_resolution entry;
    mk_status status;

    if (out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;
    status = mki_resolve(system, utf8_grapheme, &entry);
    if (status != MK_OK) {
        return status;
    }
    status = mki_string_list_from_borrowed(entry.features, entry.feature_count, out);
    mki_resolution_clear(&entry);
    return status;
}

mk_status mk_system_segment_distance(
    const mk_system *system,
    const char *utf8_a,
    const char *utf8_b,
    double *out
)
{
    return mk_system_segment_distance_with_weights(system, utf8_a, utf8_b, NULL, out);
}

bool mki_view_is_tone(mk_feature_view view)
{
    return mki_features_contain(view.features, view.count, "tonal-autosegment") ||
        mki_features_contain(view.features, view.count, "tone=+");
}

/* The score for two resolved segments, with coverage and comparability when
 * asked for. The caller owns and clears both resolutions. */
static mk_status mk_score_resolved(
    const mk_system *system,
    const mki_resolution *a,
    const mki_resolution *b,
    const char *node_weights,
    double *out,
    double *coverage,
    mk_comparability *why
)
{
    mki_scorer scorer;
    mk_status status;

    if (!mki_weight_preset_valid(node_weights)) {
        return MK_ERR_INVALID_ARGUMENT;
    }

    /* Cross-tier before anything else. A tone and a segment share no dimension
     * by construction, so scoring them through the geometry would return a
     * number built entirely from how many features the *other* one has, which
     * is not a statement about tone and sits below the cost at which an aligner
     * stops matching the two. Gold alignments never put them in one column.
     * See docs/guide/c-api.md, Distance with coverage. */
    if (mki_view_is_tone(mki_view_of(a)) != mki_view_is_tone(mki_view_of(b))) {
        *out = mki_clements_hume_cross_tier_cost;
        if (coverage != NULL) {
            *coverage = 0.0;
        }
        if (why != NULL) {
            *why = MK_CMP_CROSS_TIER;
        }
        return MK_OK;
    }

    /* Two tones in a valued system. PHOIBLE lists the tone letters, but each
     * row carries tone=+ and nothing else, so every pair of them was 0.0
     * (`˥` against `˩`): nothing in the table tells one tone from another,
     * which is the reason a valued system refuses a tone mark. A tone against
     * a segment stays cross-tier, above. */
    if (system->builtin->kind == MKI_SYSTEM_VALUED && mki_view_is_tone(mki_view_of(a)) &&
        mki_view_is_tone(mki_view_of(b)) && !mki_streq(a->grapheme, b->grapheme)) {
        return MK_ERR_UNSUPPORTED_MODEL;
    }

    scorer = mki_scorer_for(system->builtin);
    if (scorer == NULL) {
        return MK_ERR_UNSUPPORTED_MODEL;
    }
    if (a->cluster_component_count > 0 || b->cluster_component_count > 0) {
        /* Only a categorical system synthesizes clusters, so this never runs
         * for a valued one. See mk_admits_synthesized_clusters in the resolver. */
        status = mki_cluster_distance(system, a, b, node_weights, out, coverage);
    } else if (coverage == NULL && mki_streq(a->grapheme, b->grapheme)) {
        /* Two spellings of one segment. The scorer would reach 0.0 anyway; this
         * skips the walk over every leaf, group, and scale.
         *
         * Only when no coverage was asked for. A segment compared with itself
         * is not necessarily fully covered: a valued system skips the
         * dimensions the segment leaves unset (PHOIBLE's /p/ has gaps), so
         * answering 1.0 here would be coverage relative to the segment, not the
         * system-relative quantity mk_system_segment_distance_ex documents. */
        *out = 0.0;
        status = MK_OK;
    } else {
        status = scorer(
            system->builtin, mki_view_of(a), mki_view_of(b), node_weights, out, coverage
        );
    }

    /* Same tier, nothing in common. The score is 0.0 and does not mean
     * "identical"; saying which is the whole point of this channel. */
    if (status == MK_OK && why != NULL && coverage != NULL && *coverage == 0.0) {
        *why = MK_CMP_NO_SHARED_DIMENSION;
    }
    return status;
}

static mk_status mk_distance_with_coverage(
    const mk_system *system,
    const char *utf8_a,
    const char *utf8_b,
    const char *node_weights,
    double *out,
    double *coverage,
    mk_comparability *why
)
{
    mki_resolution resolved_a;
    mki_resolution resolved_b;
    mk_status status;

    if (out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = 0.0;
    if (coverage != NULL) {
        *coverage = 0.0;
    }

    status = mki_resolve(system, utf8_a, &resolved_a);
    if (status != MK_OK) {
        return status;
    }
    status = mki_resolve(system, utf8_b, &resolved_b);
    if (status != MK_OK) {
        mki_resolution_clear(&resolved_a);
        return status;
    }

    status = mk_score_resolved(
        system, &resolved_a, &resolved_b, node_weights, out, coverage, why
    );
    mki_resolution_clear(&resolved_a);
    mki_resolution_clear(&resolved_b);
    if (status != MK_OK) {
        *out = 0.0;
        if (coverage != NULL) {
            *coverage = 0.0;
        }
    }
    return status;
}

mk_status mk_system_segment_distance_with_weights(
    const mk_system *system,
    const char *utf8_a,
    const char *utf8_b,
    const char *node_weights,
    double *out
)
{
    return mk_distance_with_coverage(system, utf8_a, utf8_b, node_weights, out, NULL, NULL);
}

mk_status mk_system_segment_distance_ex(
    const mk_system *system,
    const char *utf8_a,
    const char *utf8_b,
    const char *node_weights,
    double *out,
    double *coverage,
    mk_comparability *why
)
{
    if (coverage == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    if (why != NULL) {
        *why = MK_CMP_OK;
    }
    /* Not seeded here: every scorer reports its own coverage, and a value set
     * by this caller would speak for a scorer it never looked inside. */
    return mk_distance_with_coverage(system, utf8_a, utf8_b, node_weights, out, coverage, why);
}

/* The most tokens a single system segment can span. "iau³³" already needs
 * four; nothing in the bundled inventories needs more, and an unbounded span
 * would let longest matching swallow whole words. */
#define MK_SYSTEM_SEGMENT_MAX_SPAN 4

/* Concatenates `span` orthographic tokens starting at `index`. */
static mk_status mk_join_tokens(
    char *const *tokens,
    size_t index,
    size_t span,
    char **out
)
{
    char *joined = NULL;
    size_t joined_len = 0;
    size_t joined_cap = 0;
    size_t i;

    for (i = 0; i < span; i++) {
        mk_status status = mki_append_text(&joined, &joined_len, &joined_cap, tokens[index + i]);
        if (status != MK_OK) {
            free(joined);
            return status;
        }
    }
    *out = joined;
    return MK_OK;
}

/* Whether a token is one code point: a letter with no mark. */
static bool mk_is_bare(const char *token)
{
    return token[0] != '\0' && token[mki_utf8_step(token)] == '\0';
}

/* Whether this system reads `joined` as one segment, for the purpose of
 * merging orthographic tokens.
 *
 * Only when the combined string is explicitly in the inventory or is a known
 * complex segment (affricate, labio-velar, prenasalized stop). Not
 * mk_system_is_segment: it accepts any resolution path, including
 * consonant-cluster synthesis, and so would merge ANY consonant combination
 * (th, ph, st...).
 *
 * A refusal (unknown, malformed, source marker) is a plain no; anything else,
 * such as running out of memory, is returned. */
static mk_status mk_merges_as_one_segment(
    const mk_system *system,
    const char *joined,
    bool *merge
)
{
    mki_resolution res;
    mk_status status = mki_resolve(system, joined, &res);

    *merge = false;
    if (status == MK_OK) {
        /* A segment with diacritics (`tʃʰ`, `kpʷ`) merges when the segment
         * without them would. */
        mki_resolution_path path =
            res.path == MKI_RESOLVED_DIACRITICS ? res.base_path : res.path;

        *merge = path == MKI_RESOLVED_INVENTORY ||
            path == MKI_RESOLVED_TIE_STRIPPED ||
            path == MKI_RESOLVED_AFFRICATE_RETRACTED ||
            path == MKI_RESOLVED_COMPLEX;
        mki_resolution_clear(&res);
        return MK_OK;
    }
    /* A system that cannot read the combination (a valued system offered a
     * tone-bearing vowel) is a refusal too, so the tokenizer stays total. */
    if (status == MK_ERR_UNKNOWN_GRAPHEME ||
        status == MK_ERR_PARSE ||
        status == MK_ERR_SOURCE_MARKER ||
        status == MK_ERR_UNSUPPORTED_MODEL) {
        return MK_OK;
    }
    return status;
}

/* The longest run of tokens at `index`, up to MK_SYSTEM_SEGMENT_MAX_SPAN, that
 * the system reads as one segment, falling back to the single token. Only the
 * last token of a run may carry marks: a mark belongs to the letter it follows,
 * so `tʰ` and `s` are not the affricate `tsʰ`, and `kʰ`, `æ`, `tʰ`, `s` stays
 * four tokens. On MK_OK *segment is an owned string and *span says how many
 * tokens it consumed. */
static mk_status mk_longest_segment_at(
    const mk_system *system,
    char *const *tokens,
    size_t total,
    size_t index,
    char **segment,
    size_t *span
)
{
    size_t try_span = total - index > MK_SYSTEM_SEGMENT_MAX_SPAN ? MK_SYSTEM_SEGMENT_MAX_SPAN : total - index;
    size_t bare = 0;

    *segment = NULL;
    *span = 0;
    while (index + bare < total && mk_is_bare(tokens[index + bare])) {
        bare++;
    }
    if (try_span > bare + 1) {
        try_span = bare + 1;
    }
    for (; try_span >= 1; try_span--) {
        char *joined = NULL;
        bool merge = false;
        mk_status status = mk_join_tokens(tokens, index, try_span, &joined);

        if (status != MK_OK) {
            return status;
        }
        if (joined == NULL) {
            continue;
        }
        if (try_span == 1) {
            *segment = joined;
            *span = 1;
            return MK_OK;
        }
        status = mk_merges_as_one_segment(system, joined, &merge);
        if (status != MK_OK || merge) {
            if (status == MK_OK) {
                *segment = joined;
                *span = try_span;
            } else {
                free(joined);
            }
            return status;
        }
        free(joined);
    }
    /* Unreachable: a span of one always returns above, because
     * mki_append_text allocates even for an empty token. Reported as the
     * allocation failure a NULL `joined` would mean. */
    return MK_ERR_OOM;
}

/* Whether the system reads `token` as a vowel. */
static mk_status mk_is_vowel_token(const mk_system *system, const char *token, bool *vowel)
{
    mki_resolution res;
    mk_status status = mki_resolve(system, token, &res);

    *vowel = false;
    if (status == MK_OK) {
        *vowel = mki_features_contain(res.features, res.feature_count, "vowel");
        mki_resolution_clear(&res);
        return MK_OK;
    }
    return status == MK_ERR_OOM ? status : MK_OK;
}

/* Moves a modifier letter that ends a vowel token to the token after it, when
 * that is how the system reads it. The orthographic tokenizer attaches every
 * modifier letter to the token before it, so `aⁿda` gives `aⁿ`, `d`, `a` and
 * `aʰta` gives `aʰ`, `t`, `a`: a vowel with nasal release and an aspirated
 * vowel. Prenasalization and pre-aspiration are normally medial, so the mark
 * moves to the consonant when the vowel without it, and the mark with the
 * consonant, are both segments of the system. */
static mk_status mk_move_prefix_marks(const mk_system *system, char **tokens, size_t count)
{
    size_t i;

    for (i = 0; i + 1 < count; i++) {
        size_t len = strlen(tokens[i]);
        size_t mark_at = len;
        char *vowel = NULL;
        char *moved = NULL;
        bool is_vowel = false;
        bool next_is_vowel = true;
        bool accepted = false;
        mk_status status;

        /* The start of the token's last code point. */
        while (mark_at > 0) {
            mark_at--;
            if (((unsigned char)tokens[i][mark_at] & 0xC0u) != 0x80u) {
                break;
            }
        }
        if (mark_at == 0 || !mki_is_modifier_letter_or_symbol(tokens[i] + mark_at)) {
            continue;
        }
        vowel = (char *)malloc(mark_at + 1);
        moved = (char *)malloc(len - mark_at + strlen(tokens[i + 1]) + 1);
        if (vowel == NULL || moved == NULL) {
            free(vowel);
            free(moved);
            return MK_ERR_OOM;
        }
        memcpy(vowel, tokens[i], mark_at);
        vowel[mark_at] = '\0';
        memcpy(moved, tokens[i] + mark_at, len - mark_at);
        strcpy(moved + (len - mark_at), tokens[i + 1]);

        status = mk_is_vowel_token(system, vowel, &is_vowel);
        if (status == MK_OK && is_vowel) {
            status = mk_is_vowel_token(system, tokens[i + 1], &next_is_vowel);
        }
        if (status == MK_OK && is_vowel && !next_is_vowel) {
            mki_resolution res;
            mk_status resolved = mki_resolve(system, moved, &res);

            if (resolved == MK_OK) {
                accepted = true;
                mki_resolution_clear(&res);
            } else if (resolved == MK_ERR_OOM) {
                status = resolved;
            }
        }
        if (status != MK_OK || !accepted) {
            free(vowel);
            free(moved);
            if (status != MK_OK) {
                return status;
            }
            continue;
        }
        free(tokens[i]);
        free(tokens[i + 1]);
        tokens[i] = vowel;
        tokens[i + 1] = moved;
    }
    return MK_OK;
}

/* Tokenizes one space-free chunk of the input into `items`. */
static mk_status mk_segment_chunk(
    const mk_system *system,
    const char *chunk,
    char ***items,
    size_t *count,
    size_t *cap
)
{
    mk_string_list *orthographic = NULL;
    char **tokens = NULL;
    size_t total;
    size_t index;
    size_t i;
    mk_status status;

    /* Start from the orthographic tokens so that normalization, tie bars, and
     * boundary marks keep behaving exactly as mk_segment_ipa documents, then
     * re-join runs of them that this system recognizes as one segment. */
    status = mk_segment_ipa(chunk, &orthographic);
    if (status != MK_OK) {
        return status;
    }
    total = mk_string_list_size(orthographic);
    if (total == 0) {
        mk_string_list_free(orthographic);
        return MK_OK;
    }
    tokens = (char **)calloc(total, sizeof(*tokens));
    if (tokens == NULL) {
        mk_string_list_free(orthographic);
        return MK_ERR_OOM;
    }
    for (i = 0; i < total; i++) {
        tokens[i] = mki_strdup_internal(mk_string_list_get(orthographic, i));
        if (tokens[i] == NULL) {
            status = MK_ERR_OOM;
            goto cleanup;
        }
    }
    status = mk_move_prefix_marks(system, tokens, total);
    if (status != MK_OK) {
        goto cleanup;
    }

    index = 0;
    while (index < total) {
        char *segment = NULL;
        size_t span = 0;
        char **next;

        status = mk_longest_segment_at(system, tokens, total, index, &segment, &span);
        if (status != MK_OK) {
            goto cleanup;
        }
        next = (char **)mki_grow_array(*items, cap, *count, 1, sizeof(**items), 8);
        if (next == NULL) {
            free(segment);
            status = MK_ERR_OOM;
            goto cleanup;
        }
        *items = next;
        (*items)[(*count)++] = segment;
        index += span;
    }

cleanup:
    mk_string_list_free(orthographic);
    mki_free_items(tokens, total);
    return status;
}

mk_status mk_system_segment_ipa(
    const mk_system *system,
    const char *utf8_in,
    mk_string_list **out
)
{
    char **items = NULL;
    size_t count = 0;
    size_t cap = 0;
    const char *p;
    mk_status status = MK_OK;

    if (system == NULL || system->builtin == NULL || utf8_in == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;

    /* Each space-separated chunk on its own: a space the caller wrote is a
     * boundary, and merging across it ("t s a" read as `ts`, `a`) would
     * override the segmentation the caller supplied, as in a CLDF Segments
     * column. */
    p = utf8_in;
    while (*p != '\0') {
        size_t len = strcspn(p, " \t\n\r");

        if (len > 0) {
            char *chunk = (char *)malloc(len + 1);

            if (chunk == NULL) {
                status = MK_ERR_OOM;
                goto cleanup;
            }
            memcpy(chunk, p, len);
            chunk[len] = '\0';
            status = mk_segment_chunk(system, chunk, &items, &count, &cap);
            free(chunk);
            if (status != MK_OK) {
                goto cleanup;
            }
        }
        p += len;
        if (*p != '\0') {
            p++;
        }
    }

    /* The tokens are already owned; hand them over rather than copying every
     * one and freeing the original. */
    status = mki_string_list_adopt(items, count, out);
    if (status == MK_OK) {
        items = NULL;
        count = 0;
    }

cleanup:
    mki_free_items(items, count);
    return status;
}
