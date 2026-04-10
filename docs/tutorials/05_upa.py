#' ---
#' title: "Working with UPA (Uralic Phonetic Alphabet)"
#' ---
#'
#' # Working with UPA (Uralic Phonetic Alphabet)
#'
#' The Uralic Phonetic Alphabet (UPA), also called Finno-Ugric
#' Transcription (FUT), is the standard transcription system for
#' Uralic linguistics.  Setala (1901) introduced it, it was
#' revised in the 1970s, and it remains the default in most
#' Uralistics publications and datasets, including UraLex
#' (Syrjanen et al. 2013).
#'
#' UPA does not convert mechanically to IPA.  It encodes
#' phonological function alongside phonetic quality, uses
#' different symbol conventions (Greek letters for fricatives,
#' small capitals for devoicing, acute accent for palatalization),
#' and has diacritics that remap vowel identity rather than
#' modify it.
#'
#' merkmal has a transcription adapter for UPA.  You pass UPA
#' input, it gets mapped to IPA internally, and all feature
#' systems and distance metrics work from there.
#'

import merkmal
from merkmal.upa import adapt, adapt_segment, segment_upa

#'
#' ## Segmenting UPA strings
#'
#' UPA leans on combining diacritics.  A single vowel can
#' carry a breve below, a macron, and an inverted breve above
#' at the same time.  The segmenter groups each base character
#' with its combining marks into one token.
#'

# A simple word: no diacritics
print("Simple segmentation:")
print(f"  kala → {segment_upa('kala')}")

# A word with combining breve below (back unrounded vowel marker)
print(f"  ni̮r  → {segment_upa('ni̮r')}")

# A word with modifier prime (palatalization)
print(f"  vedʹ  → {segment_upa('vedʹ')}")

# Macron (long vowel), acute accent (palatalization)
print(f"  ńēləm → {segment_upa('ńēləm')}")

#'
#' Each segment is a base letter plus whatever diacritics are
#' attached.  Whitespace, hyphens (verb stems in UraLex often
#' end with `-`), and morpheme boundary markers (`_`) are
#' stripped.
#'

print(f"\n  mən-  → {segment_upa('mən-')}")
print(f"  ka_la → {segment_upa('ka_la')}")

#'
#' ## Adapting UPA to IPA
#'
#' The `adapt` function segments a UPA string and maps each
#' segment to its IPA canonical form:
#'

print("\nUPA → IPA adaptation:\n")

examples = [
    ("käsi", "hand (Finnic)"),
    ("ńēləm", "tongue (Mansi)"),
    ("ni̮r", "nose (Komi)"),
    ("ŋüŋkə", "nose (Nganasan)"),
    ("βüt", "water (Meadow Mari)"),
    ("tǖ", "fire (Selkup)"),
    ("mi̮ni̮ni̮", "to go (Udmurt)"),
    ("bi̮ˀ", "water (Nganasan)"),
    ("nenä", "nose (Ingrian)"),
]

for upa, gloss in examples:
    ipa = adapt(upa)
    print(f"  {upa:12s} → {' '.join(ipa):16s}  ({gloss})")

#'
#' These are actual UraLex entries.  The mappings:
#'
#' - `ń` (acute) → `ɲ` (palatal nasal)
#' - `ē` (macron) → `eː` (long vowel)
#' - `i̮` (breve below) → `ɯ` (back unrounded close vowel)
#' - `ü` (umlaut) → `y` (front rounded close vowel)
#' - `ä` → `æ` (front open vowel)
#' - `ˀ` → `ʔ` (glottal stop)
#' - `β` (Greek beta) → `β` (bilabial fricative, same in IPA)
#'
#' ## UPA consonant conventions
#'
#' ### Greek letters for fricatives
#'
#' UPA uses Greek letters where IPA uses specialised symbols:
#'

print("Greek letter mapping:\n")
greek = [
    ("β", "bilabial fricative"),
    ("γ", "voiced velar fricative"),
    ("δ", "voiced dental fricative"),
    ("ϑ", "voiceless dental fricative"),
    ("χ", "voiceless velar fricative"),
    ("φ", "voiceless bilabial fricative"),
]
for upa_ch, desc in greek:
    ipa_ch = adapt_segment(upa_ch)
    print(f"  UPA {upa_ch} → IPA {ipa_ch}  ({desc})")

