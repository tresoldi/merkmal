#' ---
#' title: "Phonological Distance for Historical Linguistics"
#' ---
#'
#' # Phonological Distance for Historical Linguistics
#'
#' Cognate detection and sound correspondence discovery both need
#' a notion of "how different are these two sounds?"
#'
#' This tutorial uses merkmal to compute segment distances and
#' connect them to operations that come up in historical
#' linguistics work.
#'

import merkmal
from statistics import mean

#'
#' ## Segment distance
#'
#' Given two IPA segments, compute their distance.  Normalised to
#' [0, 1]: 0 = identical, 1 = maximally different.
#'

pairs = [
    ("p", "p", "identical"),
    ("p", "b", "voicing"),
    ("p", "f", "manner (Grimm)"),
    ("p", "k", "place"),
    ("p", "m", "manner + nasality"),
    ("i", "u", "backness + rounding"),
    ("a", "ə", "height + backness"),
]

for a, b, label in pairs:
    d = merkmal.distance(a, b, system="distinctive")
    print(f"  d({a}, {b}) = {d:.3f}   ({label})")

#'
#' Single-feature changes (voicing, manner) produce small distances;
#' multi-feature changes (manner + nasality) produce larger ones.
#' Identical segments are zero.
#'
#' ## Grimm's Law: a case study
#'
#' Grimm's Law describes the systematic consonant shift from
#' Proto-Indo-European to Proto-Germanic:
#' \*p → f, \*t → θ, \*k → x (voiceless stops → voiceless fricatives).
#'
#' ### Distances
#'

grimm_pairs = [("p", "f"), ("t", "θ"), ("k", "x")]
control_pairs = [("p", "k"), ("p", "m"), ("b", "p")]

print("Grimm's Law pairs:")
for a, b in grimm_pairs:
    d = merkmal.distance(a, b, system="distinctive")
    print(f"  {a} → {b}:  d = {d:.3f}")

print("\nControl pairs:")
for a, b in control_pairs:
    d = merkmal.distance(a, b, system="distinctive")
    print(f"  {a} → {b}:  d = {d:.3f}")

#'
#' The Grimm pairs all have similar low distances (0.21 to 0.22),
#' consistent with a single-feature manner change. The control pair
#' p/m (0.618) is much larger because it involves both manner and
#' nasality changes.
#'
#' ### Feature-level characterisation
#'
#' We can also inspect *what* changed.  Comparing the feature sets
#' of each pair gives a feature-level characterisation of the
#' sound change:
#'

print("Feature-level analysis of Grimm's Law:\n")
for a, b in grimm_pairs:
    feats_a = merkmal.get_features(a)
    feats_b = merkmal.get_features(b)
    lost = feats_a - feats_b
    gained = feats_b - feats_a
    shared = feats_a & feats_b
    print(f"  {a} → {b}:")
    print(f"    lost:   {sorted(lost)}")
    print(f"    gained: {sorted(gained)}")
    print(f"    shared: {sorted(shared)}")
    print()

#'
#' All three Grimm pairs lose `stop` and gain `fricative`, the
#' defining feature of the shift. The p→f pair also shows
#' a place shift (bilabial → labio-dental), which is a secondary
#' effect of the manner change.
#'
#' Sound change inference systems build on exactly this sort of
#' structured decomposition.
#'
#' ### Where in the feature tree?
#'
#' The geometry tree tells us *where* in the phonological hierarchy
#' the change occurs:
#'

tree = merkmal.DEFAULT_GEOMETRY

# The geometry uses scalar feature names (e.g. "continuant"),
# not descriptive labels (e.g. "stop"). We can look up which node
# each geometry feature belongs to:
for feat in ["voiced", "voiceless", "aspirated", "nasal", "rounded"]:
    parent = tree.find_parent(feat)
    if parent:
        print(f"  {feat:15s} → node: {parent.name}")

#'
#' So voicing changes are located in the Laryngeal node, while
#' manner features like nasality sit under Manner, and rounding
#' under Labial (a child of Place).
#' Grimm's Law, a manner change, is located in the Manner subtree,
#' which the geometry tree treats as a sibling of Laryngeal and Place.
#' This vocabulary lets you classify sound changes by their locus
#' in the feature hierarchy.
#'
#' ## Comparing systems for cognate detection
#'
#' Different feature systems produce different distance profiles.
#' For historical linguistics, what matters is which distances
#' best predict cognacy.
#'

