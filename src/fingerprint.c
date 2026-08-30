/* Canonical, system-level scientific provenance. This module owns the details
 * of serialization and SHA-256 so callers need one small interface rather
 * than rebuilding a partly different identity at every persistence point. */

#include "fingerprint.h"

#include "geometry.h"
#include "inventory.h"
#include "strings.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct mk_sha256 {
    uint32_t state[8];
    uint64_t bit_count;
    unsigned char block[64];
    size_t block_length;
} mk_sha256;

static uint32_t mk_rotr(uint32_t value, unsigned int count)
{
    return (value >> count) | (value << (32u - count));
}

static void mk_sha256_block(mk_sha256 *ctx, const unsigned char *block)
{
    static const uint32_t k[64] = {
        0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u, 0x3956c25bu, 0x59f111f1u,
        0x923f82a4u, 0xab1c5ed5u, 0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u,
        0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u, 0xe49b69c1u, 0xefbe4786u,
        0x0fc19dc6u, 0x240ca1ccu, 0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
        0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u, 0xc6e00bf3u, 0xd5a79147u,
        0x06ca6351u, 0x14292967u, 0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u,
        0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u, 0xa2bfe8a1u, 0xa81a664bu,
        0xc24b8b70u, 0xc76c51a3u, 0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
        0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u, 0x391c0cb3u, 0x4ed8aa4au,
        0x5b9cca4fu, 0x682e6ff3u, 0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u,
        0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u
    };
    uint32_t words[64];
    uint32_t a, b, c, d, e, f, g, h;
    size_t i;

    for (i = 0; i < 16; i++) {
        words[i] = ((uint32_t)block[i * 4] << 24) |
                   ((uint32_t)block[i * 4 + 1] << 16) |
                   ((uint32_t)block[i * 4 + 2] << 8) |
                   (uint32_t)block[i * 4 + 3];
    }
    for (i = 16; i < 64; i++) {
        uint32_t s0 = mk_rotr(words[i - 15], 7) ^ mk_rotr(words[i - 15], 18) ^
                      (words[i - 15] >> 3);
        uint32_t s1 = mk_rotr(words[i - 2], 17) ^ mk_rotr(words[i - 2], 19) ^
                      (words[i - 2] >> 10);
        words[i] = words[i - 16] + s0 + words[i - 7] + s1;
    }
    a = ctx->state[0]; b = ctx->state[1]; c = ctx->state[2]; d = ctx->state[3];
    e = ctx->state[4]; f = ctx->state[5]; g = ctx->state[6]; h = ctx->state[7];
    for (i = 0; i < 64; i++) {
        uint32_t s1 = mk_rotr(e, 6) ^ mk_rotr(e, 11) ^ mk_rotr(e, 25);
        uint32_t choice = (e & f) ^ ((~e) & g);
        uint32_t temp1 = h + s1 + choice + k[i] + words[i];
        uint32_t s0 = mk_rotr(a, 2) ^ mk_rotr(a, 13) ^ mk_rotr(a, 22);
        uint32_t majority = (a & b) ^ (a & c) ^ (b & c);
        uint32_t temp2 = s0 + majority;
        h = g; g = f; f = e; e = d + temp1;
        d = c; c = b; b = a; a = temp1 + temp2;
    }
    ctx->state[0] += a; ctx->state[1] += b; ctx->state[2] += c; ctx->state[3] += d;
    ctx->state[4] += e; ctx->state[5] += f; ctx->state[6] += g; ctx->state[7] += h;
}

static void mk_sha256_init(mk_sha256 *ctx)
{
    static const uint32_t initial[8] = {
        0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au,
        0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u
    };
    memcpy(ctx->state, initial, sizeof(initial));
    ctx->bit_count = 0;
    ctx->block_length = 0;
}

static void mk_sha256_update(mk_sha256 *ctx, const void *data, size_t length)
{
    const unsigned char *bytes = (const unsigned char *)data;
    size_t i;

    for (i = 0; i < length; i++) {
        ctx->block[ctx->block_length++] = bytes[i];
        if (ctx->block_length == sizeof(ctx->block)) {
            mk_sha256_block(ctx, ctx->block);
            ctx->bit_count += 512u;
            ctx->block_length = 0;
        }
    }
}

