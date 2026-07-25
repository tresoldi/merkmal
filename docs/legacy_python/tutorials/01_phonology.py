#' ---
#' title: "Phonological Features and Natural Classes"
#' ---
#'
#' # Phonological Features and Natural Classes
#'
#' This tutorial covers feature lookup, natural class queries,
#' minimal feature matrices, and the feature geometry tree.
#'
#' Some familiarity with phonological features is assumed
#' (Jakobson, Fant & Halle 1952; Chomsky & Halle 1968; Clements & Hume 1995).
#'

import merkmal

#'
#' ## Feature lookup
#'
#' Given an IPA segment, return its features.
#' By default merkmal uses the Descriptive system, which labels
#' segments with articulatory descriptors from CLTS (Anderson et al. 2018).
#'

print(merkmal.get_features("p"))

#'
#' Those are the articulatory descriptors of /p/.
#' A few more segments:
#'

for seg in ["t", "s", "m", "i", "a", "u"]:
    feats = merkmal.get_features(seg)
    print(f"  /{seg}/  {sorted(feats)}")

#'
#' Vowels are described by height, backness, and rounding. Consonants
#' by voicing, manner, and place, the same dimensions that organise
#' the IPA chart.
#'
#' ### Modified segments
#'
#' Diacritics are handled by compositional decomposition:
#' look up the base segment, then layer on the modifier's features.
#' Any well-formed IPA string gets a representation this way, even
#' without an explicit table entry.
#'

for seg in ["tʰ", "ã", "kʷ", "d̪", "ɲ"]:
    feats = merkmal.get_features(seg)
    print(f"  /{seg}/  {sorted(feats)}")

#'
#' Notice how /tʰ/ adds `aspirated` to the features of /t/, and /ã/
#' adds `nasalized` to those of /a/. The decomposition is recursive:
#' a segment like /t̠ʰʲ/ (post-alveolar aspirated palatalised /t/)
#' would accumulate all three modifiers.
#'

print(f"  /t̠ʰʲ/  {sorted(merkmal.get_features('t̠ʰʲ'))}")

#'
#' ## Natural classes
#'
#' A natural class is a set of segments definable by shared features.
#' You can go in either direction: from segments to shared features,
#' or from features to matching segments.
#'
#' ### Deriving class features
#'
#' What do /p, t, k/ have in common?
#'

shared = merkmal.derive_class_features(["p", "t", "k"])
print(shared)

#'
#' They are all voiceless stop consonants. Now the nasals:
#'

print(merkmal.derive_class_features(["m", "n", "ŋ"]))

#'
#' And what about /p, b/? They share place (bilabial) and manner (stop),
#' but differ in voicing:
#'

print(merkmal.derive_class_features(["p", "b"]))

#'
#' ### Querying by features
#'
#' Going the other way: which segments are `{voiceless, stop}`?
#'

stops = merkmal.features_to_graphemes(frozenset({"voiceless", "stop"}))
print(f"Found {len(stops)} voiceless stops")
print("First 20:", sorted(stops)[:20])

#'
#' The list includes all voiceless stops in merkmal's table, across
#' all places of articulation and with secondary modifications (aspirated,
#' labialised, etc.). This is a superset query: any segment whose features
#' *include* `{voiceless, stop}` matches.
#'
#' We can narrow the query by adding more features:
#'

bilabial_stops = merkmal.features_to_graphemes(
    frozenset({"voiceless", "stop", "bilabial"})
)
print(f"Voiceless bilabial stops: {sorted(bilabial_stops)}")

#'
#' ## Minimal feature matrices
#'
#' What is the smallest set of features that uniquely distinguishes
#' each segment in an inventory?  The minimal specification problem
#' (Archangeli 1988).
#'
#' For the set {p, b, m, n}:
#'

matrix = merkmal.minimal_matrix(["p", "b", "m", "n"], system="distinctive")
print(merkmal.tabulate_matrix(matrix))

#'
#' Three features suffice: `anterior` separates /n/ from the labials,
#' `continuant` separates stops from nasals, and `voice` separates
#' /p/ from /b/. All other features are redundant for this inventory.
#'
#' A larger inventory needs more features. Here is a five-vowel system:
#'

matrix = merkmal.minimal_matrix(["i", "e", "a", "o", "u"], system="distinctive")
print(merkmal.tabulate_matrix(matrix))

#'
#' And a full set of English obstruents:
#'

