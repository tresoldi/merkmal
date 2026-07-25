#' ---
#' title: "Comparing Feature Systems Across Frameworks"
#' ---
#'
#' # Comparing Feature Systems Across Frameworks
#'
#' No single feature system captures all phonological generalisations
#' (Mielke 2008, *Typological Evidence*). Different theoretical traditions assign different
#' features, and those differences matter for downstream tasks.
#'
#' merkmal has nine built-in systems.  The same segment gets
#' different representations in each, those representations
#' produce different distances, and the choice of system
#' matters more than you might expect.
#'

import merkmal
import statistics

#'
#' ## Available systems
#'
#' All nine are accessible through the same API:
#'

for name in merkmal.list_systems():
    sys = merkmal.get_system(name)
    n = len(sys.list_graphemes())
    print(f"  {name:15s}  {sys.representation_kind:12s}  {n:5d} segments")

#'
#' The systems fall into two families:
#'
#' - Categorical (Descriptive, Broad, Distinctive): features are
#'   sets of labels (`{voiceless, stop, bilabial}`). These share
#'   a common CLTS-derived segment table (778 entries) and support
#'   compositional decomposition for full IPA coverage.
#'
#' - Valued (PBase, PHOIBLE, ClassFeat): features are
#'   key-value mappings (`{voice: -, continuant: -, labial: +}`).
#'   These come from external databases with different inventories.
#'
#' ## Same segment, different representations
#'
#' How /p/ looks across systems:
#'

print("=== /p/ across systems ===\n")

for name in ["descriptive", "distinctive", "pbase-hc", "phoible"]:
    feats = merkmal.get_features("p", system=name)
    if feats:
        print(f"  {name}:")
        print(f"    {sorted(feats)}\n")

#'
#' Descriptive gives articulatory labels from the IPA description.
#' PBase-HC uses the Halle-Clements framework with multi-valued
#' features (the `=+`, `=-`, `=n` notation).  PHOIBLE gives binary
#' features from its SPE-derived system.
#'
#' These encode different theoretical commitments about which
#' properties are phonologically relevant.
#'
#' ### Theoretical traditions behind the systems
#'
#' Each feature system reflects a theoretical tradition.
#' The systems in merkmal descend from four of them:
#'
#' - SPE-derived (Distinctive, PBase-SPE): binary features in the
#'   tradition of Chomsky & Halle (1968).  Each segment is a bundle of
#'   ±values; phonological rules refer to natural classes defined by
#'   feature conjunctions.  The feature inventory is fixed by Universal
#'   Grammar.
#'
#' - Multi-valued / substance-based (PBase-HC, PBase-UFTC):
#'   features can take more than two values, and their content is
#'   grounded in articulatory or acoustic substance (Clements 1985,
#'   Halle 1995).  The neutral state (`=n`) implements a form of
#'   underspecification directly in the representation.
#'
#' - Articulatory-descriptive (Descriptive, Broad): features are
#'   IPA-style articulatory labels rather than abstract phonological
#'   primes.  This makes no commitment to a universal feature inventory;
#'   it simply describes how segments are produced.
#'
#' - Hybrid / trained (ClassFeat): combines sound class identity
#'   (following List 2012) with continuous feature dimensions, trained
#'   on cognate detection data.  The feature space is shaped by
#'   empirical performance, not by phonological theory alone.
#'
#' These traditions make different predictions about what constitutes
#' a "small" phonological change.  An SPE system treats voicing and
#' continuancy as equally weighted single-feature changes; an
#' articulatory system may distinguish them because they involve
#' different numbers of articulatory labels.  The choice depends
#' on what question you are asking.
#'
#' Having multiple systems in the same library means you can run the
#' same analysis under different assumptions and compare, rather than
#' choosing a framework up front.
#'
#' ## How representations affect distance
#'
#' Different feature sets produce different distances. Here are
#' consonant pairs that show where the systems diverge:
#'

pairs = [
    ("p", "b", "voicing"),
    ("p", "f", "manner"),
    ("p", "k", "place"),
    ("p", "m", "manner + nasality"),
    ("s", "ʃ", "place (sibilants)"),
    ("t", "d", "voicing"),
]

systems = ["descriptive", "distinctive", "classfeat"]
header = f"  {'pair':8s} {'type':20s}" + "".join(f" {s:>12s}" for s in systems)
print(header)
print("  " + "-" * (len(header) - 2))

for a, b, desc in pairs:
    dists = []
    for sys in systems:
        d = merkmal.distance(a, b, system=sys)
        dists.append(f"{d:12.3f}")
    print(f"  {a}~{b:5s} {desc:20s}" + "".join(dists))

