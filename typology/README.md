# merkmal-typology

Language-indexed phonological typology, built on `merkmal`'s segment distances.

```python
import merkmal_typology as mt

inventories = mt.inventories()          # 3,020 doculects
languages = mt.languages()              # 2,186, with family and macroarea
print(mt.segment_frequency())           # and the sample it came from
mt.inventory_comparison(a, b)           # score plus readability and comparison coverage
mt.inventory_distance(a, b)             # scalar compatibility convenience
mt.feature_economy(inventory)           # segments per feature used
```

## Why this is a separate package

The core library has spent its life refusing to have opinions about sampling
weight, genealogy and areal membership — the README's disclaimer about segment
*types* rather than languages is load-bearing, not decorative. Adding a language
column to the C core would have quietly ended that.

Keeping it here means the discipline survives the addition. It also keeps 500 KB
of share-alike data out of a 544 KB library whose distribution terms would
otherwise have to grow to carry it.

## The sample is not the world

PHOIBLE is not a balanced sample of the world's languages and was never meant to
be:

| | |
| --- | ---: |
| inventories | 3,020 |
| languages | 2,186 |
| languages with more than one doculect | 531 (up to 11) |
| Atlantic-Congo | 17.0% of inventories |
| Pama-Nyungan | 10.7% |
| Africa | 29.3% |
| Papunesia | 7.4% |

**Every cross-language number here is unweighted, and the package will not let
you see one without its sample.** `segment_frequency()` returns a `Frequency`
that carries its own `SampleComposition`, and printing it prints both:

```
m 96%, i 92%, k 90%, j 90%, u 88%
  over 3020 inventories over 2186 languages (834 extra doculects);
  largest families Atlantic-Congo 17.0%, Pama-Nyungan 10.7%, Indo-European 9.2%;
  largest areas Africa 29.3%, Eurasia 27.0%, South America 15.7%.
  Unweighted: this is PHOIBLE's composition, not the world's.
```

That /m/ is in 96% of PHOIBLE's inventories is a real and useful fact. It is not
the same claim as "/m/ is in 96% of the world's languages", and the difference
is not a technicality when two families are 28% of the sample.

No weighting scheme is provided. Choosing one is a research decision — pick a
genealogy, pick a level, defend it — and not something a library should do
silently on a user's behalf.

## What is sample-independent

`inventory_comparison` and `feature_economy` compare or describe inventories
directly and ask nothing about how the sample was drawn. They are safe to use
without engaging the question above.

`inventory_comparison` matches every segment of each inventory to its nearest
counterpart in the other and averages both directions. An explicit size penalty
was tried first and was wrong: charging for the difference in inventory size
made English closer to Yue Chinese than to French, because those differ by one
segment and six respectively — while French was twice as close by segment
content. A similarity measure that is mostly a size measure is worse than
useless, because it looks like the thing it is not. Its result carries the
unreadable segments on each side, the input readability rate, and the mean
coverage/status of the selected nearest-neighbour comparisons. A bare scalar
from `inventory_distance` is retained only for compatibility; new analyses must
store the `InventoryComparison`. It also carries Merkmal's semantic-system
fingerprint, so comparison results remain tied to the feature model that
produced them.

The result behaves: Mandarin and Yue Chinese are the closest pair tested
(0.0060), English sits nearer German (0.0115) than French (0.0134), and the
inventories furthest from English in a random sample of 120 are all Australian.

`feature_economy` is Clements' ratio, inventory size over the number of features
any of its segments takes a value on. Hawaiian, at 13 segments, is the least
economical in the first 400 inventories (0.36); Hindi at 94 segments the most
(2.54). It counts *features*, not (feature, value) pairs — the first version
counted pairs, which roughly halves the figure and is not the quantity Clements
defines. The absolute value depends on the feature system, so it compares
inventories within one system rather than across systems.

## Data

`data/` carries the reshaped PHOIBLE tables with their own
[`provenance.json`](data/provenance.json), pinned to `cldf-datasets/phoible`
v2.0.1 (`f36deac7f80b`). **CC-BY-4.0 by permission** — upstream PHOIBLE is
CC-BY-SA-3.0, and the share-alike clause is lifted by a grant whose grantor and
date the manifest still marks `UNVERIFIED`. Attribution to PHOIBLE is required
regardless.

That clause was one of two reasons this layer is a separate package. It is gone;
the other one — keeping sampling weight and genealogy out of a core that has
spent its life refusing them — is the one that actually mattered, and it still
holds.