#'
#' UPA `χ` maps to IPA `x` (velar), not IPA `χ` (uvular).
#' Same Unicode codepoint, different meaning in each system.
#'
#' ### Palatalization: acute vs prime
#'
#' UPA marks palatalization in two ways that are not equivalent:
#'
#' - Acute accent (ń, ś, ĺ, etc.): the consonant IS palatal.
#'   Place of articulation shifts to palatal.
#' - Modifier prime (lʹ, dʹ, nʹ): secondary palatalization.
#'   The consonant keeps its place but adds a palatal co-articulation.
#'

print("\nPalatalization:\n")

acute_examples = [
    ("ń", "palatal nasal (not just palatalized n)"),
    ("ś", "alveolo-palatal fricative"),
    ("ĺ", "palatal lateral"),
    ("ć", "alveolo-palatal affricate"),
    ("ŕ", "palatalized trill"),
]
for upa_ch, desc in acute_examples:
    ipa_ch = adapt_segment(upa_ch)
    print(f"  {upa_ch} → {ipa_ch}  ({desc})")

print()
prime_examples = [
    ("lʹ", "palatalized lateral"),
    ("dʹ", "palatalized alveolar stop"),
    ("nʹ", "palatalized alveolar nasal"),
]
for upa_seg, desc in prime_examples:
    ipa_seg = adapt_segment(upa_seg)
    print(f"  {upa_seg} → {ipa_seg}  ({desc})")

#'
#' This distinction matters in Uralic phonology.  Finnic
#' languages have secondary palatalization (prime), while some
#' Samoyedic languages have true palatal consonants (acute).
#' The adapter keeps them apart.
#'
#' ### Postalveolar consonants (caron)
#'

print("\nPostalveolar (caron):\n")
caron_examples = [
    ("š", "voiceless postalveolar fricative"),
    ("ž", "voiced postalveolar fricative"),
    ("č", "voiceless postalveolar affricate"),
    ("ǯ", "voiced postalveolar affricate"),
]
for upa_ch, desc in caron_examples:
    ipa_ch = adapt_segment(upa_ch)
    print(f"  {upa_ch} → {ipa_ch}  ({desc})")

#'
#' ### Small capitals (devoiced)
#'
#' UPA uses small capitals for devoiced consonants, where IPA
#' would use a voiceless diacritic (ring below):
#'

print("\nSmall capitals (devoiced):\n")
smallcap_examples = [
    ("ᴅ", "devoiced alveolar stop"),
    ("ᴢ", "devoiced alveolar fricative"),
    ("ʙ", "devoiced bilabial stop"),
    ("ɢ", "devoiced velar stop"),
]
for upa_ch, desc in smallcap_examples:
    ipa_ch = adapt_segment(upa_ch)
    print(f"  {upa_ch} → {ipa_ch}  ({desc})")

#'
#' ### Retroflex consonants (dot below)
#'
#' A dot below marks retroflex articulation in UPA:
#'

print("\nRetroflex (dot below):\n")
for base, ipa_name in [("t", "ʈ"), ("d", "ɖ"), ("n", "ɳ"), ("s", "ʂ")]:
    upa_seg = base + "\u0323"
    ipa_seg = adapt_segment(upa_seg)
    print(f"  {base}̣ → {ipa_seg}  (retroflex {base})")

#'
#' ## UPA vowel conventions
#'
#' ### Umlaut vowels
#'

print("\nUmlaut vowels:\n")
print(f"  ä → {adapt_segment('ä')}  (front open, like IPA æ)")
print(f"  ö → {adapt_segment('ö')}  (front rounded mid, like IPA ø)")
print(f"  ü → {adapt_segment('ü')}  (front rounded close, like IPA y)")
print(f"  å → {adapt_segment('å')}  (rounded open-mid back, like IPA ɔ)")

#'
#' ### Back unrounded vowels (breve below)
#'
#' The most frequent diacritic in UraLex, with 1,508
#' occurrences.  A breve below remaps a front vowel to its
#' back unrounded counterpart:
#'

print("\nBreve below (back unrounded):\n")
breve_examples = [
    ("i̮", "ɯ", "close back unrounded"),
    ("e̮", "ɤ", "close-mid back unrounded"),
    ("a̮", "ɑ", "open back"),
]
for upa_seg, expected, desc in breve_examples:
    ipa_seg = adapt_segment(upa_seg)
    print(f"  {upa_seg} → {ipa_seg}  ({desc})")

