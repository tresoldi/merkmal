"""ClassFeat: a trained feature system for cognate detection.

Classifies IPA segments into data-refined sound classes (24 classes
derived from SCA via empirical splits and merges), then computes
distance using a learned class-pair cost matrix plus per-dimension
feature weights.  Ships pre-trained weights so users need no
external dependencies.

The class structure differs from SCA in three key ways:
  - Splits: H→Hf/Hq, K→K/Q, N→N/Ng, I→I/Ic, A→A/Ab, T→T (affricates→C)
  - Merges: U+Y→V (rounded vowels), B+W→F (labial continuants)
  - Coverage: stress marks, prenasalisation, legacy IPA handled
"""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache, cached_property
from pathlib import Path

from merkmal.representations import (
    FeatureState,
    ValuedFeatures,
    _normalize_valued_query,
)
from merkmal.systems.categorical import normalize_input_grapheme

_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "classfeat"
_WEIGHTS_FILE = _DATA_DIR / "weights.json"

# ── Feature dimensions ───────────────────────────────────────────────────
# 20 dimensions: 17 segmental + 3 tonal.

FEATURE_NAMES: tuple[str, ...] = (
    "syllabic", "sonorant", "continuant", "nasal", "lateral",
    "sibilant", "approximant",
    "labial", "coronal", "dorsal", "anterior",
    "voice", "aspirated", "glottalized",
    "high", "back", "round",
    "tone_onset", "tone_mid", "tone_offset",
)

GEOMETRY_MAP: dict[str, str] = {
    "syllabic": "Manner", "sonorant": "Manner", "continuant": "Manner",
    "nasal": "Manner", "lateral": "Manner", "sibilant": "Manner",
    "approximant": "Manner",
    "labial": "Labial", "coronal": "Coronal", "dorsal": "Dorsal",
    "anterior": "Coronal",
    "voice": "Laryngeal", "aspirated": "Laryngeal",
    "glottalized": "Laryngeal",
    "high": "Dorsal", "back": "Dorsal", "round": "Labial",
    "tone_onset": "TonalOnset", "tone_mid": "TonalMid",
    "tone_offset": "TonalOffset",
}

# ── Sound classes (24 classes: SCA + data-driven refinements) ────────────
#
# Changes from SCA:
#   Split H  → Hf (h, ɦ, ħ, ʕ)  +  Hq (ʔ, ʡ)     [h vs ʔ ratio=1.0]
#   Split K  → K  (k, g, ɡ, ɠ)  +  Q  (q, ɢ, ʛ)   [k-q ratio=0.42]
#   Split N  → N  (n, ɳ, ɲ)     +  Ng (ŋ, ɴ)       [n-ŋ ratio=0.65]
#   Split I  → I  (i, ɪ)        +  Ic (ɨ, ɯ)        [i-ɨ ratio=0.29]
#   Split A  → A  (a, ɶ)        +  Ab (ɑ)            [a-ɑ ratio=0.37]
#   Merge U+Y → V  (u, ʊ, ʉ, y, ʏ)                  [U-Y ratio=1.80]
#   Merge B+W → F  (f, v, ɸ, β, w, ʋ, ⱱ, ʙ)        [B-W ratio=3.97]
#   Keep O as separate (ɒ only in SCA; we add o, ɔ, ø, œ, ɞ, ɵ)

