"""Sweep the distance between a bare tone segment and a segmental unit.

Kept because it is the evidence behind D8/D9 in REFERENCE_LIBRARY_PLAN.md: the
tier leaf's weight should land where this sweep says, and if the tone
representation changes this is how to re-derive the target.

    bench/sweep_tone_distance.py <bdpa-checkout>

The scorer here is a shim, not the library: bare tone tokens do not resolve yet,
so this parameterizes what their distance to a segment *would* be. Once they do
resolve, this should be re-run against the real implementation to confirm the
chosen weight still sits at the optimum.
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
    """merkmal for segments; ordinal Chao for tone~tone; T for tone~segment."""
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
pairs = bench.gold_pairs(bdpa)
tone_pairs = [p for p in pairs if any(levels(t) is not None for t in p[0] + p[1])]
print(f"BDPA pairs total {len(pairs)}; involving at least one tone token: {len(tone_pairs)}")
half = len(tone_pairs) // 2
dev, test = tone_pairs[:half], tone_pairs[half:]
print(f"dev {len(dev)} / test {len(test)}\n")

print(f"{'T':>6} {'gap':>9} {'dev col':>9} {'test col':>9} {'test perf':>13}")
rows=[]
for target in [0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,1.2,1.5,2.0]:
    sub = make_sub(target)
    gap = max(bench.GAP_GRID, key=lambda g: bench.score(dev, sub, g)[0])
    dacc, _ = bench.score(dev, sub, gap)
    tacc, tperf = bench.score(test, sub, gap)
    rows.append((target, gap, dacc, tacc, tperf))
    print(f"{target:6.2f} {gap:9.2f} {100*dacc:8.2f}% {100*tacc:8.2f}% {100*tperf:12.2f}%")

best = max(rows, key=lambda r: r[2])  # choose on dev, report on test
print(f"\nchosen on dev: T={best[0]:.2f} gap={best[1]:.2f}"
      f" -> test {100 * best[3]:.2f}% col, {100 * best[4]:.2f}% perfect")
print("\nBootstrap against the geometry's own value and against a flat ceiling:")
for other, ogap, label in [(0.5, 0.80, "0.50 (the geometry's natural value)"),
                           (1.0, 0.50, "1.00 (flat ceiling)")]:
    d, lo, hi = bench.bootstrap_delta(test, make_sub(best[0]), best[1], make_sub(other), ogap)
    verdict = "not significant" if lo < 0 < hi else "SIGNIFICANT"
    print(f"  T={best[0]:.2f} vs {label:34} {100 * d:+6.2f}%"
          f"  [{100 * lo:+.2f}, {100 * hi:+.2f}]  {verdict}")