#'
#' This is a semantic diacritic: it changes the vowel's
#' identity, not just its quality.  IPA has no equivalent
#' combining mark.  Komi and Udmurt use these vowels
#' everywhere.
#'

# Demonstrate with a full Komi word
print(f"\n  Komi 'nose': ni̮r → {' '.join(adapt('ni̮r'))}")
print(f"  Udmurt 'go': mi̮ni̮ni̮ → {' '.join(adapt('mi̮ni̮ni̮'))}")

#'
#' ### Inverted breve above (backing diacritic)
#'
#' The inverted breve above (U+0311) backs a vowel.  On
#' schwa, it marks the back reduced vowel of Proto-Samoyedic
#' reconstruction (Janhunen 1977):
#'
#' - `ə` = front-ish reduced vowel (< Proto-Uralic \*i)
#' - `ə̑` = back reduced vowel (< Proto-Uralic \*u)
#'
#' Nganasan keeps this contrast phonemically.
#'

print("\nInverted breve above (backing):\n")
print(f"  ə  → {adapt_segment('ə')}  (central/front schwa)")
print(f"  ə̑ → {adapt_segment('ə̑')}  (back reduced vowel, ≈ ɤ)")

#'
#' ### Vowel length (macron) and reduction (breve)
#'

print("\nVowel length:\n")
for v in ["ā", "ē", "ī", "ō", "ū", "ǖ", "ǟ", "ȫ"]:
    print(f"  {v} → {adapt_segment(v)}")

print("\nShort/reduced vowels:\n")
for v in ["ă", "ĭ", "ŏ"]:
    print(f"  {v} → {adapt_segment(v)}")

#'
#' ## Using UPA with merkmal's feature systems
#'
#' The `transcription="upa"` parameter works with any of
#' merkmal's public API functions.
#'
#' ### Feature lookup
#'

print("\nFeatures from UPA input:\n")

upa_segments = ["š", "ń", "i̮", "ü", "δ", "ə̑"]
for seg in upa_segments:
    ipa = adapt_segment(seg)
    feats = merkmal.get_features(seg, transcription="upa")
    if feats:
        print(f"  UPA {seg} (→ IPA {ipa}):")
        print(f"    {sorted(feats)}\n")

#'
#' Same features you get by passing the IPA equivalent
#' directly.
#'
#' ### Natural class queries through UPA
#'
#' What do the UPA palatals share?  Adapt them, then query:
#'

palatal_segs = ["ń", "ś", "ĺ", "ć"]
ipa_segs = [adapt_segment(s) for s in palatal_segs]
shared = merkmal.derive_class_features(ipa_segs)
print(f"Shared features of UPA palatals ({', '.join(palatal_segs)}):")
print(f"  IPA equivalents: {', '.join(ipa_segs)}")
print(f"  shared: {shared}")

#'
#' ### Distance computation
#'
#' Distances between UPA segments, using `segment_distance`
#' with `transcription="upa"`:
#'

print("\nDistances between UPA consonant pairs:\n")

upa_pairs = [
    ("s", "š", "alveolar vs postalveolar fricative"),
    ("s", "ś", "alveolar vs alveolo-palatal fricative"),
    ("t", "ť", "alveolar stop vs palatalized"),
    ("n", "ń", "alveolar vs palatal nasal"),
    ("k", "χ", "velar stop vs velar fricative"),
]

for a, b, desc in upa_pairs:
    d = merkmal.segment_distance(
        a, b, system="distinctive", transcription="upa"
    )
    ipa_a = adapt_segment(a)
    ipa_b = adapt_segment(b)
    print(f"  {a}~{b}  d={d:.3f}  ({desc})")
    print(f"       IPA: {ipa_a}~{ipa_b}")

#'
#' `s`~`ś` and `n`~`ń` involve a place shift (alveolar to
#' palatal), so their distances are higher than `t`~`ť`, where
#' only secondary palatalization is added without moving place.
#'

print("\nDistances between UPA vowel pairs:\n")

