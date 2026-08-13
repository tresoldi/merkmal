"""Native C-backed Python wrapper for merkmal."""

from __future__ import annotations

from typing import cast

__version__ = "0.7.0"

try:
    from merkmal import _native as _native  # type: ignore[attr-defined]
except ImportError as exc:  # pragma: no cover - exercised before extension build
    raise ImportError(
        "merkmal requires its native C extension. Install the package from a built "
        "wheel or run `python -m pip install -e .` from the repository root."
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
system_segment_ipa = _native.system_segment_ipa
split_tone = _native.split_tone


class Registry:
    """Owns built-in systems and caller-supplied categorical models.

    The registry keeps the native handle alive for the lifetime of this
    object. Methods raise ``KeyError`` for unknown systems and ``ValueError``
    for invalid or unknown graphemes.
    """

    def __init__(self) -> None:
        """Create a registry containing the built-in systems."""
        self._handle = _native._registry_new()

    def add_model_text(self, model_text: str) -> None:
        """Add a categorical model using the documented text format."""
        _native._registry_add_model_text(self._handle, model_text)

    def list_systems(self) -> list[str]:
        """Return the names of built-in and registered systems."""
        return cast("list[str]", _native._registry_list_systems(self._handle))

    def get_features(self, grapheme: str, *, system: str = "descriptive") -> frozenset[str]:
        """Return the feature set for ``grapheme`` in ``system``."""
        return cast(
            "frozenset[str]",
            _native._registry_get_features(self._handle, system, grapheme),
        )

    def is_segment(self, grapheme: str, *, system: str = "descriptive") -> bool:
        """Return whether ``grapheme`` is a valid segment in ``system``."""
        return cast("bool", _native._registry_is_segment(self._handle, system, grapheme))

    def distance(
        self,
        a: str,
        b: str,
        *,
        system: str = "descriptive",
        node_weights: str | None = None,
    ) -> float:
        """Return the geometry-weighted distance between two graphemes."""
        return cast(
            "float",
            _native._registry_distance(self._handle, system, a, b, node_weights),
        )

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
    "split_tone",
    "system_segment_ipa",
]
