/* Normalization. See normalize.h for what the two entry points are for. */

#include "normalize.h"

#include "generated/builtin_data.h"
#include "strings.h"
#include "utf8.h"

#include <stdlib.h>
#include <string.h>

#if MK_HAVE_UTF8PROC
#include <utf8proc.h>
#endif

static const char *mk_resolve_slash(const char *s)
{
    const char *last;
    const char *p;

    last = NULL;
    for (p = s; *p != '\0'; p++) {
        if (*p == '/') {
            last = p;
        }
    }
    if (last != NULL && last[1] != '\0') {
        return last + 1;
    }
    return s;
}

static const char *mk_strip_leading_stress(const char *s)
{
    while (mki_has_prefix(s, "ˈ") || mki_has_prefix(s, "ˌ")) {
        s += 2;
    }
    return s;
}

static const mk_decomposition *mk_find_decomposition(const char *p)
{
    size_t i;

    for (i = 0; i < mki_default_decomposition_count; i++) {
        if (mki_has_prefix(p, mki_default_decompositions[i].composed)) {
            return &mki_default_decompositions[i];
        }
    }
    return NULL;
}

/* Source spellings that are not canonical decompositions and so cannot come
 * from the table: the IPA script g, the six affricate ligatures, ASCII stand-ins
 * for the apostrophe and the length mark, and cedilla-c.
 *
 * "ç" is here for a specific reason. The generator emits a decomposition only
 * when every mark of the letter is one the feature system understands, and
 * cedilla is not among them, so "ç" is excluded from the table and needs a hand
 * mapping. Any other precomposed letter carrying an uninterpretable mark is
 * deliberately left composed, and therefore rejected rather than guessed at. */
static const mk_decomposition mk_source_conventions[] = {
    { "ɡ", "g" },
    { "ʣ", "dz" },
    { "ʤ", "dʒ" },
    { "ʥ", "dʑ" },
    { "ʦ", "ts" },
    { "ʧ", "tʃ" },
    { "ʨ", "tɕ" },
    { "ç", "ç" },
    { "’", "ʼ" },
    { "'", "ʼ" },
    { ":", "ː" },
    /* U+01DD TURNED E is a source convention for schwa: CLTS v1.4.1 names it
     * "unrounded mid central vowel", the name this inventory gives U+0259, and
     * no bundled model carries it as a row of its own. A lookalike an author
     * reached for, not a distinct sound.
     *
     * U+026B L WITH MIDDLE TILDE is BIPA's grapheme for the velarized lateral,
     * which CLTS v1.4.1 names exactly what "lˠ" resolves to here. It was added,
     * removed, and added back. The removal was right at the time: PHOIBLE
     * carries `ɫ` as its own inventory row with different feature values, and
     * this table used to be applied before lookup and unconditionally, so the
     * mapping did not add a spelling -- it destroyed a contrast PHOIBLE draws,
     * and the contrast audit caught it as one new zero-distance pair.
     *
     * The resolver now tries the written form against the inventory before
     * applying anything here, so a convention can no longer shadow a grapheme a
     * system actually has. `ɫ` resolves for the categorical systems, which lack
     * it, and stays its own segment in PHOIBLE, which has it. */
    { "ɫ", "lˠ" },
    { "ǝ", "ə" }
};

/* Decompose a token using the compiled table.
 *
 * `source_conventions` also applies the mappings above. Lookup wants them --
 * a source writing "ʧ" means the same segment as one writing "tʃ" -- while the
 * tokenizer must not, because it reports the token as the caller wrote it.
 *
 * Decomposition is driven by the table rather than by utf8proc, so lookup
 * accepts the same graphemes whether or not utf8proc is installed. The table
 * covers only letters whose combining marks the feature system can interpret,
 * so an unsupported source letter is still rejected rather than silently
 * reinterpreted. */
static mk_status mk_decompose(
    const char *utf8_in,
    int source_conventions,
    char **utf8_out
)
{
    const char *p = utf8_in;
    char *tmp = NULL;
    size_t len = 0;
    size_t cap = 0;
    mk_status status;

    *utf8_out = NULL;
    while (*p != '\0') {
        const mk_decomposition *rule = mk_find_decomposition(p);
        size_t i;

        /* Decompose first, so that a precomposed letter and its canonically
         * equivalent sequence resolve identically. Without this, "ǎ" was
         * rejected while the NFD spelling of the same character was accepted,
         * and mk_normalize_grapheme (which returns NFC) turned accepted input
         * into rejected input. */
        if (rule == NULL && source_conventions) {
            for (i = 0; i < sizeof(mk_source_conventions) / sizeof(mk_source_conventions[0]); i++) {
                if (mki_has_prefix(p, mk_source_conventions[i].composed)) {
                    rule = &mk_source_conventions[i];
                    break;
                }
            }
        }
        if (rule != NULL) {
            status = mki_append_text(&tmp, &len, &cap, rule->decomposed);
            p += strlen(rule->composed);
        } else {
            char one[5];
            size_t n = mki_utf8_step(p);
            memcpy(one, p, n);
            one[n] = '\0';
            status = mki_append_text(&tmp, &len, &cap, one);
            p += n;
        }
        if (status != MK_OK) {
            free(tmp);
            return status;
        }
    }

    if (tmp == NULL) {
        tmp = mki_strdup_internal("");
        if (tmp == NULL) {
            return MK_ERR_OOM;
        }
    }
    *utf8_out = tmp;
    return MK_OK;
}