vowel_pairs = [
    ("i", "i̮", "front vs back unrounded close"),
    ("e", "e̮", "front vs back unrounded mid"),
    ("ü", "u", "front rounded vs back rounded close"),
    ("ö", "o", "front rounded vs back rounded mid"),
    ("ə", "ə̑", "central vs back schwa"),
    ("ā", "a", "long vs short"),
]

for a, b, desc in vowel_pairs:
    d = merkmal.segment_distance(
        a, b, system="distinctive", transcription="upa"
    )
    ipa_a = adapt_segment(a)
    ipa_b = adapt_segment(b)
    print(f"  {a}~{b}  d={d:.3f}  ({desc})")
    print(f"       IPA: {ipa_a}~{ipa_b}")

#'
#' `i`~`i̮` is /i/ vs /ɯ/, a backness difference.
#' `ü`~`u` is /y/ vs /u/, same thing.  Both end up with
#' similar distances.  Length (`ā`~`a`) is cheaper because
#' only duration changes.
#'
#' ## A small Uralic comparison
#'
#' The word for "water" across several Uralic languages, all
#' in UPA:
#'

print("\n'Water' across Uralic languages:\n")

water_forms = [
    ("Finnish", "vesi"),
    ("Ingrian", "vesi"),
    ("Meadow Mari", "βüt"),
    ("Komi-Zyrian", "va"),
    ("Udmurt", "vu"),
    ("Nganasan", "bi̮ˀ"),
    ("Selkup", "üt"),
    ("Sosva Mansi", "βit"),
]

ipa_forms = {}
for lang, upa_form in water_forms:
    ipa_segs = adapt(upa_form)
    ipa_str = " ".join(ipa_segs)
    ipa_forms[lang] = ipa_segs
    print(f"  {lang:18s}  UPA: {upa_form:8s}  IPA: {ipa_str}")

#'
#' All from Proto-Uralic \*wete.  Initial \*w became `v`,
#' `β`, or `b` depending on the branch; medial \*t stuck
#' around in some languages and dropped in others; the final
#' vowel survived in Finnic but nowhere else.
#'
#' ### Pairwise word distances
#'
#' A rough comparison using just the initial consonant, since
#' the forms vary too much in length for a full alignment:
#'

print("\nInitial consonant distances (UPA, Distinctive system):\n")

langs_with_initial_c = [
    ("Finnish", "v"),
    ("Meadow Mari", "β"),
    ("Nganasan", "b"),
    ("Sosva Mansi", "β"),
    ("Selkup", "ü"),  # vowel-initial, skip
]

# Compare just the labial initials
labial_langs = [
    ("Finnish", "v"),
    ("Meadow Mari", "β"),
    ("Nganasan", "b"),
    ("Sosva Mansi", "β"),
]

header = f"  {'':18s}" + "".join(f" {l:>10s}" for l, _ in labial_langs)
print(header)
for lang_a, seg_a in labial_langs:
    row = f"  {lang_a:18s}"
    for lang_b, seg_b in labial_langs:
        d = merkmal.segment_distance(
            seg_a, seg_b, system="distinctive", transcription="upa"
        )
        row += f" {d:10.3f}"
    print(row)

#'
#' Finnish `v` and Mari `β` are both labial fricatives, so
#' distance is zero.  Nganasan `b` is a stop, farther from
#' both.  The known developments (\*w → v in Finnic, \*w → β
#' in Mari, \*w → b in Nganasan) match what the distances
#' show.
#'
#' ## Multi-system comparison on UPA data
#'
#' Different feature systems give different distances for the
#' same UPA pairs, as with IPA input (see tutorial 2).  Here
#' is what that looks like with Uralic data:
#'

print("\nSystem comparison for UPA pairs:\n")

test_pairs = [
    ("s", "š"),
    ("n", "ń"),
    ("i", "i̮"),
    ("k", "χ"),
]

systems = ["descriptive", "distinctive", "classfeat"]
header = f"  {'pair':6s}" + "".join(f" {s:>12s}" for s in systems)
print(header)
print("  " + "-" * (len(header) - 2))

for a, b in test_pairs:
    row = f"  {a}~{b:3s}"
    for sys_name in systems:
        feats_a = merkmal.get_features(a, system=sys_name, transcription="upa")
        feats_b = merkmal.get_features(b, system=sys_name, transcription="upa")
        if feats_a is not None and feats_b is not None:
            d = merkmal.distance(
                adapt_segment(a), adapt_segment(b), system=sys_name
            )
            row += f" {d:12.3f}"
        else:
            row += f" {'n/a':>12s}"
    print(row)

