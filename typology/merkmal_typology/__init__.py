"""Language-indexed phonological typology, built on merkmal's segment distances.

Deliberately a companion package rather than part of the C library. Two reasons,
and the second is the one that matters:

1. The data is 500 KB against the core's 544 KB of compiled tables, and none of
   it is needed to score a segment.
2. Sampling weight, genealogy and areal membership are exactly what the core has
   spent its life refusing to have opinions about. Keeping them out here means
   the discipline in `merkmal`'s README survives the arrival of a language
   column, instead of being quietly dropped because there is now one.

**Every cross-language number here is unweighted, and this module will not let
you see one without its sample.** PHOIBLE is not a balanced sample of the
world's languages and was never meant to be: Atlantic-Congo is 17% of its
inventories and Pama-Nyungan 10.7%, Africa has 885 inventories against
Papunesia's 224, and 531 languages carry more than one doculect -- up to 11.
A segment frequency computed over that is a frequency *in PHOIBLE*, which is a
real and useful thing and is not the same claim as a frequency in the world's
languages.

So `segment_frequency` returns a `Frequency` carrying its own sample
composition, and printing it prints both. Choosing a weighting scheme is the
caller's to make, because it is a research decision -- pick a genealogy, pick a
level, defend it -- and not one a library should make silently on their behalf.
"""

from __future__ import annotations

import collections
import csv
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import merkmal

DATA = Path(__file__).resolve().parent.parent / "data"

__all__ = [
    "Frequency",
    "Inventory",
    "Language",
    "SampleComposition",
    "feature_economy",
    "inventories",
    "inventory_distance",
    "languages",
    "sample_composition",
    "segment_frequency",
]


@dataclass(frozen=True)
class Language:
    glottocode: str
    name: str
    family: str
    macroarea: str
    latitude: str
    longitude: str


@dataclass(frozen=True)
class Inventory:
    """One doculect's phoneme inventory.

    `inventory` is PHOIBLE's contribution id, not a language: 531 languages have
    more than one, and treating them as languages is the commonest way to
    double-count.
    """

    inventory: str
    glottocode: str
    segments: tuple[str, ...]

    def __len__(self) -> int:
        return len(self.segments)

    def readable(self, system: str = "phoible") -> tuple[str, ...]:
        """The segments merkmal can score, which is 99.7% of tokens but not all."""
        out = []
        for segment in self.segments:
            try:
                if merkmal.is_segment(segment, system=system):
                    out.append(segment)
            except Exception:  # noqa: BLE001 - unreadable is not scoreable
                continue
        return tuple(out)


@lru_cache(maxsize=1)
def languages() -> dict[str, Language]:
    out = {}
    with (DATA / "languages.tsv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            out[row["GLOTTOCODE"]] = Language(
                row["GLOTTOCODE"], row["NAME"], row["FAMILY"],
                row["MACROAREA"], row["LATITUDE"], row["LONGITUDE"],
            )
    return out


@lru_cache(maxsize=1)
def inventories() -> tuple[Inventory, ...]:
    out = []
    with (DATA / "inventories.tsv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            out.append(Inventory(row["INVENTORY"], row["GLOTTOCODE"],
                                 tuple(row["SEGMENTS"].split())))
    return tuple(out)


# ------------------------------------------------------------------- sampling


@dataclass(frozen=True)
class SampleComposition:
    """What the sample behind a number is made of.

    Attached to every cross-language result, because the number alone invites
    being read as a fact about languages rather than about PHOIBLE.
    """

    inventories: int
    languages: int
    families: dict[str, int] = field(default_factory=dict)
    macroareas: dict[str, int] = field(default_factory=dict)

    @property
    def duplicated_languages(self) -> int:
        return self.inventories - self.languages

    def describe(self) -> str:
        top = sorted(self.families.items(), key=lambda kv: -kv[1])[:3]
        share = ", ".join(
            f"{name} {100 * n / self.inventories:.1f}%" for name, n in top
        )
        areas = ", ".join(
            f"{a} {100 * n / self.inventories:.1f}%"
            for a, n in sorted(self.macroareas.items(), key=lambda kv: -kv[1])[:3]
        )
        return (
            f"{self.inventories} inventories over {self.languages} languages "
            f"({self.duplicated_languages} extra doculects); "
            f"largest families {share}; largest areas {areas}. "
            "Unweighted: this is PHOIBLE's composition, not the world's."
        )