static void mk_sha256_finish(mk_sha256 *ctx, unsigned char digest[32])
{
    size_t i;
    uint64_t bits = ctx->bit_count + (uint64_t)ctx->block_length * 8u;

    ctx->block[ctx->block_length++] = 0x80u;
    if (ctx->block_length > 56) {
        while (ctx->block_length < 64) {
            ctx->block[ctx->block_length++] = 0;
        }
        mk_sha256_block(ctx, ctx->block);
        ctx->block_length = 0;
    }
    while (ctx->block_length < 56) {
        ctx->block[ctx->block_length++] = 0;
    }
    for (i = 0; i < 8; i++) {
        ctx->block[63 - i] = (unsigned char)(bits >> (i * 8));
    }
    mk_sha256_block(ctx, ctx->block);
    for (i = 0; i < 8; i++) {
        digest[i * 4] = (unsigned char)(ctx->state[i] >> 24);
        digest[i * 4 + 1] = (unsigned char)(ctx->state[i] >> 16);
        digest[i * 4 + 2] = (unsigned char)(ctx->state[i] >> 8);
        digest[i * 4 + 3] = (unsigned char)ctx->state[i];
    }
}

static void mk_sha256_hex(const void *data, size_t length, char out[65])
{
    static const char hex[] = "0123456789abcdef";
    mk_sha256 ctx;
    unsigned char digest[32];
    size_t i;

    mk_sha256_init(&ctx);
    mk_sha256_update(&ctx, data, length);
    mk_sha256_finish(&ctx, digest);
    for (i = 0; i < sizeof(digest); i++) {
        out[i * 2] = hex[digest[i] >> 4];
        out[i * 2 + 1] = hex[digest[i] & 15u];
    }
    out[64] = '\0';
}

static int mk_compare_strings(const void *left, const void *right)
{
    const char *const *a = (const char *const *)left;
    const char *const *b = (const char *const *)right;
    return strcmp(*a, *b);
}

static const char *mk_fingerprint_kind_name(mk_system_type kind)
{
    switch (kind) {
    case MK_SYSTEM_CATEGORICAL: return "categorical";
    case MK_SYSTEM_VALUED: return "valued";
    case MK_SYSTEM_TRAINED: return "trained";
    default: return "unknown";
    }
}

static void mk_hash_text(mk_sha256 *ctx, const char *text)
{
    mk_sha256_update(ctx, text, strlen(text));
}

/* Runtime model text has no durable source file. Hash its semantic inventory:
 * rows and unordered feature sets are sorted, so harmless input reordering
 * cannot change the identity. */
static void mk_runtime_model_sha256(const mk_system *system, char out[65])
{
    mk_sha256 ctx;
    const mk_builtin_system *builtin = system->builtin;
    const char *previous = NULL;
    size_t emitted;

    mk_sha256_init(&ctx);
    mk_hash_text(&ctx, "runtime-model-v1\nname=");
    mk_hash_text(&ctx, builtin->name);
    mk_hash_text(&ctx, "\n");
    for (emitted = 0; emitted < builtin->entry_count; emitted++) {
        const char *next = NULL;
        size_t i;
        for (i = 0; i < builtin->entry_count; i++) {
            const char *candidate = builtin->entries[i].grapheme;
            if (candidate != NULL &&
                (previous == NULL || strcmp(candidate, previous) > 0) &&
                (next == NULL || strcmp(candidate, next) < 0)) {
                next = candidate;
            }
        }
        if (next != NULL) {
            mk_entry_view row = {NULL, NULL, 0};
            const char *features[MK_MAX_ENTRY_FEATURES];
            size_t j;
            for (j = 0; j < builtin->entry_count; j++) {
                if (builtin->entries[j].grapheme != NULL &&
                    strcmp(builtin->entries[j].grapheme, next) == 0) {
                    row.grapheme = builtin->entries[j].grapheme;
                    row.features = (const char *const *)builtin->entries[j].features;
                    row.feature_count = builtin->entries[j].feature_count;
                    break;
                }
            }
            /* `next` comes from the same inventory, so this should be
             * unreachable. Keep the invariant explicit for optimizers and
             * for future changes to the lookup loop. */
            if (row.grapheme == NULL || row.features == NULL) {
                continue;
            }
            memcpy(features, row.features, row.feature_count * sizeof(*features));
            qsort(features, row.feature_count, sizeof(*features), mk_compare_strings);
            mk_hash_text(&ctx, row.grapheme);
            mk_hash_text(&ctx, "\t");
            for (j = 0; j < row.feature_count; j++) {
                mk_hash_text(&ctx, features[j]);
                mk_hash_text(&ctx, j + 1 == row.feature_count ? "\n" : "\t");
            }
            previous = next;
        }
    }
    {
        unsigned char digest[32];
        static const char hex[] = "0123456789abcdef";
        size_t i;
        mk_sha256_finish(&ctx, digest);
        for (i = 0; i < sizeof(digest); i++) {
            out[i * 2] = hex[digest[i] >> 4];
            out[i * 2 + 1] = hex[digest[i] & 15u];
        }
        out[64] = '\0';
    }
}

