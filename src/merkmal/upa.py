"""UPA (Uralic Phonetic Alphabet) transcription adapter.

Segments UPA strings into individual sounds and maps each to the
canonical (IPA-based) form used by merkmal's feature systems.

The mapping table lives in ``data/transcriptions/upa.tsv`` and covers
base consonants, vowels, and precomposed diacritic combinations.
Composed forms not in the table are handled by the segmenter, which
decomposes UPA diacritics into base + modification and remaps
accordingly.
"""

from __future__ import annotations

import csv
import unicodedata
from functools import cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / "data" / "transcriptions" / "upa.tsv"

# ---------------------------------------------------------------------------
# UPA-specific combining marks and modifier letters
# ---------------------------------------------------------------------------

# Combining breve below (U+032E): "back unrounded" vowel remapping.
_BREVE_BELOW = "\u032E"

# Combining inverted breve above (U+0311): backing diacritic.
_INVERTED_BREVE_ABOVE = "\u0311"

# Modifier letter prime (U+02B9): palatalization in UPA.
_MODIFIER_PRIME = "\u02B9"

# UPA acute accent (U+0301, combining): palatalization on consonants.
_COMBINING_ACUTE = "\u0301"

# UPA macron (U+0304, combining): long vowel.
_COMBINING_MACRON = "\u0304"

# UPA breve (U+0306, combining): short/reduced vowel.
_COMBINING_BREVE = "\u0306"

# Combining dot below (U+0323): retroflex/cacuminal in UPA.
_COMBINING_DOT_BELOW = "\u0323"

# Combining circumflex accent below (U+032D): sub-laminal in UPA.
_COMBINING_CIRCUMFLEX_BELOW = "\u032D"

# Combining grave accent (U+0300): low tone or stress.
_COMBINING_GRAVE = "\u0300"

# Combining caron (U+030C): postalveolar (compositional form of š, č, etc.).
_COMBINING_CARON = "\u030C"

# Combining diaeresis (U+0308): front rounded (compositional form of ö, ü, ä).
_COMBINING_DIAERESIS = "\u0308"

# Combining inverted breve below (U+032F): non-syllabic.
_COMBINING_INVERTED_BREVE_BELOW = "\u032F"

# Combining ring above (U+030A): rounded open-mid back vowel (å) in UPA.
_COMBINING_RING_ABOVE = "\u030A"

# Combining dot above (U+0307): ignore in UPA (Lithuanian convention).
_COMBINING_DOT_ABOVE = "\u0307"

# Vowel rounding via ring above: base → IPA rounded equivalent.
_RING_ABOVE_VOWEL: dict[str, str] = {
    "a": "\u0254",     # ɔ (rounded open-mid back)
}

# Modifier letter low ring (U+02F3): devoicing in UPA.
_MODIFIER_LOW_RING = "\u02F3"

# Postalveolar mapping via caron: base → IPA postalveolar.
_CARON_CONSONANT: dict[str, str] = {
    "s": "\u0283",     # ʃ
    "z": "\u0292",     # ʒ
    "c": "t\u0283",    # tʃ (č)
    "n": "\u0273",     # ɳ (ň — rare, retroflex nasal)
    "d": "d\u02B2",   # dʲ (ď — palatalized d in UPA)
}

# Front-rounded mapping via diaeresis: base → IPA front rounded.
_DIAERESIS_VOWEL: dict[str, str] = {
    "a": "\u00E6",     # æ
    "o": "\u00F8",     # ø
    "u": "y",          # y
}

# Retroflex mapping via dot below: base → IPA retroflex.
_DOT_BELOW_CONSONANT: dict[str, str] = {
    "t": "\u0288",     # ʈ
    "d": "\u0256",     # ɖ
    "n": "\u0273",     # ɳ
    "s": "\u0282",     # ʂ
    "z": "\u0290",     # ʐ
    "l": "\u026D",     # ɭ
    "r": "\u027D",     # ɽ
}

# Characters to normalize before processing (typos, encoding variants).
_CHAR_NORMALIZE: dict[str, str] = {
    "\u04D9": "\u0259",   # Cyrillic schwa → IPA schwa
    "\u00A0": " ",         # NO-BREAK SPACE → regular space
}

