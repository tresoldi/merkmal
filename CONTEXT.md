# Domain language

The words this repository uses for the things it models, and what each one is
pinned to. Terms are defined once here; `STYLE.md` says how the C core is built,
`docs/c-api.md` states the public contract, and `docs/geometry.md` explains the
weights. Where a term names something in the code, the code is the authority and
this file points at it.

Add a term here when a name starts carrying meaning the code cannot state for
itself. Do not restate what a header already says clearly.

## Segments and their spellings

**Grapheme** — a written string handed to the library, such as `p`, `t͡ʃ`, `ai³³`.
An input, not a claim that anything recognizes it.

**Segment** — a grapheme the system resolves to a feature set. `mk_system_is_segment`
answers whether a grapheme is one.

**Feature** — a label a segment carries: `bilabial`, `voiceless`, `vowel`. In a
**valued** system a feature is written `name=state`, as in `nasal=-`.

**Feature view** (`mk_feature_view`) — a feature set and nothing else: no
grapheme, no inventory row. Everything that scores takes one. It exists because
five call sites were fabricating inventory rows on the stack to score, two of
them inventing a grapheme the scorer then read.

**Tone** — pitch, written in Chao digits or letters. A tone may bind to a
nucleus (`a³³`) or stand alone as its own segment (`a` `³³`), which is how
CLTS/BIPA and the field's CLDF wordlists write it. A bare tone token carries the
`tonal-autosegment` label and sits on its own **tier**.

**Cluster** — a segment written as more than one part: a diphthong `ai`, an
untied affricate `tʃ`, a geminate `aa`. The resolver synthesizes these; no
inventory lists them.

**Component** — one part of a cluster, carrying its own spelling and the
features the resolver worked out for it. A cluster is composed from its
components, so they are resolved before the cluster exists; carrying them
forward is why scoring never resolves a spelling twice.

**Nucleus** — the first component of a cluster. It carries more weight than the
rest when a cluster is scored against a plain segment.

**Cluster policy** — the five stipulated numbers that say how a cluster's parts
compose into one distance. Data, in the geometry file's `cluster_policy`, for
the same reason the tier cost is.

## Systems and data

**System** — one named feature model: `descriptive`, `phoible`, `pbase-hc`.
Eight are compiled in; more can be added at runtime from **model text**.

**Kind** — how a system expresses features. **Categorical** systems list labels;
**valued** systems give every declared dimension a state. `MK_SYSTEM_TRAINED` is
a declared kind with no implementation.

**Inventory** — a system's table of grapheme-to-features rows.

**Registry** — the set of systems available to a caller. Immutable per system
once installed; adding a runtime model never moves a system already handed out.

**Model text** — the line-oriented format a caller supplies to add a system at
runtime. The library's only parser of untrusted input.

**Geometry** — the tree of phonological nodes and leaves, with the weights that
say how much each costs. `geometries/clements-hume.json`.

## Resolution

**Resolution** — turning a grapheme into a feature set, and the record of how
that happened.

**Resolution path** — *which* construction produced the answer: an inventory
row, a row found after stripping a tie bar, or one of five synthesizers. The
path is part of the answer, because it says whether a segment was attested or
constructed. See `src/resolver.h`.

**Synthesizer** — code that builds a feature set for a spelling no inventory
lists. Five of them, tried in order, each handing off with
`MK_ERR_UNKNOWN_GRAPHEME`.

## Scoring

**Dissimilarity** — the scalar the library returns. Experimental, not a metric,
not a probability of sound change. `README.md` says at length what it is not.

**Scorer** — the module that turns two feature views into a dissimilarity. Three
of them, and which one a system reaches is part of the answer the way a
resolution path is:

- **leaf** — scores through the compiled geometry's leaves, node groups and
  ordered scales. Takes a NULL system and scores against the geometry alone.
- **scalar** — scores through the system's own declared `scalar_dimensions`,
  never reading a geometry leaf.
- **valued** — scores through the system's geometry map and `name=state` cells.
  Requires a system.

`mki_scorer_for` in `src/geometry.c` chooses, and nothing else does.

**Coverage** — the share of a system's declared dimensions on which both
segments had a value. It separates "identical" from "nothing to compare", both
of which score `0.0`. Measured against the system, not the segments, so a
segment compared with itself is below 1.0 whenever it has a gap.

**Comparability** (`mk_comparability`) — why a score is or is not a measurement:
comparable, cross-tier, or no shared dimension.

**Tier** — tone and segments occupy different ones. A cross-tier pair is scored
by the geometry's declared `tier_policy.cross_tier_cost` rather than measured,
because gold alignments never place a tone in a column with a segment.

**Weight preset** — a named set of node weights (`flat` and others) selecting
how much each level of the geometry costs.

## What the library is not

Stated here because the words are easy to reach for and wrong:

- Not an **aligner**. It scores one segment against one segment: a substitution
  cost with no gap model and no sequence operations.
- Not a **typology**. The bundled models are segment-type catalogs and record no
  language, inventory membership, or sampling weight.
- Not a model of **sound change**. Phonetic similarity and diachronic
  probability are different quantities, and measurement says so.
