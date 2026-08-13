# Linguistics, phonology, historical linguistics, and typology review

Review date: 2026-08-12

Repository revision reviewed: `d0f57c9`

Status of the conclusions: design review and reproducible implementation audit, not an empirical validation study

## Executive conclusion

Merkmal is a promising C99 implementation of IPA normalization, feature lookup, and segment comparison. Its small ABI, immutable built-in tables, separation of source data from generated C, Unicode handling, and golden fixtures are good foundations. The linguistic contract of the library is currently weaker than its engineering contract, however.

The safest description of the current output is **experimental phonological dissimilarity**. It should not yet be described as a metric of phonological similarity, a probability or naturalness of sound change, a model of historical development, or evidence about cross-linguistic typology. The most important reasons are:

1. contrastively distinct representations can receive distance zero;
2. categorical features can be silently ignored or compressed into a single node-level difference;
3. valued comparisons change their denominator according to the pair being compared and violate the triangle inequality;
4. tonelessness collapses with mid tone, while four-digit tone strings can create contradictory features;
5. segmentation disagrees with the library's own segment recognizer for untied affricates and coarticulated stops;
6. the named Clements–Hume geometry is a project-specific numerical adaptation, not a direct implementation of that theory;
7. the archived directional-change derivation cannot establish historical direction and contains two implementation inversions;
8. model validation does not catch schema/data mismatches or meaningless runtime features; and
9. the bundled segment catalogs do not contain the language, genealogy, area, environment, or chronology needed for typological or historical claims.

The recommended product boundary is therefore:

> Merkmal maps supported transcriptions to versioned feature representations and computes configurable experimental dissimilarities. Historical and typological interpretations require a separate, validated model fitted to language-indexed data.

This wording does not diminish the library. A dependable, transparent segment prior is useful for alignment, candidate generation, transcription quality control, and exploratory comparison. It simply distinguishes those uses from claims the current data and algorithms cannot support.

## Scope and method

The review covers the active C and Python-facing implementation, source model data, the geometry, active validators and tests, and the archived CoreCog derivation script. It evaluates four distinct questions:

- **Representational adequacy:** can the model preserve distinctions it accepts?
- **Distance semantics:** what mathematical and linguistic meaning can be assigned to the returned number?
- **Historical adequacy:** does the method represent recurrent correspondences, direction, conditioning, and genealogy?
- **Typological adequacy:** is the unit of observation a language inventory, and is sampling genealogically and areally controlled?

Repository claims were checked against source data and code. External claims were checked against first-party database pages, original project documentation, or primary research publications; the references are collected at the end.

### Audit populations and limitations

The numerical results below use two explicitly different kinds of checks.

**Exhaustive audits** evaluated all 778 unique graphemes in the shared categorical source inventory at [`models/descriptive/inventory.tsv`](../models/descriptive/inventory.tsv). There are 302,253 unordered pairs. Every pair was evaluated in each categorical system. Feature-set and distance identity between `broad` and `descriptive` was also checked over all 778 graphemes and all 302,253 pairs. The geometry-effect audit covered all 101 labels obtainable through the reviewed descriptive inventory plus its supported modifier/tone feature paths, and tested whether each label could influence the default geometry calculation.

**Illustrative probes** are deliberately small counterexamples that expose a semantic or implementation property. A counterexample proves that a universal claim such as “this is a metric” is false, but its existence does not estimate how common the problem is in real corpora. The valued-distance triangle example, runtime `foo`/`bar` model, tone cases, and segmentation cases are illustrative probes.

The review does not include human perceptual judgments, gold phonological alignments, a family-balanced inventory sample, or an independently annotated historical corpus. Accordingly, it can diagnose internal inconsistencies and unsupported interpretations, but it cannot determine which replacement weighting scheme is empirically best.

## Prioritized findings

| Priority | Finding | Immediate consequence | Recommended disposition |
| --- | --- | --- | --- |
| P0 | Distinct categorical graphemes collapse to distance zero; feature coverage is incomplete | Distances do not reliably preserve accepted contrasts | Add explicit feature/dimension coverage and alias-equivalence contracts before changing weights |
| P0 | Valued scores use pair-dependent denominators and violate triangle inequality | The output is not a metric or stable geometry | Keep the old calculation only as a named compatibility dissimilarity; add a fixed-space distance |
| P0 | Tone is lossy and malformed long contours are accepted | Toneless and mid-tone forms collapse; invalid forms acquire contradictory features | Introduce explicit tone presence and structured tone parsing; reject unsupported lengths atomically |
| P1 | Segmentation and recognition disagree | Alignment changes with tie-bar spelling rather than linguistic analysis | Add a system-aware tokenizer with explicit policies |
| P1 | “Clements–Hume” names a custom tree and numerical weighting rule | The label overstates theoretical fidelity | Rename the current geometry `merkmal-clements-hume-inspired-v1` |
| P1 | Archived CoreCog directional costs reverse the stated cost logic and lack direction evidence | The resulting prior is not historically interpretable | Quarantine it; redesign around directed, family-balanced correspondence observations |
| P1 | Validators allow dead mappings and arbitrary runtime labels | Models can load while all relevant differences score zero | Make schema, header, feature, and geometry coverage validation strict |
| P2 | Current data are segment catalogs, not a typological sample | Inventory universals and frequencies cannot be inferred | Keep typology out of the core claim or add a separate language-indexed data layer |
| P2 | Provenance and licensing metadata are incomplete | Scientific reproducibility and redistribution status are unclear | Add per-artifact provenance, checksums, versions, citations, and SPDX licenses |

## 1. Categorical distance does not preserve contrasts

### Evidence

The exhaustive 778-grapheme audit found the following off-diagonal zero distances:

| System | Distinct grapheme pairs with distance `0` | Examples |
| --- | ---: | --- |
| `broad` | **802** | `y`–`yːː`, `p`–`p̥`, `t`–`t̺`, `k`–`k̚` |
| `descriptive` | **802** | the same examples and the same complete pair set as `broad` |
| `distinctive` | **599** | `c`–`k`, `c`–`q`, `a`–`æ`, `ŋ`–`ɴ`, `y`–`yːː` |

Some zero pairs may be intentional transcription aliases. The problem is not that every distinct Unicode string must have positive distance. The problem is that no alias-equivalence relation declares which zeroes are intended, while ordinary place, vowel-quality, quantity, laryngeal, and release distinctions are among the zeroes.

`broad` and `descriptive` are operationally identical at this revision: all 778 returned feature sets and all 302,253 pairwise distances agree, and their two source inventory files are byte-identical. Two public names therefore imply a choice that currently has no effect.

The exhaustive feature-effect audit found that **33 of 101 descriptive labels have no effect on the default geometry distance**. Examples include `devoiced`, `pre-nasalized`, `ultra-long`, `unreleased`, `velarized`, `apical`, `laminal`, and release-related labels. This is broader than a simple source-file mismatch: it asks whether a label the descriptive resolver can return can ever change the score.

The implementation explains these results. [`mk_process_node_feature`](../src/geometry.c) returns immediately for a leaf and silently returns for any feature that has no geometry node. For mapped non-leaf labels, [`mk_categorical_distance_resolved`](../src/geometry.c) groups all labels at the same node and records only a Boolean `differs` value. Multiple differences within a node therefore cost the same as one difference. Leaf weights are generated mechanically as `1 / depth` in [`tools/generate_c_data.py`](../tools/generate_c_data.py), rather than being derived from contrast data, perception, or sound changes.

### Linguistic interpretation