# Vowel backing map: base vowel + breve-below → back unrounded equivalent.
_BACK_UNROUNDED: dict[str, str] = {
    "i": "\u026F",   # ɯ
    "e": "\u0264",   # ɤ
    "a": "\u0251",   # ɑ
    "u": "\u026F",   # ɯ (u̮ in some Permic data)
    "ə": "\u0264",   # ɤ (ə̑ backed schwa)
}

# Vowel length map: base vowel → long IPA form.
_LONG_VOWEL: dict[str, str] = {
    "a": "a\u02D0",
    "e": "e\u02D0",
    "i": "i\u02D0",
    "o": "o\u02D0",
    "u": "u\u02D0",
    "\u00E6": "\u00E6\u02D0",   # æː
    "\u00F8": "\u00F8\u02D0",   # øː
    "y": "y\u02D0",
    "\u0259": "\u0259\u02D0",   # əː
    "\u026F": "\u026F\u02D0",   # ɯː
    "\u0264": "\u0264\u02D0",   # ɤː
    "\u0251": "\u0251\u02D0",   # ɑː
}

# Consonant palatalization via acute accent: base → IPA palatal/palatalized.
_PALATALIZED_CONSONANT: dict[str, str] = {
    "c": "t\u0255",   # tɕ  (but 'c' is also palatal stop — context-dependent)
    "d": "d\u02B2",   # dʲ
    "g": "\u025F",     # ɟ
    "k": "c",          # palatal stop
    "l": "\u028E",     # ʎ
    "n": "\u0272",     # ɲ
    "r": "r\u02B2",    # rʲ
    "s": "\u0255",     # ɕ
    "t": "t\u02B2",    # tʲ (palatalized alveolar stop)
    "z": "\u0291",     # ʑ
    "m": "m\u02B2",    # mʲ
}

# Greek letter → IPA.
_GREEK_TO_IPA: dict[str, str] = {
    "\u03B2": "\u03B2",   # β → β (same in IPA)
    "\u03B3": "\u0263",   # γ → ɣ
    "\u03B4": "\u00F0",   # δ → ð
    "\u03D1": "\u03B8",   # ϑ → θ
    "\u03C7": "x",        # χ → x (velar, not uvular)
    "\u03C6": "\u0278",   # φ → ɸ
    "\u03C1": "\u0280",   # ρ → ʀ
}

# Small capital → IPA devoiced form.
_SMALL_CAP_TO_IPA: dict[str, str] = {
    "\u0299": "b\u0325",   # ʙ → b̥
    "\u1D05": "d\u0325",   # ᴅ → d̥
    "\u0262": "\u0261\u0325",  # ɢ → ɡ̥
    "\u029F": "l\u0325",   # ʟ → l̥
    "\u1D0D": "m\u0325",   # ᴍ → m̥
    "\u0274": "n\u0325",   # ɴ → n̥
    "\u1D22": "z\u0325",   # ᴢ → z̥
    "\u1D0A": "j\u0325",   # ᴊ → j̥
    "\u1D00": "a\u0325",   # ᴀ → ḁ (voiceless vowel)
    "\u1D07": "e\u0325",   # ᴇ → e̥
    "\u1D1C": "u\u0325",   # ᴜ → u̥
}

# UPA umlaut vowels → IPA.
_UMLAUT_VOWEL: dict[str, str] = {
    "\u00E4": "\u00E6",   # ä → æ
    "\u00F6": "\u00F8",   # ö → ø
    "\u00FC": "y",         # ü → y
    "\u00E5": "\u0254",   # å → ɔ (rounded open-mid back, UPA convention)
}


# ---------------------------------------------------------------------------
# Static mapping table
# ---------------------------------------------------------------------------

@cache
def _load_mapping() -> dict[str, str]:
    """Load the UPA→canonical mapping from the bundled TSV."""
    mapping: dict[str, str] = {}
    with _DATA_PATH.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            grapheme = row["GRAPHEME"].strip()
            if grapheme.startswith("#") or not grapheme:
                continue
            canonical = row["CANONICAL"].strip()
            if canonical:
                # Normalize both sides to NFD for consistent matching.
                key = unicodedata.normalize("NFD", grapheme)
                mapping[key] = canonical
    return mapping