static mk_status mk_append_pair(char **text, size_t *length, size_t *capacity,
                                const char *key, const char *value)
{
    mk_status status = mki_append_text(text, length, capacity, key);
    if (status == MK_OK) status = mki_append_text(text, length, capacity, "=");
    if (status == MK_OK) status = mki_append_text(text, length, capacity, value);
    if (status == MK_OK) status = mki_append_text(text, length, capacity, "\n");
    return status;
}

mk_status mki_system_semantic_fingerprint(
    const mk_system *system,
    char **payload_out,
    char **digest_out
)
{
    const mk_builtin_system *builtin;
    char runtime_digest[65];
    char payload_digest[65];
    char *payload = NULL;
    char *digest = NULL;
    size_t length = 0;
    size_t capacity = 0;
    const char *model_version;
    const char *model_sha256;
    const char *scorer;
    mk_status status;

    if (system == NULL || system->builtin == NULL ||
        (payload_out == NULL && digest_out == NULL)) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    if (payload_out != NULL) *payload_out = NULL;
    if (digest_out != NULL) *digest_out = NULL;
    builtin = system->builtin;
    scorer = mki_scorer_name(mki_scorer_for(builtin));
    if (system->owns) {
        mk_runtime_model_sha256(system, runtime_digest);
        model_version = "runtime-model-v1";
        model_sha256 = runtime_digest;
    } else {
        model_version = builtin->version;
        model_sha256 = builtin->model_sha256;
    }
    status = mk_append_pair(&payload, &length, &capacity, "schema", "merkmal-system-fingerprint-v1");
    if (status == MK_OK) status = mk_append_pair(&payload, &length, &capacity, "system", builtin->name);
    if (status == MK_OK) status = mk_append_pair(&payload, &length, &capacity, "system_kind", mk_fingerprint_kind_name(builtin->kind));
    if (status == MK_OK) status = mk_append_pair(&payload, &length, &capacity, "model_version", model_version);
    if (status == MK_OK) status = mk_append_pair(&payload, &length, &capacity, "model_sha256", model_sha256);
    if (status == MK_OK) status = mk_append_pair(&payload, &length, &capacity, "scorer", scorer);
    if (status == MK_OK) status = mk_append_pair(&payload, &length, &capacity, "geometry", "merkmal-clements-hume-inspired-v1");
    if (status == MK_OK) status = mk_append_pair(&payload, &length, &capacity, "geometry_sha256", mki_fingerprint_geometry_sha256);
    if (status == MK_OK) status = mk_append_pair(&payload, &length, &capacity, "diacritics_sha256", mki_fingerprint_diacritics_sha256);
    if (status == MK_OK) status = mk_append_pair(&payload, &length, &capacity, "resolver_policy", "ipa-resolver-v1");
    if (status == MK_OK) status = mk_append_pair(&payload, &length, &capacity, "tone_policy", "chao-tone-v1");
    if (status == MK_OK) status = mk_append_pair(&payload, &length, &capacity, "comparison_policy", "segment-distance-v1");
    if (status != MK_OK) {
        free(payload);
        return status;
    }
    mk_sha256_hex(payload, length, payload_digest);
    digest = mki_strdup_internal(payload_digest);
    if (digest == NULL) {
        free(payload);
        return MK_ERR_OOM;
    }
    if (payload_out != NULL) *payload_out = payload;
    else free(payload);
    if (digest_out != NULL) *digest_out = digest;
    else free(digest);
    return MK_OK;
}
