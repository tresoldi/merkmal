"""Tests for the native C-backed top-level wrapper slice."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import merkmal
import pytest
from merkmal.cli import main

pytestmark = pytest.mark.skipif(
    getattr(merkmal, "_native", None) is None,
    reason="native extension is not built",
)


def test_native_lists_expanded_systems() -> None:
    systems = merkmal.list_systems()
    assert systems == sorted(
        [
            "descriptive",
            "distinctive",
            "pbase-hc",
            "pbase-jfh",
            "pbase-spe",
            "pbase-uftc",
            "phoible",
        ]
    )


def test_semantic_fingerprint_is_auditable_and_stable() -> None:
    payload, digest = merkmal.system_fingerprint(system="descriptive")

    assert payload.startswith("schema=merkmal-system-fingerprint-v1\n")
    assert "system=descriptive\n" in payload
    assert len(digest) == 64
    assert set(digest) <= set("0123456789abcdef")
    assert digest == hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert digest == merkmal.system_fingerprint(system="descriptive")[1]
    assert digest != merkmal.system_fingerprint(system="phoible")[1]

    registry = merkmal.Registry()
    registry.add_model_text(
        "@model fingerprint-toy\n@type categorical\n"
        "grapheme X consonant voiceless bilabial stop\n"
    )
    runtime_payload, runtime_digest = registry.system_fingerprint(system="fingerprint-toy")
    assert "model_version=runtime-model-v1\n" in runtime_payload
    assert len(runtime_digest) == 64


def test_native_wrapper_surface_is_small() -> None:
    assert "load_model" not in merkmal.__all__
    assert not hasattr(merkmal, "CategoricalEngine")
    assert "Registry" in merkmal.__all__


def test_native_features_and_validity() -> None:
    # `consonantal`, `obstruent` and `non-continuant` are derived by the
    # generator: the inventory NAME never says them, so the geometry leaves for
    # them used to be decorative and every manner distinction cost the same.
    assert merkmal.get_features("p") == frozenset(
        {"bilabial", "consonant", "consonantal", "labial", "non-continuant",
         "obstruent", "stop", "voiceless"}
    )
    assert "syllabic=+" in merkmal.get_features("a", system="phoible")
    assert "aspirated" in merkmal.get_features("pʰ")
    assert "affricate" in merkmal.get_features("t͡ʃ")
    assert "spreadGlottis=+" in merkmal.get_features("bʰ", system="phoible")
    assert merkmal.is_segment("t͡ʃ")
    assert not merkmal.is_segment("not-ipa")
    assert not merkmal.is_segment("<?>", system="descriptive")
    with pytest.raises(merkmal.SourceMarkerError):
        merkmal.get_features("<?>", system="descriptive")


def test_native_descriptive_tone_bearing_vowels_are_segments() -> None:
    assert merkmal.merge_tone_digits(["k", "a", "³¹"]) == ["k", "a³¹"]
    assert merkmal.is_segment("a³¹", system="descriptive")
    assert merkmal.is_segment("a⁵¹", system="descriptive")
    assert merkmal.is_segment("ə³³", system="descriptive")
    assert merkmal.is_segment("a³³", system="descriptive")
    assert merkmal.is_segment("o³³", system="descriptive")
    assert merkmal.is_segment("i³³", system="descriptive")
    assert not merkmal.is_segment("p³¹", system="descriptive")
    assert not merkmal.is_segment("p³³", system="descriptive")

    features_31 = merkmal.get_features("a³¹", system="descriptive")
    assert {"vowel", "tone-onset-3", "tone-offset-1"} <= features_31

    features_51 = merkmal.get_features("a⁵¹", system="descriptive")
    assert {"vowel", "tone-onset-5", "tone-offset-1"} <= features_51

    # Chao level 3 is a positive mid specification. It used to produce no
    # features at all, which made a mid-tone vowel indistinguishable from a
    # toneless one; both the presence flag and the level are now explicit.
    features_33 = merkmal.get_features("a³³", system="descriptive")
    assert "vowel" in features_33
    assert "tone-present" in features_33
    assert {"tone-onset-3", "tone-mid-3", "tone-offset-3"} <= features_33
    assert features_33 != merkmal.get_features("a", system="descriptive")
    assert merkmal.distance("a", "a³³", system="descriptive") > 0.0


def test_native_descriptive_broadened_source_tokens() -> None:
    positive = [
        "ai",
        "au",
        "ei",
        "aːi",
        "iau",
        "ai³³",
        "aːi³³",
        "ɐu³³",
        "əi³¹",
        "ɛï",
        "ɛï³³",
        "ɛï³¹",
        "ɛï³⁵",
        "ɛï⁴⁵",
        "ɛï⁴⁵³",
        "ᵐb",
        "ⁿd",
        "ⁿdʳ",
        "ɡb",
        "gb",
        "kp",
        "kpʷ",
        "kx",
        "gɣ",
        "kɣ",
        "tʂ",
        "tʂʰ",
        "ŋ̀",
        "m̀",
        "ä",
        "ă",
        "ç",
        "ḭ",
        "ṳ",
        "ṵ",
        "ṵː",
        "ṽ",
        "ñ",
        "ń",
        "ỹ",
        "kw",
        "gw",
        "ŋg",
        "kk",
        "ll",
        "tt",
        "nn",
        "pp",
        # Precomposed tone-marked vowels. These were rejected while their
        # canonically equivalent NFD spellings were accepted, and
        # merkmal.normalize() returns the precomposed form.
        "ě",
        "ǎ",
        "ý",
        "ǐ",
        "ǒ",
        "ǔ",
        # The two most frequent NC sequences in the world's languages, which a
        # two-item blocklist rejected while accepting mp, nt and ŋg.
        "mb",
        "nd",
    ]
    for token in positive:
        assert merkmal.is_segment(token, system="descriptive"), token

    negative = [
        "<?>",
        "<<->>",
        "<<[>>",
        "<<]>>",
        "<<~>>",
        "<</>>",
        "<<.>>",
        "→",
        "+",
        "∼",
        "_",
        "S",
        "T",
        "p³³",
    ]
    for token in negative:
        assert not merkmal.is_segment(token, system="descriptive"), token

    # Bare tone tokens are segments. CLTS writes tone as its own segment, which
    # is how the field's CLDF wordlists spell it; the slash forms resolve
    # because normalization takes the BIPA side of "source/BIPA".
    for token in ["³¹", "³⁵", "⁵⁵", "⁰", "˥˩", "¹/¹", "³/¹"]:
        assert merkmal.is_segment(token, system="descriptive"), token
    assert "tonal-autosegment" in merkmal.get_features("³¹", system="descriptive")
    assert "tone-neutral" in merkmal.get_features("⁰", system="descriptive")
    # Neutral tone is not a pitch level: it must not collapse into one.
    assert merkmal.distance("⁰", "³³", system="descriptive") > 0.0

    # A tone run too long to be a contour, and neutral tone mixed with a pitch
    # level, are recognized shapes with rejected content. The library reports
    # that as a parse error rather than an unknown grapheme, and the difference
    # is the point: it says the token *is* tone and is spelled wrong.
    for token in ["¹²³⁴", "⁰³"]:
        assert not merkmal.is_segment(token, system="descriptive"), token
        with pytest.raises(merkmal.NativeError):
            merkmal.get_features(token, system="descriptive")

    features_ai = merkmal.get_features("ai", system="descriptive")
    assert {
        "vowel",
        "diphthong",
        "n1-open",
        "n2-close",
        "move-height-open-close",
    } <= features_ai
    assert "open" not in features_ai
    assert "close" not in features_ai

    features_long = merkmal.get_features("aːi³³", system="descriptive")
    assert {"diphthong", "n1-long", "tone-present"} <= features_long

    features_tone = merkmal.get_features("əi³¹", system="descriptive")
    assert {"diphthong", "n1-mid", "tone-onset-3", "tone-offset-1"} <= features_tone

    features_precomposed = merkmal.get_features("ɛï³³", system="descriptive")
    assert {
        "vowel",
        "diphthong",
        "n1-open-mid",
        "n2-close",
        "n2-centralized",
    } <= features_precomposed

    features_affricate = merkmal.get_features("kɣ", system="descriptive")
    assert {"consonant", "affricate", "velar"} <= features_affricate
    assert "voiceless" not in features_affricate

    features_labialized = merkmal.get_features("kw", system="descriptive")
    assert {"consonant", "complex", "consonant-cluster"} <= features_labialized
    assert {"n1-velar", "n2-labio-velar"} <= features_labialized

    features_geminate = merkmal.get_features("kk", system="descriptive")
    assert {"consonant", "complex", "consonant-cluster", "geminate"} <= features_geminate

    assert {"consonant", "nasalized"} <= merkmal.get_features("ñ", system="descriptive")
    assert {"vowel", "nasalized"} <= merkmal.get_features("ỹ", system="descriptive")
    assert {"vowel", "creaky"} <= merkmal.get_features("ḭ", system="descriptive")
    assert {"vowel", "breathy"} <= merkmal.get_features("ṳ", system="descriptive")
    assert {"vowel", "creaky"} <= merkmal.get_features("ṵ", system="descriptive")
    assert {"vowel", "creaky", "long"} <= merkmal.get_features("ṵː", system="descriptive")

    features_v_tilde = merkmal.get_features("ṽ", system="descriptive")
    assert {"consonant", "nasalized"} <= features_v_tilde
    assert "vowel" not in features_v_tilde
    assert "voiced" not in features_affricate
    assert "sibilant" not in features_affricate

    features_syllabic = merkmal.get_features("ŋ̀", system="descriptive")
    assert {"syllabic", "tone-onset-2", "tone-offset-2"} <= features_syllabic

    for token in negative:
        with pytest.raises(ValueError):
            merkmal.get_features(token, system="descriptive")


def test_native_distance_matches_golden_probe() -> None:
    # The default is `distinctive`, which scores through its own
    # scalar_dimensions rather than the geometry tree. Naming the system keeps
    # this probe pinned to a value rather than to whatever the default is.
    assert math.isclose(merkmal.distance("p", "b"), 0.1492537313, abs_tol=1e-10)
    assert math.isclose(
        merkmal.distance("p", "b", system="descriptive"), 0.125, abs_tol=1e-10
    )
    assert math.isclose(
        merkmal.distance("p", "b", system="phoible"),
        # 0.0366 before the PHOIBLE cells were rebuilt from the pinned upstream
        # table. Reading its `0` -- "this feature does not apply" -- as `-` made
        # /p/ and /b/ agree on dimensions neither has, which shrank the distance.
        0.0394736842,
        abs_tol=1e-10,
    )
    assert merkmal.feature_distance("voiced", "voiceless") == 2
    # The tree distance is defined over the tree only, and now says so rather
    # than writing 999 into an int whose real answers run from 0 to 8. Tone
    # levels are positions on an ordered scale, and place labels are mapped to
    # the Place node rather than being leaves under it, so neither has a path.
    for a, b in (("tone-onset-1", "tone-offset-1"), ("bilabial", "velar")):
        with pytest.raises(ValueError, match="no path in the geometry tree"):
            merkmal.feature_distance(a, b)
    assert math.isclose(
        merkmal.distance("p", "b", system="distinctive", node_weights="flat"),
        0.14285714285714285,
        abs_tol=1e-10,
    )
    assert merkmal.distance("ai", "ai", system="descriptive") == 0.0
    assert merkmal.distance("ai", "a", system="descriptive") < merkmal.distance(
        "ai", "i", system="descriptive"
    )
    assert 0.0 < merkmal.distance("ai", "au", system="descriptive") < 1.0
    assert math.isfinite(merkmal.distance("ai³³", "aːi³³", system="descriptive"))


def test_native_unicode_helpers() -> None:
    assert merkmal.normalize("g") == "ɡ"
    assert merkmal.normalize("sh/ʃ") == "ʃ"
    assert merkmal.normalize("ã") == "ã"
    assert merkmal.normalize("ï") == "ï"
    assert merkmal.normalize("ḭ") == "ḭ"
    assert merkmal.normalize("ṳ") == "ṳ"
    assert merkmal.normalize("ṵ") == "ṵ"
    assert merkmal.normalize("ṽ") == "ṽ"
    assert merkmal.segment_ipa("tʰoŋ⁵⁵") == ["tʰ", "o", "ŋ", "⁵⁵"]
    assert merkmal.segment_ipa_merged("tʰoŋ⁵⁵") == ["tʰ", "o⁵⁵", "ŋ"]
    assert merkmal.merge_tone_digits(["tʰ", "o", "ŋ", "⁵⁵"]) == ["tʰ", "o⁵⁵", "ŋ"]
    assert merkmal.segment_ipa("ⁿda") == ["ⁿd", "a"]
    assert merkmal.segment_ipa("n̥a") == ["n̥", "a"]


def test_native_split_tone_inverts_the_merge() -> None:
    assert merkmal.split_tone("a¹³") == ("a", "¹³")
    assert merkmal.split_tone("o³¹") == ("o", "³¹")
    # An untoned segment has no tone, which is None rather than "" so that
    # "carries no tone" cannot be confused with "carries an empty tone".
    assert merkmal.split_tone("kʰ") == ("kʰ", None)
    # Splitting every merged segment recovers the word with tone separated.
    merged = merkmal.segment_ipa_merged("tʰo³¹pan¹³")
    assert [merkmal.split_tone(s) for s in merged] == [
        ("tʰ", None),
        ("o", "³¹"),
        ("p", None),
        ("a", "¹³"),
        ("n", None),
    ]
    # A standalone tone cluster is not a segment.
    with pytest.raises(ValueError):
        merkmal.split_tone("³¹")


def test_native_registry_runtime_model() -> None:
    registry = merkmal.Registry()
    registry.add_model_text(
        "\n".join(
            [
                "@model toy",
                "@type categorical",
                "@geometry clements-hume",
                "grapheme X consonant voiceless bilabial stop",
                "grapheme Y consonant voiced bilabial stop",
            ]
        )
    )
    assert "toy" in registry.list_systems()
    assert registry.get_features("X", system="toy") == frozenset(
        {"consonant", "voiceless", "bilabial", "stop"}
    )
    assert registry.is_segment("Y", system="toy")
    assert math.isclose(
        registry.distance("X", "Y", system="toy"), 0.2777777777777778, abs_tol=1e-10
    )


def test_runtime_model_manifest_travels_with_operation_provenance() -> None:
    registry = merkmal.Registry()
    manifest = {
        "name": "toy",
        "version": "1.0",
        "source": "test fixture",
        "interpretation": "phonemic",
        "license": "CC0-1.0",
    }
    registry.add_model_text(
        "@model toy\n@type categorical\ngrapheme X consonant stop\n",
        manifest=manifest,
    )
    assert registry.model_manifest(system="toy") == manifest
    payload, _ = registry.operation_fingerprint(system="toy")
    assert "model_manifest" in payload


def test_operation_fingerprint_includes_result_options() -> None:
    payload_a, digest_a = merkmal.operation_fingerprint(node_weights="flat")
    payload_b, digest_b = merkmal.operation_fingerprint(node_weights="ignore-tone")
    assert "merkmal-operation-fingerprint-v1" in payload_a
    assert digest_a != digest_b
    assert len(digest_a) == 64
    registry = merkmal.Registry()
    registry.add_model_text("@model toy\n@type categorical\ngrapheme X consonant stop\n")
    _, runtime_digest = registry.operation_fingerprint(system="toy", node_weights="flat")
    assert runtime_digest != digest_a

def test_runtime_model_rejects_unavailable_geometry() -> None:
    registry = merkmal.Registry()
    with pytest.raises(NotImplementedError, match="unsupported runtime geometry"):
        registry.add_model_text(
            "@model toy\n@type categorical\n@geometry deep-clements-hume\n"
            "grapheme X consonant stop\n"
        )


def test_registry_and_module_share_one_implementation() -> None:
    """A Registry method is the module-level call pointed at that registry.

    The two used to be separate C functions differing only in which registry
    pointer they read, which is how the default system name came to be written
    out four times.
    """
    registry = merkmal.Registry()

    # Omitting the system uses the same default on both paths.
    assert registry.get_features("p") == merkmal.get_features("p")
    assert registry.is_segment("a") == merkmal.is_segment("a")
    assert registry.distance("p", "b") == merkmal.distance("p", "b")
    assert registry.list_systems() == merkmal.list_systems()
    assert registry.system_segment_ipa("tʃa") == merkmal.system_segment_ipa("tʃa")

    # Naming it explicitly agrees with the default.
    assert registry.get_features("p", system="descriptive") == registry.get_features("p")
    assert merkmal.distance("p", "b", node_weights="flat") == registry.distance(
        "p", "b", node_weights="flat"
    )


def test_runtime_model_stays_inside_its_registry() -> None:
    registry = merkmal.Registry()
    registry.add_model_text(
        "@model private\n@type categorical\n@validation permissive\ngrapheme Q consonant stop\n"
    )

    assert "private" in registry.list_systems()
    # The default registry is shared, so nothing may leak into it.
    assert "private" not in merkmal.list_systems()
    with pytest.raises(KeyError):
        merkmal.get_features("Q", system="private")


def test_add_model_text_refuses_the_default_registry() -> None:
    """Adding a model mutates a registry, and the default one is process-wide."""
    with pytest.raises(ValueError, match="explicit registry"):
        merkmal._native.add_model_text("@model x\n@type categorical\ngrapheme Z consonant\n")


def test_feature_distance_takes_no_system() -> None:
    """It is a property of the compiled geometry, which every system shares.

    The argument used to be accepted, validated, and then ignored, so a caller
    asking for phoible silently received clements-hume numbers.
    """
    with pytest.raises(TypeError):
        merkmal.feature_distance("voiced", "voiceless", system="phoible")  # type: ignore[call-arg]


def test_coverage_separates_identical_from_incomparable() -> None:
    """A valued 0.0 used to mean either "the same" or "nothing to compare".

    The first independent review found PHOIBLE's tone letters carry `.` on every
    dimension and so scored 0.0 against every segment in the table, `/a/`
    included. The score is unchanged -- inventing values would be fabricating
    data -- but the caller can now see the difference.
    """
    score, coverage, why = merkmal.distance_with_coverage("˦˨", "d", system="phoible")
    assert score == 0.0
    assert coverage == 0.0  # nothing was compared at all
    assert merkmal.compatibility_dissimilarity("˦˨", "d", system="phoible") == (
        score, coverage, why
    )
    assert why == "no-shared-dimension"

    # Genuinely indistinguishable is a different thing, and now looks different:
    # P-base UFTC gives /e/ and /i/ the same value on every dimension it defines.
    score, coverage, why = merkmal.distance_with_coverage("e", "i", system="pbase-uftc")
    assert score == 0.0
    assert coverage > 0.5
    assert why == "ok"  # compared, and genuinely indistinguishable

    # A segment against itself is covered on the dimensions it actually has,
    # which is not all of them: PHOIBLE leaves 11 of /p/'s 38 cells at `.`.
    # This asserted 1.0 while the identity shortcut answered on the scorer's
    # behalf. That 1.0 was coverage relative to the segment; the documented
    # quantity is relative to the system's declared dimensions, and the two are
    # different numbers whenever the segment has a gap.
    score, coverage, why = merkmal.distance_with_coverage("p", "p", system="phoible")
    assert score == 0.0
    assert math.isclose(coverage, 27 / 38)
    assert why == "ok"

    # Asking for no coverage takes the shortcut instead, and the score agrees.
    assert merkmal.distance("p", "p", system="phoible") == 0.0

    # Categorical systems score over the union of what either segment specifies,
    # so the ambiguity cannot arise and coverage is 1.0 by construction.
    score, coverage, _why = merkmal.distance_with_coverage("p", "b", system="descriptive")
    assert coverage == 1.0
    assert math.isclose(score, merkmal.distance("p", "b", system="descriptive"))


def test_fixed_space_distance_is_distinct_from_compatibility_score() -> None:
    value = merkmal.fixed_space_distance("p", "b", system="phoible")
    assert value > 0.0
    assert value == merkmal.fixed_space_distance("b", "p", system="phoible")
    comparison = merkmal.compatibility_dissimilarity("˦˨", "d", system="phoible")
    assert comparison.comparability == "no-shared-dimension"


def test_alternative_geometry_is_explicit_and_fingerprinted() -> None:
    geometry = merkmal.load_geometry(
        Path(__file__).resolve().parents[2] / "geometries" / "deep-clements-hume.json"
    )
    assert geometry.name == "deep-clements-hume"
    assert len(geometry.digest) == 64
    assert merkmal.geometry_distance("p", "b", geometry=geometry, system="descriptive") > 0.0


def test_diagnose_says_where_a_grapheme_went_wrong() -> None:
    """Checking transcriptions is the workflow a validated inventory should be
    best at, and there the diagnosis is the product. "Unknown grapheme" does not
    tell an author whether they mistyped a mark, used a convention this library
    does not read, or wrote a sound it genuinely lacks.
    """
    fine = merkmal.diagnose("pʰ")
    assert fine["ok"] and fine["status"] == "ok"
    assert fine["valid_prefix"] == "pʰ" and fine["offending"] == ""

    # The longest prefix that resolves localizes the problem and is usually the
    # repair: `pʰ` is right, the combining mark after it is not.
    bad = merkmal.diagnose("pʰ̳zz")
    assert not bad["ok"]
    assert bad["valid_prefix"] == "pʰ"
    assert bad["offending"] == "̳"

    # The three refusals stay distinguishable, and the prefix points at the
    # right character in each.
    markup = merkmal.diagnose("<?>")
    assert markup["status"] == "source markup, not a sound"
    malformed = merkmal.diagnose("¹²³⁴")
    assert malformed["status"] == "parse error"
    assert malformed["valid_prefix"] == "¹²³"  # a run of three is a contour
    assert malformed["offending"] == "⁴"       # the fourth digit is the problem
    # U+02AD, the bidental percussive: a real IPA symbol no bundled inventory
    # lists, which is what "unknown grapheme" is for.
    unknown = merkmal.diagnose("ʭ")
    assert unknown["status"] == "unknown grapheme"
    assert unknown["valid_prefix"] == ""       # nothing of it resolves


def test_affricates_survive_inside_a_cluster() -> None:
    """`ntʃ` is n + tʃ, not n + t + ʃ.

    The tokenizer and the recognizer both read `tʃ` as one segment; the cluster
    component parser was the one path still splitting by letter.
    """
    components = {
        f.split("-", 1)[0]
        for f in merkmal.get_features("ntʃ")
        if len(f) > 1 and f[0] == "n" and f[1].isdigit()
    }
    assert components == {"n1", "n2"}
    assert {"n2-affricate", "n2-post-alveolar"} <= merkmal.get_features("ntʃ")

    # The lookahead is one unit deep and consults only the inventory and the
    # complex synthesizer. /mb/ and /nd/ are explicit pre-nasalized-stop
    # inventory entries, rather than evidence that the tokenizer inferred a
    # two-segment analysis from the spelling.
    for token in ["mb", "nd"]:
        assert "pre-nasalized" in merkmal.get_features(token)


def test_doubled_spelling_is_not_charged_for_its_own_length() -> None:
    """A geminate against a length-marked segment is not a length mismatch.

    The per-component penalty made `aa` further from `aː` (0.233) than a plain
    `a` was (0.064), while doubling is how Uralic, Austronesian and much African
    data write length.
    """
    assert merkmal.distance("aa", "aː") < merkmal.distance("aa", "a")
    assert merkmal.distance("pp", "pː") < merkmal.distance("pp", "p")

    # Waived, not reversed: nothing here claims a doubled vowel *means* length,
    # because whether it does is a property of the source.
    assert merkmal.distance("a", "aː") < merkmal.distance("aa", "aː")

    # A cluster that is not a geminate still pays the penalty.
    assert merkmal.distance("ai", "aː") > merkmal.distance("aa", "aː")


def test_labial_velars_are_one_series() -> None:
    """`ŋm` is the nasal member of the `kp`/`gb` series, not a cluster.

    CLTS v1.4.1 reads `kp` as a cluster; this library departs from that because
    the standard analysis in the Niger-Congo languages that have them is a
    single doubly-articulated segment. `ŋm` was left out of the departure, which
    put it 0.73 from `kp` where `gb` sits at 0.18.
    """
    assert merkmal.get_features("ŋm") == frozenset(
        {"consonant", "labio-velar", "nasal", "voiced"}
    )
    assert merkmal.distance("gb", "ŋm") < merkmal.distance("kp", "ŋm")
    assert merkmal.distance("kp", "ŋm") < merkmal.distance("kp", "a")
    # Close to both of the things it is articulated as, which is the point.
    assert merkmal.distance("ŋm", "ŋ") < 0.25
    assert merkmal.distance("ŋm", "m") < 0.25


def test_feature_vectors_are_fixed_width_and_labelled() -> None:
    """Numbers for the models that want numbers, with the columns named.

    Everything else here returns labels. Writing the label-to-number mapping by
    hand is easy to get wrong where it matters least visibly: a valued system
    writes `anterior=.` for "no value" and `anterior=-` for "absent", and a
    naive reader turns both into 0 or both into -1.
    """
    for system in ["distinctive", "descriptive", "phoible", "pbase-hc"]:
        labels = merkmal.vector_labels(system=system)
        vector = merkmal.feature_vector("p", system=system)
        assert isinstance(labels, tuple) and isinstance(vector, tuple)
        assert len(labels) == len(vector) > 0
        assert len(set(labels)) == len(labels), system  # columns are addressable
        # Fixed width: every segment in a system gives the same shape.
        assert len(merkmal.feature_vector("a", system=system)) == len(vector)

    # The three-valued convention, checked where it actually bites. PHOIBLE
    # writes `.` for cells that do not apply; those must be 0, not -1.
    phoible = dict(zip(
        merkmal.vector_labels(system="phoible"),
        merkmal.feature_vector("p", system="phoible"),
        strict=True,
    ))
    assert phoible["consonantal"] == 1.0
    assert phoible["periodicGlottalSource"] == -1.0
    assert phoible["tone"] == 0.0  # `.` in the table: not applicable, not absent

    # Ordered scales cannot use 0 for a middle level, because 0 already means
    # "no value on this scale". They live in (0, 1] and stay monotone.
    labels = merkmal.vector_labels(system="descriptive")
    height = {
        g: dict(zip(labels, merkmal.feature_vector(g, system="descriptive"), strict=True))[
            "vowel_height"
        ]
        for g in ["i", "e", "ɛ", "a"]
    }
    assert 0.0 < height["i"] < height["e"] < height["ɛ"] < height["a"] <= 1.0
    consonant = dict(zip(labels, merkmal.feature_vector("p", system="descriptive"), strict=True))
    assert consonant["vowel_height"] == 0.0  # the scale does not apply at all
    assert consonant["vocoid"] == -1.0

    with pytest.raises(ValueError):
        merkmal.feature_vector("not-ipa")


def test_a_tone_and_a_segment_are_not_compared() -> None:
    """They occupy different tiers, and the geometry's answer for them is an
    artifact of how many features the *other* segment has -- 0.61 against a
    stop, 0.50 against a vowel -- not a statement about tone. Gold alignments
    never put the two in one column.
    """
    for other in ["p", "a", "s", "n"]:
        score, coverage, why = merkmal.distance_with_coverage(
            "³³", other, system="descriptive"
        )
        assert why == "cross-tier", other
        assert coverage == 0.0, other
        # The declared policy value, not a measurement: geometries/clements-hume.json
        # carries it as `tier_policy.cross_tier_cost` so it is data, not a tree edit.
        assert score == 1.0, other

    # Tone against tone is an ordinary comparison and is unaffected.
    score, coverage, why = merkmal.distance_with_coverage("³³", "⁵⁵", system="descriptive")
    assert why == "ok" and coverage == 1.0 and 0.0 < score < 1.0


def test_source_markup_is_distinguishable_from_an_unsupported_sound() -> None:
    """`<?>` means the source has a gap, not that merkmal lacks the segment.

    Both used to be MK_ERR_UNKNOWN_GRAPHEME, which made a transcription-QC pass
    report other people's known gaps as its own failures -- 33,275 tokens' worth
    in Lexibank.
    """
    for token in ["<?>", "<<->>", "<<ú>>", "+", "_", "#"]:
        assert not merkmal.is_segment(token), token
        with pytest.raises(merkmal.SourceMarkerError):
            merkmal.get_features(token)

    # Still a ValueError, so callers catching that are unaffected.
    assert issubclass(merkmal.SourceMarkerError, ValueError)

    # Deliberately narrow. Dataset-specific noise is not swept in on a guess
    # about what its author meant; it stays an unknown grapheme.
    for token in ["→", "∼", "not-ipa"]:
        with pytest.raises(ValueError) as caught:
            merkmal.get_features(token)
        assert not isinstance(caught.value, merkmal.SourceMarkerError), token


def test_source_conventions_cover_clts_lookalikes() -> None:
    """U+01DD TURNED E is a source spelling of schwa, and now resolves."""
    assert merkmal.normalize("ǝ") == "ə"
    assert merkmal.distance("ǝ", "ə") == 0.0

    # U+026B maps to "lˠ" for systems that lack it, and does not shadow the
    # row PHOIBLE has. Both at once is the point: the resolver tries the written
    # form against the inventory before applying any convention, so a rule can
    # no longer replace a segment a system actually distinguishes.
    assert merkmal.normalize("ɫ") == "lˠ"
    assert merkmal.is_segment("ɫ", system="descriptive")
    assert merkmal.distance("ɫ", "lˠ", system="descriptive") == 0.0
    assert merkmal.distance("ɫ", "lˠ", system="phoible") > 0.0


def test_sound_distance_scores_bare_feature_sets() -> None:
    """The one scorer reachable without a system, a registry, or a grapheme.

    It is what produces the geometry fixtures, so it has to be callable from
    here; it was public C API that the wrapper did not expose.
    """
    p = ["consonant", "voiceless", "bilabial", "stop"]
    b = ["consonant", "voiced", "bilabial", "stop"]
    a = ["vowel", "open", "front", "unrounded"]

    assert merkmal.sound_distance(p, p) == 0.0
    assert 0.0 < merkmal.sound_distance(p, b) < merkmal.sound_distance(p, a)
    # Fed a segment's own features, it agrees with the segment scorer -- for a
    # system that scores through the geometry. The named sets above are
    # deliberately minimal and do not carry the features the generator derives,
    # so they score differently, which is the point of keeping them as data
    # rather than as inventory rows.
    assert math.isclose(
        merkmal.sound_distance(
            sorted(merkmal.get_features("p", system="descriptive")),
            sorted(merkmal.get_features("b", system="descriptive")),
        ),
        merkmal.distance("p", "b", system="descriptive"),
        abs_tol=1e-12,
    )
    # It does *not* agree with the default. `sound_distance` is the geometry
    # scorer and takes no system, while `distinctive` -- the default --
    # scores through its own scalar_dimensions. Two scorers, two answers, and a
    # caller feeding default features into sound_distance gets the geometry's
    # number rather than the one `distance` would give. Asserted so that the
    # divergence is a stated property rather than a surprise.
    assert not math.isclose(
        merkmal.sound_distance(
            sorted(merkmal.get_features("p")), sorted(merkmal.get_features("b"))
        ),
        merkmal.distance("p", "b"),
        abs_tol=1e-12,
    )
    assert merkmal.sound_distance(p, b, node_weights="flat") != merkmal.sound_distance(p, b)
    with pytest.raises(ValueError, match="invalid argument"):
        merkmal.sound_distance(p, b, node_weights="no-such-preset")
    with pytest.raises(TypeError):
        merkmal.sound_distance([1], b)  # type: ignore[list-item]


def test_geometry_cases_cover_every_fixture_row() -> None:
    """The fixtures name feature sets; the case file has to define them all.

    Producer and consumer read the same file, so a row naming a set nobody
    defines is a broken fixture, not a silent skip.
    """
    golden = Path(__file__).resolve().parents[2] / "tests" / "golden"
    cases = {
        line.split("\t")[0]
        for line in (golden / "geometry_cases.tsv").read_text(encoding="utf-8").splitlines()[1:]
        if line
    }
    assert cases

    for name, weighted in (
        ("geometry_sound_distances.tsv", False),
        ("geometry_weighted_distances.tsv", True),
    ):
        rows = (golden / name).read_text(encoding="utf-8").splitlines()[1:]
        for row in rows:
            if not row:
                continue
            fields = row.split("\t")
            a, b = (fields[1], fields[2]) if weighted else (fields[0], fields[1])
            assert a in cases, f"{name}: {a} is not in geometry_cases.tsv"
            assert b in cases, f"{name}: {b} is not in geometry_cases.tsv"


def test_error_messages_come_from_the_c_library() -> None:
    """The wrapper used to restate mk_status_string's text in its own words."""
    with pytest.raises(KeyError, match="unknown system"):
        merkmal.get_features("p", system="no-such-system")
    with pytest.raises(ValueError, match="unknown grapheme"):
        merkmal.get_features("not-ipa")
    with pytest.raises(merkmal.SourceMarkerError, match="source markup"):
        merkmal.get_features("<?>")
    with pytest.raises(ValueError, match="invalid argument"):
        merkmal.distance("p", "b", node_weights="no-such-preset")
    with pytest.raises(NotImplementedError, match="unsupported model"):
        merkmal.get_features("a⁵⁵", system="phoible")


