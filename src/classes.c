#include "classes.h"

#include "strings.h"

#include <stdbool.h>

/* These sets are tools/generate_c_data.py's, and must stay equal to them. */

static const char *const mk_sonorant_manners[] = {
    "nasal", "lateral", "approximant", "trill", "tap", "vowel",
};
/* A lateral fricative, affricate or click is an obstruent (`ɬ`, `ɮ`, `tɬ`,
 * `ǁ`): the obstruent manners are tested before the sonorant ones, except that
 * a nasal makes a segment sonorant. */
static const char *const mk_obstruent_manners[] = {
    "stop", "fricative", "affricate", "click", "implosive",
};
static const char *const mk_continuant_manners[] = {
    "fricative", "approximant", "trill", "vowel",
};
static const char *const mk_non_continuant_manners[] = {
    "stop", "affricate", "nasal", "implosive", "click",
};
static const char *const mk_anterior_places[] = {"linguolabial", "dental", "alveolar"};
static const char *const mk_non_anterior_places[] = {
    "post-alveolar", "retroflex", "alveolo-palatal",
};
static const char *const mk_distributed_places[] = {
    "dental", "post-alveolar", "alveolo-palatal", "linguolabial",
};
static const char *const mk_non_distributed_places[] = {"alveolar", "retroflex"};
static const char *const mk_labial_places[] = {
    "bilabial", "labio-dental", "labial", "labio-palatal", "labio-velar",
};
static const char *const mk_coronal_places[] = {
    "linguolabial", "dental", "alveolar", "post-alveolar", "retroflex", "alveolo-palatal",
};
static const char *const mk_dorsal_places[] = {
    "palatal", "palatal-velar", "velar", "uvular", "labio-palatal", "labio-velar",
};
static const char *const mk_guttural_places[] = {"pharyngeal", "epiglottal", "glottal"};
static const char *const mk_glide_places[] = {
    "palatal", "labio-palatal", "labio-velar", "velar",
};
static const char *const mk_non_pulmonic[] = {"click", "nasal-click", "implosive"};

#define MK_COUNT(array) (sizeof(array) / sizeof((array)[0]))

static bool mk_has_any(
    const char *const *features,
    size_t count,
    const char *const *set,
    size_t set_count
)
{
    size_t i;

    for (i = 0; i < set_count; i++) {
        if (mki_features_contain(features, count, set[i])) {
            return true;
        }
    }
    return false;
}

#define MK_HAS(set) mk_has_any(features, count, set, MK_COUNT(set))

static void mk_offer(
    const char *const *features,
    size_t count,
    const char **added,
    size_t *n,
    const char *label
)
{
    if (!mki_features_contain(features, count, label)) {
        added[(*n)++] = label;
    }
}

size_t mki_class_features(const char *const *features, size_t count, const char **added)
{
    size_t n = 0;

    /* The derivation reads the standard vocabulary, whose rows always name
     * their major class. A runtime row written in other labels is left as it
     * is: it would otherwise be given "consonantal" for lacking "vowel". */
    if (!mki_features_contain(features, count, "consonant") &&
        !mki_features_contain(features, count, "vowel")) {
        return 0;
    }

    /* A click's rear closure defines its airstream, and gets its own label
     * rather than "velar", which would compete as a place. */
    if (MK_HAS(mk_non_pulmonic)) {
        mk_offer(features, count, added, &n, "non-pulmonic");
        if (mki_features_contain(features, count, "click") ||
            mki_features_contain(features, count, "nasal-click")) {
            mk_offer(features, count, added, &n, "dorsal-closure");
        }
    }

    if (mki_features_contain(features, count, "vowel") ||
        (mki_features_contain(features, count, "approximant") && MK_HAS(mk_glide_places))) {
        mk_offer(features, count, added, &n, "vocoid");
    } else {
        mk_offer(features, count, added, &n, "consonantal");
    }

    if (MK_HAS(mk_obstruent_manners) && !mki_features_contain(features, count, "nasal")) {
        mk_offer(features, count, added, &n, "obstruent");
    } else if (MK_HAS(mk_sonorant_manners)) {
        mk_offer(features, count, added, &n, "sonorant");
    }

    if (MK_HAS(mk_continuant_manners)) {
        mk_offer(features, count, added, &n, "continuant");
    } else if (MK_HAS(mk_non_continuant_manners)) {
        mk_offer(features, count, added, &n, "non-continuant");
    }

    if (MK_HAS(mk_anterior_places)) {
        mk_offer(features, count, added, &n, "anterior");
    } else if (MK_HAS(mk_non_anterior_places)) {
        mk_offer(features, count, added, &n, "non-anterior");
    }

    if (MK_HAS(mk_distributed_places)) {
        mk_offer(features, count, added, &n, "distributed");
    } else if (MK_HAS(mk_non_distributed_places)) {
        mk_offer(features, count, added, &n, "non-distributed");
    }

    if (MK_HAS(mk_labial_places)) {
        mk_offer(features, count, added, &n, "labial");
    }
    if (MK_HAS(mk_coronal_places)) {
        mk_offer(features, count, added, &n, "coronal");
    }
    if (MK_HAS(mk_dorsal_places)) {
        mk_offer(features, count, added, &n, "dorsal");
    }
    if (MK_HAS(mk_guttural_places)) {
        mk_offer(features, count, added, &n, "guttural");
    }
    return n;
}
