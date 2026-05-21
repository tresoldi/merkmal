#' ---
#' title: "Getting started with merkmal"
#' ---
#'
#' # Getting started with merkmal
#'
#' merkmal is a zero-dependency Python library for phonological
#' features.  It ships nine feature systems, geometry-weighted
#' distance, and tone support.
#'
#' This notebook walks through the core API: feature lookup,
#' natural classes, distances across systems, sound change
#' modelling, tone, and a small cognate detection experiment.
#'

#| hide
# If running in Colab, uncomment the next line:
# !pip install -q merkmal
#|

import merkmal
from statistics import mean

print(f"merkmal {merkmal.__version__}")
print(f"Systems: {merkmal.list_systems()}")

#'
#' ## Feature lookup
#'
#' By default merkmal uses the Descriptive system, which labels
#' segments with articulatory descriptors (voiceless, bilabial, stop).
#'

for seg in ["p", "t", "s", "m", "a", "i"]:
    print(f"  /{seg}/  {sorted(merkmal.get_features(seg))}")

#'
#' Diacritics compose automatically through Unicode NFD decomposition.
#' The base segment is looked up in the table, then each combining
#' mark adds or changes features.
#'

for seg in ["tʰ", "ã", "kʷ", "d̪", "ɲ"]:
    print(f"  /{seg}/  {sorted(merkmal.get_features(seg))}")

#'
#' ## Natural classes
#'
#' `derive_class_features` finds the features shared by a set of
#' segments.  `features_to_graphemes` goes the other way: given
#' features, find all matching segments.
#'

print("Voiceless stops:", merkmal.derive_class_features(["p", "t", "k"]))
print("Nasals:         ", merkmal.derive_class_features(["m", "n", "ŋ"]))
print("Labials:        ", merkmal.derive_class_features(["p", "b", "m"]))

#'

stops = merkmal.features_to_graphemes(frozenset({"voiceless", "stop"}))
print(f"Voiceless stops in the system: {len(stops)} segments")
print(f"First 15: {stops[:15]}")

#'
#' ### Minimal feature matrix
#'
#' Given an inventory, `minimal_matrix` computes the smallest set of
#' features that distinguishes every segment from every other.
#'

matrix = merkmal.minimal_matrix(["p", "b", "m", "n"], system="distinctive")
print(merkmal.tabulate_matrix(matrix))

#'
#' **Try it yourself.**
#' Look up features for a click (`"ǀ"` or `"ǃ"`).
#' What do `["b", "d", "ɡ"]` share?
#' How many segments match `{"nasal", "consonant"}`?
#'
#' ## Multiple feature systems
#'
#' merkmal ships five system families.  Each encodes a different
#' phonological theory.
#'
#' | System | Type | Best for |
#' |--------|------|----------|
#' | Descriptive | categorical | general-purpose, typology |
#' | Distinctive | scalar, geometry | feature geometry research |
#' | ClassFeat | hybrid, trained | cognate detection |
#' | P-base (HC, JFH, SPE, UFTC) | multi-state | theory comparison |
#' | PHOIBLE | binary, 37 features | cross-linguistic surveys |
#'

for sys in ["descriptive", "distinctive", "phoible"]:
    feats = merkmal.get_features("p", system=sys)
    print(f"  {sys:14s}  {sorted(feats)}")

#'
#' The same segment looks different under each theory.  Descriptive
#' gives articulatory labels; Distinctive gives scalar dimensions
#' aligned with the geometry tree; PHOIBLE gives 37 binary features.
#'
#' How does this affect distance?
#'

pairs = [("p", "b"), ("p", "f"), ("p", "k"), ("t", "s"), ("p", "m")]
systems = ["descriptive", "distinctive", "classfeat"]

header = f"  {'pair':8s}" + "".join(f" {s:>12s}" for s in systems)
print(header)
print("  " + "-" * (8 + 13 * len(systems)))
for a, b in pairs:
    row = f"  {a}~{b:3s}"
    for s in systems:
        d = merkmal.distance(a, b, system=s)
        row += f" {d:12.3f}"
    print(row)

