#' ---
#' title: "Cognate Detection with Phonological Distance"
#' ---
#'
#' # Cognate Detection with Phonological Distance
#'
#' Cognate detection asks whether two words in related languages
#' descend from a common ancestor.  Phylogenetic inference, sound
#' law induction, and proto-form reconstruction all depend on it.
#'
#' A common baseline treats cognate detection as a distance
#' problem: align two phonological sequences, score their
#' segment-by-segment similarity, and threshold the result.  More
#' sophisticated methods exist (sound correspondence models,
#' probabilistic approaches), but distance remains a foundation
#' that many of them build on.
#'
#' Below we build a cognate detection pipeline from segment distance
#' through sequence alignment to threshold-free evaluation.
#'

import merkmal
from statistics import mean

#'
#' ## From segments to sequences
#'
#' merkmal provides segment-level distance: `merkmal.distance("p", "b")`
#' returns a normalised value in [0, 1].  But cognate detection operates
#' on *words*, variable-length sequences of segments.
#'
#' The standard bridge is Needleman-Wunsch (NW) global alignment
#' (Needleman & Wunsch 1970), the same DP algorithm used in
#' bioinformatics.  In historical linguistics it was introduced by
#' Covington (1996, 1998) and refined by List (2012).
#'
#' ### The alignment model
#'
#' The implementation here is simplified for pedagogy.  Production
#' aligners add prosodic weighting (different gap penalties for
#' onset, nucleus, coda), position-sensitive scoring (word-initial
#' vs. medial), and syllable-aware alignment (List 2012).  Those
#' refinements matter for alignment quality but are orthogonal to
#' the segment distance function.
#'
#' NW alignment finds the minimum-cost mapping between two sequences,
#' allowing three operations at each position:
#'
#' - substitution: align segment *a* with segment *b*, paying
#'   `sub_cost(a, b)`, the phonological distance between them.
#' - insertion: align a gap with segment *b*, paying `gap_cost`.
#' - deletion: align segment *a* with a gap, paying `gap_cost`.
#'
#' The gap cost is a free parameter.  Setting it too low produces
#' many gaps (over-fragmented alignments); setting it too high forces
#' unrelated segments to align.  Following List (2012), we use 0.5,
#' the midpoint of the [0, 1] distance range.
#'

GAP_COST = 0.5


def nw_distance(seq_a, seq_b, sub_cost, gap_cost=GAP_COST):
    """Needleman-Wunsch alignment distance, normalised to [0, 1].

    Uses a space-efficient two-row DP implementation.
    """
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
                prev[j - 1] + cost,      # substitution
                prev[j] + gap_cost,       # deletion
                curr[j - 1] + gap_cost,   # insertion
            )
        prev, curr = curr, prev

    raw = prev[m]
    max_cost = max(n, m) * max(gap_cost, 1.0)
    return min(1.0, raw / max_cost)

#'
#' Normalisation divides by the worst-case cost (all gaps), giving
#' a distance in [0, 1].  Identical sequences score 0.0.
#'
#' ### Alignment visualisation
#'
#' Before using the aligner as a black box, let us look at what
#' it actually produces.  Full DP matrix for traceback:
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
    # Traceback.
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
#' How the aligner handles Austronesian cognates.
#' Proto-Austronesian \*mata 'eye' is preserved across the
#' family with little change, but Hawaiian shows the
#' \*t > k shift:
#'

print("Alignment: Malay /mata/ ~ Hawaiian /maka/ (cognate, 'eye'):\n")
show_alignment(["m", "a", "t", "a"], ["m", "a", "k", "a"])

#'
#' The /t/ ~ /k/ correspondence gets a moderate cost (a place change),
#' while the identical segments contribute zero.
#'
#' Compare with a non-cognate pair, same language pair, different
#' concepts:
#'

print("\nAlignment: Malay /mata/ ~ Hawaiian /wai/ (non-cognate, 'eye' vs 'water'):\n")
show_alignment(["m", "a", "t", "a"], ["w", "a", "i"])

#'
#' The non-cognate alignment introduces gaps and aligns unrelated
#' segments, pushing up the total cost.  That separation between
#' cognate and non-cognate distances is what cognate detection
#' algorithms rely on.
#'
#' ## A mini cognate detection experiment
#'
#' ### Data
#'
#' We use a small Austronesian dataset with simplified cognacy
#' judgements for pedagogical purposes.  Each entry is a
#' (language, concept, segments, cognate_class) tuple.
#' The cognate classes are loosely based on comparative
#' Austronesian scholarship (Blust 1999, Greenhill et al. 2008),
#' but have been simplified for this demonstration.
#'