print("System comparison for Grimm's Law pairs:\n")
print(f"  {'pair':8s}", end="")
for sys in ["descriptive", "distinctive", "classfeat"]:
    print(f" {sys:>12s}", end="")
print()
print("  " + "-" * 44)

for a, b in grimm_pairs + [("p", "k"), ("p", "m")]:
    print(f"  {a}→{b:5s}", end="")
    for sys in ["descriptive", "distinctive", "classfeat"]:
        d = merkmal.distance(a, b, system=sys)
        print(f" {d:12.3f}", end="")
    print()

#'
#' ClassFeat, trained on a large cognate collection, combines
#' sound-class identity with continuous feature dimensions.  It
#' tends to give the best predictions of which segment pairs are
#' likely to be reflexes of a common ancestor.
#'
#' ## Tone handling
#'
#' Many language families (Sino-Tibetan, Oto-Manguean, Niger-Congo)
#' have contrastive tone. merkmal integrates tone into its feature
#' system using the Yip/Bao model (Yip 1980, Bao 1999) with a three-point decomposition
#' (onset, mid, offset).
#'
#' ### Chao digits and Yip/Bao decomposition
#'
#' Cross-linguistic databases encode tone as Chao digit sequences
#' (1=low to 5=high). merkmal parses these into tonal features:
#'

tones = ["⁵⁵", "³⁵", "²¹⁴", "⁵¹"]
labels = ["high level", "rising", "dipping", "falling"]

print("Chao digit decomposition (onset, mid, offset):\n")
for tone, label in zip(tones, labels):
    parsed = merkmal.parse_chao_digits(tone)
    print(f"  {tone}  ({label:12s}) → onset={parsed[0]}, mid={parsed[1]}, offset={parsed[2]}")

#'
#' Each level maps to a register (upper/lower) and height
#' (raised/lowered) in the Yip/Bao framework. The three-point
#' model captures contour tones naturally: tone 35 (rising) has
#' a low onset and high offset, while tone 51 (falling) has the
#' reverse.
#'
#' ### Tonal features in practice
#'
#' When a segment carries a Chao tone, its features include tonal
#' dimensions alongside segmental ones:
#'

seg_feats = merkmal.get_features("a⁵⁵", system="distinctive")
seg_feats_rising = merkmal.get_features("a³⁵", system="distinctive")

tone_feats_55 = sorted(f for f in seg_feats if "tone" in f)
tone_feats_35 = sorted(f for f in seg_feats_rising if "tone" in f)
seg_only = sorted(f for f in seg_feats if "tone" not in f)

print("Segmental features of /a/:", seg_only)
print()
print("Tonal features of /a⁵⁵/ (high level):", tone_feats_55)
print("Tonal features of /a³⁵/ (rising):     ", tone_feats_35)

#'
#' ### Tone-sensitive distance
#'
#' The tonal features contribute to segment distance. By adjusting
#' node weights, we can control how much tone matters:
#'

print("Distance between /a⁵⁵/ and /a³⁵/ (differ only in tone):\n")

configs = [
    ("default",    None),
    ("segmental",  "segmental"),
    ("tone-heavy", "tone-heavy"),
]

for label, weights in configs:
    d = merkmal.distance("a⁵⁵", "a³⁵", system="distinctive",
                          node_weights=weights)
    print(f"  {label:12s}  d = {d:.3f}")

#'
#' Segmental weights silence tone entirely (zero distance here,
#' since the segments are segmentally identical).  Tone-heavy
#' weights amplify tonal differences.  You pick the setting that
#' matches your data.
#'
#' ### Tone merging in transcriptions
#'
#' In CLDF wordlists, tone digits appear as separate segments.
#' merkmal's `merge_tone_digits()` function attaches them to the
#' preceding vowel:
#'

segments = ["tʰ", "a", "ŋ", "³", "⁵"]
merged = merkmal.merge_tone_digits(segments)
print(f"  Input segments:  {segments}")
print(f"  After merging:   {merged}")
print(f"  Tone digits '³⁵' are now attached to the vowel nucleus.")