_SCA_CLASSES: dict[str, set[str]] = {
    "P":  {"p", "b", "ɓ"},
    "T":  {"t", "d", "ʈ", "ɖ", "ɗ"},
    "K":  {"k", "g", "ɡ", "ɠ"},
    "Q":  {"q", "ɢ", "ʛ"},
    "C":  {"t͡s", "d͡z", "t͡ʃ", "d͡ʒ", "t͡ɕ", "d͡ʑ", "c", "ɟ",
           "t͡ʂ", "d͡ʐ", "ʄ"},
    "S":  {"s", "z", "ʃ", "ʒ", "ʂ", "ʐ", "ɕ", "ʑ", "ç", "ʝ", "ɧ"},
    "F":  {"ɸ", "β", "f", "v", "ʙ", "w", "ʋ", "ⱱ"},  # merged B+W
    "D":  {"θ", "ð"},
    "G":  {"x", "ɣ", "χ", "ʁ"},
    "Hf": {"h", "ɦ", "ħ", "ʕ"},  # fricative laryngeals
    "Hq": {"ʔ", "ʡ"},             # stop laryngeals
    "M":  {"m", "ɱ"},
    "N":  {"n", "ɳ", "ɲ"},
    "Ng": {"ŋ", "ɴ"},
    "R":  {"ɹ", "ɻ", "ʀ", "ɾ", "r", "ɽ", "ɺ"},
    "L":  {"l", "ɭ", "ʎ", "ʟ", "ɬ", "ɮ", "ɫ"},
    "J":  {"j", "ɥ", "ɰ"},
    "I":  {"i", "ɪ"},
    "Ic": {"ɨ", "ɯ"},              # central/back high unrounded
    "E":  {"e", "ɛ", "æ", "ɜ", "ɐ", "ʌ", "ə", "ɘ", "ɤ", "ɚ"},
    "A":  {"a", "ɶ"},
    "Ab": {"ɑ"},                    # back open
    "V":  {"u", "ʊ", "ʉ", "y", "ʏ"},  # merged U+Y
    "O":  {"o", "ɔ", "ɒ", "ø", "œ", "ɞ", "ɵ"},
}

# Ordered list of class names (for matrix indexing)
CLASS_NAMES: tuple[str, ...] = tuple(sorted(_SCA_CLASSES.keys()))
N_CLASSES = len(CLASS_NAMES)

# ── Prototype feature vectors per class ──────────────────────────────────

def _p(  # noqa: PLR0913
    syl: float, son: float, cnt: float, nas: float, lat: float,
    sib: float, apx: float, lab: float, cor: float, dor: float,
    ant: float, voi: float, asp: float, glo: float,
    hi: float, bk: float, rnd: float,
) -> dict[str, float]:
    """Build a prototype vector from positional args."""
    return {
        "syllabic": syl, "sonorant": son, "continuant": cnt,
        "nasal": nas, "lateral": lat, "sibilant": sib,
        "approximant": apx, "labial": lab, "coronal": cor,
        "dorsal": dor, "anterior": ant, "voice": voi,
        "aspirated": asp, "glottalized": glo,
        "high": hi, "back": bk, "round": rnd,
        "tone_onset": 0.0, "tone_mid": 0.0, "tone_offset": 0.0,
    }

