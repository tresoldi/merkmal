/* SHA-256 (FIPS 180-4) of a UTF-8 string, for operation_fingerprint().
 *
 * The C core computes SHA-256 internally, but only merkmal.h may be used from
 * here, and the public API exposes the digest of a system, not a hash
 * function. The Python package hashes its operation payload with hashlib; this
 * is the same function, so that both give the same digest for the same
 * payload (tests/testthat/test-fingerprint.R checks one against the other). */

#define R_NO_REMAP
#include <R.h>
#include <Rinternals.h>
#include <stdint.h>
#include <string.h>

static const uint32_t K[64] = {
    0x428a2f98,
    0x71374491,
    0xb5c0fbcf,
    0xe9b5dba5,
    0x3956c25b,
    0x59f111f1,
    0x923f82a4,
    0xab1c5ed5,
    0xd807aa98,
    0x12835b01,
    0x243185be,
    0x550c7dc3,
    0x72be5d74,
    0x80deb1fe,
    0x9bdc06a7,
    0xc19bf174,
    0xe49b69c1,
    0xefbe4786,
    0x0fc19dc6,
    0x240ca1cc,
    0x2de92c6f,
    0x4a7484aa,
    0x5cb0a9dc,
    0x76f988da,
    0x983e5152,
    0xa831c66d,
    0xb00327c8,
    0xbf597fc7,
    0xc6e00bf3,
    0xd5a79147,
    0x06ca6351,
    0x14292967,
    0x27b70a85,
    0x2e1b2138,
    0x4d2c6dfc,
    0x53380d13,
    0x650a7354,
    0x766a0abb,
    0x81c2c92e,
    0x92722c85,
    0xa2bfe8a1,
    0xa81a664b,
    0xc24b8b70,
    0xc76c51a3,
    0xd192e819,
    0xd6990624,
    0xf40e3585,
    0x106aa070,
    0x19a4c116,
    0x1e376c08,
    0x2748774c,
    0x34b0bcb5,
    0x391c0cb3,
    0x4ed8aa4a,
    0x5b9cca4f,
    0x682e6ff3,
    0x748f82ee,
    0x78a5636f,
    0x84c87814,
    0x8cc70208,
    0x90befffa,
    0xa4506ceb,
    0xbef9a3f7,
    0xc67178f2,
};

#define ROTR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))

static void block(uint32_t h[8], const unsigned char *p)
{
    uint32_t w[64];
    uint32_t a, b, c, d, e, f, g, k;
    for (int i = 0; i < 16; i++) {
        w[i] = (uint32_t)p[4 * i] << 24 | (uint32_t)p[4 * i + 1] << 16 | (uint32_t)p[4 * i + 2] << 8 | p[4 * i + 3];
    }
    for (int i = 16; i < 64; i++) {
        uint32_t s0 = ROTR(w[i - 15], 7) ^ ROTR(w[i - 15], 18) ^ (w[i - 15] >> 3);
        uint32_t s1 = ROTR(w[i - 2], 17) ^ ROTR(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    a = h[0];
    b = h[1];
    c = h[2];
    d = h[3];
    e = h[4];
    f = h[5];
    g = h[6];
    k = h[7];
    for (int i = 0; i < 64; i++) {
        uint32_t t1 = k + (ROTR(e, 6) ^ ROTR(e, 11) ^ ROTR(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i];
        uint32_t t2 = (ROTR(a, 2) ^ ROTR(a, 13) ^ ROTR(a, 22)) + ((a & b) ^ (a & c) ^ (b & c));
        k = g;
        g = f;
        f = e;
        e = d + t1;
        d = c;
        c = b;
        b = a;
        a = t1 + t2;
    }
    h[0] += a;
    h[1] += b;
    h[2] += c;
    h[3] += d;
    h[4] += e;
    h[5] += f;
    h[6] += g;
    h[7] += k;
}

SEXP r_mk_sha256(SEXP x)
{
    uint32_t h[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    unsigned char tail[128];
    const unsigned char *data;
    size_t len, full, rest, tail_len;
    uint64_t bits;
    char hex[65];

    if (!Rf_isString(x) || XLENGTH(x) != 1 || STRING_ELT(x, 0) == NA_STRING) {
        Rf_error("merkmal: sha256 needs a single string");
    }
    data = (const unsigned char *)Rf_translateCharUTF8(STRING_ELT(x, 0));
    len = strlen((const char *)data);
    full = len / 64;
    for (size_t i = 0; i < full; i++) {
        block(h, data + 64 * i);
    }
    rest = len - 64 * full;
    memset(tail, 0, sizeof tail);
    memcpy(tail, data + 64 * full, rest);
    tail[rest] = 0x80;
    tail_len = rest + 1 + 8 <= 64 ? 64 : 128;
    bits = (uint64_t)len * 8;
    for (size_t i = 0; i < 8; i++) {
        tail[tail_len - 1 - i] = (unsigned char)(bits >> (8 * i));
    }
    block(h, tail);
    if (tail_len == 128) {
        block(h, tail + 64);
    }
    for (int i = 0; i < 8; i++) {
        snprintf(hex + 8 * i, 9, "%08x", h[i]);
    }
    return Rf_mkString(hex);
}