# ---------------------------------------------------------------------------
# UPA segmenter
# ---------------------------------------------------------------------------

def _is_upa_combining(ch: str) -> bool:
    """Return True if the character is a UPA combining mark or modifier."""
    cat = unicodedata.category(ch)
    if cat.startswith("M"):
        return True
    # Modifier letter prime is UPA palatalization.
    if ch == _MODIFIER_PRIME:
        return True
    # Modifier letter low ring is UPA devoicing.
    if ch == _MODIFIER_LOW_RING:
        return True
    return False


def _normalize_upa_text(text: str) -> str:
    """Normalize encoding variants and typos before NFD decomposition."""
    return "".join(_CHAR_NORMALIZE.get(ch, ch) for ch in text)


def segment_upa(text: str) -> list[str]:
    """Segment a UPA string into individual sound tokens.

    Handles combining diacritics, modifier letters, and multi-character
    conventions.  Returns a list of UPA segments (not yet mapped to IPA).
    """
    normalized = unicodedata.normalize("NFD", _normalize_upa_text(text))
    segments: list[str] = []
    current: list[str] = []

    for ch in normalized:
        if _is_upa_combining(ch):
            # Attach to the current segment.
            if current:
                current.append(ch)
            # Orphaned combining mark — skip silently.
        elif unicodedata.category(ch) in ("Zs", "Cc"):
            # Whitespace / control: flush.
            if current:
                segments.append("".join(current))
                current = []
        elif ch in ("-", "_", ".", ",", ":", ";", "(", ")", "[", "]", "/"):
            # Punctuation and morpheme boundaries: flush and skip.
            if current:
                segments.append("".join(current))
                current = []
        else:
            # New base character: flush previous segment.
            if current:
                segments.append("".join(current))
            current = [ch]

    if current:
        segments.append("".join(current))

    return segments