obstruents = ["p", "b", "t", "d", "k", "ɡ", "f", "v", "θ", "ð", "s", "z", "ʃ", "ʒ"]
matrix = merkmal.minimal_matrix(obstruents, system="distinctive")
print(merkmal.tabulate_matrix(matrix))

#'
#' ## Feature geometry
#'
#' Features are organised into a tree following Clements & Hume (1995).
#' Internal nodes are organising categories (Place, Manner, Laryngeal);
#' terminal nodes are individual features (`voice`, `continuant`, `round`).
#'

tree = merkmal.DEFAULT_GEOMETRY
print(f"Root node: {tree.name}")
print(f"Major nodes: {[c.name for c in tree.children]}")

#'
#' Each major node groups related features:
#'

for node in tree.children:
    if hasattr(node, "children"):
        leaves = []
        for child in node.children:
            if hasattr(child, "positive"):
                leaves.append(child.positive)
            else:
                for grandchild in child.children:
                    if hasattr(grandchild, "positive"):
                        leaves.append(grandchild.positive)
        print(f"  {node.name}: {leaves[:6]}{'...' if len(leaves) > 6 else ''}")

#'
#' ### Depth-derived weights
#'
#' The tree depth determines feature weights. Features closer to the root
#' (depth 1: Laryngeal, Manner, Place) receive higher weight than
#' sub-features (depth 2: Labial, Coronal, Dorsal; depth 3: individual
#' place features). The weight formula is $w = 1/\text{depth}$.
#'
#' So a voicing difference (Laryngeal, depth 2, weight 0.5) contributes
#' more to distance than a rounding difference (Labial, depth 3,
#' weight 0.33).
#'
#' ### Configurable subtree silencing
#'
#' Setting a node's weight to zero removes all its descendants from the
#' distance computation (subtree silencing).  This is how you switch
#' between tone-agnostic and tone-sensitive analysis.
#'

d_default = merkmal.distance("a³⁵", "a⁵⁵", system="distinctive")
d_no_tone = merkmal.distance("a³⁵", "a⁵⁵", system="distinctive",
                              node_weights="segmental")
d_tone_heavy = merkmal.distance("a³⁵", "a⁵⁵", system="distinctive",
                                 node_weights="tone-heavy")

print(f"  a³⁵ vs a⁵⁵ (default weights):   {d_default:.3f}")
print(f"  a³⁵ vs a⁵⁵ (segmental, no tone): {d_no_tone:.3f}")
print(f"  a³⁵ vs a⁵⁵ (tone-heavy):         {d_tone_heavy:.3f}")

#'
#' With segmental weights (Tonal and Prosodic zeroed), the distance drops
#' to exactly zero: the segments are identical apart from tone. With
#' tone-heavy weights, tonal differences are amplified.
#'
#' ## Inventory analysis
#'
#' A small consonant inventory typical of a Polynesian language:
#'

inventory = ["p", "t", "k", "ʔ", "m", "n", "ŋ", "f", "s", "h",
             "l", "ɾ", "w", "j"]

print(f"Inventory: {' '.join(inventory)} ({len(inventory)} segments)\n")

#' Feature profiles:
for seg in inventory:
    feats = merkmal.get_features(seg)
    print(f"  /{seg}/  {sorted(feats)}")

#'
#' ### Natural classes in this inventory
#'

classes = {
    "Stops": ["p", "t", "k", "ʔ"],
    "Nasals": ["m", "n", "ŋ"],
    "Fricatives": ["f", "s", "h"],
    "Approximants": ["l", "ɾ", "w", "j"],
}

print()
for name, segs in classes.items():
    shared = merkmal.derive_class_features(segs)
    print(f"  {name} ({', '.join(segs)}): {shared}")

#'
#' ### Minimal feature matrix for this inventory
#'

matrix = merkmal.minimal_matrix(inventory, system="distinctive")
print(merkmal.tabulate_matrix(matrix))

#'
#' That is the minimum feature set needed to distinguish every segment
#' in the inventory: its contrastive specification.
#'
#'
#' ## Privative vs equipollent features
#'
#' Are features privative (presence/absence, like [nasal]) or
#' equipollent (two-valued, like [±voice])?  Privative features
#' encode markedness asymmetries directly: only marked segments bear
#' the feature.  Equipollent features treat both poles as equally
#' specified.
#'
#' The geometry tree encodes this distinction.  Here is the split:
#'

tree = merkmal.DEFAULT_GEOMETRY

privative = []
equipollent = []

