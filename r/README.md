# merkmal for R

merkmal maps IPA transcriptions of speech segments to phonological feature
representations under several feature systems, and computes dissimilarities
between segments from those representations. This package is the R interface
to the merkmal C99 library. The C core is compiled into the package and every
computation calls it; there is no separate implementation and no system
dependency. Results are those of the Python package and the command line for
the same version: the tests replay the library's golden fixtures, and
fingerprints agree with Python's digest for digest.

The library, its method and its limits are documented in the
[repository](https://github.com/tresoldi/merkmal).

## Installation

```r
# install.packages("remotes")
remotes::install_github("tresoldi/merkmal", subdir = "r")
```

The package needs R 4.1 or later and a C compiler (Rtools on Windows, the
Xcode command line tools on macOS).

## Usage

```r
library(merkmal)

list_systems()                                   # the built-in feature systems
get_features("pʰ")                               # feature labels
distance("p", c("b", "t", "a"))                  # vectorized, default system
distance("p", "b", system = "phoible")           # another feature theory
distance_with_coverage("ai", "au", system = "phoible")
diagnose(c("tʰ", "pʰ1", "<?>"))                  # why a segment is refused
system_segment_ipa("tʃa")                        # list(c("tʃ", "a"))
segment_ipa_merged("tʰoŋ⁵⁵")                     # list(c("tʰ", "o⁵⁵", "ŋ"))

d <- distance_matrix(c("p", "b", "t", "d", "a", "i"))
plot(hclust(as.dist(d)))                         # clustering of segments

system_fingerprint()$digest                      # store with any result kept
```

Every function that reads segments takes `system` (default `"distinctive"`)
and `registry` (default: the built-in systems), and is vectorized over its
segment arguments. A segment a system cannot read gives `NA` with a warning,
never a guessed value; `is_segment()` tests and `diagnose()` explains.

| Function | Result |
| --- | --- |
| `list_systems()`, `system_kind()`, `system_inventory()` | The systems of a registry, their kind, their tables |
| `is_segment()`, `get_features()`, `diagnose()` | Whether, how and why not a grapheme is read |
| `distance()`, `distance_with_coverage()`, `distance_matrix()` | Distances, with coverage and comparability, or for every pair |
| `feature_vectors()`, `vector_labels()` | Fixed-width numeric vectors, one row per grapheme |
| `normalize()`, `unicode_normalize()` | merkmal's normalized form; plain NFC or NFD |
| `segment_ipa()`, `system_segment_ipa()` | Orthographic segmentation; segmentation as a system reads it |
| `segment_ipa_merged()`, `merge_tone_digits()`, `split_tone()`, `ascii_chao_digits()` | Chao tones attached to and split from their segments |
| `feature_distance()`, `sound_distance()` | Measurements in the feature geometry itself |
| `system_fingerprint()`, `operation_fingerprint()` | The identity of the data and settings behind a result |
| `mk_registry()`, `add_model()` | A registry with feature systems of your own, in the runtime text format |
| `abstract_segment()`, `with_cells()`, `compare_abstract()`, `is_compatible()`, `compatible_graphemes()` | Feature bundles with unspecified values, compared with exact bounds |
| `build_info()` | The library version, data profile and Unicode version |

`?distance` and the other help pages document each function.

## Strings and locales

Graphemes are passed to the library as UTF-8 and returned marked as UTF-8.
Read wordlists with their encoding declared (for example
`read.delim(path, encoding = "UTF-8")`). In an R session whose locale is not
UTF-8, IPA typed at the console may not reach R as the characters you see;
`Sys.setlocale("LC_CTYPE", "C.UTF-8")` (or `en_US.UTF-8`) avoids this.

## Building from the repository

The package compiles a copy of the C core kept in `src/merkmal/`, written by
`tools/sync_r_sources.py` at the repository root and committed, so that an
install from GitHub needs nothing outside `r/`. After changing the C core:

```sh
python tools/sync_r_sources.py
R CMD build r && R CMD check merkmal_*.tar.gz
```

## License

The source code is MIT. The feature data compiled into the package carries the
terms of its sources (CC BY 4.0, CC BY-SA 3.0 and CC BY-NC-SA 4.0); see
`LICENSE` and `inst/NOTICE`.