DATA = [
    # 'eye': PAN *maCa, cognate class E1
    ("Malay",    "eye",   ["m", "a", "t", "a"],         "E1"),
    ("Tagalog",  "eye",   ["m", "a", "t", "a"],         "E1"),
    ("Javanese", "eye",   ["m", "ɔ", "t", "ɔ"],         "E1"),
    ("Hawaiian", "eye",   ["m", "a", "k", "a"],          "E1"),
    # 'hand': two cognate classes:
    #   H1: PAN *tangan reflexes (Malay, Javanese)
    #   H2: PAN *lima reflexes (Hawaiian, Fijian, Tagalog)
    ("Malay",    "hand",  ["t", "a", "ŋ", "a", "n"],    "H1"),
    ("Tagalog",  "hand",  ["k", "a", "m", "a", "j"],    "H2"),
    ("Javanese", "hand",  ["t", "a", "ŋ", "a", "n"],    "H1"),
    ("Hawaiian", "hand",  ["l", "i", "m", "a"],          "H2"),
    ("Fijian",   "hand",  ["l", "i", "ŋ", "a"],          "H2"),
    # 'water': two cognate classes:
    #   W1: PAN *waiR reflexes (Malay, Hawaiian, Fijian)
    #   W2: unrelated etyma (Tagalog tubig, Javanese banyu)
    ("Malay",    "water", ["a", "j", "e", "r"],          "W1"),
    ("Tagalog",  "water", ["t", "u", "b", "i", "g"],    "W2"),
    ("Javanese", "water", ["b", "a", "ɲ", "u"],          "W2"),
    ("Hawaiian", "water", ["w", "a", "i"],                "W1"),
    ("Fijian",   "water", ["w", "a", "i"],                "W1"),
    # 'fire': two cognate classes:
    #   F1: PAN *Sapuy reflexes (Malay, Tagalog, Hawaiian)
    #   F2: unrelated etyma (Javanese geni, Fijian buka)
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
#' Following List (2012) and Jäger (2013), we build two sets of
#' word pairs:
#'
#' - Cognate pairs: same concept, same cognate class, different
#'   languages (the positive examples).
#' - Non-cognate pairs: same concept, different cognate class.
#'   Harder negatives than random cross-concept pairs, because
#'   they control for semantic similarity.
#'
#' Using same-concept negatives (sometimes called "hard negatives")
#' forces the system to rely on phonological similarity rather than
#' the trivial signal that words for different concepts tend to sound
#' different.
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
#' ### Computing word distances
#'
#' For each pair, NW alignment distance with merkmal's segment
#' distance as substitution cost.  Three systems: Descriptive
#' (articulatory categories), Distinctive (scalar features +
#' geometry), and ClassFeat (trained hybrid).
#'

systems = ["descriptive", "distinctive", "classfeat"]

results = {}
for sys_name in systems:
    sub = lambda a, b, s=sys_name: merkmal.distance(a, b, system=s)
    cog_dists = [nw_distance(a, b, sub) for a, b, *_ in cognate_pairs]
    non_dists = [nw_distance(a, b, sub) for a, b, *_ in non_cognate_pairs]
    results[sys_name] = (cog_dists, non_dists)

for sys_name in systems:
    cog_dists, non_dists = results[sys_name]
    print(f"\n  {sys_name}:")
    print(f"    cognate mean:     {mean(cog_dists):.3f}")
    print(f"    non-cognate mean: {mean(non_dists):.3f}")
    print(f"    separation:       {mean(non_dists) - mean(cog_dists):.3f}")

#'
#' All three systems show clear separation: cognate pairs have lower
#' mean distance than non-cognate pairs.  But the *degree* of
#' separation varies; this is where evaluation metrics come in.
#'
#' ## Threshold-free evaluation: AUC
#'
#' ### Why not accuracy?
#'
#' A threshold ("cognate if distance < 0.3") gives a single accuracy
#' number, but the right threshold varies by dataset, family, and
#' time depth.
#'
#' The area under the ROC curve (AUC) sidesteps this by evaluating
#' ranking quality across all thresholds.  AUC = 1.0 means perfect
#' separation; 0.5 is random.  Probabilistically (Fawcett 2006),
#' it is the chance that a randomly chosen cognate pair has a lower
#' distance than a randomly chosen non-cognate pair.
#'
#' ### Computing AUC
#'
#' We compute the Wilcoxon-Mann-Whitney statistic, which is
#' equivalent to AUC but computed directly from pairwise rank
#' comparisons:
#'


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


print("\nAUC by system:\n")
for sys_name in systems:
    cog_dists, non_dists = results[sys_name]
    auc = compute_auc(cog_dists, non_dists)
    print(f"  {sys_name:14s}  AUC = {auc:.3f}")

#'
#' Even on this small dataset, the ranking differences between
#' systems are visible.  ClassFeat, which was trained on a large
#' cognate collection, typically produces the best separation.
#'
#' On larger evaluations (58 Lexibank datasets, >300,000 forms),
#' these differences sharpen: ClassFeat achieves AUC 0.952 on the
#' full corpus and 0.937 on held-out data, compared to SCA's 0.936
#' and 0.909 respectively.
#'
#' ## Anatomy of an alignment
#'
#' ### What makes a good substitution cost?
#'
#' Alignment quality depends on the substitution cost function.
#' Some segment correspondences are more likely to reflect common
#' ancestry than others, and the cost function should reflect that.
#'
#' From our Austronesian data:
#'

print("Substitution costs (Distinctive):\n")
correspondences = [
    ("t", "k", "regular: PAN *t > Hawaiian k"),
    ("t", "t", "identity: PAN *t preserved"),
    ("a", "ɔ", "regular: vowel lowering"),
    ("b", "v", "regular: lenition (Fijian)"),
    ("p", "l", "irregular: voiceless stop ~ lateral"),
]

for a, b, label in correspondences:
    d = merkmal.distance(a, b, system="distinctive")
    print(f"  d({a}, {b}) = {d:.3f}   {label}")

#'
#' The regular correspondences (t~k, b~v) get low costs because
#' they involve single-feature changes.  The irregular pair (p~l)
#' gets a high cost because voiceless stops and laterals differ in
#' multiple features (voicing, manner, place).  This gradient
#' signal is what alignment exploits: common sound changes are
#' cheap, rare ones are expensive.
#'
#' ### Gap costs and morphological change
#'
#' Gaps model insertions and deletions, the phonological reflex of
#' morphological change (loss of affixes, epenthesis, apocope).
#' The gap cost controls the trade-off between forcing bad alignments
#' and over-segmenting:
#'

print("\nEffect of gap cost on alignment distance:\n")
sub = lambda a, b: merkmal.distance(a, b, system="distinctive")

# Malay /api/ ~ Tagalog /apoj/ (cognate, 'fire')
for gap in [0.25, 0.50, 0.75, 1.00]:
    d = nw_distance(["a", "p", "i"], ["a", "p", "o", "j"], sub, gap_cost=gap)
    print(f"  gap={gap:.2f}:  d(api, apoj) = {d:.3f}")

#'
#' Low gap costs (0.25) are lenient about extra segments, producing
#' lower distances for pairs that differ in length.  High gap costs
#' (1.00) penalise length mismatches heavily.  The default of 0.50
#' (List 2012) balances these concerns and works well across
#' diverse language families.
#'
#' ## System comparison
#'
#' ### Why systems disagree
#'
#' Different feature systems encode different theories about which
#' segment pairs should be "close."  Some diagnostic cases:
#'

print("System disagreement on diagnostic pairs:\n")
diagnostic_pairs = [
    ("p", "k", "labial ~ velar stop"),
    ("t", "k", "alveolar ~ velar stop"),
    ("b", "v", "stop ~ fricative (lenition)"),
    ("n", "ŋ", "alveolar ~ velar nasal"),
    ("a", "ɔ", "open front ~ open-mid back"),
]

print(f"  {'pair':8s}", end="")
for sys in systems:
    print(f"  {sys:>12s}", end="")
print()
print("  " + "-" * 46)

for a, b, label in diagnostic_pairs:
    print(f"  {a}~{b:5s}", end="")
    for sys in systems:
        d = merkmal.distance(a, b, system=sys)
        print(f"  {d:12.3f}", end="")
    print(f"   {label}")

#'
#' ClassFeat gives p~k distance 0.0: same sound class, maximally
#' similar.  Makes sense for cognate detection, where labial~velar
#' correspondences are common.  Distinctive gives a moderate
#' distance (the place change).  Descriptive treats each
#' articulatory difference equally, often producing larger
#' distances.  Which scoring best separates cognates from
#' non-cognates is ultimately an empirical question.
#'
#' ## The hard negative problem
#'
#' ### Same-concept negatives
#'
#' Above we used same-concept, different-cognate-class entries as
#' negatives, the "hard negative" design (List 2012, Jäger 2013).
#' It forces the distance function to rely on phonological
#' similarity, not the trivial signal that different concepts tend
#' to sound different.
#'
#' How much does it matter?
#'

sub_dist = lambda a, b: merkmal.distance(a, b, system="distinctive")

# Easy negative: different concepts
easy_neg = nw_distance(
    ["m", "a", "t", "a"],  # 'eye'
    ["b", "a", "ɲ", "u"],  # 'water'
    sub_dist,
)

# Hard negative: same concept, different cognate class
hard_neg = nw_distance(
    ["t", "a", "ŋ", "a", "n"],  # Malay 'hand' (H1)
    ["l", "i", "m", "a"],        # Hawaiian 'hand' (H2)
    sub_dist,
)

# Cognate: same concept, same class
cognate = nw_distance(
    ["m", "a", "t", "a"],  # Malay 'eye' (E1)
    ["m", "a", "k", "a"],  # Hawaiian 'eye' (E1)
    sub_dist,
)

print("Negative difficulty:\n")
print(f"  cognate (eye, Malay~Hawaiian):   {cognate:.3f}")
print(f"  easy negative (eye~water):       {easy_neg:.3f}")
print(f"  hard negative (hand, Mal~Haw):   {hard_neg:.3f}")

#'
#' The easy negative is trivially separable from the cognate pair.
#' The hard negative is much closer: it comes from the same semantic
#' field, and both forms are real words for 'hand' in their
#' respective languages.  A system that achieves high AUC on hard
#' negatives is genuinely relying on phonological structure, not
#' semantic shortcuts.
#'
#' ### Why this matters for real applications
#'
#' Real cognate detection systems are applied within
#' concept slots: given all forms for 'hand' across 50 languages,
#' partition them into cognate sets.  All negatives in this setting
#' are hard negatives.  A system evaluated only on easy negatives
#' will overestimate its real-world performance.
#'
#' ## Geometry-weighted vs flat distance
#'
#' The geometry tree assigns lower weight to deeper features:
#' place sub-features (anterior, distributed) contribute less
#' than manner features (continuant, nasal).  This reflects the
#' fact that manner differences are perceptually more salient
#' and typologically more stable.
#'
#' Does it help?  Compare geometry weights to flat (uniform) ones:
#'

print("Geometry vs flat weighting:\n")

for weight_label, weights in [("geometry (default)", None), ("flat", "flat")]:
    sub = lambda a, b, w=weights: merkmal.distance(
        a, b, system="distinctive", node_weights=w,
    )
    cog_dists = [nw_distance(a, b, sub) for a, b, *_ in cognate_pairs]
    non_dists = [nw_distance(a, b, sub) for a, b, *_ in non_cognate_pairs]
    auc = compute_auc(cog_dists, non_dists)
    sep = mean(non_dists) - mean(cog_dists)
    print(f"  {weight_label:20s}  AUC = {auc:.3f}  separation = {sep:.3f}")

#'
#' On large-scale evaluations, geometry weighting consistently
#' beats flat weighting for categorical systems (Descriptive:
#' AUC 0.931 vs 0.894 on held-out data).  It helps because
#' fine-grained place distinctions (dental~alveolar,
#' bilabial~labiodental) are common within cognate
#' correspondences and should cost less, while major manner
#' and laryngeal changes should cost more.
#'
#' ## Tone-aware cognate detection
#'
#' ### The problem
#'
#' Many of the world's language families are tonal: Sino-Tibetan,
#' Oto-Manguean, Niger-Congo, Kra-Dai, Hmong-Mien.  In these
#' families, tone is contrastive and carries historical signal:
#' cognates often preserve tonal correspondences alongside
#' segmental ones.
#'
#' Cross-linguistic databases (CLDF/Lexibank) typically encode
#' tone as Chao digit sequences separated from segments:
#' `['t', 'a', 'ŋ', '³', '⁵']`.  Without preprocessing, these
#' digits are treated as independent segments, distorting the
#' alignment.
#'
#' ### Tone merging
#'
#' merkmal's `merge_tone_digits()` attaches Chao digits to the
#' preceding vowel, producing a single tone-bearing segment whose
#' features include both segmental and tonal dimensions:
#'

raw_a = ["m", "a", "³", "⁵"]
raw_b = ["m", "a", "⁵", "¹"]
raw_c = ["p", "a", "²", "¹", "⁴"]

merged_a = merkmal.merge_tone_digits(raw_a)
merged_b = merkmal.merge_tone_digits(raw_b)
merged_c = merkmal.merge_tone_digits(raw_c)

print("Tone merging:\n")
print(f"  {raw_a} → {merged_a}")
print(f"  {raw_b} → {merged_b}")
print(f"  {raw_c} → {merged_c}")

#'
#' ### Tonal distance
#'
#' After merging, segment distance automatically includes a tonal
#' component.  We can control how much tone matters using node
#' weights:
#'

print("\nTonal cognate pair (ma³⁵ ~ ma⁵¹):\n")
sub_default = lambda a, b: merkmal.distance(a, b, system="distinctive")
sub_seg = lambda a, b: merkmal.distance(
    a, b, system="distinctive", node_weights="segmental",
)
sub_heavy = lambda a, b: merkmal.distance(
    a, b, system="distinctive", node_weights="tone-heavy",
)

for label, sub in [("default", sub_default), ("segmental", sub_seg), ("tone-heavy", sub_heavy)]:
    d = nw_distance(merged_a, merged_b, sub)
    print(f"  {label:12s}  d = {d:.3f}")

#'
#' Segmental weights silence tone (distance 0.0, since the segments
#' are otherwise identical).  Default weights add a small tonal
#' component.  Tone-heavy weights let tone dominate.
#'
#' Which setting to use depends on the family.  Where tonal
#' correspondences are regular (Sino-Tibetan, Oto-Manguean),
#' including tone helps.  Where tone is innovative or poorly
#' transcribed, segmental weights are safer.
#'
#' ### Impact on tonal data
#'
#' On the Sino-Tibetan subset of Lexibank (7 densely-toned
#' datasets), tone merging improves all feature systems:
#' ImprovedSCA gains +7.0 percentage points on the narrow tonal
#' subset, and the held-out Burmish dataset shows +9.1pp.
#' To our knowledge, no other general-purpose feature system
#' integrates Yip/Bao tonal decomposition for cognate
#' detection.
#'
#' ## Sound classes and feature distance
#'
#' ### The SCA baseline
#'
#' List's (2012) Sound Class Algorithm (SCA) maps IPA segments to
#' 23 broad classes (P for labial stops, T for alveolar stops,
#' K for velar stops, etc.).  Cognate detection then reduces to
#' class-level comparison: same class = 0, different class = 1.
#'
#' This works well (AUC 0.936 on the full corpus), because
#' the classes capture the major contrasts that matter for cognacy.
#' But binary class identity discards gradient information: p~f
#' (Grimm's Law, common) gets the same cost as p~l (rare).
#'

print("SCA-style binary vs feature-based cost:\n")

sca_like = [
    ("p", "f", "same manner region"),
    ("p", "l", "different manner"),
    ("t", "s", "assibilation"),
    ("t", "l", "unrelated"),
]

for a, b, label in sca_like:
    d_dist = merkmal.distance(a, b, system="distinctive")
    d_cf = merkmal.distance(a, b, system="classfeat")
    print(f"  {a}~{b}:  distinctive={d_dist:.3f}  classfeat={d_cf:.3f}   ({label})")

#'
#' Distinctive captures the gradient: p~f (0.214) is much closer
#' than p~l (0.783).  ClassFeat combines both: p~f gets a low cost
#' (same broad class), p~l gets a higher one.
#'
#' ### ClassFeat: trained hybrid scoring
#'
#' ClassFeat blends two components: a 24x24 matrix of learned
#' class-pair costs (P, T, K, S, N, ...; same class = 0, distant
#' classes ≈ 1) and weighted Euclidean distance over 20 continuous
#' feature dimensions.  The blending parameter alpha (≈ 0.5) and
#' 297 total parameters are trained on 46 Lexibank datasets
#' (~300,000 forms) with Powell's optimiser, maximising AUC.
#'
#' The learned weights are phonologically interpretable:
#'

sys_cf = merkmal.get_system("classfeat")

print("\nClassFeat learned parameters:\n")

# Show dimension weights
if hasattr(sys_cf, '_dimension_weights'):
    weights = sys_cf._dimension_weights
    sorted_weights = sorted(weights.items(), key=lambda x: -x[1])
    print("  Top feature dimensions by weight:")
    for dim, w in sorted_weights[:8]:
        print(f"    {dim:20s}  {w:.3f}")
    print(f"    ...")
    for dim, w in sorted_weights[-3:]:
        print(f"    {dim:20s}  {w:.3f}")

#'
#' Labial and continuant dominate, consistent with the known
#' importance of manner and place for cognate detection.  The tight
#' range of weights (typically 0.89 to 1.75) suggests the optimiser
#' found a stable, interpretable solution rather than an extreme
#' corner.
#'
#' ## Building a cognate clustering pipeline
#'
#' ### From distances to clusters
#'
#' In practice, cognate detection is a *clustering* problem:
#' given all forms for a concept across languages, partition
#' them into cognate sets.  The standard approach:
#'
#' 1. Compute pairwise NW distances.
#' 2. Apply a threshold to get a binary similarity graph.
#' 3. Cluster with a graph-based algorithm (e.g. connected
#'    components, UPGMA, or the Infomap community detection
#'    used by LingPy).
#'
#' Step 1 for the 'eye' data:
#'

eye_data = [(lang, segs) for lang, con, segs, cls in DATA if con == "eye"]

print("Pairwise distance matrix ('eye'):\n")
print(f"  {'':10s}", end="")
for lang, _ in eye_data:
    print(f"  {lang:>8s}", end="")
print()

sub = lambda a, b: merkmal.distance(a, b, system="classfeat")
matrix = {}
for i, (lang_a, segs_a) in enumerate(eye_data):
    print(f"  {lang_a:10s}", end="")
    for j, (lang_b, segs_b) in enumerate(eye_data):
        d = nw_distance(segs_a, segs_b, sub)
        matrix[(lang_a, lang_b)] = d
        print(f"  {d:8.3f}", end="")
    print()

#'
#' All distances are low (< 0.20), confirming that these forms are
#' all cognate.  In a real pipeline, we would apply a threshold
#' (e.g. 0.50) and cluster the remaining edges.  At threshold 0.50,
#' all five forms would fall into a single cluster, the correct
#' result.
#'
#' ### Threshold sensitivity
#'
#' The threshold is the weak point.  Too low and it splits genuine
#' cognates; too high and it merges unrelated forms.  The right
#' value varies by family, time depth, and transcription quality.
#'
#' AUC avoids this for evaluation, but real clustering needs a
#' concrete threshold.  Two strategies: (1) tune on a development
#' set of gold-standard cognacy judgements, or (2) use algorithms
#' that take continuous distances directly (Infomap, UPGMA).
#'

thresholds = [0.20, 0.30, 0.40, 0.50, 0.60]
all_data = [(lang, con, segs, cls) for lang, con, segs, cls in DATA]
concepts = sorted(set(con for _, con, _, _ in DATA))

print("\nClustering accuracy at different thresholds:\n")
for threshold in thresholds:
    correct = 0
    total = 0
    for concept in concepts:
        entries = [(l, s, c) for l, co, s, c in all_data if co == concept]
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                _, segs_a, cls_a = entries[i]
                _, segs_b, cls_b = entries[j]
                d = nw_distance(segs_a, segs_b, sub)
                predicted_cognate = d < threshold
                actual_cognate = cls_a == cls_b
                if predicted_cognate == actual_cognate:
                    correct += 1
                total += 1
    acc = correct / total if total > 0 else 0.0
    print(f"  threshold = {threshold:.2f}:  accuracy = {acc:.3f}  ({correct}/{total})")

#'
#' The accuracy varies significantly with the threshold, illustrating
#' why threshold-free evaluation (AUC) is preferred for comparing
#' systems, and why threshold tuning is essential for deployment.
#'
#' ## Error analysis
#'
#' Aggregate metrics hide individual failures.  The most informative
#' cases are the system's worst mistakes: the highest-distance cognate
#' pair (would be rejected first) and the lowest-distance non-cognate
#' pair (would be accepted first).
#'

# Collect all scored pairs with metadata
sub_cf = lambda a, b: merkmal.distance(a, b, system="classfeat")
scored_pairs = []
for concept in concepts:
    entries = [(l, s, c) for l, co, s, c in all_data if co == concept]
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            lang_a, segs_a, cls_a = entries[i]
            lang_b, segs_b, cls_b = entries[j]
            d = nw_distance(segs_a, segs_b, sub_cf)
            is_cognate = cls_a == cls_b
            scored_pairs.append((d, is_cognate, lang_a, lang_b, concept,
                                 segs_a, segs_b, cls_a, cls_b))

# Worst cognate: highest distance among true cognates
cognates_scored = [p for p in scored_pairs if p[1]]
worst_cognate = max(cognates_scored, key=lambda p: p[0])

# Best non-cognate: lowest distance among true non-cognates
non_cognates_scored = [p for p in scored_pairs if not p[1]]
best_non_cognate = min(non_cognates_scored, key=lambda p: p[0])

print("Most confident errors (ClassFeat):\n")

d, _, la, lb, con, sa, sb, ca, cb = worst_cognate
print(f"  Hardest cognate (would be rejected first):")
print(f"    {la} /{' '.join(sa)}/ ~ {lb} /{' '.join(sb)}/  ('{con}', {ca})")
print(f"    distance = {d:.3f}")

d, _, la, lb, con, sa, sb, ca, cb = best_non_cognate
print(f"\n  Easiest false match (would be accepted first):")
print(f"    {la} /{' '.join(sa)}/ ~ {lb} /{' '.join(sb)}/  ('{con}', {ca} vs {cb})")
print(f"    distance = {d:.3f}")

#'
#' The hardest cognate typically involves heavy phonological
#' divergence (accumulated sound changes, length mismatches
#' forcing gaps).  The easiest false match tends to be accidental
#' similarity: unrelated forms that happen to share manner and
#' place features.
#'
#' ### Vowel vs consonant bias
#'
#' Distance functions can have systematic biases.  A common one:
#' vowel pairs tend to have smaller distances than consonant pairs.
#' Vowels vary along fewer dimensions (height, backness, rounding),
#' while consonants spread across place, manner, voicing, and
#' secondary articulations.
#'

vowel_pairs = [("a", "i"), ("a", "u"), ("i", "u"), ("e", "o"), ("a", "e")]
cons_pairs = [("p", "k"), ("t", "n"), ("s", "l"), ("b", "ŋ"), ("f", "d")]

v_dists = [merkmal.distance(a, b, system="distinctive") for a, b in vowel_pairs]
c_dists = [merkmal.distance(a, b, system="distinctive") for a, b in cons_pairs]

print("\nVowel vs consonant distance (Distinctive):\n")
print(f"  vowel pairs:     mean = {mean(v_dists):.3f}  (range {min(v_dists):.3f} to {max(v_dists):.3f})")
print(f"  consonant pairs: mean = {mean(c_dists):.3f}  (range {min(c_dists):.3f} to {max(c_dists):.3f})")

#'
#' If vowel distances are systematically lower, the aligner will
#' prefer to align vowels (cheap) and gap consonants (moderate
#' cost), even when the consonant correspondence is historically
#' regular.  This is a known bias in feature-based distance methods
#' and one reason why sound-class-based systems like SCA remain
#' competitive: they normalise the vowel/consonant asymmetry by
#' mapping both to coarse classes with similar cost scales.
#'
#' These patterns affect all feature-based distance systems, not
#' just merkmal.  Keep this in mind when interpreting results
#' or designing hybrid approaches.
#'
#' ## Methodological considerations
#'
#' ### Distance as a baseline, not the paradigm
#'
#' This tutorial used phonological distance with a fixed threshold
#' as a baseline cognate detection strategy.  We chose it because
#' it directly exercises merkmal's distance API, but production
#' cognate detection systems go well beyond distance thresholding.
#'
#' The main alternatives:
#'
#' - Sound correspondence models (List 2012, Jäger 2013) learn
#'   language-pair-specific substitution scores, capturing the
#'   fact that *t*~*k* is regular in Austronesian but not
#'   Indo-European.  LexStat (List 2012) combines SCA-based
#'   distance with PMI-derived correspondence weights and
#'   consistently outperforms pure distance methods.
#'
#' - Probabilistic and Bayesian approaches (Bouchard-Côté et al.
#'   2013) model sound change as a stochastic process with
#'   directionality and branch-specific rates, jointly inferring
#'   cognacy and phylogeny.
#'
#' - Embedding and neural approaches represent words as continuous
#'   vectors and classify cognacy with learned similarity functions.
#'
#' The distance function is a component, not a complete pipeline.
#' Segment-level costs can feed into any of these
#' richer models: as initial substitution scores, alignment priors,
#' or features in a learned classifier.
#'
#' ### Assumptions of the distance metric
#'
#' The distance function is a proper metric: symmetric
#' (d(a, b) = d(b, a)) and satisfying the triangle inequality.
#' Both properties are useful for downstream algorithms (clustering,
#' nearest-neighbour search), but neither holds for historical
#' sound change:
#'
#' - Symmetry: sound change is directional.  Lenition
#'   (p → f) is typologically common; fortition (f → p) is rare.
#'   A symmetric distance treats both directions equally.  This is
#'   appropriate for measuring *structural similarity* between
#'   segments, but it does not model *diachronic probability*.
#'   Capturing directionality requires transition probabilities or
#'   weighted correspondence matrices, machinery that sits above
#'   the feature layer.
#'
#' - Independence: the distance function scores each aligned
#'   segment pair independently.  In reality, segments interact:
#'   vowel harmony, consonant harmony, and compensatory lengthening
#'   all create dependencies across positions.  Alignment-based
#'   models with position-specific scoring (List 2014) or
#'   correspondence-aware models partially address this.
#'
#' - Compositionality: feature distance assumes that a segment's
#'   phonological identity is the sum of its features.  This misses
#'   emergent properties: clicks, for example, have phonological
#'   behaviour that is not fully predicted by the union of their
#'   component features.
#'
#' These are inherent properties of feature-based distance.
#' Richer models are needed for final cognacy decisions and
#' phylogenetic inference.
#'
#' ### What distance captures, and what it misses
#'
#' Beyond the metric assumptions above, phonological distance has
#' further practical limitations:
#'
#' 1. Semantic shift: cognates can diverge in meaning
#'    (English *deer* ~ German *Tier* 'animal').  Distance-based
#'    methods only work within a shared concept slot.
#'
#' 2. Borrowing: loanwords can have low distance to genuine
#'    cognates.  Japanese *pan* 'bread' (< Portuguese *pão*) would
#'    score as a near-perfect match to Spanish *pan*, but it's a
#'    borrowing, not a cognate.
#'
#' 3. Extreme time depth: at sufficient time depth (>8,000
#'    years?), sound change accumulates to the point where cognates
#'    are phonologically unrecognisable.  No distance function can
#'    recover the signal.
#'
#' 4. Irregular sound change: sporadic changes (metathesis,
#'    haplology, analogical levelling) produce large distances
#'    that overstate the phonological divergence.
#'
#' All of these affect distance-based approaches generally,
#' not just merkmal.
#'
#' ### Evaluation pitfalls
#'
#' Several traps can inflate reported accuracy:
#'
#' - Easy negatives: cross-concept pairs as negatives inflate AUC
#'   because the system can exploit the trivial signal that
#'   different concepts sound different.  Use same-concept
#'   negatives.
#'
#' - Language-level leakage: if the same language pair appears in
#'   training and test data, the system may learn pair-specific
#'   biases.  Hold out entire datasets, not individual pairs.
#'
#' - Sample imbalance: most concept slots have many more non-cognate
#'   than cognate pairs.  AUC handles this; accuracy does not.
#'
#' - Transcription quality: CLDF datasets vary in granularity
#'   and accuracy.  Good performance on careful transcriptions
#'   does not guarantee good performance on coarser ones.
#'
#' ## References
#'
#' - Blust, R. (1999). Subgrouping, circularity and extinction: some issues in Austronesian comparative linguistics. In E. Zeitoun & P. J.-K. Li (Eds.), *Selected papers from the Eighth International Conference on Austronesian Linguistics* (pp. 31-94). Institute of Linguistics, Academia Sinica.
#' - Covington, M. A. (1996). An algorithm to align words for historical comparison. *Computational Linguistics*, 22(4), 481-496.
#' - Covington, M. A. (1998). Alignment of multiple languages for historical comparison. In *Proceedings of COLING-ACL 1998* (pp. 275-279).
#' - Fawcett, T. (2006). An introduction to ROC analysis. *Pattern Recognition Letters*, 27(8), 861-874.
#' - Greenhill, S. J., Blust, R., & Gray, R. D. (2008). The Austronesian Basic Vocabulary Database: from bioinformatics to lexomics. *Evolutionary Bioinformatics*, 4, 271-283.
#' - Jäger, G. (2013). Phylogenetic inference from word lists using weighted alignment with empirically determined weights. *Language Dynamics and Change*, 3(2), 245-291.
#' - List, J.-M. (2012). SCA: phonetic alignment based on sound classes. In M. Slavkovik & D. Lassiter (Eds.), *New directions in logic, language and computation* (pp. 32-51). Springer.
#' - List, J.-M. (2014). *Sequence comparison in historical linguistics*. Düsseldorf University Press.
#' - Bouchard-Côté, A., Hall, D., Griffiths, T. L., & Klein, D. (2013). Automated reconstruction of ancient languages using probabilistic models of sound change. *Proceedings of the National Academy of Sciences*, 110(11), 4224-4229.
#' - Needleman, S. B., & Wunsch, C. D. (1970). A general method applicable to the search for similarities in the amino acid sequence of two proteins. *Journal of Molecular Biology*, 48(3), 443-453.
