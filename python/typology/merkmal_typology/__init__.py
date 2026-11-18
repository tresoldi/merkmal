"""Language-indexed phonological typology over PHOIBLE inventories.

A companion package to merkmal rather than part of the C library: its data
(PHOIBLE 2.0, see ``data/provenance.json``) is not needed to score a segment,
and sampling weight, genealogy and areal membership are outside the scope of
the core library, which describes segment types, not languages.

**Every cross-language figure is unweighted.** PHOIBLE is not a balanced sample
of the world's languages. In the bundled data (``sample_composition()``),
Atlantic-Congo accounts for 17.0% of the 3,020 inventories and Pama-Nyungan for
10.7%; Africa has 885 inventories and Papunesia 224; and 531 languages have
more than one doculect, up to 11. A segment frequency computed over this sample
is a frequency in PHOIBLE, not in the world's languages.

For that reason ``segment_frequency`` returns a ``Frequency`` that carries its
sample composition, and its string form prints both. The package applies no
weighting: the choice of a genealogy, a level and a weighting scheme is a
research decision left to the caller.
"""

from __future__ import annotations

import collections
import csv
import warnings
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import merkmal

DATA = Path(__file__).resolve().parent.parent / "data"

__all__ = [
    "MIN_MATCH_COVERAGE",
    "Frequency",
    "Inventory",
    "InventoryComparison",
    "InventoryReadability",
    "Language",
    "LowCoverageWarning",
    "SampleComposition",
    "feature_economy",
    "inventories",
    "inventory_comparison",
    "inventory_distance",
    "languages",
    "sample_composition",
    "segment_frequency",
]


#: The mean match coverage below which a comparison is flagged as weak. Over a
#: random sample of 150 PHOIBLE inventory pairs the mean match coverage under
#: ``phoible`` lies between 0.63 and 0.74, so a value below 0.5 means that a
#: large share of the matches compared few dimensions.
MIN_MATCH_COVERAGE = 0.5


class LowCoverageWarning(UserWarning):
    """An inventory comparison rests on matches that compared few dimensions."""


@dataclass(frozen=True)
class Language:
    """A language as PHOIBLE's language table gives it.

    Coordinates are kept as the source's strings; ``family`` and
    ``macroarea`` may be empty.
    """

    glottocode: str
    name: str
    family: str
    macroarea: str
    latitude: str
    longitude: str


@dataclass(frozen=True)
class Inventory:
    """One doculect's phoneme inventory.

    ``inventory`` is PHOIBLE's contribution id, not a language: a language
    may have several inventories, and counting inventories as languages
    counts those languages more than once.
    """

    inventory: str
    glottocode: str
    segments: tuple[str, ...]

    def __len__(self) -> int:
        return len(self.segments)

    def readable(self, system: str = "phoible") -> tuple[str, ...]:
        """The segments ``system`` can score; ``readability`` also lists the rest."""
        return self.readability(system).readable

    def readability(self, system: str = "phoible") -> InventoryReadability:
        """Partition this inventory by whether ``system`` can score its segments.

        A segment for which ``merkmal.is_segment`` raises is counted as
        unreadable.
        """
        readable: list[str] = []
        unreadable: list[str] = []
        for segment in self.segments:
            try:
                if merkmal.is_segment(segment, system=system):
                    readable.append(segment)
                else:
                    unreadable.append(segment)
            except Exception:  # noqa: BLE001 - reported as unreadable, not dropped
                unreadable.append(segment)
        return InventoryReadability(
            inventory=self.inventory,
            system=system,
            readable=tuple(readable),
            unreadable=tuple(unreadable),
        )


@dataclass(frozen=True)
class InventoryReadability:
    """The segments a system can and cannot score in one inventory."""

    inventory: str
    system: str
    readable: tuple[str, ...]
    unreadable: tuple[str, ...]

    @property
    def total(self) -> int:
        """The number of segments in the inventory."""
        return len(self.readable) + len(self.unreadable)

    @property
    def coverage(self) -> float:
        """The share of segments that are readable, in ``[0, 1]``; 0.0 if none."""
        return len(self.readable) / self.total if self.total else 0.0