#'
#' After merging, the vowel carries tone information as superscript
#' digits, and the feature lookup produces tonal features automatically.
#'
#' ## A Proto-Sino-Tibetan example
#'
#' Velar palatalisation is a common Sino-Tibetan sound change:
#' \*k → tɕ (before high vowels). This involves simultaneous
#' changes in place (velar → alveolo-palatal) and manner
#' (stop → affricate).
#'

print("Proto-Sino-Tibetan velar palatalisation:\n")

a, b = "k", "t͡ʃ"
d = merkmal.distance(a, b, system="distinctive")
feats_a = merkmal.get_features(a)
feats_b = merkmal.get_features(b)
lost = sorted(feats_a - feats_b)
gained = sorted(feats_b - feats_a)

print(f"  d({a}, {b}) = {d:.3f}")
print(f"  lost:   {lost}")
print(f"  gained: {gained}")

#'
#' The distance is higher than any single Grimm pair because
#' a conditioned multi-feature change disrupts more of the
#' phonological system.
#'
#' ### Tonogenesis
#'
#' The voicing split (*b → p) that historically conditioned tone
#' genesis in many Sino-Tibetan languages shows a characteristic
#' distance profile:
#'

print("Tonogenesis-related changes:\n")
for a, b, label in [("b", "p", "devoicing"), ("p", "pʰ", "aspiration split")]:
    d = merkmal.distance(a, b, system="distinctive")
    feats_a = merkmal.get_features(a)
    feats_b = merkmal.get_features(b)
    diff = sorted((feats_a - feats_b) | (feats_b - feats_a))
    print(f"  {a} → {b} ({label}):  d = {d:.3f}  features: {diff}")

#'
#' The aspiration split (p → pʰ) shows a smaller distance than the
#' voicing split (b → p), consistent with aspiration being a
#' single-feature (spread glottis) change while voicing is a more
#' disruptive laryngeal change.
#'
#' ## Lenition as a distance trajectory
#'
#' Lenition (weakening) is a well-attested cross-linguistic
#' tendency. The classical lenition scale
#' (Lavoie 2001, Kirchner 1998) orders segments by
#' "articulatory effort": voiceless stop > voiced stop > fricative
#' > approximant > zero.
#'
#' Each step on the scale should produce a small, roughly equal
#' distance, and the cumulative distance from the starting point
#' should grow monotonically.
#'

lenition_chain = [("p", "b"), ("b", "β"), ("β", "w")]

print("Lenition chain p → b → β → w:\n")
cumulative = 0.0
prev = "p"
for a, b in lenition_chain:
    d = merkmal.distance(a, b, system="distinctive")
    cumulative += d
    print(f"  {a} → {b}:  step = {d:.3f}   cumulative from /p/ = {cumulative:.3f}")

# Direct distance p → w (should ≈ cumulative if the path is linear)
direct = merkmal.distance("p", "w", system="distinctive")
print(f"\n  Direct d(p, w) = {direct:.3f}")
print(f"  Cumulative     = {cumulative:.3f}")
print(f"  Ratio direct/cumulative = {direct/cumulative:.2f}")

#'
#' Here the ratio is 1.0: the direct distance equals the sum of
#' steps, so the path happens to be linear in feature space.
#' When the ratio drops below 1.0, a triangle inequality effect
#' appears because intermediate stages are not on a straight line
#' and the direct path cuts across dimensions.
#'
#' When we observe p ~ w correspondences, the intermediate stages
#' are phonologically motivated: each step is small in feature
#' space.
#'
#' ## Natural vs unnatural sound changes
#'
#' Not all segment correspondences are equally likely to reflect
#' regular sound change. Blevins (2004, *Evolutionary Phonology*)
#' argues that "natural" changes (those with clear articulatory
#' or perceptual motivation) recur independently across language
#' families, while "unnatural" changes are rare or absent.
#'
#' One way to operationalise this: natural changes should
#' produce small feature distances, while unnatural ones should
#' produce large distances.
#'

natural_changes = [
    ("p", "f",  "stop → fricative (Grimm)"),
    ("t", "s",  "stop → sibilant (assibilation)"),
    ("k", "tʃ", "velar → postalveolar (palatalisation)"),
    ("s", "h",  "sibilant → glottal (debuccalisation)"),
    ("n", "ŋ",  "coronal → velar nasal (place assimilation)"),
]

unnatural_changes = [
    ("p", "l",  "voiceless stop → lateral"),
    ("m", "s",  "nasal → sibilant"),
    ("f", "n",  "fricative → nasal"),
    ("ŋ", "t",  "velar nasal → coronal stop"),
    ("w", "k",  "approximant → voiceless stop"),
]