#'
#' Descriptive and Distinctive agree on ranking but diverge in
#' magnitude.  ClassFeat, trained on cognate data, compresses
#' voicing changes (p~b) and spreads manner changes (p~f).
#'
#' **Try it yourself.**
#' Compare `"e"` and `"ɛ"` across systems.  Distinctive collapses
#' them to 0 -- why?  Try `"o"` vs `"ɔ"` too.
#'
#' ## Phonological distance and geometry
#'
#' Distances are normalised to [0, 1].  The Clements & Hume (1995)
#' geometry tree gives structure-aware weights: features higher in
#' the tree contribute more than features buried in a subtree.
#' The effect is that major-class changes (manner, laryngeal) cost
#' more than sub-place changes (anterior vs distributed).
#'
#' ### Vowel distance matrix
#'

vowels = ["i", "e", "a", "o", "u"]
print(f"{'':6s}" + "".join(f"{v:>6s}" for v in vowels))
for v1 in vowels:
    row = f"{v1:6s}"
    for v2 in vowels:
        d = merkmal.distance(v1, v2, system="distinctive")
        row += f"{d:6.2f}"
    print(row)

#'
#' Front vowels (i, e, a) cluster together, back vowels (o, u)
#' cluster together, and the cross-group distances are larger.
#'
#' ### Consonant distance matrix
#'

consonants = ["p", "t", "k", "b", "d", "ɡ", "m", "n", "ŋ"]
print(f"{'':4s}" + "".join(f"{c:>5s}" for c in consonants))
for c1 in consonants:
    row = f"{c1:4s}"
    for c2 in consonants:
        d = merkmal.distance(c1, c2, system="distinctive")
        row += f"{d:5.2f}"
    print(row)

#'
#' Voicing pairs (p~b, t~d, k~ɡ) are close.  Nasals are further
#' from their oral counterparts because nasality changes a Manner
#' feature, which sits higher in the tree than Place sub-features.
#'
#' **Try it yourself.**
#' Build a distance matrix for `["t", "ʈ", "d", "ɖ"]` (retroflex
#' vs dental/alveolar).  Try `node_weights="flat"` on the vowel
#' matrix and see what changes.
#'
#' ## Sound changes as feature distances
#'
#' A sound change maps one feature bundle to another.  The
#' phonological distance quantifies the size of the change.
#' Natural changes should produce small distances.
#'
#' ### Grimm's Law
#'

grimm = [("p", "f"), ("t", "θ"), ("k", "x")]
for a, b in grimm:
    d = merkmal.distance(a, b, system="distinctive")
    lost = sorted(merkmal.get_features(a) - merkmal.get_features(b))
    gained = sorted(merkmal.get_features(b) - merkmal.get_features(a))
    shared = sorted(merkmal.get_features(a) & merkmal.get_features(b))
    print(f"  {a} → {b}:  d = {d:.3f}")
    print(f"    lost: {lost}   gained: {gained}   shared: {shared}\n")

#'
#' All three Grimm pairs have similar low distances (0.21-0.22):
#' each is a stop-to-fricative change that preserves voicing and
#' most of the place features.
#'
#' ### Palatalisation and lenition
#'

changes = [
    ("k", "t͡ʃ", "palatalisation"),
    ("s", "h",   "debuccalisation"),
    ("b", "β",   "lenition (spirantisation)"),
]
for a, b, label in changes:
    d = merkmal.distance(a, b, system="distinctive")
    print(f"  {a} → {b}:  d = {d:.3f}  ({label})")

#'
#' Palatalisation (k → t͡ʃ) costs more than Grimm because it changes
#' both place and manner.  Lenition (b → β) costs the same as
#' Grimm -- a single manner change.
#'
#' ### Lenition chain
#'

chain = [("p", "b"), ("b", "β"), ("β", "w")]
cumulative = 0.0
for a, b in chain:
    d = merkmal.distance(a, b, system="distinctive")
    cumulative += d
    print(f"  {a} → {b}:  step = {d:.3f}   cumulative = {cumulative:.3f}")

direct = merkmal.distance("p", "w", system="distinctive")
print(f"\n  Direct d(p, w) = {direct:.3f}")
print(f"  Cumulative     = {cumulative:.3f}")