A feature representation may legitimately be underspecified, and a pseudometric may legitimately assign zero to declared equivalent objects. Neither fact licenses silent collapse. For phonology, the model must state whether its values represent phonetic descriptions, universal distinctive features, language-specific contrastive features, or transcription metadata. These are different objects. For historical work, even a good synchronic feature representation is only a prior: recurrent language-pair-specific correspondence patterns are central evidence for reconstruction ([List 2019](https://aclanthology.org/J19-1004/)).

### Alternatives

#### A. Fixed explicit dimensions, with an alias relation — recommended default

Compile every scoring feature into a declared dimension. Give each dimension a stable identifier, domain (`binary`, `categorical`, `ordinal`, or `set-valued`), missingness policy, weight, and geometry path. Reject an active feature with no scoring declaration. Define aliases separately, for example by a canonical-grapheme table or named equivalence classes.

How:

1. extend the model schema with `dimensions` and `aliases`;
2. make generation fail if a returned feature is neither a dimension value nor declared metadata;
3. compute weighted L1/Hamming distance over a fixed dimension set;
4. require `d(x,y)=0` only when `x` and `y` share an explicit alias class;
5. expose a coverage report listing scored, ignored-metadata, and invalid features.

Pros:

- precise semantics and predictable denominators;
- easy to test exhaustively;
- compatible with metric behavior for appropriate dimension distances;
- makes intended transcription equivalence explicit.

Cons:

- requires careful modeling of multivalued place, contour segments, and coarticulation;
- changes many current scores;
- forces decisions that the current free-form label representation postpones.

#### B. Weighted set distance within geometry nodes

Treat labels below a node as a weighted set and compare them with a set distance such as weighted Jaccard, rather than one Boolean node difference.

Pros:

- smaller change to categorical data;
- preserves multiple differences within a node;
- can naturally support multivalued articulations.

Cons:

- absence, negative value, and underspecification remain easy to conflate;
- Jaccard-like scores do not automatically express phonological opposition;
- geometry-node membership still needs complete validation.

#### C. Learn an embedding or pair-cost table

Fit weights or embeddings to human similarity judgments, gold alignments, or held-out correspondence tasks.

Pros:

- optimizes a real target task;
- can capture interactions not expressible with additive hand weights.

Cons:

- results depend heavily on languages, task, sampling, and transcription;
- less interpretable and harder to version;
- cannot repair an ill-defined input representation by itself.

**Recommendation:** implement A as the semantic core. Later allow B or C as separately named experimental scorers consuming the same validated representation.

### Acceptance tests

- Exhaust all accepted categorical grapheme pairs and fail on an undeclared off-diagonal zero.
- Assert positive distance for a curated contrast suite including quantity, vowel height/backness, major place, phonation, secondary articulation, release, and apical/laminal contrasts.
- Assert zero for declared orthographic/transcription aliases only.
- Fail model generation when a scorable feature lacks a dimension or is mapped to a nonexistent node.
- Assert that every public system name differs in either data, semantics, or declared alias status.

### Migration consequence

Changing dimensions or zero-equivalence classes changes observable numerical output. Treat it as a new model major version, not a patch. Preserve current results under explicit names such as `descriptive@1` and introduce the corrected model as `descriptive@2`; do not silently replace cached scores. Deprecate `broad@1` as an alias of `descriptive@1`, or define and test an actual broadening transform before retaining it as a distinct public choice.

## 2. Valued distance is a pairwise dissimilarity, not a metric

### Evidence

[`mk_valued_distance`](../src/geometry.c) includes a dimension only when both entries have a parseable value and omits it when both values are neutral. The set and total weight of compared dimensions therefore varies by pair. The same pair-dependent normalization occurs in scalar categorical distance when both scalar values are zero.

The following illustrative `pbase-hc` counterexample violates the triangle inequality:

```text
d(ɜ, ø̞̂ˑ) = 0.2142857142857143
d(ɜ, e̞)   = 0.04
d(e̞, ø̞̂ˑ) = 0.08

0.2142857142857143 > 0.04 + 0.08
```

One counterexample is sufficient to show that the function is not a metric. Pairwise deletion also makes scores less comparable: `0.2` computed over five observed dimensions is not the same evidence as `0.2` computed over thirty.

### Alternatives

#### A. Fixed-space weighted distance with an explicit missingness state — recommended default

Represent every model dimension for every segment as `positive`, `negative`, `neutral`, or `missing`. Use a fixed denominator. Define a per-dimension distance table; for example, opposite values cost `1`, neutral-to-polar costs a declared intermediate value, and missingness either raises an error or receives a separately reported penalty.

Pros:

- comparable scores and straightforward property tests;
- can be a true metric if each component distance is a metric and weights are nonnegative;
- preserves the distinction between neutral and unknown.

Cons:

- the correct interpretation of P-base states `n`, `o`, `x`, and `.` must be verified from provenance rather than guessed;
- any imputation or missingness penalty is a scientific choice.

#### B. Keep pairwise-complete comparison and return coverage

Retain current pairwise deletion but rename the function/output `pairwise_complete_dissimilarity` and return both score and comparable weight or dimension count.

Pros:

- backward compatible;
- avoids inventing values for missing observations;
- useful for exploratory comparison when coverage is high.

Cons:

- remains nonmetric;
- rankings can be driven by coverage;
- callers must propagate a richer result type and threshold low-coverage cases.

#### C. Multiple imputation or probabilistic expected distance

Estimate distributions for missing states conditional on model, segment class, or language, then integrate over uncertainty.

Pros:

- principled uncertainty propagation;
- potentially useful for historical models.

Cons:

- data-hungry and model-dependent;
- inappropriate as a universal built-in default;
- much more complex to explain and reproduce.

**Recommendation:** add A as the default `distance` in a new model/API version. Retain B under an explicit compatibility name. Do not introduce C until language-indexed training data and calibration targets exist.

### Acceptance tests

- Check non-negativity, symmetry, identity, and triangle inequality exhaustively where tractable and by deterministic property sampling elsewhere.
- Return or expose the same denominator for all pairs in fixed-space mode.
- Test `missing` separately from `neutral` for every state symbol.
- In compatibility mode, return comparison coverage and reject/flag values below a documented threshold.
- Do not use “metric,” “metric space,” or metric-dependent indexing/clustering claims for an algorithm that fails these properties.

### Migration consequence

This change reorders neighbors and affects alignments, clusters, thresholds, and stored features. Version scorer semantics independently from model data (`model_id`, `model_version`, `scorer_id`, `scorer_version`). Provide a transition utility that can calculate v1 and v2 scores side by side on a caller's corpus.

## 3. Tone representation is contrastively lossy and parser behavior is inconsistent

### Evidence

Level 3 returns no feature in [`mk_add_chao_level_features`](../src/system.c). Consequently, the descriptive representations and distances of toneless `a` and mid-tone `a³³` are identical:

```text
features_descriptive(a)    = features_descriptive(a³³)
distance_descriptive(a,a³³) = 0
```

For valued systems, synthesized tone labels have no valued-effect mapping. Both `a³³` and `a⁵⁵` are therefore identical to `a` in `pbase-hc` and `phoible` under the current score. Tone support is thus system-dependent in an undocumented and contrastively unsafe way.

The Chao sequence recognizer uses a three-element buffer and explicitly rejects a following fourth digit. The surrounding decomposition loop does not make that rejection atomic, however. The illustrative probe `a¹²³⁴` is accepted as a descriptive segment and returns mutually incompatible labels at the same tone positions. The exact set includes both lower and upper/raised information across reused onset, mid, and offset positions. At the tokenization layer, `segment_ipa("a¹²³⁴")` returns `['a', '¹²³⁴']`, so tokenization, recognition, and feature synthesis enforce different tone grammars.

### Linguistic interpretation

Mid tone is a positive tonal specification in a system that contrasts tones; it is not the same as absence of tone. Tone also belongs to a tone-bearing unit and may involve register, contour, association, floating tones, and language-specific normalization. Encoding it only as optional labels inside a segment bundle loses these distinctions.

### Alternatives

#### A. Structured tone object attached to a tone-bearing unit — recommended default

Parse tone separately from the segmental nucleus:

```text
Tone {
  present: true,
  levels: [3, 3],
  register: optional,
  contour: level | rising | falling | complex,
  notation: chao_digits,
  association: index/range of tone-bearing units
}
```

Project the structured tone into feature labels only for compatibility. Add `tone-present` so level 3 differs from tonelessness. Let each model declare `tone_support = none | categorical | contour`.

Pros:

- preserves absence versus mid level and segment versus suprasegment;
- permits future representation of association and floating tones;
- parser validity becomes independent of scoring features.

Cons:

- requires an ABI/API type beyond a flat feature set;
- language-specific tone interpretation remains outside a universal parser;
- callers that assume one token equals one segment bundle must adapt.

#### B. Extend the current flat features

Add `tone-present`, explicit mid values, and hard validation of one to three levels.

Pros:

- smaller ABI change;
- fixes the immediate collision and malformed-contour bug.

Cons:

- continues to conflate the tone-bearing segment with tone;
- association, register systems, and contour normalization remain awkward;
- flat labels can become internally contradictory unless schema validation is strong.

#### C. Treat tone as an opaque token

Tokenize and validate tone marks but do not score them in the core library.

Pros:

- scientifically honest and simple;
- lets language-specific consumers provide their own tone model.

Cons:

- no built-in tonal comparison;
- insufficient for tone-sensitive alignment without an extension.

**Recommendation:** use A in the long-term data model and B as an immediate corrective release. If valued systems have no tone dimensions, report tone as unsupported rather than returning zero as though equality had been established.

### Acceptance tests

- `a` and `a³³` differ in every system claiming tone support.
- `a³³` parses to `tone-present` plus an explicit mid level.
- A system declaring no tone support returns `unsupported`, not a falsely precise zero.
- One-, two-, and three-level contours have documented deterministic mappings.
- Four or more digits are rejected as a whole unless a documented resampling policy is selected.
- No accepted form can contain opposing values for one tone dimension.
- Tokenization, `is_segment`, and feature lookup share the same tone grammar.

### Migration consequence

Correcting mid tone changes feature equality, hashes, distance values, and likely alignments. Make strict tone parsing opt-in in a minor compatibility release, then default in the next major ABI/model version. Store the original tone spelling alongside the normalized structure so data can be re-exported without loss.

## 4. Segmentation and segment recognition use incompatible units

### Evidence

[`mk_segment_ipa`](../src/unicode.c) starts a new token at each new base code point unless a tie bar connects it to the previous base. It therefore produces:

```text
segment_ipa("tʃa") == ["t", "ʃ", "a"]
segment_ipa("kpa") == ["k", "p", "a"]
```

The descriptive system nevertheless recognizes untied `tʃ` and `kp` as single source-token segments in [`mk_synthesize_descriptive_complex`](../src/system.c). The same source representation is thus a valid segment when queried directly but is split before a word-level alignment. Tie-bar presence can change downstream edit operations even when the library otherwise normalizes tied and untied affricate spellings.

There is no universally correct context-free segmentation for every transcription. Untied affricates, doubly articulated stops, prenasalized consonants, diphthongs, geminates, and adjacent segment sequences can be ambiguous, sometimes language-specifically.

### Alternatives

#### A. System-aware longest matching with explicit policy — recommended default for word processing

Build a trie from the selected system's inventory and synthesis grammar. Normalize first, then choose the longest recognized token at each position. Expose policy switches for affricates, coarticulated stops, prenasalization, vowel sequences, tones, and explicit boundaries. Return diagnostics or alternative tokenizations when a match is ambiguous.

Pros:

- agrees with the system's own recognizer;
- efficient and predictable;
- handles known multicodepoint inventory entries.

Cons:

- longest match can be linguistically wrong (`kp` may be /k.p/ in a language);
- results depend on the selected system and inventory version;
- synthesis grammar must not greedily swallow arbitrary sequences.

#### B. Strict orthographic/Unicode segmentation

Keep the present tie-bar rule but document it as orthographic tokenization, not phonological segmentation.

Pros:

- stable, simple, and language-neutral;
- preserves explicit author markup.

Cons:

- inconsistent with untied multi-base inventory entries;
- poor default for many lexical datasets;
- makes historical alignment sensitive to transcription convention.

#### C. Require caller-supplied token boundaries

Accept presegmented input only for scientific workflows; offer heuristics merely as convenience utilities.

Pros:

- avoids pretending ambiguity can be universally resolved;
- best for curated historical datasets whose `Segments` field is authoritative.

Cons:

- less ergonomic;
- pushes normalization and error handling to callers.

**Recommendation:** expose all three. Name B `segment_unicode_ipa`, add `mk_system_segment_ipa` for A, and document C as the preferred reproducible input for historical corpora. Do not silently change the old function in place.

### Acceptance tests

- Under model-aware mode, `tʃa` becomes `[tʃ, a]` and `kpa` becomes `[kp, a]` when those tokens are recognized.
- Tied and untied declared aliases produce equivalent normalized token sequences under an affricate policy.
- Strict mode retains the documented base-codepoint behavior.
- Explicit boundaries override longest matching.
- Every token emitted in a system-aware mode passes that system's `is_segment` predicate.
- Ambiguous fixtures cover affricate/cluster, labial-velar/sequence, diphthong/hiatus, and geminate/sequence analyses.

### Migration consequence

Tokenization changes invalidate stored alignments and derived cognate scores. Add a policy argument and tokenization version to output metadata. Keep the current tokenizer under an explicit legacy name for at least one major release.

## 5. The geometry is Clements–Hume-inspired, not the published model

### Evidence

The file [`geometries/clements-hume.json`](../geometries/clements-hume.json) describes itself as “Clements & Hume (1995) feature geometry,” but it adds a `Prosodic` node containing length, nasalization, secondary articulations, ejectivity, and stress, and a separate onset–mid–offset tonal tree. The generator converts tree depth mechanically to `1 / depth` base weights in [`geometry_node_depth` and `geometry_leaves`](../tools/generate_c_data.py). The runtime then treats the hierarchy as a numerical aggregation structure.

Clements and Hume's chapter is a theory of internal feature organization, constituency, spreading, and the representation of simple, complex, and contour segments. It is not a proposal that similarity or sound-change cost equals inverse tree depth. The hierarchy may inspire a useful engineering representation, but the numeric transformation and extra nodes are Merkmal decisions.

### Alternatives

#### A. Rename and fully specify the custom geometry — recommended

Call it `merkmal-clements-hume-inspired-v1`. Document each node, each departure from the source theory, the rationale for depth weights, and the intended interpretation of the output.

Pros:

- accurate with minimal code disruption;
- makes experimentation legitimate and versionable;
- avoids falsely attributing project choices to the cited authors.

Cons:

- weaker marketing shorthand;
- does not itself validate the numerical choices.

#### B. Implement a theory-faithful representational model separately

Represent root, laryngeal and oral-cavity structure, articulator nodes, multiple association, and contour timing without immediately converting the graph to a scalar.

Pros:

- useful for phonological-rule and spreading research;
- separates representation from scoring.

Cons:

- substantially more complex;
- “faithful” still requires explicit interpretive choices and expert review;
- no scalar distance follows automatically.

#### C. Remove theoretical naming and use a neutral engineering taxonomy

Use names such as `articulatory-tree-v1` and cite multiple influences.

Pros:

- avoids theoretical overclaim entirely;
- supports pragmatic evolution.

Cons:

- loses useful intellectual lineage;
- users cannot easily compare it with known frameworks.

**Recommendation:** A now, optionally B later. Treat representation graphs and scorer weights as separate versioned artifacts.

### Acceptance tests

- Schema validation confirms all node references, unique feature ownership, and nonnegative finite weights.
- Documentation snapshots list every extension and every scoring rule.
- A scorer cannot infer weights from tree depth unless its scorer specification explicitly says so.
- Renaming does not alter v1 numerical compatibility; changed weights require a new scorer version.

## 6. The archived CoreCog direction prior is not historically valid

### Evidence

[`docs/legacy_python/scripts/derive_direction_costs.py`](legacy_python/scripts/derive_direction_costs.py) says the more frequent direction should receive a discount below `1.0`, but computes:

```python
ratio = pos_to_neg / total_changes
pos_to_neg = 2.0 * ratio
```

A more frequent `pos_to_neg` event therefore receives a *larger* multiplier, the opposite of the stated cost semantics.

The output caveat says direction is relative to the alphabetically first variety. In fact, `seen_varieties` and `list(seen_varieties.items())` retain input encounter order, and `combinations` uses that order. No alphabetical sort occurs. More fundamentally, an unordered comparison between two daughter languages does not identify which state is historically earlier. The script also:

- generates all language pairs within a cognate set, so larger sets contribute quadratically;
- allows densely represented datasets/families to dominate;
- has no proto-language, dated ancestor, branch orientation, or phylogenetic integration;
- pools environments, even though changes are often conditioned by neighboring segments, syllable position, stress, morphology, or prosody;
- does not represent borrowing, annotation uncertainty, alignment uncertainty, or correspondence regularity; and
- aligns with the same experimental dissimilarity that the procedure is then used to calibrate, creating potential circularity.

Primary computational historical-linguistics work treats recurrent correspondence patterns as central to reconstruction, and modern reconstruction workflows combine alignment with detected correspondence patterns rather than substituting a universal pair cost for them ([List 2019](https://aclanthology.org/J19-1004/); [List, Forkel & Hill 2022](https://aclanthology.org/2022.lchange-1.9/)).

### Alternatives

#### A. Quarantine the result as an undirected exploratory co-occurrence statistic — immediate recommendation

Do not load it as a direction cost. Rename outputs and documentation to state that pair orientation is arbitrary, fix the cost inversion if any “cost” is retained, and report family/dataset contributions.

Pros:

- honest and inexpensive;
- may still help diagnose alignments or feature confusions.

Cons:

- does not provide sound-change direction;
- existing derived numbers should not be used as priors.

#### B. Learn directed changes only from ancestor–descendant evidence — recommended redesign

Use reconstructed proto-forms with reviewed reflex alignments, genuinely earlier/later attestations, or a phylogenetic model that integrates direction uncertainty. Estimate smoothed conditional costs such as negative log probabilities, normalize by opportunities for change, and stratify or condition by environment.

At minimum, an observation should identify:

```text
family, branch, ancestor_state, descendant_state,
left_context, right_context, prosodic_position,
time_depth/ordering, cognate_set, source, confidence
```

Weight each cognate set and family so that large sets and well-sampled families do not dominate. Split evaluation by family, not by word pair, to test generalization.

Pros:

- direction has an interpretable evidential basis;
- supports conditioning and uncertainty;
- produces a genuine historical component.

Cons:

- much less training data;
- reconstructed ancestors are analyses, not direct observations;
- phylogenetic and annotation assumptions must be recorded.

#### C. Learn language-pair correspondence models without universal direction

For cognate detection/alignment, estimate recurrent correspondences for a specified language pair or subgroup, leaving diachronic orientation unresolved.

Pros:

- matches the evidence available in daughter–daughter data;
- often immediately useful for alignments and cognate validation;
- avoids false historical direction.

Cons:

- not portable as a universal prior;
- needs enough cognate data for each comparison.

**Recommendation:** apply A to the archived artifact and pursue C before B if the immediate goal is better alignment. Pursue B only with explicitly directed data.

### Acceptance tests

- Synthetic counts verify that a more frequent change receives lower cost when cost is defined as negative log probability or an equivalent monotonic transform.
- Reordering input rows cannot reverse a historical label.
- Each directed observation has explicit direction evidence.
- Each cognate set has bounded total weight; report effective sample size by family.
- Hold out complete families and report calibration as well as prediction accuracy.
- Compare against context-free, symmetric, and language-pair baselines.

### Migration consequence

Do not “correct” the current JSON in place because that would silently reverse consumers' behavior. Mark it invalid/legacy, assign any redesigned prior a new identifier and provenance manifest, and require callers to opt into historically directed scoring.

## 7. Validation does not enforce semantic integrity

### Evidence

Two static mismatches pass [`scripts/validate_models.py`](../scripts/validate_models.py):

- [`models/pbase-jfh/model.json`](../models/pbase-jfh/model.json) maps `"vocalic "` with a trailing space, while the inventory header is `vocalic`. The entire intended dimension is therefore absent from distance calculations.
- [`models/pbase-spe/model.json`](../models/pbase-spe/model.json) maps `spread`, but no `spread` column exists in its inventory.

The validator reports mapping counts but does not compare mapping keys exactly with inventory headers, reject surrounding whitespace, or require full column coverage.

Runtime categorical models are weaker still. [`docs/runtime-model-format.md`](runtime-model-format.md) states that `feature` declarations are not used for validation. This illustrative model registers successfully:

```text
@model arbitrary
@type categorical
@geometry clements-hume
grapheme X foo
grapheme Y bar
```

The returned distance is `0.0`, because both labels are unknown to the geometry. Successful registration therefore does not imply a meaningful comparison model.

### Alternatives

#### A. Strict schema and semantic validation — recommended default

Validate exact header-to-map agreement, whitespace, duplicate normalized names, state symbols, feature domains, geometry nodes, weights, and coverage. Runtime models must declare every feature and whether it is scorable or metadata. Reject unknown directives rather than ignoring them in strict mode.

Pros:

- failures occur at model load, not silently in results;
- supports reliable third-party models;
- makes generated-data review much easier.

Cons:

- rejects models that currently load;
- requires schema evolution and better diagnostics.

#### B. Permissive validation with warnings and coverage reports

Allow unknown features but exclude them explicitly and return a warning/report.

Pros:

- convenient for exploratory models;
- backward compatible.

Cons:

- warnings are often ignored;
- library results remain easy to misinterpret.

**Recommendation:** A for built-ins and the default runtime path. Offer B only behind an explicit `permissive` option, and attach validation warnings to the registered model metadata.

### Acceptance tests

- Reject leading/trailing whitespace in identifiers.
- Reject `geometry_map - inventory_columns` and, unless explicitly ignored, `inventory_columns - geometry_map`.
- Reject unknown geometry nodes, duplicate normalized features, illegal states, contradictory values, and non-finite/negative weights.
- The `foo`/`bar` model fails strict registration with actionable diagnostics.
- Generated built-ins pass exactly the same semantic validator as runtime models.
- CI fails if feature coverage, zero-collision count, or unsupported modifier count regresses.

### Migration consequence

Strictness can break caller-supplied models. Add a validation API that reports all errors before enforcing it, ship one deprecation cycle with explicit permissive mode, and make strict mode the default in the next major format version.

## 8. The current library is not yet a typological database

### Evidence and interpretation

The active models contain universal segment-type catalogs and feature tables. They do not retain, in the public analytical layer, which phonemes belong to which language inventory, whether a segment is contrastive or allophonic, the source analysis, marginal status, dialect/doculect identity, family, area, or sampling weight. “PHOIBLE coverage” in this repository therefore means coverage of PHOIBLE-like segment types, not coverage of languages or an adequate sample for typological inference.

PHOIBLE itself is inventory-indexed and warns through its documentation that filtering and sampling choices matter; it even supplies examples such as selecting one inventory per Glottocode. Its feature system was designed by PHOIBLE's developers for cross-linguistic descriptive adequacy, is loosely based on Hayes with additions from Moisik and Esling, and may change as languages and corrections are added ([PHOIBLE FAQ](https://phoible.org/faq)). It is not a universal Clements–Hume theory.

CLTS describes itself as a reference catalog linking transcription systems and datasets, not as a typological theory or a learned historical model ([CLTS 2.3.0](https://clts.clld.org/)). A catalog makes identifiers interoperable; it does not turn counts of distinct catalog entries into language frequencies.

### Alternatives

#### A. Keep typology explicitly out of the core library — recommended near-term

Present Merkmal as a segment representation and dissimilarity dependency. Let external language-indexed datasets provide inventories and sampling designs.

Pros:

- focused, maintainable scope;
- avoids bundling large, differently licensed data;
- callers can choose appropriate typological sources.

Cons:

- fewer turnkey typology functions;
- integration examples are still needed.

#### B. Add a separate language-inventory layer

Store doculect/inventory IDs, Glottocodes, source citations, marginality, inventory membership, genealogy, geography, and upstream version. Implement family/area-aware sampling separately from segment scoring.

Pros:

- enables reproducible inventory typology;
- connects representation failures to actual contrast systems;
- supports feature economy and implicational analyses.

Cons:

- substantial data governance, licensing, and update work;
- “one inventory per language” still requires analytical choices;
- risks making the small core ABI data-heavy.

**Recommendation:** A in the core, with B as an optional package or downstream project. Never expose typological frequency without an explicit unit of observation and sampling design.

### Acceptance tests for a future typology layer

- Every observation is traceable to a doculect, inventory, source, and upstream release.
- Analyses declare whether the unit is segment, inventory, doculect, language, family, or area.
- Sampling presets are deterministic and reported in output metadata.
- Results are stable under duplicate-inventory removal and are accompanied by family/area sensitivity analyses.
- Contrast audits operate within inventories, not merely over the universal segment catalog.

## 9. Provenance, versions, and licenses need artifact-level treatment

### Evidence

The built-in model JSON files contain a local name/version/description/license but generally no upstream release, URL, commit, extraction procedure, checksum, or full citation. The repository root is labeled MIT, while data artifacts declare different licenses. In particular:

- [`models/phoible/model.json`](../models/phoible/model.json) says generic `CC-BY`; the official PHOIBLE 2.0 site states **CC BY-SA 3.0 Unported** ([PHOIBLE](https://phoible.org/faq)).
- P-base's official site states **CC BY-NC-SA 4.0**, consistent with the P-base model files but materially different from MIT and relevant to commercial redistribution ([PBase](https://pbase.phon.chass.ncsu.edu/)).
- The categorical and IPA modifier data use descriptions and filenames suggesting IPA/CLTS-related derivation, but the artifact metadata do not establish which CLTS release, if any, was used. The current CLTS site states **CC BY 4.0** and supplies a versioned citation ([CLTS 2.3.0](https://clts.clld.org/)). Provenance must be established rather than inferred from filenames.

This is both a legal-packaging issue and a scientific reproducibility issue. A model called `1.0.0` locally is not reproducible unless its upstream inputs and transformation are identifiable.

### Recommended design

Add a manifest per generated artifact with at least:

```json
{
  "artifact_id": "...",
  "artifact_version": "...",
  "upstream_name": "...",
  "upstream_release": "...",
  "upstream_url": "...",
  "upstream_commit_or_doi": "...",
  "retrieved": "YYYY-MM-DD",
  "input_sha256": "...",
  "generator_version": "...",
  "transformation": "...",
  "citation": "...",
  "license_spdx": "...",
  "redistribution_notes": "..."
}
```

Generate a package-level `NOTICE`/data bill of materials from these manifests. Distinguish software licensing from each data artifact in the README and distributions. Have the maintainer verify license compatibility; this review identifies mismatches but is not legal advice.

Pros:

- reproducible builds and auditable updates;
- accurate attribution and machine-readable packaging;
- makes model changes reviewable independently of code.

Cons:

- requires reconstructing provenance for existing files;
- noncommercial/share-alike data may require packaging decisions or optional downloads.

### Acceptance tests

- Every bundled model and geometry has complete provenance and a recognized SPDX license expression.
- Generated C embeds artifact/scorer versions and source hashes.
- Release CI compares generated output with pinned inputs.
- Wheels/source distributions expose all required notices.
- A release cannot describe the entire package simply as MIT when differently licensed data are bundled.

## Recommended semantic architecture

The recurring design problem is that several distinct concepts are compressed into a single feature set and scalar. A more durable architecture separates them:

```text
input transcription
    -> normalization (versioned, loss-aware)
    -> tokenization (policy + model + diagnostics)
    -> representation (segmental features + tone/prosody + missingness)
    -> scorer (versioned mathematical function)
    -> task model (alignment/cognacy/correspondence/reconstruction)
    -> study design (languages, families, areas, chronology, evaluation split)
```

Each arrow should expose its policy and version. This produces deeper, more testable modules:

- normalization answers “which spellings are canonical equivalents?”;
- tokenization answers “what units does this analysis assume?”;
- representation answers “what properties are asserted, neutral, or unknown?”;
- the scorer answers “how is representation difference converted to a number?”;
- historical models answer “which correspondences recur in this language relationship and environment?”; and
- typological studies answer “what population and sampling process does this statistic describe?”

A scalar distance alone cannot answer all six questions.

## Validation strategy

### Layer 1: schema and static integrity

Run on every model, geometry, diacritic table, and runtime model:

- exact normalized identifier matching;
- no leading/trailing whitespace;
- complete feature-to-dimension/node coverage;
- explicit metadata-only exclusions;
- valid state domains and missingness meanings;
- unique nodes, dimensions, graphemes, aliases, and normalized forms;
- compatible model/scorer versions;
- complete provenance and license metadata.

### Layer 2: exhaustive finite-inventory properties

For every built-in finite inventory:

- enumerate all feature sets and pair scores;
- report off-diagonal zeros by declared alias class;
- test symmetry, bounds, and identity;
- test triangle inequality for scorers advertised as metrics;
- report per-feature influence and dead dimensions;
- report score and feature identity across supposedly distinct systems;
- snapshot nearest neighbors for a curated cross-section of segment types.

The existing 802/802/599 zero counts should become explicit baseline artifacts. A correction is expected to change them; CI should require review of the change rather than merely accepting a regenerated golden file.

### Layer 3: linguistic contrast suites

Maintain expert-reviewed fixtures for:

- vowel height, backness, rounding, ATR, nasalization, and length;
- consonant place, manner, laryngeal state, airstream, secondary articulation, and release;
- affricates, contour and coarticulated segments, prenasalization, and clicks;
- tone presence, level, register, and contour;
- declared aliases versus distinct transcriptions;
- underspecified and missing states.

Tests should assert meaningful relations or orderings, not arbitrary exact floating-point values where the science does not motivate them.

### Layer 4: external task validation

Evaluate scorers as priors on held-out tasks:

1. expert phonetic/phonological alignments;
2. cognate identification with full-family holdout;
3. correspondence-pattern recurrence and prediction;
4. reconstruction accuracy where directed gold analyses exist; and
5. human similarity judgments if perceptual similarity is claimed.

Compare against simple baselines: exact match, flat feature Hamming, established sound classes, and a language-pair correspondence model. Report uncertainty, coverage, family-level variation, and ablations. Tune on training families only.

### Layer 5: typological validation

If a language-inventory layer is added:

- reproduce a small number of published descriptive statistics from the pinned upstream release;
- rerun them under one-inventory-per-Glottocode and family/area-balanced samples;
- report sensitivity to source choice and duplicate doculects;
- never interpret catalog-entry frequency as language frequency.

## Staged roadmap

### Stage 0 — truthful contract and guardrails

Target: one small release.

- Call all current numeric outputs **experimental dissimilarities** in public documentation.
- State explicitly that valued v1 output is nonmetric.
- Rename/document the geometry as Clements–Hume-inspired.
- Quarantine the CoreCog direction artifact and prevent it from being loaded as a historical prior.
- Add known-issue tests for the exact probes in this review.
- Publish artifact-specific licensing and provisional provenance notes.

Exit criterion: a caller cannot reasonably mistake current output for a sound-change probability, a validated metric, or a typological statistic.

### Stage 1 — data and parser integrity

Target: next minor-to-major transition.

- Fix `vocalic ` and remove or justify `spread`.
- Implement strict model validation and coverage reporting.
- Reject malformed tone contours atomically.
- Add `tone-present` and explicit mid tone for systems claiming tone support.
- Add a system-aware tokenizer without changing legacy tokenization silently.
- Declare alias equivalence classes.

Exit criterion: every accepted model feature has declared semantics; tokenizer output is valid under its selected policy; no malformed tone form yields contradictory features.

### Stage 2 — versioned representation and scoring

Target: major model/API version.

- Separate representation, geometry, and scorer versions.
- Add fixed-space metric distance with explicit neutral/missing states.
- Retain pairwise-complete v1 only under a compatibility name and return coverage.
- Resolve `broad`/`descriptive` identity through deprecation or a real broadening transform.
- Add structured tone/prosody types or a clear extension path.

Exit criterion: the default scorer passes its advertised mathematical properties and all off-diagonal zeros are declared aliases.

### Stage 3 — empirical calibration

Target: research release.

- Assemble expert alignment and contrast benchmarks.
- Evaluate by held-out family and transcription source.
- Calibrate weights for named tasks rather than a single universal notion of similarity.
- Publish datasets, splits, metrics, ablations, and confidence intervals.

Exit criterion: claims about alignment or similarity name the target task and are supported by held-out results.

### Stage 4 — historical and typological extensions

Target: optional packages or downstream modules.

- Learn language-pair/subgroup correspondence models.
- Add genuinely directed ancestor–descendant models with context and uncertainty only where evidence supports them.
- Add a separately licensed language-inventory layer with genealogy/area-aware sampling if typological analysis is a product goal.

Exit criterion: historical direction is backed by direction evidence, and typological claims specify their language sample and unit of observation.

## Suggested claim language by maturity

### Safe now

> Merkmal is a C99 library for mapping supported IPA-like graphemes to several versioned feature representations and computing configurable experimental dissimilarities.

### Safe after Stages 1–2

> Merkmal provides validated, versioned segment representations, explicit tokenization policies, and both fixed-space metric distances and compatibility dissimilarities.

### Only after Stage 3 validation

> On the named held-out benchmark and sampling design, scorer X improves alignment/cognate/correspondence performance over baselines Y and Z.

### Avoid without separate evidence

- “distance equals phonological naturalness”;
- “distance predicts sound-change probability”;
- “Clements–Hume distance” for the current numerical rule;
- “typologically frequent” based on catalog segment types;
- “directional sound-change cost” from unordered daughter–daughter pairs; and
- “metric” for any scorer that violates triangle inequality or identity of indiscernibles.

## Source map

### Repository sources

- Project scope and current feature claims: [`README.md`](../README.md)
- Categorical and valued scoring implementation: [`src/geometry.c`](../src/geometry.c), especially `mk_process_node_feature`, `mk_categorical_distance_resolved`, `mk_scalar_categorical_distance`, and `mk_valued_distance`
- Tone parsing and descriptive complex synthesis: [`src/system.c`](../src/system.c), especially `mk_add_chao_level_features`, `mk_match_chao_tone_sequence`, `mk_decompose_diacritics`, and `mk_synthesize_descriptive_complex`
- Unicode-oriented segmentation: [`src/unicode.c`](../src/unicode.c), especially `mk_segment_ipa`
- Custom geometry and weight presets: [`geometries/clements-hume.json`](../geometries/clements-hume.json)
- Geometry code generation and inverse-depth weighting: [`tools/generate_c_data.py`](../tools/generate_c_data.py)
- Static validator: [`scripts/validate_models.py`](../scripts/validate_models.py)
- Runtime model validation contract: [`docs/runtime-model-format.md`](runtime-model-format.md)
- Exact valued-model mismatches: [`models/pbase-jfh/model.json`](../models/pbase-jfh/model.json), [`models/pbase-spe/model.json`](../models/pbase-spe/model.json), and their adjacent `inventory.tsv` files
- PHOIBLE metadata: [`models/phoible/model.json`](../models/phoible/model.json)
- Archived CoreCog derivation: [`docs/legacy_python/scripts/derive_direction_costs.py`](legacy_python/scripts/derive_direction_costs.py)

### Primary external sources

- Clements, G. N. & Hume, E. V. (1995), “The Internal Organization of Speech Sounds,” in *The Handbook of Phonological Theory*, pp. 245–306. Bibliographic record and chapter context: [Wiley's phonological-theory references](https://onlinelibrary.wiley.com/doi/abs/10.1002/9781444335262.wbctp0027).
- List, J.-M. (2019), “Automatic Inference of Sound Correspondence Patterns across Multiple Languages,” *Computational Linguistics* 45(1): 137–161. [ACL Anthology and DOI](https://aclanthology.org/J19-1004/).
- List, J.-M., Forkel, R. & Hill, N. (2022), “A New Framework for Fast Automated Phonological Reconstruction Using Trimmed Alignments and Sound Correspondence Patterns.” [ACL Anthology and DOI](https://aclanthology.org/2022.lchange-1.9/).
- Moran, S. & McCloy, D. (eds.) (2019), *PHOIBLE 2.0*. Feature-system scope, sampling guidance, citation, and CC BY-SA 3.0 license: [official PHOIBLE FAQ](https://phoible.org/faq).
- List, J.-M., Anderson, C., Tresoldi, T. & Forkel, R. (2024), *CLTS 2.3.0*. Catalog scope, versioned citation, and CC BY 4.0 license: [official CLTS site](https://clts.clld.org/).
- Mielke, J., *PBase*. Database scope and CC BY-NC-SA 4.0 license: [official PBase site](https://pbase.phon.chass.ncsu.edu/).

## Final recommendation

Do not discard the current implementation. Preserve it as a versioned compatibility scorer, narrow its claim, and use its transparent structure to build stronger contracts around it. The highest-value sequence is:

1. strict coverage and alias validation;
2. atomic, explicit tone parsing;
3. policy-driven system-aware tokenization;
4. a fixed-space metric scorer with explicit missingness;
5. artifact-level provenance/versioning; and only then
6. task-specific empirical calibration or separate historical/typological layers.

That sequence turns the current toolkit into a reliable substrate for computational historical linguistics without asking a universal segment distance to stand in for phonological analysis, the comparative method, or typological sampling.
