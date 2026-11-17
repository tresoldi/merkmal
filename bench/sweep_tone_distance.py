"""Sweep the cost of aligning a bare tone with a segment, on BDPA.

This is the evidence for the cross-tier cost (`tier_policy.cross_tier_cost`
in data/geometries/clements-hume.json; docs/guide/c-api.md, Distance with
coverage): the script reports the value above which every cost gives the same
alignments. If the tone representation changes, it re-derives that value.

    bench/sweep_tone_distance.py <bdpa-checkout>

The substitution function is not the library's alone, so that the cost can be
varied without rebuilding: it uses merkmal for two segments, its own mean
difference of Chao levels for two tones, and the swept constant T for a tone
against a segment.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench_alignment as bench

SUP = "⁰¹²³⁴⁵⁶⁷⁸⁹"
LET = "˩˨˧˦˥"
def levels(t):
    if t and all(c in SUP for c in t):
        return [SUP.index(c) for c in t]
    if t and all(c in LET for c in t):
        return [LET.index(c) + 1 for c in t]
    return None

def make_sub(target, system="distinctive"):
    """A substitution cost: merkmal for two segments, the mean Chao-level
    difference for two tones, and ``target`` for a tone against a segment."""
    base = bench.merkmal_sub(system)
    cache = {}

    def f(a, b):
        k = (a, b)
        if k in cache:
            return cache[k]
        la, lb = levels(a), levels(b)
        if la is not None or lb is not None:
            if la is None or lb is None:
                v = target
            elif a == b:
                v = 0.0
            else:
                n = max(len(la), len(lb))
                pa = [la[min(i, len(la) - 1)] for i in range(n)]
                pb = [lb[min(i, len(lb) - 1)] for i in range(n)]
                v = sum(abs(x - y) for x, y in zip(pa, pb, strict=True)) / (4.0 * n)
        else:
            v = base(a, b)
        cache[k] = v
        return v
    return f

bdpa = Path(sys.argv[1] if len(sys.argv) > 1 else "~/lexibank_clone/bdpa").expanduser()

# Split at alignment boundaries, not at pair boundaries. Up to three pairs come
# from the same alignment (same wordlist, same doculects), so a pair-level split
# would put related pairs on both sides and leak test data into tuning.
groups = bench.gold_pairs_grouped(bdpa)
tone_groups = {
    name: prs for name, prs in groups.items()
    if any(levels(t) is not None for pr in prs for t in pr[0] + pr[1])
}
keys = sorted(tone_groups)
half = len(keys) // 2
dev = [pr for k in keys[:half] for pr in tone_groups[k]]
test = [pr for k in keys[half:] for pr in tone_groups[k]]
n_pairs = sum(len(v) for v in tone_groups.values())
print(f"alignments containing tone: {len(keys)}; pairs from them: {n_pairs}")
print(f"dev {len(dev)} / test {len(test)}  (split between alignments)\n")

print(f"{'T':>6} {'gap':>9} {'dev col':>9} {'test col':>9} {'test perf':>13}")
rows=[]
for target in [0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,1.2,1.5,2.0]:
    sub = make_sub(target)
    gap = max(bench.GAP_GRID, key=lambda g: bench.score(dev, sub, g)[0])
    dacc, _ = bench.score(dev, sub, gap)
    tacc, tperf = bench.score(test, sub, gap)
    rows.append((target, gap, dacc, tacc, tperf))
    print(f"{target:6.2f} {gap:9.2f} {100*dacc:8.2f}% {100*tacc:8.2f}% {100*tperf:12.2f}%")

# Report the saturation point, not an argmax. Above some value the aligner no
# longer matches a tone with a segment, and every larger cost, including an
# infinite one, produces identical alignments. An argmax over that flat region
# would report a value the data cannot distinguish from any other value in the
# region, or from treating tone and segment as incomparable.
top = max(r[3] for r in rows)
saturated = [r for r in rows if abs(r[3] - top) < 1e-12]
floor_t = min(r[0] for r in saturated)
print(f"\nsaturation: every T >= {floor_t:.2f} gives identical results "
      f"({100 * top:.2f}% test column accuracy).")
print(f"  values in the saturated region: {[f'{r[0]:.2f}' for r in saturated]}")
if len(saturated) > 1:
    print("  The benchmark therefore cannot pick a cost inside this region, and")
    print("  cannot distinguish any of them from declaring tone and segments")
    print("  incomparable. It identifies a rule, not a weight.")

low = min(rows, key=lambda r: abs(r[0] - 0.5))
best = min(saturated, key=lambda r: r[0])
d, lo, hi = bench.bootstrap_delta(test, make_sub(best[0]), best[1], make_sub(low[0]), low[1])
verdict = "not significant" if lo < 0 < hi else "SIGNIFICANT"
print(f"\nT={best[0]:.2f} (saturation floor) vs T={low[0]:.2f} (the geometry's own value):"
      f" {100 * d:+.2f}%  [{100 * lo:+.2f}, {100 * hi:+.2f}]  {verdict}")