#'
#' Each step is small, but the accumulation gives a large distance
#' for the endpoints.  When we see p ~ w correspondences, the
#' intermediate stages are phonologically motivated.
#'
#' ### Tonogenesis
#'

print(f"  b → p (devoicing):      d = {merkmal.distance('b', 'p', system='distinctive'):.3f}")
print(f"  p → pʰ (aspiration):    d = {merkmal.distance('p', 'pʰ', system='distinctive'):.3f}")

#'
#' These are the segmental traces of tone genesis: a laryngeal
#' contrast migrates to pitch, then the onset neutralises.
#' Both changes are small in feature space.
#'
#' **Try it yourself.**
#' Trace the assibilation chain `t → ts → s`.
#' Compute `d("k", "tɕ")` for Sino-Tibetan palatalisation.
#' What do `["p", "f"]` share vs what differs?
#'
#' ## Tone
#'
#' merkmal integrates tone using the Yip (1980) / Bao (1999)
#' geometry.  Chao digit sequences (1-5) are decomposed into
#' onset, mid, and offset targets.  The Tonal node sits alongside
#' Laryngeal, Manner, and Place in the geometry tree.
#'
#' ### Chao digit decomposition
#'

for digits in ["⁵⁵", "³⁵", "²¹⁴", "⁵¹"]:
    parsed = merkmal.parse_chao_digits(digits)
    print(f"  {digits:5s} → onset={parsed[0]}, mid={parsed[1]}, offset={parsed[2]}")

#'
#' ### Tone merging
#'
#' CLDF data typically segments tone digits as separate tokens.
#' `merge_tone_digits` attaches them to the vowel nucleus.
#'

raw = ["tʰ", "a", "ŋ", "³", "⁵"]
merged = merkmal.merge_tone_digits(raw)
print(f"  {raw} → {merged}")

raw2 = ["m", "a", "⁵", "¹"]
merged2 = merkmal.merge_tone_digits(raw2)
print(f"  {raw2} → {merged2}")

#'
#' ### Tonal distance with weight presets
#'
#' Node weight presets control how much tone contributes to
#' distance.  `"segmental"` ignores tone entirely; `"tone-heavy"`
#' doubles its weight.
#'

presets = [None, "segmental", "tone-heavy"]
labels = ["default", "segmental", "tone-heavy"]
for preset, label in zip(presets, labels):
    d = merkmal.distance("a⁵⁵", "a³⁵", system="distinctive", node_weights=preset)
    print(f"  {label:14s}  d(a⁵⁵, a³⁵) = {d:.3f}")

#'
#' With segmental weighting, a⁵⁵ and a³⁵ are identical (same vowel,
#' tone ignored).  With tone-heavy, the distance is larger than
#' default because the tonal subtree contributes twice as much.
#'

print("\nTonal distance matrix (distinctive, tone-heavy):\n")
tones = ["a⁵⁵", "a³⁵", "a²¹⁴", "a⁵¹"]
tone_labels = ["⁵⁵", "³⁵", "²¹⁴", "⁵¹"]
print(f"{'':8s}" + "".join(f"{t:>8s}" for t in tone_labels))
for i, t1 in enumerate(tones):
    row = f"{tone_labels[i]:8s}"
    for t2 in tones:
        d = merkmal.distance(t1, t2, system="distinctive", node_weights="tone-heavy")
        row += f"{d:8.3f}"
    print(row)

#'
#' Register differences (⁵⁵ vs ²¹⁴) cost more than contour
#' differences (⁵⁵ vs ⁵¹), following the Yip/Bao hierarchy.
#'
#' **Try it yourself.**
#' Compare `"a⁵⁵"` to `"a¹¹"` (max tonal distance) with different
#' presets.  Try `node_weights="tone-only"` -- what happens to
#' the segmental component?
#'
#' ## Cognate detection with phonological distance
#'
#' Segment distance feeds into Needleman-Wunsch alignment, which
#' scores word pairs.  Threshold-free evaluation with AUC tells us
#' how well alignment cost separates cognates from non-cognates.
#'
#' ### The aligner
#'