_CLASS_PROTOTYPES: dict[str, dict[str, float]] = {
    # fmt: off
    #         syl son cnt nas lat sib apx lab cor dor ant voi asp glo hi  bk rnd
    "P":  _p(-1, -1, -1,  0,  0,  0,  0,  1,  0,  0,  0, -1,  0,  0,  0,  0,  0),
    "T":  _p(-1, -1, -1,  0,  0,  0,  0,  0,  1,  0,  1, -1,  0,  0,  0,  0,  0),
    "K":  _p(-1, -1, -1,  0,  0,  0,  0,  0,  0,  1,  0, -1,  0,  0,  0,  0,  0),
    "Q":  _p(-1, -1, -1,  0,  0,  0,  0,  0,  0,  1,  0, -1,  0,  0,  0,  1,  0),
    "C":  _p(-1, -1, -1,  0,  0,  1,  0,  0,  1,  0,  0, -1,  0,  0,  0,  0,  0),
    "S":  _p(-1, -1,  1,  0,  0,  1,  0,  0,  1,  0,  0, -1,  0,  0,  0,  0,  0),
    "F":  _p(-1, -1,  1,  0,  0,  0,  0,  1,  0,  0,  0, -1,  0,  0,  0,  0,  0),
    "D":  _p(-1, -1,  1,  0,  0,  0,  0,  0,  1,  0,  1, -1,  0,  0,  0,  0,  0),
    "G":  _p(-1, -1,  1,  0,  0,  0,  0,  0,  0,  1,  0, -1,  0,  0,  0,  0,  0),
    "Hf": _p(-1, -1,  1,  0,  0,  0,  0,  0,  0,  0,  0, -1,  0,  0,  0,  0,  0),
    "Hq": _p(-1, -1, -1,  0,  0,  0,  0,  0,  0,  0,  0, -1,  0,  1,  0,  0,  0),
    "M":  _p(-1,  1, -1,  1,  0,  0,  0,  1,  0,  0,  0,  1,  0,  0,  0,  0,  0),
    "N":  _p(-1,  1, -1,  1,  0,  0,  0,  0,  1,  0,  1,  1,  0,  0,  0,  0,  0),
    "Ng": _p(-1,  1, -1,  1,  0,  0,  0,  0,  0,  1,  0,  1,  0,  0,  0,  0,  0),
    "R":  _p(-1,  1,  1,  0,  0,  0,  1,  0,  1,  0,  1,  1,  0,  0,  0,  0,  0),
    "L":  _p(-1,  1,  1,  0,  1,  0,  1,  0,  1,  0,  1,  1,  0,  0,  0,  0,  0),
    "J":  _p(-1,  1,  1,  0,  0,  0,  1,  0,  0,  1,  0,  1,  0,  0,  1, -1,  0),
    "I":  _p( 1,  1,  1,  0,  0,  0,  0,  0,  0,  1,  0,  1,  0,  0,  1, -1, -1),
    "Ic": _p( 1,  1,  1,  0,  0,  0,  0,  0,  0,  1,  0,  1,  0,  0,  1,  0, -1),
    "E":  _p( 1,  1,  1,  0,  0,  0,  0,  0,  0,  1,  0,  1,  0,  0,  0,  0, -1),
    "A":  _p( 1,  1,  1,  0,  0,  0,  0,  0,  0,  1,  0,  1,  0,  0, -1,  0, -1),
    "Ab": _p( 1,  1,  1,  0,  0,  0,  0,  0,  0,  1,  0,  1,  0,  0, -1,  1, -1),
    "V":  _p( 1,  1,  1,  0,  0,  0,  0,  0,  0,  1,  0,  1,  0,  0,  1,  0,  1),
    "O":  _p( 1,  1,  1,  0,  0,  0,  0,  0,  0,  1,  0,  1,  0,  0,  0,  1,  1),
    # fmt: on
}

# ── IPA base → class lookup ──────────────────────────────────────────────

_IPA_TO_CLASS: dict[str, str] = {}
for _cls, _segs in _SCA_CLASSES.items():
    for _seg in _segs:
        _IPA_TO_CLASS[_seg] = _cls

# ── Legacy IPA mappings ──────────────────────────────────────────────────

_LEGACY_MAP: dict[str, str] = {
    "ʧ": "t͡ʃ", "ʨ": "t͡ɕ", "ʦ": "t͡s", "ʣ": "d͡z",
    "ʤ": "d͡ʒ", "ʥ": "d͡ʑ",
    "ȵ": "ɲ",
    "ǝ": "ə",   # turned e → schwa
    "ʍ": "w",   # voiceless labial-velar → w (with devoicing)
    "ȶ": "t",   # legacy palatalized t
    "ł": "ɫ",   # barred l → dark l
}

# Characters that map IPA vowels used in Chinese dialectology
_SINITIC_VOWELS: dict[str, str] = {
    "ɿ": "ɨ",   # apical front → barred i
    "ʅ": "ɨ",   # apical back → barred i
}

# ── Modifier adjustments ─────────────────────────────────────────────────

_MODIFIER_ADJUSTMENTS: dict[str, dict[str, float]] = {
    "ʰ": {"aspirated": 1.0},
    "ʱ": {"aspirated": 1.0, "voice": 1.0},
    "ʼ": {"glottalized": 1.0},
    "ˀ": {"glottalized": 1.0},
    "\u0303": {"nasal": 1.0},     # combining tilde
    "ⁿ": {"nasal": 1.0},
    "\u0325": {"voice": -1.0},    # combining ring below
    "\u032C": {"voice": 1.0},     # combining caron below
    "ˠ": {"dorsal": 1.0},
    "ʷ": {"labial": 1.0, "round": 1.0},
    "ʲ": {"dorsal": 1.0, "high": 1.0},
    "ˤ": {},
    "ː": {},
}

# Prefix characters to strip before classification
_STRIP_PREFIXES: set[str] = {
    "ˈ", "ˌ",  # stress marks
    "ˀ",       # preglottalised
}

