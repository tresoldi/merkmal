#ifndef MK_CLASSES_H
#define MK_CLASSES_H

/* The class and articulator labels a categorical feature set implies.
 *
 * Inventory names ("voiceless velar stop consonant") never say "obstruent",
 * "consonantal" or "dorsal", and place scales are defined per articulator, so
 * without these labels a manner difference reduces to one mismatch and two
 * segments at different articulators share no place dimension: /b/ and /g/
 * would be at distance zero. The generator adds them to every compiled
 * inventory row (tools/generate_c_data.py, derive_class_features); this is the
 * same derivation for the feature sets built at run time, which are the
 * complex segments the resolver synthesizes and the rows of a runtime model.
 * The python/tests check that the two agree on every compiled row. */

#include <stddef.h>

/* The most labels mki_class_features can return. */
#define MKI_MAX_CLASS_FEATURES 12

/* Writes to `added` the labels that `features` implies and does not already
 * carry, and returns how many. A set naming neither "consonant" nor "vowel"
 * implies nothing. `added` must have room for
 * MKI_MAX_CLASS_FEATURES pointers; the strings are static. */
size_t mki_class_features(const char *const *features, size_t count, const char **added);

#endif
