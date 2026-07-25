"""Native C-backed Python wrapper for merkmal."""

from __future__ import annotations

__version__ = "0.6.0"

try:
    from merkmal import _native as _native
except ImportError as exc:  # pragma: no cover - exercised before extension build
    raise ImportError(
        "merkmal requires its native C extension. Install the package from a built "
        "wheel or run `python -m pip install -e python` from the repository root."
    ) from exc

NativeError = _native.NativeError
distance = _native.distance
feature_distance = _native.feature_distance
get_features = _native.get_features
is_segment = _native.is_segment
list_systems = _native.list_systems
merge_tone_digits = _native.merge_tone_digits
normalize = _native.normalize
segment_ipa = _native.segment_ipa
segment_ipa_merged = _native.segment_ipa_merged


class Registry:
    """Owned native registry for built-ins plus caller-supplied model text."""

    def __init__(self) -> None:
        self._handle = _native._registry_new()

    def add_model_text(self, model_text: str) -> None:
        _native._registry_add_model_text(self._handle, model_text)

    def list_systems(self) -> list[str]:
        return _native._registry_list_systems(self._handle)

    def get_features(self, grapheme: str, *, system: str = "descriptive") -> frozenset[str]:
        return _native._registry_get_features(self._handle, system, grapheme)

    def is_segment(self, grapheme: str, *, system: str = "descriptive") -> bool:
        return _native._registry_is_segment(self._handle, system, grapheme)

    def distance(
        self,
        a: str,
        b: str,
        *,
        system: str = "descriptive",
        node_weights: str | None = None,
    ) -> float:
        return _native._registry_distance(self._handle, system, a, b, node_weights)

__all__ = [
    "NativeError",
    "Registry",
    "__version__",
    "distance",
    "feature_distance",
    "get_features",
    "is_segment",
    "list_systems",
    "merge_tone_digits",
    "normalize",
    "segment_ipa",
    "segment_ipa_merged",
]