def _adapt_segment(seg: str) -> str:
    """Map a single UPA segment to its IPA canonical form.

    Tries the static table first, then falls back to compositional
    decomposition rules.
    """
    # Normalize encoding variants first.
    seg = _normalize_upa_text(seg)
    nfd = unicodedata.normalize("NFD", seg)
    mapping = _load_mapping()

    # 1. Direct table lookup.
    if nfd in mapping:
        return mapping[nfd]

    # 2. Compositional decomposition.
    # Separate the base letter(s) from combining marks.
    base_chars: list[str] = []
    combining: list[str] = []
    for ch in nfd:
        cat = unicodedata.category(ch)
        if cat.startswith("M") or ch in (_MODIFIER_PRIME, _MODIFIER_LOW_RING):
            combining.append(ch)
        else:
            base_chars.append(ch)

    base = "".join(base_chars)
    marks = combining

    # Try to resolve the base first.
    ipa_base = base
    if base in _GREEK_TO_IPA:
        ipa_base = _GREEK_TO_IPA[base]
    elif base in _SMALL_CAP_TO_IPA:
        ipa_base = _SMALL_CAP_TO_IPA[base]
    elif base in _UMLAUT_VOWEL:
        ipa_base = _UMLAUT_VOWEL[base]
    elif base in mapping:
        ipa_base = mapping[base]

    # Apply UPA combining marks with UPA-specific semantics.
    result = ipa_base
    ipa_combining: list[str] = []
    for mark in marks:
        if mark == _BREVE_BELOW:
            # Back unrounded remapping.
            stripped = _strip_ipa_modifiers(result)
            if stripped in _BACK_UNROUNDED:
                result = _BACK_UNROUNDED[stripped]
            else:
                ipa_combining.append(mark)
        elif mark == _INVERTED_BREVE_ABOVE:
            # Backing diacritic (same as breve below for vowels).
            stripped = _strip_ipa_modifiers(result)
            if stripped in _BACK_UNROUNDED:
                result = _BACK_UNROUNDED[stripped]
            else:
                ipa_combining.append(mark)
        elif mark == _COMBINING_ACUTE:
            # Palatalization on consonants.
            stripped = _strip_ipa_modifiers(result)
            if stripped in _PALATALIZED_CONSONANT:
                result = _PALATALIZED_CONSONANT[stripped]
            else:
                ipa_combining.append("\u02B2")  # ʲ
        elif mark == _MODIFIER_PRIME:
            # Modifier prime = secondary palatalization.
            result += "\u02B2"  # append ʲ
        elif mark == _COMBINING_MACRON:
            # Long vowel.
            stripped = _strip_ipa_modifiers(result)
            if stripped in _LONG_VOWEL:
                result = _LONG_VOWEL[stripped]
            else:
                result += "\u02D0"  # ː
        elif mark == _COMBINING_BREVE:
            # Short/reduced — map to ultra-short in IPA.
            result += "\u0306"  # combining breve (ultra-short)
        elif mark == _COMBINING_CARON:
            # Postalveolar (compositional form of š, č, etc.).
            stripped = _strip_ipa_modifiers(result)
            if stripped in _CARON_CONSONANT:
                result = _CARON_CONSONANT[stripped]
            else:
                ipa_combining.append(mark)
        elif mark == _COMBINING_DIAERESIS:
            # Front rounded vowel (compositional form of ö, ü, ä).
            stripped = _strip_ipa_modifiers(result)
            if stripped in _DIAERESIS_VOWEL:
                result = _DIAERESIS_VOWEL[stripped]
            else:
                ipa_combining.append(mark)
        elif mark == _COMBINING_DOT_BELOW:
            # Retroflex/cacuminal.
            stripped = _strip_ipa_modifiers(result)
            if stripped in _DOT_BELOW_CONSONANT:
                result = _DOT_BELOW_CONSONANT[stripped]
            else:
                ipa_combining.append(mark)
        elif mark == _COMBINING_CIRCUMFLEX_BELOW:
            # Sub-laminal articulation — pass through as IPA combining.
            ipa_combining.append("\u033B")  # IPA combining square below (laminal)
        elif mark == _COMBINING_INVERTED_BREVE_BELOW:
            # Non-syllabic.
            ipa_combining.append("\u032F")  # IPA combining inverted breve below
        elif mark == _COMBINING_GRAVE:
            # Low tone / stress — pass through as IPA combining grave.
            ipa_combining.append(mark)
        elif mark == _MODIFIER_LOW_RING:
            # Devoicing in UPA.
            ipa_combining.append("\u0325")  # IPA combining ring below (voiceless)
        elif mark == _COMBINING_RING_ABOVE:
            # Rounding / rounded vowel (å convention).
            stripped = _strip_ipa_modifiers(result)
            if stripped in _RING_ABOVE_VOWEL:
                result = _RING_ABOVE_VOWEL[stripped]
            else:
                # On consonants this is devoicing (same as IPA).
                ipa_combining.append("\u0325")  # ring below
        elif mark == _COMBINING_DOT_ABOVE:
            # Ignore dot above (Lithuanian convention, no phonetic value).
            pass
        else:
            # Pass through other combining marks to IPA.
            ipa_combining.append(mark)

    # Reattach any remaining IPA combining marks.
    if ipa_combining:
        result += "".join(ipa_combining)

    return result


def _strip_ipa_modifiers(s: str) -> str:
    """Return only base characters from an IPA string (strip combining/modifiers)."""
    return "".join(
        ch for ch in unicodedata.normalize("NFD", s)
        if not unicodedata.category(ch).startswith("M")
        and ch not in ("\u02D0", "\u02D1", "\u02B2", "\u02B7", "\u02B0")
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def adapt(text: str) -> list[str]:
    """Convert a UPA transcription to a list of IPA segments.

    This is the main entry point. It segments the UPA text, maps each
    segment to its IPA canonical form, and returns the list.

    >>> adapt("käsi")
    ['k', 'æ', 's', 'i']
    >>> adapt("ńēləm")
    ['ɲ', 'eː', 'l', 'ə', 'm']
    >>> adapt("ni̮r")
    ['n', 'ɯ', 'r']
    """
    segments = segment_upa(text)
    return [_adapt_segment(seg) for seg in segments]


def adapt_segment(segment: str) -> str:
    """Convert a single UPA segment to its IPA canonical form.

    >>> adapt_segment("š")
    'ʃ'
    >>> adapt_segment("ə̑")
    'ɤ'
    >>> adapt_segment("i̮")
    'ɯ'
    """
    return _adapt_segment(segment)