#'
#' A few things to notice.  Distinctive treats p~b and p~f as
#' equidistant (both single-feature changes), while Descriptive
#' distinguishes them because its label set is richer.  ClassFeat
#' assigns different costs again, because it blends learned
#' class-pair costs with continuous feature distances.  But all
#' three systems agree that manner+nasality changes (p~m) are
#' larger than single-feature changes.
#'
#' ## Cross-system distance profiles
#'
#' A more systematic comparison: for a set of segments, compute
#' all pairwise distances and see how systems rank them.
#'

segments = ["p", "t", "k", "b", "d", "ɡ", "m", "n", "ŋ", "f", "s"]

print("=== Pairwise distance comparison ===\n")
print("Pairs where systems disagree most on relative ranking:\n")

# Collect all pairwise distances for two systems
desc_dists = {}
dist_dists = {}
for i, a in enumerate(segments):
    for b in segments[i+1:]:
        desc_dists[(a, b)] = merkmal.distance(a, b, system="descriptive")
        dist_dists[(a, b)] = merkmal.distance(a, b, system="distinctive")

# Find pairs with largest rank difference
desc_ranked = sorted(desc_dists.keys(), key=lambda k: desc_dists[k])
dist_ranked = sorted(dist_dists.keys(), key=lambda k: dist_dists[k])

desc_rank = {k: i for i, k in enumerate(desc_ranked)}
dist_rank = {k: i for i, k in enumerate(dist_ranked)}

diffs = [(abs(desc_rank[k] - dist_rank[k]), k) for k in desc_dists]
diffs.sort(reverse=True)

print(f"  {'pair':8s} {'desc dist':>10s} {'desc rank':>10s} {'dist dist':>10s} {'dist rank':>10s}")
print("  " + "-" * 48)
for _, (a, b) in diffs[:8]:
    print(f"  {a}~{b:5s} {desc_dists[(a,b)]:10.3f} {desc_rank[(a,b)]:10d}"
          f" {dist_dists[(a,b)]:10.3f} {dist_rank[(a,b)]:10d}")

#'
#' Where the rankings diverge, the two systems disagree about
#' phonological similarity. These are different theoretical
#' stances on what counts as a "small" change.
#'
#' ## Coverage comparison
#'
#' Not all systems handle all segments.  Here is a challenging
#' inventory with modified and rare segments:
#'

test_segments = [
    "p", "tʰ", "kʷ", "ɓ", "ɗ",
    "t͡s", "d͡ʒ", "ɲ",
    "ã", "ɨ", "ɤ",
    "ʘ", "ǀ",
]

print(f"Testing {len(test_segments)} segments:\n")
for name in ["descriptive", "pbase-hc", "phoible"]:
    resolved = 0
    failed = []
    for seg in test_segments:
        if merkmal.get_features(seg, system=name) is not None:
            resolved += 1
        else:
            failed.append(seg)
    print(f"  {name:15s}  {resolved}/{len(test_segments)} resolved")
    if failed:
        print(f"    missing: {', '.join(failed)}")

#'
#' Descriptive achieves full coverage through compositional
#' decomposition: unknown segments are broken into a known base
#' plus modifiers.  PBase-HC has a smaller table (1,068 entries) and
#' no decomposition, so rare segments may fail.  PHOIBLE has the
#' largest table (3,142 entries) but still no decomposition, so
#' unusual combinations can miss.
#'
#' ## Choosing a system
#'
#' Rough guide:
#'
#' | System | Best for | Strengths |
#' |--------|----------|-----------|
#' | Descriptive | General-purpose analysis | Full coverage, interpretable labels |
#' | Distinctive | Feature geometry research | Scalar features aligned with tree leaves |
#' | ClassFeat | Cognate detection | Trained on cognate data, highest AUC |
#' | PBase-HC | Theory comparison | Halle-Clements multi-state features |
#' | PHOIBLE | Typological surveys | Largest segment inventory |
#'
#' You can also register your own system and use it through the
#' same API.
#'
#'
#' ## Feature economy and inventory structure
#'
#' Clements (2003) proposed that phonological inventories are
#' feature-economical: they reuse features across segments,
#' yielding symmetric systems.  The minimal matrix lets us
#' test this.
#'
#' Compare a maximally economical 6-consonant inventory with
#' a non-economical one of the same size:
#'

# Economical: full exploitation of voicing × 3 places
econ = ["p", "b", "t", "d", "k", "ɡ"]
# Non-economical: gaps that waste feature contrasts
nonecon = ["p", "d", "k", "f", "n", "l"]

for label, inv in [("Economical (p b t d k ɡ)", econ),
                   ("Non-economical (p d k f n l)", nonecon)]:
    m = merkmal.minimal_matrix(inv, system="distinctive")
    print(f"{label}:")
    print(f"  {len(inv)} segments, {len(m.columns)} features needed")
    ratio = len(inv) / len(m.columns) if m.columns else 0
    print(f"  economy ratio (segments/features): {ratio:.2f}")
    print(merkmal.tabulate_matrix(m))
    print()

