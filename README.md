# merkmal

`merkmal` is a C99 library for mapping supported IPA-like graphemes to
versioned phonological feature representations and computing configurable
**experimental dissimilarities** between segments.

## What the number means

The scalar `merkmal` returns is an experimental dissimilarity. Read the
following before building on it:

- **It is not a metric.** The valued scorer compares only dimensions where both
  segments have a parseable value, so the denominator changes with the pair,
  and a score of `0.2` over five compared dimensions is not the same evidence
  as `0.2` over thirty. It violates the triangle inequality; in `pbase-hc`,
  `d(ðˠ, mʲ) = 0.3113 > d(ðˠ, d̪ʲ) + d(d̪ʲ, mʲ) = 0.0943 + 0.2091`. Do not use
  it where metric properties are assumed — metric-tree indexing, some
  clustering algorithms, embedding claims.
- **It is not a probability or naturalness of sound change**, and it is not
  evidence about historical direction. Nothing in this library observes a
  change happening. See [typologies/README.md](typologies/README.md).
- **It is not a typological statistic.** The bundled models are segment-type
  catalogs. They do not record which phoneme belongs to which language
  inventory, whether a segment is contrastive or allophonic, or any genealogy,
  area, or sampling weight. "PHOIBLE coverage" here means coverage of
  PHOIBLE-like segment *types*, not of languages.
- **It does not track how likely a sound change is.** Measured over pairs from
  named sound laws, historically frequent changes come out *further* apart on
  average than rare ones: `d(k, tʃ)` far exceeds `d(k, q)`, though velar
  palatalisation is among the commonest changes in the world and unconditioned
  uvularisation is rare. Phonetic similarity and diachronic probability are
  different quantities. Use recurrent correspondence patterns estimated from
  language-pair data for anything that claims to be about change.
- **Every zero is on the record.** `tests/golden/contrast_baseline.tsv` records
  the zero-distance pairs of all eight systems, with reasons;
  `scripts/contrast_baseline.py --check` fails on a regression. The categorical
  systems currently have none. The valued systems do, because the upstream
  feature tables genuinely do not distinguish the segments — the P-base UFTC
  feature set gives /e/ and /i/ identical values on every dimension it defines —
  so those are published as counts rather than papered over.
- **The weights are stipulated, not fitted.** They come from tree depth and
  hand-set scale weights, not from contrast data, perception, or observed sound
  change. See [docs/geometry.md](docs/geometry.md).

A dependable, transparent segment prior is genuinely useful for alignment,
candidate generation, transcription quality control, and exploratory
comparison. Those uses are what this supports today. Historical and typological
interpretation requires a separate, validated model fitted to language-indexed
data, which this library does not provide.

## It is a substitution cost, not an aligner