print("Natural sound changes:")
nat_dists = []
for a, b, label in natural_changes:
    d = merkmal.distance(a, b, system="distinctive")
    nat_dists.append(d)
    print(f"  {a} → {b}:  d = {d:.3f}  ({label})")

print("\nUnnatural sound changes:")
unnat_dists = []
for a, b, label in unnatural_changes:
    d = merkmal.distance(a, b, system="distinctive")
    unnat_dists.append(d)
    print(f"  {a} → {b}:  d = {d:.3f}  ({label})")

print(f"\n  Mean natural:   {mean(nat_dists):.3f}")
print(f"  Mean unnatural: {mean(unnat_dists):.3f}")

#'
#' Natural changes cluster in the low-distance range (0.2 to 0.5),
#' unnatural changes are much larger (0.6 to 0.8).  Small feature
#' distance and articulatory naturalness correlate because both
#' amount to minimal articulatory reorganisation.
#'
#' In cognate detection, segment correspondences with very high
#' feature distances are unlikely to be regular sound changes and
#' should receive a higher penalty in alignment scoring. ClassFeat's
#' trained weights already encode this.
#'
#' ## Vowel chain shifts
#'
#' Chain shifts (Labov 1994, *Principles of Linguistic Change*)
#' are a diagnostic of push/pull dynamics in phonological space.
#' In a chain shift, one vowel's movement triggers a neighbour
#' to move, maintaining contrast.
#'
#' The Great Vowel Shift (GVS) is the textbook example:
#' iː → aɪ, eː → iː, aː → eː (simplifying enormously).
#' Each link in the raising chain should show a small, uniform
#' distance, as expected in a drag chain, while the
#' diphthongisation link is larger.
#'
#' merkmal handles diphthongs compositionally: /aɪ/ is
#' decomposed into its component vowels and their features are
#' unioned, so the representation captures both targets of
#' the diphthong.
#'

gvs_chain = [
    ("iː", "aɪ", "high front → diphthong (breaking)"),
    ("eː", "iː", "mid → high (raising, drag)"),
    ("aː", "eː", "low → mid (raising, drag)"),
]

print("Great Vowel Shift (simplified chain):\n")
for a, b, label in gvs_chain:
    d = merkmal.distance(a, b, system="distinctive")
    feats_a = merkmal.get_features(a)
    feats_b = merkmal.get_features(b)
    changed = sorted((feats_a - feats_b) | (feats_b - feats_a))
    print(f"  {a} → {b}:  d = {d:.3f}  ({label})")
    print(f"    changed features: {changed}")

#'
#' The raising links (eː→iː, aː→eː) show equal distances:
#' each is a single height step. The breaking link (iː→aɪ)
#' is larger because diphthongisation involves both a height
#' change and the addition of a second target.
#'
#' Looking at the chain as a whole: in a drag chain, each step
#' should be small and uniform.  Independent changes would show
#' unequal step sizes:
#'

raising_steps = [
    merkmal.distance("aː", "eː", system="distinctive"),
    merkmal.distance("eː", "iː", system="distinctive"),
]
print(f"\n  Raising steps: {[f'{d:.3f}' for d in raising_steps]}")
print(f"  Uniform? {'yes' if len(set(f'{d:.3f}' for d in raising_steps)) == 1 else 'no'}")

#'
#' Uniform step distances within a chain are a useful diagnostic.
#' If vowel correspondences between two languages all show similar
#' small distances and form a connected path through vowel space,
#' that points to a chain shift rather than independent changes.
#'
#' ## Distance as a predictor of borrowability
#'
#' Haugen (1950) observed that borrowed words tend to be
#' adapted to the recipient language's phonology. The adaptation
#' follows a "closest substitute" principle: each foreign segment
#' is replaced by the nearest native segment.
#'
#' With merkmal, the predicted adaptation target for a foreign
#' segment is simply the minimum-distance segment in the native
#' inventory.
#'

# Japanese has no /l/; English loanwords adapt /l/ → /ɾ/.
# Japanese has no /θ/; adapts to /s/.
# We test whether minimum-distance substitution predicts
# the attested adaptation. ClassFeat, trained on cross-linguistic
# correspondences, is the natural system for this.