# Prenasalisation prefixes (superscript nasals)
_PRENASAL_PREFIXES: set[str] = {"ⁿ", "ᵐ", "ᵑ"}

# Pre-aspiration prefix
_PREASP_PREFIX: str = "ʰ"

# ── Chao digit → tone value mapping ──────────────────────────────────────

_CHAO_VALUE: dict[str, float] = {
    "5": 1.0, "4": 0.5, "3": 0.0, "2": -0.5, "1": -1.0,
}


# ── Feature extraction ───────────────────────────────────────────────────

def _preprocess(grapheme: str) -> str | None:
    """Normalise and clean a grapheme before classification."""
    normalized = normalize_input_grapheme(grapheme)
    if not normalized:
        return None

    # Handle slash notation (e.g. "ќ/kʼ" → take right side)
    if "/" in normalized:
        parts = normalized.split("/")
        normalized = parts[-1]
        if not normalized:
            return None

    # Apply legacy IPA replacements
    for old, new in _LEGACY_MAP.items():
        normalized = normalized.replace(old, new)
    for old, new in _SINITIC_VOWELS.items():
        normalized = normalized.replace(old, new)

    # Strip stress and other prefixes
    while normalized and normalized[0] in _STRIP_PREFIXES:
        normalized = normalized[1:]

    # Strip prenasalisation prefixes
    for prefix in _PRENASAL_PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break

    # Strip pre-aspiration
    if normalized.startswith(_PREASP_PREFIX) and len(normalized) > 1:
        rest = normalized[len(_PREASP_PREFIX):]
        # Only strip if the remainder starts with a consonant
        if rest and rest[0] not in "aeiouɑɛɔəɨɪʊʉæøœɒɤɯɜɐʌɵɞɶʏ":
            normalized = rest

    return normalized if normalized else None


def _classify_segment(grapheme: str) -> dict[str, float] | None:
    """Map an IPA grapheme to a feature vector via class + modifiers."""
    normalized = _preprocess(grapheme)
    if not normalized:
        return None

    nfd = unicodedata.normalize("NFD", normalized)

    # Try multi-char base first (affricates with tie bar)
    base = None
    cls = None
    remainder = nfd

    for tie in ("͡", "͜"):
        if tie in nfd:
            tie_pos = nfd.index(tie)
            candidate = nfd[:tie_pos + 2]
            if candidate in _IPA_TO_CLASS:
                cls = _IPA_TO_CLASS[candidate]
                base = candidate
                remainder = nfd[len(candidate):]
                break

    # Single-char base lookup
    if cls is None and nfd:
        first = nfd[0]
        if first in _IPA_TO_CLASS:
            cls = _IPA_TO_CLASS[first]
            base = first
            remainder = nfd[1:]

    if cls is None:
        return None

    # Start from class prototype
    vector = dict(_CLASS_PROTOTYPES[cls])

    # Apply voicing from specific IPA base
    voiced = {
        "b", "d", "ɖ", "g", "ɡ", "ɢ", "ɟ", "ɓ", "ɗ", "ɠ", "ʛ",
        "d͡z", "d͡ʒ", "d͡ʑ", "d͡ʐ",
        "z", "ʒ", "ʐ", "ʑ", "ʝ",
        "β", "v", "ð", "ɣ", "ʁ", "ɦ", "ʕ", "ɮ",
    }
    voiceless = {
        "p", "t", "ʈ", "k", "q", "c",
        "t͡s", "t͡ʃ", "t͡ɕ", "t͡ʂ",
        "s", "ʃ", "ʂ", "ɕ", "ç",
        "ɸ", "f", "θ", "x", "χ", "h", "ʔ", "ħ", "ɬ",
    }
    if base in voiced:
        vector["voice"] = 1.0
    elif base in voiceless:
        vector["voice"] = -1.0

    # Implosives
    if base in {"ɓ", "ɗ", "ɠ", "ʛ", "ʄ"}:
        vector["glottalized"] = 1.0

    # Vowel refinements
    vowel_classes = {"I", "Ic", "E", "A", "Ab", "V", "O"}
    if cls in vowel_classes:
        _refine_vowel(base, vector)

    # Apply modifier adjustments
    for char in remainder:
        adj = _MODIFIER_ADJUSTMENTS.get(char)
        if adj:
            vector.update(adj)

    # Tone from Chao superscript digits
    _apply_tone(normalized, vector)

    return vector