@dataclass(frozen=True)
class InventoryComparison:
    """An inventory distance with the coverage of the evidence behind it.

    ``score`` is computed over readable segments only, so it is interpretable
    only together with ``left`` and ``right`` (the readability of each
    inventory), ``mean_match_coverage`` (the mean coverage of the selected
    nearest-neighbour matches) and ``comparability`` (the matches counted by
    comparability label, ``"no-score"`` for a segment with no scorable
    match). A low score with low coverage indicates a weak comparison, not
    similar inventories. ``system_fingerprint`` is the SHA-256 of the
    system's semantic fingerprint.
    """

    score: float
    system: str
    system_fingerprint: str
    left: InventoryReadability
    right: InventoryReadability
    selected_matches: int
    mean_match_coverage: float
    comparability: dict[str, int] = field(default_factory=dict)

    @property
    def input_coverage(self) -> float:
        """The share of both inventories' segments that the system can read."""
        total = self.left.total + self.right.total
        readable = len(self.left.readable) + len(self.right.readable)
        return readable / total if total else 0.0

    @property
    def low_coverage(self) -> bool:
        """Whether ``mean_match_coverage`` is below ``MIN_MATCH_COVERAGE``.

        Such a score, however low, says little about how alike the two
        inventories are.
        """
        return self.mean_match_coverage < MIN_MATCH_COVERAGE


@lru_cache(maxsize=1)
def languages() -> dict[str, Language]:
    """PHOIBLE's languages, keyed by Glottocode. Read once and cached."""
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
    """Every PHOIBLE inventory, in the source's order. Read once and cached."""
    out = []
    with (DATA / "inventories.tsv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            out.append(Inventory(row["INVENTORY"], row["GLOTTOCODE"],
                                 tuple(row["SEGMENTS"].split())))
    return tuple(out)


# Sampling


@dataclass(frozen=True)
class SampleComposition:
    """The composition of the sample behind a cross-language figure.

    Attached to every cross-language result, so that the figure is not read as
    a fact about languages rather than about the sample. ``families`` and
    ``macroareas`` count inventories, not languages; an inventory whose
    language is not in the language table counts as ``"(unknown)"``.
    """

    inventories: int
    languages: int
    families: dict[str, int] = field(default_factory=dict)
    macroareas: dict[str, int] = field(default_factory=dict)

    @property
    def duplicated_languages(self) -> int:
        """Inventories beyond the first of each language."""
        return self.inventories - self.languages

    def describe(self) -> str:
        """One sentence: the counts and the three largest families and areas."""
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
    """The composition of ``sample``, by default every inventory."""
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


# Frequencies


@dataclass(frozen=True)
class Frequency:
    """A segment's occurrence across inventories, with its sample attached.

    ``counts`` is the number of inventories that contain each segment, not
    the number of languages; the two differ whenever a language has more than
    one inventory in the sample.
    """

    counts: dict[str, int]
    sample: SampleComposition

    def share(self, segment: str) -> float:
        """The share of the sample's inventories that contain ``segment``."""
        return self.counts.get(segment, 0) / self.sample.inventories

    def most_common(self, n: int = 20) -> list[tuple[str, int, float]]:
        """The ``n`` most frequent segments as ``(segment, count, share)``."""
        rows = sorted(self.counts.items(), key=lambda kv: -kv[1])[:n]
        return [(s, c, c / self.sample.inventories) for s, c in rows]

    def __str__(self) -> str:
        head = ", ".join(f"{s} {100 * p:.0f}%" for s, _c, p in self.most_common(5))
        return f"{head}\n  over {self.sample.describe()}"


def segment_frequency(sample: tuple[Inventory, ...] | None = None) -> Frequency:
    """The number of inventories in ``sample`` (default: all) containing each segment.

    The statistic most affected by the sample's skew, so it is returned with
    its sample composition rather than as a bare mapping.
    """
    sample = sample if sample is not None else inventories()
    counts: collections.Counter[str] = collections.Counter()
    for item in sample:
        counts.update(set(item.segments))
    return Frequency(dict(counts), sample_composition(sample))