#'
#' ## Compositional diacritics
#'
#' When a UPA segment is not in the static table, it gets
#' decomposed into base + diacritics and each diacritic is
#' applied according to its UPA semantics.  Proto-language
#' reconstructions and dialectological transcriptions with
#' unusual combinations still work:
#'

print("\nCompositional decomposition:\n")

composed = [
    ("lʹ", "lateral + prime (palatalized)"),
    ("kʹ", "velar stop + prime (palatalized)"),
    ("tʹ", "alveolar stop + prime (palatalized)"),
    ("s\u0323", "alveolar fricative + dot below (retroflex)"),
]

for seg, desc in composed:
    ipa = adapt_segment(seg)
    feats = merkmal.get_features(seg, transcription="upa")
    print(f"  {seg} → {ipa}  ({desc})")
    if feats:
        print(f"    features: {sorted(feats)[:6]}...")

#'
#' ## Encoding normalization
#'
#' Real UPA data is messy.  The adapter normalizes common
#' encoding variants:
#'

print("\nEncoding normalization:\n")

# Cyrillic schwa (U+04D9) vs IPA schwa (U+0259)
cyrillic_schwa = "\u04D9"
ipa_schwa = "\u0259"
print(f"  Cyrillic ə (U+04D9) → {adapt_segment(cyrillic_schwa)}")
print(f"  IPA ə (U+0259)      → {adapt_segment(ipa_schwa)}")
print(f"  Same result: {adapt_segment(cyrillic_schwa) == adapt_segment(ipa_schwa)}")

# Precomposed vs decomposed forms
import unicodedata
pre = "\u0144"  # ń precomposed
dec = unicodedata.normalize("NFD", pre)  # n + combining acute
print(f"\n  Precomposed ń (U+0144) → {adapt_segment(pre)}")
print(f"  Decomposed n+◌́         → {adapt_segment(dec)}")
print(f"  Same result: {adapt_segment(pre) == adapt_segment(dec)}")

#'
#' ## Coverage
#'
#' All 84 unique codepoints in UraLex 2.0 (11 languages,
#' 3,961 forms) are covered.  The static table has 90+
#' entries; compositional decomposition handles the rest.
#'
#' Conventions at a glance:
#'
#' | UPA convention | Mechanism | Example |
#' |---|---|---|
#' | Greek letters | Static mapping | δ → ð |
#' | Acute accent (palatal) | Static + compositional | ń → ɲ |
#' | Modifier prime (palatalized) | Compositional | lʹ → lʲ |
#' | Caron (postalveolar) | Static + compositional | š → ʃ |
#' | Small capitals (devoiced) | Static mapping | ᴅ → d̥ |
#' | Umlaut (front rounded) | Static + compositional | ü → y |
#' | Macron (long) | Static + compositional | ā → aː |
#' | Breve (short) | Static + compositional | ă → a̯ |
#' | Breve below (back unrounded) | Semantic remapping | i̮ → ɯ |
#' | Inverted breve above (backing) | Semantic remapping | ə̑ → ɤ |
#' | Dot below (retroflex) | Compositional | ṭ → ʈ |
#' | Ring above (rounded) | Compositional | å → ɔ |
#' | Low ring (devoicing) | Compositional | l˳ → l̥ |
#' | Dot above | Ignored (Lithuanian) | ė → e |
#'
#' ## References
#'
#' - Janhunen, J. (1977). *Samojedischer Wortschatz: Gemeinsamojedische Etymologien*. Castrenianumin toimitteita 17. Helsinki.
#' - Setala, E. N. (1901). Uber transskription der finnisch-ugrischen sprachen. *Finnisch-Ugrische Forschungen*, 1, 15-52.
#' - Syrjanen, K., Honkola, T., Korhonen, K., Lehtinen, J., Vesakoski, O., & Wahlberg, N. (2013). Shedding more light on language classification using basic vocabularies and phylogenetic methods: a case study of Uralic. *Diachronica*, 30(3), 323-352.
#' - ISO/IEC JTC1/SC2/WG2 N2419 (2002). Proposal for encoding characters for the Uralic Phonetic Alphabet. Unicode Consortium.
