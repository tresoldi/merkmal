/* The built-in NFC and NFD.
 *
 * Two halves. Fixed vectors always run: they pin the cases that matter to
 * merkmal (issue #3's `ỹ`, mark reordering, blocking, Hangul, malformed bytes).
 * When the build found libutf8proc, every code point and a large set of
 * generated mark sequences are also compared against it -- an independent
 * implementation -- provided it carries the same Unicode version as the
 * tables. A different version is a skip, not a failure: the forms of newly
 * assigned characters legitimately differ. */

#include "unicode_norm.h"

#include "generated/unicode_data.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if MK_HAVE_UTF8PROC
#include <utf8proc.h>
#endif

#define MK_SKIP 77

static int failures = 0;

static void check(const char *label, const char *input, int compose, const char *expected)
{
    char *out = NULL;
    mk_status status = compose ? mki_unicode_nfc(input, &out) : mki_unicode_nfd(input, &out);

    if (status != MK_OK || out == NULL || strcmp(out, expected) != 0) {
        fprintf(stderr, "%s %s: got \"%s\", expected \"%s\"\n",
            compose ? "NFC" : "NFD", label, out == NULL ? "(null)" : out, expected);
        failures++;
    }
    free(out);
}

static void fixed_vectors(void)
{
    /* Issue #3: the fallback returned this decomposed. */
    check("y tilde", "g\x79\xcc\x83nh", 1, "g\xe1\xbb\xb9nh");
    check("y tilde", "g\xe1\xbb\xb9nh", 0, "g\x79\xcc\x83nh");
    /* u + diaeresis (230) + diaeresis below (220): reordered, then the 220
     * mark composes first and blocks nothing it should not. */
    check("u marks", "u\xcc\x88\xcc\xa4", 1, "\xe1\xb9\xb3\xcc\x88");
    check("u marks", "u\xcc\x88\xcc\xa4", 0, "u\xcc\xa4\xcc\x88");
    /* a + ring below (220) + acute (230) leaves the acute unattached, since
     * there is no a-with-ring-below precomposed. */
    check("blocked", "a\xcc\xa5\xcc\x81", 1, "\xe1\xb8\x81\xcc\x81");
    /* Composition exclusion: U+0958 stays decomposed under NFC. */
    check("exclusion", "\xe0\xa5\x98", 1, "\xe0\xa4\x95\xe0\xa4\xbc");
    /* Singleton: OHM SIGN normalizes to OMEGA. */
    check("singleton", "\xe2\x84\xa6", 1, "\xce\xa9");
    /* Hangul syllable with a trailing consonant, both ways. */
    check("hangul", "\xea\xb0\x81", 0, "\xe1\x84\x80\xe1\x85\xa1\xe1\x86\xa8");
    check("hangul", "\xe1\x84\x80\xe1\x85\xa1\xe1\x86\xa8", 1, "\xea\xb0\x81");
    /* IPA that must survive untouched. */
    check("ipa", "t\xcd\xa1\xca\x83\xca\xb0", 1, "t\xcd\xa1\xca\x83\xca\xb0");
    /* Malformed bytes pass through and do not swallow what follows. */
    check("malformed", "a\xff\xcc\x81", 1, "a\xff\xcc\x81");
    check("truncated", "e\xcc", 1, "e\xcc");
    check("empty", "", 1, "");
}

#if MK_HAVE_UTF8PROC
static size_t encode(unsigned int cp, char *out)
{
    if (cp < 0x80) {
        out[0] = (char)cp;
        return 1;
    }
    if (cp < 0x800) {
        out[0] = (char)(unsigned char)(0xC0u | (cp >> 6));
        out[1] = (char)(unsigned char)(0x80u | (cp & 0x3Fu));
        return 2;
    }
    if (cp < 0x10000) {
        out[0] = (char)(unsigned char)(0xE0u | (cp >> 12));
        out[1] = (char)(unsigned char)(0x80u | ((cp >> 6) & 0x3Fu));
        out[2] = (char)(unsigned char)(0x80u | (cp & 0x3Fu));
        return 3;
    }
    out[0] = (char)(unsigned char)(0xF0u | (cp >> 18));
    out[1] = (char)(unsigned char)(0x80u | ((cp >> 12) & 0x3Fu));
    out[2] = (char)(unsigned char)(0x80u | ((cp >> 6) & 0x3Fu));
    out[3] = (char)(unsigned char)(0x80u | (cp & 0x3Fu));
    return 4;
}