def test_a_duplicate_system_name_is_refused() -> None:
    """A second system under an existing name used to install and vanish.

    `mk_registry_get_system` returns the first match, so appending a second
    `descriptive` registered with MK_OK and was then unreachable for the rest of
    the registry's life: the caller was told it worked and every query answered
    from the built-in one.

    The exception type is `ValueError` rather than `NativeError` because the
    type now comes from the status. It used to come from whether the C library
    happened to produce a diagnostic string, which meant every model-text
    failure carrying detail looked the same to a caller regardless of cause.
    """
    model = (
        "@model toy\n"
        "@type categorical\n"
        "@geometry clements-hume\n"
        "grapheme X consonant voiceless bilabial stop\n"
    )
    registry = merkmal.Registry()
    registry.add_model_text(model)

    for name in ("toy", "descriptive"):
        with pytest.raises(ValueError, match=f"'{name}' is already registered"):
            registry.add_model_text(model.replace("@model toy", f"@model {name}"))

    systems = registry.list_systems()
    assert len(systems) == len(set(systems))
    # The first model is untouched and the refused ones installed nothing.
    assert registry.is_segment("X", system="toy")
    assert registry.get_features("p", system="descriptive")


def test_cli_uses_native_wrapper(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["systems"]) == 0
    output = capsys.readouterr().out.splitlines()
    assert "descriptive" in output

    assert main(["--system", "phoible", "features", "bʰ"]) == 0
    output = capsys.readouterr().out.splitlines()
    assert "spreadGlottis=+" in output


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["features", "not-ipa"], "unknown grapheme"),
        (["--system", "nope", "features", "p"], "unknown system"),
        (["distance", "p", "xyz"], "unknown grapheme"),
        (["--system", "phoible", "features", "³³"], "unsupported"),
    ],
)
def test_cli_reports_user_mistakes_without_a_traceback(
    argv: list[str], expected: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every one of these used to escape the handler and print a traceback.

    The CLI caught merkmal.NativeError, which is created with no base class and
    so is not a superclass of the KeyError, ValueError and NotImplementedError
    the wrapper actually raises. `_print_error` was unreachable for any ordinary
    mistake. The success paths were the only ones under test, which is why it
    survived.
    """
    assert main(argv) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert expected in captured.err
    # KeyError renders its argument with repr(); the message is for a person.
    assert "'" not in captured.err


def test_tone_presence_separates_mid_tone_from_tonelessness() -> None:
    """Regression cover for the review's tone findings.

    Before this, Chao level 3 contributed no features, so a mid-tone segment
    and a toneless one had identical representations and compared equal.
    """
    toneless = merkmal.get_features("a", system="descriptive")
    mid = merkmal.get_features("a³³", system="descriptive")
    high = merkmal.get_features("a⁵⁵", system="descriptive")

    assert "tone-present" not in toneless
    assert "tone-present" in mid
    assert "tone-present" in high
    assert toneless != mid != high

    for other in ("a³³", "a⁵⁵", "a¹¹"):
        assert merkmal.distance("a", other, system="descriptive") > 0.0
    assert merkmal.distance("a³³", "a⁵⁵", system="descriptive") > 0.0

    # The all-mid macron reaches the same conclusion through the combining
    # diacritic table rather than through Chao digits.
    assert "tone-present" in merkmal.get_features("ā", system="descriptive")
    assert merkmal.distance("a", "ā", system="descriptive") > 0.0

    # Deliberately ignoring tone is still available, and still means zero.
    assert merkmal.distance(
        "a", "a³³", system="descriptive", node_weights="ignore-tone"
    ) == 0.0


def test_overlong_chao_runs_are_rejected_atomically() -> None:
    """A four-digit run used to be split into two contradictory tone readings."""
    assert not merkmal.is_segment("a¹²³⁴", system="descriptive")
    with pytest.raises(merkmal.NativeError):
        merkmal.get_features("a¹²³⁴", system="descriptive")

    # Tokenization keeps the malformed run in one piece, so the tokenizer and
    # the recognizer agree about what was rejected.
    assert merkmal.segment_ipa("a¹²³⁴") == ["a", "¹²³⁴"]

    # One, two, and three levels stay accepted.
    for token in ("a¹", "a¹²", "a¹²³"):
        assert merkmal.is_segment(token, system="descriptive"), token


def test_valued_systems_report_tone_as_unsupported() -> None:
    """Silently dropping tone made a¹¹ and a⁵⁵ compare equal in these systems."""
    for system in ("pbase-hc", "pbase-jfh", "pbase-spe", "pbase-uftc", "phoible"):
        with pytest.raises(NotImplementedError):
            merkmal.get_features("a³³", system=system)
        with pytest.raises(NotImplementedError):
            merkmal.distance("a¹¹", "a⁵⁵", system=system)


def test_system_aware_tokenizer_agrees_with_the_recognizer() -> None:
    """Orthographic tokenization splits segments the system itself accepts."""
    # The disagreement the review reported, and its fix.
    assert merkmal.segment_ipa("tʃa") == ["t", "ʃ", "a"]
    assert merkmal.system_segment_ipa("tʃa", system="descriptive") == ["tʃ", "a"]
    assert merkmal.segment_ipa("kpa") == ["k", "p", "a"]
    assert merkmal.system_segment_ipa("kpa", system="descriptive") == ["kp", "a"]

    # Tie-bar spelling no longer changes the token sequence.
    assert merkmal.system_segment_ipa(
        "t͡ʃa", system="descriptive"
    ) == ["t͡ʃ", "a"]

    # A standalone tone remains its own autosegment. Association is a
    # prosodic analysis the segment tokenizer does not infer.
    assert merkmal.system_segment_ipa("tʰoŋ⁵⁵", system="descriptive") == ["tʰ", "o", "ŋ", "⁵⁵"]
    assert merkmal.system_segment_ipa("papa", system="descriptive") == ["p", "a", "p", "a"]

    # Every emitted token that the system recognizes passes its own predicate.
    for token in merkmal.system_segment_ipa("aːi³³ka", system="descriptive"):
        assert merkmal.is_segment(token, system="descriptive"), token

    # Unrecognized input is passed through rather than dropped.
    assert merkmal.system_segment_ipa("xyz", system="descriptive") == ["x", "y", "z"]

    # The legacy tokenizer is unchanged: it is a separate, documented policy.
    assert merkmal.segment_ipa("t͡ʃa") == ["t͡ʃ", "a"]


def test_curated_contrast_suite_is_preserved() -> None:
    """Every one of these contrasts used to score exactly zero.

    The labels involved (devoiced, apical/laminal, unreleased, the length
    series, the secondary articulations, major class) reached no geometry node,
    so they could not move the distance at all.
    """
    contrasts = [
        ("p", "p̥", "phonation: devoiced"),
        ("t", "t̺", "coronal: apical"),
        ("t", "t̻", "coronal: laminal"),
        ("k", "k̚", "release: unreleased"),
        ("y", "yːː", "quantity: ultra-long"),
        ("a", "ă", "quantity: ultra-short"),
        ("k", "kˠ", "secondary: velarized"),
        ("a", "a̠", "place: retracted"),
        ("a", "a̝", "place: raised"),
        ("o", "o̜", "rounding: less-rounded"),
    ]
    for a, b, label in contrasts:
        for system in ("descriptive", "distinctive"):
            assert merkmal.distance(a, b, system=system) > 0.0, f"{label} in {system}"


def test_major_class_dominates_within_class_differences() -> None:
    """A consonant-vowel difference should outweigh any consonant-consonant one.

    Before major class reached the score, p~s (0.70) was almost as far apart as
    p~a (0.68), which is not a defensible ordering for any use of the number.
    """
    across = merkmal.distance("p", "a", system="descriptive")
    for a, b in (("p", "b"), ("p", "t"), ("p", "k"), ("p", "s"), ("t", "s")):
        assert merkmal.distance(a, b, system="descriptive") < across
    for a, b in (("a", "i"), ("a", "u"), ("i", "u")):
        assert merkmal.distance(a, b, system="descriptive") < across


def test_valued_scorer_is_documented_as_nonmetric() -> None:
    """Guards the README's claim rather than the implementation.

    The valued scorer compares only dimensions where both segments carry a
    parseable value, so the denominator varies by pair. That is a deliberate
    (documented) choice, but it means the result is not a metric, and this test
    fails loudly if someone starts describing it as one.
    """
    a, b, c = "ðˠ", "mʲ", "d̪ʲ"
    direct = merkmal.distance(a, b, system="pbase-hc")
    via = (
        merkmal.distance(a, c, system="pbase-hc")
        + merkmal.distance(c, b, system="pbase-hc")
    )
    assert direct > via, "triangle inequality no longer violated; update the README claim"


def test_ordered_properties_score_by_distance_not_mismatch() -> None:
    """Vowel height, backness, duration and tone are ordered, not privative.

    Encoded as independent flags, /i/ scored further from /e/ than from /a/, a
    half-long vowel was further from a long one than a plain vowel was, and the
    two-bit Chao code made levels 2 and 4 as far apart as 1 and 5.
    """
    d = merkmal.distance

    # Height: monotone along close > close-mid > open-mid > open.
    assert d("i", "e") < d("i", "ɛ") < d("i", "a")
    assert d("e", "ɛ") < d("e", "a")

    # Backness: monotone along front > central > back.
    assert d("i", "ɨ") < d("i", "u")

    # Duration: ultra-short < short < half-long < long < ultra-long.
    assert d("a", "aˑ") < d("a", "aː") < d("a", "aːː")
    assert d("aˑ", "aː") < d("a", "aː")
    assert d("aː", "aːː") > 0.0

    # Tone: cost proportional to the difference in Chao level.
    tone = {"node_weights": "tone-only"}
    assert (
        d("a¹¹", "a²²", **tone)
        < d("a¹¹", "a³³", **tone)
        < d("a¹¹", "a⁴⁴", **tone)
        < d("a¹¹", "a⁵⁵", **tone)
    )
    assert d("a²²", "a⁴⁴", **tone) < d("a¹¹", "a⁵⁵", **tone)


def test_tone_spellings_that_denote_one_segment_are_one_segment() -> None:
    for group in (("a¹", "a¹¹", "a¹¹¹"), ("a³", "a³³", "a³³³"), ("a⁵", "a⁵⁵")):
        for other in group[1:]:
            assert merkmal.distance(group[0], other) == 0.0, (group[0], other)

    # A two-digit contour takes the midpoint of its glide.
    assert "tone-mid-3" in merkmal.get_features("a¹⁵")

    # IPA tone letters are the primary IPA notation and mean the same thing.
    assert merkmal.distance("a˥˥", "a⁵⁵") == 0.0
    assert merkmal.is_segment("a˥˩")
    assert merkmal.segment_ipa("ta˥˩") == ["t", "a", "˥˩"]


def test_precomposed_and_decomposed_spellings_agree() -> None:
    """normalize() returns NFC, so a mismatch here turns working input into
    failing input for anyone doing the documented preprocessing step."""
    import unicodedata

    for grapheme in ("ǎ", "ě", "ǐ", "ǒ", "ǔ", "ý", "á", "à", "ā"):
        assert merkmal.is_segment(grapheme), grapheme
        assert merkmal.is_segment(unicodedata.normalize("NFD", grapheme)), grapheme
        assert merkmal.is_segment(merkmal.normalize(grapheme)), grapheme


def test_manner_and_place_distinctions_are_not_one_boolean() -> None:
    """`sonorant`, `continuant`, `anterior` and `distributed` were unreachable.

    No inventory name states them, so every manner distinction cost the same and
    a click was exactly equidistant from a velar and a coronal stop.
    """
    features = merkmal.get_features("p")
    assert {"consonantal", "obstruent", "non-continuant"} <= features
    assert "sonorant" in merkmal.get_features("m")
    assert "continuant" in merkmal.get_features("f")
    assert {"anterior", "non-distributed"} <= merkmal.get_features("t")
    assert {"non-anterior", "distributed"} <= merkmal.get_features("ʃ")

    # Manner differences no longer all cost the same.
    assert len({round(merkmal.distance("p", x), 10) for x in ("f", "m", "r", "ʔ")}) == 4

    # A click carries its rear closure as its own feature, not as a second place.
    assert merkmal.distance("ǃ", "k") != merkmal.distance("ǃ", "t")


def test_glides_are_close_to_their_vowels() -> None:
    """/w/ scored as far from /u/ as /ʔ/ does from /a/, though w~u and j~i
    alternations are among the most common things in historical phonology."""
    assert "vocoid" in merkmal.get_features("w")
    assert "vocoid" in merkmal.get_features("j")
    assert "consonantal" in merkmal.get_features("l")
    assert merkmal.distance("w", "u") < merkmal.distance("ʔ", "a")
    assert merkmal.distance("j", "i") < merkmal.distance("ʔ", "a")


def test_presets_drop_only_what_they_name() -> None:
    """`segmental` zeroed the whole Prosodic node, so it silently discarded
    nasalisation and ejectivity -- phonemic contrasts -- along with length."""
    assert merkmal.distance("a", "aː", node_weights="segmental") == 0.0
    assert merkmal.distance("a", "a³³", node_weights="segmental") == 0.0
    assert merkmal.distance("a", "ã", node_weights="segmental") > 0.0
    assert merkmal.distance("k", "kʼ", node_weights="segmental") > 0.0
    assert merkmal.distance("t", "tʲ", node_weights="segmental") > 0.0
    assert merkmal.distance("a", "aː", node_weights="ignore-length") == 0.0


def test_contradictory_and_malformed_composition_is_rejected() -> None:
    # Breve plus length mark asserts both ultra-short and long.
    for grapheme in ("ăː", "aˑː", "aːːː"):
        assert not merkmal.is_segment(grapheme), grapheme
        with pytest.raises(merkmal.NativeError):
            merkmal.get_features(grapheme)


def test_cluster_synthesis_defects() -> None:
    # A two-item blocklist rejected the two most frequent NC sequences in the
    # world's languages while accepting mp, nt and ŋg.
    for token in ("mb", "nd", "mp", "nt", "ŋg"):
        assert merkmal.is_segment(token), token
        assert "pre-nasalized" in merkmal.get_features(token), token

    # Prenasalisation needs a following non-nasal obstruent: geminates and the
    # labial-velar nasal are not prenasalised segments.
    for token in ("mm", "nn", "ŋm"):
        assert "pre-nasalized" not in merkmal.get_features(token), token
    assert "geminate" in merkmal.get_features("mm")
    # A doubled vowel is one vowel written twice, not a glide from /a/ to /a/.
    assert "geminate" in merkmal.get_features("aa")
