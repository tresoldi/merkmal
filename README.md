# merkmal

merkmal is a C99 library that maps IPA transcriptions of speech segments to
phonological feature representations under several feature systems, and
computes dissimilarities between segments from those representations. It is
intended for computational historical linguistics and phonological typology:
as a substitution cost in sequence alignment, for transcription quality
control, and for comparing segments across feature theories. The library has
no runtime dependencies; a Python package, a command-line interface and a
WebAssembly build are thin wrappers around the same C interface.

## Contents

- [Feature systems](#feature-systems)
- [Method](#method)
- [Scope and interpretation](#scope-and-interpretation)
- [Installation](#installation)
- [Usage](#usage)
- [Documentation](#documentation)
- [Citation](#citation)
- [License](#license)

## Feature systems

Each feature system is a versioned table of segments and their features,
compiled into the library from the source data in [data/models/](data/models/).

| System | Feature basis | Kind | Source data |
| --- | --- | --- | --- |
| `distinctive` (default) | Distinctive features after Clements and Hume (1995), with scalar dimensions | categorical | CLTS 1.4.1 (List et al.) |
| `descriptive` | Articulatory descriptions of IPA segments, scored through the feature geometry | categorical | CLTS 1.4.1 (List et al.) |
| `phoible` | PHOIBLE binary features (37 dimensions) | valued | PHOIBLE 2.0 (Moran and McCloy 2019) |
| `pbase-spe` | SPE features (Chomsky and Halle 1968) | valued | P-base (Mielke) |
| `pbase-jfh` | Acoustic features of Jakobson, Fant and Halle (1952) | valued | P-base (Mielke) |
| `pbase-hc`, `pbase-uftc` | The HC and UFTC feature sets of P-base | valued | P-base (Mielke) |

A *categorical* system describes a segment by a set of feature labels; a
*valued* system assigns each segment a value (`+`, `-`, `0`, or unknown) on a
fixed set of dimensions. The provenance of each table, including the upstream
release and every transformation applied to it, is recorded in
`data/models/<system>/provenance.json` and summarized in [NOTICE](NOTICE).

Segments that a table does not list are, where possible, derived from listed
ones: a base segment with diacritics, tone marks or length, a diphthong, an
affricate or labial-velar written without a tie bar, or a consonant cluster.

Callers may also register models of their own at run time, in a line-oriented
text format ([docs/guide/runtime-model-format.md](docs/guide/runtime-model-format.md)).

## Method

Categorical systems are compared through a feature geometry, a tree of feature
nodes derived from, but not identical to, the proposal of Clements and Hume
(1995). Each feature contributes in proportion to the inverse depth of its node;
ordered properties (vowel height, backness, length, tone level) are compared as
positions on a scale rather than as unrelated labels. `distinctive` compares
segments on its own scalar dimensions; `descriptive` compares them through the
geometry directly. Valued systems compare only the dimensions on which both
segments have a value.

Every comparison can also report its *coverage*, the share of the system's
dimensions on which both segments were compared, and whether the two segments
were comparable at all (a tone and a segment are not compared on a shared
scale). Tone is represented by the presence of a tone and an ordered Chao level
at each position, so that a mid level tone is distinct from the absence of tone.

The geometry, its weights and its open problems are described in
[docs/method/geometry.md](docs/method/geometry.md). Comparisons with external
references (expert alignments, coverage of published wordlists, robustness
across feature theories) are reported in
[docs/method/evaluation.md](docs/method/evaluation.md).

## Scope and interpretation

The library computes a dissimilarity between two segments. The following
properties limit what that number can be used for.

- **It is not a metric.** Valued systems compare only the dimensions both
  segments define, so the basis of comparison changes from pair to pair, and the
  triangle inequality does not hold: in `pbase-hc`,
  d(ðˠ, mʲ) = 0.3113 > d(ðˠ, d̪ʲ) + d(d̪ʲ, mʲ) = 0.0943 + 0.2091.
- **It is not a probability of sound change.** Phonetic similarity and the
  frequency of a change are different quantities: velar palatalization is among
  the most frequent changes attested, yet d(k, tʃ) = 0.41 is far greater than
  d(k, q) = 0.05 in the default system. Claims about change require models
  estimated from correspondences between languages.
- **It is not a typological statistic.** The tables are catalogues of segment
  types. They do not record which languages have a segment, whether it is
  contrastive, or any genealogical or areal grouping. A companion package,
  [python/typology/](python/typology/), provides language-indexed inventories
  separately.
- **The weights are stipulated, not estimated.** They follow from the depth of
  the geometry and from hand-set scale weights, not from perception, contrast or
  observed change.
- **It is a substitution cost, not an aligner.** The library has no gap model and
  no sequence operations. The gap cost that best reproduces expert alignments
  differs between systems ([evaluation](docs/method/evaluation.md#1-segment-substitution-cost-in-pairwise-alignment)).
- **Identical values are reported, not hidden.** Pairs of distinct segments with
  a distance of zero are listed with their reasons in
  `tests/golden/contrast_baseline.tsv`. In the categorical systems they are
  spellings of one segment (diacritics in another order, or an equivalent
  notation); in the valued systems they are segments that the source table
  does not distinguish.

Results depend on the system, its version and the scoring policy. The semantic
fingerprint of a system ([docs/method/semantic-fingerprint.md](docs/method/semantic-fingerprint.md))
identifies all three and should be stored with any result that is kept.

## Installation

The C library is built with CMake (3.20 or later) and a C99 compiler:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build
cmake --install build
```

The Python package (CPython 3.12 or later) is built from the same sources:

```sh
python -m pip install merkmal
```

Installed C consumers can use CMake (`find_package(merkmal CONFIG)`, target
`merkmal::merkmal`) or pkg-config. Static and shared builds, and a build without
the share-alike and non-commercial data, are described in
[docs/guide/installation.md](docs/guide/installation.md).

## Usage

In Python:

```python
import merkmal

merkmal.get_features("pʰ")                      # frozenset of feature labels
merkmal.distance("p", "b")                      # 0.1429, default system
merkmal.distance("p", "b", system="phoible")    # another feature theory
merkmal.distance_with_coverage("ai", "au")      # score, coverage, comparability
merkmal.system_segment_ipa("tʃa", system="descriptive")   # ['tʃ', 'a']
```

From the command line, with machine-readable output:

```sh
merkmal --system phoible features bʰ
merkmal --tsv distance ai au
```

In C:

```c
#include "merkmal.h"
#include <stdio.h>

int main(void)
{
    mk_registry *registry = NULL;
    const mk_system *system = NULL;
    double distance = 0.0;

    if (mk_registry_new_builtin(&registry) != MK_OK) {
        return 1;
    }
    if (mk_registry_get_system(registry, "distinctive", &system) == MK_OK &&
        mk_system_segment_distance(system, "p", "b", &distance) == MK_OK) {
        printf("%.4f\n", distance);
    }
    mk_registry_free(registry);
    return 0;
}
```

[examples/transcribe.c](examples/transcribe.c) is a complete program: it
segments a transcription, prints the features of each segment, scores a pair,
and explains why a segment was refused.

Two tokenization policies are provided. `segment_ipa` splits at every base
character not joined by a tie bar; `system_segment_ipa` takes the longest
sequence the chosen system recognizes as one segment. Neither is a phonological
analysis (`kp` may be a cluster in a language without labial-velars), and the
policy and system used should be recorded with any stored tokenization.

## Documentation

[docs/README.md](docs/README.md) lists the documentation: the C interface, the
Python package and command line, the model formats, the method and its
evaluation, and the development conventions. Changes between releases are
recorded in [CHANGELOG.md](CHANGELOG.md).

## Citation

Please cite the software as described in [CITATION.cff](CITATION.cff), and also
cite the source of the feature data for each system used:

- List, Johann-Mattis, Cormac Anderson, Tiago Tresoldi, Christoph Rzymski and
  Robert Forkel. Cross-Linguistic Transcription Systems (CLTS), version 1.4.1.
  https://github.com/cldf-clts/clts (`distinctive`, `descriptive`).
- Moran, Steven and Daniel McCloy (eds.). 2019. PHOIBLE 2.0. Jena: Max Planck
  Institute for the Science of Human History. https://phoible.org/ (`phoible`).
- Mielke, Jeff. P-base. North Carolina State University (`pbase-*`).

Other works cited above:

- Chomsky, Noam and Morris Halle. 1968. *The sound pattern of English*. New
  York: Harper & Row.
- Clements, G. N. and Elizabeth V. Hume. 1995. The internal organization of
  speech sounds. In John A. Goldsmith (ed.), *The handbook of phonological
  theory*, 245–306. Oxford: Blackwell.
- Jakobson, Roman, C. Gunnar M. Fant and Morris Halle. 1952. *Preliminaries to
  speech analysis: The distinctive features and their correlates*. Cambridge,
  MA: MIT Press.

## License

The source code is released under the MIT license ([LICENSE](LICENSE)). The
feature data compiled into the library carries the terms of its sources:

| Data | License |
| --- | --- |
| `distinctive`, `descriptive` | CC BY 4.0 |
| `phoible` | CC BY-SA 3.0 |
| `pbase-spe`, `pbase-jfh`, `pbase-hc`, `pbase-uftc` | CC BY-NC-SA 4.0 |

The distributed package is therefore licensed as
`MIT AND CC-BY-4.0 AND CC-BY-SA-3.0 AND CC-BY-NC-SA-4.0`: software built on it
inherits the share-alike terms of PHOIBLE and P-base and the non-commercial
terms of P-base. A build containing only the CC BY 4.0 data is available
(`MERKMAL_DATA_PROFILE=cc-by`; see
[docs/guide/installation.md](docs/guide/installation.md#data-profiles)).
[NOTICE](NOTICE) gives the attribution each source requires.