GAP_COST = 0.5


def nw_distance(seq_a, seq_b, sub_cost, gap_cost=GAP_COST):
    """Needleman-Wunsch alignment distance, normalised to [0, 1]."""
    n, m = len(seq_a), len(seq_b)
    if n == 0 and m == 0:
        return 0.0
    if n == 0 or m == 0:
        return 1.0
    prev = [j * gap_cost for j in range(m + 1)]
    curr = [0.0] * (m + 1)
    for i in range(1, n + 1):
        curr[0] = i * gap_cost
        for j in range(1, m + 1):
            cost = sub_cost(seq_a[i - 1], seq_b[j - 1])
            curr[j] = min(
                prev[j - 1] + cost,
                prev[j] + gap_cost,
                curr[j - 1] + gap_cost,
            )
        prev, curr = curr, prev
    raw = prev[m]
    max_cost = max(n, m) * max(gap_cost, 1.0)
    return min(1.0, raw / max_cost)


def compute_auc(cognate_distances, non_cognate_distances):
    """AUC via the Wilcoxon-Mann-Whitney U statistic."""
    n_cog = len(cognate_distances)
    n_non = len(non_cognate_distances)
    if n_cog == 0 or n_non == 0:
        return 0.5
    count = 0
    ties = 0
    for c in cognate_distances:
        for n in non_cognate_distances:
            if c < n:
                count += 1
            elif c == n:
                ties += 1
    return (count + 0.5 * ties) / (n_cog * n_non)

#'
#' ### Austronesian data
#'
#' A small dataset with five concepts across five languages.
#' Cognate classes are loosely based on comparative Austronesian
#' scholarship (Blust 1999, Greenhill et al. 2008).
#'

DATA = [
    # 'eye': PAN *maCa, cognate class E1
    ("Malay",    "eye",   ["m", "a", "t", "a"],         "E1"),
    ("Tagalog",  "eye",   ["m", "a", "t", "a"],         "E1"),
    ("Javanese", "eye",   ["m", "ɔ", "t", "ɔ"],         "E1"),
    ("Hawaiian", "eye",   ["m", "a", "k", "a"],          "E1"),
    ("Fijian",   "eye",   ["m", "a", "t", "a"],          "E1"),
    # 'hand': two cognate classes
    ("Malay",    "hand",  ["t", "a", "ŋ", "a", "n"],    "H1"),
    ("Tagalog",  "hand",  ["k", "a", "m", "a", "j"],    "H2"),
    ("Javanese", "hand",  ["t", "a", "ŋ", "a", "n"],    "H1"),
    ("Hawaiian", "hand",  ["l", "i", "m", "a"],          "H2"),
    ("Fijian",   "hand",  ["l", "i", "ŋ", "a"],          "H2"),
    # 'water': two cognate classes
    ("Malay",    "water", ["a", "j", "e", "r"],          "W1"),
    ("Tagalog",  "water", ["t", "u", "b", "i", "g"],    "W2"),
    ("Javanese", "water", ["b", "a", "ɲ", "u"],          "W2"),
    ("Hawaiian", "water", ["w", "a", "i"],                "W1"),
    ("Fijian",   "water", ["w", "a", "i"],                "W1"),
    # 'fire': two cognate classes
    ("Malay",    "fire",  ["a", "p", "i"],               "F1"),
    ("Tagalog",  "fire",  ["a", "p", "o", "j"],          "F1"),
    ("Javanese", "fire",  ["g", "ə", "n", "i"],          "F2"),
    ("Hawaiian", "fire",  ["a", "h", "i"],                "F1"),
    ("Fijian",   "fire",  ["b", "u", "k", "a"],          "F2"),
    # 'stone': one cognate class (PAN *batu)
    ("Malay",    "stone", ["b", "a", "t", "u"],          "S1"),
    ("Tagalog",  "stone", ["b", "a", "t", "o"],          "S1"),
    ("Javanese", "stone", ["w", "a", "t", "u"],          "S1"),
    ("Hawaiian", "stone", ["p", "o", "h", "a", "k", "u"],"S1"),
    ("Fijian",   "stone", ["v", "a", "t", "u"],          "S1"),
]