def collect_leaves(node):
    if hasattr(node, "positive"):
        if node.is_privative:
            privative.append(node.name)
        else:
            equipollent.append((node.name, node.positive, node.negative))
    elif hasattr(node, "children"):
        for child in node.children:
            collect_leaves(child)

collect_leaves(tree)

print(f"Privative features ({len(privative)}):")
print(f"  {', '.join(privative[:12])}...")
print(f"\nEquipollent features ({len(equipollent)}):")
for name, pos, neg in equipollent:
    print(f"  {name}: {pos} / {neg}")

#'
#' The asymmetry is theoretically motivated. Features like `nasal`,
#' `lateral`, and `aspirated` are privative because only marked segments
#' bear them; there is no "anti-nasal" property. But `voice` is
#' equipollent because both voiced and voiceless segments are actively
#' specified in many languages (Lombardi 1991, Honeybone 2005).
#'
#' The consequence for distance: a privative feature fires only when
#' one segment has it and the other doesn't.  An equipollent feature
#' fires when the two segments sit on opposite poles.
#'
#' ## Underspecification and contrastive hierarchy
#'
#' The minimal matrices above implement contrastive specification
#' (Dresher 2009): only features needed to distinguish segments
#' in the inventory survive.  In the Contrastive Hierarchy theory,
#' features are ordered by a language-specific hierarchy and applied
#' top-down until all contrasts are resolved.
#'
#' Compare the five-vowel system with a larger seven-vowel system:
#'

inv5 = ["i", "e", "a", "o", "u"]
inv7 = ["i", "e", "ɛ", "a", "ɔ", "o", "u"]

m5 = merkmal.minimal_matrix(inv5, system="distinctive")
m7 = merkmal.minimal_matrix(inv7, system="distinctive")

print(f"5-vowel system ({', '.join(inv5)}): {len(m5.columns)} features needed")
print(merkmal.tabulate_matrix(m5))
print(f"\n7-vowel system ({', '.join(inv7)}): {len(m7.columns)} features needed")
print(merkmal.tabulate_matrix(m7))

#'
#' The five-vowel system needs only `back` and `high`, the two
#' dimensions of the classic vowel triangle.  The seven-vowel system
#' requires more features because mid and open-mid vowels must now
#' be told apart.
#'
#' Dresher's (2009) point: the *same* feature can be contrastive in
#' one inventory and redundant in another.  The minimal matrix gives
#' you the contrastive specification automatically.
#'
#' ### A limitation: the e/ɛ collapse
#'
#' Notice a subtlety in the Distinctive system:
#'

d_dist = merkmal.distance("e", "ɛ", system="distinctive")
d_desc = merkmal.distance("e", "ɛ", system="descriptive")
print(f"d(e, ɛ) Distinctive = {d_dist:.3f}")
print(f"d(e, ɛ) Descriptive = {d_desc:.3f}")

#'
#' In the Distinctive system, /e/ and /ɛ/ receive zero distance because
#' both map to the same scalar values: `close-mid` and `open-mid` both
#' map to 0.0 on the `high` dimension. The Descriptive system
#' distinguishes them because it retains the original height labels.
#'
#' Systems that collapse a many-valued dimension (height) into a
#' few scalar values can lose contrasts.  Having multiple systems
#' lets you see where that happens.
#'
#' ## Feature geometry and phonological processes
#'
#' Feature geometry makes predictions about which feature combinations
#' can spread, be deleted, or participate in harmony
#' (Clements 1985, Sagey 1986).
#'
#' The prediction is that only features dominated by a single node
#' can spread as a unit. Place features spread together (place
#' assimilation), laryngeal features spread together (voicing
#' assimilation), but place + laryngeal cannot spread as an atomic
#' operation.
#'
#' Nasal place assimilation is a good test case, since it is among
#' the most common phonological processes cross-linguistically:
#'

# In nasal place assimilation, a nasal takes on the place of a
# following stop: /n/ → [m] before /p/, /n/ → [ŋ] before /k/.
# The features that change are exactly the Place node's children.
print("Nasal place assimilation: features that change\n")