mk_status mki_normalize_input_grapheme(
    const char *utf8_in,
    char **utf8_out
)
{
    if (utf8_in == NULL || utf8_out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *utf8_out = NULL;
    return mk_decompose(
        mk_strip_leading_stress(mk_resolve_slash(utf8_in)),
        1,
        utf8_out
    );
}

mk_status mki_normalize_input_grapheme_literal(
    const char *utf8_in,
    char **utf8_out
)
{
    if (utf8_in == NULL || utf8_out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *utf8_out = NULL;
    return mk_decompose(
        mk_strip_leading_stress(mk_resolve_slash(utf8_in)),
        0,
        utf8_out
    );
}

static const char *mk_compose_known_pair(const char *base, const char *mark)
{
    if (mki_streq(base, "a") && mki_streq(mark, "̃")) {
        return "ã";
    }
    if (mki_streq(base, "e") && mki_streq(mark, "̃")) {
        return "ẽ";
    }
    if (mki_streq(base, "i") && mki_streq(mark, "̃")) {
        return "ĩ";
    }
    if (mki_streq(base, "o") && mki_streq(mark, "̃")) {
        return "õ";
    }
    if (mki_streq(base, "u") && mki_streq(mark, "̃")) {
        return "ũ";
    }
    if (mki_streq(base, "v") && mki_streq(mark, "̃")) {
        return "ṽ";
    }
    if (mki_streq(base, "a") && mki_streq(mark, "̈")) {
        return "ä";
    }
    if (mki_streq(base, "e") && mki_streq(mark, "̈")) {
        return "ë";
    }
    if (mki_streq(base, "i") && mki_streq(mark, "̈")) {
        return "ï";
    }
    if (mki_streq(base, "o") && mki_streq(mark, "̈")) {
        return "ö";
    }
    if (mki_streq(base, "y") && mki_streq(mark, "̈")) {
        return "ÿ";
    }
    if (mki_streq(base, "a") && mki_streq(mark, "̆")) {
        return "ă";
    }
    if (mki_streq(base, "e") && mki_streq(mark, "̆")) {
        return "ĕ";
    }
    if (mki_streq(base, "i") && mki_streq(mark, "̆")) {
        return "ĭ";
    }
    if (mki_streq(base, "o") && mki_streq(mark, "̆")) {
        return "ŏ";
    }
    if (mki_streq(base, "u") && mki_streq(mark, "̆")) {
        return "ŭ";
    }
    if (mki_streq(base, "c") && mki_streq(mark, "̧")) {
        return "ç";
    }
    if (mki_streq(base, "a") && mki_streq(mark, "́")) {
        return "á";
    }
    if (mki_streq(base, "e") && mki_streq(mark, "́")) {
        return "é";
    }
    if (mki_streq(base, "i") && mki_streq(mark, "́")) {
        return "í";
    }
    if (mki_streq(base, "o") && mki_streq(mark, "́")) {
        return "ó";
    }
    if (mki_streq(base, "u") && mki_streq(mark, "́")) {
        return "ú";
    }
    if (mki_streq(base, "a") && mki_streq(mark, "̀")) {
        return "à";
    }
    if (mki_streq(base, "e") && mki_streq(mark, "̀")) {
        return "è";
    }
    if (mki_streq(base, "i") && mki_streq(mark, "̀")) {
        return "ì";
    }
    if (mki_streq(base, "o") && mki_streq(mark, "̀")) {
        return "ò";
    }
    if (mki_streq(base, "u") && mki_streq(mark, "̀")) {
        return "ù";
    }
    if (mki_streq(base, "a") && mki_streq(mark, "̂")) {
        return "â";
    }
    if (mki_streq(base, "e") && mki_streq(mark, "̂")) {
        return "ê";
    }
    if (mki_streq(base, "i") && mki_streq(mark, "̂")) {
        return "î";
    }
    if (mki_streq(base, "o") && mki_streq(mark, "̂")) {
        return "ô";
    }
    if (mki_streq(base, "u") && mki_streq(mark, "̂")) {
        return "û";
    }
    if (mki_streq(base, "u") && mki_streq(mark, "̈")) {
        return "ü";
    }
    if (mki_streq(base, "u") && mki_streq(mark, "̤")) {
        return "ṳ";
    }
    if (mki_streq(base, "i") && mki_streq(mark, "̰")) {
        return "ḭ";
    }
    if (mki_streq(base, "u") && mki_streq(mark, "̰")) {
        return "ṵ";
    }
    if (mki_streq(base, "a") && mki_streq(mark, "̄")) {
        return "ā";
    }
    if (mki_streq(base, "e") && mki_streq(mark, "̄")) {
        return "ē";
    }
    if (mki_streq(base, "i") && mki_streq(mark, "̄")) {
        return "ī";
    }
    if (mki_streq(base, "o") && mki_streq(mark, "̄")) {
        return "ō";
    }
    if (mki_streq(base, "u") && mki_streq(mark, "̄")) {
        return "ū";
    }
    return NULL;
}

mk_status mk_normalize_grapheme(
    const char *utf8_in,
    char **utf8_out
)
{
    const char *p;
    char *tmp;
    char *out;
    size_t len;
    size_t cap;
    mk_status status;

    if (utf8_in == NULL || utf8_out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *utf8_out = NULL;

    status = mki_normalize_input_grapheme(utf8_in, &tmp);
    if (status != MK_OK) {
        return status;
    }

    out = NULL;
    len = 0;
    cap = 0;
    p = tmp;
    while (*p != '\0') {
        size_t base_len = mki_utf8_step(p);
        if (p[base_len] != '\0') {
            char base[5];
            char mark[5];
            size_t mark_len = mki_utf8_step(p + base_len);
            const char *composed;

            memcpy(base, p, base_len);
            base[base_len] = '\0';
            memcpy(mark, p + base_len, mark_len);
            mark[mark_len] = '\0';
            composed = mk_compose_known_pair(base, mark);
            if (composed != NULL) {
                status = mki_append_text(&out, &len, &cap, composed);
                p += base_len + mark_len;
            } else if (*p == 'g') {
                status = mki_append_text(&out, &len, &cap, "ɡ");
                p++;
            } else {
                char one[5];
                size_t n = mki_utf8_step(p);
                memcpy(one, p, n);
                one[n] = '\0';
                status = mki_append_text(&out, &len, &cap, one);
                p += n;
            }
        } else if (*p == 'g') {
            status = mki_append_text(&out, &len, &cap, "ɡ");
            p++;
        } else {
            char one[5];
            memcpy(one, p, base_len);
            one[base_len] = '\0';
            status = mki_append_text(&out, &len, &cap, one);
            p += base_len;
        }
        if (status != MK_OK) {
            free(tmp);
            free(out);
            return status;
        }
    }
    free(tmp);

    if (out == NULL) {
        out = mki_strdup_internal("");
        if (out == NULL) {
            return MK_ERR_OOM;
        }
    }

#if MK_HAVE_UTF8PROC
    {
        utf8proc_uint8_t *nfc = utf8proc_NFC((const utf8proc_uint8_t *)out);
        free(out);
        if (nfc == NULL) {
            return MK_ERR_OOM;
        }
        out = (char *)nfc;
    }
#endif

    *utf8_out = out;
    return MK_OK;
}

mk_status mki_segmentation_nfd(
    const char *utf8_in,
    char **utf8_out
)
{
    char *tmp = NULL;
    mk_status status;

    if (utf8_in == NULL || utf8_out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *utf8_out = NULL;

    /* The same table lookup uses, so the tokenizer and the recognizer agree on
     * which precomposed letters decompose. This used to be a separate
     * hand-written list of twenty-one letters against the table's 386, which
     * only mattered when utf8proc was absent -- exactly the build that has no
     * second chance to get it right. The source conventions are not applied
     * here: a token is reported as the caller wrote it. */
    status = mk_decompose(utf8_in, 0, &tmp);
    if (status != MK_OK) {
        return status;
    }

#if MK_HAVE_UTF8PROC
    {
        utf8proc_uint8_t *normalized = utf8proc_NFD((const utf8proc_uint8_t *)tmp);
        free(tmp);
        if (normalized == NULL) {
            return MK_ERR_OOM;
        }
        tmp = (char *)normalized;
    }
#endif

    if (tmp == NULL) {
        tmp = mki_strdup_internal("");
        if (tmp == NULL) {
            return MK_ERR_OOM;
        }
    }
    *utf8_out = tmp;
    return MK_OK;
}
