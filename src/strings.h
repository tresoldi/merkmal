#ifndef MK_STRINGS_H
#define MK_STRINGS_H

/* Small string helpers shared across modules. Nothing here knows about
 * phonology, Unicode, or the data tables. */

#include "merkmal.h"

#include <stddef.h>

/* An owned copy, or NULL on allocation failure. NULL in, NULL out. */
char *mki_strdup_internal(const char *s);

/* String equality. A NULL on either side is unequal to everything, including
 * to another NULL -- callers use this on table fields that are never NULL, and
 * treating two absent values as equal would make an absent grapheme match an
 * absent one. */
int mki_streq(const char *a, const char *b);

int mki_has_prefix(const char *s, const char *prefix);

/* Whether a feature set holds a label. Takes the array and its count rather
 * than an mk_feature_view, so the resolver -- which builds feature arrays
 * before any view exists -- and everything holding a view can share one body:
 * a view caller passes `view.features, view.count`.
 *
 * A NULL or empty needle is in nothing. The geometry's leaves carry "" for a
 * feature with no negative pole, and testing for it would match nothing while
 * looking like it might. */
int mki_features_contain(const char *const *items, size_t count, const char *feature);

/* Append to a growable NUL-terminated buffer, doubling capacity as needed.
 * *text may be NULL with *len and *cap zero. Shared because the tokenizer and
 * the resolver both build strings a codepoint at a time. */
mk_status mki_append_text(char **text, size_t *len, size_t *cap, const char *suffix);

/* Frees `count` owned strings and the array holding them. Tolerates NULL. */
void mki_free_items(char **items, size_t count);

#endif