#'
#' Both inventories need the same number of features here, but
#' the economical one fully cross-classifies voicing and place:
#' every feature combination is filled.  The non-economical
#' inventory has gaps, so it wastes potential contrasts even though
#' the raw feature count is the same.
#'
#' Clements' prediction is that natural languages favour the first
#' pattern. The economy ratio (segments / features) quantifies this:
#' higher values indicate more economical inventories.
#'
#' ## The Descriptive / Distinctive divergence
#'
#' The Descriptive and Distinctive systems give categorically different
#' answers for certain segment pairs, because they encode different
#' theories of phonological similarity.
#'
#' The reason is that Descriptive features are articulatory labels
#' (present or absent), while Distinctive features are scalar
#' dimensions mapped to the geometry tree (each taking a value from
#' a closed set).  Concretely:
#'
#' - Descriptive treats /e/ and /ɛ/ as different (different height
#'   labels), but Distinctive collapses them (both map to 0.0 on the
#'   `high` dimension).
#' - Descriptive distinguishes /p/~/b/ (losing `voiceless` and
#'   gaining `voiced`) from /p/~/f/ (losing `stop`/`bilabial` and
#'   gaining `fricative`/`labio-dental`), but Distinctive treats both
#'   as single-feature changes.
#'

print("Pairs where Descriptive ≠ Distinctive:\n")
diagnostic_pairs = [
    ("e", "ɛ", "mid vowels"),
    ("o", "ɔ", "mid rounded vowels"),
    ("p", "b", "voicing (stops)"),
    ("p", "f", "manner (Grimm)"),
    ("s", "ʃ", "sibilant place"),
    ("t", "d̪", "dental vs alveolar"),
]

print(f"  {'pair':8s} {'type':22s} {'descriptive':>12s} {'distinctive':>12s} {'ratio':>8s}")
print("  " + "-" * 68)
for a, b, desc in diagnostic_pairs:
    d_desc = merkmal.distance(a, b, system="descriptive")
    d_dist = merkmal.distance(a, b, system="distinctive")
    ratio = d_desc / d_dist if d_dist > 0 else float("inf")
    print(f"  {a}~{b:5s} {desc:22s} {d_desc:12.3f} {d_dist:12.3f} {ratio:8.2f}")

#'
#' The ratio column shows the pattern.  Where Descriptive sees
#' multiple label changes and Distinctive sees one dimension change,
#' Descriptive produces larger distances.  Where Distinctive's
#' scalar mapping collapses a contrast (e~ɛ), Descriptive preserves
#' it.  Which behaviour you want depends on your analysis.
#'
#' ## Valued features and multi-state systems
#'
#' PBase systems use multi-state features beyond binary +/−.
#' Here is how that affects representation:
#'

# Compare representations of the same segments across valued systems
test_segs = ["p", "t", "n", "s", "l"]

print("Multi-state features in PBase-HC:\n")
for seg in test_segs:
    feats = merkmal.get_features(seg, system="pbase-hc")
    if feats:
        # Extract features with non-trivial states
        interesting = sorted(f for f in feats if "=+" in f or "=n" in f)
        print(f"  /{seg}/  positive/neutral: {interesting}")

#'
#' The `=n` values (neutral state) encode a third possibility
#' beyond +/−: features not relevant to the segment.  Unlike the
#' minimal matrices above, which derive underspecification from the
#' inventory, PBase-HC bakes it into the representation itself.
#'
#' ## Distance matrices as typological signatures
#'
#' A language's consonant inventory, viewed through its pairwise
#' distance matrix, is a typological fingerprint. The distribution
#' of distances reflects how the language organises its phonological
#' space.
#'
#' Two typologically different inventories:
#'

# Hawaiian-type: small, symmetric
hawaiian = ["p", "k", "ʔ", "m", "n", "h", "l", "w"]
# Georgian-type: rich in manner contrasts
georgian = ["p", "pʰ", "b", "t", "tʰ", "d", "k", "kʰ", "ɡ"]

for label, inv in [("Hawaiian-type", hawaiian), ("Georgian-type", georgian)]:
    dists = []
    for i, a in enumerate(inv):
        for b in inv[i+1:]:
            d = merkmal.distance(a, b, system="distinctive")
            dists.append(d)
    mean_d = statistics.mean(dists)
    stdev_d = statistics.stdev(dists) if len(dists) > 1 else 0
    min_d = min(dists)
    max_d = max(dists)
    print(f"{label} ({len(inv)} segments, {len(dists)} pairs):")
    print(f"  mean distance:  {mean_d:.3f}")
    print(f"  std deviation:  {stdev_d:.3f}")
    print(f"  range:          [{min_d:.3f}, {max_d:.3f}]")
    print(f"  dispersion (stdev/mean): {stdev_d/mean_d:.3f}")
    print()