def _refine_vowel(base: str | None, vector: dict[str, float]) -> None:
    """Refine vowel features for specific IPA symbols."""
    if base is None:
        return
    height_map = {
        "i": 1.0, "ɪ": 0.7, "ɨ": 1.0, "ɯ": 1.0,
        "u": 1.0, "ʊ": 0.7, "ʉ": 1.0,
        "y": 1.0, "ʏ": 0.7,
        "e": 0.5, "ø": 0.5, "ɘ": 0.5, "ɤ": 0.5, "o": 0.5,
        "ə": 0.0, "ɐ": -0.3,
        "ɛ": -0.5, "æ": -0.7, "ɜ": -0.5, "ʌ": -0.5, "ɔ": -0.5,
        "œ": -0.5, "ɞ": -0.5, "ɵ": 0.5,
        "a": -1.0, "ɑ": -1.0, "ɶ": -1.0, "ɒ": -1.0,
    }
    back_map = {
        "i": -1.0, "ɪ": -0.7, "e": -1.0, "ɛ": -1.0, "æ": -1.0,
        "y": -1.0, "ʏ": -0.7, "ø": -1.0, "œ": -1.0, "ɶ": -1.0,
        "ɨ": 0.0, "ʉ": 0.0, "ɘ": 0.0, "ə": 0.0, "ɜ": 0.0,
        "ɐ": 0.0, "ɵ": 0.0, "ɞ": 0.0,
        "ɯ": 1.0, "ɤ": 1.0, "ʌ": 1.0,
        "u": 1.0, "ʊ": 1.0, "o": 1.0, "ɔ": 1.0, "ɑ": 1.0,
        "ɒ": 1.0, "a": 0.0,
    }
    round_map = {
        "y": 1.0, "ʏ": 1.0, "ø": 1.0, "œ": 1.0, "ɶ": 1.0,
        "ɵ": 1.0, "ɞ": 1.0,
        "u": 1.0, "ʊ": 1.0, "ʉ": 1.0, "o": 1.0, "ɔ": 1.0,
        "ɒ": 1.0,
    }
    if base in height_map:
        vector["high"] = height_map[base]
    if base in back_map:
        vector["back"] = back_map[base]
    if base in round_map:
        vector["round"] = round_map[base]
    elif base in {
        "i", "ɪ", "ɨ", "ɯ", "e", "ɛ", "æ", "ɘ", "ɤ",
        "ə", "ɐ", "ɜ", "ʌ", "a", "ɑ",
    }:
        vector["round"] = -1.0


def _apply_tone(grapheme: str, vector: dict[str, float]) -> None:
    """Extract trailing Chao superscript digits and set tone features.

    Uses continuous interpolation for the midpoint (no rounding).
    """
    sup_map = {
        "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5",
    }
    digits = []
    for ch in reversed(grapheme):
        if ch in sup_map:
            digits.append(sup_map[ch])
        else:
            break
    if not digits:
        return
    digits.reverse()
    tone_str = "".join(digits)
    onset_val = _CHAO_VALUE.get(tone_str[0], 0.0)
    vector["tone_onset"] = onset_val
    if len(tone_str) == 1:
        vector["tone_mid"] = onset_val
        vector["tone_offset"] = onset_val
    elif len(tone_str) == 2:
        offset_val = _CHAO_VALUE.get(tone_str[-1], 0.0)
        vector["tone_mid"] = (onset_val + offset_val) / 2.0
        vector["tone_offset"] = offset_val
    else:
        # 3+ digits: mid = second digit (explicit)
        vector["tone_mid"] = _CHAO_VALUE.get(tone_str[1], 0.0)
        vector["tone_offset"] = _CHAO_VALUE.get(tone_str[-1], 0.0)


def classify_to_class(grapheme: str) -> str | None:
    """Return the class label for a grapheme, or None."""
    normalized = _preprocess(grapheme)
    if not normalized:
        return None
    nfd = unicodedata.normalize("NFD", normalized)
    for tie in ("͡", "͜"):
        if tie in nfd:
            tie_pos = nfd.index(tie)
            candidate = nfd[:tie_pos + 2]
            if candidate in _IPA_TO_CLASS:
                return _IPA_TO_CLASS[candidate]
    if nfd and nfd[0] in _IPA_TO_CLASS:
        return _IPA_TO_CLASS[nfd[0]]
    return None