#'
#' ### Pair generation
#'
#' Cognate pairs share a concept and cognate class.  Non-cognate
#' pairs share a concept but differ in class -- harder negatives
#' than random cross-concept pairs.
#'

cognate_pairs = []
non_cognate_pairs = []

for concept in ["eye", "hand", "water", "fire", "stone"]:
    entries = [(lang, segs, cls) for lang, con, segs, cls in DATA if con == concept]
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            lang_a, segs_a, cls_a = entries[i]
            lang_b, segs_b, cls_b = entries[j]
            if lang_a == lang_b:
                continue
            pair = (segs_a, segs_b, lang_a, lang_b, concept)
            if cls_a == cls_b:
                cognate_pairs.append(pair)
            else:
                non_cognate_pairs.append(pair)

print(f"Cognate pairs:     {len(cognate_pairs)}")
print(f"Non-cognate pairs: {len(non_cognate_pairs)}")

#'
#' ### Word distances and AUC
#'

eval_systems = ["descriptive", "distinctive", "classfeat"]
results = {}
for sys_name in eval_systems:
    sub = lambda a, b, s=sys_name: merkmal.distance(a, b, system=s)
    cog_dists = [nw_distance(a, b, sub) for a, b, *_ in cognate_pairs]
    non_dists = [nw_distance(a, b, sub) for a, b, *_ in non_cognate_pairs]
    results[sys_name] = (cog_dists, non_dists)

print(f"\n  {'system':14s}  {'cog mean':>9s}  {'non mean':>9s}  {'sep':>6s}  {'AUC':>6s}")
print("  " + "-" * 50)
for sys_name in eval_systems:
    cog_dists, non_dists = results[sys_name]
    auc = compute_auc(cog_dists, non_dists)
    sep = mean(non_dists) - mean(cog_dists)
    print(f"  {sys_name:14s}  {mean(cog_dists):9.3f}  {mean(non_dists):9.3f}  {sep:6.3f}  {auc:6.3f}")

#'
#' All three systems separate cognates from non-cognates.  ClassFeat
#' typically gives the best AUC because it was trained on cognate
#' data from Lexibank.
#'
#' ### Alignment visualisation
#'

def nw_align(seq_a, seq_b, sub_cost, gap_cost=GAP_COST):
    """Return the optimal alignment as two parallel lists."""
    n, m = len(seq_a), len(seq_b)
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i * gap_cost
    for j in range(m + 1):
        dp[0][j] = j * gap_cost
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = sub_cost(seq_a[i - 1], seq_b[j - 1])
            dp[i][j] = min(
                dp[i - 1][j - 1] + cost,
                dp[i - 1][j] + gap_cost,
                dp[i][j - 1] + gap_cost,
            )
    align_a, align_b = [], []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            cost = sub_cost(seq_a[i - 1], seq_b[j - 1])
            if abs(dp[i][j] - (dp[i - 1][j - 1] + cost)) < 1e-9:
                align_a.append(seq_a[i - 1])
                align_b.append(seq_b[j - 1])
                i -= 1
                j -= 1
                continue
        if i > 0 and abs(dp[i][j] - (dp[i - 1][j] + gap_cost)) < 1e-9:
            align_a.append(seq_a[i - 1])
            align_b.append("-")
            i -= 1
            continue
        align_a.append("-")
        align_b.append(seq_b[j - 1])
        j -= 1
    return list(reversed(align_a)), list(reversed(align_b))


def show_alignment(seq_a, seq_b, system="distinctive"):
    """Print an alignment with per-position costs."""
    sub = lambda a, b: merkmal.distance(a, b, system=system)
    a, b = nw_align(seq_a, seq_b, sub)
    costs = []
    for x, y in zip(a, b):
        if x == "-" or y == "-":
            costs.append(GAP_COST)
        else:
            costs.append(merkmal.distance(x, y, system=system))
    w = 6
    print("  ", "".join(f"{x:>{w}s}" for x in a))
    print("  ", "".join(f"{x:>{w}s}" for x in b))
    print("  ", "".join(f"{c:{w}.2f}" for c in costs))

#'

