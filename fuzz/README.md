# Fuzzing

Three harnesses, one per boundary that consumes caller-supplied text. Each
calls the core directly, so none of them needs a CLI, a file, or process state.

| harness | entry points |
|---|---|
| `fuzz_model_text` | `mk_parse_model_text` — the runtime-model parser |
| `fuzz_segment` | `mk_segment_ipa`, `mk_segment_ipa_merged`, `mk_normalize_grapheme`, `mk_split_tone` |
| `fuzz_resolve` | `mk_system_is_segment`, `mk_system_grapheme_features`, `mk_system_segment_distance`, `mk_system_segment_ipa`, against every built-in system |

## Running

libFuzzer, so Clang:

```sh
CC=clang cmake -S . -B build/fuzz \
  -DCMAKE_BUILD_TYPE=Debug \
  -DMERKMAL_USE_UTF8PROC=OFF \
  -DMERKMAL_BUILD_TESTS=OFF \
  -DMERKMAL_BUILD_FUZZERS=ON
cmake --build build/fuzz

./build/fuzz/fuzz_segment fuzz/corpus/segment -max_total_time=300
```

The harnesses are built with `-fsanitize=fuzzer,address,undefined`, so a
finding is reported rather than silently tolerated.

CI runs each for 60 seconds, which checks that the harnesses still build and
that the seed corpus survives. It is not a campaign; run those by hand.

Build with `-DMERKMAL_USE_UTF8PROC=ON` as well when changing normalization —
utf8proc adds an NFC/NFD pass that the fallback profile does not have, so the
two profiles are different code.

## Corpus

Seeds are real transcriptions: graphemes from the golden fixtures, tie-barred
affricates, clicks, tone-marked syllables, and two small runtime models. Add a
seed whenever a new construction becomes reachable.

## Crashes

A crashing input belongs in `tests/c/test_malformed.c` as a case, so it is
replayed by `ctest` forever after rather than only by whoever runs the fuzzer.
That file copies each input into a heap buffer sized exactly to its bytes, so
a read past the terminator is a heap overflow AddressSanitizer can see; the
same bytes in a string literal would run into adjacent rodata and pass.