static int compare(const char *text)
{
    int compose;

    for (compose = 0; compose <= 1; compose++) {
        char *ours = NULL;
        utf8proc_uint8_t *theirs = compose ?
            utf8proc_NFC((const utf8proc_uint8_t *)text) :
            utf8proc_NFD((const utf8proc_uint8_t *)text);
        mk_status status = compose ? mki_unicode_nfc(text, &ours) : mki_unicode_nfd(text, &ours);
        int same = status == MK_OK && theirs != NULL && strcmp(ours, (const char *)theirs) == 0;

        if (!same) {
            size_t i;
            fprintf(stderr, "%s differs from utf8proc on:", compose ? "NFC" : "NFD");
            for (i = 0; text[i] != '\0'; i++) {
                fprintf(stderr, " %02x", (unsigned char)text[i]);
            }
            fprintf(stderr, "\n");
        }
        free(ours);
        free(theirs);
        if (!same) {
            return 0;
        }
    }
    return 1;
}

/* xorshift: deterministic, so a failure reproduces. */
static unsigned int next_random(unsigned int *state)
{
    unsigned int x = *state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *state = x;
    return x;
}

static void against_utf8proc(void)
{
    unsigned int cp;
    unsigned int state = 0x9E3779B9u;
    unsigned int pool[4096];
    size_t pool_count = 0;
    size_t i;
    char text[256];
    int reported = 0;

    for (cp = 1; cp <= 0x10FFFF && reported < 10; cp++) {
        size_t n;
        if (cp >= 0xD800 && cp <= 0xDFFF) {
            continue;
        }
        n = encode(cp, text);
        text[n] = '\0';
        if (!compare(text)) {
            failures++;
            reported++;
        }
    }

    /* Sequences drawn from the characters that make normalization hard: every
     * mark with a combining class, every decomposable letter, Hangul jamo and
     * syllables, and plain letters for them to attach to. */
    for (i = 0; i < mki_unicode_tables.ccc_count && pool_count < 4096; i++) {
        pool[pool_count++] = mki_unicode_tables.ccc_code_points[i];
    }
    for (i = 0; i < mki_unicode_tables.decomposition_count && pool_count < 4096; i += 2) {
        pool[pool_count++] = mki_unicode_tables.decomposition_code_points[i];
    }
    for (cp = 0x1100; cp < 0x1100 + 19 && pool_count < 4096; cp++) {
        pool[pool_count++] = cp;
    }
    for (cp = 0x1161; cp < 0x1161 + 21 && pool_count < 4096; cp++) {
        pool[pool_count++] = cp;
    }
    for (cp = 0x11A8; cp < 0x11A7 + 28 && pool_count < 4096; cp++) {
        pool[pool_count++] = cp;
    }
    for (cp = 'a'; cp <= 'z' && pool_count < 4093; cp++) {
        pool[pool_count++] = cp;
    }
    pool[pool_count++] = 0xAC00;
    pool[pool_count++] = 0xAC01;
    pool[pool_count++] = 0x0259;

    for (i = 0; i < 400000 && reported < 20; i++) {
        size_t length = 1 + next_random(&state) % 8;
        size_t used = 0;
        size_t k;

        for (k = 0; k < length; k++) {
            used += encode(pool[next_random(&state) % pool_count], text + used);
        }
        text[used] = '\0';
        if (!compare(text)) {
            failures++;
            reported++;
        }
    }
}
#endif

int main(void)
{
    fixed_vectors();
#if MK_HAVE_UTF8PROC
    if (strcmp(utf8proc_unicode_version(), mki_unicode_version) != 0) {
        fprintf(stderr,
            "utf8proc carries Unicode %s and the tables %s; skipping the oracle\n",
            utf8proc_unicode_version(), mki_unicode_version);
        return failures == 0 ? MK_SKIP : 1;
    }
    against_utf8proc();
#endif
    if (failures != 0) {
        fprintf(stderr, "%d normalization failure(s)\n", failures);
        return 1;
    }
    return 0;
}