foreign_segs = ["l", "θ"]
native_candidates = ["ɾ", "b", "d", "s", "t"]
expected = {"l": "ɾ", "θ": "s"}

print("Loanword adaptation (English → Japanese, ClassFeat distances):\n")
for foreign in foreign_segs:
    print(f"  Foreign /{foreign}/:")
    best_seg, best_d = None, float("inf")
    for native in native_candidates:
        d = merkmal.distance(foreign, native, system="classfeat")
        if d < best_d:
            best_d = d
            best_seg = native
    for native in native_candidates:
        d = merkmal.distance(foreign, native, system="classfeat")
        marker = " ← minimum" if native == best_seg else ""
        print(f"    → /{native}/:  d = {d:.3f}{marker}")
    exp = expected[foreign]
    match = "correct" if best_seg == exp else "mismatch"
    print(f"    Predicted: /{best_seg}/  Attested: /{exp}/  ({match})")
    print()

#'
#' The minimum-distance prediction recovers the attested
#' adaptation: /l/ → /ɾ/ (same sound class in ClassFeat's
#' trained model) and /θ/ → /s/ (both voiceless coronal
#' fricatives). Both loanword adaptation and trained feature
#' distance track articulatory similarity as perceived by
#' speakers, so the two measures agree.
#'
#' ## Feature locus and change typology
#'
#' Sound changes can be classified by *where* in the feature
#' geometry they operate (Clements 2001, Hyman 2009). Changes in the Laryngeal
#' node (voicing, aspiration) behave differently from changes in
#' the Place or Manner nodes: they tend to be conditioned by
#' different environments and have different typological
#' distributions.
#'
#' The geometry tree can do this classification for us.
#'

tree = merkmal.DEFAULT_GEOMETRY

# Classify a set of changed features by their geometry locus
changes = [
    ("p", "b",  "voicing"),
    ("p", "f",  "manner (spirantisation)"),
    ("t", "k",  "place"),
    ("p", "pʰ", "aspiration"),
    ("k", "tʃ", "place + manner"),
]

sys_obj = merkmal.get_system("distinctive")

print("Geometry locus of sound changes:\n")
for a, b, label in changes:
    scalars_a = sys_obj.grapheme_to_scalars(a)
    scalars_b = sys_obj.grapheme_to_scalars(b)
    # Find dimensions that differ
    diff_dims = set()
    all_dims = set(scalars_a.keys()) | set(scalars_b.keys())
    for dim in all_dims:
        if scalars_a.get(dim, 0.0) != scalars_b.get(dim, 0.0):
            diff_dims.add(dim)

    # Map each differing dimension to its geometry parent
    loci = set()
    for dim in diff_dims:
        parent = tree.find_parent(dim)
        if parent:
            loci.add(parent.name)

    print(f"  {a} → {b} ({label})")
    print(f"    differing dimensions: {sorted(diff_dims)}")
    print(f"    geometry loci:        {sorted(loci)}")

#'
#' As expected, voicing and aspiration land in the Laryngeal node,
#' spirantisation in Manner, palatalisation in both Place and
#' Manner.  For typological surveys, you can automatically tally
#' which geometry nodes are most frequently affected by diachronic
#' change in a given language family.
#'
#' ## References
#'
#' - Bao, Z. (1999). *The structure of tone*. Oxford University Press.
#' - Blevins, J. (2004). *Evolutionary phonology: the emergence of sound patterns*. Cambridge University Press.
#' - Clements, G. N. (2001). Representational economy in constraint-based phonology. In T. A. Hall (Ed.), *Distinctive feature theory* (pp. 71-146). Mouton de Gruyter.
#' - Haugen, E. (1950). The analysis of linguistic borrowing. *Language*, 26(2), 210-231.
#' - Hyman, L. M. (2009). How (not) to do phonological typology: the case of pitch-accent. *Language Sciences*, 31(2-3), 213-238.
#' - Kirchner, R. (1998). *An effort-based approach to consonant lenition* (Doctoral dissertation). UCLA.
#' - Labov, W. (1994). *Principles of linguistic change, vol. 1: Internal factors*. Blackwell.
#' - Lavoie, L. M. (2001). *Consonant strength: phonological patterns and phonetic manifestations*. Garland.
#' - Yip, M. (1980). *The tonal phonology of Chinese* (Doctoral dissertation). MIT.