`merkmal` scores one segment against one segment. It has no gap model, no
alignment, and no sequence operations, and that is a scope decision rather than
an omission to be filled in later. If you are aligning words, use
[LingPy](https://lingpy.org/) and give it these distances, or write the
Needleman-Wunsch yourself — it is thirty lines.

The gap cost is yours to choose, so here is what it measured out at rather than
leaving you to guess. Tuning on held-out BDPA alignments, the optimum sits at
**0.30–0.50** for the categorical systems and up to 0.80 for the valued ones;
`bench/bench_alignment.py` re-derives it. It is not transferable between
systems, because the distance distributions differ.

Two things worth knowing before you build on the number:

- **A tone and a segment are not comparable on a shared scale**, and the value
  you get today for `d(³³, p)` is a placeholder the project does not defend.
  Gold alignments never put tone in a column with a segment; a pipeline should
  not either. See `REFERENCE_LIBRARY_PLAN.md`.
- **`sound_distance` is the geometry scorer and takes no system.** It agrees
  with `distance` only for the geometry-scored systems (`descriptive`, `broad`),
  not for the default.

See [docs/review-response.md](docs/review-response.md) for the standing
external review of these claims and what remains open.

The repository is being reorganized around a small C ABI. The C library
contains compiled-in built-in models and can also accept caller-supplied
runtime models. Python support is now a native wrapper around the C
library. The old pure-Python implementation and Go support have been removed
from the active codebase. Historical Python tutorials, notebooks, and research
scripts are archived under `docs/legacy_python/`.

## Current Status

The C implementation currently covers the high-level operations selected
for the first native slice:

- built-in registry creation and system lookup
- listing built-in systems
- grapheme feature lookup
- segment validity checks
- categorical and valued segment distance
- geometry feature distance
- set-based sound distance with weight presets
- IPA normalization and two tokenization policies (orthographic and
  system-aware longest match)
- Chao tone digit merging
- descriptive source-token validation for vowel clusters, selected
  author-defined consonant clusters, precomposed Latin source letters,
  broader affricate spellings, and tone-bearing nuclei
- registering a simple caller-supplied categorical model from text

Built-in C systems currently include:

- `distinctive` — **the default.** It recognizes the same graphemes as
  `descriptive` (0 disagreements over 7,396 Lexibank segment types) and scores
  better: on BDPA gold alignments it is not statistically distinguishable from
  LingPy's SCA, where `descriptive` is measurably behind it. Reach for this one
  unless you have a reason not to.
- `descriptive` — same recognition, scores through the geometry tree rather than
  its own dimensions. Use it when you want the geometry's numbers, or when you
  want `sound_distance` on a feature set to agree with `distance` on a grapheme,
  which only holds for the geometry-scored systems.
- `broad` — **deprecated, and now a pure duplicate of `descriptive`.** Not
  merely "operationally identical": 0 differences in feature sets, 0 in
  distances, and 0 in recognition across the whole corpus. Two public names for
  one thing. It still resolves so nothing breaks; it will be removed in the next
  major version. Do not start anything new on it.
- `pbase-hc`
- `pbase-jfh` — an *acoustic* feature set (Jakobson–Fant–Halle) mapped onto an
  articulatory tree for weighting; the mapping is a convenience, not a claim
  that the two systems align
- `pbase-spe`
- `pbase-uftc`
- `phoible`

`classfeat` is intentionally not part of the first native C slice, but
the generated-data and API layout leave room for it.

## Build And Install

From the repository root:

```sh
cmake -S . -B build/c-debug -DCMAKE_BUILD_TYPE=Debug
cmake --build build/c-debug
ctest --test-dir build/c-debug --output-on-failure
```

`utf8proc` is detected with `pkg-config` when available. Development
builds can use the built-in IPA-focused fallback. To require the system
library:

```sh
cmake -S . -B build/c-debug -DMERKMAL_REQUIRE_UTF8PROC=ON
```

For installation as a downstream C dependency:

```sh
cmake -S . -B build/release \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/usr/local \
  -DMERKMAL_REQUIRE_UTF8PROC=ON
cmake --build build/release
cmake --install build/release
```

Installed consumers can use either CMake:

```cmake
find_package(merkmal CONFIG REQUIRED)
target_link_libraries(example PRIVATE merkmal::merkmal)
```

or pkg-config:

```sh
cc example.c $(pkg-config --cflags --libs merkmal) -o example
```

See [docs/distribution.md](docs/distribution.md) for static/shared builds,
custom prefixes, and `utf8proc` dependency notes. See
[docs/release-policy.md](docs/release-policy.md) for release dependency and
validation policy. See [docs/webassembly.md](docs/webassembly.md) for the
initial Emscripten and Node smoke-test path.

## C Example

```c
#include "merkmal.h"

#include <stdio.h>

int main(void) {
    mk_registry *registry = NULL;
    const mk_system *system = NULL;
    mk_string_list *features = NULL;
    double distance = 0.0;

    if (mk_registry_new_builtin(&registry) != MK_OK) {
        return 1;
    }
    if (mk_registry_get_system(registry, "descriptive", &system) != MK_OK) {
        mk_registry_free(registry);
        return 1;
    }
    if (mk_system_grapheme_features(system, "pʰ", &features) == MK_OK) {
        for (size_t i = 0; i < mk_string_list_size(features); i++) {
            puts(mk_string_list_get(features, i));
        }
        mk_string_list_free(features);
    }
    if (mk_system_segment_distance(system, "p", "b", &distance) == MK_OK) {
        printf("%f\n", distance);
    }
    mk_registry_free(registry);
    return 0;
}
```

See [docs/c-api.md](docs/c-api.md) for the public C surface and
[docs/distribution.md](docs/distribution.md) for installation and downstream
integration. See
[docs/runtime-model-format.md](docs/runtime-model-format.md) for the
line-oriented caller-supplied model format.

## Python Wrapper

The Python package builds `merkmal._native` with the CPython Limited API
and exposes the supported high-level operations from the top-level
`merkmal` module.

```sh
python -m pip install -e ".[dev]"
python -m pytest python/tests -q
python -m build --sdist --wheel
```

The wheel is built as `cp312-abi3` for broad CPython compatibility.

```python
import merkmal

print(merkmal.list_systems())
print(merkmal.get_features("pʰ"))
print(merkmal.distance("p", "b"))
print(merkmal.feature_distance("voiced", "voiceless"))
print(merkmal.segment_ipa("tʰoŋ⁵⁵"))
print(merkmal.is_segment("aːi³³", system="descriptive"))
```

### Tokenization: pick a policy deliberately

`segment_ipa` is *orthographic*: a token starts at each new base code point
unless a tie bar joins it to the previous one. It is stable and
language-neutral, but it splits sequences the systems themselves accept as
single segments.

`system_segment_ipa` is *system-aware*: longest match against the selected
system's inventory and synthesis grammar.

```python
merkmal.segment_ipa("tʃa")                              # ['t', 'ʃ', 'a']
merkmal.system_segment_ipa("tʃa", system="descriptive") # ['tʃ', 'a']
merkmal.segment_ipa("kpa")                              # ['k', 'p', 'a']
merkmal.system_segment_ipa("kpa", system="descriptive") # ['kp', 'a']
```

Longest match is a policy, not a truth: `kp` may be /k.p/ in a language with no
labial-velar, and `ai` may be hiatus rather than a diphthong. Results depend on
the selected system and its inventory version, so record both alongside any
stored tokenization. For curated historical corpora, supplying your own token
boundaries remains the most reproducible option.

### Tone

Tone is represented by a `tone-present` feature plus per-position level
features, so a mid-level tone is distinguishable from tonelessness:

```python
merkmal.distance("a", "a³³")   # > 0; these are not the same segment
merkmal.distance("a", "a³³", node_weights="ignore-tone")  # 0.0, deliberately
```

Each position carries an ordered Chao level, so distance is proportional to the
difference in pitch: `d(a¹¹, a²²) < d(a¹¹, a³³) < d(a¹¹, a⁵⁵)`. Both notations
work — superscript digits and the IPA tone letters U+02E5–U+02E9 — and `a¹`,
`a¹¹` and `a¹¹¹` are the same segment.

Chao runs of four or more digits are rejected as a whole rather than being
reinterpreted in pieces. The valued systems (`pbase-*`, `phoible`) have no
dimension a tone modifier can move, so they raise `NotImplementedError`
("unsupported model") for tone-bearing graphemes rather than returning a
falsely precise zero.

The Python package is intentionally native-only; unsupported legacy helper
APIs are no longer exported from `merkmal`.

Runtime model registration is exposed through an owned native registry:

```python
registry = merkmal.Registry()
registry.add_model_text("""
@model toy
@type categorical
@geometry clements-hume
grapheme X consonant voiceless bilabial stop
grapheme Y vowel open front unrounded
""")
print(registry.distance("X", "Y", system="toy"))
```

## Runtime Models

The C registry can accept a complete categorical model supplied as text:

```text
@model toy
@type categorical
@geometry clements-hume
grapheme X consonant voiceless bilabial stop
grapheme Y vowel open front unrounded
```

```c
mk_registry_add_model_text(registry, model_text);
```

The format is intentionally line-oriented, UTF-8, and grep-friendly.
Only categorical models are currently public in this format.

## Repository Structure

```text
merkmal/
├── include/                public C headers
├── src/                    C99 implementation and generated built-in data
├── cmake/                  CMake and pkg-config package templates
├── tools/                  data generators for compiled-in C tables
├── scripts/                active source-data validation and audit scripts
├── bench/                  footprint and lookup benchmarks, with a baseline
├── fuzz/                   libFuzzer harnesses and seed corpora
├── tests/c/                C tests
├── tests/golden/           parity fixtures for the native implementation
├── models/                 source model data used by generators
├── geometries/             source geometry data
├── diacritics/             source diacritic/tone/modifier mappings
├── typologies/             source typology data reserved for later C support
├── python/                 native Python wrapper
├── docs/legacy_python/     archived pre-C tutorials, notebooks, and scripts
└── docs/                   C API and format documentation
```

Contributing to the C core: [STYLE.md](STYLE.md) covers the module map,
ownership and error conventions, the build/test/sanitizer/fuzz commands, and
what to know before changing the generated data.

## License

The **source code** is MIT. See [LICENSE](LICENSE).

The **bundled data is not all MIT**, and the compiled-in tables are part of
every wheel:

| Data | License |
| --- | --- |
| `broad`, `descriptive`, `distinctive` | CC BY 4.0 — derived from CLTS v1.4.1 |
| `phoible` | CC BY 4.0 **by permission** (upstream: CC BY-SA 3.0) |
| `pbase-hc`, `pbase-jfh`, `pbase-spe`, `pbase-uftc` | CC BY 4.0 **by permission** (upstream: CC BY-NC-SA 4.0) |
| `classfeat` | MIT |

The distribution declares `MIT AND CC-BY-4.0`. **There is no non-commercial or
share-alike restriction on anything bundled here**, which is the practical
answer to "can my institution use this".

Two things to know before relying on that. Attribution is still required: credit
the upstream project each manifest names and say that changes were made. And
PHOIBLE and P-base are carried under CC-BY-4.0 **by permission**, not under
their own terms — CC-BY-SA-3.0 and CC-BY-NC-SA-4.0 do not allow dropping
share-alike or the non-commercial clause unilaterally, so the declaration rests
on a grant. Each manifest has a `relicensed` block whose grantor, date and
evidence are still `UNVERIFIED`; they must be established before the next data
release, the same way the CLTS derivation was established rather than assumed.

See [NOTICE](NOTICE), generated from `models/*/provenance.json`.

This is a record, not legal advice.
