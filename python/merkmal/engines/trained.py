"""Trained feature engine (classfeat).

Classifies IPA segments into data-refined sound classes, then computes
distance using a learned class-pair cost matrix plus per-dimension
feature weights.
"""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING, ClassVar

from merkmal.geometry import GeometryNode
from merkmal.grapheme import normalize_input_grapheme
from merkmal.representations import (
    FeatureState,
    ValuedFeatures,
    _normalize_valued_query,
)

if TYPE_CHECKING:
    from merkmal.geometry import Geometry
    from merkmal.model import ModelConfig


@dataclass
class TrainedEngine:
    """ClassFeat engine: trained sound classes + feature-weighted distance."""

    config: ModelConfig
    geometry: Geometry

    representation_kind: str = "valued"

    @property
    def name(self) -> str:
        return self.config.name

    @cached_property
    def _feature_names(self) -> tuple[str, ...]:
        return tuple(self.config.raw.get("feature_names", []))

    @cached_property
    def _geometry_map(self) -> dict[str, str]:
        return self.config.raw.get("geometry_map", {})

    @cached_property
    def _sound_classes(self) -> dict[str, set[str]]:
        raw = self.config.raw.get("sound_classes", {})
        return {cls: set(members) for cls, members in raw.items()}

    @cached_property
    def _class_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._sound_classes.keys()))

    @cached_property
    def _ipa_to_class(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for cls, segs in self._sound_classes.items():
            for seg in segs:
                result[seg] = cls
        return result

    @cached_property
    def _class_prototypes(self) -> dict[str, dict[str, float]]:
        return self.config.raw.get("class_prototypes", {})

    @cached_property
    def _alpha(self) -> float:
        return self.config.raw.get("alpha", 0.5)

    @cached_property
    def _weights(self) -> dict:
        weights_path = self.config.model_dir / "weights.json"
        if weights_path.exists():
            with weights_path.open(encoding="utf-8") as f:
                return json.load(f)
        return {
            "dimension_weights": {n: 1.0 for n in self._feature_names},
            "class_costs": {},
        }

    @cached_property
    def _dimension_weights(self) -> dict[str, float]:
        return self._weights.get(
            "dimension_weights",
            {n: 1.0 for n in self._feature_names},
        )

    @cached_property
    def _class_costs(self) -> dict[str, float]:
        return self._weights.get("class_costs", {})

    @cached_property
    def _node_inv_depths(self) -> dict[str, float]:
        node_depth: dict[str, int] = {}

        def _walk(node: object, depth: int) -> None:
            node_depth[node.name] = depth  # type: ignore[union-attr]
            if isinstance(node, GeometryNode):
                for child in node.children:
                    _walk(child, depth + 1)

        _walk(self.geometry.tree, 1)

        inv_depths: dict[str, float] = {}
        total = 0.0
        for feat_name in self._feature_names:
            node_name = self._geometry_map.get(feat_name, "")
            depth = node_depth.get(node_name, 3)
            inv_depths[feat_name] = 1.0 / depth
            total += inv_depths[feat_name]

        for feat_name in inv_depths:
            inv_depths[feat_name] /= total

        return inv_depths

    # ── Legacy IPA and modifier handling ────────────────────────────────

    _LEGACY_MAP: ClassVar[dict[str, str]] = {
        "ʧ": "t͡ʃ", "ʨ": "t͡ɕ", "ʦ": "t͡s", "ʣ": "d͡z",
        "ʤ": "d͡ʒ", "ʥ": "d͡ʑ",
        "ȵ": "ɲ", "ǝ": "ə", "ʍ": "w", "ȶ": "t", "ł": "ɫ",
    }

    _SINITIC_VOWELS: ClassVar[dict[str, str]] = {"ɿ": "ɨ", "ʅ": "ɨ"}

    _MODIFIER_ADJUSTMENTS: ClassVar[dict[str, dict[str, float]]] = {
        "ʰ": {"aspirated": 1.0},
        "ʱ": {"aspirated": 1.0, "voice": 1.0},
        "ʼ": {"glottalized": 1.0},
        "ˀ": {"glottalized": 1.0},
        "̃": {"nasal": 1.0},
        "ⁿ": {"nasal": 1.0},
        "̥": {"voice": -1.0},
        "̬": {"voice": 1.0},
        "ˠ": {"dorsal": 1.0},
        "ʷ": {"labial": 1.0, "round": 1.0},
        "ʲ": {"dorsal": 1.0, "high": 1.0},
        "ˤ": {},
        "ː": {},
    }

    _STRIP_PREFIXES: ClassVar[set[str]] = {"ˈ", "ˌ", "ˀ"}
    _PRENASAL_PREFIXES: ClassVar[set[str]] = {"ⁿ", "ᵐ", "ᵑ"}
    _PREASP_PREFIX: ClassVar[str] = "ʰ"

    _CHAO_VALUE: ClassVar[dict[str, float]] = {
        "5": 1.0, "4": 0.5, "3": 0.0, "2": -0.5, "1": -1.0,
    }

    _VOWEL_CHARS: ClassVar[str] = "aeiouɑɛɔəɨɪʊʉæøœɒɤɯɜɐʌɵɞɶʏ"

    def _preprocess(self, grapheme: str) -> str | None:
        normalized = normalize_input_grapheme(grapheme)
        if not normalized:
            return None
        if "/" in normalized:
            parts = normalized.split("/")
            normalized = parts[-1]
            if not normalized:
                return None
        for old, new in self._LEGACY_MAP.items():
            normalized = normalized.replace(old, new)
        for old, new in self._SINITIC_VOWELS.items():
            normalized = normalized.replace(old, new)
        while normalized and normalized[0] in self._STRIP_PREFIXES:
            normalized = normalized[1:]
        for prefix in self._PRENASAL_PREFIXES:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
                break
        if normalized.startswith(self._PREASP_PREFIX) and len(normalized) > 1:
            rest = normalized[len(self._PREASP_PREFIX):]
            if rest and rest[0] not in self._VOWEL_CHARS:
                normalized = rest
        return normalized if normalized else None

    def _classify_segment(self, grapheme: str) -> dict[str, float] | None:
        normalized = self._preprocess(grapheme)
        if not normalized:
            return None
        nfd = unicodedata.normalize("NFD", normalized)
        base = None
        cls = None
        remainder = nfd

        for tie in ("͡", "͜"):
            if tie in nfd:
                tie_pos = nfd.index(tie)
                candidate = nfd[:tie_pos + 2]
                if candidate in self._ipa_to_class:
                    cls = self._ipa_to_class[candidate]
                    base = candidate
                    remainder = nfd[len(candidate):]
                    break

        if cls is None and nfd:
            first = nfd[0]
            if first in self._ipa_to_class:
                cls = self._ipa_to_class[first]
                base = first
                remainder = nfd[1:]

        if cls is None:
            return None

        vector = dict(self._class_prototypes.get(cls, {}))
        for name in self._feature_names:
            vector.setdefault(name, 0.0)

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

        if base in {"ɓ", "ɗ", "ɠ", "ʛ", "ʄ"}:
            vector["glottalized"] = 1.0

        vowel_classes = {"I", "Ic", "E", "A", "Ab", "V", "O"}
        if cls in vowel_classes:
            self._refine_vowel(base, vector)

        for char in remainder:
            adj = self._MODIFIER_ADJUSTMENTS.get(char)
            if adj:
                vector.update(adj)

        self._apply_tone(normalized, vector)
        return vector

    def _refine_vowel(self, base: str | None, vector: dict[str, float]) -> None:
        if base is None:
            return
        height_map = {
            "i": 1.0, "ɪ": 0.7, "ɨ": 1.0, "ɯ": 1.0,
            "u": 1.0, "ʊ": 0.7, "ʉ": 1.0, "y": 1.0, "ʏ": 0.7,
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
            "u": 1.0, "ʊ": 1.0, "ʉ": 1.0, "o": 1.0, "ɔ": 1.0, "ɒ": 1.0,
        }
        unround = {
            "i", "ɪ", "ɨ", "ɯ", "e", "ɛ", "æ", "ɘ", "ɤ",
            "ə", "ɐ", "ɜ", "ʌ", "a", "ɑ",
        }
        if base in height_map:
            vector["high"] = height_map[base]
        if base in back_map:
            vector["back"] = back_map[base]
        if base in round_map:
            vector["round"] = round_map[base]
        elif base in unround:
            vector["round"] = -1.0

    def _apply_tone(self, grapheme: str, vector: dict[str, float]) -> None:
        sup_map = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5"}
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
        onset_val = self._CHAO_VALUE.get(tone_str[0], 0.0)
        vector["tone_onset"] = onset_val
        if len(tone_str) == 1:
            vector["tone_mid"] = onset_val
            vector["tone_offset"] = onset_val
        elif len(tone_str) == 2:
            offset_val = self._CHAO_VALUE.get(tone_str[-1], 0.0)
            vector["tone_mid"] = (onset_val + offset_val) / 2.0
            vector["tone_offset"] = offset_val
        else:
            vector["tone_mid"] = self._CHAO_VALUE.get(tone_str[1], 0.0)
            vector["tone_offset"] = self._CHAO_VALUE.get(tone_str[-1], 0.0)

    def _classify_to_class(self, grapheme: str) -> str | None:
        normalized = self._preprocess(grapheme)
        if not normalized:
            return None
        nfd = unicodedata.normalize("NFD", normalized)
        for tie in ("͡", "͜"):
            if tie in nfd:
                tie_pos = nfd.index(tie)
                candidate = nfd[:tie_pos + 2]
                if candidate in self._ipa_to_class:
                    return self._ipa_to_class[candidate]
        if nfd and nfd[0] in self._ipa_to_class:
            return self._ipa_to_class[nfd[0]]
        return None

    def _feature_distance(
        self, va: dict[str, float], vb: dict[str, float],
    ) -> float:
        total = 0.0
        for feat_name in self._feature_names:
            a_val = va.get(feat_name, 0.0)
            b_val = vb.get(feat_name, 0.0)
            if a_val == 0.0 and b_val == 0.0:
                continue
            diff = abs(a_val - b_val)
            w = self._dimension_weights.get(feat_name, 1.0) * self._node_inv_depths.get(
                feat_name, 1.0 / len(self._feature_names),
            )
            total += diff * w
        return total

    # ── FeatureSystem protocol ──────────────────────────────────────────

    def list_graphemes(self) -> tuple[str, ...]:
        return tuple(sorted(self._ipa_to_class.keys()))

    def grapheme_to_representation(self, grapheme: str) -> ValuedFeatures | None:
        vector = self._classify_segment(grapheme)
        if vector is None:
            return None
        state_map = {}
        for feat_name, val in vector.items():
            if val > 0:
                state_map[feat_name] = FeatureState.POSITIVE
            elif val < 0:
                state_map[feat_name] = FeatureState.NEGATIVE
            else:
                state_map[feat_name] = FeatureState.DOT
        return ValuedFeatures(values=state_map)

    def grapheme_to_features(self, grapheme: str) -> frozenset[str] | None:
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

    def class_representation(self, grapheme: str) -> ValuedFeatures | None:
        return None

    def class_features(self, grapheme: str) -> frozenset[str] | None:
        return None

    def add_features(self, base: frozenset[str], added: frozenset[str]) -> frozenset[str]:
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

    def partial_match(self, pattern: frozenset[str], target: frozenset[str]) -> bool:
        msg = "Set-based partial_match not meaningful for ClassFeat."
        raise NotImplementedError(msg)

    def feature_distance(self, feat_a: str, feat_b: str) -> float:
        return 0.0 if feat_a == feat_b else 1.0

    def segment_distance(
        self, a: object, b: object,
        node_weights: dict[str, float] | str | None = None,
    ) -> float:
        if not isinstance(a, ValuedFeatures) or not isinstance(b, ValuedFeatures):
            msg = "ClassFeat segment_distance requires ValuedFeatures."
            raise NotImplementedError(msg)
        va = _vec_from_rep(a)
        vb = _vec_from_rep(b)
        return self._feature_distance(va, vb)

    def sound_distance(
        self, feats_a: frozenset[str], feats_b: frozenset[str],
        node_weights: dict[str, float] | str | None = None,
    ) -> float:
        msg = "Set-based sound_distance not meaningful for ClassFeat."
        raise NotImplementedError(msg)

    def grapheme_vector(self, grapheme: str) -> dict[str, float] | None:
        return self._classify_segment(grapheme)

    def grapheme_cost(self, grapheme_a: str, grapheme_b: str) -> float:
        va = self._classify_segment(grapheme_a)
        vb = self._classify_segment(grapheme_b)
        if va is None or vb is None:
            return 1.0
        cls_a = self._classify_to_class(grapheme_a)
        cls_b = self._classify_to_class(grapheme_b)
        if cls_a is not None and cls_b is not None:
            key = f"{min(cls_a, cls_b)}:{max(cls_a, cls_b)}"
            class_cost = self._class_costs.get(key, 1.0 if cls_a != cls_b else 0.0)
        else:
            class_cost = 1.0
        feat_dist = self._feature_distance(va, vb)
        return self._alpha * class_cost + (1.0 - self._alpha) * feat_dist


def _vec_from_rep(rep: ValuedFeatures) -> dict[str, float]:
    result: dict[str, float] = {}
    for name, state in rep.values.items():
        if state == FeatureState.POSITIVE:
            result[name] = 1.0
        elif state == FeatureState.NEGATIVE:
            result[name] = -1.0
        else:
            result[name] = 0.0
    return result