# Distances


def inventory_comparison(
    a: Inventory,
    b: Inventory,
    system: str = "phoible",
) -> InventoryComparison:
    """Compare two inventories, with the coverage of the comparison.

    Each readable segment of each inventory is matched to its nearest readable
    segment in the other under ``merkmal.distance_with_coverage``, and the
    score is the mean of the two directions' mean nearest-neighbour
    distances, in ``[0, 1]``. A segment with no scorable match counts as 1.0;
    the score is 1.0 when either inventory has no readable segment.

    There is no separate term for a difference in size: segments one
    inventory has and the other lacks already contribute their distance to
    the nearest available segment. An explicit size term would make the score
    depend mostly on inventory size rather than on segment content.

    The comparison concerns the two inventories only and does not depend on
    the sample. The score is not a metric, for the same reasons the segment
    distance is not one. Matching is nearest-neighbour, not an optimal
    one-to-one assignment.

    Emits ``LowCoverageWarning`` when the result's ``low_coverage`` is true,
    so that a weak comparison is not read as a close one.
    """
    left = a.readability(system)
    right = b.readability(system)
    compared_coverages: list[float] = []
    comparability: collections.Counter[str] = collections.Counter()

    def result(score: float) -> InventoryComparison:
        return InventoryComparison(
            score=score,
            system=system,
            system_fingerprint=merkmal.system_fingerprint(system=system)[1],
            left=left,
            right=right,
            selected_matches=len(compared_coverages),
            mean_match_coverage=(
                sum(compared_coverages) / len(compared_coverages)
                if compared_coverages else 0.0
            ),
            comparability=dict(comparability),
        )

    readable_left, readable_right = left.readable, right.readable
    if not readable_left or not readable_right:
        return result(1.0)

    def one_way(source: tuple[str, ...], target: tuple[str, ...]) -> float:
        total = 0.0
        for segment in source:
            best = 1.0
            best_coverage = 0.0
            best_status = "no-score"
            for other in target:
                try:
                    score, coverage, status = merkmal.distance_with_coverage(
                        segment, other, system=system
                    )
                except Exception:  # noqa: BLE001 - an unscorable pair stays at 1.0
                    continue
                if score < best:
                    best, best_coverage, best_status = score, coverage, status
                    if best == 0.0:
                        break
            total += best
            compared_coverages.append(best_coverage)
            comparability[best_status] += 1
        return total / len(source)

    comparison = result((one_way(readable_left, readable_right) +
                         one_way(readable_right, readable_left)) / 2.0)
    if comparison.low_coverage:
        warnings.warn(
            f"{a.inventory} and {b.inventory}: mean match coverage "
            f"{comparison.mean_match_coverage:.3f} is below {MIN_MATCH_COVERAGE}; "
            "the score reflects few compared dimensions",
            LowCoverageWarning,
            stacklevel=2,
        )
    return comparison


def inventory_distance(
    a: Inventory,
    b: Inventory,
    system: str = "phoible",
) -> float:
    """Return ``inventory_comparison(a, b, system).score``.

    The bare score omits unreadable segments and match coverage;
    :func:`inventory_comparison` reports both.
    """
    return inventory_comparison(a, b, system).score


# Feature economy


def feature_economy(inventory: Inventory, system: str = "phoible") -> float:
    """The feature economy of an inventory: segments per feature used.

    Following Clements (2003), the ratio of the number of readable segments to
    the number of features (vector columns of ``system``) on which at least
    one of them has a nonzero, known value. A higher value means more segments
    built from the same features. Features are counted, not (feature, value)
    pairs, as in Clements' definition. Returns 0.0 for an inventory with no
    readable segment or no feature used.

    The value depends on the feature system, whose number of dimensions
    differs, so it compares inventories within one system only. It describes
    one inventory and does not depend on the sample.

    Clements, G. N. 2003. Feature economy in sound systems. *Phonology* 20(3):
    287-333.
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
            if value != 0.0 and value == value:  # NaN: value unknown, not used
                used.add(name)
    return len(segments) / len(used) if used else 0.0