# ── Weights loading ──────────────────────────────────────────────────────

@cache
def _load_weights() -> dict:
    """Load pre-trained weights from JSON."""
    if not _WEIGHTS_FILE.exists():
        return {
            "dimension_weights": {n: 1.0 for n in FEATURE_NAMES},
            "class_costs": {},
        }
    with _WEIGHTS_FILE.open(encoding="utf-8") as f:
        return json.load(f)


# ── Node inverse depths ──────────────────────────────────────────────────

@cache
def _compute_node_inv_depths() -> dict[str, float]:
    """Compute 1/depth for each feature dimension based on geometry."""
    from merkmal.geometry import DEFAULT_GEOMETRY, GeometryNode

    node_depth: dict[str, int] = {}

    def _walk(node: object, depth: int) -> None:
        node_depth[node.name] = depth  # type: ignore[union-attr]
        if isinstance(node, GeometryNode):
            for child in node.children:
                _walk(child, depth + 1)

    _walk(DEFAULT_GEOMETRY, 1)

    inv_depths: dict[str, float] = {}
    total = 0.0
    for name in FEATURE_NAMES:
        node_name = GEOMETRY_MAP[name]
        depth = node_depth.get(node_name, 3)
        inv_depths[name] = 1.0 / depth
        total += inv_depths[name]

    for name in inv_depths:
        inv_depths[name] /= total

    return inv_depths


# ── Distance functions ───────────────────────────────────────────────────

def _feature_distance(
    va: dict[str, float],
    vb: dict[str, float],
    dim_weights: dict[str, float],
    node_inv_depths: dict[str, float],
) -> float:
    """Weighted feature-vector distance."""
    total = 0.0
    for name in FEATURE_NAMES:
        a_val = va.get(name, 0.0)
        b_val = vb.get(name, 0.0)
        if a_val == 0.0 and b_val == 0.0:
            continue
        diff = abs(a_val - b_val)
        w = dim_weights.get(name, 1.0) * node_inv_depths.get(
            name, 1.0 / len(FEATURE_NAMES),
        )
        total += diff * w
    return total


def segment_cost(
    grapheme_a: str,
    grapheme_b: str,
    dim_weights: dict[str, float],
    class_costs: dict[str, float],
    node_inv_depths: dict[str, float],
    alpha: float = 0.5,
) -> float:
    """Combined class-pair + feature distance for two graphemes.

    Returns alpha * class_cost + (1-alpha) * feature_distance.
    The alpha parameter and class_costs are learned during training.
    """
    va = _classify_segment(grapheme_a)
    vb = _classify_segment(grapheme_b)
    if va is None or vb is None:
        return 1.0

    cls_a = classify_to_class(grapheme_a)
    cls_b = classify_to_class(grapheme_b)

    # Class-pair cost (symmetric)
    if cls_a is not None and cls_b is not None:
        key = f"{min(cls_a,cls_b)}:{max(cls_a,cls_b)}"
        class_cost = class_costs.get(key, 1.0 if cls_a != cls_b else 0.0)
    else:
        class_cost = 1.0

    # Feature distance
    feat_dist = _feature_distance(va, vb, dim_weights, node_inv_depths)

    return alpha * class_cost + (1.0 - alpha) * feat_dist


