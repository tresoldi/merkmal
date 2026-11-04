# Release plan: 0.9.0

Written 2026-11-04, from a review of the tree at `7bb6e3e`, both open issues,
and the work done on `claude/serene-mendel-f1pwb7` since. It records what is
ready, what still blocks a tag, and where the library should go next as a
phonological tool. Delete or archive it once 0.9.0 is out.

## 1. Where the release stands

0.9.0 is the first release of the C core and the native Python wrapper. Nothing
from it has been published: 0.1.0–0.6.0 were the retired pure-Python and Go
implementation, and the 1.0.0 the tree carried until 2026-08-20 was never
released.

Done on this branch, each with tests:

| Change | Why it mattered for a release |
| --- | --- |
| `ʏ`, `ʮ`, `ʯ` may open a vowel component (closes #2) | German `ɔʏ̯`, `ʏɐ` were unknown; the test now covers every one-letter vowel as either element of a V+V cluster |
| `ɚ`/`ɝ` read as `ə˞`/`ɜ˞` | standard IPA letters every system rejected |
| Normalization compiled in, utf8proc dropped (closes #3) | one commit gave different strings on different machines; now no build can |
| Place diacritics replace the base place | `n̪̊`, `t̪ʲʰ`, `ɹ̪`, `d̪̤`, `ɾ̪` failed in the two default systems |
| Contradictory diacritics refused | `s̪̩̯`, `ts̪̻̺` resolved and scored 0.0 against either mark |
| Contrast baseline has no `UNDECLARED` row | the README's "every zero is on the record, with reasons" was false for 56 pairs |
| Tie-barred complex segments, `ˁ`, `ε` | `t͡ʂ` failed while `tʂ` read |
| License and version documentation corrected | the README still claimed the withdrawn CC-BY-4.0 relicense of PHOIBLE and P-base |

Verified at the branch head: `ctest` (12 tests, including the utf8proc oracle
over all 1,112,064 scalar values; GCC and Clang with `-Werror`, ASan with
`detect_stack_use_after_return`, and without utf8proc installed), the Python suite,
`regenerate_golden.py --check` (no fixture moved), `contrast_baseline.py
--check`, `bench_coverage.py --check`, `check_generated_data.py`, static
analysis, ruff, mypy, and an sdist installed into a clean virtual environment.
Lexibank coverage under the default system went from 7,027 to 7,059 of 7,396
segment types.

## 2. Blocking the tag

In order. Items marked **(owner)** need someone with rights or knowledge
this session did not have.

1. **Apply the workflow patch (owner).** The session's GitHub token lacks the
   `workflow` scope, so `.github/workflows/` could not be pushed. The patch
   `docs/release/workflows.patch` brings `ci.yml` in line with the
   dependency-free library (one sanitizer profile; utf8proc is now only the
   oracle; a Python 3.13 step that reproduces the Unicode tables) and adds
   `wheels.yml`, a cibuildwheel + trusted-publishing workflow that does not
   exist today. The current `ci.yml` still passes without the patch. Apply with
   `git apply docs/release/workflows.patch`, check it, push, delete the patch.
   `wheels.yml` has not run anywhere: check the runner labels and the
   cibuildwheel version on its first `workflow_dispatch`.
2. **Two distributions — done.** `merkmal` carries every table; the new
   `merkmal-cc-by` carries only the CC-BY-4.0 systems (`distinctive`,
   `descriptive`), with no PHOIBLE or P-base data in its wheels or sdist. On
   PyPI, create the project `merkmal-cc-by` and a trusted publisher for each
   project, with the environments `pypi-full` and `pypi-cc-by` that
   `wheels.yml` names. Still open for 1.0: a valued system under permissive
   terms, so `merkmal-cc-by` users have one too (see §3).
3. **Rebuild the web demo (owner, needs emcc).** `web/merkmal.wasm` was built
   from `cc02289`, before this work and much else. Run `web/build-wasm.sh`,
   commit, and let `pages.yml` deploy. `tests/wasm/run_node_smoke.sh` should
   pass first; neither could run here.
4. **Provenance gap — done.** PHOIBLE's retrieval date is recorded as
   2026-08-01, on the maintainer's word, and the manifest says so.
5. **`BRANCH_LOCAL_ONLY.md` — decided.** The review being public is fine;
   parts of it will be folded elsewhere later. Nothing in the sdist or wheel
   includes either file.
6. **Answer #2 and #3** when the branch merges, so Arca Verborum and regulae
   know that `HAVE_UTF8PROC` stays `True` in every build and that
   `UNICODE_VERSION` is the thing to key caches on. Arca's CI workaround
   (installing libutf8proc, `MERKMAL_REQUIRE_UTF8PROC=1`) becomes unnecessary
   but harmless.
7. **Tag `v0.9.0`**, let `wheels.yml` publish, and archive the release on
   Zenodo so that `CITATION.cff` can carry a DOI.

## 3. Making it more robust as a phonological tool

Ranked by value to users against cost. The first group is mostly engineering
and could follow 0.9.0 quickly; the second carries a modelling claim and
needs the evaluation in §4 behind it.

### Robustness

- **Caller-supplied source conventions.** The global convention table can only
  take spellings that mean one thing everywhere (`ʧ`, `ɚ`, `ˁ`). Most of the
  remaining unread Lexibank types are spellings that are consistent within a
  source and ambiguous across sources: macron below `a̱` (retracted, ATR, or a
  tone, depending on the Africanist tradition), spacing tone letters `ˉ`/`ˋ`,
  Indological `ṛ`, archiphoneme capitals `R`/`T`/`S`. A per-call or
  per-registry profile, recorded in `operation_fingerprint`, would let a user
  say what their source means without the library guessing for everyone. It
  is the orthography-profile idea, applied at the segment level.
- **Put `UNICODE_VERSION` in the system fingerprint.** Normalization decides
  which graphemes resolve, so it is part of a result's identity. It is exposed
  but not fingerprinted, because adding it changes every digest. Do it once, as
  a v2 payload, before people start storing fingerprints.
- **Cluster tokenization through longest match** (paper-notes §12.6), so that
  `ntʃ` is *n + tʃ* rather than *n + t + ʃ* under `segment_ipa` too.
- **Diacritic semantics beyond place.** This branch makes place marks
  replace place. The same question applies to manner and phonation marks on a
  base that already carries the opposite value (`b̥` vs `p`, `ʋ̞`). The
  contradictory-pair table is a start. Auditing each mark for "adds",
  "replaces" or "refuses" would turn an implicit policy into a data file.

### Linguistic coverage and modelling

- **A permissively licensed valued system.** Commercial users currently have
  no valued system they can use. PanPhon's feature table (Mortensen et al.
  2016) is the obvious candidate if its license is confirmed compatible. It
  would also make the cross-theory comparison in `manuscript-notes.md` §1 less
  dependent on four P-base variants that share an inventory, which that note
  already lists as a weakness.
- **Tone on the valued systems.** They refuse tone-bearing graphemes rather
  than return a false zero, which is correct. A structured tone value on the
  tone-bearing unit (paper-notes §12.4) would let them answer.
- **Length, gemination and syllabicity as tiers.** Long-vowel and doubled-vowel
  spellings are reconciled by a waiver in `cluster.c`. If length were a
  property of the timing tier rather than of a segment, the waiver would not
  be needed.
- **Contrastive vs. allophonic use** belongs to the typology package, not the
  core, per the scope the README already sets. It is still the most requested
  thing a segment-type catalog cannot answer.

## 4. Toward publication

There are two outputs, and they should be kept apart.

1. **A software paper (JOSS or similar).** The release, archived with a DOI,
   tests, documentation and a statement of need are what JOSS reviews, and
   most of that now exists. The README's "what the number means" section is
   the statement of need it asks for. Blocked on §2.
2. **A research paper** from `docs/manuscript-notes.md` and
   `docs/paper-notes.md`. The notes already list their own gaps: a by-system
   breakdown for the cross-theory disagreement, a tonal corpus, more families
   for the fitted-cost result, and the independence caveat for the P-base
   variants. Two more come out of this work:
   - **External validation against perception.** The distances are stipulated,
     and the README says so. Consonant and vowel confusion matrices (Miller &
     Nicely 1955 and later replications) are the standard independent test of
     a segment-similarity measure, and none is reported yet.
   - **The coverage story is a finding.** Most of what the default system
     cannot read in Lexibank is the sources' own CLTS markup, not unsupported
     phonetics. In `williamsonbenuecongo`, every one of the top unread tokens
     is `<?>` or `<<…>>`. That distinction belongs in the paper's coverage
     section, with token and type rates reported separately, as
     `manuscript-notes.md` §3 argues.