print("Cognate pair -- Malay /mata/ ~ Hawaiian /maka/ ('eye'):\n")
show_alignment(["m", "a", "t", "a"], ["m", "a", "k", "a"])

print("\n\nNon-cognate pair -- Malay /mata/ ~ Hawaiian /wai/ ('eye' vs 'water'):\n")
show_alignment(["m", "a", "t", "a"], ["w", "a", "i"])

#'
#' The cognate pair aligns with mostly zero costs (identical segments)
#' and one moderate substitution (t~k, a regular sound change).
#' The non-cognate pair forces gaps and unrelated substitutions.
#'
#' ### Tonal cognate detection
#'
#' Tone carries phylogenetic signal.  To show this, we build a small
#' set of tonal pairs and measure how well tonal distance separates
#' "cognate-like" pairs (similar tone) from "non-cognate-like" pairs
#' (distant tone).
#'

tone_cognate = [
    (["a⁵⁵"], ["a⁵³"]),
    (["a³⁵"], ["a²⁴"]),
    (["a²¹⁴"], ["a²¹³"]),
    (["a⁵¹"], ["a⁴¹"]),
]
tone_noncognate = [
    (["a⁵⁵"], ["a²¹⁴"]),
    (["a³⁵"], ["a⁵¹"]),
    (["a⁵⁵"], ["a¹¹"]),
    (["a⁵¹"], ["a³⁵"]),
]

sub_tone = lambda a, b: merkmal.distance(a, b, system="distinctive", node_weights="tone-heavy")
tone_cog_dists = [nw_distance(a, b, sub_tone) for a, b in tone_cognate]
tone_non_dists = [nw_distance(a, b, sub_tone) for a, b in tone_noncognate]

print(f"Tone-only AUC: {compute_auc(tone_cog_dists, tone_non_dists):.3f}")
print(f"  cognate mean:     {mean(tone_cog_dists):.3f}")
print(f"  non-cognate mean: {mean(tone_non_dists):.3f}")

#'
#' Even with just four pairs in each group, tonal distance provides
#' discriminative power.  On larger tonal datasets (Sino-Tibetan,
#' Tai-Kadai, Hmong-Mien), proper tone handling improves AUC by
#' 6-8 points across all systems.
#'
#' **Try it yourself.**
#' Add Fijian entries to the data and re-run.
#' Try `node_weights="flat"` instead of geometry weighting -- does
#' AUC change?  Align your own word pairs from a family you know.
#'
#' ## Where to go from here
#'
#' This notebook covered the core API.  The full tutorials go deeper:
#'
#' - Tutorial 1 (phonological features): minimal matrices, geometry tree, weight presets
#' - Tutorial 2 (typology): system comparison, feature economy, coverage
#' - Tutorial 3 (historical linguistics): sound change chains, natural vs unnatural, GVS
#' - Tutorial 4 (cognate detection): full evaluation pipeline, error analysis
#'
#' ## References
#'
#' - Bao, Z. (1999). *The structure of tone*. Oxford University Press.
#' - Blust, R. (1999). Subgrouping, circularity and extinction. In E. Zeitoun & P. J.-K. Li (Eds.), *Selected papers from ICAL 8* (pp. 31-94).
#' - Chomsky, N., & Halle, M. (1968). *The sound pattern of English*. Harper & Row.
#' - Clements, G. N., & Hume, E. V. (1995). The internal organization of speech sounds. In J. A. Goldsmith (Ed.), *The handbook of phonological theory* (pp. 245-306). Blackwell.
#' - Covington, M. A. (1996). An algorithm to align words for historical comparison. *Computational Linguistics*, 22(4), 481-496.
#' - List, J.-M. (2012). SCA: phonetic alignment based on sound classes. In M. Slavkovik & D. Lassiter (Eds.), *New directions in logic, language and computation* (pp. 32-51). Springer.
#' - Needleman, S. B., & Wunsch, C. D. (1970). A general method applicable to the search for similarities in the amino acid sequence of two proteins. *Journal of Molecular Biology*, 48(3), 443-453.
#' - Yip, M. (1980). *The tonal phonology of Chinese* (Doctoral dissertation). MIT.