def sample_composition(sample: tuple[Inventory, ...] | None = None) -> SampleComposition:
    sample = sample if sample is not None else inventories()
    meta = languages()
    families: collections.Counter[str] = collections.Counter()
    areas: collections.Counter[str] = collections.Counter()
    for item in sample:
        info = meta.get(item.glottocode)
        families[info.family if info else "(unknown)"] += 1
        areas[info.macroarea if info else "(unknown)"] += 1
    return SampleComposition(
        inventories=len(sample),
        languages=len({i.glottocode for i in sample}),
        families=dict(families),
        macroareas=dict(areas),
    )


# ---------------------------------------------------------------- frequencies


@dataclass(frozen=True)
class Frequency:
    """A segment's occurrence across inventories, with its sample attached.

    `counts` is how many *inventories* contain the segment, never how many
    languages: the two differ by 834 here and conflating them is the sampling
    error this package exists to make hard.
    """

    counts: dict[str, int]
    sample: SampleComposition

    def share(self, segment: str) -> float:
        return self.counts.get(segment, 0) / self.sample.inventories

    def most_common(self, n: int = 20) -> list[tuple[str, int, float]]:
        rows = sorted(self.counts.items(), key=lambda kv: -kv[1])[:n]
        return [(s, c, c / self.sample.inventories) for s, c in rows]

    def __str__(self) -> str:
        head = ", ".join(f"{s} {100 * p:.0f}%" for s, _c, p in self.most_common(5))
        return f"{head}\n  over {self.sample.describe()}"


def segment_frequency(sample: tuple[Inventory, ...] | None = None) -> Frequency:
    """How many inventories contain each segment.

    The classic typological statistic and the one most damaged by the skew, so
    it comes back wrapped in its sample rather than as a bare dict.
    """
    sample = sample if sample is not None else inventories()
    counts: collections.Counter[str] = collections.Counter()
    for item in sample:
        counts.update(set(item.segments))
    return Frequency(dict(counts), sample_composition(sample))


# ------------------------------------------------------------------ distances


def inventory_distance(
    a: Inventory,
    b: Inventory,
    system: str = "phoible",
) -> float:
    """How far one inventory is from another, in [0, 1]. Symmetric.

    Every segment of each inventory is matched to its nearest counterpart in the
    other, and the two mean nearest-neighbour distances are averaged. Size
    difference needs no separate penalty and does not get one: an inventory with
    segments the other lacks pays for them when those segments have to find a
    match, and pays in proportion to how unlike anything available they are.

    An explicit size term was tried first and was wrong. Charging
    `(larger - smaller) / larger` made English closer to Yue Chinese (0.045) than
    to French (0.158), because the first pair differs by one segment and the
    second by six -- while French was twice as close by segment content. A
    measure of inventory *similarity* that is mostly a measure of inventory
    *size* is worse than useless, because it looks like the thing it is not.

    Sample-independent: this compares two inventories and asks nothing about how
    either was collected. Not a metric, for the same reason the segment distance
    is not one. Nearest-neighbour matching is greedy rather than an optimal
    assignment, which is a deliberate cheapness.
    """
    left, right = a.readable(system), b.readable(system)
    if not left or not right:
        return 1.0

    def one_way(source: tuple[str, ...], target: tuple[str, ...]) -> float:
        total = 0.0
        for segment in source:
            best = 1.0
            for other in target:
                try:
                    score = merkmal.distance(segment, other, system=system)
                except Exception:  # noqa: BLE001 - unscoreable stays maximally far
                    continue
                if score < best:
                    best = score
                    if best == 0.0:
                        break
            total += best
        return total / len(source)

    return (one_way(left, right) + one_way(right, left)) / 2.0


# ------------------------------------------------------------- feature economy


def feature_economy(inventory: Inventory, system: str = "phoible") -> float:
    """Segments per feature the inventory actually uses.

    Clements' observation: inventories reuse a small number of features across
    many segments rather than spending one feature per segment. The ratio is
    inventory size over the number of features on which any of its segments
    takes a value, so a higher number means more segments wrung from the same
    featural machinery.

    Counted per *feature*, not per (feature, value) pair. The first version
    counted pairs, which roughly halves the number and is not the quantity
    Clements defines.

    The absolute value depends on the feature system -- a set with more
    dimensions produces a lower ratio for the same inventory -- so it compares
    inventories within one system and not across systems.

    Per-inventory, so the sampling question does not arise: this is a fact about
    one language's phonology however the sample around it was drawn.
    """
    segments = inventory.readable(system)
    if not segments:
        return 0.0
    labels = merkmal.vector_labels(system=system)
    used: set[str] = set()
    for segment in segments:
        try:
            vector = merkmal.feature_vector(segment, system=system)
        except Exception:  # noqa: BLE001 - skip what cannot be vectorized
            continue
        for name, value in zip(labels, vector, strict=True):
            if value != 0.0:
                used.add(name)
    return len(segments) / len(used) if used else 0.0