#'
#' The Hawaiian-type inventory shows higher mean distance and
#' dispersion: its segments are spread far apart in feature space,
#' as expected from an inventory that favours maximal perceptual
#' contrast (Liljencrants & Lindblom 1972). The Georgian-type
#' inventory clusters segments more tightly because it packs many
#' segments into the same manner/place space, differing mainly in
#' laryngeal features (plain, aspirated, voiced).
#'
#' Two theories of inventory structure are in tension here:
#' Dispersion Theory (Flemming 2002) predicts that inventories
#' maximise perceptual distance, while Feature Economy
#' (Clements 2003) predicts maximal reuse of features.  The
#' distance matrix lets you quantify where a language falls
#' between them.
#'
#' ## System agreement and disagreement as a research tool
#'
#' ### Why rank-based comparison?
#'
#' Different feature systems produce distance values on different
#' scales: Descriptive's set-overlap metric and Distinctive's
#' geometry-weighted scalar metric are not commensurable. A distance
#' of 0.3 in one system does not "mean" the same as 0.3 in the other.
#' Comparing raw magnitudes across systems would be meaningless.
#'
#' The right comparison is at the ranking level: do the two systems
#' agree on which pairs are *more* or *less* similar?  Spearman's ρ
#' (used here) and AUC (used in the paper's cognate detection
#' evaluation) are both rank-based, invariant to monotonic
#' transformations of the distance scale.
#'
#' ### Measuring agreement
#'
#' Agreement across frameworks suggests the ranking is robust.
#' Disagreements point to the segments and contrasts where
#' theoretical assumptions diverge.
#'
#' Spearman ρ between Descriptive and Distinctive over a larger
#' set of consonant pairs:
#'

segments = ["p", "t", "k", "b", "d", "ɡ", "m", "n", "ŋ",
            "f", "s", "ʃ", "x", "v", "z", "l", "r", "j", "w"]

desc_dists = []
dist_dists = []
pair_labels = []

for i, a in enumerate(segments):
    for b in segments[i+1:]:
        desc_dists.append(merkmal.distance(a, b, system="descriptive"))
        dist_dists.append(merkmal.distance(a, b, system="distinctive"))
        pair_labels.append(f"{a}~{b}")

# Compute Spearman rank correlation manually
def rank(values):
    sorted_idx = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0] * len(values)
    for rank_val, idx in enumerate(sorted_idx):
        ranks[idx] = rank_val
    return ranks

desc_ranks = rank(desc_dists)
dist_ranks = rank(dist_dists)
n = len(desc_ranks)
d_sq_sum = sum((dr - tr) ** 2 for dr, tr in zip(desc_ranks, dist_ranks))
rho = 1 - (6 * d_sq_sum) / (n * (n**2 - 1))

print(f"Spearman ρ (Descriptive vs Distinctive): {rho:.3f}")
print(f"  over {n} consonant pairs from {len(segments)} segments")
print(f"  ρ = 1.0 would mean perfect rank agreement")

#'
#' A high ρ means the two systems largely agree on relative
#' similarity; disagreements are on fine details, not gross
#' rankings.
#'
#' For cognate detection, the practical upshot: results are probably
#' robust across system choice for clearly cognate or clearly
#' non-cognate pairs.  The system choice starts to matter for
#' borderline cases, which is also where theoretical assumptions
#' deserve the most scrutiny.
#'
#' ## References
#'
#' - Chomsky, N., & Halle, M. (1968). *The sound pattern of English*. Harper & Row.
#' - Clements, G. N. (1985). The geometry of phonological features. *Phonology Yearbook*, 2, 225-252.
#' - Clements, G. N. (2003). Feature economy in sound systems. *Phonology*, 20(3), 287-333.
#' - Flemming, E. (2002). *Auditory representations in phonology*. Routledge.
#' - Halle, M. (1995). Feature geometry and feature spreading. *Linguistic Inquiry*, 26(1), 1-46.
#' - Liljencrants, J., & Lindblom, B. (1972). Numerical simulation of vowel quality systems: the role of perceptual contrast. *Language*, 48(4), 839-862.
#' - List, J.-M. (2012). SCA: phonetic alignment based on sound classes. In M. Slavkovik & D. Lassiter (Eds.), *New directions in logic, language and computation* (pp. 32-51). Springer.
#' - Mielke, J. (2008). *The emergence of distinctive features*. Oxford University Press.