# ── System class ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ClassFeatFeatureSystem:
    """SCA-inspired feature system with learned class costs."""

    @property
    def name(self) -> str:
        return "classfeat"

    @property
    def representation_kind(self) -> str:
        return "valued"

    @cached_property
    def _weights(self) -> dict:
        return _load_weights()

    @cached_property
    def _dimension_weights(self) -> dict[str, float]:
        return self._weights.get(
            "dimension_weights",
            {n: 1.0 for n in FEATURE_NAMES},
        )

    @cached_property
    def _class_costs(self) -> dict[str, float]:
        return self._weights.get("class_costs", {})

    @cached_property
    def _alpha(self) -> float:
        return self._weights.get("alpha", 0.5)

    @cached_property
    def _node_inv_depths(self) -> dict[str, float]:
        return _compute_node_inv_depths()

    def list_graphemes(self) -> tuple[str, ...]:
        return tuple(sorted(_IPA_TO_CLASS.keys()))

    def grapheme_to_representation(
        self, grapheme: str,
    ) -> ValuedFeatures | None:
        vector = _classify_segment(grapheme)
        if vector is None:
            return None
        state_map = {}
        for name, val in vector.items():
            if val > 0:
                state_map[name] = FeatureState.POSITIVE
            elif val < 0:
                state_map[name] = FeatureState.NEGATIVE
            else:
                state_map[name] = FeatureState.DOT
        return ValuedFeatures(values=state_map)

    def grapheme_to_features(
        self, grapheme: str,
    ) -> frozenset[str] | None:
        rep = self.grapheme_to_representation(grapheme)
        if rep is None:
            return None
        return frozenset(
            f"{name}={state.value}" for name, state in rep.values.items()
        )

    def features_to_grapheme(self, features: object) -> str | None:
        return None

    def is_class(self, grapheme: str) -> bool:
        return False

    def class_representation(
        self, grapheme: str,
    ) -> ValuedFeatures | None:
        return None

    def class_features(
        self, grapheme: str,
    ) -> frozenset[str] | None:
        return None

    def add_features(
        self, base: frozenset[str], added: frozenset[str],
    ) -> frozenset[str]:
        msg = "Set-based add_features not meaningful for ClassFeat."
        raise NotImplementedError(msg)

    def matches(self, pattern: object, target: object) -> bool:
        if isinstance(pattern, ValuedFeatures):
            query = pattern.values
        elif isinstance(pattern, Mapping):
            query = _normalize_valued_query(pattern)
        else:
            msg = "ClassFeat requires dict or ValuedFeatures queries."
            raise NotImplementedError(msg)
        if not isinstance(target, ValuedFeatures):
            msg = "ClassFeat matching requires ValuedFeatures targets."
            raise NotImplementedError(msg)
        return all(
            target.values.get(key) == value
            for key, value in query.items()
        )

    def partial_match(
        self, pattern: frozenset[str], target: frozenset[str],
    ) -> bool:
        msg = "Set-based partial_match not meaningful for ClassFeat."
        raise NotImplementedError(msg)

    def feature_distance(self, feat_a: str, feat_b: str) -> float:
        return 0.0 if feat_a == feat_b else 1.0

    def segment_distance(
        self, a: object, b: object,
        node_weights: dict[str, float] | str | None = None,
    ) -> float:
        if not isinstance(a, ValuedFeatures) or not isinstance(
            b, ValuedFeatures,
        ):
            msg = "ClassFeat segment_distance requires ValuedFeatures."
            raise NotImplementedError(msg)
        va = _vec_from_rep(a)
        vb = _vec_from_rep(b)
        return _feature_distance(
            va, vb, self._dimension_weights, self._node_inv_depths,
        )

    def sound_distance(
        self, feats_a: frozenset[str], feats_b: frozenset[str],
        node_weights: dict[str, float] | str | None = None,
    ) -> float:
        msg = "Set-based sound_distance not meaningful for ClassFeat."
        raise NotImplementedError(msg)

    def grapheme_vector(
        self, grapheme: str,
    ) -> dict[str, float] | None:
        """Return the raw numeric feature vector."""
        return _classify_segment(grapheme)

    def grapheme_cost(
        self, grapheme_a: str, grapheme_b: str,
    ) -> float:
        """Combined class + feature cost for the eval/training path."""
        return segment_cost(
            grapheme_a, grapheme_b,
            self._dimension_weights, self._class_costs,
            self._node_inv_depths, self._alpha,
        )


def _vec_from_rep(rep: ValuedFeatures) -> dict[str, float]:
    """Convert a ValuedFeatures back to a numeric dict."""
    result: dict[str, float] = {}
    for name, state in rep.values.items():
        if state == FeatureState.POSITIVE:
            result[name] = 1.0
        elif state == FeatureState.NEGATIVE:
            result[name] = -1.0
        else:
            result[name] = 0.0
    return result