for nasal_in, nasal_out, stop in [("n","m","p"), ("n","ŋ","k")]:
    feats_in = merkmal.get_features(nasal_in)
    feats_out = merkmal.get_features(nasal_out)
    changed = (feats_in - feats_out) | (feats_out - feats_in)
    shared = feats_in & feats_out

    # Check which geometry nodes the changed features belong to
    nodes = set()
    for f in changed:
        parent = tree.find_parent(f)
        if parent:
            nodes.add(parent.name)

    print(f"  /{nasal_in}/ → [{nasal_out}] before /{stop}/:")
    print(f"    changed features: {sorted(changed)}")
    print(f"    geometry nodes:   {sorted(nodes)}")
    print(f"    preserved:        {sorted(shared)}")
    print()

#'
#' In both cases, the changing features belong to Place sub-nodes
#' (Labial, Coronal, Dorsal), while Manner and Laryngeal features
#' are preserved. Place assimilation operates on a natural class
#' of features defined by the geometry, as predicted.
#'
#' ### Sibling features and geometric locality
#'
#' The geometry tree defines which features are siblings (share a
#' parent node). Siblings are expected to interact (compete or
#' co-occur) more than non-siblings.
#'

print("Sibling relationships in the geometry:\n")
for feat in ["voiced", "nasal", "rounded", "close"]:
    sibs = tree.siblings_of(feat)
    print(f"  {feat:10s} siblings: {sorted(sibs)}")

#'
#' The siblings of `voiced` are the other laryngeal properties
#' (voiceless, aspirated, breathy, creaky, glottalized), the set
#' that patterns together in laryngeal alternations cross-linguistically.
#' The siblings of `close` include other Dorsal vowel features
#' (height, backness) but not place features from other nodes.
#'
#' ## Distance as a vowel space
#'
#' merkmal distances create an implicit vowel space.  A distance
#' matrix for the cardinal vowels should recover something like
#' the traditional vowel quadrilateral:
#'

vowels = ["i", "e", "a", "o", "u"]

# Build and display distance matrix
print(f"Vowel distance matrix (Distinctive):\n")
print(f"{'':6s}" + "".join(f"{v:>6s}" for v in vowels))
for v1 in vowels:
    print(f"{v1:6s}", end="")
    for v2 in vowels:
        d = merkmal.distance(v1, v2, system="distinctive")
        print(f"{d:6.3f}", end="")
    print()

#'
#' /i/ and /u/ are equidistant from /a/ (high vs low), /i/-/e/ and
#' /u/-/o/ form close pairs (adjacent heights), and /i/ to /o/ is
#' more distant than /i/ to /e/ (crossing both height and backness).
#' So far, so expected.
#'
#' More interesting is the asymmetry: i/a = 0.286 but a/u = 0.571.
#' /a/ is classified as front-unrounded, so it sits closer to /i/
#' than to /u/.  Whether low vowels are phonologically front or
#' central is a long-running debate (Ladefoged & Maddieson 1996), and
#' the distance matrix makes the system's stance on it visible.
#'
#' ## References
#'
#' - Anderson, C., Tresoldi, T., Chacon, T. C., Fehn, A.-M., Walworth, M., Forkel, R., & List, J.-M. (2018).
#'   A cross-linguistic database of phonetic transcription systems. *Yearbook of the Poznań Linguistic Meeting*, 4(1), 21-53.
#' - Archangeli, D. (1988). Aspects of underspecification theory. *Phonology*, 5(2), 183-207.
#' - Chomsky, N., & Halle, M. (1968). *The sound pattern of English*. Harper & Row.
#' - Clements, G. N. (1985). The geometry of phonological features. *Phonology Yearbook*, 2, 225-252.
#' - Clements, G. N., & Hume, E. V. (1995). The internal organization of speech sounds. In J. A. Goldsmith (Ed.), *The handbook of phonological theory* (pp. 245-306). Blackwell.
#' - Dresher, B. E. (2009). *The contrastive hierarchy in phonology*. Cambridge University Press.
#' - Honeybone, P. (2005). Diachronic evidence in segmental phonology: the case of obstruent laryngeal specifications. In M. van Oostendorp & J. van de Weijer (Eds.), *The internal organization of phonological segments* (pp. 319-354). Mouton de Gruyter.
#' - Jakobson, R., Fant, G., & Halle, M. (1952). *Preliminaries to speech analysis*. MIT Press.
#' - Ladefoged, P., & Maddieson, I. (1996). *The sounds of the world's languages*. Blackwell.
#' - Lombardi, L. (1991). *Laryngeal features and laryngeal neutralization* (Doctoral dissertation). University of Massachusetts Amherst.
#' - Sagey, E. (1986). *The representation of features and relations in non-linear phonology* (Doctoral dissertation). MIT.
