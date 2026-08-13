"""Tests for the native C-backed top-level wrapper slice."""

from __future__ import annotations

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
            "broad",
            "descriptive",
            "distinctive",
            "pbase-hc",
            "pbase-jfh",
            "pbase-spe",
            "pbase-uftc",
            "phoible",
        ]
    )


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
    with pytest.raises(ValueError):
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
        "¹/¹",
        "³/¹",
        "³¹",
        "³⁵",
        "⁵⁵",
        "p³³",
    ]
    for token in negative:
        assert not merkmal.is_segment(token, system="descriptive"), token

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
    assert math.isclose(merkmal.distance("p", "b"), 0.125, abs_tol=1e-10)
    assert math.isclose(
        merkmal.distance("p", "b", system="phoible"),
        0.0365853659,
        abs_tol=1e-10,
    )
    assert merkmal.feature_distance("voiced", "voiceless") == 2
    # Tone levels are ordered-scale values, not tree leaves, so they have no
    # tree path; the geometry distance is defined over the tree only.
    assert merkmal.feature_distance("tone-onset-1", "tone-offset-1") == 999
    assert merkmal.feature_distance("bilabial", "velar") == 999
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
    # Fed a segment's own features, it agrees with the segment scorer. The
    # named sets above are deliberately minimal and do not carry the features
    # the generator derives, so they score differently -- which is the point of
    # keeping them as data rather than as inventory rows.
    assert math.isclose(
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
        merkmal.get_features("<?>")
    with pytest.raises(ValueError, match="invalid argument"):
        merkmal.distance("p", "b", node_weights="no-such-preset")
    with pytest.raises(NotImplementedError, match="unsupported model"):
        merkmal.get_features("a⁵⁵", system="phoible")


def test_cli_uses_native_wrapper(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["systems"]) == 0
    output = capsys.readouterr().out.splitlines()
    assert "broad" in output

    assert main(["--system", "phoible", "features", "bʰ"]) == 0
    output = capsys.readouterr().out.splitlines()
    assert "spreadGlottis=+" in output


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

    # Tone attaches to its nucleus, and nothing over-merges.
    assert merkmal.system_segment_ipa("tʰoŋ⁵⁵", system="descriptive") == ["tʰ", "o", "ŋ⁵⁵"]
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
        for system in ("broad", "descriptive", "distinctive"):
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
