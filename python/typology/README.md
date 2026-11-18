# merkmal_typology

`merkmal_typology` is a companion Python package that provides the phoneme
inventories of PHOIBLE 2.0 (Moran and McCloy 2019), indexed by language, and
functions that compare and describe inventories with merkmal's segment
distances. It is kept apart from the core library, which describes segment
types and records no languages, genealogy or areal grouping; the bundled data
are not part of the `merkmal` distribution.

The package is the separate distribution `merkmal-typology`, which depends on
`merkmal` and carries the inventories in its wheel. It is not on PyPI; it is
installed from a checkout:

```sh
python -m pip install ./python/typology
```

```python
import merkmal_typology as mt

inventories = mt.inventories()          # tuple of Inventory, one per doculect
languages = mt.languages()              # dict of Language, keyed by Glottocode
frequency = mt.segment_frequency()      # Frequency, with its sample attached
mt.inventory_comparison(a, b)           # InventoryComparison
mt.inventory_distance(a, b)             # the score of inventory_comparison only
mt.feature_economy(inventory)           # segments per feature used
```

## Contents

| Name | Provides |
| --- | --- |
| `languages()` | `Language` records: Glottocode, name, family, macroarea, latitude, longitude |
| `inventories()` | `Inventory` records: PHOIBLE inventory id, Glottocode, segments |
| `Inventory.readability(system)` | `InventoryReadability`: the segments `system` can and cannot score |
| `sample_composition(sample)` | `SampleComposition`: inventories, languages, families and macroareas of a sample |
| `segment_frequency(sample)` | `Frequency`: the number of inventories containing each segment, with the `SampleComposition` of the sample |
| `inventory_comparison(a, b, system)` | `InventoryComparison`: a score with the readability of both inputs and the coverage of the matches |
| `inventory_distance(a, b, system)` | The score of `inventory_comparison` alone |
| `feature_economy(inventory, system)` | Inventory size over the number of features used |

`sample` defaults to all inventories and `system` to `phoible`.

An `Inventory` is a doculect, not a language: `Inventory.inventory` is
PHOIBLE's contribution identifier, and several inventories may share a
Glottocode.

## Sampling

PHOIBLE is not a balanced sample of the world's languages. The composition of
the bundled data, as computed by `sample_composition()`:

| | |
| --- | ---: |
| inventories | 3,020 |
| languages (Glottocodes) | 2,186 |
| languages with more than one inventory | 531 (at most 11) |
| Atlantic-Congo | 17.0% of inventories |
| Pama-Nyungan | 10.7% of inventories |
| Africa | 29.3% of inventories |
| Papunesia | 7.4% of inventories |

All cross-language figures computed by the package are unweighted counts over
inventories, not over languages. `segment_frequency()` returns a `Frequency`
that carries the `SampleComposition` of its sample, and its string form prints
both:

```text
m 96%, i 92%, k 90%, j 90%, u 88%
  over 3020 inventories over 2186 languages (834 extra doculects); largest families Atlantic-Congo 17.0%, Pama-Nyungan 10.7%, Indo-European 9.2%; largest areas Africa 29.3%, Eurasia 27.0%, South America 15.7%. Unweighted: this is PHOIBLE's composition, not the world's.
```

That /m/ occurs in 96% of PHOIBLE's inventories is a statement about this
sample; it is not an estimate of the share of the world's languages that have
/m/. The package provides no weighting scheme. A weighting requires a choice of
genealogy and of the level at which to weight, which is a decision of the
analysis, not of the package.

## Inventory comparison

`inventory_comparison` and `feature_economy` describe individual inventories or
pairs of inventories and do not depend on the composition of the sample.

`inventory_comparison` matches each segment of each inventory to its nearest
segment in the other, under merkmal's segment distance, and averages the mean
nearest-neighbour distance of the two directions. Differences in inventory size
enter only through these matches: a segment without a close counterpart in the
other inventory contributes its distance to the nearest one. There is no
separate size term, because such a term makes inventories of similar size
appear similar regardless of their content. The matching is greedy rather than an
optimal assignment, and the result is not a metric.

The score is computed over the segments the system can read. The returned
`InventoryComparison` therefore also carries the readable and unreadable
segments of each inventory, the share of input segments that could be read,
the mean coverage of the selected matches, the comparability status of each
match, and the semantic fingerprint of the system used
([docs/method/semantic-fingerprint.md](../../docs/method/semantic-fingerprint.md)).
A low score with low coverage indicates a weak comparison, not similar
inventories: when the mean match coverage is below `MIN_MATCH_COVERAGE` (0.5),
`InventoryComparison.low_coverage` is true and the comparison emits a
`LowCoverageWarning`. Over a random sample of 150 inventory pairs the mean
match coverage under `phoible` lies between 0.63 and 0.74.
`inventory_distance` returns the score alone; results that are kept should
store the `InventoryComparison`.

## Feature economy

`feature_economy` is inventory size divided by the number of features on which
at least one of the inventory's readable segments has a value, after Clements
(2003). It counts features, not feature-value pairs. The number of features
depends on the system, so values are comparable between inventories within one
system but not across systems.

## Data

`merkmal_typology/data/inventories.tsv` (one row per inventory, segments
separated by spaces) and `merkmal_typology/data/languages.tsv` (one row per
Glottocode) are reshaped from
`cldf/values.csv`, `cldf/languages.csv` and `cldf/contributions.csv` of
`cldf-datasets/phoible` v2.0.1 (commit `f36deac7f80b`). The transformation,
input hashes and sampling note are recorded in
[`merkmal_typology/data/provenance.json`](merkmal_typology/data/provenance.json).

These files are distributed under PHOIBLE's own terms, CC-BY-SA-3.0, like
the PHOIBLE model compiled into the core library: attribution to PHOIBLE is
required, and adaptations must be shared under the same or a compatible
license. No permission to relicense PHOIBLE has been recorded
([docs/development/release-policy.md, Data releases](../../docs/development/release-policy.md#data-releases)).

## References

- Clements, G. N. 2003. Feature economy in sound systems. *Phonology* 20(3):
  287–333.
- Moran, Steven and Daniel McCloy (eds.). 2019. PHOIBLE 2.0. Jena: Max Planck
  Institute for the Science of Human History. https://phoible.org/
